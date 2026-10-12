"""Summarize stored direct comparisons and fixture evaluations without rerunning."""
import argparse
from collections import Counter
import json
from pathlib import Path
import statistics


def summarize(directory):
    result = {'comparisons': [], 'fixtures': []}
    for path in sorted(directory.glob('*/report.json')):
        report = json.loads(path.read_text())
        roles = {'a': [], 'b': []}
        for trace_path in sorted(path.parent.glob('game-*.json')):
            for decision in json.loads(trace_path.read_text()):
                fields = dict(x.split('=', 1) for x in decision['trace'].splitlines()[0].split())
                roles[decision['role']].append((decision['ms'], int(fields['depth']), int(fields['nodes']),
                                                 int(fields.get('tactical_nodes', 0)), fields['limited'] == 'true'))
        measurements = {}
        for role, rows in roles.items():
            if rows:
                measurements[role] = {'moves': len(rows), 'median_ms': round(statistics.median(r[0] for r in rows), 3),
                                      'max_ms': max(r[0] for r in rows),
                                      'depth_counts': dict(sorted(Counter(r[1] for r in rows).items())),
                                      'limited_moves': sum(r[4] for r in rows),
                                      'tree_nodes': sum(r[2] for r in rows),
                                      'extended_internal_nodes': sum(r[3] for r in rows)}
        result['comparisons'].append({'experiment': path.parent.name,
            **{k: report[k] for k in ['a_wins', 'b_wins', 'draws', 'unfinished']}, 'measurements': measurements})
    for path in sorted(directory.glob('*.json')):
        report = json.loads(path.read_text())
        if not isinstance(report, dict) or report.get('mode') != 'evaluate':
            continue
        rows = report['fixtures']
        result['fixtures'].append({'experiment': path.stem, 'total': len(rows),
                                  'search_pass': sum(r['search_pass'] for r in rows),
                                  'one_ply_pass': sum(r['baseline_pass'] for r in rows),
                                  'failures': [r['id'] for r in rows if not r['search_pass']]})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    summary = summarize(args.directory)
    (args.directory / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='ascii')
    for item in summary['comparisons']:
        print(f"{item['experiment']}: {item['a_wins']}-{item['b_wins']} unfinished={item['unfinished']}")
    for item in summary['fixtures']:
        print(f"{item['experiment']}: {item['search_pass']}/{item['total']}")


if __name__ == '__main__':
    main()

