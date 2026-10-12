"""Build reproducible development positions and frozen opening manifests."""
import argparse
import hashlib
import json
from pathlib import Path
import random

from lab import COLUMNS, Referee
from sgf_io import read_game, replay


def openings(seed, count):
    rng = random.Random(seed)
    points = [f'{COLUMNS[x]}{y}' for x in [2, 3, 15, 16] for y in [3, 4, 16, 17]]
    result, seen = [], set()
    while len(result) < count:
        sequence = rng.sample(points, rng.choice([2, 4, 6]))
        key = tuple(sequence)
        if key in seen: continue
        seen.add(key)
        moves = [['B' if i % 2 == 0 else 'W', move] for i, move in enumerate(sequence)]
        ref = Referee(19, 7.5)
        for color, move in moves: ref.play(color, move)
        result.append({'id': f'opening-{len(result):03d}', 'moves': moves})
    return result


def build(paths):
    rows, failures, seen = [], [], set()
    for path in sorted(paths):
        try:
            game = read_game(path.read_text(encoding='utf-8-sig'))
            if game['size'] != 19: continue
            replay(game)
            source = game['source_sha256']
            if source in seen: continue
            seen.add(source)
            # All positions from the same game stay together. These historical
            # games were already inspected; both splits are development only.
            split = 'development-validation' if int(source[:8], 16) % 4 == 0 else 'development-train'
            for ply in [20, 80, 160, 240]:
                if ply >= len(game['moves']): continue
                moves = game['moves'][:ply]
                rows.append({'id': source[:12] + f'-{ply}', 'source_game': source,
                    'source_path': str(path), 'split': split, 'size': 19, 'komi': game['komi'],
                    'moves': moves, 'color': 'W' if moves[-1][0] == 'B' else 'B',
                    'label': None, 'expert_reviewed': False})
        except (ValueError, AssertionError, UnicodeError) as exc:
            failures.append({'path': str(path), 'error': str(exc)})
    return {'positions': rows, 'rejected_sources': failures,
            'note': 'Historical lab games, no pristine holdout or expert best-move labels.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seed', type=int, default=20260921)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    corpus = build(args.input.rglob('*.sgf'))
    (args.output/'positions.json').write_text(json.dumps(corpus, indent=2), encoding='ascii')
    (args.output/'openings.json').write_text(json.dumps({'seed':args.seed,'openings':openings(args.seed, 50)}, indent=2), encoding='ascii')
    print('Positions:', len(corpus['positions']), 'rejected:', len(corpus['rejected_sources']))
