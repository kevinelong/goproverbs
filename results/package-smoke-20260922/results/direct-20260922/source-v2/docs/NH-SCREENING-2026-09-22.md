# NH versus HH: 20-pair screening, September 22, 2026

Neural nomination plus heuristic search (NH) won **36 of 40 games (90%)**
against heuristic-only nomination/search (HH), on 20 previously unused opening
pairs at 200 ms per move. All games finished and passed independent board and
final-score checks. This supports advancing NH to further comparison; it does
not establish an Elo rating or justify changing the default engine yet.

| Result | Observed |
|---|---:|
| Complete color-swapped pairs | 20/20 |
| NH wins / losses / draws | 36 / 4 / 0 |
| NH wins as Black / White | 18/20 / 18/20 |
| Pairs swept / split / lost by NH | 16 / 4 / 0 |
| Mean paired score | 90% |
| Conservative 95% paired interval | 59.6%-100% |
| Broker errors | 0 |
| Decisions after the fixed openings | 18,187 |
| Elapsed time, including startup and cleanup | 61.04 minutes |

The interval uses the pre-existing Hoeffding bounded-mean summary, treating
each complete opening pair as one independent observation. It is conditional
on this opening distribution and experimental setting. These are unused
development openings, not expert-reviewed pristine holdout positions.

## Fixed protocol and provenance

- 19x19 Tromp-Taylor, komi 7.5; each opening played with NH as each color.
- Exactly original opening IDs `opening-002` through `opening-021`, selected
  before outcomes. Pilot IDs 000/001 and their exact histories were excluded.
  A separate audit found 20 unique histories under rotations/reflections and
  no symmetry-equivalent pilot histories. No openings were replaced or dropped.
- Original frozen native Windows arena executable, SHA256
  `c4052674f6a924652ec396da07972e138fafc06e46317aa805a313d5d8d5dd9c`.
- KataGo OpenCL 1.18.1, old b10 network
  `kata1-b10c128-s919229184-d169515535.txt.gz`, unchanged baseline profile.
- Neural root nomination uses the top three policy moves from one visit,
  full move history, serial inference, fixed orientation, and no pondering.
  Root inference/setup is deducted from the common 200 ms move allowance.
- Hybrid search: depth ceiling 12, beam 12, 10,000,000-node ceiling.
  Both sides use heuristic leaves. All recorded decisions have neural leaf
  evaluation disabled. No tuning or default promotion occurred during this run.
- Frozen harness comes from the final source archive. The original arena
  source is separately preserved in `executable-source/src`; that historical
  source directory did not include a contemporaneous hash manifest. The
  executable itself is pinned to the original pilot manifest. The `snapshot/src`
  and `snapshot/tests` copies belong to the later final revision used for WSL
  validation, not the original arena executable. See the provenance note below.

## Timing and resource checks

| Decision metric | NH | HH |
|---|---:|---:|
| Recorded decisions | 9,096 | 9,091 |
| Median wall time | 200.001 ms | 199.550 ms |
| 95th percentile | 200.474 ms | 199.783 ms |
| Maximum wall time | 201.043 ms | 200.323 ms |
| Decisions exceeding 210 ms | 0 | 0 |
| Median remaining search budget | 195 ms | 199 ms |
| Decisions with zero remaining search budget | 0 | 0 |

The budget is cooperative, not a strict wall-time ceiling. NH exceeded exactly
200 ms on 4,558 decisions and HH on 54; these small overshoots are included
above. NH selected a neural-hinted move on 2,139/9,096 decisions; this is
descriptive overlap, not causal attribution for the wins. There were 9,097
broker queries: one warmup plus one per NH decision.

One inference workload ran. GPU memory was 2,748 MiB used before loading,
2,931 MiB loaded, and 2,763 MiB immediately after cleanup. A subsequent check
found 2,748 MiB used, no KataGo/goproverbs processes, and no loaded Ollama model.
Run interval: 2026-09-22 07:12:28-08:13:30 UTC (00:12:28-01:13:30 Pacific).

## Validation, evidence, and next gate

`scripts/summarize_nh_screening.py` verified all 40 finished records, both colors
for exactly the 20 selected IDs, per-move mode/color accounting, saved SGFs,
decision counts, zero neural-leaf use, query accounting, zero broker errors,
and every pinned snapshot/external/run input hash after completion. The runner
compared both engine boards to an independent Python referee after each move
and checked both final scores for every finished game. Process exit code was 0.

- [Summary and timing](../results/nh-screen-20260922/summary.json).
- [Prespecified selection, command, and hashes](../results/nh-screen-20260922/plan.json).
- [Run manifest and resource snapshots](../results/nh-screen-20260922/run/manifest.json).
- [All game results](../results/nh-screen-20260922/run/games.json); adjacent files
  contain SGFs, decision traces, and the complete KataGo request/response log.
- [Executable source provenance clarification](../results/nh-screen-20260922/executable-source-provenance.json).
- [Opening symmetry audit](../results/nh-screen-20260922/opening-symmetry-audit.json).

Do not pool the pilot's four NH games into this screening result. Next, compare
NH against the standalone pretrained policy/search reference and directly
against NN. Before more NN volume, fix and test end-to-end neural leaf deadlines
and stale-request handling. Preserve full-history superko semantics and atomic
complete-round fallback. Confirm any proposed default/weight promotion on at
least 50 additional fresh pairs, with protocol selected before outcomes.

Separately, the handoff validation gap is closed for Linux: all 21 final Rust
source/test/Cargo files matched the final snapshot, reconciling the observed
47-test WSL pass. Native Windows full-suite execution remains subject to the
previous Application Control block. See the separate
[WSL performance report](WSL-PERFORMANCE-2026-09-21.md); its 44-test timing
snapshot and this native Windows strength screening are different experiments.
