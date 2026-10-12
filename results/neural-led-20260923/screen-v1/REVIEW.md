# Paired screen evidence review

Status: failed.
White live controls: 40/40; gate: passed.
Games recorded: 41/80.
Error: RuntimeError('Game operational gate failed; see saved game and traces')

| Matchup | Complete pairs | A wins / finished games | Unfinished | Pair score | 95% conservative interval |
|---|---:|---:|---:|---:|---|
| combined-vs-neural | 0 | 0/0 | 1 | None | None |
| neural-vs-policy | 20 | 24/40 | 0 | 0.6 | [0.2963192690458474, 0.9036807309541526] |

| Role | Decisions | Median ms | Max ms | Over 200 ms | Fallbacks | Completed rounds | Specialist-only choices |
|---|---:|---:|---:|---:|---:|---:|---:|
| combined | 144 | 122.02 | 223.45 | 10 | 10 | 134 | 14 |
| neural | 6677 | 62.59 | 209.33 | 9 | 9 | 6668 | 0 |
| policy | 6529 | 15.21 | 85.20 | 0 | 0 | 0 | 0 |

Neural role totals combine stages; inspect raw games for matchup-specific costs.
Incomplete pairs do not enter paired intervals; failed decisions do not become awarded losses.
Wins and selected specialist moves do not identify which individual overrides caused a result.
These screens do not automatically promote defaults or establish Elo.

combined-vs-neural: {"B": {"a_wins": 0, "draws": 0, "games": 0}, "W": {"a_wins": 0, "draws": 0, "games": 0}}

neural-vs-policy: {"B": {"a_wins": 12, "draws": 0, "games": 20}, "W": {"a_wins": 12, "draws": 0, "games": 20}}
