"""Summarize saved roadmap evidence without rerunning inference."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import statistics

from paired_summary import summarize


def timing(values):
    ordered=sorted(values)
    return {'n':len(values),'median_ms':statistics.median(values),
            'p95_ms':ordered[math.ceil(0.95*len(ordered))-1],'max_ms':max(values)} if values else None


def decisions(rows):
    result={}
    for mode in sorted({row['mode'] for row in rows}):
        selected=[row for row in rows if row['mode']==mode]
        result[mode]={
            'decisions':len(selected),
            'retained_external_round':sum('external_leaf=true' in row['trace']['report'] for row in selected),
            'completed_depths':dict(Counter(re.search(r' depth=(\d+)',row['trace']['report']).group(1) for row in selected)),
            'timing':timing([row['trace']['ms'] for row in selected]),
        }
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result={'probes':{},'backends':{},'arenas':{}}
    for path in sorted(args.root.glob('*/manifest.json')):
        manifest=json.loads(path.read_text())
        if manifest['status']!='complete': continue
        folder=path.parent
        task=manifest['settings']['task']
        if task=='probe': result['probes'][folder.name]=decisions(json.loads((folder/'probes.json').read_text()))
        elif task=='backend':
            result['backends'][folder.name]=timing([row['ms'] for row in json.loads((folder/'backend.json').read_text())])
        elif task=='arena':
            games=json.loads((folder/'games.json').read_text())
            rows=[]
            for game in games:
                source=folder/(f"{game['opening']}-{game['mode']}-{game['variant_color']}.jsonl")
                rows.extend(json.loads(line) for line in source.read_text().splitlines())
            result['arenas'][folder.name]={
                **summarize(games),'decisions':decisions(rows),
                'total_recorded_moves':sum(g['moves'] for g in games),
                'broker_queries':manifest['broker_queries'],'broker_errors':manifest['broker_errors']}
    optimization=json.loads((args.root/'optimization.json').read_text())
    result['optimization']={k:v for k,v in optimization.items() if k!='cases'}
    result['optimization']['identical_candidates']=len(optimization['cases'])
    result['optimization']['fixed_depth_matches']=sum('fixed_depth_match' in row for row in optimization['cases'])
    ablation=json.loads((args.root/'ablations/report.json').read_text())
    result['ablations']=[{'removed':row['removed'],'cases':len(row['evaluation']['fixtures']),
        'immediate_accepted':sum(case['baseline_pass'] for case in row['evaluation']['fixtures']),
        'search_accepted':sum(case['search_pass'] for case in row['evaluation']['fixtures'])} for row in ablation['ablations']]
    args.output.write_text(json.dumps(result,indent=2),encoding='ascii')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
