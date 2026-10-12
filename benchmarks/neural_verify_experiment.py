"""Frozen serial timing and gated reference screen for override verification."""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import time

from lab import Referee
from neural import KataGo, config_text, digest, make_query
from neural_disagreement import key, proposals
from neural_led import _child, _terminal
from neural_led_probe import BENCH, GO, Proposer, save, verify
from neural_led_screen import engine
from neural_verify import checked_value, choose_verified

ORIGIN = GO/'results/neural-led-20260923/pass-v1'
PRIOR = GO/'results/neural-led-20260923/disagreements-v1'
DEFAULT = GO/'results/neural-led-20260923/verification-v1'


def history_key(moves):
    return key('full-history-v1', moves)


def collect():
    prior = json.loads((PRIOR/'cases.json').read_text())
    excluded = {history_key(c['moves']) for c in prior}
    profiles = []
    for stratum, role in (('confidence', 'neural'), ('specialist', 'combined')):
        selected = sorted((c for c in prior if c['stratum'] == stratum), key=lambda c:key(230930,c['id']))[:10]
        profiles.extend(dict(id=c['id'], moves=c['moves'], color=c['color'], role=role) for c in selected)
    schedule = json.loads((ORIGIN/'schedule.json').read_text())
    cases, missing = [], []
    sources = [PRIOR/'cases.json', ORIGIN/'schedule.json']
    for stage, role in ((1,'neural'), (2,'combined')):
        games = [g for g in schedule if g['stage'] == stage]
        ids = sorted({g['opening']['id'] for g in games}, key=lambda x:key(230932,x))
        development = set(ids[:10])
        for game in games:
            path = ORIGIN/(game['stem']+'.jsonl')
            sources.append(path)
            history = copy.deepcopy(game['opening']['moves'])
            eligible = []
            for row in (json.loads(line) for line in path.read_text().splitlines()):
                if row['role'] == role and proposals(row) and history_key(history) not in excluded:
                    eligible.append(dict(id=f'{game["stem"]}-{row["turn"]}', role=role,
                        opening=game['opening']['id'], game=game['stem'], color=row['color'],
                        moves=copy.deepcopy(history), history_hash=history_key(history),
                        split='development' if game['opening']['id'] in development else 'validation'))
                history.append([row['color'],row['move']])
            if eligible:
                cases.append(min(eligible, key=lambda c:key(230931,c['game'],int(c['id'].rsplit('-',1)[1]))))
            else:
                missing.append(game['stem'])
    return profiles, sorted(cases,key=lambda c:key(230933,c['id'])), missing, sources


def percentile(values, p):
    return sorted(values)[max(0,math.ceil(len(values)*p)-1)] if values else None


def operational(row):
    t = row['trace']
    return (row['ms'] <= 200 and not t['verification_fallback'] and
            not t['baseline']['fallback'] and row['legal'])


def depth_gate(rows):
    output = {}
    for visits in (4,8,16):
        selected = [r for r in rows if r['visits'] == visits]
        times = [r['ms'] for r in selected]
        verified = {role:sum(r['role']==role and r['trace']['verification_complete'] for r in selected)
                    for role in ('neural','combined')}
        result = dict(decisions=len(selected), median_ms=statistics.median(times) if times else None,
            p95_ms=percentile(times,.95), max_ms=max(times) if times else None, verified=verified)
        result['passed'] = (len(selected)==20 and all(operational(r) for r in selected)
                            and result['p95_ms']<=150 and result['max_ms']<=180 and min(verified.values())>=5)
        output[str(visits)] = result
    passing = [v for v in (4,8,16) if output[str(v)]['passed']]
    return dict(selected_visits=max(passing) if passing else None, budgets=output)


def opening_mean(rows, visits, field):
    groups = {}
    for row in rows:
        groups.setdefault(row['opening'],[]).append(row['deltas'][str(visits)][field])
    return statistics.mean(statistics.mean(g) for g in groups.values()) if groups else None


def quality_gate(rows):
    means = {str(v):{field:opening_mean(rows,v,field) for field in ('versus_current','versus_policy')}
             for v in (128,512)}
    role_means = {role:{str(v):opening_mean([r for r in rows if r['role']==role],v,'versus_current')
                       for v in (128,512)} for role in ('neural','combined')}
    counts = {role:sum(r['role']==role for r in rows) for role in role_means}
    beneficial = sum(r['deltas']['512']['versus_current']>=.001 for r in rows)
    harmful = sum(r['deltas']['512']['versus_current']<=-.001 for r in rows)
    severe = sum(all(r['deltas'][str(v)]['versus_current']<-.05 for v in (128,512)) for r in rows)
    times = [r['decision']['ms'] for r in rows]
    passed = (len(rows)>=30 and len({r['opening'] for r in rows})>=15 and min(counts.values())>=15
        and all(operational(r['decision']) for r in rows) and percentile(times,.95)<=180
        and all(m['versus_current'] is not None and m['versus_current']>=.005 and m['versus_policy']>=0 for m in means.values())
        and all(m is not None and m>=0 for role in role_means.values() for m in role.values())
        and beneficial>=5 and beneficial>=2*harmful and severe==0)
    return dict(passed=passed,cases=len(rows),openings=len({r['opening'] for r in rows}),role_counts=counts,
        opening_means=means,role_means=role_means,beneficial=beneficial,harmful=harmful,severe_harm=severe,
        p95_ms=percentile(times,.95),max_ms=max(times) if times else None)


