# Hybrid and standard-board results - 2026-09-20

## Outcome

The hybrid is implemented and available with `--search hybrid`. It uses
heuristics and a shallow all-move scan to nominate candidates, then feeds
completed deeper-search scores back into the final choice. In the snapback
regression it rejects the initial favorite after deeper reading.

It won **4 of 4 pilot 19x19 games** against the existing selective search,
covering two openings with colors swapped. This is promising but too small a
sample to establish stronger play. The default remains selective; hybrid is
opt-in. No learned profile was promoted.

The scope correction is also implemented: empty_corner, side_development,
and early_33 now activate only on 19x19. Local tactical measurements remain
available on other sizes. Small-board algorithm checks are kept separate from
standard-board strategic evidence. See [design and sources](HYBRID-SEARCH.md).

## Search correctness controls

New tests compare full-width alpha-beta and unpruned minimax with an independent
exhaustive recursion on four 3x3 positions at depth three. Root values agree
within 1e-10, selected moves agree, and alpha-beta visits no more nodes.
The full/minimax modes ignore the quiet beam when tactical extensions are zero.

A separate release/GTP check uses four 5x5 fixtures at completed depth three,
with ample time/node budgets. Moves and displayed scores agree in every case:

| Position | Alpha-beta nodes | Plain minimax nodes |
| --- | ---: | ---: |
| capture-pair | 2,604 | 6,288 |
| capture-corner-pair | 4,399 | 10,364 |
| snapback-trap | 286 | 608 |
| respect-ko | 1,251 | 5,581 |

Node totals include iterative-deepening work. The GTP score comparison uses
three-decimal output; the Rust oracle tests use full-precision values.
These checks establish agreement on these trees, not exhaustive correctness
for all Go positions. [Reference report](../results/hybrid-round/reference-5.json).

## Ten 19x19 development positions

All modes used baseline weights, no tactical extensions, 20,000 nodes, 1,000 ms,
maximum depth three, beam 12, and hybrid shortlist three per ranking.

| Mode | Acceptance | Completed depth in every case | Median nodes | Median round trip |
| --- | ---: | ---: | ---: | ---: |
| Current selective | 7/10 | 3 | 1,319.5 | 104.1 ms |
| Hybrid | 7/10 | 3 | 1,034.5 | 50.2 ms |
| Full-width alpha-beta | 7/10 | 1 | 20,000 | 242.2 ms |
| Plain minimax | 7/10 | 1 | 20,000 | 238.2 ms |

Full-width methods could not complete depth two before exhausting the node
budget. Their 7/10 result therefore does not compare equal completed depths
with the other methods. The purpose here is to measure the budget tradeoff.
The hybrid reaches the same acceptance score more cheaply in this small suite.

All four miss the immediate local targets in rescue-single, capture-pair, and
capture-corner-pair on 19x19. These labels are handcrafted expectations, not
expert proof that taking territory elsewhere is wrong. The larger three-stone
rescue is selected by all four. The suite mostly places local tactical shapes
on a standard board; it is not a broad fuseki/middlegame strategy benchmark.

The 19x19 cases preserve bottom/left edge context where that matters. The
5x5 snapback and 3x3 simultaneous-capture cases were not blindly enlarged:
changing their opposite boundaries would change their tactical meaning.

[Fixtures](../benchmarks/fixtures-19.json),
[selective results](../results/hybrid-round/selective-19.json),
[hybrid results](../results/hybrid-round/hybrid-19.json),
[full-width results](../results/hybrid-round/full-19.json), and
[minimax results](../results/hybrid-round/minimax-19.json).

## Paired 19x19 pilot

Both players use the same baseline weights, Tromp-Taylor rules, komi 0.5,
5,000 nodes / 200 ms / maximum depth four / beam 12. Hybrid uses shortlist three;
tactical extensions are disabled. Each two-move opening is generated from its
recorded seed, then played with both color assignments. A 722-move cap would
mark unfinished games without awarding wins; all four games finished normally.

| Seed | Hybrid color | Final result | Winner |
| --- | --- | --- | --- |
| 20260921 | Black | B+42.5 | Hybrid |
| 20260921 | White | W+71.5 | Hybrid |
| 20260922 | Black | B+74.5 | Hybrid |
| 20260922 | White | W+79.5 | Hybrid |

An independent Python referee checked each generated move, both engines'
boards, and both final scores. There were no disagreements. SGFs and per-move
traces are stored beside the [first pair](../results/hybrid-round/hybrid-v-selective-19/report.json)
and [second pair](../results/hybrid-round/hybrid-v-selective-19-seed2/report.json).
Time-limited play can vary with machine load; completed depths and elapsed
times are recorded. Two opening pairs are not a rating estimate or a reliable
measurement of general win rate. Both participants use the same approximate
evaluator and share its blind spots.

## Verification and provenance

- **40 Rust integration tests passed** with `cargo test --offline -j 1`.
- **13 Python referee/release-protocol tests passed**.
- Format check, Clippy with warnings denied, and release build passed.
- New tests cover full/minimax/oracle agreement, beam independence, hybrid
  refutation of a heuristic favorite, equal-depth evidence rollback when a
  round is interrupted, legal fallback, and board-size feature restrictions.
- Release tests cover invalid-mode/shortlist atomicity, legal hybrid variations,
  reported score agreement, and opening feature gates on 9/13/19/25 boards.
- Earlier full test attempts hit Windows LNK1104 on test executables. A
  serialized build subsequently passed the entire suite; no security controls
  were changed. The new search-mode tests also passed independently.

Executable SHA256:
`302f621fb393e556f486cca6ab993dba596f5dd7f6439e94fdcf39dd32bc8c22`.
Each experiment records relevant input/harness hashes.
[Aggregate data](../results/hybrid-round/summary.json) and
[source manifest](../results/hybrid-round/source-manifest.json).
All runs are CPU-only; no inference server or GPU workload was launched.

## Next evidence to gather

Expand the paired 19x19 opening set and use expert-reviewed full-board positions
with tactical and strategic exceptions. Compare at several time/node budgets,
including the usual one-second budget, and against an established external
engine. Test revisiting excluded root alternatives after a nominee is refuted.
Keep board-size applicability, rule legality, and learned weights distinct.
The current hybrid provides the requested feedback mechanism; its general
playing strength and the numeric proverb weights remain research questions.
