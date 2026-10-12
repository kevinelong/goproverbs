"""Read historical NH traces without re-running or modifying their evidence."""
import hashlib
import json
from pathlib import Path


def diagnose(directory):
    groups = {}
    hashes = {}
    for path in sorted(directory.glob('opening-*.jsonl')):
        opponent = path.stem.split('-vs-')[1].rsplit('-', 1)[0]
        group = groups.setdefault(opponent, dict(decisions=0, with_hints=0,
                                                 first_hint=0, any_hint=0, outside_hints=0))
        raw = path.read_bytes()
        hashes[path.name] = hashlib.sha256(raw).hexdigest()
        for line in raw.splitlines():
            row = json.loads(line)
            if row['role'] != 'NH':
                continue
            group['decisions'] += 1
            hints = row['trace'].get('hints', [])
            if hints:
                group['with_hints'] += 1
                group['first_hint'] += row['move'] == hints[0]
                group['any_hint'] += row['move'] in hints
                group['outside_hints'] += row['move'] not in hints
    return {'source': str(directory), 'input_sha256': hashes, 'groups': groups,
            'interpretation': 'Override frequency only; no per-move harm or causal attribution.'}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = diagnose(args.directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='ascii') as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps(result['groups'], indent=2))
