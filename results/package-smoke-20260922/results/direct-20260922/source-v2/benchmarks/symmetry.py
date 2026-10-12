"""Generate eight board symmetries per development fixture (not independent games)."""
import argparse
import copy
import json
from pathlib import Path

from lab import COLUMNS, ROOT, load_cases


def transform(vertex, size, rotations, mirrored):
    if vertex == 'pass':
        return vertex
    x, y = COLUMNS.index(vertex[0]), size - int(vertex[1:])
    if mirrored:
        x = size - 1 - x
    for _ in range(rotations):
        x, y = size - 1 - y, x
    return f'{COLUMNS[x]}{size-y}'


def expand(cases):
    result = []
    for base in cases:
        for mirrored in [False, True]:
            for rotation in range(4):
                case = copy.deepcopy(base)
                convert = lambda v: transform(v, case['size'], rotation, mirrored)
                case['id'] = f"{base['id']}-m{int(mirrored)}r{rotation}"
                case['base_id'] = base['id']
                case['moves'] = [[c, convert(v)] for c, v in base['moves']]
                for label in ['accept', 'reject']:
                    if label in case:
                        case[label] = [convert(v) for v in base[label]]
                result.append(case)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'benchmarks/fixtures.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; choose a new file')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(expand(load_cases(args.input)), indent=2), encoding='ascii')


if __name__ == '__main__':
    main()
