#!/bin/bash
# Run every lint/static check the CI runs, over the whole repo.
# All checks run even if an earlier one fails; a summary is printed at the end.
#
# Checks: ruff check, ruff format, ty (--error-on-warning, as in CI), pyrefly
#         (0 new vs pyrefly-baseline.json), import-linter, relative-import check,
#         cspell, benchmarks (compared against the machine-local baseline in
#         .benchmarks/).

set -uo pipefail

cd "$(dirname "$0")/.."

# CI generates this stub; locally it comes from a normal run/build.
if [[ ! -f src/barks-reader/src/barks_reader/_version.py ]]; then
    echo "ERROR: src/barks-reader/src/barks_reader/_version.py is missing."
    echo "       Run the app or build once to generate it (ty will fail without it)."
    exit 1
fi

declare -a failed=()

run_check() {
    local name="$1"
    shift

    echo
    echo "==== ${name} ===="
    if ! "$@"; then
        failed+=("$name")
    fi
}

run_check "ruff check"            uv run ruff check .
run_check "ruff format"           uv run ruff format --check .
run_check "ty"                    uv run ty check --error-on-warning
run_check "pyrefly"               uv run pyrefly check --progress-bar=no
run_check "import-linter"         uv run lint-imports
run_check "relative-import-check" bash scripts/check-relative-imports.sh
run_check "cspell"                bunx cspell --no-progress
run_check "benchmarks"            bash scripts/run_benchmark.sh

echo
echo "===================="
if [[ ${#failed[@]} -eq 0 ]]; then
    echo "All lint checks passed."
else
    echo "FAILED checks: ${failed[*]}"
    exit 1
fi
