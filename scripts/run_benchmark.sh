#!/usr/bin/env bash
# Compare the load-time benchmarks against the most recent recorded baseline.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=scripts/_benchmark_cpu_guard.sh
source "${SCRIPT_DIR}/_benchmark_cpu_guard.sh"

require_stable_cpu

# Auto-pick the newest recorded baseline (highest NNNN_ prefix among *_baseline.json).
# record_benchmark_baseline.sh writes these; --benchmark-compare wants the bare name.
latest_baseline="$(
    find "${REPO_ROOT}/.benchmarks" -type f -name '*_baseline.json' -printf '%f\n' 2>/dev/null \
        | sort -n | tail -1
)"
if [[ -z "${latest_baseline}" ]]; then
    echo "ERROR: No *_baseline.json found under .benchmarks/." >&2
    echo "       Record one first:  bash scripts/record_benchmark_baseline.sh" >&2
    exit 1
fi
compare_name="${latest_baseline%.json}"
echo "Comparing against baseline: ${compare_name}"

# Gate on the median, not the min. `min` is a tail draw, and time-to-first-page is
# heavy-left-tailed - the worker thread and the scheduler callback occasionally line
# up much faster than usual. Comparing one recorded tail sample against another made
# this flap: measured over six back-to-back runs at 50 rounds, the min varied by 5.1%
# (CoV) while the median varied by 0.9%. More rounds does not fix min - min-of-N only
# reaches further into the tail as N grows - but it does settle the median.
uv run pytest src/barks-reader/tests/benchmarks/ \
    --benchmark-compare="${compare_name}" \
    --benchmark-compare-fail=median:20%
