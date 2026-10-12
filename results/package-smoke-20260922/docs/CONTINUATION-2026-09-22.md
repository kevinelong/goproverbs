# Deferred-work continuation, September 22

The user authorized proceeding with the deferred plans. The coordinating
session owns implementation; bounded agents review or edit explicitly disjoint
files. Inference remains serial. Completed snapshots/results are never replaced.

## Execution gates selected before new match outcomes

1. Fix neural deadlines and stale-request handling; preserve full histories and
   complete search rounds. Run fault regressions, full Rust/Python suites and a
   real KataGo cancellation/ko legality check. Do not optimize representation or
   introduce a board-only cache.
2. Freeze the revised executable, harness, profile and b10/OpenCL identity.
   Use opening-022 for a six-game smoke: NH vs NN, NH vs raw policy, NH vs
   KataGo search, with both colors. Same 19x19 TT, komi 7.5, 200 ms allowance.
   The policy reference intentionally uses one visit; it is not equal compute.
   Search reserves 10 ms for host overhead (190 ms engine setting at 200 ms).
3. Smoke acceptance: all six finish, all referee checks pass, pinned hashes
   unchanged, zero broker/protocol errors and no standalone timeout fallbacks.
   Record total wall/overshoot, root timeouts, NN complete-round retention and
   cleanup. Unexpected fallback/unfinished games trigger diagnosis before volume.
   If NN retains neural evaluation on fewer than 80% of its moves, keep it a
   diagnostic result and address throughput before expanding that matchup.
4. Eligible matchups expand to 10 pairs each on opening-023 through opening-032.
   Keep smoke, previous pilot, previous screening and expansion separate.
   Report paired intervals and color effects; no Elo or default promotion.
5. Run CPU-small NH vs HH on two fresh smoke pairs, and fixed-model budget
   probes, before choosing any larger CPU strength experiment. Model and backend
   changes are separate from the algorithm comparisons above.
6. Use the evidence to select a finalist, if any. Only then prepare at least
   50 additional fresh pairs and a calibrated opponent pool. Existing 50-opening
   corpus is insufficient for that holdout after the preceding allocations.

Native SGF/controller integration, stronger tactical/shape fixtures and release
preparation remain subsequent implementation tracks. Genuine expert-reviewed
labels need an identified expert/source; machine-generated cases will be marked
as such. Windows signing remains contingent on a certificate/service, with WSL
available for local builds. No certificate purchase is part of this execution.

The separate LLM-harness continuation is staged-vs-one-shot prompting across
at least five tasks and three workspaces each, Bonsai packing/runtime controls,
and specialized CPU evaluation. It follows the serial Go inference queue and
requires its own frozen task set and protocol; current results must not be
pooled across model/runtime/workspace treatments.

## Deadline implementation and initial validation

- Rust recomputes its monotonic budget for each socket read/write and rejects
  late/nonfinite responses. EVAL2 carries a host absolute expiry so the broker
  can discard expired requests in its queue. Wall-time mapping is local-host
  only; Rust's monotonic deadline remains authoritative.
- Broker admission, lock waiting and KataGo requests have bounded deadlines.
  Expired queries are cancelled. Both cancellation acknowledgement and the
  original terminal response must drain before new inference is submitted.
- A dedicated writer prevents a stalled OS pipe from blocking the caller.
  Unexpected responses poison the transport until restart. Broken-pipe cleanup
  still reaps the owned process and closes logs.
- On this Python 3.11 Windows host, monotonic() uses GetTickCount64 with 15.625 ms
  resolution. The new deadline API uses the monotonic high-resolution
  perf_counter (QueryPerformanceCounter). Scheduling can still overshoot;
  deadlines are cooperative, not a real-time guarantee.
- WSL full Rust suite: 51 tests pass, including four new transport regressions.
  Windows formatting, Clippy with warnings denied and release build pass.
  Python suite: 47 tests pass, including eight cancellation/cleanup regressions.
- Real-runtime gate v3 passed: deliberately expired 2 ms request returned after
  9.821 ms, cancellation/late-response recovery succeeded, Rust and KataGo both
  forbade the full-history ko recapture, and NN bridge play stayed referee-legal.
  This does not prove all superko cycles; capture/pass history retention has
  separate Rust and Python regression coverage.
- Initial gate failure was an overly specific diagnostic-text assertion;
  Rust correctly rejected the move. Its evidence remains preserved. v2 used
  the coarser Python clock; v3 is the high-resolution-clock result.

