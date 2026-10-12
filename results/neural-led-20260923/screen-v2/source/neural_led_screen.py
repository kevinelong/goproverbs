"""Frozen serial White validation and paired strength screening."""
import argparse
import copy
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import sys
import time

from direct_arena import paired_summary
from lab import COLUMNS, GTP, Referee
from neural import KataGo, config_text, digest, make_query
from neural_led import choose
from neural_led_probe import BENCH, GO, Proposer, save, verify

DEFAULT = GO/'results/neural-led-20260923/screen-v1'
VARIANTS = ('policy', 'neural', 'heuristic', 'tactical', 'combined')


def canonical(moves):
    """History identity modulo the eight square symmetries, preserving colors."""
    forms = []
    for reflect in (False, True):
        for rotation in range(4):
            points = []
            for color, move in moves:
                if move == 'pass':
                    points.append((color, -1, -1))
                    continue
                x, y = COLUMNS.index(move[0]), int(move[1:])-1
                if reflect:
                    x = 18-x
                for _ in range(rotation):
                    x, y = 18-y, x
                points.append((color, x, y))
            forms.append(tuple(points))
    return min(forms)


def fresh_openings(excluded, count=40):
    rng = random.Random(23092026)
    seen, rows = set(excluded), []
    while len(rows) < count:
        points = []
        for right, top in ((False, False), (True, False), (False, True), (True, True)):
            x, y = rng.choice((2, 3)), rng.choice((2, 3))
            x, y = (18-x if right else x), (18-y if top else y)
            points.append(f'{COLUMNS[x]}{y+1}')
        rng.shuffle(points)
        moves = [['B' if i % 2 == 0 else 'W', move] for i, move in enumerate(points)]
        key = canonical(moves)
        if key in seen:
            continue
        seen.add(key)
        rows.append({'id': f'led-fresh-{len(rows):03d}', 'moves': moves})
    return rows


def schedule(openings):
    rng, rows = random.Random(23092027), []
    for stage, a, b, chosen in ((1, 'neural', 'policy', openings[:20]),
                                (2, 'combined', 'neural', openings[20:])):
        chosen = chosen.copy()
        rng.shuffle(chosen)
        for opening in chosen:
            colors = ['B', 'W']
            rng.shuffle(colors)
            for color in colors:
                rows.append(dict(stage=stage, opening=opening, a=a, b=b, a_color=color,
                                 stem=f'{opening["id"]}-{a}-vs-{b}-{color}'))
    return rows


