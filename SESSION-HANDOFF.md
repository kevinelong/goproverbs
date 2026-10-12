# goproverbs: shared status and session handoff

Updated: 2026-09-23, small-search verification complete; development gate failed.
Project: `C:/Users/kevin/local-llm-lab/goproverbs`.

## Completed small-search verification: no active inference

User authorized timing profiles at4/8/16 visits, one fixed verification rule,
separate development/validation checks, and fresh paired games only if both
pass. This session owns new benchmarks/neural_verify.py,
neural_verify_experiment.py and their tests, new verification protocol/results,
and results/neural-led-20260923/verification-v1. Completed60 timing decisions,
selected16 visits, then40 development cases with160 child reference searches.
Timing fits: maximum106.36ms. Pooled reference gains passed, but combined-role
mean at512 visits was-0.037 percentage point, failing its fixed nonnegative gate.
Validation40 cases remain unqueried; no fresh games.98 Python tests passed;
artifact review reproduced gates, checked values/hashes and verified cleanup.
New reviewer: benchmarks/review_neural_verify.py. See
docs/NEURAL-VERIFY-RESULTS-2026-09-23.md. No model or GTP process/run lock remains.
Existing playing controller, frozen evidence, defaults and releases preserved.
One inference workload; no subagents requested for this continuation.

## Completed disagreement review: no active inference

User authorized saved disagreement analysis, deeper KataGo reference, one focused
candidate if supported, then conditional fresh screens. Root owns new diagnostic
script/tests/protocol and results/neural-led-20260923/disagreements-v1. No change
to the playing controller before diagnostic gates. Serial inference; preserve
all frozen runs. Open produced reports in their default Windows application.

disagreements-v1 complete79/79 cases at128/512 visits.39 confidence overrides,
40 specialist choices;370 model child analyses plus2 exact terminal values.
Fixed policy-protection candidate failed development and validation criteria;
no controller change or fresh matches.89 Python tests pass. Hashes and cleanup
verified. See docs/NEURAL-LED-DISAGREEMENT-RESULTS-2026-09-23.md. Next research
option is bounded deeper verification under a new protocol, not threshold tuning.

## Completed pass-agreement work: no active inference

User authorized pass handling, deterministic controls, saved failure replay,
endgame validation, then separately labeled fresh paired screens. Root owns
neural_led.py and tests, neural_led_screen.py and tests, new pass protocol and
new results. Preserve all prior frozen runs; one inference workload at a time.
No default promotion, commits or larger confirmation without its evidence gate.

Implemented and validated.85 Python tests and36 frozen controls passed;
45/45 live position checks and5/5 endgame replays passed. The original unfinished
game now ends at380 total moves (B+42.5). New pass-v1 completed80/80 fresh games:
neural-policy20/40, combined-neural21/40, both inconclusive.27,560 decisions,
zero deadline overruns/fallbacks,31 separately counted pass agreements. All
input hashes/freshness checked; no model, GTP process, resident Ollama model or
run lock remains. No promotion/confirmation/full-KataGo expansion triggered.
Read docs/NEURAL-LED-PASS-RESULTS-2026-09-23.md and the frozen pass-v1 artifacts.
The older pass-rule proposals and stopped-screen notes below are historical.

## Paired-screen outcome, September 23: no active inference

User authorized the next steps: live White validation, 20 fresh opening pairs
neural versus policy, then 20 separate pairs combined versus neural at 200 ms.
Root owns benchmarks/neural_led_screen.py, its tests, the screen protocol,
new results/neural-led-20260923/screen-v1 and this handoff. Serial inference;
do not launch CPU or other model jobs concurrently. No historical edits or
engine-default changes. Strength expansion beyond these screens is gated.

