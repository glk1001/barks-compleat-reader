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
# A visible run opens one Xephyr window per worker, which takes the host keyboard
# focus when it appears: click back to your own window once it is up, and do not
# type into it. A key that reaches the app from the host fails the test with a
# "STRAY INPUT" line in the report (the app logs every key press, and the report
# counts them against the probe's input log).
#
# --soak runs only the random walk (test_random_walk.py, marker "soak"), which the
# default run skips; BARKS_GUI_WALK_STEPS and BARKS_GUI_WALK_SEED set its length
# and seed. --app PATH runs the suite against a built executable instead of
# `uv run main.py` (BARKS_PROBE_APP), for the packaging the workspace run never
# exercises: the binary must honour the config and data dir env vars, as the
# app does when they are set.
#
# --quiet prints the pytest command it is about to run and then only failures
# and the summary line (for full-lint.sh, where the per-test verbosity is noise).
#
# --screen WxH runs the suite on a nested screen of that size instead of the
# 900x1300 default, e.g. --screen 1920x1080 to see the app as a 1080p monitor
# shows it (there the window is height-limited, about 636x1005, as on a real
# 1080p desktop). Only the size is simulated: Kivy's density is fixed at 1.0 on
# Linux, so dp() is plain pixels whatever DPI the screen reports.
#
# --prebuilt 0|1 and --png-images 0|1 run the whole suite on the other comic or
# panel source than the live profile uses (use_prebuilt_comics, use_png_images);
# --ini key=value (repeatable) sets any other Barks Reader setting for the run.
# Settings the harness pins (fullscreen, quit confirm, ...) are refused. The
# tests in test_comic_sources.py pin their own source, so every source with its
# data on this machine is read once whatever the run's default.
#
# They live outside pytest's testpaths (like the benchmarks) because each test
# boots the real app, which needs a graphical session, Xephyr, xte and the
# reader's data directories, and drives it in real time (the first three tests
# took 84s together). Extra arguments go to pytest, e.g. `-k speech` or `-x`.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

# The app sizes its window from the nested screen. Nothing in the suite clicks
# by pixel any more (every move is a key, waited on through the log), but the
# fullscreen round trips compare the window size before and after, so the size
# is fixed here rather than left to the probe's default. --screen, or an
# exported BARKS_PROBE_SCREEN, picks another size for the whole run.
export BARKS_PROBE_SCREEN="${BARKS_PROBE_SCREEN:-900x1300}"

workers="${BARKS_GUI_WORKERS:-}"
quiet=""
soak=""
# Run-wide settings, handed to the harness as "key=value;key=value".
add_ini() {
    export BARKS_GUI_INI="${BARKS_GUI_INI:+$BARKS_GUI_INI;}$1"
}
while [[ "${1:-}" == --* ]]; do
    case "$1" in
    --headless)
        export BARKS_PROBE_HEADLESS=1
        shift
        ;;
    --quiet)
        quiet=1
        shift
        ;;
    --workers)
        workers="${2:?--workers needs a count}"
        shift 2
        ;;
    --screen)
        export BARKS_PROBE_SCREEN="${2:?--screen needs WxH, e.g. 1920x1080}"
        shift 2
        ;;
    --ini)
        add_ini "${2:?--ini needs key=value}"
        shift 2
        ;;
    --soak)
        soak=1
        shift
        ;;
    --app)
        export BARKS_PROBE_APP="${2:?--app needs the path of the executable}"
        [[ -x "$BARKS_PROBE_APP" ]] || { echo "run_gui_tests: not an executable: $BARKS_PROBE_APP" >&2; exit 2; }
        shift 2
        ;;
    --prebuilt)
        add_ini "use_prebuilt_comics=${2:?--prebuilt needs 0 or 1}"
        shift 2
        ;;
    --png-images)
        add_ini "use_png_images=${2:?--png-images needs 0 or 1}"
        shift 2
        ;;
    *) break ;;
    esac
done
# Xvfb and Xephyr take the size as WxH; anything else only fails later as "the X
# server did not come up", so say what was wrong here.
if ! [[ "$BARKS_PROBE_SCREEN" =~ ^[0-9]+x[0-9]+$ ]]; then
    echo "run_gui_tests: screen size must be WxH (e.g. 1920x1080), not '$BARKS_PROBE_SCREEN'" >&2
    exit 2
fi
if [[ -z "$workers" ]]; then
    workers=1
    [[ -n "${BARKS_PROBE_HEADLESS:-}" ]] && workers=4
fi
parallel=()
[[ "$workers" -gt 1 ]] && parallel=(-n "$workers" --dist load)

# One artifacts directory for the whole run, whichever worker writes into it.
export BARKS_GUI_RUN_STAMP
BARKS_GUI_RUN_STAMP="$(date +%Y%m%d-%H%M%S)"

[[ -n "${BARKS_GUI_INI:-}" ]] && echo "run_gui_tests: settings for this run: ${BARKS_GUI_INI}"
bash "${SCRIPT_DIR}/gui-probe.sh" doctor >/dev/null || {
    echo "run_gui_tests: this machine is not ready - see: bash scripts/gui-probe.sh doctor" >&2
    exit 1
}

# The benchmark plugin (kept loaded: pyproject's pytest options are its flags)
# warns from every worker that it disables itself under xdist. Nothing here
# benchmarks, so drop that one warning by its message.
export PYTHONWARNINGS="${PYTHONWARNINGS:+$PYTHONWARNINGS,}ignore:Benchmarks are automatically disabled"
# The soak walk is long and aimless; it runs only when asked for, and then alone.
select=(-m "not soak")
[[ -n "$soak" ]] && select=(-m soak)
[[ -n "${BARKS_PROBE_APP:-}" ]] && echo "run_gui_tests: running the built executable ${BARKS_PROBE_APP}"
cmd=(uv run pytest src/barks-reader/tests/gui/ "${parallel[@]}" "${select[@]}" "$@")
# shellcheck source=scripts/_show_cmd.sh
source "${SCRIPT_DIR}/_show_cmd.sh"
if [[ -z "$quiet" ]]; then
    # Per-test lines and every duration: the durations say whether a boot-per-test
    # stays tolerable, so they are the point of a hands-on run.
    "${cmd[@]}" -v --durations=0
    exit
fi

show_cmd "${cmd[@]}" -q --tb=short
# Keep failures (their name, the short traceback's E lines) and the summary
# line, which in -q mode has no bars; pipefail hands pytest's status through.
# "skipped" is kept so a run that skipped everything says so rather than
# printing nothing.
if ! "${cmd[@]}" -q --tb=short | grep -E "^(FAILED|ERROR) |^E  |[0-9]+ (passed|failed|error|skipped)"; then
    echo "run_gui_tests: artifacts in build/gui-tests/${BARKS_GUI_RUN_STAMP}" >&2
    exit 1
fi
