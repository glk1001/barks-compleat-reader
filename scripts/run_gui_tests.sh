#!/usr/bin/env bash
# Run the GUI path tests against the real app on the nested Xephyr display, or
# headless on Xvfb with --headless (or BARKS_PROBE_HEADLESS=1): no window, no
# graphical session needed, software OpenGL.
#
# Headless runs the tests in parallel, one Xvfb per pytest worker on displays
# :2, :3, ... (--workers N, default 4; BARKS_GUI_WORKERS). Visible runs stay
# serial on one Xephyr window unless --workers says otherwise: several windows
# would pile up on the second monitor, and the point of watching is one at a time.
#
# They live outside pytest's testpaths (like the benchmarks) because each test
# boots the real app, which needs a graphical session, Xephyr, xte and the
# reader's data directories, and drives it in real time (the first three tests
# took 84s together). Extra arguments go to pytest, e.g. `-k speech` or `-x`.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# The app sizes its window from the nested screen, and every pixel coordinate
# in the suite was measured at this size; the harness refuses to click at any
# other. Pinned here rather than left to the probe's default so the two cannot
# drift apart.
export BARKS_PROBE_SCREEN=900x1300

workers="${BARKS_GUI_WORKERS:-}"
while [[ "${1:-}" == --* ]]; do
    case "$1" in
    --headless)
        export BARKS_PROBE_HEADLESS=1
        shift
        ;;
    --workers)
        workers="${2:?--workers needs a count}"
        shift 2
        ;;
    *) break ;;
    esac
done
if [[ -z "$workers" ]]; then
    workers=1
    [[ -n "${BARKS_PROBE_HEADLESS:-}" ]] && workers=4
fi
parallel=()
[[ "$workers" -gt 1 ]] && parallel=(-n "$workers" --dist load)

# One artifacts directory for the whole run, whichever worker writes into it.
export BARKS_GUI_RUN_STAMP
BARKS_GUI_RUN_STAMP="$(date +%Y%m%d-%H%M%S)"

bash "${SCRIPT_DIR}/gui-probe.sh" doctor >/dev/null || {
    echo "run_gui_tests: this machine is not ready - see: bash scripts/gui-probe.sh doctor" >&2
    exit 1
}

# Boots are sequential by nature (one nested display), and the durations are
# the point: they say whether a test-speed boot-per-test is tolerable.
uv run pytest "${REPO_ROOT}/src/barks-reader/tests/gui/" -v --durations=0 "${parallel[@]}" "$@"
