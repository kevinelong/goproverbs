# Neural-led paired screening protocol

Frozen before inference. User authorized live White validation followed by two
20-pair screens. Same pinned controller, b10 model, KataGo 1.18.1 OpenCL, Rust
executable/profile, TT rules, 19x19, komi 7.5, 200 ms total decision allowance.
One serial inference workload. No commits, default promotion or historical edits.

## Fixed treatments and data

First validate all five variants on eight White-to-move development positions,
made by removing the final White move from the previous eight Black positions.
These 40 decisions test legality, perspective and timely complete comparison;
they are not strength evidence. All must be legal, timely within 205 ms, with
all evaluated rounds complete. White values must equal one minus Black-reported
winrate, and negate Black-reported scoreLead. Failures hold strength screens.

Generate 40 new, legal four-move openings from one randomly chosen 3/4 corner
point in each corner, alternating Black/White, seed 23092026. Reject exact or
board-symmetry-equivalent histories present in any previous openings JSON under
results, as well as duplicates within this selection. Do not neural-filter for
estimated balance or change openings after seeing outcomes. Equal corner-stone
allocation is structural balance, not proof of equal winning chances.

First 20 openings: neural versus raw policy. Next 20 disjoint openings: combined
versus neural. Each opening is played with both role/color assignments. Shuffle
pair order and within-pair color order with seed 23092027. Run stage one before
stage two. Stage two proceeds regardless of stage-one wins if operational gates
pass. No tuning between stages. Clear neural cache before each game, never
reuse a position result across roles. No resignation, two passes end the game.
722 played moves beyond the opening is an unfinished game, never an awarded win.

The clock includes history replay, legality checks, policy retrieval, nomination
and neural comparison. Game setup, board synchronization and artifact logging
are outside the decision clock for every role. Record both decision and full
turn timing. All completed moves are independently checked against Rust and the
TT referee, and terminal area scores must agree. Full histories and SGFs saved.
If the owned proposer transport is killed on a stuck command, preserve its
fallback and stop the screen for transport recovery; do not silently rebuild
and continue a changed treatment. Ordinary nomination-budget exhaustion or a
late but fully drained command returns the retained root move and counts as
fallback under the completed-round gate.

## Operational and outcome gates

Stop immediately on missing root, malformed result, legality/board/score
disagreement, poisoned proposer, decision exceeding 220 ms, unfinished game,
STOP request or resource/cleanup failure. Save failures and partial evidence;
do not retry unchanged games to obtain a pass. After each complete pair require
at least 80% completed rounds for each evaluated role, and at most 1% decisions
over 205 ms. Report every overshoot above 200 ms including smaller tolerances.
The thresholds permit measured scheduler jitter, not extra planned search time.

Report games, wins/draws, color results, completed pairs and conservative 95%
Hoeffding intervals over pair scores. Report incomplete pairs separately.
Intervals describe this fixed opening distribution; no Elo claims. Record
per-role latency, complete comparisons, fallbacks, policy overrides and selected
specialist-only moves. Specialist selection is not a per-move causal benefit.

Larger confirmation requires an operationally valid screen with the conservative
interval lower bound above 0.5. Otherwise report inconclusive or unfavorable.
Even a passing screen does not automatically launch a larger experiment or
promote defaults. Full KataGo comparison follows confirmation in a new protocol.
No source/model changes, resampling, score blending or sequential win-based
stopping during either screen. All frozen input hashes verified before and after.
