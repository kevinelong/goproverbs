# Neural-led hybrid plan and delegated implementation

User authorized writing the plan, launching a coding agent, and active root
supervision. One implementation agent owns the new decision module and its
tests. The coordinating root owns this plan, integration/probe harness, review,
live experiments and SESSION-HANDOFF.md. No commits or publication. Existing
Rust engine, profiles, completed evidence and release bundles stay preserved.

## Direction and evidence

NH defeated HH 36/40, but scored 3/20 against raw neural policy and 0/20 against
KataGo search. Investigate whether our ranking overrides useful neural advice.
The hypothesis is not established by those match totals alone. Keep the 200 ms
NN retention gate (78.4%, minimum 80%) closed for that historical treatment.

Use neural policy for candidate ordering and neural values for comparable
position judgments. Rules enforce legality, full-history superko, captures and
exact terminal scoring. Heuristics nominate alternatives and provide truthful
features. Tactical reading proposes forcing alternatives but cannot claim a
proof from a depth-limited search. Preserve a timely neural move as the fallback.
Do not mix arbitrary proverb bonuses into neural values.

## First deliverable

Implement a separately labeled Python controller over the existing pinned
KataGo and Rust GTP interfaces, with a pure/testable decision core. It leaves
historical HH/NH/HN/NN behavior unchanged. Return a move without mutating the
root game, plus complete timing, candidates, values and fallback telemetry.

Treatments: raw policy; neural candidate evaluation alone; that evaluation plus
heuristic nominees; plus tactical nominees; and both additions. Every variant
shares the same total wall allowance and model. Root policy recommendation is
obtained first. The evaluated shortlist always includes it. Compare candidates
only after a whole consistent evaluation round is complete; incomplete rounds
retain the root neural recommendation and are explicitly reported as fallback.
Failure to obtain an initial timely neural result is a failed decision, not an
invented heuristic move. Never consume late values as timely results.

Initial candidate cap: top three neural moves, up to two additional heuristic
and two tactical nominees. Validate every candidate against an independent
full-history referee; deduplicate, keep legal pass, reject malformed inputs.
Use a single calibrated neural outcome objective, with score only as a
documented tie-breaker; normalize Black/White perspective explicitly. Finished
two-pass positions use exact TT scoring. Current neural callbacks/transport are
serial; batching and caching are later performance experiments, not shortcuts
that discard history. No new model, runtime upgrade or neural training.

Pinned prototype details: child evaluations use one visit, with winrate from
KataGo rootInfo and reportAnalysisWinratesAs = BLACK, normalized to the original
player. Exact winrate ties use scoreLead only if all candidates provide it;
otherwise preserve neural-first nomination order. Specialist nomination gets
at most 50 ms and 30% of the post-root remainder. Existing Rust tactical level
2 search gets at most 25 ms, 100000 nodes, depth 4, beam 8; it is a proposal,
not a proof. GTP nomination timeout kills only that trial's owned GTP process.
All replay, legality, nomination, query and decision work counts toward the
move allowance; process startup, warmup, cache clearing and artifact hashing
are setup outside the allowance, identical across treatments.

## Diagnostics and validation

1. Deterministic tests: opponent/root perspective, illegal/duplicate nominees,
   complete versus partial rounds, expired/late queries, root fallback, no input
   mutation, exact terminal handling, missing/nonfinite values and cancellation.
2. Review the implementation before any inference. Reuse the pinned runtime,
   b10 model, existing Rust executable/profile, and serial resource preflight.
3. Freeze source and input hashes. Replay eight existing development positions
   at 200 and 400 ms, all five variants in fixed shuffled order. Record policy
   rank, selected move, nominated candidates, root/nomination/evaluation times,
   completed-round count, fallback and total overshoot. Position probes are
   diagnostics, never strength matches or a reopened historical gate.
4. Save diagnosis of historical NH policy overrides from the existing records;
   optional deeper reference evaluation is labeled an estimate, not ground truth.
5. Select no strength finalist until legality, deadlines, cleanup and usable
   neural evaluation all pass. A larger time allowance is a separate treatment.

## Later strength and performance gates

First strength target: outperform raw policy under the same total time budget.
Then compare to full KataGo search. Use fresh opening pairs with both colors,
unchanged weights/runtime/rules/hardware, separate development and holdout sets,
paired uncertainty, and no Elo or default promotion from a tiny smoke.
Add each specialist separately so we can identify both helpful and harmful
overrides. Larger confirmation remains conditional on a promising screen.

Profile before optimizing: distinguish nomination/ranking, neural execution,
serialization/IPC, and waiting. Explore persistent transport or batched leaves
only when measured costs justify it. Any cache identity includes model, rules,
komi, player and rule-relevant complete history. The first deliverable is a
working, reviewed, measured prototype; engine superiority remains unproven.