def prepare(output):
    previous = verify(ORIGIN)
    verify(PRIOR)
    profiles,cases,missing,sources = collect()
    output.mkdir(parents=True,exist_ok=False)
    source = output/'source'; source.mkdir()
    for path in (GO/'benchmarks').glob('*.py'):
        shutil.copy2(path,source/path.name)
    shutil.copy2(GO.parent/'benchmarks/compare_bonsai_packing_20260922.py',source/'compare_bonsai_packing_20260922.py')
    shutil.copy2(GO/'docs/NEURAL-VERIFY-PLAN-2026-09-23.md',output/'PROTOCOL.md')
    save(output/'profile-cases.json',profiles)
    save(output/'cases.json',cases)
    save(output/'sampling.json',dict(missing=missing,expected=len(cases),profile_expected=len(profiles)))
    (output/'analysis.cfg').write_text(config_text(30000),encoding='ascii')
    paths = list(source.iterdir())+list(output.glob('*.*'))+sources+[Path(p) for p in previous['assets'].values()]
    save(output/'identity.json',dict(assets=previous['assets'],hashes={str(p):digest(p) for p in paths}))
    save(output/'status.json',dict(status='prepared',cases=len(cases),missing=missing))
    print('Prepared',len(profiles),'profile cases and',len(cases),'new cases; missing:',missing)


def clear(kata, identifier):
    response = kata.request(dict(id='clear-'+identifier,action='clear_cache'),deadline=time.perf_counter()+30)
    if response.get('error') or response.get('warning'):
        raise RuntimeError('cache clear failed')


def decide(kata, assets, case, visits, identifier, stop):
    gp,ref = engine(assets,case['moves'])
    try:
        before = gp.command('gp-sgf')
        proposer = Proposer(gp,case['moves'])
        started = time.perf_counter()
        move,trace = choose_verified(kata,case['moves'],case['color'],19,7.5,200,visits,
            variant=case['role'],proposer=proposer,identifier=identifier,cancelled=stop.exists)
        elapsed = (time.perf_counter()-started)*1000
        for thread in proposer.threads:
            thread.join(timeout=1)
        if proposer.poisoned or any(t.is_alive() for t in proposer.threads):
            raise RuntimeError('proposer incomplete or poisoned')
        if before != gp.command('gp-sgf'):
            raise RuntimeError('root mutated')
        ref.play(case['color'],move)
        gp.command(f'play {case["color"]} {move}')
        ref.compare(gp.command('showboard'))
        return dict(id=case['id'],role=case['role'],visits=visits,move=move,ms=elapsed,trace=trace,legal=True)
    finally:
        gp.close()


def references(kata, case, decision, identifier, stop):
    ref = Referee(19,7.5)
    for color,move in case['moves']:
        ref.play(color,move)
    moves = list(dict.fromkeys((decision['trace']['root_move'],decision['trace']['baseline_move'],decision['move'])))
    moves.sort(key=lambda m:key(230934,case['id'],m))
    budgets = sorted((128,512),key=lambda v:key(230935,case['id'],v))
    output = {}
    for visits in budgets:
        values = {}
        for index,move in enumerate(moves):
            if stop.exists(): raise RuntimeError('STOP requested')
            child = _child(ref,case['color'],move)
            if child.passes>=2:
                values[move] = dict(value=_terminal(child,case['color']),exact=True)
                continue
            qid = f'{identifier}-{visits}-{index}'
            clear(kata,qid)
            other = 'W' if case['color']=='B' else 'B'
            query = make_query(qid,case['moves']+[[case['color'],move]],other,19,7.5,'policy')
            query['maxVisits'] = visits
            started = time.perf_counter()
            response = kata.request(query,deadline=started+35)
            values[move] = dict(value=checked_value(response,qid,other,case['color'],visits),
                rootInfo=response['rootInfo'],ms=(time.perf_counter()-started)*1000)
        output[str(visits)] = values
    return output


def report(output, state, profiles, rows):
    lines = ['# Small-search verification experiment','',f'Status: {state["status"]}',
        f'Phase: {state.get("phase")}; profiles: {len(profiles)}; reference cases: {len(rows)}.',
        '', 'Same-model reference estimates; internal samples from previously inspected games.',
        'No game-strength claim. Validation runs only after development passes.', '']
    if 'depth' in state:
        lines += ['Timing gate:','```json',json.dumps(state['depth'],indent=2),'```','']
    for split in ('development','validation'):
        if split in state:
            lines += [split+' gate:','```json',json.dumps(state[split],indent=2),'```','']
    if 'outcome' in state: lines += [state['outcome'],'']
    if 'error' in state: lines += [state['error'],'']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='ascii')


