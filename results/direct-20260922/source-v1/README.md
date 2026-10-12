# goproverbs

An experimental Rust Go player with weighted, explainable heuristics, bounded
search, an ASCII board, GTP v2, and SGF export. The standalone engine runs on
the CPU with no model server and no external Rust dependencies. Optional
research adapters add pretrained KataGo guidance on CPU or GPU.

## Start here

Latest: [nine-part plan](docs/ROADMAP-2026-09-21.md),
[executed results and remaining gates](docs/ROADMAP-RESULTS-2026-09-21.md),
and [terminal/neural research workflow](docs/RESEARCH-WORKFLOW.md).

September 22: [20-pair NH screening](docs/NH-SCREENING-2026-09-22.md) completed
with 36/40 wins over HH at 200 ms on unused openings. All games validated;
this is screening evidence, not an Elo rating or a default promotion.

```powershell
cd C:\Users\kevin\local-llm-lab\goproverbs
cargo build --offline --release
.\target\release\goproverbs.exe --size 19 --suggest D4 Q16
.\target\release\goproverbs.exe --size 9 --rank C3 G7
.\target\release\goproverbs.exe --gtp --profile profiles/baseline.weights
```

Use the baseline profile with search. The separately saved tuned profile is an
experiment: it has not demonstrated better playing strength. See the
[executed results](docs/RESEARCH-2026-09-20.md).

## What the player does

1. Generate legal moves. Game rules are mandatory and never receive weights.
2. Rank moves using capture, rescue, shape, and opening features.
3. Search alternating moves with iterative deepening and alpha-beta pruning.
4. Explain the chosen line, leaf evaluation, and weighted move preferences.

Proverbs are preferences with exceptions. Search may override a proverb when
its evaluated continuation is better. Its scores are arbitrary evaluation units,
not win probabilities, ratings, or predicted final margins.

The default budget is 1,000 ms, 20,000 tree positions, depth 4, and 12 quiet
candidates per position. Immediate captures, rescues, new ataris, and pass are
also retained. The beam makes search selective; this is not exhaustive reading.
Only a completed iteration supplies the result. An interrupted first iteration
falls back to a legal heuristic choice, or the first legal point if even ranking
cannot finish. Candidate simulations are not counted as tree nodes. Time checks
are cooperative, so the wall-clock budget is not a hard real-time guarantee.

```powershell
.\target\release\goproverbs.exe --size 9 --suggest --time-ms 500 --nodes 5000 --depth 3 --beam 12 C3 G7
.\target\release\goproverbs.exe --profile profiles/modern.weights --suggest D4
.\target\release\goproverbs.exe --profile profiles/baseline.weights --weight save_atari=12 --write-profile profiles/my.weights
```

## Coordinates, rules, and scoring

- Board sizes 2..25; default 19. Conventional alternatives include 9 and 13.
- GTP coordinates skip I; A1 is bottom left. CLI moves alternate from Black.
- ASCII: X is Black, O is White, dots are empty, plus signs mark star points.
- CLI and the executable's GTP mode default to **Tromp-Taylor**: positional
  superko, legal multi-stone suicide, area scoring after two passes.
- Komi defaults to 6.5; change it with `--komi`. Early experiments used 0.5;
  the September 21 roadmap comparisons use 7.5 on 19x19.
- Capture dead stones before passing: scoring counts the board as it stands.
  There is no automatic dead-stone adjudication or Japanese territory scoring.
- `--rules simple` preserves the earlier simple-ko/no-suicide model, which
  pauses after two passes without declaring a score. For compatibility,
  `Game::new`, `Game::default`, and the library's default GTP engine still use it.
- SGF FF[4] main-line export includes rules and a result when available.
  The Python terminal supports validated main-line import; native Rust import
  and setup nodes remain unsupported. See the research workflow for limits.

```powershell
.\target\release\goproverbs.exe --size 9 C3 G7 C7 G3 E5
.\target\release\goproverbs.exe --sgf D4 Q16 pass
```

## Connect a Go controller

Launch `target/release/goproverbs.exe --gtp` from a GTP-capable program.
Standard input/output contain only GTP responses. Core commands, `showboard`,
`undo`, and `final_score` are implemented. `final_score` requires a finished
Tromp-Taylor game. GTP accepts explicit colors and same-color setup sequences;
Tromp-Taylor games cannot resume after finishing unless undone or cleared.
The legacy simple policy permits resuming after passes.

| Private command | Purpose |
| --- | --- |
| `gp-search COLOR` | Search and explain without changing the game |
| `gp-last-search` | Explain the last generated move |
| `gp-limits MS NODES DEPTH BEAM` | Set search budgets |
| `gp-tactical N` | Set optional extra tactical plies (0..4, default 0) |
| `gp-mode MODE` / `gp-shortlist N` | Select search algorithm and hybrid shortlist size |
| `gp-explain COLOR VERTEX` | Explain immediate move preferences |
| `gp-candidates COLOR` | List legal candidates and raw move features |
| `gp-weights` / `gp-weight NAME VALUE` | Inspect or change weights |
| `gp-load-weights PATH` / `gp-save-weights PATH` | Persist a profile |
| `gp-sgf` | Export the current main line |

