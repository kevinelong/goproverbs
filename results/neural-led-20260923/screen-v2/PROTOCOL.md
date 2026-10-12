# Combined screen v2: history-preserving copy optimization

The v1 run completed all 20 neural-versus-policy pairs (24/40 wins) but stopped
in the first combined game after a 223.45 ms decision exceeded its predefined
220 ms operational gate. It has zero complete combined pairs. Preserve all v1
evidence. Do not retry that same game or pool it into this strength screen.

Diagnosis: nomination took 166.57 ms, but Rust proposal work took only 18.04 ms.
The controller repeatedly used deepcopy on the complete set of historical board
tuples. Tuples and stone strings are immutable; independent shallow copies of
the board list and seen-position set preserve the entire superko history without
recursively copying every tuple. This is a copy implementation change, not a
board-only history cache or move-policy change. Tests must verify long-history
equivalence, branch isolation, capture, ko and pass/terminal semantics.

Freeze changed controller and tests, unchanged model/runtime/Rust/profile, source
dependencies and this protocol before inference. Validate all five variants on
the eight previous White development positions plus the exact failed White root
(45 decisions). The failed root is development data only. Every validation move
must be legal, finish within 205 ms and complete its neural comparison; perspective
checks remain required. No strength game starts unless all 45 pass.

Then run combined versus neural on 20 new four-move openings, both colors, at
the same total 200 ms allowance. Both roles use the optimized controller. The
generation/exclusion rule is unchanged; exclude all previous openings JSON,
including the entire v1 planned set, before selecting these new pairs. Fixed
generation seed 23092026, schedule seed 23092027. The first neural-policy screen
is not repeated or relabeled; this experiment is the separate specialist screen.

All other v1 rules apply unchanged: TT19, komi7.5, no resignation, 722-move cap,
serial inference, no tuning or result-based stopping, full history and SGFs,
independent referee and Rust board/final-score agreement, preserved partial and
failed evidence, STOP cancellation, input hashes and cleanup. Decision clock
includes history reconstruction, legality, inference and nomination; setup,
synchronization and logging are outside for both roles.

Stop on any failed root, invalid response, legality/score mismatch, poisoned GTP,
decision over220ms, unfinished game, STOP or cleanup failure. After each pair,
each role must complete at least80% of rounds and have at most1% over205ms.
Record every over200ms decision. A drained nomination timeout may return the
retained root; an owned transport killed by timeout stops the experiment.

Report complete-pair score, color results and conservative95% Hoeffding interval,
latency, fallbacks and selected specialist moves. No Elo or per-move causal claims.
Larger confirmation remains held unless the screen is operationally valid and
its interval lower bound exceeds0.5. No automatic default promotion. No pooling
of timing measurements or strength outcomes across changed v1/v2 treatments.