v1 stopped and cleaned up: White40/40 passed; neural-policy20pairs complete,
24/40 wins (12 wins per color), conservative interval0.296-0.904. Combined's
first game failed223.45ms hard timing gate; zero complete combined pairs.
Root diagnosed deepcopy of immutable history tuples; copy-diagnosis.json
preserves20 CPU samples (14.63ms old versus0.022ms container-copy child).
Agent changed only neural_led._child and tests, preserving full superko history.
screen-v2 failed before inference (relative config path); fixed absolute output
resolution. screen-v3 passed45/45 White controls and played2 complete pairs
(combined2/4) before the fifth game hit722-move cap. All2,326 match decisions
were timely and complete; the losing neural role declined180 policy passes
because exact terminal loss0 was below tiny positive continuation estimates.
Remaining35 games held. No default/confirmation promotion. Sources/results
frozen, no pooling. All80 Python tests and32 frozen controls passed. Verified
model/process/lock cleanup. Details and proposed pass-policy next gate:
docs/NEURAL-LED-SCREEN-RESULTS-2026-09-23.md. The pass rule is not implemented.

## Completed neural-led implementation, September 23

User explicitly requested a written plan and supervised coding agent.
Plan: docs/NEURAL-LED-PLAN-2026-09-23.md. Results:
docs/NEURAL-LED-RESULTS-2026-09-23.md. One Astra agent implemented only the new
benchmarks/neural_led.py and benchmarks/test_neural_led.py; root reviewed,
implemented neural_led_probe.py and its tests, and supervised live validation.
73 Python tests passed; frozen controller/probe copy passed all 25 controls.
results/neural-led-20260923/probe-v1 is complete: 80/80 legal timely decisions,
64/64 complete neural rounds, zero fallbacks/timeouts; unchanged input hashes
and verified cleanup. No model, GTP process or run lock remains. Historical
override counts saved alongside it. No Rust/default profile/release changes.
No strength expansion launched; next gate is fresh paired games, first neural
versus raw policy, then combined versus neural, with full protocol frozen first.
Do not confuse these reused development probes with strength evidence or reopen
the historical NN retention gate. CPU packing work remains memory-held.

## September 23 coordinating owner

Current outcome: completion experiment is finished and cleaned up. New prompt
6/6 correct and clean versus baseline 4/6 correct, 1/6 clean. Staged graph smoke
still timed out, so the 30-run batch stays held. All 9 Python deadline tests and
14 focused WSL Rust retention/transport tests passed. No Go source or release
changed; larger strength matches remain held by 78.4% retention at 200 ms.
CPU reruns are prepared but memory-held in ai_bench/cpu-headroom-20260923-v1;
last post-unload check was 7.16 GiB physical, 11.32 GiB commit headroom versus
required 14/10 GiB. User is freeing RAM. See parent FOLLOWUP-RESULTS-2026-09-23.md.
The launch description below is historical; no LLM queue is currently active.

The user authorized completion diagnosis/follow-up, gated staging, CPU reruns
with memory headroom, and maintaining the Go retention gate. One writer owns
parent benchmarks/completion_followup_20260923.py, its test/protocol, reporting,
and this handoff. Go scope initially read-only deadline/probe review and tests;
no strength matches or executable edits are claimed. Active LLM queue:
`C:/Users/kevin/ai_bench/completion-20260923-v1`; inspect status/lock first.
September 22 overnight v3 is complete (00:18 PDT), all owned models cleaned up.
The following overnight-owner and earlier status paragraphs are historical.

## New overnight owner, after the completed Go work

