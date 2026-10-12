"""Direct paired comparison of NH, NN, and standalone KataGo roles.

The input opening file is an explicit frozen selection: it must contain exactly
``--pairs`` openings. Each matchup uses both colors. Inference is serial and
every engine board and final score is checked by an independent TT referee.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import statistics
import re
import time

from guidance import Broker, choose
from lab import GTP, ROOT, Referee
from neural import (KataGo, config_text, digest, hardware, make_query,
                    policy_move, search_move)


ROLES = ('HH', 'NH', 'NN', 'policy', 'search')
MATCHUPS = (('NH', 'NN'), ('NH', 'policy'), ('NH', 'search'))
SIZE = 19
KOMI = 7.5


def load_openings(path, pairs):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    openings = data.get('openings') if isinstance(data, dict) else None
    if not isinstance(openings, list) or len(openings) != pairs:
        raise ValueError(f'opening file must contain exactly {pairs} openings')
    identifiers = set()
    histories = set()
    for opening in openings:
        if not isinstance(opening, dict) or not isinstance(opening.get('id'), str):
            raise ValueError('each opening needs a string id')
        if opening['id'] in identifiers:
            raise ValueError('opening ids must be unique')
        if not re.fullmatch(r'[A-Za-z0-9_-]+', opening['id']):
            raise ValueError('opening id must be a safe filename component')
        identifiers.add(opening['id'])
        moves = opening.get('moves')
        if not isinstance(moves, list) or len(moves) % 2:
            raise ValueError(f'{opening["id"]}: moves must be an even-length list')
        ref = Referee(SIZE, KOMI)
        for index, move in enumerate(moves):
            if (not isinstance(move, list) or len(move) != 2 or
                    move[0] != ('B' if index % 2 == 0 else 'W')):
                raise ValueError(f'{opening["id"]}: moves must alternate from Black')
            ref.play(move[0], move[1])
        key = tuple(map(tuple, moves))
        if key in histories:
            raise ValueError('opening histories must be unique')
        histories.add(key)
        if ref.passes == 2:
            raise ValueError('opening cannot already be a finished game')
    return openings


def parse_matchups(values):
    pairs = [tuple(value.split(':')) for value in values]
    if any(len(pair) != 2 or pair[0] == pair[1] or any(r not in ROLES for r in pair) for pair in pairs):
        raise ValueError('matchups need two distinct HH/NH/NN/policy/search roles')
    if len(set(pairs)) != len(pairs):
        raise ValueError('duplicate matchup')
    return pairs


def build_schedule(openings, matchups=MATCHUPS):
    return [
        {'opening': opening, 'a': a, 'b': b, 'a_color': color,
         'stem': f'{opening["id"]}-{a}-vs-{b}-{color}'}
        for opening in openings for a, b in matchups for color in ('B', 'W')
    ]


def role_for_color(game, color):
    return game['a'] if color == game['a_color'] else game['b']


def standalone_decision(kata, ref, moves, color, role, time_ms, identifier):
    if role not in ('policy', 'search'):
        raise ValueError('standalone role must be policy or search')
    started = time.perf_counter()
    deadline = time.perf_counter() + (time_ms - (5 if role == 'search' else 0)) / 1000
    query = make_query(identifier, moves, color, SIZE, KOMI, role)
    if role == 'search':
        query['overrideSettings'] = {'maxTime': max(0.001, (time_ms - 10) / 1000)}
        query['reportDuringSearchEvery'] = .02
    try:
        response = kata.request(query, deadline=deadline, allow_partial=(role == 'search'))
        if response['rootInfo']['currentPlayer'] != color:
            raise RuntimeError('KataGo side-to-move mismatch')
        move = policy_move(response, SIZE) if role == 'policy' else search_move(response)
        trace = {'source': 'katago', 'fallback': False, 'request_id': identifier,
                 'used_intermediate': response.get('_used_intermediate', False),
                 'root': response['rootInfo']}
    except TimeoutError as exc:
        raise RuntimeError(f'{role} produced no timely answer; stop comparison instead of substituting a weak move') from exc
    trace['ms'] = (time.perf_counter() - started) * 1000
    return move, trace


def engine(args):
    gp = GTP(args.exe, args.profile, size=SIZE, nodes=10000000, depth=12,
             beam=12, search_mode='hybrid', time_ms=args.time_ms)
    gp.command(f'komi {KOMI}')
    return gp


def setup_game(gps, opening):
    ref = Referee(SIZE, KOMI)
    for color, move in opening['moves']:
        ref.play(color, move)
        for gp in gps:
            gp.command(f'play {color} {move}')
    for gp in gps:
        ref.compare(gp.command('showboard'))
    return ref, copy.deepcopy(opening['moves'])


def hybrid_decision(gp, broker, moves, color, role, time_ms):
    move, trace = choose(gp, broker, moves, color, KOMI, role, time_ms)
    trace['source'] = 'goproverbs'
    trace['fallback'] = bool(trace.get('root_timeout'))
    return move, trace


def summarize_role(decisions, role):
    rows = [row for row in decisions if row['role'] == role]
    times = [row['ms'] for row in rows]
    reports = [row['trace'].get('report', '') for row in rows]
    summary = {
        'decisions': len(rows),
        'median_ms': statistics.median(times) if times else None,
        'max_ms': max(times) if times else None,
        'fallbacks': sum(bool(row['trace'].get('fallback')) for row in rows),
        'root_timeouts': sum(bool(row['trace'].get('root_timeout')) for row in rows),
    }
    if role == 'NN':
        summary['external_complete_rounds'] = sum(
            'external_leaf=true' in report for report in reports)
        summary['external_fallback_rounds'] = sum(
            'external_leaf=false' in report for report in reports)
    elif role in ('policy', 'search'):
        summary['valid_neural_decisions'] = len(rows) - summary['fallbacks']
        summary['intermediate_decisions'] = sum(bool(row['trace'].get('used_intermediate')) for row in rows)
        summary['terminal_responses'] = summary['valid_neural_decisions'] - summary['intermediate_decisions']
        summary['external_timeout_fallbacks'] = summary['fallbacks']
    else:
        summary['external_complete_rounds'] = 0
        summary['external_fallback_rounds'] = 0
    return summary


def paired_summary(games):
    result = {}
    for a, b in sorted({tuple(row['matchup'].split('-vs-')) for row in games}):
        name = f'{a}-vs-{b}'
        rows = [row for row in games if row['matchup'] == name]
        grouped = {}
        for row in rows:
            grouped.setdefault(row['opening'], []).append(row)
        scores = []
        for pair in grouped.values():
            if (len(pair) == 2 and {row['a_color'] for row in pair} == {'B', 'W'}
                    and all(row['finished'] for row in pair)):
                scores.append(sum(0.5 if row['result'] == '0' else float(row['a_won'])
                                  for row in pair) / 2)
        mean = sum(scores) / len(scores) if scores else None
        radius = math.sqrt(math.log(40) / (2 * len(scores))) if scores else None
        result[name] = {
            'games': len(rows), 'complete_pairs': len(scores),
            'a_wins': sum(row['a_won'] for row in rows),
            'unfinished': sum(not row['finished'] for row in rows),
            'mean_pair_score_for_a': mean,
            'conservative_95_interval': ([max(0, mean - radius), min(1, mean + radius)]
                                         if scores else None),
        }
    return {
        'matchups': result,
        'method': ('Hoeffding bounded-mean interval treating each complete '
                   'opening pair as one independent observation.'),
        'limitations': ('Conditional on completed pairs and the supplied opening '
                        'distribution; incomplete pairs are excluded; no Elo estimate.'),
    }


def play_game(args, kata, broker, game, sequence):
    decisions = []
    with engine(args) as black_gp, engine(args) as white_gp:
        gps = (black_gp, white_gp)
        ref, moves = setup_game(gps, game['opening'])
        with (args.output / f'{game["stem"]}.jsonl').open('w', encoding='ascii') as wire:
            for turn in range(args.move_cap):
                if (args.output / 'STOP').exists():
                    break
                color = 'B' if len(moves) % 2 == 0 else 'W'
                role = role_for_color(game, color)
                actor = black_gp if color == 'B' else white_gp
                started = time.perf_counter()
                if role in ('HH', 'NH', 'NN'):
                    move, trace = hybrid_decision(actor, broker, moves, color, role,
                                                  args.time_ms)
                    other = white_gp if actor is black_gp else black_gp
                    other.command(f'play {color} {move}')
                else:
                    identifier = f'direct-{sequence}-{turn}-{role}'
                    move, trace = standalone_decision(kata, ref, moves, color, role,
                                                      args.time_ms, identifier)
                    for gp in gps:
                        gp.command(f'play {color} {move}')
                wall_ms = (time.perf_counter() - started) * 1000
                ref.play(color, move)
                for gp in gps:
                    ref.compare(gp.command('showboard'))
                moves.append([color, move])
                row = {'turn': turn, 'color': color, 'role': role, 'move': move,
                       'ms': wall_ms, 'trace': trace}
                decisions.append(row)
                wire.write(json.dumps(row, sort_keys=True) + '\n')
                wire.flush()
                if (turn + 1) % 100 == 0:
                    print(game['stem'], turn + 1, flush=True)
                if ref.passes == 2:
                    break
        finished = ref.passes == 2
        margin = ref.margin()
        winner_color = 'B' if margin > 0 else 'W' if margin < 0 else 'draw'
        result = f'{winner_color}+{abs(margin):g}' if margin else '0'
        if finished:
            for gp in gps:
                if gp.command('final_score') != result:
                    raise RuntimeError('referee and GTP final scores disagree')
        (args.output / f'{game["stem"]}.sgf').write_text(
            black_gp.command('gp-sgf'), encoding='ascii')
    a_won = finished and winner_color == game['a_color']
    return {
        'opening': game['opening']['id'], 'matchup': f'{game["a"]}-vs-{game["b"]}',
        'a': game['a'], 'b': game['b'], 'a_color': game['a_color'],
        'finished': finished, 'result': result if finished else 'unfinished',
        'a_won': a_won, 'moves': len(moves), 'raw_area_margin': margin,
        'roles': {role: summarize_role(decisions, role) for role in (game['a'], game['b'])},
    }


def validate_args(parser, args):
    if args.pairs < 1 or args.time_ms < 20 or args.move_cap < 2:
        parser.error('pairs must be positive, time-ms >= 20, and move-cap >= 2')
    for path in (args.katago, args.model, args.exe, args.profile, args.openings):
        if not path.is_file():
            parser.error(f'input file does not exist: {path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--katago', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--openings', type=Path, required=True)
    parser.add_argument('--pairs', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--time-ms', type=int, default=200)
    parser.add_argument('--move-cap', type=int, default=722)
    parser.add_argument('--cpu', action='store_true')
    parser.add_argument('--matchups', nargs='+', default=['NH:NN', 'NH:policy', 'NH:search'])
    args = parser.parse_args()
    validate_args(parser, args)
    matchups = parse_matchups(args.matchups)
    openings = load_openings(args.openings, args.pairs)
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    config = args.output / 'analysis.cfg'
    config.write_text(config_text(args.time_ms) +
                      ('\nnumEigenThreadsPerModel = 4\n' if args.cpu else ''), encoding='ascii')
    hashed = {'katago': args.katago, 'model': args.model, 'goproverbs': args.exe,
              'profile': args.profile, 'openings': args.openings, 'config': config,
              'harness': Path(__file__), 'guidance': ROOT / 'benchmarks/guidance.py',
              'neural': ROOT / 'benchmarks/neural.py', 'referee': ROOT / 'benchmarks/lab.py',
              'sgf': ROOT / 'benchmarks/sgf_io.py'}
    manifest = {
        'status': 'running', 'rules': 'tromp-taylor', 'board_size': SIZE, 'komi': KOMI,
        'settings': {key: str(value) if isinstance(value, Path) else value
                     for key, value in vars(args).items()},
        'matchups': [f'{a}-vs-{b}' for a, b in matchups],
        'hashes_before': {name: digest(path) for name, path in hashed.items()},
        'opening_ids': [opening['id'] for opening in openings],
        'games': [],
    }

    def save():
        (args.output / 'manifest.json').write_text(
            json.dumps(manifest, indent=2), encoding='ascii')
        (args.output / 'games.json').write_text(
            json.dumps(manifest['games'], indent=2), encoding='ascii')

    save()
    try:
        manifest['hardware_before'] = hardware()
        for directory in ('round-20260920', 'overnight-20260916'):
            if (Path.home() / 'ai_bench' / directory / 'RUNNING.lock').exists():
                raise RuntimeError(f'competing inference lock: {directory}')
        resident = manifest['hardware_before'].get('ollama', {}).get('stdout', '').strip().splitlines()
        if len(resident) > 1:
            raise RuntimeError('resident Ollama model; inspect before running')
        with KataGo(args.katago.resolve(), args.model.resolve(), config, args.output) as kata:
            manifest['version'] = kata.request(
                {'id': 'version', 'action': 'query_version'},
                deadline=time.perf_counter() + 30)
            with Broker(kata) as broker:
                broker.query([], 'B', SIZE, KOMI, deadline=time.perf_counter() + 30)
                manifest['hardware_loaded'] = hardware()
                for sequence, game in enumerate(build_schedule(openings, matchups)):
                    if (args.output / 'STOP').exists():
                        break
                    kata.request({'id': f'clear-{sequence}', 'action': 'clear_cache'},
                                 deadline=time.perf_counter() + 30)
                    manifest['games'].append(play_game(args, kata, broker, game, sequence))
                    print(game['stem'], manifest['games'][-1]['result'], flush=True)
                    save()
                manifest['broker'] = {'count': broker.count, 'errors': list(broker.errors),
                                      'metrics': dict(broker.metrics)}
                manifest['kata_metrics'] = dict(kata.metrics)
                if broker.errors:
                    raise RuntimeError('neural broker errors; inspect manifest')
            manifest['paired'] = paired_summary(manifest['games'])
            observed_hashes = {name: digest(path) for name, path in hashed.items()}
            if observed_hashes != manifest['hashes_before']:
                raise RuntimeError('pinned input changed during run')
            manifest['status'] = ('stopped' if (args.output / 'STOP').exists()
                                  else 'complete')
    except BaseException as exc:
        manifest['status'] = 'failed'
        manifest['error'] = repr(exc)
        raise
    finally:
        manifest['hardware_after'] = hardware()
        manifest['hashes_after'] = {name: digest(path) for name, path in hashed.items()}
        manifest['hashes_unchanged'] = manifest['hashes_after'] == manifest['hashes_before']
        save()


if __name__ == '__main__':
    main()
