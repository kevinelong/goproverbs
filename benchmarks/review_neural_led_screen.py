"""Read-only evidence aggregation for a completed or stopped paired screen."""
import argparse
import json
from pathlib import Path
import statistics

from direct_arena import paired_summary


def review(output):
    state = json.loads((output/'status.json').read_text())
    games = json.loads((output/'games.json').read_text())
    rows = []
    for path in sorted(output.glob('led-fresh-*.jsonl')):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            row['file'] = path.name
            rows.append(row)
    metrics = {}
    for role in sorted({r['role'] for r in rows}):
        decisions = [r for r in rows if r['role'] == role and 'move' in r]
        if not decisions:
            continue
        times = [r['ms'] for r in decisions]
        metrics[role] = dict(decisions=len(decisions), median_ms=statistics.median(times),
            max_ms=max(times), over_200=sum(t > 200 for t in times),
            over_205=sum(t > 205 for t in times),
            completed_rounds=sum(r['trace']['completed_rounds'] for r in decisions),
            pass_agreements=sum(r['trace'].get('pass_agreement',False) for r in decisions),
            fallbacks=sum(r['trace']['fallback'] for r in decisions),
            policy_overrides=sum(r['move'] != r['trace']['root_move'] for r in decisions),
            specialist_only_selected=sum(any(c['move'] == r['move'] and 'neural' not in c['sources']
                for c in r['trace']['candidates']) for r in decisions))
    paired = paired_summary(games)
    colors = {}
    for name in paired['matchups']:
        colors[name] = {}
        for color in ('B', 'W'):
            selected = [g for g in games if g['matchup'] == name and g['a_color'] == color and g['finished']]
            colors[name][color] = dict(games=len(selected), a_wins=sum(g['a_won'] for g in selected),
                                       draws=sum(g['result'] == '0' for g in selected))
    return dict(status=state, paired=paired, role_metrics=metrics, colors=colors,
                decision_errors=[r for r in rows if 'error' in r])


def render(data):
    s = data['status']
    lines = ['# Paired screen evidence review', '', f'Status: {s["status"]}.',
             f'White live controls: {s.get("white_completed", 0)}/{s.get("white_expected", 40)}; gate: {s.get("white_gate", "held")}.',
             f'Games recorded: {s.get("games_recorded", 0)}/{s.get("games_expected", 80)}.',
             f'Error: {s.get("error", "none")}', '',
             '| Matchup | Complete pairs | A wins / finished games | Unfinished | Pair score | 95% conservative interval |',
             '|---|---:|---:|---:|---:|---|']
    for name, row in data['paired']['matchups'].items():
        lines.append(f'| {name} | {row["complete_pairs"]} | {row["a_wins"]}/{row["games"]-row["unfinished"]} | {row["unfinished"]} | '
                     f'{row["mean_pair_score_for_a"]} | {row["conservative_95_interval"]} |')
    lines += ['', '| Role | Decisions | Median ms | Max ms | Over 200 ms | Fallbacks | Completed rounds | Pass agreements | Specialist-only choices |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for role, row in data['role_metrics'].items():
        lines.append(f'| {role} | {row["decisions"]} | {row["median_ms"]:.2f} | {row["max_ms"]:.2f} | '
                     f'{row["over_200"]} | {row["fallbacks"]} | {row["completed_rounds"]} | {row["pass_agreements"]} | {row["specialist_only_selected"]} |')
    lines += ['', 'Neural role totals combine stages; inspect raw games for matchup-specific costs.',
              'Incomplete pairs do not enter paired intervals; failed decisions do not become awarded losses.',
              'Wins and selected specialist moves do not identify which individual overrides caused a result.',
              'These screens do not automatically promote defaults or establish Elo.']
    for name, colors in data['colors'].items():
        lines += ['', name+': '+json.dumps(colors, sort_keys=True)]
    return '\n'.join(lines)+'\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    data = review(args.output)
    (args.output/'REVIEW.json').write_text(json.dumps(data, indent=2), encoding='ascii')
    (args.output/'REVIEW.md').write_text(render(data), encoding='ascii')
    print(render(data))
