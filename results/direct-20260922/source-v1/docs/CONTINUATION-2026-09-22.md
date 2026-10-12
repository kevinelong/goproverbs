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
