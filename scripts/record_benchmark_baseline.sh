#!/usr/bin/env bash
# Record a fresh benchmark baseline. pytest-benchmark auto-prefixes the save name
# with an incrementing counter, so repeated runs of `--benchmark-save=baseline`
# produce 0003_baseline, 0004_baseline, 0005_baseline, ... in .benchmarks/.
#
# After recording, point run_benchmark.sh's --benchmark-compare= at the new file.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/_benchmark_cpu_guard.sh
source "${SCRIPT_DIR}/_benchmark_cpu_guard.sh"

require_stable_cpu

SAVE_NAME="${1:-baseline}"

uv run pytest src/barks-reader/tests/benchmarks/ \
    --benchmark-save="${SAVE_NAME}"
