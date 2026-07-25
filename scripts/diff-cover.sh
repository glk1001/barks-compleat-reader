#!/bin/bash
# Enforce test coverage on CHANGED lines only, not the whole tree.
#
# The global coverage floor (fail_under in pyproject) is deliberately low because
# the Kivy UI layer is hard to unit-test. diff-cover complements it: whatever code a
# branch adds or modifies must itself be covered, so overall coverage ratchets up
# instead of eroding — without demanding the whole app hit a high bar at once.
#
# Only lines in the measured coverage source ([tool.coverage.run] source, currently
# barks_reader + barks_fantagraphics) are counted; changes elsewhere pass for free.
#
# Usage:
#   bash scripts/diff-cover.sh                  # compare against origin/main
#   bash scripts/diff-cover.sh main             # compare against a specific branch
#   FAIL_UNDER=70 bash scripts/diff-cover.sh    # override the threshold (default 80)
set -euo pipefail
cd "$(dirname "$0")/.."

base="${1:-origin/main}"
fail_under="${FAIL_UNDER:-80}"

# CI generates this stub; locally it comes from a normal run/build.
if [[ ! -f src/barks-reader/src/barks_reader/_version.py ]]; then
    echo "ERROR: src/barks-reader/src/barks_reader/_version.py is missing (run the app or build once)."
    exit 1
fi

uv run pytest -q --cov --cov-report=xml
uv run diff-cover coverage.xml --compare-branch="$base" --fail-under="$fail_under"
