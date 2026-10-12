# Initial validation

Executed locally on Windows x64 on 2026-09-20.

- Rust 1.96.0, Cargo 1.96.0, stable MSVC toolchain.
- Microsoft Visual Studio Build Tools 2022 (17.14.41) installed with the C++
  workload and Windows SDK after the initial build lacked `link.exe`.
- `cargo test --offline`: 23 integration tests passed (18 core/heuristic,
  four protocol, one CLI); no failures.
- `cargo fmt --check`: passed.
- `cargo clippy --offline --all-targets -- -D warnings`: passed.
- `cargo build --offline --release`: passed.
- Release CLI: rendered a 9x9 board with C3, G7, C7, G3, E5 in the correct
  orientation, alternating stone colors, and White to play.
- Release GTP: checked protocol version, explicit-color plays, explanation,
  move generation, board display, and quit through a PowerShell pipe.

In the GTP tactical fixture, Black B2 had one liberty after White A2, C2, B1.
The engine selected B3 and reported:

```text
B3: 2.510 (base=0.010)
  save_atari: 0.250 * 10.000 = +2.500
```

Tests include every coordinate round trip on supported board sizes, ASCII
orientation, capture ordering, whole-string capture, suicide/ko rollback,
passes, resignation, SGF coordinate conventions, GTP response framing, and
weight effects. Eye-shape tests distinguish a corner eye from a false eye.
Short self-play checks legality only, not successful game completion or strength.

No external GUI, tournament controller, rating estimate, full-game scoring,
search, independent SGF parser, or comparative playing-strength benchmark was
tested. All executed program tests used CPU only and required no inference server.
