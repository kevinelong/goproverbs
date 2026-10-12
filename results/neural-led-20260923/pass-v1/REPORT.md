# Neural-led paired screens

Status: complete
White validation: 45/45
Games recorded: 80/80

| Matchup | Games | Complete pairs | A wins | Unfinished | Pair score | Conservative 95% interval |
|---|---:|---:|---:|---:|---:|---|
| combined-vs-neural | 40 | 20 | 21 | 0 | 0.525 | [0.22131926904584742, 0.8286807309541526] |
| neural-vs-policy | 40 | 20 | 20 | 0 | 0.5 | [0.1963192690458474, 0.8036807309541526] |

Hoeffding bounded-mean interval treating each complete opening pair as one independent observation.
Conditional on completed pairs and the supplied opening distribution; incomplete pairs are excluded; no Elo estimate.

No automatic expansion or default promotion. See status.json for operational failures.
