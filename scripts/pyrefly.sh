#!/bin/bash
# On-demand pyrefly run. pyrefly is a GATE (CI, pre-commit, full-lint.sh) run
# alongside ty; this script is the convenience entry point + baseline refresher.
#
# Residual findings are grandfathered in pyrefly-baseline.json (wired via
# pyrefly.toml), so a clean run reports "0 errors" and only NEW issues surface
# (and fail the gate). After intentionally changing that set, refresh it:
#     bash scripts/pyrefly.sh --update-baseline

set -uo pipefail

cd "$(dirname "$0")/.."

# Same stub prerequisite as full-lint.sh: pyrefly (like ty) can't resolve the
# gitignored _version.py module until a normal run/build has generated it.
if [[ ! -f src/barks-reader/src/barks_reader/_version.py ]]; then
    echo "ERROR: src/barks-reader/src/barks_reader/_version.py is missing."
    echo "       Run the app or build once to generate it (pyrefly will fail without it)."
    exit 1
fi

echo "==== pyrefly ===="
uv run pyrefly check "$@"
