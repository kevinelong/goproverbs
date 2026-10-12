"""Pair-level score and a conservative bounded-mean uncertainty interval."""
import argparse
import json
import math
from pathlib import Path


def summarize(games):
    result={}
    for mode in sorted({g['mode'] for g in games}):
        rows=[g for g in games if g['mode']==mode]
        pairs={}
        for row in rows: pairs.setdefault(row['opening'],[]).append(row)
        scores=[]
        for pair in pairs.values():
            if len(pair)==2 and {r['variant_color'] for r in pair}=={'B','W'} and all(r['finished'] for r in pair):
                scores.append(sum(0.5 if r['result']=='0' else float(r['variant_won']) for r in pair)/2)
        mean=sum(scores)/len(scores) if scores else None
        radius=math.sqrt(math.log(40)/(2*len(scores))) if scores else None
        result[mode]={'games':len(rows),'wins':sum(r['variant_won'] for r in rows),
            'unfinished':sum(not r['finished'] for r in rows),'complete_pairs':len(scores),'mean_pair_score':mean,
            'conservative_95_interval': [max(0,mean-radius),min(1,mean+radius)] if scores else None}
    return {'variants':result,'method':'Hoeffding bounded-mean interval treating each complete opening pair as one independent observation.',
            'limitations':'Conditional on completed pairs and the sampled opening distribution; no Elo estimate. Incomplete pairs are counted and excluded from the score.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('games',type=Path); p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(); args.output.write_text(json.dumps(summarize(json.loads(args.games.read_text())),indent=2),encoding='ascii')
