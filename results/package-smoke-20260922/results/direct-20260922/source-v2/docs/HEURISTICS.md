# A proverb-driven Go player

Initial research: 2026-09-17; implementation update: 2026-09-20. This catalog is
not a complete encoding of the Go proverb literature.

## Method

1. Generate legal candidates with the game model. Legality never has a weight.
2. Measure bounded features in the current and resulting position.
3. Calculate `score = 0.01 + sum(weight * feature)` for placements; pass has 0.
4. Use the score to order bounded search; --rank exposes the immediate policy. Ties use deterministic row-major order.
5. Retain every nonzero feature's value, weight, and contribution for explanation.

Weights are engineering starting values, not learned values or source claims.
All immediate move-feature values lie in [0,1]. Search evaluation terms below use different scales. Tactical stone counts saturate at four,
which is intentionally simple and can undervalue large groups. The pass policy
is only a fallback, not endgame judgment. Rules are soft preferences: even eye
filling and self-atari can be correct in tactical sequences.

## Implemented feature catalog

| ID | Initial weight | Interpretation and measurable trigger | Source and caveat |
| --- | ---: | --- | --- |
| `capture` | 8 | Captured stones / 4, capped at 1 | [GNU Go local features][gnu]. Material alone misses sacrifice and snapback. |
| `save_atari` | 10 | Own stones in one-liberty groups that gain at least two liberties after the move, / 4, capped at 1 | [Urgency principle][urgent]. A proxy for urgent defense, not proof of life or ladder escape. |
| `self_atari` | -12 | New group has one liberty and the move captures nothing | [GNU Go local features][gnu]. Sacrifices can be useful; capturing moves are exempt in this baseline. |
| `connect` | 1.5 | Distinct friendly groups joined by orthogonal contact, minus one, / 3, capped at 1 | [Shape discussion][shape]. Our deliberately crude connection proxy; redundant or heavy connections can be bad. |
| `fill_eye` | -15 | Orthogonal neighbors are friendly; at least three interior diagonals or all edge diagonals are friendly | [GNU Go eye avoidance][gnu]. A local shape check, not proof of two eyes or seki. |
| `empty_corner` | 2 | Opening move at a 3-3, 3-4, 4-3, or 4-4 point in an empty 5x5 corner | [Opening principles][opening]. Equal preference among these points; no joseki reading. |
| `side_development` | 0.5 | Opening third/fourth-line move outside those corner points, with no stone within Manhattan distance two | [Opening principles][opening]. Spacing proxy only, not a territorial estimate. |
| `early_33` | 0 | 3-3 invasion under an opponent's 4-4 stone, with no other stone in the surrounding radius-three square | [AlphaGo innovations][modern]. Experimental opt-in detector; it cannot evaluate the follow-up sequence. |

Opening features now apply only on 19x19 while fewer than one quarter of
intersections are occupied. This threshold and the spatial gates are our design
choices. Occupied corners disable the empty-corner reward. Adjacent connection
groups and rescued stones are counted once. Feature overlap still exists;
ablation testing must check whether several terms reward the same benefit.

## Classic source lineage and provenance

The research points to several collections, not one machine-readable canonical
rule list. Milton Bradley's [author introduction][bradley] traces the lineage
through Kensaku Segoe's *Go Proverbs Illustrated*, David Mitchell's *Go Proverbs*,
and the Nihon Ki-in handbook. These are targets for a sourced catalog; their full
contents have not been ingested or claimed as implemented here.

John Power's [author announcement of Essential Go Proverbs][power] offers a
more recent collection. The British Go Association's published teaching articles
provide the directly inspected classical guidance used above.

Each future entry should record an exact bibliographic location, a short
paraphrase, applicability conditions, counterexamples, feature definition,
normalization, weight, and test positions. Do not label our numerical proxies
as literal historical teachings or claim original authorship without evidence.

## Modern guidance and conflicting advice

