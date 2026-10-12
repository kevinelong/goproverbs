# Windows and WSL performance: September 21, 2026

On this machine and project, WSL built faster and ran the measured release
searches faster. Repeated Windows-to-WSL launches can erase the advantage for
very short commands. No security settings were changed.

## Measurements

Median wall-clock seconds, including process startup/output capture. WSL rows
are timed inside Ubuntu unless explicitly marked as launched from Windows.

| Workload | Windows native | WSL, Linux sources | WSL, Windows sources |
|---|---:|---:|---:|
| Clean release build, 3 runs | 2.935 | 1.416 | 1.463 |
| Unchanged release build, 5 runs | 0.143 | 0.012 | 0.035 |
| Compile debug test executables, 1 run | 7.019 | 2.251 | Not measured |
| Compile release test executables, 1 run | 6.549 | 1.637 | Not measured |
| Run debug test suite, 3 runs | Blocked | 2.177 | Not measured |
| Run release test suite, 3 runs | Blocked | 0.312 | Not measured |
| Release 9x9 search, 5 runs | 0.089 | 0.039 | Not measured |
| Release 19x19 search, 5 runs | 0.408 | 0.258 | Not measured |

Both Windows test-suite attempts stopped with Application Control error 4551.
Their durations are not valid successful-suite measurements. The Windows release
app itself ran successfully. All 44 tests in the frozen performance snapshot
passed under WSL, in both debug and release configurations.

With Ubuntu already running, a Windows `wsl.exe ... true` call took a median
0.145 seconds. A complete Windows-to-WSL call for an unchanged Cargo build took
0.162 seconds, versus 0.143 seconds for native Windows Cargo. These use five
measured runs after one warmup. Cold WSL startup/shutdown was not measured.

The 9x9 and 19x19 release workloads were approximately 2.27x and 1.58x faster in
WSL by elapsed time. Both platforms produced identical text after removing only
elapsed_ms, leaf_us, and ranking_us timing fields. Moves, scores, principal
variations, node counts, leaf-call counts, and depth matched in all ten pairs.

## Method and limits

- Same hashed source snapshot, Rust/Cargo 1.96.0, LLVM 22.1.2, two build jobs,
  offline locked dependencies, default Cargo release optimization. Native targets
  differ: x86_64-pc-windows-msvc versus x86_64-unknown-linux-gnu.
- Windows 11 and Ubuntu 24.04.4 / WSL 2 on the same Core Ultra 9 285 desktop.
  Platform suites ran sequentially. Other desktop activity was not disabled.
- Each clean build used a new target directory. This means no prior compiled
  artifacts, not a flushed operating-system disk cache. No-op builds reused one
  completed target. Test runs followed separate test compilation.
- Linux build artifacts stayed on the Linux filesystem in both WSL variants;
  the third variant read source through /mnt/c, matching the shared project setup.
- Search: selective mode, depth 4, beam 8, 100,000-node ceiling, 60-second ceiling;
  every measured search completed without either ceiling limiting it. Positions
  were D4 F6 C3 G7 on 9x9 and D4 Q16 D16 Q4 on 19x19. One warmup per position.
- Live source changed during initial verification. A frozen copy received the
  compiler-suggested shared lifetime on analyze_guided's weights/evaluator
  parameters before both platforms compiled it. No live source was edited for
  the comparison. The current tree later compiled successfully with that signature
  already present, and passed 47 tests on Rust 1.98.1; those are separate results.
- These compare complete local toolchains, including OS, linker/runtime, process
  startup and active endpoint protection. They do not isolate virtualization cost
  or establish a speed advantage for arbitrary tools/models. Small samples have
  no confidence intervals; single test-compilation timings are descriptive only.

## Practical choice

Use the WSL workflow for this project. Keeping the shared source on C: costs
little on its clean builds, while Linux-native sources reduce no-op build time.
Batch short commands into one WSL session rather than invoking wsl.exe separately
for every tiny operation. Use release builds for search/performance measurements;
debug builds remain useful for ordinary testing. Signing is unnecessary for the
Linux executable, but Windows releases remain a separate target.

[Compact evidence](../results/wsl-performance-20260921.json) includes source hashes,
commands, individual timings, and output equivalence checks. Full frozen sources,
scripts, and logs are in `C:/Users/kevin/ai_bench/wsl-perf-20260921`.
