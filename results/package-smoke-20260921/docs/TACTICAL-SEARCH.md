# Tactical leaf extensions

The experimental `--tactical-plies N` option permits 0..4 extra alternating
moves after the normal search depth. Zero is the default and preserves the
previous search policy. GTP exposes `gp-tactical N`; `gp-limits` keeps that
setting while changing the other budgets.

## Trigger and alternatives

An extension occurs only if a nonterminal leaf contains at least one group
with exactly one liberty (atari). Its alternatives are legal immediate
captures, rescues, new ataris, pass, and the highest-ranked non-tactical move.
That last alternative allows playing elsewhere instead of assuming every
threat must be answered. Pass is an actual game move, so it participates in
turn order and the two-pass termination rule.

The allowance decreases on each extra ply. It is not reset by a new threat.
All extra positions consume the same node and wall-clock budgets as ordinary
search. Iterative-deepening results are still accepted only after every root
candidate in that iteration has completed.

The reported `depth` counts normal plies. The displayed `pv` can be up to
`depth + tactical_plies` moves long. `tactical_nodes` counts extended internal
nodes across all iterations, including work discarded when a later iteration
runs out of budget. It is a subset of `nodes`, not an additional allowance.
The leaf features and alternating edge preferences still account for the
reported score.

This is selective tactical reading. It does not prove a group alive or dead,
and a leaf can still be unstable when its allowance ends. Only one quiet
alternative is retained during extensions, so a useful sacrifice or remote
move can be missed. At small budgets, extension work can reduce the completed
normal depth. More search is not automatically stronger search.

## Experiments

```powershell
.\target\release\goproverbs.exe --size 9 --suggest --tactical-plies 2 C3 G7
python benchmarks/lab.py evaluate --tactical 2 --output results/my-extensions.json --nodes 5000 --depth 3 --beam 12
python benchmarks/compare.py --tactical-a 2 --output results/my-comparison/report.json --pairs 6
python benchmarks/compare.py --profile-a profiles/tuned.weights --output results/my-tuned-comparison/report.json --pairs 6
```

`compare.py` uses two synchronized GTP processes. Both search with equal
node/time/depth/beam limits. A and B may have different profiles and extension
allowances. Each seeded two-move opening is played with colors swapped. The
independent referee checks both boards after every generated move and both
final scores. SGFs and traces are saved alongside the report. Existing report
paths are refused to prevent accidental replacement of completed experiments.

`profiles/material-risk.weights` changes only atari_risk from -1.5 to -0.5;
other weights inherit defaults. It is a separate experiment, not a new default.
Executable hashes in each report identify the inherited defaults.

For orientation checks:

```powershell
python benchmarks/symmetry.py --output results/my-symmetries.json
python benchmarks/lab.py evaluate --fixtures results/my-symmetries.json --output results/my-symmetry-evaluation.json --nodes 5000 --depth 3 --beam 12
```

Each original case generates eight rotations/reflections. These are correlated
views of the same eleven development cases, not 88 independent test positions.
Labels are transformed with the moves. Row-major tie breaking and quiet-beam
selection can make search prefer different symmetry-equivalent moves.
