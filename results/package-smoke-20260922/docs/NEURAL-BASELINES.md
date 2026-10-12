# Pretrained neural baselines

The benchmark adapter in `benchmarks/neural.py` adds two independently selectable
KataGo decision rules. It does not change the default goproverbs engine.

- `policy`: select the largest nonnegative entry in KataGo's raw `policy` array.
  Request one visit to retrieve that array, but never use searched moves, values,
  or win rates to select the move. Pass competes normally with board moves.
  Ties use row-major order. This is a policy-only decision, not a claim that the
  KataGo process performs literally no search bookkeeping.
- `search`: use KataGo's recommended move (`moveInfos` entry with `order=0`)
  following neural-guided Monte Carlo search, with the same weights.
- `hybrid`: the existing goproverbs heuristic/scout shortlist and deeper
  alpha-beta verification. No neural network is used by this player yet.

## Installation used for the first pilot

Portable runtime and model live outside the repository:

```text
C:/Users/kevin/ai_bench/katago/opencl-1.18.1/katago.exe
C:/Users/kevin/ai_bench/katago/kata1-b10c128-s919229184-d169515535.txt.gz
```

Runtime: official KataGo 1.18.1 Windows OpenCL, downloaded from its GitHub
release. Archive SHA256:
`1710db1903ab921aa6837a9599c8474f8a59f057650217c5d9bc125ee393a9ff`.
This matches the published asset digest. The small 10-block/128-channel network
is an old 2020 pretrained baseline, deliberately chosen for a lightweight
integration experiment. It is not the latest or strongest KataGo network.
The 14,465,630-byte compressed text network is directly accepted by KataGo.
Its exact SHA256 and the runtime executable hash are in each result manifest.

OpenCL avoids installing a separate CUDA/cuDNN runtime. Local logs confirm
RTX 5070 placement and FP16 storage/tensor cores; this is not an LLM GGUF
quantization. First startup performs GPU tuning. Do not count that startup
as per-move inference speed.

## Reproduce

Choose a new output directory for each command; existing directories are refused.

```powershell
$kata = 'C:/Users/kevin/ai_bench/katago/opencl-1.18.1/katago.exe'
$net = 'C:/Users/kevin/ai_bench/katago/kata1-b10c128-s919229184-d169515535.txt.gz'
python -m unittest discover -s benchmarks -p 'test_*.py'
python benchmarks/neural.py smoke --katago $kata --model $net --output results/neural-smoke-new
python benchmarks/neural.py fixtures --katago $kata --model $net --output results/neural-fixtures-new
python benchmarks/neural.py arena --katago $kata --model $net --time-ms 200 --pairs 1 --komi 7.5 --output results/neural-arena-new
```

Before inference, inspect `nvidia-smi`, `ollama ps`, and other active inference
work. Unload only identified idle models. The harness refuses known lab runner
locks and resident Ollama models; these checks do not detect every possible
external workload. One KataGo worker handles requests serially and exits on
success or failure. Hardware snapshots capture before/load/after VRAM and RAM.

## Match contract

- 19x19, Tromp-Taylor, positional superko, legal multi-stone suicide, no handicap
  bonus, no resignation, two passes end the game. Default arena komi is 7.5.
- Every pairing plays both colors from the same seeded two-corner opening.
  One pair produces six games: policy/hybrid, search/hybrid, search/policy.
- Search time cap defaults to 200 ms for both search engines. goproverbs uses
  depth 12 and 10 million nodes as high secondary limits, beam 12, shortlist 3,
  baseline weights and no tactical extensions. KataGo uses one search thread,
  batch size 1, up to 10 million visits, no wide root noise and one fixed neural
  orientation. Search-tree state is not reused across KataGo queries; neural
  inference cache can be reused. Policy-only uses fewer resources by design.
- These are equal configured search-time caps, not hard wall-clock deadlines.
  Per-decision latency includes protocol and selection overhead and is saved.
  CPU heuristic search and GPU neural inference have different hardware costs.
- Full ordered move history is sent on every game query. Never silently replace
  it with a board snapshot: that would lose ko/superko context.
- The independent Python referee validates every played move. Its board is
  compared with goproverbs after every move; finished raw area scores must match.
  KataGo's predicted score is not used for adjudication. A move-cap game is
  unfinished, never converted into a win based on an intermediate board score.

Development fixtures remain diagnostics, not expert move-strength labels.
Composed shapes are provided to KataGo as setup stones with explicit next
player; the immediate-ko fixture retains its actual placement/capture history.
goproverbs retains its historical fixture setup behavior. Thus fixture inputs
do not have identical neural history features; actual games do retain history.
Small local captures can be less valuable than open corners on a mostly empty
19x19 board. Failure to choose the fixture's local move is not proof of bad Go.

## Saved evidence

Each run includes config, manifest with hashes/settings/version, stderr backend
log, and every JSON request/response in `wire.jsonl`. Arena also writes SGF and
per-move JSONL for each game, plus an incrementally updated `games.json`.
Failures remain recorded; a process exit alone does not establish benchmark
success. `manifest.json` must say `complete` and games must say `finished`.

The next controlled extension is neural move nomination inside our own hybrid
search, retaining our leaf evaluator first. Changing both nomination and leaf
evaluation at once would obscure what helped. A contemporary pretrained network
and more independent openings are separate follow-up variables.

## Primary sources

- [KataGo 1.18.1 release](https://github.com/lightvector/KataGo/releases/tag/v1.18.1)
- [Published network catalog](https://katagotraining.org/networks/)
- [Pinned analysis protocol](https://github.com/lightvector/KataGo/blob/v1.18.1/docs/Analysis_Engine.md)
- [Pinned analysis configuration](https://github.com/lightvector/KataGo/blob/v1.18.1/cpp/configs/analysis_example.cfg)
