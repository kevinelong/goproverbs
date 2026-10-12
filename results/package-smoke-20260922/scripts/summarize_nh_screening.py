"""Validate and summarize a completed frozen NH screening without inference."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    directory = args.directory.resolve()
    snapshot, run = directory / 'snapshot', directory / 'run'
    plan = json.loads((directory / 'plan.json').read_text())
    manifest = json.loads((run / 'manifest.json').read_text())
    assert manifest['status'] == 'complete', manifest['status']
    assert manifest['broker_errors'] == []
    for name, expected in plan['snapshot_hashes'].items():
        assert digest(snapshot / name) == expected, name
    for name, expected in plan['fixed_external_hashes'].items():
        assert digest(Path(name)) == expected, name
    for name, expected in manifest['hashes'].items():
        assert digest(Path(name)) == expected, name
    sys.path.insert(0, str(snapshot / 'benchmarks'))
    from paired_summary import summarize
    games = json.loads((run / 'games.json').read_text())
    assert games == manifest['records']
    assert len(games) == plan['expected_games'] == 40
    ids = plan['selected_opening_ids']
    assert {(g['opening'], g['variant_color']) for g in games} == {(i, c) for i in ids for c in ('B', 'W')}
    assert all(g['finished'] and g['mode'] == 'NH' for g in games)
    opening_lengths = {r['id']: len(r['moves']) for r in json.loads((snapshot / 'openings.json').read_text())['openings']}
    times = {'NH': [], 'HH': []}
    remaining = {'NH': [], 'HH': []}
    depths = {'NH': Counter(), 'HH': Counter()}
    hint_selected = Counter()
    for game in games:
        stem = f"{game['opening']}-NH-{game['variant_color']}"
        with (run / (stem + '.jsonl')).open() as stream:
            count = 0
            for index, line in enumerate(stream):
                row = json.loads(line)
                color = 'B' if index % 2 == 0 else 'W'
                mode = 'NH' if color == game['variant_color'] else 'HH'
                assert row['color'] == color and row['mode'] == mode
                trace = row['trace']
                assert trace['mode'] == mode
                assert 'external_leaf=true' not in trace['report']
                assert mode != 'HH' or not trace['hints']
                assert math.isfinite(trace['ms']) and trace['ms'] >= 0
                times[mode].append(trace['ms'])
                remaining[mode].append(trace['remaining_search_ms'])
                depths[mode][re.search(r' depth=(\d+)', trace['report']).group(1)] += 1
                hint_selected[mode] += row['move'] in trace['hints']
                count += 1
        assert count + opening_lengths[game['opening']] == game['moves']
        assert (run / (stem + '.sgf')).is_file()
    assert manifest['broker_queries'] == len(times['NH']) + 1  # One warmup.
    paired = summarize(games)
    assert paired['variants']['NH']['complete_pairs'] == 20
    timing = {}
    for mode, values in times.items():
        ordered = sorted(values)
        timing[mode] = {'decisions': len(values), 'median_ms': statistics.median(values),
                        'p95_ms': ordered[math.ceil(.95 * len(values)) - 1], 'max_ms': max(values),
                        'over_200_ms': sum(v > 200 for v in values),
                        'over_210_ms': sum(v > 210 for v in values),
                        'zero_remaining_search_budget': sum(v == 0 for v in remaining[mode]),
                        'median_remaining_search_ms': statistics.median(remaining[mode]),
                        'completed_depths': dict(depths[mode]),
                        'selected_move_in_neural_hints': hint_selected[mode]}
    result = {'validation': 'complete: 40 finished games, 20 distinct color-swapped pairs, all pinned hashes match',
              'selected_opening_ids': ids, 'pilot_excluded': True, 'paired': paired,
              'timing': timing, 'broker_queries': manifest['broker_queries'], 'broker_errors': [],
              'total_moves_including_openings': sum(g['moves'] for g in games),
              'limitations': ['Unused development openings, not pristine expert-reviewed holdout.',
                              'Screening evidence at one budget/network/backend, not an Elo rating.',
                              'Cooperative 200 ms budget includes root nomination; wall overshoot is reported.',
                              'This run uses the frozen native Windows pilot executable, not the WSL performance snapshot.']}
    with (directory / 'summary.json').open('x', encoding='ascii') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
