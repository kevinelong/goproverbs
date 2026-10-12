"""Frozen, paired-opening disagreement diagnostics; reference estimates, not truth."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import shutil
import statistics
import time

from lab import Referee
from neural import KataGo, config_text, digest, make_query
from neural_led import _child, _terminal, _value
from neural_led_probe import GO, BENCH, save, verify

DEFAULT = GO/'results/neural-led-20260923/disagreements-v1'
ORIGIN = GO/'results/neural-led-20260923/pass-v1'


def key(seed, *parts):
    return hashlib.sha256(json.dumps([seed,*parts]).encode('ascii')).hexdigest()


def proposals(row):
    trace = row['trace']
    if not trace['completed_rounds'] or row['move']==trace['root_move']:
        return None
    root = next(c for c in trace['candidates'] if c['move']==trace['root_move'])
    chosen = next(c for c in trace['candidates'] if c['move']==row['move'])
    neural = max((c for c in trace['candidates'] if 'neural' in c['sources']),
                 key=lambda c:(c['value']['winrate'], c['value']['score'] if trace.get('score_tiebreak_used') else 0))
    return dict(root=root, chosen=chosen, neural=neural)


def guard_applies(choices):
    return choices['root']['policy_probability']>=.50 and (
        choices['chosen']['value']['winrate']-choices['root']['value']['winrate']<.02)


def collect(origin):
    schedule = json.loads((origin/'schedule.json').read_text())
    cases, missing, hashes = [], [], {str(origin/'schedule.json'):digest(origin/'schedule.json')}
    for stage, role, stratum in ((1,'neural','confidence'),(2,'combined','specialist')):
        games = [g for g in schedule if g['stage']==stage]
        identifiers = sorted({g['opening']['id'] for g in games},key=lambda x:key(230925,x))
        development = set(identifiers[:10])
        for game in games:
            path = origin/(game['stem']+'.jsonl')
            hashes[str(path)] = digest(path)
            history = copy.deepcopy(game['opening']['moves'])
            eligible = []
            for row in (json.loads(line) for line in path.read_text().splitlines()):
                choices = proposals(row) if row['role']==role else None
                if choices and ((stratum=='confidence' and guard_applies(choices)) or
                                (stratum=='specialist' and 'neural' not in choices['chosen']['sources'])):
                    eligible.append(dict(id=f'{game["stem"]}-{row["turn"]}',
                        opening=game['opening']['id'], game=game['stem'], turn=row['turn'],
                        split='development' if game['opening']['id'] in development else 'validation',
                        stratum=stratum, color=row['color'], moves=copy.deepcopy(history),
                        choices=choices, guard_applies=guard_applies(choices)))
                history.append([row['color'],row['move']])
            if eligible:
                cases.append(min(eligible,key=lambda c:key(230924,c['game'],c['turn'])))
            else:
                missing.append(dict(game=game['stem'],stratum=stratum))
    random.Random(230926).shuffle(cases)
    return cases, missing, hashes


def reference_value(response, player, color, visits):
    if response.get('isDuringSearch') or response.get('_used_intermediate'):
        raise ValueError('Incomplete reference result')
    if response['rootInfo']['visits']<visits:
        raise ValueError('Insufficient reference visits')
    return _value(response, player, color)


def candidate_gate(rows, split):
    chosen = [r for r in rows if r['stratum']=='confidence' and r['split']==split]
    groups = {}
    for row in chosen:
        groups.setdefault(row['opening'],[]).append(row)
    means = {str(v):statistics.mean(statistics.mean(r['deltas'][str(v)]['root_minus_chosen'] for r in g)
                    for g in groups.values()) if groups else None for v in (128,512)}
    beneficial = sum(r['deltas']['512']['root_minus_chosen']>=.001 for r in chosen)
    harmful = sum(r['deltas']['512']['root_minus_chosen']<=-.001 for r in chosen)
    severe = sum(all(r['deltas'][str(v)]['root_minus_chosen']<-.05 for v in (128,512)) for r in chosen)
    passed = (len(chosen)>=10 and len(groups)>=5 and all(m is not None and m>=.005 for m in means.values())
              and beneficial>=5 and beneficial>=2*harmful and severe==0)
    return dict(passed=passed,cases=len(chosen),openings=len(groups),opening_mean_improvement=means,
                beneficial=beneficial,harmful=harmful,severe_harm=severe)


def describe(rows):
    output = {}
    for stratum in ('confidence','specialist'):
        chosen = [r for r in rows if r['stratum']==stratum]
        summary = dict(cases=len(chosen))
        field = 'chosen_minus_neural' if stratum=='specialist' else 'chosen_minus_root'
        summary['depth_direction_reversals'] = sum(
            (r['deltas']['128'][field]>=.001 and r['deltas']['512'][field]<=-.001) or
            (r['deltas']['128'][field]<=-.001 and r['deltas']['512'][field]>=.001) for r in chosen)
        for visits in ('128','512'):
            field = 'chosen_minus_neural' if stratum=='specialist' else 'chosen_minus_root'
            values = [r['deltas'][visits][field] for r in chosen]
            scores = [r['deltas'][visits][field+'_score'] for r in chosen]
            summary[visits] = dict(mean_winrate_difference=statistics.mean(values) if values else None,
                mean_score_difference=statistics.mean(scores) if scores else None,
                chosen_better=sum(v>=.001 for v in values), chosen_worse=sum(v<=-.001 for v in values),
                near_ties=sum(abs(v)<.001 for v in values))
            summary[visits]['saturated_reference_pairs'] = sum(
                all(r['references'][visits][r['choices'][n]['move']]['value']['winrate']<.001 for n in ('chosen','root' if stratum=='confidence' else 'neural')) or
                all(r['references'][visits][r['choices'][n]['move']]['value']['winrate']>.999 for n in ('chosen','root' if stratum=='confidence' else 'neural')) for r in chosen)
        output[stratum] = summary
    output['candidate_development'] = candidate_gate(rows,'development')
    output['candidate_validation'] = candidate_gate(rows,'validation')
    output['implementation_gate'] = all(output[k]['passed'] for k in ('candidate_development','candidate_validation'))
    return output


def report(output, state, rows):
    summary = describe(rows)
    save(output/'summary.json',summary)
    lines = ['# Saved disagreement review','',f'Status: {state["status"]}; completed {len(rows)}/{state["expected"]} cases.',
             'Deeper same-model estimates are not ground truth. Enriched sample, paired openings.','',
             '| Stratum | Visits | Cases | Chosen better | Chosen worse | Near tie | Mean winrate difference | Mean score difference |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for stratum in ('confidence','specialist'):
        for visits in ('128','512'):
            s=summary[stratum]; r=s[visits]
            lines.append(f'| {stratum} | {visits} | {s["cases"]} | {r["chosen_better"]} | {r["chosen_worse"]} | '
                         f'{r["near_ties"]} | {r["mean_winrate_difference"]} | {r["mean_score_difference"]} |')
    lines += ['', 'Confidence: chosen versus root policy. Specialist: chosen versus best saved neural candidate.',
              'Better/worse requires at least0.001 estimated win-probability difference.',
              'Means above are descriptive case averages, not independent-game statistics.','',
              'Development candidate gate: '+json.dumps(summary['candidate_development'],sort_keys=True),
              'Validation candidate gate: '+json.dumps(summary['candidate_validation'],sort_keys=True),
              'Implement candidate: '+str(state['status']=='complete' and summary['implementation_gate']),
              'Validation is not counted as support unless development passes. No threshold tuning or pooled strength claim.']
    for stratum in ('confidence','specialist'):
        lines += [f'{stratum}: depth-direction reversals={summary[stratum]["depth_direction_reversals"]}; '
                  f'saturated pairs at512 visits={summary[stratum]["512"]["saturated_reference_pairs"]}.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='ascii')


def prepare(output):
    output=output.resolve()
    previous=verify(ORIGIN)
    cases, missing, hashes=collect(ORIGIN)
    output.mkdir(parents=True,exist_ok=False)
    source=output/'source'; source.mkdir()
    for name in ('neural_disagreement.py','test_neural_disagreement.py','neural_led.py','neural_led_probe.py','neural.py','lab.py','sgf_io.py'):
        shutil.copy2(GO/'benchmarks'/name,source/name)
    shutil.copy2(GO.parent/'benchmarks/compare_bonsai_packing_20260922.py',source/'compare_bonsai_packing_20260922.py')
    save(output/'cases.json',cases)
    save(output/'sampling.json',dict(missing=missing,source_hashes=hashes,expected=len(cases)))
    shutil.copy2(GO/'docs/NEURAL-LED-DISAGREEMENT-PLAN-2026-09-23.md',output/'PROTOCOL.md')
    (output/'analysis.cfg').write_text(config_text(30000),encoding='ascii')
    assets=previous['assets']
    paths=list(source.iterdir())+[p for p in output.iterdir() if p.is_file()]+[Path(p) for p in assets.values()]
    hashes.update({str(p):digest(p) for p in paths})
    save(output/'identity.json',dict(assets=assets,hashes=hashes))
    save(output/'status.json',dict(status='prepared',expected=len(cases)))
    print('Prepared',len(cases),'cases; missing games:',len(missing))


def run(output):
    output=output.resolve()
    identity=verify(output)
    if (output/'results.json').exists(): raise RuntimeError('Refusing to reuse partial/completed labels')
    import compare_bonsai_packing_20260922 as resource
    locks=list(BENCH.glob('*/RUNNING.lock'))+list((GO/'results').glob('**/RUNNING.lock'))
    if locks: raise RuntimeError('Competing run lock: '+str(locks))
    preflight=resource.preflight()
    if preflight['ram_bytes']['available']<4*1024**3: raise RuntimeError('Less than4GiB RAM headroom')
    cases=json.loads((output/'cases.json').read_text())
    assets={k:Path(v) for k,v in identity['assets'].items()}
    state=dict(status='running',expected=len(cases),started=time.time(),preflight=preflight)
    rows=[]
    lock=output/'RUNNING.lock'
    with lock.open('x') as handle: handle.write(str(__import__('os').getpid()))
    def record():
        state['completed']=len(rows)
        save(output/'status.json',state); save(output/'results.json',rows); report(output,state,rows)
    try:
        record()
        with KataGo(assets['katago'],assets['model'],output/'analysis.cfg',output) as kata:
            state['version']=kata.request({'id':'version','action':'query_version'},deadline=time.perf_counter()+30)
            kata.request(make_query('warmup',[],'B',19,7.5,'policy'),deadline=time.perf_counter()+60)
            for i,case in enumerate(cases):
                if (output/'STOP').exists(): raise RuntimeError('STOP requested')
                state['active']=case['id']; record()
                ref=Referee(19,7.5)
                for color,move in case['moves']: ref.play(color,move)
                row=copy.deepcopy(case); row['references']={}; row['deltas']={}
                moves=list(dict.fromkeys(case['choices'][name]['move'] for name in ('root','chosen','neural')))
                budgets=(128,512) if int(key(230927,case['id']),16)%2 else (512,128)
                for visits in budgets:
                    values={}
                    for j,move in enumerate(moves):
                        if (output/'STOP').exists(): raise RuntimeError('STOP requested')
                        child=_child(ref,case['color'],move)
                        if child.passes>=2:
                            values[move]=dict(value=_terminal(child,case['color']),exact=True)
                            continue
                        identifier=f'case-{i}-{visits}-{j}'
                        kata.request({'id':'clear-'+identifier,'action':'clear_cache'},deadline=time.perf_counter()+30)
                        other='W' if case['color']=='B' else 'B'
                        query=make_query(identifier,case['moves']+[[case['color'],move]],other,19,7.5,'policy')
                        query['maxVisits']=visits
                        started=time.perf_counter()
                        response=kata.request(query,deadline=started+35)
                        value=reference_value(response,other,case['color'],visits)
                        values[move]=dict(value=value,rootInfo=response['rootInfo'],ms=(time.perf_counter()-started)*1000)
                    row['references'][str(visits)]=values
                    v={name:values[case['choices'][name]['move']]['value'] for name in ('root','chosen','neural')}
                    row['deltas'][str(visits)]=dict(
                        root_minus_chosen=v['root']['winrate']-v['chosen']['winrate'],
                        chosen_minus_root=v['chosen']['winrate']-v['root']['winrate'],
                        chosen_minus_root_score=v['chosen']['score']-v['root']['score'],
                        chosen_minus_neural=v['chosen']['winrate']-v['neural']['winrate'],
                        chosen_minus_neural_score=v['chosen']['score']-v['neural']['score'])
                rows.append(row); record()
                print(len(rows),len(cases),case['stratum'],case['split'],case['id'],flush=True)
            state['transport_metrics']=dict(kata.metrics)
        verify(output)
        state.update(status='complete',inputs_unchanged=True)
    except BaseException as exc:
        state.update(status='stopped' if (output/'STOP').exists() else 'failed',error=repr(exc))
        state['partial_case']=locals().get('row')
        raise
    finally:
        state['finished']=time.time()
        try:
            verify(output); state['inputs_unchanged']=True
            state['remaining_model_processes']=resource.active_processes()
            if state['remaining_model_processes']: raise RuntimeError('Model process remains after cleanup')
        except Exception as exc:
            state.update(status='failed',cleanup_error=repr(exc))
        finally:
            lock.unlink(); record()
        if state.get('cleanup_error'): raise RuntimeError(state['cleanup_error'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('--output',type=Path,default=DEFAULT)
    args=parser.parse_args()
    if args.action=='prepare': prepare(args.output)
    else:
        if Path(__file__).parent.resolve()!=(args.output/'source').resolve(): raise RuntimeError('Run frozen source copy')
        run(args.output)