User authorized overnight follow-up. A serial LLM/CPU queue is now running from
`C:/Users/kevin/ai_bench/overnight-followup-20260922-v3` (worker PID 1630976 at
launch). Check its status.json and RUNNING.lock before using inference resources.
The v2 queue was stopped and preserved as a diagnostic after a scorer/lifecycle
bookkeeping bug; v3 passed validation with that fix before launch.
The v3 smoke completed: staged passed 55/55 and finished cleanly in 59.0 seconds;
one-shot passed 55/55 but the repeat guard terminated it after 28.7 seconds.
Both had complete token counts and verified process/model cleanup. The fixed
gate therefore holds the 30-run guarded staging batch. The 12-run guard versus
observation ablation is running next, followed by the separate CPU controls.
Its source is frozen; no Go builds, edits, or further strength matches are queued.
The current work is repeat-call intervention/ablation, conditional guarded
staging, and slower CPU packing controls. STOP in that directory cancels its
own work. Details: parent OVERNIGHT-PLAN-2026-09-22.md; live REPORT.md in the queue.
The completed-session observations below precede this new authorization.

## Latest continuation after user-authorized Comet closure

The user authorized closing Comet. Normal close requests completed; no Comet
process remained, and available RAM rose to 5.56 GiB. The earlier resource
question is resolved. No unrelated application was closed.

LLM smoke-v3 passed preflight but Ollama failed CUDA warmup; no scored agent
phase ran and the model unloaded. Unchanged smoke-v4 then loaded successfully.
Staged graph scored 53/55 and one-shot 55/55, but both reached the 180-second
wall limit. Staged repeated the same cycle check 60 times; its audit never ran.
One-shot's interrupted response left token accounting incomplete. These are
diagnostics, not main comparison results. The 30-run main-v1 remains held by
the clean-completion gate. Do not rerun unchanged trials to seek a passing draw.

The staged timeout also exposed sandbox denial of taskkill /T. The parent
exited and an elevated read verified no remaining direct children. The runner
now stops the batch when process-tree cleanup is denied or times out; all 12
runner tests pass. Historical smoke sources/results remain unchanged.

Bonsai GPU packing main-v2 completed all four cases and 12 fixed-prompt
repetitions, with required-tool and streaming controls passing, unchanged
input hashes, and identical observed generated text. Median generation rates:
PTQ1 54.30/49.70 tok/s at 8K/32K, PQ2 54.86/52.93. These are short-prompt
measurements with different context allocations, not long-context quality.
One GPU telemetry sample timed out; it remains missing in the memory summary.

Preserved main-v1 used an object-form tool_choice that the pinned runtime
silently downgraded to auto; its measurements are excluded from the corrected
table. The runner now uses required with one tool, checks tool-call completion
and integer arguments, and passes seven unit tests. Corrected CPU-only attempts
cpu-ptq1-v2 and cpu-pq2-v2 each timed out on the 120-second tool control before
measured repetitions. These are failed bounded controls, not throughput scores.

All inference has stopped. Final cleanup found no owned model processes, no
Ollama resident models or run locks, 10.64 GiB available RAM and 10,103 MiB free
VRAM. Cleanup record: `ai_bench/packing-20260922/final-cleanup-v2.json`.
See parent [staging diagnosis](../STAGING-RESULTS-2026-09-22.md) and
[packing results](../PACKING-RESULTS-2026-09-22.md). No further experiment is queued.
No Go source, frozen evidence or release ZIP changed during this continuation.
The prior memory-pending paragraphs below are historical observations.

## Ownership and immediate coordination

The user reports two sessions redundantly editing this project. This note is
the starting point for reconciling their work; it does not establish what the
other session is doing or notify that session automatically.

| Session/work | Status | Scope / next action |
|---|---|---|
| Session that executed the September 21 nine-part roadmap | Implementation stopped; handed off after writing this note | No further source edits or experiments claimed; this handoff adds only `AGENTS.md` and `SESSION-HANDOFF.md` |
| Coordinating owner, September 22 continuation | Finished; no active workload | Go work and bundle complete. LLM smoke failed the clean-completion gate; main staging held. Corrected Bonsai GPU comparison complete; CPU controls timed out. Reports and handoff updated; prior evidence preserved. |
| Parallel review agents for coordinating owner | Finished and stopped | Read-only screening and neural audits delivered. No source edits, builds, model runs, or publication. Findings recorded below. |

