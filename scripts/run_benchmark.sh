#!/usr/bin/env bash
# Compare the load-time benchmarks against the most recent recorded baseline.
#
# --quiet prints the pytest command, then only the result tables and the
# summary line (for full-lint.sh). Extra arguments go to pytest.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"
# shellcheck source=scripts/_benchmark_cpu_guard.sh
source "${SCRIPT_DIR}/_benchmark_cpu_guard.sh"
# shellcheck source=scripts/_show_cmd.sh
source "${SCRIPT_DIR}/_show_cmd.sh"

quiet=""
if [[ "${1:-}" == "--quiet" ]]; then
    quiet=1
    shift
fi

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
# A benchmark must never run under parallel workers, and with pytest-xdist
# merely installed its plugin makes pytest-benchmark warn on every run: keep
# it out of this session altogether.
# Rows within a table are sorted by name, not (the default) by the fastest
# minimum, so the baseline is always the top row and NOW the bottom one; by
# minimum the two swapped places depending on which run happened to win.
cmd=(
    uv run pytest src/barks-reader/tests/benchmarks/ -p no:xdist
    --benchmark-compare="${compare_name}"
    --benchmark-compare-fail=median:20%
    --benchmark-sort=name
    "$@"
)
if [[ -z "$quiet" ]]; then
    exec "${cmd[@]}"
fi

show_cmd "${cmd[@]}" -q --no-header
# The plugin warns on stderr whenever the machine info differs from the
# baseline's (a kernel update does it); the tables carry the comparison, so in
# quiet mode that warning is dropped by its message.
export PYTHONWARNINGS="${PYTHONWARNINGS:+$PYTHONWARNINGS,}ignore:Benchmark machine_info is different"
# Keep the result tables (from the first table rule up to the legend), any
# regression, failure or error lines, and the summary; stderr goes through the
# same filter, and pipefail hands pytest's status through it.
"${cmd[@]}" -q --no-header 2>&1 | awk '
    /^-+ benchmark/ { in_table = 1 }
    /^Legend:/      { in_table = 0 }
    in_table        { print; next }
    /FAILED|ERROR|Error|Traceback|regress|[0-9]+ (passed|failed|error)/ { print }
'
