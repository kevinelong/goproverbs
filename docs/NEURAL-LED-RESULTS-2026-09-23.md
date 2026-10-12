# Neural-led prototype: reviewed and measured

The first deliverable in NEURAL-LED-PLAN-2026-09-23.md is complete. One
gpt-6-astra coding agent implemented the controller and 22 deterministic tests.
The coordinating root reviewed the code, implemented the bounded Rust proposer
and frozen probe driver, ran regression tests and live inference, and reviewed
the evidence. This is an experimental Python controller over existing pinned
KataGo and Rust executables, not a new default Rust engine or release.

## What changed

benchmarks/neural_led.py provides choose(kata, moves, color, size, komi, time_ms,
variant='neural', proposer=None, identifier='neural-led', clock=..., cancelled=None).
It returns (move, trace) without changing the root game. A terminal root returns
None and exact TT scoring. Failed root availability or malformed output raises
DecisionError carrying its trace. Callers must configure Black-reported values.

All variants retain a timely raw-policy recommendation. Neural evaluation
compares the top three legal policy moves. The heuristic, tactical and combined
variants add bounded proposals from existing Rust interfaces; their scores
never enter the neural objective. Only a completed comparison may override
the retained move. Full history, including positional-superko state, is retained.
Timeouts, partial values and nominee provenance are recorded explicitly.

The driver is benchmarks/neural_led_probe.py; its Proposer adapter assumes an
existing GTP process loaded with the supplied root history. It enforces the
specialist sub-budget and kills only its owned GTP process on a stuck command.
No caching, batching, training, Rust behavior change or release replacement.

## Validation and live results

- All 73 Python tests passed, including 22 controller and 3 probe controls.
- The frozen source copy passed its 25 controller/probe tests before inference.
- Fixed randomized schedule: 8 reused development positions, 5 variants,
  200/400 ms budgets, exactly 80 decisions. No selected reruns.
- Those positions represent seven source games and are all Black-to-move.
  White normalization, deadlines and cancellation passed deterministic controls
  but were not exercised by the live probes. Add live White coverage before
  treating this as validation for paired-color matches.
- 80/80 chosen moves legal under the independent full-history referee; live
  Rust boards also agreed. Nomination left every root SGF unchanged.
- 64/64 evaluated variants completed their whole candidate round. The other
  16 were raw-policy controls. No fallbacks, deadline overshoots or poisoned GTP
  processes. Maximum observed decision time across all variants was 144.00 ms.
- 440 transport requests including administrative actions, zero cancellations,
  late replies or lock timeouts. Frozen inputs were unchanged. No model or
  goproverbs process, resident Ollama model or run lock remained afterward.

| Variant | Median at 200 ms | Median at 400 ms |
|---|---:|---:|
| Raw policy | 8.24 ms | 8.25 ms |
| Neural top-three evaluation | 30.59 ms | 30.21 ms |
| Plus heuristic proposals | 45.11 ms | 46.73 ms |
| Plus tactical proposals | 66.70 ms | 66.13 ms |
| Plus both | 84.25 ms | 80.97 ms |

Same model/runtime: KataGo 1.18.1 OpenCL, b10c128 s919229184 network, RTX 5070.
Preflight had 7.17 GiB available system RAM and 10077 MiB free GPU memory.
Each child used one visit; process setup, warmup, cache clearing and input hash
verification were outside the per-decision clock. History reconstruction,
legality, nomination and neural comparison were inside it. This is not a
throughput benchmark or a comparison to the old NN search treatment.

## What the probes teach us

Each evaluated variant overrode raw policy on five of eight positions, with
identical moves at both budgets. Specialists changed the neural-only choice
on just one position: da01e9e87f58-80. Neural-only selected R14, heuristic and
combined selected B16, and tactical selected R13. All other specialist choices
matched neural-only. The added cost is established here; the added strength is
not. No move-quality ground truth or match outcomes were collected.
The distinguishing position recorded zero tactical nodes; R13 is a bounded
search nominee, not evidence that tactical reading improved the decision.

Six of eight neural-only positions had all candidate win estimates below 0.001
or above 0.999. These lopsided positions make small estimated winrate differences
weak evidence for useful overrides. For example, B16's estimated winrate was
0.999993193 with score lead 154.85; R13's was 0.999990759 with score lead 170.64.
Selecting B16 follows the declared winrate-first objective. It does not establish
that B16 is stronger, and the experiment does not establish value calibration.
Do not tune a new score blend on these eight positions and call it confirmation.
Trace field score_tiebreak_used means scores were available for tie-breaking;
it does not prove an exact winrate tie occurred. This telemetry naming caveat
is preserved here without altering frozen source or results.

Historical replay diagnosis found NH selected outside its neural top three on
4000/4872 decisions (82.1%) against raw policy and 4003/5278 (75.8%) against
search. This identifies override frequency, not which individual overrides
caused losses. Reproduction script: benchmarks/diagnose_nh_overrides.py.
Input hashes and counts: results/neural-led-20260923/historical-overrides.json.

## Evidence and next gate

Frozen source, config, plan, schedule, positions, asset hashes, raw wire traffic,
decision traces, report and cleanup status are all under
results/neural-led-20260923/probe-v1/. The experiment is complete and must not be
reused for reruns. Preparing another labeled experiment requires a new directory.

Operational feasibility passed on this small development set. Playing-strength
superiority remains untested. Next, predeclare fresh, more balanced openings and
paired-color games at the same total 200 ms allowance: neural-only versus raw
policy first, then combined versus neural-only to isolate specialist value.
A 20-pair screen is a screening result, not sufficient by itself for default
promotion. Preserve game-level uncertainty, deadline/cleanup gates and all
failed runs. Full KataGo search remains the subsequent baseline.

No automatic strength expansion was launched. The old NN 200 ms gate stays
closed; this separate prototype does not reopen historical results. CPU packing
work remains held for its own 14 GiB physical / 10 GiB commit requirement.
