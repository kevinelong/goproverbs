# Paired screen evidence review

Status: failed.
White live controls: 45/45; gate: passed.
Games recorded: 5/40.
Error: RuntimeError('Game operational gate failed; see saved game and traces')

| Matchup | Complete pairs | A wins / finished games | Unfinished | Pair score | 95% conservative interval |
|---|---:|---:|---:|---:|---|
| combined-vs-neural | 2 | 2/4 | 1 | 0.5 | [0, 1] |

| Role | Decisions | Median ms | Max ms | Over 200 ms | Fallbacks | Completed rounds | Specialist-only choices |
|---|---:|---:|---:|---:|---:|---:|---:|
| combined | 1163 | 56.48 | 153.06 | 0 | 0 | 1163 | 96 |
| neural | 1163 | 18.94 | 98.26 | 0 | 0 | 1163 | 0 |

Neural role totals combine stages; inspect raw games for matchup-specific costs.
Incomplete pairs do not enter paired intervals; failed decisions do not become awarded losses.
Wins and selected specialist moves do not identify which individual overrides caused a result.
These screens do not automatically promote defaults or establish Elo.

combined-vs-neural: {"B": {"a_wins": 0, "draws": 0, "games": 2}, "W": {"a_wins": 2, "draws": 0, "games": 2}}