[DeepMind's account][modern] describes early 3-3 invasions and cases where low
second-line moves worked for whole-board reasons. Therefore early invasions must
remain candidates and low-line moves must not be made illegal by a proverb.
Our early-3-3 feature starts at zero because detecting the shape alone is not
enough to establish that the invasion is good. Its presence can be explained
and its weight enabled for controlled experiments.

The [BGA shape article][shape] also illustrates how a seemingly obvious defensive
connection can be inefficient. A [published professional-game commentary][hane]
gives a case where hane is unsuitable because of the following cuts. These are
reasons to attach preconditions and tactical verification to future rules.

## Next features: researched candidates, not implemented

| Candidate | Required work before enabling |
| --- | --- |
| Hane at the head of two stones | Rotated/reflected patterns plus cut and liberty checks; [BGA example][two] |
| Respond to peeps; maintain useful connections | Distinguish real cutting threats, bamboo joints, and redundant defense; [shape][shape] |
| Extension distance from a wall | Wall strength, available space, weak groups, and invasion tests; [shape][shape] |
| Cut a knight's move at its waist | Pattern recognition and sacrifice/ladder reading; [professional example][knight] |
| Use thickness to attack | Reliable strength and influence estimates; [Bradley sample][bradley] |
| Urgent attacks before territorial expansion | Threat severity, whether a response is forced, and whole-board alternatives; [urgency][urgent] |

## Evaluation plan

First use handcrafted tactical fixtures plus rotated/reflected counterparts.
For each rule include a positive case, a non-applicable case, and a known
exception. Then use held-out SGF positions and paired-color matches, reporting
illegal moves, score, match results, thinking time, and per-rule ablations.
Split by game/source to avoid testing on training examples. Tune bounded weights
on a training set and freeze them before evaluation. A small development-fixture tuner now implements this workflow; its profile is experimental.

Shallow tactical search is now implemented. Continue validating the
weighted move preferences and separate leaf evaluator. A stronger GTP engine
can provide comparison analysis, but its recommendations should remain separate
from our human-readable rules. No competitive strength has been measured yet.

[gnu]: https://www.gnu.org/s/gnugo/gnugo_14.html
[urgent]: https://www.britgo.org/files/bgj/bgj180log.pdf
[opening]: https://www.britgo.org/files/bgj/bgj187loc.pdf
[shape]: https://www.britgo.org/bgj/06329.html
[modern]: https://deepmind.google/blog/innovations-of-alphago/
[bradley]: https://go.arkian.net/NewProverbsSample.html
[power]: https://www.usgo.org/content.aspx?club_id=454497&item_id=88575&page_id=5
[hane]: https://www.britgo.org/bgj/01306.html
[two]: https://www.britgo.org/bgj/06514.html
[knight]: https://www.britgo.org/bgj/01306.html

## Implemented search and profiles (2026-09-20)

Additional move features: `atari=2` counts newly threatened enemy stones / 4,
capped at one; `cut_pressure=0` counts adjacent independent enemy groups minus
one / 3, capped at one. The latter is disabled by default because adjacency
alone does not establish a useful cut. Neither claims to encode a sourced
classical proverb faithfully.

The separate leaf evaluator uses signed own-minus-opponent features:

| Feature | Baseline weight | Definition |
| --- | ---: | --- |
| `stone_balance` | 1 | Stones on the board |
| `atari_risk` | -1.5 | Stones in groups with exactly one liberty |
| `liberty_balance` | 0.1 | Sum of each group's liberties, capped at six per group |
| `influence_balance` | 0.3 | Empty points closer to one color, weighted by inverse nearest distance within four steps |

Komi is also included. A terminal Tromp-Taylor leaf uses the actual area margin
instead. These are uncalibrated positional proxies; influence is not territory,
and atari does not prove capture. In particular, the atari penalty can overvalue
leaving an opponent's threatened group on the board. This is a target for future
leaf-evaluation and tactical-extension experiments.

Selective negamax searches alternating plies, with iterative deepening,
alpha-beta pruning, and time/node limits. Quiet beam pruning retains all
immediate captures, rescues, new ataris, and pass. Each edge adds
`0.15 * clamp(move_preference, -20, 20)` from the mover's perspective.
The displayed line, signed leaf terms, and alternating edge-preference sum
account for the reported search score. This favors explainability but is not
an exact minimax solution of Go or a calibrated score predictor.

`profiles/baseline.weights` reproduces defaults. `modern.weights` enables a
small early-3-3 preference (0.5) as an unvalidated experiment. `tuned.weights`
is produced by bounded coordinate descent on six training cases; it changes
save_atari to 14.25, empty_corner to 3, and side_development to 0. Search leaf
weights are not tuned. Missing profile entries inherit defaults. Profiles are
loaded explicitly and tuning does not change the engine defaults.

See [executed research](RESEARCH-2026-09-20.md) for the mixed fixture results,
paired-color match evidence, independent referee, and remaining limitations.

## Board scope and hybrid verification

The latest scope correction restricts empty_corner, side_development, and
early_33 to 19x19. Their previous activation on 9x9/13x13/25x25 was an unvalidated
transfer. Other local feature values remain measurable across board sizes,
but their relative weights and full-position usefulness are not thereby proven
portable. Small-board learned profiles remain experimental.

The optional hybrid mode nominates moves by both heuristic and shallow-search
rankings, then uses completed deeper scores to choose among the nominees.
See [hybrid search and board scope](HYBRID-SEARCH.md).