Active continuation: see `docs/CONTINUATION-2026-09-22.md`. Deadline regressions
and real-runtime recovery/ko checks passed; current validation is 65 Rust tests
in WSL and 48 Python tests, with Windows format/Clippy/release passing. The
direct runner was implemented by a bounded agent in two new files, then reviewed
and extended by the coordinating owner. All helper agents are finished/stopped.
The first smoke is stopped and preserved at `results/direct-20260922/smoke-v1`.
Its standalone-search matchup is invalid strength evidence: timeout fallback
distorted play. The corrected adapter uses timely intermediate search reports
and aborts if no timely answer exists. Fifteen real search probes passed in
`results/deadline-runtime-v4-20260922`, including cancellation recovery.
The replacement six-game smoke completed at `results/direct-20260922/smoke-v2`:
all legal/referee-checked, hashes unchanged, no broker errors or standalone
fallbacks. NH scored 0/2 against each opponent. NN complete-round retention was
279/356 = 78.4%, below the 80% gate; NN expansion is held by the protocol.

Queue record: `C:/Users/kevin/ai_bench/continuation-20260922/status.json`.
Its 40 policy/search games on openings023..032 completed: NH 3/20 versus policy,
0/20 versus search; hashes unchanged, no broker errors or standalone fallbacks.
CPU-small NH/HH smoke finished 3/4 wins for NH. Budget probes completed at
50/100/200/400 ms: NN retained complete rounds on 3/8, 6/8, 7/8 and 8/8 fixed
development positions. These are throughput diagnostics, not strength claims.
The queue then stopped at LLM smoke-v1 preflight: sandbox WMI access denied.
Root replaced WMI with supported Get-Process listing. Smoke-v2 passed all 11
runner tests and all task/scorer controls but stopped before inference because
available physical RAM was below 4 GiB. An independent reading found 3.51 GiB
physical and 3.61 GiB commit headroom. WSL uses about 700 MiB; no resident model.
The user has been asked which unused apps may be closed or to free RAM directly.
No model is running now. Do not kill unrelated apps or WSL services (Postgres
and Tailscale are active). Retry with a new smoke-v3 label after resources allow;
main-v1 is still unused and must follow a passing smoke. Preserve failed labels.
Queue code: parent `benchmarks/continue_research_20260922.py`. Child PIDs,
logs and output paths are recorded in queue status. A queue STOP is checked
between jobs; the active experiment's STOP stops within a job. Do not launch
competing inference or modify frozen files. Preserve incomplete results.

All bounded agents have finished and were stopped. Native SGF is integrated
through GTP loadsgf with protocol tests. Parent-lab staging task/scorer and
runner files are implemented; all 11 runner tests and task controls/mutants
pass, including timeout accounting and normal dataclass imports. Actual Pi relay
integration still needs its own gate before the 30-run experiment.
The runner executes its protocol tests before inference.
Ordinary timed-out candidates fail their trial;
unknown usage without expected cancellation still aborts the experiment.
Prepared 30-workspace protocol: `ai_bench/staging-20260922/prepared-v1`, no model
calls. Smoke-v1/v2 stopped before inference; smoke-v3 and main-v1 remain unused.
All agents are stopped. No inference job is queued or running.

Parent Bonsai packing runner/test files are also prepared and root-reviewed:
`benchmarks/compare_bonsai_packing_20260922.py` and its test file. Six tests pass;
inference awaits memory headroom. The runner pins the
old Prism release and model revision; new PTQ1 download is about 5.95 GB, with
the exact expected hash recorded in `PACKING-PROTOCOL-2026-09-22.md`.
New benchmark sources, API controls, flags and failed-run handling were reviewed
and strengthened. Keep packing and staged LLM inference serial.

PTQ1 download-v2 completed and verified: 5,946,648,928 bytes, SHA256
`53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3`.
Download-v1 records the sandbox network denial. No packing inference ran.
Final resource check: 3.73 GiB available RAM, 8,560 MiB free VRAM, Ollama empty.
The resource question remains pending; do not start inference below the RAM gate.

