"""Prepare one-feature removals; evaluate development labels without tuning."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from lab import ROOT, read_weights, evaluate_fixtures


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--evaluate',action='store_true')
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    weights=read_weights(ROOT/'profiles/baseline.weights')
    reports=[]
    for removed in [None]+[name for name,value in weights.items() if value != 0]:
        profile=args.output/((removed or 'baseline')+'.weights')
        changed=dict(weights)
        if removed: changed[removed]=0
        profile.write_text('# Single-feature ablation; not a recommended profile.\n'+''.join(f'{k}={v:g}\n' for k,v in changed.items()),encoding='ascii')
        row={'removed':removed,'profile':str(profile)}
        if args.evaluate:
            options=SimpleNamespace(exe=ROOT/'target/release/goproverbs.exe',profile=profile,
                fixtures=ROOT/'benchmarks/fixtures-19.json',nodes=5000,depth=3,beam=12,tactical=0,
                search='hybrid',shortlist=3,time_ms=200)
            row['evaluation']=evaluate_fixtures(options)
        reports.append(row)
    (args.output/'report.json').write_text(json.dumps({'note':'Development-label diagnostics only. No optimization or strength promotion.',
        'disabled_baseline_features':[k for k,v in weights.items() if v==0], 'ablations':reports},indent=2),encoding='ascii')


if __name__=='__main__': main()
