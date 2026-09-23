#!/usr/bin/env bash
# cspell:ignore servernum taskkill
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
# work from the build. The popup waits for a click, so the run is killed after
# a while; the verdict comes from what the installer left on disk.
#
# The build is copied into an empty directory first, so a data pack lying
# beside the real one (as in a developer checkout) does not turn this into a
# full install. All three platforms' builds are taken: the Linux and Windows
# onefile executables as they are, and the zipped macOS .app bundle, which is
# unpacked and launched by the binary inside it (the app anchors its config
# and the installer's files beside the bundle). On Linux it runs under xvfb-run
# when there is no display; on the other two the runner's own session shows
# the window. The wait-and-kill is done here rather than with `timeout`, which
# macOS does not ship and which cannot reach a Windows process tree.
#
# With KIVY_GL_BACKEND set (CI's Windows leg runs a second time with angle_sdl2),
# the launch hands it to the build, and the test also requires Kivy's line naming
# the graphics backend it drew through to name that one: a build missing the
# backend's DLLs would otherwise fall back, or crash, and still look alive.
#
# With --press-escape the run goes one step further: once the popup logs that it
# is open, Escape is pressed through the OS's real input path (send_os_key.py:
# xdotool on Linux, on an Xvfb this script starts, SendInput on Windows,
# CGEventPostToPid on macOS), and the popup must log that it closed and the program
# exit by itself - so the build takes a key the way a keyboard or remote sends it.
#
# Usage: scripts/smoke-test-build.sh [--press-escape] <executable or .zip> [seconds, default 90]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
PRESS=""
if [[ "${1:-}" == "--press-escape" ]]; then
    PRESS=1
    shift
fi
# How long the program has to exit once Escape has been pressed.
EXIT_AFTER_KEY_SECS=20
POPUP_OPENED="Standalone popup opened"
POPUP_CLOSED="Standalone popup closed"

BUILD="${1:?usage: smoke-test-build.sh [--press-escape] <executable or .zip> [seconds]}"
SECS="${2:-90}"
[[ -e "$BUILD" ]] || { echo "smoke-test-build: no such build: $BUILD" >&2; exit 2; }

WORK="$(mktemp -d)"
xvfb_pid=""
trap 'rm -rf "$WORK"; [[ -n "$xvfb_pid" ]] && kill "$xvfb_pid" 2>/dev/null; true' EXIT
cp "$BUILD" "$WORK/"
cd "$WORK"

# Where the executable is, and what the app anchors its files beside.
if [[ "$BUILD" == *.zip ]]; then
    unzip -q "$(basename "$BUILD")"
    exe="$(find . -path '*.app/Contents/MacOS/*' -type f -perm -u+x | head -1 || true)"
    [[ -n "$exe" ]] || { echo "smoke-test-build: no executable inside a .app in $BUILD" >&2; exit 2; }
else
    exe="./$(basename "$BUILD")"
    [[ -x "$exe" ]] || chmod +x "$exe"
fi

# The app must not find a developer's directories through the environment.
unset BARKS_READER_CONFIG_DIR BARKS_READER_DATA_DIR

runner=()
if [[ -n "$PRESS" && "$OSTYPE" == linux* ]]; then
    # The key sender must know the display, so this run owns its Xvfb rather than
    # letting xvfb-run pick one. -displayfd writes the display number it chose.
    Xvfb -displayfd 5 -screen 0 1280x1024x24 -nolisten tcp 5>"$WORK/display" >/dev/null 2>&1 &
    xvfb_pid=$!
    for ((i = 0; i < 20; i++)); do
        [[ -s "$WORK/display" ]] && break
        sleep 0.5
    done
    [[ -s "$WORK/display" ]] || { echo "smoke-test-build: Xvfb did not start" >&2; exit 2; }
    export DISPLAY=":$(head -1 "$WORK/display")"
    unset WAYLAND_DISPLAY