Evidence: `results/deadline-runtime-20260922`, `deadline-runtime-v2-20260922`,
and `deadline-runtime-v3-20260922`. Runtime cancellation follows the upstream
[KataGo analysis protocol](https://github.com/lightvector/KataGo/blob/master/docs/Analysis_Engine.md#terminate).

## Integration and replacement smoke

Native Rust SGF import and GTP loadsgf are integrated. Full WSL suite: 62 tests;
Windows format/Clippy/release pass; Python Go suite: 48 tests. Explicit TT rules,
first variation, complete history, move-number limits, undo and atomic failure
are supported. Unsupported setup/handicap and national rules are rejected.

The first smoke is preserved as stopped. NH lost both games against NN and both
against raw policy. The standalone search matchup is invalid: 100/178 search
decisions in its first game timed out and used a weak, slow fallback. Do not
pool it into strength summaries. A second game was deliberately stopped.

The replacement search adapter requests intermediate reports every 20 ms,
reserves 5 ms of its host budget, and accepts only a report consumed before
that deadline. The engine maxTime remains 190 ms at a 200 ms allowance. If no
timely report exists, the experiment aborts instead of substituting a move.
Cancellation and terminal replies still drain before subsequent inference.
Fifteen real-runtime probes on five saved development histories passed in v4;
each chosen move was referee-legal, with no fallback. This changes the search
adapter treatment and requires a separate snapshot/result. Opening-022 remains
a debugging smoke only; expansion-023..032 is unchanged and unobserved.

The parent LLM task controls and seeded/mutant checks pass after correcting the
paths scorer's output type. Staging-runner unit tests pass (5). No new LLM
inference has run yet; live Pi/stream usage integration is a prerequisite.

Replacement smoke completed: 6/6 finished, all referee checks passed, hashes
unchanged, no broker errors, and no standalone fallbacks. NH scored 0/2 against
each opponent. NN retained 279/356 complete neural decisions (78.4%), so its
10-pair expansion is held by the prespecified 80% gate. Policy/search expand
separately on openings023..032 (40 games); neither smoke is pooled into them.
The serial queue then performs CPU-small smoke and fixed-model budget probes,
followed by the LLM integration gate. Live queue status is stored under
`C:/Users/kevin/ai_bench/continuation-20260922`.

Three composed shape/scoring regressions also pass, bringing Rust tests to 65;
see [engineering fixtures](ENGINEERING-FIXTURES-2026-09-22.md). The LLM runner
passes seven tests, including real local HTTP streaming, reduced quota
allowances and rejection of missing usage. Three additional timeout-accounting
regressions will run before queued LLM inference. Thirty workspaces were
prepared without model calls; live smoke and main runs use different labels.

## Completed direct expansion

All 40 games on openings023..032 finished and passed referee checks. Pinned
hashes remained unchanged. NH won 3/20 against raw b10 policy and 0/20 against
standalone b10 search. All three policy wins were with NH playing White.
Broker: 10,151 completed requests, zero timeouts/errors. Standalone roles had
zero fallbacks. The original 36/40 NH-over-HH screening remains valid but does
not establish an advantage over these stronger neural references.

Each matchup contains 10 opening pairs. Prespecified conservative paired-mean
95% intervals for NH are [0, 0.5795] against policy and [0, 0.4295] against
search. These bounds are deliberately broad; no Elo or universal strength
claim follows. Current evidence does not justify an NH default promotion or
a 50-pair confirmation campaign for NH as a superior neural engine.

The shared KataGo process is serial, with cache cleared between games. Policy
uses one visit; search uses timely intermediate reports when needed. These
are different deployment treatments under the same 200 ms allowance, not
equal amounts of computation. Scheduling and cancellation are cooperative.

CPU-small smoke and fixed-model budget probes are next in the active queue.
The parent-lab report is generated by `summarize_continuation_20260922.py` from
saved records. New LLM cases now include two path-ancestor distractors and
strict typed comparisons; all controls are revalidated before inference.

## CPU smoke, budget curve, and current LLM gate

CPU-small b6/Eigen NH won 4/4 against HH on openings033..034. All four games
finished with unchanged input hashes and no broker errors. This is two smoke
pairs with a different model/backend; it is not pooled with b10/OpenCL results.

On eight fixed development positions, NN complete-round retention was 3/8 at
50 ms, 6/8 at 100 ms, 7/8 at 200 ms, and 8/8 at 400 ms. Median NN wall times
were 51.5, 101.8, 201.4 and 401.5 ms. No root nominations timed out. More budget
improved retention on this small set; it does not establish better play or
justify retrospectively reopening the failed 200 ms game-screen gate.

All 65 Rust tests, 48 Go Python tests, 11 staging-runner tests and six packing
runner tests pass. The five-task external scorer's controls and selected
mutants pass, including strict return/mutation types, ancestor distractors and
normal dataclass import behavior. These are finite checks, not correctness proof.

The LLM smoke made no inference calls. v1 failed because WMI process inspection
was blocked by the Windows sandbox; supported Get-Process listing replaced it.
v2 then passed protocol/scorer checks but stopped at the 4 GiB available-RAM
gate. About 3.51 GiB RAM and 3.61 GiB commit headroom were observed afterward.
No abandoned model was found. Existing applications and WSL services were
preserved, and the user was asked how to free memory. Both preparations are
retained; the 30-run experiment remains conditional on a passing fresh smoke.
