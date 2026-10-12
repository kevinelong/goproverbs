# Frozen disagreement review and one candidate gate

User authorized reviewing saved disagreements, deeper KataGo reference analysis,
one focused change if supported and conditional fresh paired screens. Preserve
all prior evidence. No default promotion, model changes or competing inference.

## Sample before reference labels

Source is the completed pass-v1 80-game screen. Enumerate full histories from
opening plus decision records; only completed neural comparisons with selected
move different from root policy are eligible. No labels from game winner or
score are used for selection. Hash all source traces, schedule and source files.

Two diagnostic strata: (A) neural-only against policy, restricted to root policy
probability>=0.50 and original selected-minus-root win estimate<0.02; (B) combined
against neural-only, restricted to selected moves nominated only by specialists.
Pick one eligible position per game by smallest SHA256(seed=230924, stem, turn).
Record missing eligible games instead of substituting other games. This enriched
sample is not representative of all play; positions share opening pairs.

Within each matchup, rank the20 opening IDs by SHA256(seed=230925, ID). First10
pairs are development, remaining10 are validation. Both colors of an opening
stay together. Freeze membership before deeper analysis. No threshold tuning
after reading either split. Validation is a fixed check, not pristine external
data: all originating games are previously inspected lab development evidence.

## Reference analysis

Same b10 model and pinned KataGo1.18.1 OpenCL. Black-reported values normalized
to the original mover. Analyze the child after each unique compared move: root
policy, actual chosen move, and best neural-only candidate among the saved
combined shortlist. Full history, komi7.5, TT19; independent referee legality.
Exact two-pass terminal children use exact TT values instead of a model query.

Use128 and512 completed visits per child, maxTime30 seconds, transport deadline
35 seconds. Clear cache before each child/budget. Alternate budget order by a
fixed hash; shuffle cases with seed230926. Reject intermediate/late/wrong-player,
nonfinite or insufficient-visit results. Preserve all raw queries/responses.
No higher-confidence claim from the same model simply because it searched more.
These are noisy, correlated reference estimates, never move-quality ground truth.

Report chosen minus policy winrate/score at each depth, specialist versus best
saved neural candidate, rank reversals and saturated estimates. The best saved
neural candidate is not a counterfactual full game. Large score/winrate divergence
is diagnostic. Cases, not individual child calls, are the unit; aggregate related
colors by opening when interpreting means. Do not infer per-move causal wins.

## Single fixed candidate and development gate

Candidate: retain root policy when its probability>=0.50 and the candidate's
one-visit win estimate improves by<0.02. Otherwise keep current behavior,
including pass agreement and complete-round requirements. No other thresholds,
blends or specialists will be tried in this experiment. Initially test this as
an offline decision rule on frozen traces, without modifying the live engine.

Use stratum A to decide whether it earns implementation. Each split must have
at least10 cases from at least5 openings. At both128 and512 visits, mean root
minus chosen winrate, averaged first within each opening, must be>=0.005.
At512 visits, beneficial cases (root improvement>=0.001) must be at least twice
harmful cases (root worse by>=0.001), with at least5 beneficial cases. No case
may lose>0.05 win probability under the candidate at BOTH reference depths.
This is an engineering screen, not a significance claim. Development must pass
before treating validation as support; validation must independently pass the
same fixed criteria. Never adjust criteria to turn a failed screen into a pass.

If either split fails, stop at the diagnostic report: no controller change or
fresh matches. If both pass, implement only this rule, test deadlines/pass/legality
and threshold boundaries, validate saved decisions, then freeze a separate fresh
20-pair candidate-versus-current neural screen at200ms. Carry forward all prior
completion, timing, cleanup and uncertainty gates. Larger confirmation remains
conditional; no automatic default promotion.

Always record source/asset hashes, preflight headroom and final cleanup. STOP
cancels between requests. Preserve partial failure labels without retrying them.
Open the produced report using its default Windows application.