elif [[ "$OSTYPE" == linux* && -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] && command -v xvfb-run >/dev/null; then
    runner=(xvfb-run --auto-servernum)
fi

# Run it, and stop it once the popup has had time to appear. The launch goes
# through an inner bash so that the kill lands on the app's process tree (the
# onefile bootstrap and the program it unpacked, plus xvfb-run and its Xvfb)
# and never on this script's own child: a job killed by a signal would have
# bash print "Killed" into the CI log; the inner shell absorbs that and exits.
# Windows has no pgrep, and its tree is stopped by image name instead.
descendants() {
    local child
    for child in $(pgrep -P "$1" 2>/dev/null); do
        descendants "$child"
        echo "$child"
    done
}
stop_tree() {
    local pids
    if [[ "$OSTYPE" == msys* || "$OSTYPE" == cygwin* ]]; then
        taskkill //F //T //IM "$(basename "$exe")" >/dev/null 2>&1 || true
        return
    fi
    pids="$(descendants "$1")"
    [[ -n "$pids" ]] && kill -TERM $pids 2>/dev/null
    sleep 5
    pids="$(descendants "$1")"
    [[ -n "$pids" ]] && kill -KILL $pids 2>/dev/null
    return 0
}
# Press Escape in the program through the OS's input path. Windows is found by its
# executable's name (Git Bash's pids are not Windows pids); Linux and macOS by the
# processes under the launch.
press_escape() {
    local args=(Escape)
    if [[ "$OSTYPE" == msys* || "$OSTYPE" == cygwin* ]]; then
        args+=(--image "$(basename "$exe")")
    else
        # shellcheck disable=SC2046  # one pid per word
        args+=(--pids $(descendants "$pid"))
    fi
    uv run --project "$REPO_ROOT" python "$SCRIPT_DIR/send_os_key.py" "${args[@]}"
}
popup_logged() {
    grep -qs "$1" "$WORK/stdout.log" "$WORK"/barks-reader-installer-*.log
}

echo "smoke-test-build: launching $exe for up to ${SECS}s..."
# The ${arr[@]+...} form: macOS's /bin/bash is 3.2, where "${runner[@]}" on an
# empty array is an unbound variable under set -u (bash 4.4 and later allow it).
bash -c '"$@"' _ ${runner[@]+"${runner[@]}"} "$exe" >"$WORK/stdout.log" 2>&1 &
pid=$!
pressed=""
press_failed=""
for ((waited = 0; waited < SECS; waited++)); do
    kill -0 "$pid" 2>/dev/null || break
    if [[ -n "$PRESS" && -z "$pressed$press_failed" ]] && popup_logged "$POPUP_OPENED"; then
        sleep 1 # let the popup finish appearing before the key
        if press_escape; then
            pressed=$waited
        else
            press_failed=1
        fi
    fi
    if [[ -n "$pressed" ]] && ((waited - pressed >= EXIT_AFTER_KEY_SECS)); then
        break
    fi
    sleep 1
done
killed=""
if kill -0 "$pid" 2>/dev/null; then
    killed=1
    stop_tree "$pid"
fi
set +e
wait "$pid"
rc=$?
set -e
if [[ -n "$killed" && -z "$PRESS" ]]; then
    echo "smoke-test-build: stopped at the popup after ${waited}s, as expected"
elif [[ -n "$killed" ]]; then
    echo "smoke-test-build: stopped after ${waited}s"
else
    echo "smoke-test-build: exited on its own with code $rc after ${waited}s"
fi

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
if [[ -n "$PRESS" ]]; then
    if [[ -n "$press_failed" ]]; then
        echo "smoke-test-build: FAIL - the popup opened but Escape could not be sent (see above)" >&2
        fail=1
    elif [[ -z "$pressed" ]]; then
        echo "smoke-test-build: FAIL - the popup never logged \"$POPUP_OPENED\", so no key was pressed" >&2
        fail=1
    else
        if ! popup_logged "$POPUP_CLOSED"; then
            echo "smoke-test-build: FAIL - Escape was pressed but the popup never logged \"$POPUP_CLOSED\"" >&2
            fail=1
        fi
        if [[ -n "$killed" ]]; then
            echo "smoke-test-build: FAIL - the program did not exit within ${EXIT_AFTER_KEY_SECS}s of Escape" >&2
            fail=1
        fi
    fi
fi
if [[ -n "${KIVY_GL_BACKEND:-}" ]]; then
    # Kivy's own lines are not in stdout or the installer log (the installer logs
    # through loguru); Kivy writes them to its log file under its home, which the
    # app keeps in the config folder beside the executable. So every log the run
    # left in the work folder is searched. Only "Backend used <...>" is matched:
    # Kivy's file log writes the message's "GL:" as a category column.
    if grep -rqF --include='*.log' --include='*.txt' "Backend used <${KIVY_GL_BACKEND}>" "$WORK"; then
        echo "smoke-test-build: drew through the ${KIVY_GL_BACKEND} graphics backend, as asked"
    else
        used="$(grep -rohE --include='*.log' --include='*.txt' "Backend used <[^>]*>" "$WORK" | head -1 || true)"
        echo "smoke-test-build: FAIL - asked for the ${KIVY_GL_BACKEND} graphics backend; the logs say: ${used:-no backend line}" >&2
        echo "smoke-test-build: the logs searched:" >&2
        find "$WORK" \( -name '*.log' -o -name '*.txt' \) -type f >&2
        fail=1
    fi
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
if [[ -n "$PRESS" ]]; then
    echo "smoke-test-build: OK - the build reports the missing data pack, closes on Escape and exits"
else
    echo "smoke-test-build: OK - the build runs, resolves its directories, and reports the missing data pack"
fi
