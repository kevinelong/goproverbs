"""Read-only checks and descriptive summaries of a frozen verification run."""
import argparse
import json
from pathlib import Path
import statistics

from lab import Referee
from neural import digest
from neural_led import _child, _terminal
from neural_led_probe import verify, save
from neural_verify import checked_value, select_move
from neural_verify_experiment import DEFAULT, PRIOR, depth_gate, history_key, quality_gate


def review(output):
    verify(output)
    read=lambda name:json.loads((output/name).read_text())
    state,profiles,rows,cases=map(read,('status.json','profiles.json','results.json','cases.json'))
    assert state['status']=='complete'
    assert not (output/'RUNNING.lock').exists()
    assert digest(output/'depth.json')==state['depth_hash']
    assert depth_gate(profiles)==state['depth']==read('depth.json')
    assert state['development']==quality_gate([r for r in rows if r['split']=='development'])
    old=json.loads((PRIOR/'cases.json').read_text())
    assert not ({history_key(c['moves']) for c in cases}&{history_key(c['moves']) for c in old})
    assert not ({c['opening'] for c in cases if c['split']=='development'}&
                {c['opening'] for c in cases if c['split']=='validation'})
    assert len({c['history_hash'] for c in cases})==len(cases)
    if not state['development']['passed']:
        assert all(r['split']=='development' for r in rows)
        assert not list(output.glob('validation-*-decision.json'))
    refs=exact=0
    summaries={}
    for role in ('neural','combined'):
        selected=[r for r in rows if r['role']==role]
        summaries[role]=dict(cases=len(selected),
            verified=sum(r['decision']['trace']['verification_complete'] for r in selected),
            retained_override=sum(r['decision']['move']!=r['decision']['trace']['root_move'] for r in selected),
            changed_to_policy=sum(r['decision']['move']!=r['decision']['trace']['baseline_move'] for r in selected),
            median_ms=statistics.median(r['decision']['ms'] for r in selected),
            max_ms=max(r['decision']['ms'] for r in selected),
            beneficial=sum(r['deltas']['512']['versus_current']>=.001 for r in selected),
            harmful=sum(r['deltas']['512']['versus_current']<=-.001 for r in selected))
    for row in rows:
        d=row['decision']; trace=d['trace']
        ref=Referee(19,7.5)
        for color,move in row['moves']: ref.play(color,move)
        _child(ref,row['color'],d['move'])
        if trace['verification_complete']:
            assert d['move']==select_move(trace['root_move'],trace['baseline_move'],trace['values'])
        for visits,values in row['references'].items():
            for move,record in values.items():
                child=_child(ref,row['color'],move)
                if record.get('exact'):
                    assert child.passes>=2
                    assert record['value']==_terminal(child,row['color']); exact+=1
                else:
                    player='W' if row['color']=='B' else 'B'
                    assert record['value']==checked_value(dict(id='audit',rootInfo=record['rootInfo']),
                        'audit',player,row['color'],int(visits)); refs+=1
            selected=values[d['move']]['value']['winrate']
            assert row['deltas'][visits]['versus_current']==selected-values[trace['baseline_move']]['value']['winrate']
            assert row['deltas'][visits]['versus_policy']==selected-values[trace['root_move']]['value']['winrate']
    wire=[json.loads(line) for line in (output/'wire.jsonl').read_text().splitlines()]
    result=dict(passed=True,profiles=len(profiles),reference_cases=len(rows),
        searched_reference_children=refs,exact_reference_children=exact,roles=summaries,
        inputs_unchanged=True,no_validation_queries=not any('validation-' in json.dumps(r) for r in wire),
        transport=state['transport_metrics'],seconds=state['finished']-state['started'],
        postflight_free_ram_gib=state['postflight']['ram_bytes']['available']/1024**3,
        postflight_gpu=state['postflight']['gpu']['stdout'],
        postflight_ollama=state['postflight']['ollama']['stdout'])
    save(output/'REVIEW.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT)
    args=parser.parse_args()
    print(json.dumps(review(args.output),indent=2))
