# Pretrained neural pilot: September 20, 2026

Executed locally on RTX 5070 12 GB. This is a six-game integration pilot
with one shared opening and swapped colors, not a playing-strength rating.

## Finished games

| Match | First player color | Result | Winner | Moves |
|---|---|---|---|---|
| policy vs hybrid | B | B+208.5 | policy | 491 |
| policy vs hybrid | W | W+216.5 | policy | 494 |
| search vs hybrid | B | B+219.5 | search | 507 |
| search vs hybrid | W | W+256.5 | search | 544 |
| search vs policy | B | B+130.5 | search | 363 |
| search vs policy | W | W+39.5 | search | 310 |

Completed: 6/6; every played move was checked by the independent TT referee and the
goproverbs board matched after every move. All completed raw area scores
matched goproverbs. No resignations or estimated-score adjudication.

## Measured decision times

| Player | Moves | Median ms | Maximum ms |
|---|---:|---:|---:|
| hybrid | 1013 | 200.42 | 201.12 |
| policy | 825 | 3.81 | 9.33 |
| search | 859 | 200.53 | 207.64 |

Both search players had a 200 ms configured search cap. Actual decision
times include protocol overhead; these are not hard deadlines. Policy-only
retrieves raw policy with one visit and uses no searched values for selection.
GPU neural inference and CPU heuristic search have different compute costs.

## Development fixture diagnostics

| Player | Local label matches |
|---|---:|
| hybrid | 7/10 |
| policy | 5/10 |
| search | 5/10 |

These mostly empty 19x19 positions have handcrafted local labels. The neural
players often preferred open corners over small local captures/rescues. This
does not establish that either choice is globally optimal. Fixture-label
acceptance must not be used as a substitute for playing strength. Composed
neural fixture inputs use setup stones; the ko fixture keeps capture history.
Actual games preserve the complete move history for every neural query.

## Runtime and resources

- KataGo 1.18.1, Windows OpenCL, one search thread, batch 1, fixed neural orientation.
- Old small pretrained network: `kata1-b10c128-s919229184-d169515535` (2020).
- Weights are identical for policy-only and searched KataGo; no training performed.
- 19x19 Tromp-Taylor, arena komi 7.5, no handicap bonus. Fixtures retain komi 0.5.
- Opening: B Q4, W D4, seed 20260921. Same opening in all games.
- goproverbs hybrid: baseline weights, depth cap 12, node cap 10 million,
  beam 12, shortlist 3, tactical extensions off. Defaults were not changed.
- This pilot differs from the older hybrid-v-selective pilot in komi and
  secondary limits; do not combine their win counts.

GPU snapshots (total device usage, including desktop applications):

```text
before: NVIDIA GeForce RTX 5070, 2090 MiB, 9854 MiB, 610.60
  available system RAM: 4.91 GiB
loaded: NVIDIA GeForce RTX 5070, 2273 MiB, 9671 MiB, 610.60
  available system RAM: 4.67 GiB
after: NVIDIA GeForce RTX 5070, 2090 MiB, 9854 MiB, 610.60
  available system RAM: 6.37 GiB
```

No resident Ollama model or competing lab runner was found before testing;
no unrelated application was killed. KataGo exited and released its model
after the experiment. Backend log reports FP16 storage and tensor cores.

## Interpretation and next experiment

The games compare complete configured players. A neural-policy win over our
hybrid points toward move selection/position judgment as a useful improvement
target, but does not isolate which heuristic or leaf-evaluation term is weak.
Search versus policy using the same weights isolates the added search system
more directly. One opening and two games per matchup remain far too small for Elo.

Next: add neural nominees to our hybrid while retaining its existing leaf
evaluator. Then test neural leaf evaluation separately. Also increase opening
diversity and compare a contemporary network as its own controlled variable.

Before tuning proverb weights against fixture scores, add expert-reviewed
whole-board positions where the labeled local move is actually urgent.

## Evidence and verification

- 17 Python tests passed: 13 existing referee/protocol tests plus 4 neural
  decision/coordinate/history tests. Rust engine source was not changed.
- [Arena manifest](../results/neural-round/arena/manifest.json): settings,
  executable/model/config/harness/referee hashes, version, results and resources.
- [Fixture manifest](../results/neural-round/fixtures/manifest.json).
- [Game summary](../results/neural-round/arena/games.json); per-game SGF/JSONL
  and complete neural `wire.jsonl` are alongside it.
- [Methodology and reproduction](NEURAL-BASELINES.md).
- Everything remains local; no commit or GitHub publication in this round.
