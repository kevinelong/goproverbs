#!/usr/bin/env bash
# Build the shared sources with Linux Rust; keep artifacts on the Linux filesystem.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ -f "$HOME/.cargo/env" ]]; then source "$HOME/.cargo/env"; fi
if ! command -v cargo >/dev/null; then
    printf 'Linux Rust is required: https://rust-lang.org/tools/install/\n' >&2
    exit 1
fi
target_dir="${GOPROVERBS_TARGET_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/goproverbs/target}"
action="${1:-build}"
if (( $# )); then shift; fi
cd -- "$project_dir"
case "$action" in
    build)
        cargo build --offline --locked --release --target-dir "$target_dir" "$@"
        ;;
    test)
        cargo test --offline --locked -j 2 --target-dir "$target_dir" "$@"
        ;;
    run)
        cargo build --offline --locked --release --target-dir "$target_dir"
        exec "$target_dir/release/goproverbs" "$@"
        ;;
    *)
        printf 'Usage: bash scripts/wsl.sh {build|test|run} [arguments...]\n' >&2
        exit 2
        ;;
esac
