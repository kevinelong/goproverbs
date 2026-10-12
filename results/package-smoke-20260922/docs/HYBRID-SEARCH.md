# Hybrid search and board-size scope

## Target board

19x19 is the target for strategic proverb evaluation. Small boards remain useful
for rules, tactical shapes, exhaustive search comparisons, and fast software
checks. Their win rates do not establish the best 19x19 strategy or weights.

This distinction is consistent with the different 9x9 strategic treatment in
[81 Little Lions](https://cdn.online-go.com/81_little_lions/81_little_lions_an_introduction_to_the_9x9_board_for_advanced_beginners_2022.pdf)
and the whole-board setting of the BGA's
[opening strategy article](https://www.britgo.org/bgj/00002.html).
Our applicability gates and numerical weights are engineering decisions, not
claims that those sources prescribe these exact features or constants.

| Feature family | Current applicability | Interpretation |
| --- | --- | --- |
| Legal capture, liberties, connectivity, repetition | All supported board sizes | Rules enforced by the game model |
| Capture/rescue/self-atari, eye shape, connection, local cutting/atari proxies | All sizes | Local measurements; usefulness still depends on the full position |
| empty_corner, side_development, early_33 | **19x19 only** | Whole-board opening proxies; disabled elsewhere pending separate validation |
| Stone balance, atari risk, liberties, limited-radius influence | Shared search evaluator | Experimental relative values, not established cross-size strategic weights |

The opening gate previously enabled these three features on boards at least
9x9. Restricting them to 19x19 prevents silently transferring those assumptions
to 9x9, 13x13, or 25x25. It does not claim that corners have no value elsewhere.
Earlier small-board match reports remain historical evidence under the earlier
gate and must not be combined directly with new results.

## Search modes

| Mode | Candidate policy | Role |
| --- | --- | --- |
| selective | Top beam plus immediate tactical moves and pass at each node | Existing default/control |
| full | All legal moves, with alpha-beta pruning | Full-width comparison |
| minimax | All legal moves, with alpha-beta cutoffs disabled | Small-board correctness reference |
| hybrid | Broad one-ply scan, then a heuristic/search shortlist at the root; selective replies | Experimental allocation of deeper search |

All modes share legality, leaf evaluation, weighted edge preferences, budgets,
and completed-iteration fallback. Plain minimax is also depth first; alpha-beta
can omit branches without changing a completed full-width minimax value, while
our beam/shortlist pruning can change it. See the
[Berkeley minimax explanation](https://inst.eecs.berkeley.edu/~cs188/textbook/games/minimax.html).
For the full-width/minimax reference comparisons, tactical extensions are zero.
Enabling extensions still invokes the separate selective tactical reader at
extended leaves; that is not the unextended exhaustive reference configuration.

## How the hybrid feeds evidence back

1. Rank every legal root move using the existing weighted heuristics.
2. Complete a one-ply evaluation of every legal root move. This scout round
   does not use tactical extensions.
3. Retain the top three heuristic choices and top three scout choices, plus
   all immediate captures/rescues/new ataris and pass. Duplicates are removed.
   `--shortlist` changes the number from each ranking. The union can exceed six.
4. Deepen every retained candidate against alternating opponent replies. Replies
   use the existing selective beam, including tactical candidates and pass.
5. Choose by the best completed equal-depth search score. Display each nominee's
   heuristic score, scout score, deeper score, and verification depth.

The shortlist is fixed after the scout round in this first version. Search
feedback changes the final ranking; it does not automatically learn new weights
or permanently revise the proverb catalog. A future adaptive shortlist could
revisit excluded alternatives when a favorite is refuted.

Only a fully completed round updates the decision and root evidence. If time
expires after deepening just some candidates, the entire partial round is
ignored. This prevents comparing a deep score for one move with shallow scores
for its competitors. A legal fallback remains available before any round
completes. The score continues to include the existing weighted edge bonuses,
so this experiment isolates search allocation rather than also replacing the
objective function.

This is corroborating/refuting evidence within a bounded selected tree. It is
not proof of a good move: root pruning, selective replies, limited depth, and
the approximate evaluator can all miss something important.

## Example: revising a heuristic favorite

In the 5x5 snapback regression, all nominees finish depth three:

| Move | Heuristic preference | Scout evaluation | Deeper evaluation |
| --- | ---: | ---: | ---: |
| C1 | 6.510 | 15.426 | 8.427 |
| E2 | 3.510 | 8.076 | 14.402 |
| A4 | 2.510 | 14.427 | **17.751** |
| pass | 0.000 | 5.750 | 10.500 |

C1 is favored by both the initial heuristic and the scout, but deeper reading
selects A4. C1 permits a larger recapture. These numbers are evaluation units,
not predicted points or win probabilities; the heuristic column is on a
separate preference scale. This small-board example demonstrates the feedback
mechanism, not standard-board strategic strength.
[Full trace](../results/hybrid-round/refuted-snapback.txt).

## Run it

```powershell
.\target\release\goproverbs.exe --size 19 --suggest --search hybrid --shortlist 3 D4 Q16
.\target\release\goproverbs.exe --gtp --search hybrid --time-ms 1000 --nodes 20000
python benchmarks/check_reference.py --output results/my-reference.json
python benchmarks/lab.py evaluate --fixtures benchmarks/fixtures-19.json --search hybrid --output results/my-19.json --nodes 20000 --depth 3 --beam 12
python benchmarks/compare.py --mode-a hybrid --mode-b selective --size 19 --pairs 1 --nodes 5000 --time-ms 200 --depth 4 --move-cap 722 --output results/my-hybrid-match/report.json
```

GTP supports `gp-mode selective|full|minimax|hybrid` and `gp-shortlist N`.
Invalid settings leave the existing setting intact. `gp-limits` preserves the
mode and shortlist setting. The benchmark harness accepts corresponding search
mode options and records them along with budgets and hashes. A move-cap cutoff
is recorded as unfinished; its provisional board margin never awards a win.

See [executed results](HYBRID-RESULTS-2026-09-20.md). Hybrid remains opt-in while
we gather broader 19x19 evidence.