GTP profile paths cannot contain whitespace or `#`; CLI `--profile` supports
quoted paths with spaces. Profiles use one `name=value` per line and allow `#`
comments. Missing features inherit defaults; unknown, duplicate, nonfinite,
or out-of-range values fail. CLI profile loads and overrides apply in argument
order. Profile saves overwrite the named file.

GTP `time_settings` and `time_left` support absolute/Canadian time allocation;
the controller remains authoritative for timeouts. `gp-time-budget COLOR`
reports the current search cap. Handicap commands and native `loadsgf` remain
unsupported. Match the controller's rules to the selected policy. KataGo has
been tested through the research harness; external GUI integration remains open.

## Reproduce the experiments

Python 3, standard library only:

```powershell
python -m unittest discover -s benchmarks -p test_lab.py -v
python benchmarks/lab.py tune --output profiles/my-tuned.weights
python benchmarks/lab.py evaluate --output results/my-fixtures.json --nodes 5000 --depth 3 --beam 12
python benchmarks/lab.py arena --output results/my-arena/report.json --pairs 3 --size 9 --nodes 2000 --depth 3 --beam 12
```

Tuning uses only six training fixtures and saves an independent profile plus
provenance. The five other cases are development regression checks, not an
untouched expert test set. The arena pairs colors on seeded openings, compares
search against the same profile's one-move policy, checks every move and final
score with an independent Python referee, and saves SGFs and decision traces.
These matches isolate search; they do not compare baseline versus tuned search.

## Development

The [WSL build](docs/WSL-BUILD.md) is verified: Linux release build, all 47 current
Rust tests, and a command-line smoke test passed on September 21. The separate
[performance comparison](docs/WSL-PERFORMANCE-2026-09-21.md) uses a frozen source
snapshot and matched compilers. From PowerShell:

```powershell
wsl -d Ubuntu -- bash /mnt/c/Users/kevin/local-llm-lab/goproverbs/scripts/wsl.sh build
wsl -d Ubuntu -- bash /mnt/c/Users/kevin/local-llm-lab/goproverbs/scripts/wsl.sh test
wsl -d Ubuntu -- bash /mnt/c/Users/kevin/local-llm-lab/goproverbs/scripts/wsl.sh run --size 9 --suggest D4
```

For builds affected by Smart App Control, a [build/sign/run workflow](docs/WINDOWS-SIGNING.md)
is prepared in `scripts/Invoke-SignedCargo.ps1`. Trusted signing enrollment is
still required; no executable has been signed yet.

```powershell
cargo fmt --check
cargo test --offline -j 1
cargo clippy --offline --all-targets -- -D warnings
cargo build --offline --release
```

Windows requires MSVC C++ Build Tools and a Windows SDK. Compilation, Clippy,
release integration tests, and matches succeeded locally. The earlier Rust test
execution block from Windows Application Control did not recur on the new build;
all 40 Rust tests passed in the latest serialized build. See the follow-up report for the
exact validation boundary. Earlier test results remain in
[initial validation](docs/VALIDATION.md).

Read the [heuristic catalog](docs/HEURISTICS.md),
[standards decisions](docs/STANDARDS.md), and
[search/tuning results and limitations](docs/RESEARCH-2026-09-20.md).

## Tactical research follow-up

Optional bounded tactical extensions, direct search-versus-search matches,
and rotated/reflected fixture evaluation are available. Defaults remain the
baseline weights with extensions disabled. See the
[controls and methodology](docs/TACTICAL-SEARCH.md) and
[follow-up results](docs/TACTICAL-RESULTS-2026-09-20.md).


## Hybrid search and standard-board strategy

19x19 is now the explicit target for strategic proverb evaluation. The three
opening proxies (`empty_corner`, `side_development`, `early_33`) activate only
on 19x19. Local tactics remain available on every supported size. Historical
small-board match results do not establish standard-board strategic strength.

Try `--search hybrid` to let heuristic and shallow-search nominees undergo
deeper verification before the final decision. `--search full` and
`--search minimax` provide full-width controls. The default remains `selective`.
Read the [algorithm and board-size decisions](docs/HYBRID-SEARCH.md) and
[19x19 results](docs/HYBRID-RESULTS-2026-09-20.md).

## Pretrained neural opponents

`benchmarks/neural.py` compares raw pretrained KataGo policy, the same network
with KataGo search, and our existing heuristic hybrid on 19x19. It records full
protocol transcripts, paired games, independent legality/scoring checks, and
actual move times. See [setup and methodology](docs/NEURAL-BASELINES.md).
The [first six-game pilot](docs/NEURAL-RESULTS-2026-09-20.md) compares the same
small pretrained network with and without search against our heuristic hybrid.
The neural backend is optional; ordinary goproverbs remains a standalone CPU
engine with its existing defaults.

## Research roadmap and terminal play

The [nine-part plan](docs/ROADMAP-2026-09-21.md) tracks the next research phase.
See [workflow and commands](docs/RESEARCH-WORKFLOW.md) for SGF replay, human
terminal play, neural nomination/evaluation ablations, group diagnostics and
local release packaging. Start a human game with:

```powershell
python benchmarks/play.py --size 19 --komi 7.5 --color B
```