Local release `dist/goproverbs-research-20260922-v2.zip` corrects the CPU smoke
prose to 3/4 wins. The original ZIP is preserved; its 4/4 prose is incorrect,
while its included raw game records and generated table correctly show 3/4.
No source/executable behavior changed for this documentation correction.

Before taking over, read the current files and update this table with a bounded
task and file scope. Prefer one writer in this checkout. These entries are
advisory, not atomic locks. Do not assume this note means the other session has
stopped. Refresh it when finishing or changing scope.

At the original September 21 handoff, SHA256 comparison found **zero differences across all
78 files** recorded in `results/roadmap-20260921/source-final/manifest.json`.
That covers the tested source/docs/scripts/profiles and release executable.
It does not inventory new files outside the manifest or detect future edits.
The two handoff files were added afterward and are outside the frozen bundle.

`git status --short` currently lists the project files/directories as untracked.
This session made no commit or GitHub publication. Do not treat untracked files
as disposable or assume Git can restore this implementation; use the snapshots.

## Authoritative documents and frozen artifacts

- [Nine-part plan and progress](docs/ROADMAP-2026-09-21.md).
- [Executed results, limitations and next gates](docs/ROADMAP-RESULTS-2026-09-21.md).
- [Terminal, SGF, neural and clock workflow](docs/RESEARCH-WORKFLOW.md).
- [Structured proverb catalog](docs/PROVERB-CATALOG.json).
- `results/reference-20260921`: original source/executable; 34 manifest files
  verified. Preserve this pre-roadmap baseline.
- `results/roadmap-20260921/source-arena-v2` and
  `goproverbs-arena-v2.exe`: frozen revision used for the 12 new games.
- `results/roadmap-20260921/source-final`: final source/executable; 78 files
  verified. Adds controller clocks beyond the arena revision.
- `results/roadmap-20260921/summary.json` and `validation.json`: compact evidence.
- `dist/goproverbs-research-20260921.zip`: verified local bundle, 145 files.
  SHA256: `a52dc4379a4a359dff8ee2677d664bb1d47f8076983b6aea0ac7434721a988cb`.
  Extracted terminal play/rank/explain smoke test passed; record in
  `results/package-smoke-20260921.json`. No neural model is needed for that UI.

Do not regenerate or overwrite these artifacts to incorporate later changes.
Use a new run/release name and record its own source/executable identity.

## Already implemented: avoid doing this twice

| Area | Main live files | Completed work |
|---|---|---|
| SGF and benchmark corpus | `benchmarks/sgf_io.py`, `corpus.py`, `paired_summary.py` | Validated main-line replay; explicit unsupported setup/handicap errors; 40 development positions from 10 games; 50 seeded openings |
| Neural nomination/evaluation | `src/search.rs`, `external.rs`, `gtp.rs`; `benchmarks/guidance.py`, `roadmap.py` | Optional legal root nominees, localhost evaluator, perspective conversion, complete-round fallback, four-way ablation |
| Search optimization | `src/engine.rs`, `search.rs`; `benchmarks/check_optimization.py` | Relevant-group filtering and telemetry; measured equivalence checks |
| Proverbs | `docs/PROVERB-CATALOG.json`, `benchmarks/ablate.py` | 16 catalog entries; 13 profiles evaluated on 10 development fixtures |
| Safety diagnostics | `benchmarks/safety.py` | Eye candidates, liberties and bounded capture proof; unknown remains unknown |
| CPU/neural backends | `benchmarks/neural.py`, `roadmap.py` | Eigen CPU and OpenCL timing with old b10 and newer small b6 weights |
| Human/controller interface | `benchmarks/play.py`, `src/clock.rs`, `gtp.rs` | Terminal play/rank/explain/undo/save/load/groups/capture; absolute/Canadian GTP clocks |
| Packaging/reporting | `scripts/freeze_research.py`, `package_release.py`, `benchmarks/summarize_roadmap.py` | Frozen source, verified bundle and summaries from saved evidence |

