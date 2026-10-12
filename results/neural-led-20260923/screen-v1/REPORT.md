# Neural-led paired screens

Status: failed
White validation: 40/40
Games recorded: 41/80

| Matchup | Games | Complete pairs | A wins | Unfinished | Pair score | Conservative 95% interval |
|---|---:|---:|---:|---:|---:|---|
| combined-vs-neural | 1 | 0 | 0 | 1 | None | None |
| neural-vs-policy | 40 | 20 | 24 | 0 | 0.6 | [0.2963192690458474, 0.9036807309541526] |

Hoeffding bounded-mean interval treating each complete opening pair as one independent observation.
Conditional on completed pairs and the supplied opening distribution; incomplete pairs are excluded; no Elo estimate.

No automatic expansion or default promotion. See status.json for operational failures.