def prepare(output, combined_only=False):
    output.mkdir(parents=True, exist_ok=False)
    source = output/'source'
    source.mkdir()
    names = ('neural_led_screen.py', 'test_neural_led_screen.py', 'neural_led.py',
             'test_neural_led.py', 'neural_led_probe.py', 'test_neural_led_probe.py',
             'direct_arena.py', 'guidance.py', 'lab.py', 'neural.py', 'sgf_io.py')
    for name in names:
        shutil.copy2(GO/'benchmarks'/name, source/name)
    shutil.copy2(GO.parent/'benchmarks/compare_bonsai_packing_20260922.py',
                 source/'compare_bonsai_packing_20260922.py')
    old = GO/'results/neural-led-20260923/probe-v1'
    previous = verify(old)
    for name in ('neural_led.py', 'neural_led_probe.py', 'lab.py', 'neural.py', 'sgf_io.py'):
        if combined_only and name == 'neural_led.py':
            continue
        if digest(source/name) != digest(old/'source'/name):
            raise RuntimeError('Controller/dependency differs from tested prototype: '+name)
    excluded, opening_hashes = set(), {}
    for path in sorted((GO/'results').glob('**/*openings*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        rows = data.get('openings', []) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and 'moves' in row:
                excluded.add(canonical(row['moves']))
        opening_hashes[str(path)] = digest(path)
    openings = fresh_openings(excluded)
    save(output/'openings.json', {'seed': 23092026, 'openings': openings})
    save(output/'exclusions.json', {'previous_input_hashes': opening_hashes,
                                   'canonical_histories_excluded': len(excluded)})
    games = schedule(openings)
    if combined_only:
        games = [g for g in games if g['stage'] == 2]
    save(output/'schedule.json', games)
    white = json.loads((old/'positions.json').read_text())
    for row in white:
        assert row['moves'][-1][0] == 'W'
        row['moves'] = row['moves'][:-1]
        row['color'] = 'W'
        row['id'] += '-white'
    if combined_only:
        failed = GO/'results/neural-led-20260923/screen-v1'
        state = json.loads((failed/'status.json').read_text())
        log = failed/(state['active']+'.jsonl')
        history = [json.loads(line) for line in log.read_text().splitlines()]
        game = next(g for g in json.loads((failed/'schedule.json').read_text()) if g['stem'] == state['active'])
        assert history[-1]['color'] == 'W' and history[-1].get('error')
        white.append(dict(id='failed-root-v1-white', size=19, komi=7.5, color='W',
                          moves=game['opening']['moves']+[[r['color'], r['move']] for r in history[:-1]],
                          source_game=state['active'], source_sha256=digest(log)))
    save(output/'white-positions.json', white)
    protocol = 'NEURAL-LED-SCREEN-V2-2026-09-23.md' if combined_only else 'NEURAL-LED-SCREEN-2026-09-23.md'
    shutil.copy2(GO/'docs'/protocol, output/'PROTOCOL.md')
    save(output/'settings.json', dict(white_expected=len(white)*len(VARIANTS), games_expected=len(games),
                                     combined_only=combined_only))
    (output/'analysis.cfg').write_text(config_text(200), encoding='ascii')
    assets = previous['assets']
    paths = list(source.iterdir()) + [Path(p) for p in assets.values()]
    paths += [p for p in output.iterdir() if p.is_file()]
    save(output/'identity.json', {'assets': assets, 'hashes': {str(p): digest(p) for p in paths}})
    save(output/'status.json', dict(status='prepared', white_expected=len(white)*len(VARIANTS), games_expected=len(games)))


def engine(assets, moves, komi=7.5):
    gp = GTP(assets['exe'], assets['profile'], size=19, nodes=100000, depth=4,
             beam=8, tactical=2, search_mode='hybrid', time_ms=25)
    try:
        gp.command(f'komi {komi}')
        ref = Referee(19, komi)
        for color, move in moves:
            ref.play(color, move)
            gp.command(f'play {color} {move}')
        ref.compare(gp.command('showboard'))
        return gp, ref
    except BaseException:
        gp.close()
        raise


def decision(kata, gp, ref, moves, color, role, identifier, stop):
    proposer = Proposer(gp, moves)
    before = gp.command('gp-sgf')
    started = time.perf_counter()
    try:
        move, trace = choose(kata, moves, color, 19, ref.komi, 200,
                             variant=role, proposer=proposer, identifier=identifier,
                             cancelled=stop.exists)
    except BaseException as exc:
        # Preserve model failure traces even when no legal choice is available.
        if not hasattr(exc, 'trace'):
            exc.trace = {}
        exc.trace['outer_ms'] = (time.perf_counter()-started)*1000
        raise
    elapsed = (time.perf_counter()-started)*1000
    row = dict(color=color, role=role, move=move, ms=elapsed, trace=trace,
               proposer=proposer.last, poisoned=proposer.poisoned)
    for thread in proposer.threads:
        thread.join(timeout=1)
    if any(t.is_alive() for t in proposer.threads):
        row['error'] = 'Proposer thread failed to finish'
    if proposer.poisoned:
        row['error'] = 'Proposer transport poisoned; no changed-treatment recovery'
    if elapsed > 220:
        row['error'] = 'Decision exceeded 220 ms hard operational gate'
    if move is None:
        row['error'] = 'Nonterminal root returned no move'
    if not row.get('error'):
        try:
            if before != gp.command('gp-sgf'):
                raise RuntimeError('Decision mutated root history')
            ref.play(color, move)
            gp.command(f'play {color} {move}')
            ref.compare(gp.command('showboard'))
        except BaseException as exc:
            row['error'] = 'Move validation: '+repr(exc)
    return row


def role_summary(rows, role):
    chosen = [r for r in rows if r['role'] == role]
    times = [r['ms'] for r in chosen]
    return dict(decisions=len(chosen), median_ms=statistics.median(times) if times else None,
                max_ms=max(times) if times else None,
                complete_rounds=sum(r['trace']['completed_rounds'] for r in chosen),
                fallbacks=sum(r['trace']['fallback'] for r in chosen),
                over_200=sum(t > 200 for t in times), over_205=sum(t > 205 for t in times),
                policy_overrides=sum(r['move'] != r['trace']['root_move'] for r in chosen),
                specialist_only_selected=sum(any(c['move'] == r['move'] and
                    'neural' not in c['sources'] for c in r['trace']['candidates']) for r in chosen))


def pair_gate(games):
    for role in {name for g in games for name in g['roles']}:
        rows = [g['roles'][role] for g in games if role in g['roles']]
        count = sum(r['decisions'] for r in rows)
        if not count:
            raise RuntimeError('Empty role decisions')
        if sum(r['over_205'] for r in rows)/count > .01:
            raise RuntimeError(f'{role} exceeds 1% decision overshoot gate')
        if role != 'policy' and sum(r['complete_rounds'] for r in rows)/count < .80:
            raise RuntimeError(f'{role} below 80% completed-round gate')


def play(kata, assets, game, output):
    moves = copy.deepcopy(game['opening']['moves'])
    gp, ref = engine(assets, moves)
    rows = []
    result = dict(opening=game['opening']['id'], matchup=f'{game["a"]}-vs-{game["b"]}',
                  a=game['a'], b=game['b'], a_color=game['a_color'], finished=False,
                  result='unfinished', a_won=False, stage=game['stage'])
    try:
        with (output/f'{game["stem"]}.jsonl').open('x', encoding='ascii') as log:
            for turn in range(722):
                if (output/'STOP').exists():
                    raise RuntimeError('STOP requested')
                color = 'B' if len(moves) % 2 == 0 else 'W'
                role = game['a'] if color == game['a_color'] else game['b']
                started = time.perf_counter()
                try:
                    row = decision(kata, gp, ref, moves, color, role,
                                   f'{game["stem"]}-{turn}', output/'STOP')
                except BaseException as exc:
                    log.write(json.dumps(dict(turn=turn, role=role, color=color,
                              error=repr(exc), trace=getattr(exc, 'trace', {})))+'\n')
                    log.flush()
                    raise
                row.update(turn=turn, turn_ms=(time.perf_counter()-started)*1000)
                rows.append(row)
                log.write(json.dumps(row)+'\n')
                log.flush()
                if row.get('error'):
                    raise RuntimeError(row['error'])
                moves.append([color, row['move']])
                if ref.passes == 2:
                    margin = ref.margin()
                    winner = 'B' if margin > 0 else 'W' if margin < 0 else 'draw'
                    score = f'{winner}+{abs(margin):g}' if margin else '0'
                    if gp.command('final_score') != score:
                        raise RuntimeError('Final referee/GTP score disagreement')
                    result.update(finished=True, result=score, a_won=winner==game['a_color'],
                                  raw_area_margin=margin)
                    break
                if (turn+1) % 100 == 0:
                    print(game['stem'], 'ply', turn+1, flush=True)
            if not result['finished']:
                raise RuntimeError('Game unfinished at 722-move cap')
    except BaseException as exc:
        result['error'] = repr(exc)
    finally:
        result.update(moves=len(moves), roles={r: role_summary(rows, r) for r in (game['a'], game['b'])})
        try:
            if gp.proc.poll() is None:
                (output/f'{game["stem"]}.sgf').write_text(gp.command('gp-sgf'), encoding='ascii')
        except Exception as exc:
            result['sgf_error'] = repr(exc)
            result.setdefault('error', 'SGF recording failed')
        finally:
            try:
                gp.close()
            except Exception as exc:
                result['cleanup_error'] = repr(exc)
                result.setdefault('error', 'GTP cleanup failed')
    return result


def report(output, state, games):
    summary = paired_summary(games)
    save(output/'paired.json', summary)
    lines = ['# Neural-led paired screens', '', f'Status: {state["status"]}',
             f'White validation: {state.get("white_completed", 0)}/{state["white_expected"]}',
             f'Games recorded: {len(games)}/{state["games_expected"]}', '',
             '| Matchup | Games | Complete pairs | A wins | Unfinished | Pair score | Conservative 95% interval |',
             '|---|---:|---:|---:|---:|---:|---|']
    for name, row in summary['matchups'].items():
        lines.append(f'| {name} | {row["games"]} | {row["complete_pairs"]} | {row["a_wins"]} | '
                     f'{row["unfinished"]} | {row["mean_pair_score_for_a"]} | {row["conservative_95_interval"]} |')
    lines += ['', summary['method'], summary['limitations'], '',
              'No automatic expansion or default promotion. See status.json for operational failures.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='ascii')


def run(output):
    identity = verify(output)
    if (output/'games.json').exists():
        raise RuntimeError('Refusing to reuse partial/completed experiment')
    if 'reportAnalysisWinratesAs = BLACK' not in (output/'analysis.cfg').read_text():
        raise RuntimeError('Incorrect neural reporting perspective')
    import compare_bonsai_packing_20260922 as resource
    locks = list(BENCH.glob('*/RUNNING.lock')) + list((GO/'results').glob('**/RUNNING.lock'))
    if locks:
        raise RuntimeError('Other run lock: '+str(locks))
    preflight = resource.preflight()
    if preflight['ram_bytes']['available'] < 4*1024**3:
        raise RuntimeError('Less than 4 GiB physical headroom')
    assets = {k: Path(v) for k, v in identity['assets'].items()}
    settings = json.loads((output/'settings.json').read_text())
    state = dict(status='running', pid=os.getpid(), started=time.time(), preflight=preflight, **settings)
    games, white_rows = [], []
    lock = output/'RUNNING.lock'
    with lock.open('x') as handle:
        handle.write(str(os.getpid()))
    def record():
        state.update(white_completed=len(white_rows), games_recorded=len(games))
        save(output/'status.json', state)
        save(output/'games.json', games)
        save(output/'white-results.json', white_rows)
        report(output, state, games)
    try:
        record()
        with KataGo(assets['katago'], assets['model'], output/'analysis.cfg', output) as kata:
            state['version'] = kata.request({'id':'version', 'action':'query_version'}, deadline=time.perf_counter()+30)
            kata.request(make_query('warmup', [], 'B', 19, 7.5, 'policy'), deadline=time.perf_counter()+60)
            for case in json.loads((output/'white-positions.json').read_text()):
                for role in VARIANTS:
                    if (output/'STOP').exists():
                        raise RuntimeError('STOP requested')
                    name = case['id']+'-'+role
                    state['active'] = name
                    record()
                    kata.request({'id':'clear-'+name, 'action':'clear_cache'}, deadline=time.perf_counter()+30)
                    gp, ref = engine(assets, case['moves'], case['komi'])
                    try:
                        row = decision(kata, gp, ref, case['moves'], 'W', role, name, output/'STOP')
                        row['case'] = case['id']
                        white_rows.append(row)
                        record()
                        if row.get('error') or row['ms'] > 205:
                            raise RuntimeError('White legality/timing gate failed: '+str(row.get('error')))
                        trace = row['trace']
                        if role != 'policy' and trace['completed_rounds'] != 1:
                            raise RuntimeError('White completed-round gate failed')
                        queries = iter(trace['queries'][1:])
                        for candidate in trace['candidates']:
                            value = candidate['value']
                            if value['exact']:
                                continue
                            raw = next(queries)['rootInfo']
                            if raw['currentPlayer'] != 'B' or abs(value['winrate']-(1-raw['winrate'])) > 1e-12:
                                raise RuntimeError('White winrate normalization failure')
                            if value['score'] is not None and abs(value['score']+raw['scoreLead']) > 1e-9:
                                raise RuntimeError('White score normalization failure')
                    except BaseException as exc:
                        state['white_failure'] = dict(case=case['id'], role=role,
                            error=repr(exc), trace=getattr(exc, 'trace', {}))
                        raise
                    finally:
                        gp.close()
            state['white_gate'] = 'passed'
            record()
            print('WHITE GATE PASSED', len(white_rows), flush=True)
            for index, game in enumerate(json.loads((output/'schedule.json').read_text())):
                verify(output)
                state['active'] = game['stem']
                record()
                kata.request({'id':f'clear-game-{index}', 'action':'clear_cache'}, deadline=time.perf_counter()+30)
                result = play(kata, assets, game, output)
                games.append(result)
                record()
                print(game['stem'], result['result'], result.get('error', ''), flush=True)
                if not result['finished'] or result.get('error'):
                    raise RuntimeError('Game operational gate failed; see saved game and traces')
                if len(games) % 2 == 0:
                    pair_gate(games[-2:])
            state['transport_metrics'] = dict(kata.metrics)
        verify(output)
        state.update(status='complete', inputs_unchanged=True)
    except BaseException as exc:
        state.update(status='stopped' if (output/'STOP').exists() else 'failed', error=repr(exc))
        raise
    finally:
        state['finished'] = time.time()
        try:
            verify(output)
            state['inputs_unchanged'] = True
        except Exception as exc:
            state.update(status='failed', inputs_unchanged=False, identity_error=repr(exc))
        try:
            state['remaining_model_processes'] = resource.active_processes()
            if state['remaining_model_processes']:
                state.update(status='failed', cleanup_error='Model process remains')
        except Exception as exc:
            state.update(status='failed', cleanup_error=repr(exc))
        finally:
            lock.unlink()
            record()
        if state.get('cleanup_error'):
            raise RuntimeError(state['cleanup_error'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    parser.add_argument('--output', type=Path, default=DEFAULT)
    parser.add_argument('--combined-only', action='store_true')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.output, args.combined_only)
    else:
        if Path(__file__).parent.resolve() != (args.output/'source').resolve():
            raise RuntimeError('Run frozen source copy')
        run(args.output)
