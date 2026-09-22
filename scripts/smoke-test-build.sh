#!/usr/bin/env bash
# cspell:ignore servernum
# Smoke-test a built Barks Reader executable: does the packaged program run at all?
#
# The GUI test suite exercises the app from the workspace (`uv run main.py`), so
# nothing checks what Nuitka packaged until someone launches it. This launches
# it. With no data pack beside it and no config, a fresh build takes its
# first-run path: the compiled entry point runs, config_info resolves the
# directories, the installer starts, looks for the data packs, does not find
# them, writes the failed flag beside the executable and shows a Kivy popup
# saying so. Reaching that popup proves the onefile unpacks and the Python
# runtime, the compiled packages, loguru, the installer and a Kivy window all
# work from the build. The popup waits for a click, so the run is killed by
# `timeout`; the verdict comes from what the installer left on disk.
#
# The executable is copied into an empty directory first, so a data pack lying
# beside the real one (as in a developer checkout) does not turn this into a
# full install. On Linux it runs under xvfb-run when there is no display.
#
# Usage: scripts/smoke-test-build.sh ./barks-reader-linux [seconds, default 90]
set -euo pipefail

EXE="${1:?usage: smoke-test-build.sh <executable> [seconds]}"
SECS="${2:-90}"
[[ -x "$EXE" ]] || { echo "smoke-test-build: not an executable: $EXE" >&2; exit 2; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cp "$EXE" "$WORK/"
cd "$WORK"
exe="./$(basename "$EXE")"

# The app must not find a developer's directories through the environment.
unset BARKS_READER_CONFIG_DIR BARKS_READER_DATA_DIR

runner=()
if [[ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] && command -v xvfb-run >/dev/null; then
    runner=(xvfb-run --auto-servernum)
fi
echo "smoke-test-build: launching $exe for up to ${SECS}s..."
set +e
"${runner[@]}" timeout --signal=TERM --kill-after=10 "$SECS" "$exe" >"$WORK/stdout.log" 2>&1
rc=$?
set -e
echo "smoke-test-build: exit code $rc (124 = killed at the popup, as expected)"

fail=0
flag="$WORK/barks-reader-installer-failed.flag"
log="$(ls "$WORK"/barks-reader-installer-*.log 2>/dev/null | head -1 || true)"
if [[ -z "$log" ]]; then
    echo "smoke-test-build: FAIL - the installer wrote no log beside the executable" >&2
    fail=1
elif ! grep -q "Checking existence of installer zip" "$log"; then
    echo "smoke-test-build: FAIL - the installer never looked for its data packs" >&2
    fail=1
fi
if [[ ! -f "$flag" ]]; then
    echo "smoke-test-build: FAIL - no installer-failed flag: the missing data pack was not reported" >&2
    fail=1
fi
if grep -q "Traceback (most recent call last)" "$WORK/stdout.log" ${log:+"$log"}; then
    echo "smoke-test-build: FAIL - a traceback:" >&2
    grep -A12 "Traceback (most recent call last)" "$WORK/stdout.log" ${log:+"$log"} | head -40 >&2
    fail=1
fi
if [[ $fail -ne 0 ]]; then
    echo "---- stdout/stderr ----" >&2
    tail -40 "$WORK/stdout.log" >&2
    [[ -n "$log" ]] && { echo "---- installer log ----" >&2; tail -20 "$log" >&2; }
    exit 1
fi
echo "smoke-test-build: OK - the build runs, resolves its directories, and reports the missing data pack"
