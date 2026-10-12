# Small-search verification fits the budget; candidate not promoted

Completed the authorized timing profile and development screen. All three
small-search budgets fit; the fixed rule selected16 visits per compared child.
The quality gate failed because the combined role had a slightly negative
mean reference-estimated change at512 visits. The40 validation cases remain
unqueried and no fresh games were launched. The existing playing controller
and engine defaults are unchanged. All inference is stopped and cleaned up.

## What was tested

The experimental wrapper first runs the current neural/combined chooser. When
it proposes an override, it searches the policy and alternative children and
keeps the alternative only with an estimated win-probability gain>=0.005.
Otherwise it returns policy. Existing pass agreement remains intact. A single
200ms deadline covers baseline generation, specialist work, replay, legality,
both verification searches and selection. Incomplete verification returns policy
with explicit fallback telemetry; invalid results fail rather than hiding errors.

Pinned KataGo1.18.1 OpenCL and b10 model, TT19, komi7.5, full history, Black-reported
values normalized to the mover. Protocol and sources were frozen before inference.
Depth selection used timing only. No thresholds were changed after seeing results.

## Timing profile

Each depth ran the actual chooser on20 old diagnostic positions,10 per role,
with cache clearing before each complete decision. All60 decisions verified an
override and were legal, timely and complete, with zero fallbacks.

| Visits per child | Median full decision | 95th percentile | Maximum |
|---|---:|---:|---:|
| 4 | 49.15ms | 69.99ms | 75.75ms |
| 8 | 56.54ms | 80.78ms | 83.29ms |
| 16 | 74.83ms | 100.80ms | 102.07ms |

All passed the fixed p95<=150ms and maximum<=180ms profile gates.16 visits was
the largest allowed depth, so it was selected and recorded before new reference
labels. These are sampled warmed-runtime timings, not a worst-case guarantee.
External Rust board synchronization, cache clearing and logs are outside the
decision timer, matching prior experiments; specialist nomination is inside it.

## Development quality gate

Selected80 previously unqueried override positions, one per old pass-v1 game.
No full-history overlap with the earlier79-case diagnostic; no missing games.
Both colors of each opening stay together. Development and validation each have
40 cases from20 openings,20 cases per role. These are fresh positions within
previously inspected games, not pristine external validation.

Development ran40 live decisions, then160 completed child reference searches at
128/512 visits. Comparisons use the live baseline choice from this run. Means
below average within opening pairs first. Units are percentage points of
estimated winning probability; deeper same-model estimates are not ground truth.

| Comparison | 128 visits | 512 visits |
|---|---:|---:|
| Verified candidate minus current chooser, pooled | +0.585 | +0.701 |
| Verified candidate minus raw policy, pooled | +0.685 | +0.677 |
| Verified candidate minus current neural-only chooser | +1.144 | +1.439 |
| Verified candidate minus current combined chooser | +0.025 | -0.037 |

The pooled means cleared their thresholds. At512 visits,6 decisions improved
by at least0.1 percentage point,2 worsened by at least that amount, and32 were
near ties. No decision exceeded the severe-harm threshold at both depths.
However, the protocol also required nonnegative improvement in EACH role at
BOTH depths. The combined role's-0.037-point result failed that condition.
This is a small negative estimate, not evidence of a large strength regression.

Neural-only retained4/20 proposed overrides and returned to policy16 times;
it had6 beneficial,1 harmful and13 near-tied changes at512 visits. Combined
retained2/20 overrides and returned to policy18 times; it had0 beneficial,
1 harmful and19 near-tied changes. These are selected-position diagnostics,
not game win rates or representative frequencies across all decisions.

All40 development decisions were legal and complete. Neural-only median51.98ms,
maximum66.43ms; combined median93.79ms, maximum106.36ms. Overall p95 was102.14ms.
No deadline overruns, fallback, cancellation, late reply or transport lock timeout.

## Result and next decision

Keep the experimental implementation and evidence, but do not integrate it into
the normal playing controller. Validation and fresh strength games were correctly
held by the failed development gate. No model or threshold sweep followed.

The neural-only result is encouraging development evidence. A future experiment
could test a separately specified neural-only treatment on new opening groups.
It would be a new hypothesis prompted by these results, not a passing subgroup
of this experiment or authorization to reuse this development evidence as
confirmation. The combined treatment has not earned more strength-testing cost.

## Verification and artifacts

- 98 Python tests passed, including9 new verification/gating controls. The frozen
  copy separately passed the9 new controls before inference.
- Independent artifact review reproduced the gates, checked every reference
  value/perspective and selected move, legality, split isolation and source hashes.
- 1,146 transport requests including warmup/cache/version calls; zero cancellations,
  late replies or lock timeouts. No validation requests in the wire log.
- Preflight8.20GiB available RAM; postflight8.16GiB and10,042MiB free VRAM. Ollama
  empty; no KataGo, GTP engine, llama server or run lock remained.
- Protocol: docs/NEURAL-VERIFY-PLAN-2026-09-23.md.
- New code: benchmarks/neural_verify.py, neural_verify_experiment.py,
  test_neural_verify.py and review_neural_verify.py.
- Frozen run: results/neural-led-20260923/verification-v1/, including PROTOCOL.md,
  source/, identity.json, profile-cases.json, cases.json, depth.json, profiles.json,
  per-case decisions, results.json, wire.jsonl, status.json, REPORT.md and REVIEW.json.

Do not resume or overwrite this completed label. Old results, Rust binaries,
default profiles and release bundles were preserved. No commit or publication.
