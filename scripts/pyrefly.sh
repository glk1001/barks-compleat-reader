#!/bin/bash
# ADVISORY, NON-GATING second-opinion type check with pyrefly.
#
# `ty` (scripts/git-ty.sh, scripts/full-lint.sh, CI) remains the sole gate.
# pyrefly is much faster and stricter about nullability; run this on demand to
# surface latent issues ty does not flag. Its findings are informational — they
# are deliberately NOT part of the lint gate or pre-commit/CI, and a non-zero
# exit here does not fail any build. Config + rationale live in pyrefly.toml.

set -uo pipefail

cd "$(dirname "$0")/.."

# Same stub prerequisite as full-lint.sh: pyrefly (like ty) can't resolve the
# gitignored _version.py module until a normal run/build has generated it.
if [[ ! -f src/barks-reader/src/barks_reader/_version.py ]]; then
    echo "ERROR: src/barks-reader/src/barks_reader/_version.py is missing."
    echo "       Run the app or build once to generate it (pyrefly will fail without it)."
    exit 1
fi

echo "==== pyrefly (advisory — not a gate) ===="
uv run pyrefly check "$@"
