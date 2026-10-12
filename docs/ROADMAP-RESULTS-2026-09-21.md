# Roadmap execution - September 21, 2026

All nine workstreams received an implementation or an executed experiment.
This completes an initial engineering and research pass, not the larger
confirmation program. The standalone default and feature weights remain
unchanged. The most promising next screening candidate is neural nomination
with heuristic search (NH): it retains deeper search and adds little latency.
That is a prioritization decision, not a demonstrated strength ranking.

The [written plan](ROADMAP-2026-09-21.md) records assumptions and remaining
acceptance gates. The [workflow](RESEARCH-WORKFLOW.md) gives runnable commands.
Machine-readable totals are in `results/roadmap-20260921/summary.json`.

## Completed comparisons

Twelve new complete games: 19x19 Tromp-Taylor, komi 7.5, two seeded opening
pairs, each variant playing both colors against the same HH heuristic hybrid.
The older b10 network and KataGo 1.18.1 OpenCL stayed fixed. Each move had a
200 ms decision budget including neural nomination and protocol setup.

| Variant | Neural nominees | Neural evaluation | Wins against HH | Retained neural rounds | Median / p95 move time |
|---|---|---|---|---|---|
| HH control | No | No | Reference | Not applicable | 199.8 / 200.4 ms |
| NH | Yes, up to 3 | No | 4/4 | Not applicable | 200.3 / 200.9 ms |
| HN | No | Yes | 2/4 | 724/724 decisions | 201.8 / 205.7 ms |
| NN | Yes, up to 3 | Yes | 4/4 | 537/803 decisions | 202.4 / 206.2 ms |

- All games finished. Independent Python legality, board comparisons against
  both Rust engines, and final score agreement passed. There were 4,884
  measured decisions and 4,908 recorded moves including opening moves.
- No broker errors in 53,351 queries. Raw requests/responses, move traces, SGFs,
  executable/model/configuration hashes, and hardware snapshots are preserved.
- HN and NN retained depth one throughout these games. HH and NH completed
  depths two through four. NN fell back to the heuristic scout on 266 moves
  because the entire expanded neural round could not finish in budget.
- Wall time is cooperatively bounded: the largest observed decision was
  218.4 ms. The small neural overshoots are a limitation of this comparison.
- Two pairs give very wide conservative 95% pair intervals: NH/NN approximately
  0.04..1.00, HN 0..1.00. They do not establish superiority, rank, or Elo.
  HN won both White games and lost both Black games. No direct NH-versus-NN
  comparison has been run. These are generated opening samples, not a
  representative tournament distribution or expert-reviewed positions.

The earlier 76 documented games remain historical evidence. These 12 bring
the documented total to 88; they must not be pooled into one win rate because
opponents, boards, budgets, and experimental questions differ.

## A failed mechanism, then a useful correction

The first evaluator hook attempted a full depth-two neural verification round.
At 200 ms it completed none of those rounds on eight development positions,
with either the older b10 or the newer small network. At 1,000 ms it completed
6/8 with the b10 network. Counting these as effective neural decisions would
have misrepresented the experiment.

The revision first evaluates every nominee one ply ahead, retaining that
complete neural round if deeper search is interrupted. It completed this
round on 7/8 development probes at 200 ms. Partial scores are never mixed into
the final decision. The arena above uses this revision plus the measured
candidate optimization; every variant shares that optimization.

