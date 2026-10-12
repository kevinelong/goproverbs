# Small-search verification: fixed protocol

Authorized September23 after the failed disagreement candidate. One new
experiment; preserve prior source/results. Same pinned b10 model, KataGo1.18.1
OpenCL, BLACK reports, TT19, komi7.5, full history and200ms total decision budget.
No change to default engine. Serial inference, resource preflight and cleanup.

## Candidate fixed before measurements

Run the current neural or combined chooser. If its completed comparison selects
an alternative to root policy, compare that alternative and policy using N
completed visits per child. Retain the alternative only when its estimated
winning probability exceeds policy by at least0.005 (0.5 percentage points).
No score tie-break in this new verification. Otherwise choose policy. Exact
two-pass children use referee scores; preserve current pass agreement. Incomplete
verification retains policy and is explicitly counted as a verification fallback.
Invalid responses fail the decision, rather than silently becoming fallbacks.
One shared absolute200ms deadline includes baseline choice, replay, legality,
both child searches and final selection. No partial results affect choice.

## Timing-only depth selection

Take10 cases per old disagreement stratum by ascending SHA256(seed=230930,id).
Do not read prior reference labels. For each case run the actual experimental
chooser at4,8,16 visits in hash order, clearing cache before each full decision.
Rust setup/synchronization, cache clear and external logs remain outside the
decision timer, matching prior timing definitions. Current baseline generation,
specialist nomination and verification are inside. Record outer elapsed time.
Select the largest depth with all20 decisions legal/complete, no fallback,
p95<=150ms, maximum<=180ms, and at least5 verified overrides in each role.
If no depth qualifies, stop. This small profile is feasibility, not a latency
guarantee. Freeze the selected depth in depth.json before new reference labels.

## Fresh internal sample and split

From the completed pass-v1 games, select one previously unqueried override
position per game (neural in stage1, combined in stage2). Eligible positions have
a completed old comparison and chosen move different from root. Exclude every
full-history hash in the prior79-case disagreement dataset, including profiling
cases. Pick smallest SHA256(seed=230931,game,turn). Missing games remain missing.
Within each role, sort20 opening IDs by SHA256(seed=230932,id); first10 openings
are development, remaining10 validation. Both colors stay together. Freeze all
membership and source hashes before inference. These are new positions from
previously inspected games, not pristine independent external validation.

At the selected depth, run the live experimental chooser on each development
position. Save its current baseline move, root policy, selected move and complete
trace before reference analysis. Reference each unique compared child at128 and
512 completed visits, with cache clearing and hash-ordered depths/moves. Exact
terminal children use the independent referee. Reject intermediate, wrong-ID,
warning/error, nonfinite, wrong-player or insufficient-visit responses. Each
reference has35s transport deadline,30s maxTime. Same-model estimates are noisy
and correlated; deeper search is not ground truth or game strength evidence.

## Gates fixed before measurements

For each split, require at least30 cases and15 openings, at least15 cases in
each role, no decision over200ms or fallback, p95<=180ms, all legal, all required
visits complete. Compute candidate-minus-current and candidate-minus-policy
win probability at both reference depths, first averaging within opening pairs.
Require pooled mean improvement over current>=0.005 at BOTH depths; pooled
improvement over policy>=0 at BOTH depths. Neither role may have negative mean
improvement over current at either depth. At512 visits require at least5
beneficial cases (>=0.001), at least twice as many beneficial as harmful
(<=-0.001), and no case worse than current by>0.05 at BOTH depths.
These are conservative engineering screening gates, not significance tests.

If development fails, stop and leave validation references unopened. If it
passes, run validation once under identical gates. No threshold changes or
depth selection using quality labels. If validation fails, stop with report.
If both pass, freeze a separate20-opening-pair (40-game) verified-combined versus
raw-policy screen with fresh openings disjoint from all prior screens. Before
games, carry out existing pass/White/terminal/deadline controls. All games must
finish, preserve legality/score consistency and meet200ms timing/no-fallback
gates; move cap722 new moves. Report pair-level conservative95% intervals and
color counts; require lower interval>0.5 before larger confirmation. No default
promotion. A failed completion gate stops the remaining games without scoring
unfinished games as losses. No automatic full-KataGo comparison.

## Records

New output verification-v1 contains frozen sources, protocol, sample membership,
assets/input hashes, resource state, raw wire traffic, decision traces, reference
values, timing, status, gates and report. STOP cancels between requests and in
decision callbacks. Preserve partial failures; no in-place retry. At least4GiB
free physical RAM; inspect model processes, Ollama and GPU before and after.
Open the final report using the user's file association and update the handoff.