Native Rust `loadsgf` now imports explicit TT move-only records. Safety diagnostics
do not adjudicate life/death or alter scoring. Standalone defaults and weights
were not promoted or changed on the basis of pilot win rates.

## Results and known traps

- New arena: 12 finished 19x19 TT games at komi 7.5 and 200 ms, two opening
  pairs per variant against HH. NH (neural nominees only) won 4/4; HN (neural
  evaluation only) 2/4; NN (both) 4/4. All boards and final scores independently
  checked. Two pairs are insufficient for strength/rating claims.
- NN retained a complete neural round on 537/803 moves; the rest fell back to
  the heuristic scout. HN retained it on 724/724. Both searched only one ply
  in these games. Do not call every NN move a neural decision.
- Initial evaluator attempts completed zero depth-two neural rounds at 200 ms.
  Those probes are preserved. The revision retains a complete neural one-ply
  round before attempting deeper work. Do not reintroduce partial-score mixing.
- Ranking outputs matched on 94 positions, with four fixed-depth answers/node
  counts matching. Sample aggregate ranking time improved 41.4%; this is not
  a whole-engine speedup claim. Final clock-enabled build also matched the
  frozen arena build on the same semantic checks.
- Small b6 model: median ~8.98 ms CPU / ~3.08 ms GPU per position; old b10:
  ~25.07 / ~3.42 ms. CPU logs confirm Eigen. These are timing comparisons,
  not demonstrated network-strength comparisons.
- Development labels are not best-move proofs. Removing influence changed
  hybrid fixture agreement from 7/10 to 8/10; no weights were promoted.
- Earlier 76 games plus these 12 = 88 documented games across different
  experiments. Do not pool them into a single strength statistic.

## Validation: what passed and what did not run

September 22 reconciliation: all 21 live Rust source/test/Cargo files match
`source-final/manifest.json`. The coordinating session's WSL build and all
47 Rust tests passed on this revision (CLI 1, clocks 2, core 18, neural hooks 5,
protocol 4, search/scoring 12, search modes 5). This closes the Linux source
validation gap; it does not claim native Windows test binaries ran. The
performance experiment used an earlier, separate 44-test frozen snapshot.
See `docs/WSL-PERFORMANCE-2026-09-21.md` and the new screening `plan.json`
for source reconciliation hashes. The entries below preserve the prior
session's Windows observations.

- Formatting, Clippy with warnings denied, and offline release build pass.
- 16 targeted Rust tests pass: clocks 2, neural hooks 5, protocol 4, search
  modes 5. All 32 Python tests pass.
- Full Rust suite is incomplete: Windows Application Control blocked `core`
  and `search_and_scoring` test binaries with OS error 4551. Earlier default
  build-directory attempts also hit LNK1104. Policy was not bypassed. Do not
  rebuild/rename blocked binaries merely to evade that control or report the
  historical full-suite result as current validation.
- The final Python log contains a PowerShell `NativeCommandError` wrapper for
  unittest's stderr stream; actual exit code is zero and summary is OK.

For a substantive new change, these are the previously passing checks:

```powershell
cargo clippy --offline --all-targets -- -D warnings
cargo build --offline --release
cargo test --offline --target-dir target/roadmap-20260921 --test clocks --test neural_hooks --test search_modes --test protocol
python -m unittest discover -s benchmarks -p 'test_*.py' -v
```

Do not rerun expensive comparisons just to reconstruct this session's history.
Read their saved records first. Do not rebuild a binary another session is
currently using for timed matches.

## Runtime/resource state

At the end of this session's research, all its test/model processes had exited;
the final check found zero `katago`/`goproverbs` processes and GPU memory at
2,157 MiB used / 9,787 MiB free. This is a historical observation, not a claim
about workloads the other session may start. No processes were launched for
this documentation handoff.