Neural values use rawLead with explicit Black/White perspective conversion.
Exact terminal area scoring takes precedence. Existing path preferences are
still added, so the combined score is not calibrated Go points. Neural values
are not attributed to proverb explanations. `external_leaf` describes the
retained round; terminal branches within it still use exact scoring.
Protocol reference: [KataGo 1.18.1 analysis engine](https://github.com/lightvector/KataGo/blob/v1.18.1/docs/Analysis_Engine.md).

## CPU-only and smaller-network measurements

Twelve fixed development positions per backend/network combination, cleared
neural cache before each position, warmed runtime, full history and protocol
overhead included. One inference workload ran at a time.

| Network | Eigen CPU, 4 threads | OpenCL RTX 5070 |
|---|---:|---:|
| kata1-b10c128-s919229184-d169515535 | 25.07 ms median | 3.42 ms median |
| lionffen_b6c64_3x3_v10 | 8.98 ms median | 3.08 ms median |

CPU logs explicitly confirm Eigen. No GPU computation is required by that
backend. The standalone heuristic engine also remains CPU-only.

The small network is a 2025 six-block, 64-channel extra network aimed at 19x19;
its architecture can lack a whole-board receptive field. It is a useful local
speed candidate, not established here as the strongest or newest available
model. Source and limitations: [official extra networks catalog](https://katagotraining.org/extra_networks/).
The official Eigen AVX2 archive digest was checked against its release asset.
Each run records executable and network hashes.

No match-strength comparison between these two networks was performed.
CPU nomination at roughly 9 ms looks feasible inside a 200 ms budget, but its
playing strength and completed search depths need their own matches.

## Search optimization and proverb evidence

Candidate ranking formerly repeated group work even for unaffected groups.
Rescue checks now inspect relevant groups unless captures can change remote
liberties; new-atari checks inspect enemy groups that lose a second liberty.

All candidate output matched on 94 positions, including generated small-board
histories. Four fixed-depth searches matched move, score, depth and node count.
Aggregate measured ranking time fell from 110.32 to 64.68 ms (41.4%); median
individual call time fell from 1.30 to 0.87 ms. This is a measured sample result,
not a 41% whole-engine speedup. Evidence: `optimization.json`.

[The structured catalog](PROVERB-CATALOG.json) contains 16 entries with
provenance, scope, exceptions, implementation status and missing tests, plus
the four engineering leaf features. Historical sayings and invented numeric
weights are kept distinct. Strategic opening proxies remain gated to 19x19.

Thirteen profiles were evaluated on ten existing development fixtures at
komi 0.5: baseline plus removal of each nonzero feature. Baseline immediate
ranking met 10/10 labels; hybrid search met 7/10. Removing capture reduced
search agreement to 6/10, rescue to 5/10, atari-risk to 5/10, and influence
increased it to 8/10. Other changes are in `ablations/report.json`.
These labels are preferences, not proven best moves. Unchanged results do not
prove a feature useless; improved agreement does not prove stronger play.
No weights were promoted.

## Infrastructure and playable tools

- Frozen reference: exact original executable/source/profiles and SHA256
  manifest under `results/reference-20260921`.
- SGF parser and independent replay: explicit unsupported setup/handicap errors,
  first-variation selection, collections, escapes, passes, colored history,
  strict TT replay or explicit conversion assumption. Not a native Rust
  `loadsgf` implementation. [SGF FF4 reference](https://www.red-bean.com/sgf/sgf4.html).
- Corpus: 40 positions from ten historical 19x19 games, grouped by source hash;
  50 distinct deterministic legal openings. These are development splits,
  with no claim of expert labels or a pristine holdout.
- Group diagnostics: liberties, eye candidates, and bounded capture search.
  A proof checks every legal defense within its bounded tree; missing proof
  returns unknown. This does not establish general life, seki, or dead stones,
  and does not change legality or final scoring.
- Human terminal: play, engine reply, rank, explain, undo, groups, capture,
  validated SGF save/load. Scripted interaction tests pass.
- Controller clocks: absolute/Canadian `time_settings`, `time_left`, conservative
  search allocation, per-color updates and `gp-time-budget`. The controller
  adjudicates timeouts. Undo requires a fresh controller time update.
- Local release bundle: Windows executable, source, tests, docs, profiles,
  compact evidence and checked SHA256 manifest. External neural runtimes and
  weights are not bundled. JSONL wire logs stay in local results.

## Validation and reproducibility

Final implementation checks:

- `cargo fmt` and `cargo clippy --offline --all-targets -- -D warnings` pass.
- `cargo build --offline --release` passes.
- 16 targeted Rust tests pass: clocks (2), neural hooks (5), protocol (4),
  search modes (5).
- All 32 Python tests pass, including independent rules/scoring, SGF, guidance,
  safety diagnostics, and scripted terminal behavior.
- Full native Rust testing remains incomplete: Windows Application Control
  blocked execution of the older core and search-and-scoring test binaries
  with OS error 4551. Earlier default-directory attempts also hit linker
  LNK1104. Policy was not changed or bypassed. Historical 40-test success is
  not a claim that the full current suite passed today.

The arena executable is separately frozen as `goproverbs-arena-v2.exe` with
its source under `source-arena-v2`. The packaged executable additionally has
controller clocks; the arena used no controller clock settings. Per-run
manifests identify exact tested executables. The original run manifests omit
the imported `neural.py` hash; it is preserved in source snapshots, and future
run manifests now include it explicitly.

The final clock-enabled executable also matched the frozen arena executable
on all 94 candidate outputs and four fixed-depth move/score/depth/node checks
(`final-default-equivalence.json`). This verifies default search equivalence
on the sample, not an additional speed improvement. Expired overtime remains
exhausted until the controller supplies a new update.

Recreate the tables without inference:

```powershell
python benchmarks/summarize_roadmap.py results/roadmap-20260921 --output results/roadmap-20260921/summary.json
```

GPU workloads were checked before inference. Ollama was empty; no unrelated
desktop applications were killed. All model processes exited after their runs.
Post-arena GPU memory was about 2.3 GiB with roughly 9.6 GiB free. No commit,
GitHub push, or publication was made in this execution pass.

## Next gates, in priority order

1. Obtain an allowed full Rust test run; preserve the blocked-run diagnosis.
2. Screen NH against HH on 20 new opening pairs at fixed 200 ms. Keep the two
   pilot openings separate. Do not tune on screening outcomes.
3. Compare NH directly against NN and the standalone pretrained reference;
   report complete-round retention, color effects, overshoots and total cost.
4. Batch neural leaf requests or reduce repeated full-history transport, with
   timeout and superko equivalence tests, before increasing NN match volume.
5. Run CPU-small nomination matches and fixed-model budget curves separately.
6. Add reviewed tactical/strategic positions, symmetry tests, and a fresh
   confirmation split. Include ladder breakers, seki, captures, sacrifices,
   false eyes, ko threats and exact endgame examples.
7. Extend shape features only with positive, negative and exception tests;
   promote any weight change only after paired games on separate openings.
8. Validate a finalist on at least 50 fresh pairs and a calibrated opponent
   pool before making a strength/rating claim.
9. Finish native SGF/controller interoperability, then review a versioned
   release for GitHub publication.
