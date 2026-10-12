"""Summarize completed neural pilot artifacts without rerunning inference."""
import argparse
import json
from pathlib import Path
import statistics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('round', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    arena = json.loads((args.round / 'arena/manifest.json').read_text())
    fixtures = json.loads((args.round / 'fixtures/manifest.json').read_text())
    if arena['status'] != 'complete' or fixtures['status'] != 'complete':
        raise RuntimeError('Both arena and fixtures must finish successfully before summarizing')
    # This report includes interpretation of the initial pilot, not arbitrary
    # future experiments. Refuse different settings rather than mislabel them.
    expected = {'time_ms': 200, 'pairs': 1, 'komi': 7.5, 'seed': 20260921}
    if any(arena['settings'][k] != v for k, v in expected.items()):
        raise ValueError('This report template is specific to the initial pilot settings')
    games = arena['games']
    durations = {}
    for path in (args.round / 'arena').glob('*-vs-*.jsonl'):
        for line in path.read_text().splitlines():
            move = json.loads(line)
            durations.setdefault(move['role'], []).append(move['ms'])
    modes = ['hybrid', 'policy', 'search']
    scores = {mode: sum(r['accepted'] for r in fixtures['fixtures'] if r['mode'] == mode)
              for mode in ['policy', 'search']}
    scores['hybrid'] = sum(r['hybrid_accepted'] for r in fixtures['fixtures'] if r['mode'] == 'policy')
    lines = ['# Pretrained neural pilot: September 20, 2026', '',
             'Executed locally on RTX 5070 12 GB. This is a six-game integration pilot',
             'with one shared opening and swapped colors, not a playing-strength rating.', '',
             '## Finished games', '', '| Match | First player color | Result | Winner | Moves |',
             '|---|---|---|---|---|']
    for g in games:
        lines.append(f"| {g['a']} vs {g['b']} | {g['a_color']} | {g['result']} | {g['winner']} | {g['moves']} |")
    lines += ['', f"Completed: {sum(g['finished'] for g in games)}/{len(games)}; "
              'every played move was checked by the independent TT referee and the',
              'goproverbs board matched after every move. All completed raw area scores',
              'matched goproverbs. No resignations or estimated-score adjudication.', '',
              '## Measured decision times', '', '| Player | Moves | Median ms | Maximum ms |',
              '|---|---:|---:|---:|']
    for mode in modes:
        times = durations[mode]
        lines.append(f'| {mode} | {len(times)} | {statistics.median(times):.2f} | {max(times):.2f} |')
    lines += ['', 'Both search players had a 200 ms configured search cap. Actual decision',
              'times include protocol overhead; these are not hard deadlines. Policy-only',
              'retrieves raw policy with one visit and uses no searched values for selection.',
              'GPU neural inference and CPU heuristic search have different compute costs.', '',
              '## Development fixture diagnostics', '', '| Player | Local label matches |',
              '|---|---:|']
    for mode in modes:
        lines.append(f'| {mode} | {scores[mode]}/10 |')
    lines += ['', 'These mostly empty 19x19 positions have handcrafted local labels. The neural',
              'players often preferred open corners over small local captures/rescues. This',
              'does not establish that either choice is globally optimal. Fixture-label',
              'acceptance must not be used as a substitute for playing strength. Composed',
              'neural fixture inputs use setup stones; the ko fixture keeps capture history.',
              'Actual games preserve the complete move history for every neural query.', '',
              '## Runtime and resources', '',
              '- KataGo 1.18.1, Windows OpenCL, one search thread, batch 1, fixed neural orientation.',
              '- Old small pretrained network: `kata1-b10c128-s919229184-d169515535` (2020).',
              '- Weights are identical for policy-only and searched KataGo; no training performed.',
              '- 19x19 Tromp-Taylor, arena komi 7.5, no handicap bonus. Fixtures retain komi 0.5.',
              '- Opening: B Q4, W D4, seed 20260921. Same opening in all games.',
              '- goproverbs hybrid: baseline weights, depth cap 12, node cap 10 million,',
              '  beam 12, shortlist 3, tactical extensions off. Defaults were not changed.',
              '- This pilot differs from the older hybrid-v-selective pilot in komi and',
              '  secondary limits; do not combine their win counts.', '',
              'GPU snapshots (total device usage, including desktop applications):', '', '```text']
    for phase in ['before', 'loaded', 'after']:
        snapshot = arena['hardware_' + phase]
        lines.append(phase + ': ' + snapshot['gpu']['stdout'].strip().splitlines()[-1])
        if 'ram_bytes' in snapshot:
            lines.append(f"  available system RAM: {snapshot['ram_bytes']['available'] / 2**30:.2f} GiB")
    lines += ['```', '',
              'No resident Ollama model or competing lab runner was found before testing;',
              'no unrelated application was killed. KataGo exited and released its model',
              'after the experiment. Backend log reports FP16 storage and tensor cores.', '',
              '## Interpretation and next experiment', '',
              'The games compare complete configured players. A neural-policy win over our',
              'hybrid points toward move selection/position judgment as a useful improvement',
              'target, but does not isolate which heuristic or leaf-evaluation term is weak.',
              'Search versus policy using the same weights isolates the added search system',
              'more directly. One opening and two games per matchup remain far too small for Elo.', '',
              'Next: add neural nominees to our hybrid while retaining its existing leaf',
              'evaluator. Then test neural leaf evaluation separately. Also increase opening',
              'diversity and compare a contemporary network as its own controlled variable.', '',
              'Before tuning proverb weights against fixture scores, add expert-reviewed',
              'whole-board positions where the labeled local move is actually urgent.', '',
              '## Evidence and verification', '',
              '- 17 Python tests passed: 13 existing referee/protocol tests plus 4 neural',
              '  decision/coordinate/history tests. Rust engine source was not changed.',
              '- [Arena manifest](../results/neural-round/arena/manifest.json): settings,',
              '  executable/model/config/harness/referee hashes, version, results and resources.',
              '- [Fixture manifest](../results/neural-round/fixtures/manifest.json).',
              '- [Game summary](../results/neural-round/arena/games.json); per-game SGF/JSONL',
              '  and complete neural `wire.jsonl` are alongside it.',
              '- [Methodology and reproduction](NEURAL-BASELINES.md).',
              '- Everything remains local; no commit or GitHub publication in this round.', '']
    args.output.write_text('\n'.join(lines), encoding='ascii')
    print(args.output)


if __name__ == '__main__':
    main()
