#!/usr/bin/env bash
# Download the latest CI-built Windows executable — no git clone, no tagged
# release needed. Grabs the barks-reader-win.exe artifact from the most recent
# Build Verification run on a branch (default: main), waiting for the run to
# finish if it's still building.
#
# Usage:
#   ./get-win-build.sh [branch] [dest-dir]
#
# Examples:
#   ./get-win-build.sh                 # latest main build -> ./win-test/
#   ./get-win-build.sh my-feature      # latest my-feature build -> ./win-test/
#   ./get-win-build.sh main ~/Desktop  # latest main build -> ~/Desktop/
#
# Requires: gh (authenticated). Works from any directory — targets the repo via
# GH_REPO below, so you don't need to be inside a clone.
set -euo pipefail

REPO="${GH_REPO:-glk1001/barks-compleat-reader}"
WORKFLOW="build.yml"
ARTIFACT="barks-reader-win.exe"
BRANCH="${1:-main}"
DEST="${2:-./win-test}"

echo "Looking up latest '${WORKFLOW}' run on '${BRANCH}' in ${REPO}..."

# Pull id + live status of the newest run in one call.
read -r RUN_ID STATUS CONCLUSION <<<"$(
    gh run list -R "$REPO" --branch "$BRANCH" --workflow "$WORKFLOW" -L1 \
        --json databaseId,status,conclusion \
        -q '.[0] | "\(.databaseId) \(.status) \(.conclusion // "")"'
)"

if [[ -z "${RUN_ID:-}" ]]; then
    echo "No '${WORKFLOW}' runs found on branch '${BRANCH}'." >&2
    exit 1
fi

echo "Run ${RUN_ID}: status=${STATUS} conclusion=${CONCLUSION:-<pending>}"

# Still building? Block until it's done (gh run watch exits non-zero on failure).
if [[ "$STATUS" != "completed" ]]; then
    echo "Run still in progress — waiting for it to finish..."
    if ! gh run watch -R "$REPO" "$RUN_ID" --exit-status; then
        echo "Run ${RUN_ID} did not succeed — nothing to download." >&2
        exit 1
    fi
elif [[ "$CONCLUSION" != "success" ]]; then
    echo "Latest run concluded '${CONCLUSION}', not 'success' — nothing to download." >&2
    exit 1
fi

mkdir -p "$DEST"
echo "Downloading '${ARTIFACT}' -> ${DEST}/ ..."
gh run download -R "$REPO" "$RUN_ID" -n "$ARTIFACT" -D "$DEST"

echo "Done. Executable at: ${DEST}/${ARTIFACT}"