def run(output):
    identity = verify(output)
    if (output/'profiles.json').exists(): raise RuntimeError('No reuse of run labels')
    import compare_bonsai_packing_20260922 as resource
    locks = list(BENCH.glob('**/RUNNING.lock'))+list((GO/'results').glob('**/RUNNING.lock'))
    if locks: raise RuntimeError('Competing run lock: '+str(locks))
    preflight = resource.preflight()
    if preflight['ram_bytes']['available']<4*1024**3: raise RuntimeError('Less than4GiB RAM available')
    assets = {k:Path(v) for k,v in identity['assets'].items()}
    state = dict(status='running',phase='profile',pid=os.getpid(),started=time.time(),preflight=preflight)
    profiles,rows = [],[]
    lock=output/'RUNNING.lock'
    with lock.open('x') as handle: handle.write(str(os.getpid()))
    stop=output/'STOP'
    def record():
        save(output/'status.json',state); save(output/'profiles.json',profiles); save(output/'results.json',rows)
        report(output,state,profiles,rows)
    try:
        record()
        with KataGo(assets['katago'],assets['model'],output/'analysis.cfg',output) as kata:
            state['model_pid'] = kata.proc.pid
            state['version'] = kata.request(dict(id='version',action='query_version'),deadline=time.perf_counter()+30)
            kata.request(make_query('warmup',[],'B',19,7.5,'policy'),deadline=time.perf_counter()+60)
            for i,case in enumerate(json.loads((output/'profile-cases.json').read_text())):
                for visits in sorted((4,8,16),key=lambda v:key(230936,case['id'],v)):
                    if stop.exists(): raise RuntimeError('STOP requested')
                    identifier=f'profile-{i}-{visits}'
                    clear(kata,identifier)
                    profiles.append(decide(kata,assets,case,visits,identifier,stop))
                    state['active']=identifier; record()
                    print(identifier,round(profiles[-1]['ms'],2),flush=True)
            state['depth'] = depth_gate(profiles)
            save(output/'depth.json',state['depth'])
            state['depth_hash'] = digest(output/'depth.json')
            record()
            depth = state['depth']['selected_visits']
            if depth is None:
                state['outcome'] = 'Timing gate failed; quality references and fresh games held.'
            else:
                cases=json.loads((output/'cases.json').read_text())
                for split in ('development','validation'):
                    state['phase']=split
                    for i,case in enumerate(c for c in cases if c['split']==split):
                        if stop.exists(): raise RuntimeError('STOP requested')
                        identifier=f'{split}-{i}'
                        clear(kata,identifier)
                        decision=decide(kata,assets,case,depth,identifier,stop)
                        # Persist the choice before any reference labels exist.
                        save(output/(identifier+'-decision.json'),decision)
                        values=references(kata,case,decision,identifier,stop)
                        d=decision['trace']
                        deltas={v:dict(versus_current=values[v][decision['move']]['value']['winrate']-values[v][d['baseline_move']]['value']['winrate'],
                                      versus_policy=values[v][decision['move']]['value']['winrate']-values[v][d['root_move']]['value']['winrate']) for v in values}
                        rows.append(dict(**case,decision=decision,references=values,deltas=deltas))
                        state['active']=case['id']; record()
                        print(split,i+1,case['id'],flush=True)
                    state[split]=quality_gate([r for r in rows if r['split']==split]); record()
                    if not state[split]['passed']:
                        state['outcome']=split+' gate failed; remaining validation/fresh games held.'
                        break
                else:
                    state['outcome']='Both reference gates passed; fresh-game stage authorized and ready for separate frozen preparation.'
                    state['fresh_games_ready']=True
            state['transport_metrics']=dict(kata.metrics)
        verify(output)
        if 'depth_hash' in state and digest(output/'depth.json')!=state['depth_hash']:
            raise RuntimeError('Selected depth mutated')
        state.update(status='complete',inputs_unchanged=True)
    except BaseException as exc:
        state.update(status='stopped' if stop.exists() else 'failed',error=repr(exc))
        if hasattr(exc,'trace'): save(output/'failure-trace.json',exc.trace)
        raise
    finally:
        state['finished']=time.time()
        try:
            verify(output); state['inputs_unchanged']=True
            state['remaining_model_processes']=resource.active_processes()
            state['postflight']=resource.machine_state()
            if state['remaining_model_processes']: raise RuntimeError('Model process remains')
            if len(state['postflight']['ollama'].get('stdout','').strip().splitlines())>1:
                raise RuntimeError('Ollama resident model remains')
        except Exception as exc:
            state.update(status='failed',cleanup_error=repr(exc))
        finally:
            lock.unlink(); record()
        if state.get('cleanup_error'): raise RuntimeError(state['cleanup_error'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('--output',type=Path,default=DEFAULT)
    args=parser.parse_args(); output=args.output.resolve()
    if args.action=='prepare': prepare(output)
    else:
        if Path(__file__).parent.resolve() != (output/'source').resolve(): raise RuntimeError('Run frozen source copy')
        run(output)
