"""Compare candidate semantics and fixed-depth answers before/after optimization."""
import argparse
import copy
import json
import random
import statistics
import time
from pathlib import Path
from lab import GTP, ROOT, Referee, COLUMNS
from neural import digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before',type=Path,required=True); p.add_argument('--after',type=Path,default=ROOT/'target/release/goproverbs.exe')
    p.add_argument('--output',type=Path,required=True); args=p.parse_args()
    cases=json.loads((ROOT/'results/roadmap-20260921/corpus/positions.json').read_text())['positions']
    rng=random.Random(20260921)
    for size in [3,5,9,19]:
        ref=Referee(size,7.5); moves=[]
        for turn in range(min(size*size*2,70)):
            color='B' if turn%2==0 else 'W'
            options=[f'{COLUMNS[x]}{y+1}' for x in range(size) for y in range(size)]
            rng.shuffle(options)
            for move in options+['pass']:
                try: ref.play(color,move); break
                except AssertionError: continue
            moves.append([color,move])
            if ref.passes==2: break
            if turn%4==0: cases.append({'id':f'random-{size}-{turn}','size':size,'komi':7.5,'moves':copy.deepcopy(moves),'color':'W' if color=='B' else 'B'})
    rows=[]
    with GTP(args.before,search_mode='hybrid',nodes=1000000,depth=2,time_ms=10000,beam=12) as a, GTP(args.after,search_mode='hybrid',nodes=1000000,depth=2,time_ms=10000,beam=12) as b:
        for i,case in enumerate(cases):
            for gp in [a,b]:
                gp.command(f"boardsize {case['size']}"); gp.command(f"komi {case['komi']}")
                for color,move in case['moves']: gp.command(f'play {color} {move}')
            replies={}; timings={}
            for label,gp in ([('before',a),('after',b)] if i%2==0 else [('after',b),('before',a)]):
                start=time.perf_counter(); replies[label]=gp.command(f"gp-candidates {case['color']}"); timings[label]=(time.perf_counter()-start)*1000
            assert replies['before']==replies['after'],case['id']
            row={'id':case['id'],'candidate_outputs_identical':True,'ms':timings}
            if i in [0,1,2,3]:
                reports=[dict(f.split('=',1) for f in gp.command(f"gp-search {case['color']}").splitlines()[0].split()) for gp in [a,b]]
                for key in ['move','score','depth','nodes']: assert reports[0][key]==reports[1][key],(case['id'],key,reports)
                assert all(r['depth']=='2' for r in reports)
                row['fixed_depth_match']=reports
            rows.append(row)
    result={'before_sha256':digest(args.before),'after_sha256':digest(args.after),'cases':rows,
            'median_ms':{name:statistics.median(r['ms'][name] for r in rows) for name in ['before','after']},
            'total_ms':{name:sum(r['ms'][name] for r in rows) for name in ['before','after']}}
    args.output.write_text(json.dumps(result,indent=2),encoding='ascii'); print('Identical candidate lists:',len(rows)); print(result['total_ms'])


if __name__=='__main__': main()
