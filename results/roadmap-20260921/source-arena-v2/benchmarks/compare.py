"""Paired-color search-versus-search matches with an independent TT referee."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import time

from lab import COLUMNS, GTP, ROOT, Referee


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, default=ROOT / 'target/release/goproverbs.exe')
    parser.add_argument('--profile-a', type=Path, default=ROOT / 'profiles/baseline.weights')
    parser.add_argument('--profile-b', type=Path, default=ROOT / 'profiles/baseline.weights')
    parser.add_argument('--mode-a', choices=['selective', 'full', 'minimax', 'hybrid'], default='selective')
    parser.add_argument('--mode-b', choices=['selective', 'full', 'minimax', 'hybrid'], default='selective')
    parser.add_argument('--shortlist', type=int, default=3)
    parser.add_argument('--time-ms', type=int, default=1000)
    parser.add_argument('--move-cap', type=int, default=None)
    parser.add_argument('--tactical-a', type=int, choices=range(5), default=0)
    parser.add_argument('--tactical-b', type=int, choices=range(5), default=0)
    parser.add_argument('--size', type=int, choices=range(2, 26), default=9)
    parser.add_argument('--pairs', type=int, default=6)
    parser.add_argument('--seed', type=int, default=20260921)
    parser.add_argument('--nodes', type=int, default=2000)
    parser.add_argument('--depth', type=int, default=3)
    parser.add_argument('--beam', type=int, default=12)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.pairs < 1:
        parser.error('--pairs must be positive')
    if args.output.exists():
        parser.error('output already exists; choose a new result directory')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    records = []
    settings = {'exe': args.exe, 'size': args.size, 'nodes': args.nodes,
                'depth': args.depth, 'beam': args.beam, 'shortlist': args.shortlist, 'time_ms': args.time_ms}
    for pair in range(args.pairs):
        opening = []
        ref = Referee(args.size)
        for color in ['B', 'W']:
            choices = [f'{COLUMNS[x]}{y+1}' for x in range(args.size) for y in range(args.size)]
            rng.shuffle(choices)
            for move in choices:
                try:
                    ref.play(color, move)
                    opening.append((color, move))
                    break
                except AssertionError:
                    continue
        for a_color in ['B', 'W']:
            ref = Referee(args.size)
            decisions = []
            with GTP(**settings, profile=args.profile_a, tactical=args.tactical_a, search_mode=args.mode_a) as a, \
                 GTP(**settings, profile=args.profile_b, tactical=args.tactical_b, search_mode=args.mode_b) as b:
                for engine in [a, b]:
                    engine.command('komi 0.5')
                    for color, move in opening:
                        engine.command(f'play {color} {move}')
                for color, move in opening:
                    ref.play(color, move)
                finished = False
                for turn in range(args.move_cap if args.move_cap is not None else 4 * args.size ** 2):
                    color = 'B' if turn % 2 == 0 else 'W'
                    actor, observer = (a, b) if color == a_color else (b, a)
                    started = time.perf_counter()
                    move = actor.command(f'genmove {color}')
                    trace = actor.command('gp-last-search')
                    elapsed = (time.perf_counter() - started) * 1000
                    observer.command(f'play {color} {move}')
                    ref.play(color, move)
                    for engine in [a, b]:
                        ref.compare(engine.command('showboard'))
                    decisions.append({'role': 'a' if color == a_color else 'b', 'color': color,
                                      'move': move, 'ms': round(elapsed, 3), 'trace': trace})
                    if ref.passes == 2:
                        finished = True
                        break
                margin = ref.margin()
                winner = 'B' if margin > 0 else 'W' if margin < 0 else 'draw'
                result = 'unfinished'
                if finished:
                    result = f'{winner}+{abs(margin):g}' if winner != 'draw' else '0'
                    for engine in [a, b]:
                        assert engine.command('final_score') == result
                stem = args.output.parent / f'game-{pair}-{a_color}'
                stem.with_suffix('.sgf').write_text(a.command('gp-sgf'), encoding='ascii')
                stem.with_suffix('.json').write_text(json.dumps(decisions, indent=2), encoding='ascii')
                record = {'pair': pair, 'a_color': a_color, 'opening': opening,
                          'finished': finished, 'result': result, 'moves': len(decisions) + 2,
                          'winner': ('a' if winner == a_color else 'b') if finished and winner != 'draw' else winner if finished else None,
                          'final_board_margin': margin}
                records.append(record)
                print(f"pair={pair} a={a_color} result={result} winner={record['winner']}", flush=True)
    result = {'games': records, 'a_wins': sum(r['winner'] == 'a' for r in records),
              'b_wins': sum(r['winner'] == 'b' for r in records),
              'draws': sum(r['winner'] == 'draw' for r in records),
              'unfinished': sum(not r['finished'] for r in records),
              'seed': args.seed, 'board_size': args.size, 'komi': 0.5,
              'limits': {'nodes': args.nodes, 'depth': args.depth, 'beam': args.beam, 'time_ms': args.time_ms, 'shortlist': args.shortlist, 'move_cap': args.move_cap},
              'a': {'profile': str(args.profile_a), 'profile_sha256': digest(args.profile_a), 'tactical_plies': args.tactical_a, 'mode': args.mode_a},
              'b': {'profile': str(args.profile_b), 'profile_sha256': digest(args.profile_b), 'tactical_plies': args.tactical_b, 'mode': args.mode_b},
              'executable_sha256': digest(args.exe), 'harness_sha256': digest(__file__),
              'referee_sha256': digest(ROOT / 'benchmarks/lab.py'),
              'independent_referee_checked_both_boards_and_final_scores': True}
    args.output.write_text(json.dumps(result, indent=2), encoding='ascii')
    print(json.dumps({k: v for k, v in result.items() if k != 'games'}, indent=2), flush=True)


if __name__ == '__main__':
    main()
