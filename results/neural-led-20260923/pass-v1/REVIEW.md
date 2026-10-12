# Paired screen evidence review

Status: complete.
White live controls: 45/45; gate: passed.
Games recorded: 80/80.
Error: none

| Matchup | Complete pairs | A wins / finished games | Unfinished | Pair score | 95% conservative interval |
|---|---:|---:|---:|---:|---|
| combined-vs-neural | 20 | 21/40 | 0 | 0.525 | [0.22131926904584742, 0.8286807309541526] |
| neural-vs-policy | 20 | 20/40 | 0 | 0.5 | [0.1963192690458474, 0.8036807309541526] |

| Role | Decisions | Median ms | Max ms | Over 200 ms | Fallbacks | Completed rounds | Pass agreements | Specialist-only choices |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| combined | 7284 | 47.81 | 100.03 | 0 | 0 | 7281 | 3 | 728 |
| neural | 13781 | 12.69 | 45.78 | 0 | 0 | 13753 | 28 | 0 |
| policy | 6495 | 2.95 | 9.66 | 0 | 0 | 0 | 0 | 0 |

Neural role totals combine stages; inspect raw games for matchup-specific costs.
Incomplete pairs do not enter paired intervals; failed decisions do not become awarded losses.
Wins and selected specialist moves do not identify which individual overrides caused a result.
These screens do not automatically promote defaults or establish Elo.

combined-vs-neural: {"B": {"a_wins": 11, "draws": 0, "games": 20}, "W": {"a_wins": 10, "draws": 0, "games": 20}}

neural-vs-policy: {"B": {"a_wins": 8, "draws": 0, "games": 20}, "W": {"a_wins": 12, "draws": 0, "games": 20}}
