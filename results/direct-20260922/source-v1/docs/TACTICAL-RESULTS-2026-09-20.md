# Tactical research results - 2026-09-20

## Decision

Keep the baseline profile and leave tactical extensions disabled by default.
The new extension mechanism, comparison harness, and symmetry checks are
available for controlled experiments. None of the tested alternatives improved
the direct match result against baseline search at the tested budget.

This follow-up tests two changes separately and together: two extra tactical
plies at atari leaves, and reducing `atari_risk` from -1.5 to -0.5. It also tests
the previously fixture-tuned profile directly against baseline search.

## Direct matches

All use the same executable, 9x9 Tromp-Taylor, komi 0.5, maximum 2,000 tree
nodes / 1,000 ms / depth 3 / quiet beam 12 per move. Seed 20260921 produces six
two-move openings, each played with colors swapped. A is the variant below;
B always uses baseline weights with extensions off. Both players search.

| Variant A | A wins | Baseline wins | Unfinished |
| --- | ---: | ---: | ---: |
| Two tactical extension plies | 5 | 7 | 0 |
| Smaller atari penalty only | 2 | 10 | 0 |
| Extensions plus smaller penalty | 3 | 9 | 0 |
| Previously tuned profile, no extensions | 5 | 7 | 0 |

All **48 games** completed. An independent Python referee agreed with every
move, both engines' resulting boards, and both final scores. Individual SGFs
and decision traces sit beside each report:

- [Extensions](../results/tactical-round/extensions-v-baseline/report.json)
- [Smaller penalty](../results/tactical-round/material-v-baseline/report.json)
- [Combined](../results/tactical-round/combined-v-baseline/report.json)
- [Tuned](../results/tactical-round/tuned-v-baseline/report.json)

These are six paired openings per comparison, not a rating test. Results are
conditional on this engine, board size, opening sample, and budget. In
particular, the match budget is smaller than the CLI's default 20,000 nodes /
depth 4. No variant was promoted from a small favorable subset of games.

## Fixture checks

Maximum 5,000 nodes / 1,000 ms / depth 3 / beam 12. No labels or weights were
retuned during this round. The additional 88 cases are the original eleven
positions rotated/reflected eight ways; they are correlated development
checks, not 88 independent positions or a pristine held-out set.

| Search configuration | Original cases | Rotations/reflections |
| --- | ---: | ---: |
| Baseline | 9/11 | 67/88 |
| Extensions | 9/11 | 67/88 |
| Smaller atari penalty | 10/11 | 78/88 |
| Both changes | 10/11 | 78/88 |

The smaller penalty improves local acceptance but loses most direct matches.
This is a concrete reason not to optimize only for the current small fixture
suite. The single-stone rescue case still fails its immediate-rescue label;
that label expresses intended local urgency, not proof that a sacrifice or
move elsewhere must be wrong in the full position.

Orientation checks also reveal sensitivity to tie breaking and beam selection.
For example, baseline search captures the center pair immediately in only
three of its eight orientations. The move-order features can be symmetric
while a pruned, deterministically ordered search chooses different continuations.
Fixing that requires better candidate selection/evaluation and wider evidence;
rotating a few passing examples is not sufficient validation.

[Machine-readable summary](../results/tactical-round/summary.json),
[original fixtures](../benchmarks/fixtures.json), and
[generated symmetry fixtures](../results/tactical-round/symmetry-fixtures.json).
Detailed per-position reports are the `baseline`, `extensions`, `material`,
`combined`, and corresponding `symmetry-*` JSON files in that result directory.

## Why extensions did not earn a default change

In the extension-only comparison, the extra reader completed normal depth 3
on just 89 of 615 moves (14.5%); baseline completed it on 603 of 616 (97.9%).
Extra tactical work consumed the shared node allowance, leaving less completed
whole-board search. Median search round trip was about 102 ms versus 37 ms.
The time ceiling was the same, but equal node ceilings do not imply equal work
per node or equal actual elapsed time. Timing now uses Python `perf_counter`
for finer resolution than the previous harness's Windows monotonic readings.

The trigger considers any group in atari, and each extended node still ranks
all legal moves before selecting tactical alternatives. That is intentionally
simple and measurable, but too broad/expensive to assume a strength benefit.
Also, two extra plies can still end in an unstable position. The mechanism is
bounded tactical reading, not a life-and-death solver.

## Implementation and reproducibility

- `Limits::tactical_plies`, CLI `--tactical-plies 0..4`, and GTP `gp-tactical`.
- An extended leaf keeps captures, rescues, new ataris, pass, and one quiet
  alternative, allowing a threat to be ignored. It never uses a fictitious pass.
- Extensions consume the ordinary node/time budgets and decrease their own
  per-line allowance. Completed-iteration fallback remains intact.
- `tactical_nodes` telemetry; longer principal variations remain legal and
  their leaf terms plus edge preferences still explain the score.
- `benchmarks/compare.py`: two synchronized search engines, paired colors,
  independent referee, per-game SGF/trace output, and configuration hashes.
- `benchmarks/symmetry.py`: transformed moves and labels, preserving family/split.
- `benchmarks/summarize.py`: repeatable aggregation from saved evidence.
- `profiles/material-risk.weights`: optional partial profile; no default changed.

All engine experiments use executable SHA256
`b499c25a6005c5f51fc4654c4175df2edc92ba9073bdbba8b8ef2147814ddd59`.
Individual reports record executable, profile, harness, and fixture/referee
hashes as appropriate. The current source manifest is saved with this round.
Earlier results are preserved in their original directories.

See [controls and methodology](TACTICAL-SEARCH.md) for commands. The match
harness refuses an existing report path; use a new output directory for a new
experiment. These tests use CPU only and need no model server or VRAM cleanup.

## Validation

- **35 Rust integration tests passed**, including new tactical extension budget,
  legal variation, quiet-leaf, and invalid-limit tests.
- **10 Python tests passed**, including independent referee cases and release
  protocol tests for extension nonmutation, shared budgets, legal variations,
  invalid settings, and quiet positions.
- `cargo fmt --check`, Clippy with warnings denied, and release build passed.
- All 48 direct games and all four 88-case orientation evaluations completed.
- The previous Windows Application Control execution block did not recur on
  this build. No security controls were disabled or bypassed.
- A first summary regeneration exposed self-ingestion of `summary.json`; the
  summarizer now selects only evaluation reports and was rerun twice successfully.

## Next useful experiments

Prioritize a larger, expert-reviewed tactical corpus and better leaf/candidate
selection over more global weight tweaks. Narrow the extension trigger, avoid
full-board candidate work inside tactical continuations, and compare at both
fixed-node and fixed-time budgets. Then test against an established external
GTP engine and on independently selected openings/positions. The present
results do not establish a playing rank or general superiority of one search
method; they support retaining the current default while improving evaluation.
