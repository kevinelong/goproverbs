# Standards and design decisions

Updated 2026-09-20. Standards guide interchange and playing rules; the Rust
memory layout is an implementation choice.

## GTP v2

The [GTP v2 draft specification](https://www.lysator.liu.se/~gunnar/gtp/gtp2-spec-draft2.pdf)
defines the command/response interface. Required core commands are implemented,
with IDs, comments, blank-line framing, explicit colors, and discovery through
`list_commands` / `known_command`. Extensions use the `gp-` prefix.

Coordinates run left to right, skipping I, and bottom to top. We support square
boards 2..25. GTP does not prescribe our diagram glyphs and does not negotiate
the entire ruleset. Controllers must select compatible rules. Handicap setup,
SGF loading, and controller time-management commands remain unimplemented.
The private `gp-limits` command supplies per-move search budgets.

## ASCII

The [GNU Go manual's GTP example](https://www.gnu.org/s/gnugo/gnugo_19.html)
uses X for Black, O for White, dots for empty points, and plus signs for stars.
We follow that convention without color escapes or Unicode. Five stars on 9x9
and nine on 13x13/19x19 are display choices; other sizes have none.

## SGF FF[4]

The [SGF specification](https://www.red-bean.com/sgf/sgf4.html),
[property definitions](https://www.red-bean.com/sgf/properties.html), and
[Go-specific definitions](https://www.red-bean.com/sgf/go.html) guide export.
Records include FF[4], GM[1], CA[UTF-8], application/version, size, komi, B/W
moves, and results when known. Tromp-Taylor uses RU[Tromp-Taylor]; the legacy
partial policy is described in a comment instead of claiming national rules.

SGF coordinates start at the upper left. GTP A19 is SGF aa on a 19x19 board.
Pass exports as an empty value. Rectangles, setup nodes, annotations, general
SGF import, and variation trees are outside the current main-line exporter.

## Tromp-Taylor rules

John Tromp's [Logical Rules of Go](https://tromp.github.io/go.html) provide a
compact scoring policy suitable for automated experiments. The implementation:

- Clears opposing groups without liberties before clearing a suicidal own group.
- Rejects placements repeating any previous board coloring (positional superko).
- Exempts pass from repetition checking; two alternating passes finish the game.
- Counts stones and empty regions reaching only one color; other empty points
  are neutral. White receives the configured komi.
- Scores the actual final board; dead stones must be captured before passing.

Exact board comparisons avoid hash-collision concerns; history uses shared,
immutable boards. The conventional 19x19 rules are generalized to supported
board sizes for experiments. Captured-stone totals are informational, not part
of area scoring. Resignation is an application-level termination option.

The CLI and executable GTP mode default to this policy. Explicit-color GTP
setup is a controller convenience; ordinary game play alternates colors.

## Legacy policy

`SimpleKoNoSuicide` remains available with `--rules simple` and as the library's
historical default. It pauses after two passes and supplies no final score.
The [BGA rules](https://www.britgo.org/files/rules/rulesofplayfull.pdf) were the
initial reference for groups, liberties, and capture order. The legacy policy
does not implement BGA/AGA scoring, pass stones, or superko and is not labeled
as compliant with those complete rulesets.