Installed runtimes/weights are under `C:/Users/kevin/ai_bench/katago`:

- `opencl-1.18.1/katago.exe`, `eigenavx2-1.18.1/katago.exe`.
- `kata1-b10c128-s919229184-d169515535.txt.gz`.
- `lionffen_b6c64_3x3_v10.txt.gz` (19x19 small extra network).

Before new inference, inspect current processes/VRAM/Ollama and both lab runner
locks. Preserve the user's rule: release identified idle model workloads,
run one inference workload at a time, and leave unrelated applications alone.
There is no global mutex implemented by the roadmap harness.

## Original September 21 backlog (historical)

1. DONE: reconciled scope and final source identity; all 47 Rust tests passed in WSL. Native Windows full-suite block remains.
2. DONE: NH won 36/40 across 20 unused color-swapped pairs at 200 ms; pilot kept separate. See September 22 report.
3. Compare NH directly with NN and the pretrained standalone reference.
4. Improve neural batching/transport and complete-round retention before more
   NN volume; preserve timeout and superko semantics.
5. Run CPU-small strength matches and controlled budget curves.
6. Add reviewed positions, fresh holdout data, shape exceptions, ladders, seki
   and endgame coverage. General life/death remains unfinished.
7. Confirm any finalist/weight change on fresh paired games before promotion.
8. Finish native SGF/GUI interoperability and separately prepare publication.

Current disposition: 1-3 and 5 are complete; 4 has deadline/cancellation fixes
but batching and NN retention improvements remain. Native SGF in 8 is complete;
external GUI verification and publication remain. Expert-reviewed fixtures,
fresh holdouts, general life/death and finalist confirmation remain research
gates. No finalist was promoted. Read the current status above before acting
on this historical list.

## September 22 screening and audit addendum

The user selected gate 2, now completed. Preparation froze harness/source/profile/executable
under `results/nh-screen-20260922/snapshot`; the derived opening manifest selects
exactly original indices [2:22], excludes pilot IDs and sequences, and verifies
20 unique legal even-length histories. `plan.json` pins input hashes before
outcomes. No tuning or default promotion is part of this run. These are unused
development openings, not a pristine reviewed holdout. Expected 40 games at
200 ms, with independent referee board and final-score checks on every game.
The run took 61.04 minutes and exited 0. All 40 games finished; NH won 36,
including 18/20 as each color. Pair outcomes: 16 sweeps and 4 splits. The
conservative paired interval is 59.6%-100%. No decision exceeded 201.044 ms;
zero broker errors. All pinned hashes still matched after the run. Models and
engine processes exited; final check found GPU memory at 2,748 MiB used and
no loaded Ollama model. No further workload is queued.

Report: [NH screening](docs/NH-SCREENING-2026-09-22.md). Evidence and frozen inputs
are under `results/nh-screen-20260922`. Preparation and validation scripts are
`scripts/prepare_nh_screening.py` and `scripts/summarize_nh_screening.py`.
The separately archived `executable-source/src` is the pilot arena source;
`snapshot/src` and `snapshot/tests` are the final WSL validation revision. This distinction
is recorded in `executable-source-provenance.json`. The original arena source
directory had no contemporaneous source manifest; executable identity is
independently pinned to the pilot hash. No historical artifact was overwritten.

Read-only neural audit: perspective conversion and complete-round retention
look correct. Before more NN screening or transport changes, address the
cooperative end-to-end timeout: Rust connect/write/read can each consume the
remaining duration, while a stale broker inference may block later requests.
Add wall/queue/stale-request telemetry and a real ko/superko history-equivalence
fixture before replacing full SGF histories or changing cache keys. Preserve
BLACK-reported raw lead and side-to-move conversion. NH screening has no neural
leaf calls; it retains full-history serial root nomination and records total
decision wall time. Future batching work remains unimplemented.
