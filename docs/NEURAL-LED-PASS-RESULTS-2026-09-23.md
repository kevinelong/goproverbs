# Pass agreement: validated, fresh screens complete

The authorized plan is complete. The controller now accepts a timely root-policy
pass when the opponent has just passed. All other moves retain the existing
comparison rule. Pass agreements are recorded separately from completed neural
rounds and deadline fallbacks. No historical run, Rust default or release changed.

## Validation

- 85 Python regression tests passed. The frozen experiment passed36 controller
  and harness controls, including29 controller tests. Pass controls cover both
  colors, winning/losing/drawn outcomes, missing agreement conditions, exact
  scoring and deadline handling. Full-history superko tests remain intact.
- 45/45 live position checks passed, including the saved root that repeatedly
  rejected an opponent/policy pass agreement. All evaluated variants agreed to
  pass there and matched the independent terminal score.
- 5/5 endgame development replays finished normally with referee/Rust score
  agreement. The formerly unfinished game, replayed from its original opening,
  finished at380 total moves (376 new moves) with B+42.5, instead of hitting the
  old722-new-move cap. These replays are development evidence, not strength data.
- All80 fresh strength games finished. There were no illegal moves, mismatched
  boards/scores, deadline overruns, fallbacks or poisoned transports.
- 27,560 strength decisions:21,034 completed neural comparison rounds,
  31 timely pass agreements and6,495 raw-policy decisions. No agreements were
  counted as completed comparisons. Maximum observed decision time100.03ms.
- Frozen hashes, opening-history freshness and final counts verified. Model/GTP
  processes stopped, Ollama had no resident model and no run lock remained.

## Fresh paired results

Same200ms total allowance, model/runtime/rules/profile and fixed schedule.
20 distinct opening pairs per matchup, role colors swapped, disjoint opening
sets. Each pair contributes one observation to the conservative95% Hoeffding
interval. Results are conditional on this opening distribution; no Elo estimate.

| Matchup | First role wins | Pair score | Conservative95% interval | Wins as Black / White |
|---|---:|---:|---|---|
| Neural vs raw policy | 20/40 | 50% | 19.6%-80.4% | 8/20;12/20 |
| Combined vs neural | 21/40 | 52.5% | 22.1%-82.9% | 11/20;10/20 |

Neither interval excludes no advantage. Neither treatment meets the predefined
larger-confirmation gate. These results do not establish that adding neural
one-ply evaluation beats policy, or that the heuristic/tactical specialists
improve on neural-only. Earlier24/40 and partial2/4 results belong to different
treatments and opening sets; do not pool them or attribute their differences
causally to the pass rule.

| Matchup | Role | Decisions | Median decision ms | Maximum ms | Pass agreements |
|---|---|---:|---:|---:|---:|
| Neural vs policy | Neural | 6496 | 12.89 | 25.87 | 20 |
| Neural vs policy | Policy | 6495 | 2.95 | 9.66 | 0 |
| Combined vs neural | Combined | 7284 | 47.81 | 100.03 | 3 |
| Combined vs neural | Neural | 7285 | 12.44 | 45.78 | 8 |

Combined selected specialist-only moves728 times. This measures use, not benefit.
Its median cost was about3.8 times neural-only in the same matchup without a
demonstrated strength gain. Timing includes replay, legality, pass scoring,
nomination and neural work, but excludes setup, board synchronization and logs.

## Interpretation and next gate

The pass rule addresses the observed known-loss/nonzero-estimate loop and passed
the planned completion validation. It does not prove that every future game
will terminate quickly or that every policy-recommended pass is strategically
optimal. Keep the move cap and exact scoring checks.

Keep the efficient full-history clone and explicit pass telemetry. Do not
promote the combined engine or expand strength confirmation from this evidence.
Full KataGo comparison remains held under the declared protocol. The next
research work should inspect saved disagreements and evaluation reliability
before changing candidate selection or adding more specialist cost. Any new
objective/search treatment needs a separate fixed protocol and fresh openings.

## Reproduction and handoff

Protocol: docs/NEURAL-LED-PASS-PLAN-2026-09-23.md.
Controller/tests: benchmarks/neural_led.py and test_neural_led.py.
Runner/tests: benchmarks/neural_led_screen.py and test_neural_led_screen.py.
Evidence: results/neural-led-20260923/pass-v1/ contains frozen source, model and
executable hashes, excluded opening hashes, schedule, positions, endgame inputs,
raw traffic, full move traces, SGFs, status, paired.json and REVIEW.md/REVIEW.json.
Aggregate report is reproduced by benchmarks/review_neural_led_screen.py.
Run is complete; do not resume or overwrite it. No inference remains active.
After the run, a preparation guard and regression test were added to prevent
labeling the current controller as an older treatment. Use --pass-agreement for
future preparation; old treatment reproduction requires its frozen source.
That launcher guard does not alter the completed experiment or decision rule.
