#!/usr/bin/env bash
#
# Check that this machine can run scripts/run_overnight.sh, and say what is missing.
#
# Run it on the machine that is to run the overnight suite, from its checkout of
# this repo. It checks what the run reads beyond this repo: the sibling repos
# beside it, .env.runtime (gitignored: it holds the key that decrypts the comic
# archives), the real cpi.db rather than its git-lfs pointer, the tools the
# stages call, and the app's profile and data folders - the last two through
# gui-probe.sh doctor, headless, which knows the app's settings. The comic build
# tree is not checked: a second machine runs with --skip build-check (that tree
# is this project's build output, about 330 GB, and is checked where it is made).
# scripts/copy-to-overnight-host.sh sets a machine up; this says whether it worked.
#
# Usage: scripts/check-overnight-host.sh
# Exit status: 0 when everything required is there, 1 otherwise. What is only
# advised (the touch rule, this machine's GUI timing calibration) never fails it.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

missing=0
ok() { echo "  OK   $1"; }
bad() {
    echo "  MISSING  $1"
    missing=1
}
advise() { echo "  ADVISE   $1"; }

echo "== sibling repos (beside this one) =="
for repo in barks-comic-building barks-ocr barks-wiki; do
    if [[ -d "../${repo}/.git" ]]; then
        ok "../${repo}"
    else
        bad "../${repo}: clone it beside this repo (the siblings, wiki-order and wiki stages read it)"
    fi
done

echo "== this repo =="
if [[ -f .env.runtime ]]; then
    ok ".env.runtime"
    for var in BARKS_ZIPS_KEY BARKS_READER_CONFIG_DIR BARKS_READER_DATA_DIR; do
        if grep -q "^${var}=" .env.runtime; then ok "  ${var}"; else bad "  ${var} in .env.runtime"; fi
    done
    # The reader's own files (panel zips, indexes, fonts, the shipped wiki copy),
    # which doctor does not look inside the data folder for.
    data_dir="$(grep '^BARKS_READER_DATA_DIR=' .env.runtime | cut -d= -f2- | tr -d '"')"
    data_dir="${data_dir//\$\{HOME\}/$HOME}"
    if [[ -n "$data_dir" && -d "${data_dir}/Reader Files" ]]; then
        ok "  ${data_dir}/Reader Files"
    else
        bad "  Reader Files in the data folder (${data_dir:-unset})"
    fi
else
    bad ".env.runtime (gitignored; copy its BARKS_ lines from the main machine)"
fi
cpi_db=src/comic-utils/src/comic_utils/cpi.db
# A git-lfs pointer is a few lines of text; the real database is tens of MB.
if [[ -f "$cpi_db" ]] && (($(stat -c %s "$cpi_db") > 100000)); then
    ok "$cpi_db (the real file)"
else
    bad "$cpi_db is its git-lfs pointer: git lfs install && git lfs pull"
fi
if [[ -d .venv ]]; then ok ".venv"; else bad ".venv: uv sync"; fi

echo "== tools the stages call =="
for tool in uv git git-lfs bun systemd-inhibit Xvfb xvfb-run; do
    if command -v "$tool" >/dev/null 2>&1; then ok "$tool"; else bad "$tool"; fi
done

echo "== the GUI probe (tools, profile, data folders) =="
if BARKS_PROBE_HEADLESS=1 bash "${SCRIPT_DIR}/gui-probe.sh" doctor; then
    :
else
    missing=1
fi

echo "== advised =="
if [[ -f .benchmarks/gui-timings.json ]]; then
    ok "this machine's GUI timing calibration"
else
    advise "no GUI timing calibration here: bash scripts/run_gui_tests.sh --calibrate"
    advise "  (until then the committed budgets, measured on the main machine, apply)"
fi
if BARKS_PROBE_TOUCH=1 BARKS_PROBE_HEADLESS=1 bash "${SCRIPT_DIR}/gui-probe.sh" doctor >/dev/null 2>&1; then
    ok "touch mode"
else
    advise "touch mode not set up: the overnight touch stage skips itself (see"
    advise "  BARKS_PROBE_TOUCH=1 BARKS_PROBE_HEADLESS=1 bash scripts/gui-probe.sh doctor)"
fi

echo
if ((missing)); then
    echo "check-overnight-host: not ready - fix what is MISSING above."
    exit 1
fi
echo "check-overnight-host: ready. Run: bash scripts/run_overnight.sh --skip build-check"
