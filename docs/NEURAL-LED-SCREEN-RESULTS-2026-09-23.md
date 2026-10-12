# Neural-led paired screens: findings and stopping gates

The neural-only screen is complete. The combined screen remains held after
revealing an endgame-completion problem. No default promotion or larger
confirmation was launched. All runs and failures were preserved; no engine,
model or run lock remains active.

## Completed neural-only screen

screen-v1:40/40 live White controls passed, followed by20 fresh opening pairs at
200ms per decision. Neural-only won24/40 against raw policy:12/20 as Black and
12/20 as White, no draws or unfinished games. Complete-pair mean score0.60;
conservative95% Hoeffding interval[0.2963,0.9037]. This does not establish an
advantage and does not meet the predefined larger-confirmation gate.

6,533 neural decisions included9 deadline fallbacks; maximum209.33ms. These
exceeded the nominal200ms allowance but passed the predefined scheduling
tolerance and per-pair retention gates. Policy had6,529 decisions, no fallbacks,
maximum85.20ms. Both roles used the same total allowance, model and full history.

## Performance failure and correction

The first combined-vs-neural game in v1 stopped at223.45ms, above the220ms hard
gate. It produced no complete combined pair and no awarded win/loss. Trace:
166.57ms nomination, including only18.04ms Rust proposal work. Repeated deepcopy
of immutable historical board tuples was unnecessary. A20-repetition isolated
CPU diagnostic measured14.63ms median for old child copy/play versus0.022ms for
container copies, preserving all292 seen positions at the failed291-move root.

An Astra coding agent changed only the child clone and its tests, under root
supervision. The child now independently copies the mutable board list and
seen-position set; immutable tuples are shared. Every historical position is
retained. Move selection and evaluation stayed unchanged. All80 Python tests
passed, including26 controller tests for long-history equivalence, sibling/root
isolation, capture, superko through passes, and terminal scoring.

screen-v2 failed at startup because a relative config path was interpreted under
the experiment working directory. Zero decisions ran; cleanup was verified.
The launcher now resolves the output path absolutely. This failure is preserved.

## Revised combined screen and endgame failure

screen-v3: separately frozen optimized controller,32 frozen controls passed,
then45/45 live White checks passed. These include all five variants at the exact
failed v1 root. The combined variant finished that comparison in73.25ms.

Both match roles used the optimized controller on new openings excluding all
earlier planned histories. Two opening pairs completed:combined2/4, winning
both White games and losing both Black games. The third pair's first game
reached the722-played-move cap and was recorded unfinished. Complete-pair
interval[0,1]; no strength conclusion. The remaining35 games were not run.

Across all five attempted games each role made1,163 decisions. Combined median
56.48ms, maximum153.06ms; neural median18.94ms, maximum98.26ms. All2,326 decisions
completed their neural comparison, with zero deadline fallbacks or overshoots.
Combined selected specialist-only moves96 times. That count is not a causal
measure of helpful proposals. Do not pool these timings or outcomes with v1.

The unfinished game exposes a winrate-objective problem. Combined, playing
Black, passed163 times. Neural-only, playing White, never passed despite its
root policy recommending pass180 times. In the final100 White decisions it
never accepted a pass; Black passed97 times in its own final100 decisions.
After Black passed, an exact terminal loss had win probability0, while further
play received small positive estimates (about0.0002). The winrate-first selector
therefore preferred continuation to accepting the known loss. Last decision:
pass would end at-21.5 points with exact win probability0; Q6 was estimated at
0.0002309 win probability and-43.8 points. Full-history superko remained enforced.

This is not fixed by widening the clock, raising the move cap or counting the
unfinished game as a loss. The frozen completion gate stopped the experiment.

## Next implementation gate

Specify an endgame/pass policy before another strength run. A concrete candidate
is to retain the raw-policy pass when the opponent has just passed and the root
neural policy also recommends pass. This explicitly delegates agreement to end
the game to policy instead of allowing tiny positive value estimates to reject
a known loss forever. It can also miss a useful continuation, so it must be
labeled a decision-rule change, tested for both colors, and compared separately.
No such rule has been implemented or silently applied to these results.

First add deterministic losing/winning/drawn two-pass and premature-pass controls,
then replay the saved failure as development data. Require completed games in a
small endgame validation set before allocating another20 fresh opening pairs.
Reconfirm neural versus policy as well if the shared decision rule changes.
Full KataGo comparison and larger confirmation remain held.

## Artifacts

- results/neural-led-20260923/screen-v1/:complete neural-policy screen and first
  combined timing failure; frozen source/protocol,40 White controls, games,
  full decision/transport traces, SGFs, hashes and cleanup status.
- results/neural-led-20260923/copy-diagnosis.json and
  benchmarks/diagnose_neural_led_copy.py:reproducible CPU copy diagnostic.
- results/neural-led-20260923/screen-v2/:preserved zero-decision startup failure.
- results/neural-led-20260923/screen-v3/:45 White controls,4 complete games,
  1 unfinished game, all traces and verified cleanup.
- benchmarks/review_neural_led_screen.py:reproducible per-role/color aggregation;
  each run's REVIEW.md/REVIEW.json separates complete pairs from failures.

The earlier historical NN retention gate, default Rust engine and release ZIPs
remain unchanged. CPU packing remains separately memory-held.
