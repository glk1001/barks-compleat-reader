#!/bin/bash
# Enforce test coverage on the lines a branch changes, and on each package.
#
# diff-cover: whatever code a branch adds or modifies must itself be 80% covered.
# Only lines in the measured coverage source ([tool.coverage.run] source in
# pyproject.toml) are counted; changes elsewhere pass for free.
#
# package_coverage.py: each measured package must stay at or above its own floor, a
# point below what it reached, so a package near 100% cannot drift down a few lines
# at a time inside that 80%. The total's own floor in pyproject (fail_under) is far
# below the real figure and guards nothing.
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
# Each package against its own floor, from the same run (package_coverage.py says why).
uv run python scripts/package_coverage.py
