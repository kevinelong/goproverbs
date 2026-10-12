# Disagreement review: candidate rejected, engine unchanged

Completed the authorized saved-position review and tested one fixed conservative
override rule offline. The candidate failed its predefined development and
validation criteria. It was not added to the playing controller and no fresh
matches were launched for it. All inference is stopped and cleaned up.

## What was reviewed

79 saved positions from the completed pass-v1 screen:39 high-policy-probability,
small-gain neural overrides and40 specialist-only choices. One qualifying position
per game, hash-selected without reference labels or game outcomes. One game had
no eligible confidence case and was recorded missing, not replaced. Both colors
of an opening stayed in the same development/validation group, fixed in advance.

Every compared child was checked at128 and512 visits with the same pinned b10
model and KataGo1.18.1, full history and Black-reported values normalized to the
original mover.370 child searches completed their required visits;2 exact
two-pass terminal evaluations brought the total to372 compared child/budget
values. These are correlated same-model reference estimates, not ground truth.
The enriched sample does not represent every move or a new strength test.

89 Python tests passed, including4 new diagnostic controls. Frozen source,
source traces, sampling choices, assets and protocol hashes verified unchanged.
742 transport requests including cache clearing, version and warmup:zero
cancellations, late replies or lock timeouts. No model process or run lock remains.

## Findings at512 visits

Better/worse means at least0.1 percentage point difference in estimated winning
probability. Near ties fall within that threshold. Means are descriptive case
averages; the candidate gate averages within opening pairs first.

| Selected move compared with | Cases | Better | Worse | Near tie | Mean win estimate difference | Mean score difference |
|---|---:|---:|---:|---:|---:|---:|
| Root policy in small-gain overrides | 39 | 10 | 15 | 14 | -0.76 percentage points | -3.34 points |
| Best saved neural candidate for specialist choices | 40 | 5 | 4 | 31 | +0.24 percentage points | -3.88 points |

27/40 specialist comparisons had both win estimates below0.001 or above0.999.
This saturation makes small winrate differences hard to interpret even when
score estimates differ materially. A lower score is not automatically a worse
move under a win-probability objective. Three confidence cases reversed the
direction of their reference preference between128 and512 visits; no specialist
case reversed beyond the same threshold. The reference itself is not infallible.

## Why the proposed rule did not pass

The one fixed candidate retained root policy when its probability was>=0.50
and the original one-visit win estimate improvement was<0.02. No parameter sweep
or adjustment was performed after viewing reference results.

- Development:19 cases from10 openings. Estimated gain from retaining policy,
  averaged by opening, was+0.19 percentage points at128 visits and-0.23 at512.
  Neither met the required+0.50-point minimum at both depths.8 beneficial and4
  harmful cases at512 visits did not rescue the failed mean criterion.
- Validation:20 cases from10 openings. Mean gains were+1.57 and+1.71 percentage
  points, but7 beneficial versus6 harmful cases failed the required2:1 ratio.
  Validation is not treated as support when development failed.
- No case exceeded the severe-harm threshold at both depths. That alone is not
  enough to justify implementing a rule with inconsistent benefits.

The pooled average favoring policy cannot override these predeclared checks.
Higher policy probability plus a small one-visit gain does not reliably separate
useful overrides from harmful ones in this sample.

## Concrete examples

Each ID below is a saved decision; win differences are from the original mover's
perspective at512 visits. The same preference direction held at128 visits for
these examples. They illustrate reference judgments, not proven tactical truth.

| Saved decision | Choice | Reference comparison |
|---|---|---|
| led-fresh-017-neural-vs-policy-B-56 | E14 over policy E12 | E14 lower by22.30 percentage points and5.62 score points |
| led-fresh-009-neural-vs-policy-B-114 | O6 over policy R5 | O6 higher by5.55 percentage points and1.57 score points |
| led-fresh-022-combined-vs-neural-B-28 | Specialist P14 over neural O10 | P14 higher by13.70 percentage points and3.79 score points |
| led-fresh-034-combined-vs-neural-B-148 | Specialist J7 over neural K6 | J7 lower by4.97 percentage points and1.15 score points |

The rejected rule would prevent the first override but also reject the second.
Specialist proposals can supply useful exceptions, but their current selection
rule also accepts poorer alternatives. Neither a blanket override ban nor more
specialist nominations is justified by these examples.

## Next research direction

Keep the current pass agreement, full-history clone optimization and raw-policy
baseline. No default promotion, new threshold or fresh strength batch follows
this failed candidate gate.

A separately specified next experiment could spend part of the unused decision
budget on verifying alternatives before an override. First profile much smaller
visit budgets:the128-visit child reference already took138.79ms median and512
took517.58ms, so applying these depths to every shortlisted move does not fit
the200ms total allowance. Do not simply transplant this diagnostic's reference
settings into the playing engine. Any new treatment needs fixed thresholds,
separate validation and the same completion/deadline gates.

## Artifacts

- Protocol:docs/NEURAL-LED-DISAGREEMENT-PLAN-2026-09-23.md.
- Script/tests:benchmarks/neural_disagreement.py and test_neural_disagreement.py.
- results/neural-led-20260923/disagreements-v1/:frozen source, sampled cases and
  full histories, missing-case record, hashes, raw wire traffic, all reference
  values, summary.json, REPORT.md and final cleanup status.
- Playing controller remains identical to the completed pass-v1 controller.
  Historical matches are preserved and were not reclassified or rerun.
