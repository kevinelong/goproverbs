# Research workflow and optional neural guidance

The staged plan is [ROADMAP-2026-09-21.md](ROADMAP-2026-09-21.md).
The original source/executable snapshot is in `results/reference-20260921`.
Verify its files against `manifest.json` before using it as a control.

## Terminal play

```powershell
python benchmarks/play.py --size 19 --komi 7.5 --time-ms 1000 --color B
```

A coordinate or `pass` plays a move and receives a CPU hybrid reply. `go` asks
the engine to play the current turn. `undo` returns to the preceding human turn.
`rank` lists preferences; `explain` describes the last generated move. `groups`
shows liberties and eye candidates. `capture A1` runs a bounded capture check.
`save "game.sgf"` refuses overwrites. `load "game.sgf"` validates the whole
supported main line before replacing the game. `board` displays; `quit` exits.
In the release bundle, pass `--exe bin/goproverbs.exe`.

## SGF import boundary

`benchmarks/sgf_io.py` parses collections, property maps, escaped values and
nested variations. Replay selects/reports the first variation, preserving
colored move history and komi. Empty passes and legacy `tt` passes (<=19) work.
Replay rejects setup/handicap/edit properties, rectangles, midgame rule/setup
changes, unsupported games, malformed properties and post-termination moves.
Unknown annotations remain in parsed nodes; this is not a lossless editing UI.
Only UTF-8 is supported, not every historical charset.

The validator's `--assume-tt` flag is an explicit rules-conversion assumption.
The terminal loader requires explicit Tromp-Taylor rules. No setup is silently
represented as ordinary moves or stripped of meaningful ko history.
Source: [SGF FF4](https://www.red-bean.com/sgf/sgf4.html).

## Corpus and openings

```powershell
python benchmarks/corpus.py --input results --output results/my-corpus
```

Produces replayed positions and 50 frozen seeded opening sequences. All
positions from each source game share a split. Historical lab games remain
development data even in development-validation: no expert labels or pristine
holdout. Rejected sources are recorded. Generated openings are varied legal
positions, not professional recommendations or a tournament distribution.

## Four-way ablation

| Code | Extra neural root nominees | Neural verification leaves |
|---|---|---|
| HH | No | No |
| NH | Yes | No |
| HN | No | Yes |
| NN | Yes | Yes |

All modes retain the same all-root heuristic scout and its heuristic/scout/
tactical/pass nominees. First-letter N adds up to three raw-policy nominees.
Probabilities are not added to heuristic scores. Second-letter N uses raw
neural `rawLead`, converting BLACK reporting to the leaf's player perspective.
Exact terminal area scores bypass neural evaluation. Existing path-preference
bonuses remain engineering preferences, not calibrated Go points.

The initial hook could not complete neural depth two at 200 ms. The revision
first completes a neural one-ply round over all nominees. That complete round
survives an interrupted deeper round. Partial, failed, late or nonfinite
evaluation never replaces completed evidence. Reports identify whether the
retained decision used neural leaves; proverb contributions do not explain
the neural score.

`gp-nominees D4,Q16,pass` sets deduplicated hints; `gp-nominees -` clears them.
Illegal hints fail analysis. Hints clear on play, undo and reset.
`gp-neural-port PORT` enables a localhost-only evaluator; zero disables it.
Guided analysis requires hybrid mode. The Python broker shares one serial
KataGo process, sends full SGF history, and requests one-visit raw values.

The move budget includes root inference and protocol setup. Rust receives the
remaining time, uses socket timeouts and completed-round fallback. Actual wall
time can overshoot due to cooperative checks and OS scheduling. Neural caches
are cleared before probes/games, then reused within games. No weights learn
across games.

```powershell
$kata = 'C:/Users/kevin/ai_bench/katago/opencl-1.18.1/katago.exe'
$net = 'C:/Users/kevin/ai_bench/katago/kata1-b10c128-s919229184-d169515535.txt.gz'
python benchmarks/roadmap.py probe --katago $kata --model $net --output results/probe-new
python benchmarks/roadmap.py arena --katago $kata --model $net --pairs 2 --output results/arena-new
python benchmarks/paired_summary.py results/arena-new/games.json --output results/arena-new/paired-summary.json
```

Use `--time-ms 1000` or `--modes HH NH` to vary budget or isolate nomination.
Every requested non-HH mode plays HH with colors swapped. An output-directory
`STOP` file ends gracefully and marks the current game unfinished. Outputs are
never reused. Inspect GPU processes, runner locks and Ollama before inference;
release models afterward, including failures.

Pair summaries use a conservative Hoeffding bounded-mean interval, assuming
independent opening pairs. Incomplete pairs are excluded and counted. No Elo
claim follows. Source: [KataGo 1.18.1 protocol](https://github.com/lightvector/KataGo/blob/v1.18.1/docs/Analysis_Engine.md).

## Proverb and group-safety work

[PROVERB-CATALOG.json](PROVERB-CATALOG.json) records interpretations, sources,
exceptions and test gaps. `benchmarks/ablate.py` creates single-feature removals;
`--evaluate` runs development fixtures. Label acceptance never promotes weights.

Group diagnostics say `unknown` rather than infer life from eye counts. The
capture reader restricts attack choices but checks all legal defenses before
reporting capture within its horizon. A missing proof does not establish life.
It retains superko history and stops at node/horizon caps. This optional
diagnostic is not integrated into scoring. General ladders, seki and dead-stone
adjudication remain open work.

## Local release

GTP `time_settings MAIN_SECONDS PERIOD_SECONDS PERIOD_STONES` and
`time_left COLOR SECONDS STONES` support absolute and Canadian time controls.
Positive period time with zero stones means unlimited time. Main time is
allocated over a conservative 30-move horizon; period time is divided by the
remaining stones, with a 10 ms reserve and the configured search cap.
`gp-time-budget COLOR` reports that cap. Only `genmove` charges the local clock;
`gp-search` is diagnostic analysis at its configured budget. Controllers should
send fresh `time_left` after undo or external adjustments and adjudicate
timeouts themselves. A zero budget still returns a legal fallback; it is not
a guarantee of responding in zero wall time. See the
[GTP specification](https://www.lysator.liu.se/~gunnar/gtp/gtp2-spec-draft2/gtp2-spec.html).

```powershell
python scripts/package_release.py --output dist/goproverbs-research.zip
```

Includes sources, tests, docs, profiles, Windows executable and compact evidence,
with verified hashes. Models/runtimes remain external; full JSONL transcripts
remain in local results. Packaging does not publish. Native Rust `loadsgf`,
arbitrary SGF setup edits and signed distribution remain open.
