# WSL build verified September 21, 2026

The shared Windows project builds and runs in Ubuntu 24.04.4 under WSL 2.
Installed the official minimal rustup toolchain for Linux user `kevin`:
rustc 1.98.1 (48a229cea 2026-09-01), cargo 1.98.1 (797e8a9bc 2026-08-05).
The existing C compiler is Ubuntu GCC 13.3.0. No signing service is needed for
this Linux build, and no Windows security setting was changed.

From PowerShell, these commands work from any directory:

```powershell
wsl -d Ubuntu -- bash /mnt/c/Users/kevin/local-llm-lab/goproverbs/scripts/wsl.sh build
wsl -d Ubuntu -- bash /mnt/c/Users/kevin/local-llm-lab/goproverbs/scripts/wsl.sh test
wsl -d Ubuntu -- bash /mnt/c/Users/kevin/local-llm-lab/goproverbs/scripts/wsl.sh run --size 9 --suggest D4
```

Source files remain in the shared repository. Linux artifacts are stored in
`/home/kevin/.cache/goproverbs/target`, separate from Windows build output.
The release executable is `/home/kevin/.cache/goproverbs/target/release/goproverbs`.
The helper loads `~/.cargo/env`; rustup did not modify shell startup files.
Builds use the lockfile and offline mode. `GOPROVERBS_TARGET_DIR` can override
the Linux target directory if needed.

## Initial executed validation

- Release build succeeded; ELF x86-64 GNU/Linux executable confirmed.
- `cargo test` passed all 40 integration tests: CLI 1, core 18, protocol 4,
  search/scoring 12, search modes 5. Unit/doc-test targets contained zero tests.
- Release smoke test with a 9x9 board, D4 played, and a bounded depth-2 search
  exited successfully, rendered the board, and suggested F9 with line F9 G9.
- Release binary SHA256:
  `a12c253ccfcbb1c9f02e3a29c44e36b800b267ae3655ea911d3cef3623eaea43`.

This validates the core Linux app and its Rust suite. Windows-only execution and
the optional external KataGo backend were not part of this build check. Existing
native Windows builds and the prepared signing workflow remain available.

Later the same day, the expanded working tree rebuilt successfully and passed
47 Rust tests, including new clock and neural-hook checks. The reusable `run`
command also passed its smoke test. The initial binary hash above describes the
earlier source. See the [separate matched performance comparison](WSL-PERFORMANCE-2026-09-21.md)
for Windows versus Linux timings on a frozen 44-test snapshot.
