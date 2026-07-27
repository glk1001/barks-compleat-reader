#!/usr/bin/env bash
#
# Drive the Barks Reader GUI on a nested Xephyr display.
#
# The app normally runs as an XWayland client under Mutter, where screen capture
# and input injection are both mediated and unreliable: `import -window <id>`
# returns a frozen pixmap (repeat captures are byte-identical while the app has
# moved on), `import -window root` is blocked outright, and `xte` needs a
# per-session screen-share approval before XTEST events stop being dropped.
#
# On a nested Xephyr server none of that applies. It is a plain X server we own,
# with no compositor and no window manager: root captures are always fresh, xte
# injects without a portal, and there is no HiDPI scaling, so pixel coordinates
# read straight off a screenshot are the coordinates to click.
#
# Usage:
#   scripts/gui-probe.sh doctor           # check this machine has what it needs
#   scripts/gui-probe.sh start            # Xephyr + app, waits until ready
#   scripts/gui-probe.sh shot out.png     # fresh full-screen capture
#   scripts/gui-probe.sh click 840 74     # click at screenshot coordinates
#   scripts/gui-probe.sh key Down Down Return
#   scripts/gui-probe.sh type "pirate gold"
#   scripts/gui-probe.sh wait 'Goto title' 10
#   scripts/gui-probe.sh settle           # block until rendering has stopped
#   scripts/gui-probe.sh log              # print the app log path
#   scripts/gui-probe.sh tail 20          # last N app log lines
#   scripts/gui-probe.sh stop             # kill both, restore the user config
#
# Env overrides: BARKS_PROBE_DISPLAY (:2), BARKS_PROBE_SCREEN (900x1300).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DPY="${BARKS_PROBE_DISPLAY:-:2}"
SCREEN="${BARKS_PROBE_SCREEN:-900x1300}"
RUN_DIR="${XDG_RUNTIME_DIR:-/tmp}/barks-gui-probe"
APP_LOG="$RUN_DIR/app.log"
XEPHYR_LOG="$RUN_DIR/xephyr.log"
XEPHYR_PID_FILE="$RUN_DIR/xephyr.pid"
APP_PID_FILE="$RUN_DIR/app.pid"
CONFIG_BACKUP="$RUN_DIR/barks-reader.json.bak"

# The tree build finishing and the loading popup being dismissed is the last
# thing that happens before the app is interactive.
READY_MARKER="Received the 'on_finished_building_event'"

WINDOW_NAME="Compleat Barks Disney Reader"

# Tool -> Debian/Ubuntu package providing it.
declare -A TOOL_PKGS=(
    [Xephyr]=xserver-xephyr
    [xte]=xautomation
    [xdpyinfo]=x11-utils
    [xwininfo]=x11-utils
    [import]=imagemagick
    [convert]=imagemagick
)

die() {
    echo "gui-probe: $*" >&2
    exit 1
}

config_file() {
    local dir
    dir="$(grep -oP '(?<=^BARKS_READER_CONFIG_DIR=").*(?="$)' "$REPO_ROOT/.env.runtime" 2>/dev/null || true)"
    dir="${dir/\$\{HOME\}/$HOME}"
    echo "${dir:-$HOME/opt/barks-reader/config}/barks-reader.json"
}

require_running() {
    [[ -f "$XEPHYR_PID_FILE" ]] || die "not started - run 'gui-probe.sh start' first"
    kill -0 "$(cat "$XEPHYR_PID_FILE")" 2>/dev/null || die "Xephyr died; see $XEPHYR_LOG"
}

# Check everything a fresh machine needs. Tools and secrets are hard failures;
# a missing data directory only limits what can be verified, so it warns.
cmd_doctor() {
    local fail=0 warn=0 missing_pkgs=()

    echo "== host display =="
    if [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]; then
        echo "  OK   graphical session (Xephyr needs one to open its window in)"
    else
        echo "  FAIL no DISPLAY or WAYLAND_DISPLAY - run this from a desktop session"
        fail=1
    fi

    echo "== tools =="
    local tool
    for tool in Xephyr xte xdpyinfo xwininfo import convert uv; do
        if command -v "$tool" >/dev/null; then
            echo "  OK   $tool"
        else
            echo "  FAIL $tool"
            fail=1
            [[ -n "${TOOL_PKGS[$tool]:-}" ]] && missing_pkgs+=("${TOOL_PKGS[$tool]}")
        fi
    done

    echo "== optional =="
    if command -v xdotool >/dev/null; then
        echo "  OK   xdotool (pointer queries and chord keys on the nested display)"
    else
        echo "  --   xdotool absent (optional: 'sudo apt install xdotool')"
    fi

    echo "== repo =="
    if [[ -f "$REPO_ROOT/.env.runtime" ]]; then
        echo "  OK   .env.runtime"
        local var
        for var in BARKS_ZIPS_KEY BARKS_READER_CONFIG_DIR BARKS_READER_DATA_DIR; do
            if grep -q "^$var=" "$REPO_ROOT/.env.runtime"; then
                echo "  OK   $var"
            else
                echo "  FAIL $var not set in .env.runtime"
                fail=1
            fi
        done
    else
        echo "  FAIL .env.runtime - gitignored (it holds BARKS_ZIPS_KEY), copy it from a working machine"
        fail=1
    fi
    if [[ -d "$REPO_ROOT/.venv" ]]; then
        echo "  OK   .venv"
    else
        echo "  FAIL .venv - run 'uv sync'"
        fail=1
    fi

    echo "== app data =="
    local ini
    ini="$(dirname "$(config_file)")/barks-reader.ini"
    if [[ -f "$ini" ]]; then
        echo "  OK   $ini"
        # Every *_dir setting, checked generically. Several are absolute paths
        # baked in on whichever machine wrote them, so they routinely need
        # editing after copying the config to a new machine.
        local key path
        while IFS='=' read -r key path; do
            key="${key//[[:space:]]/}"
            path="${path#"${path%%[![:space:]]*}"}"
            path="${path//\$\{HOME\}/$HOME}"
            if [[ -d "$path" ]]; then
                echo "  OK   $key"
            else
                echo "  WARN $key -> $path (missing; edit $ini)"
                warn=1
            fi
        done < <(grep -E '^[a-z_]+_dir[[:space:]]*=' "$ini" || true)
    else
        echo "  WARN $ini not found - the app will write a default on first run"
        warn=1
    fi

    if [[ ${#missing_pkgs[@]} -gt 0 ]]; then
        # shellcheck disable=SC2207
        local uniq=($(printf '%s\n' "${missing_pkgs[@]}" | sort -u))
        echo
        echo "Install the missing tools with:"
        echo "  sudo apt install ${uniq[*]}"
    fi

    echo
    if [[ $fail -ne 0 ]]; then
        echo "doctor: NOT ready - fix the FAIL items above."
        return 1
    fi
    if [[ $warn -ne 0 ]]; then
        echo "doctor: ready, but some data dirs are missing (see WARN)."
    else
        echo "doctor: ready."
    fi
}

cmd_start() {
    for tool in Xephyr xte import; do
        command -v "$tool" >/dev/null ||
            die "missing required tool: $tool (run 'gui-probe.sh doctor')"
    done
    [[ -f "$XEPHYR_PID_FILE" ]] && kill -0 "$(cat "$XEPHYR_PID_FILE")" 2>/dev/null &&
        die "already running (stop it first)"

    mkdir -p "$RUN_DIR"
    : >"$APP_LOG"

    # The app rewrites its config on exit; keep the user's copy intact.
    local cfg
    cfg="$(config_file)"
    [[ -f "$cfg" ]] && cp "$cfg" "$CONFIG_BACKUP"

    # Detach fully (stdin included). A background child that still holds the
    # caller's stdin/stdout keeps the calling shell's pipeline open, so `start`
    # would appear to hang until the app exits.
    setsid Xephyr "$DPY" -screen "$SCREEN" -resizeable -title "barks-gui-probe" \
        </dev/null >"$XEPHYR_LOG" 2>&1 &
    echo $! >"$XEPHYR_PID_FILE"
    disown

    local waited=0
    until DISPLAY="$DPY" xdpyinfo >/dev/null 2>&1; do
        sleep 0.5
        waited=$((waited + 1))
        [[ $waited -gt 20 ]] && die "Xephyr did not come up; see $XEPHYR_LOG"
    done
    echo "gui-probe: Xephyr up on $DPY ($SCREEN)"

    setsid env DISPLAY="$DPY" uv run --directory "$REPO_ROOT" main.py \
        </dev/null >>"$APP_LOG" 2>&1 &
    echo $! >"$APP_PID_FILE"
    disown

    echo "gui-probe: waiting for the app to become interactive..."
    cmd_wait "$READY_MARKER" 120 || die "app never became ready; see $APP_LOG"
    # The marker fires when the tree is built, ~1s before the first paint finishes.
    cmd_settle 1000 30

    # No window manager runs on the nested display, so X input focus follows the
    # pointer (PointerRoot). Park it inside the window or keystrokes go nowhere.
    park_pointer
    echo "gui-probe: ready. Log: $APP_LOG"
}

park_pointer() {
    local geom w h
    geom="$(DISPLAY="$DPY" xwininfo -root -children |
        grep -F "$WINDOW_NAME" | grep -oP '\d+x\d+\+\d+\+\d+' | head -1 || true)"
    if [[ -n "$geom" ]]; then
        w="${geom%%x*}"
        h="${geom#*x}"
        h="${h%%+*}"
        # Mid-height on the far left: inside the window but clear of the action
        # bar and the goto arrows, so no hover state is triggered.
        xte -x "$DPY" "mousemove 5 $((h / 2))" >/dev/null
    else
        xte -x "$DPY" "mousemove 5 400" >/dev/null
    fi
}

cmd_stop() {
    # setsid made each child its own process-group leader, so a negative pid
    # takes the whole group (uv wrapper plus the python process it execs).
    if [[ -f "$APP_PID_FILE" ]]; then
        kill -TERM -- "-$(cat "$APP_PID_FILE")" 2>/dev/null || true
        sleep 2
    fi
    if [[ -f "$XEPHYR_PID_FILE" ]]; then
        kill -TERM -- "-$(cat "$XEPHYR_PID_FILE")" 2>/dev/null || true
    fi
    sleep 1

    local cfg
    cfg="$(config_file)"
    if [[ -f "$CONFIG_BACKUP" ]]; then
        cp "$CONFIG_BACKUP" "$cfg"
        echo "gui-probe: restored $cfg"
    fi
    rm -f "$XEPHYR_PID_FILE" "$APP_PID_FILE"
    echo "gui-probe: stopped"
}

cmd_shot() {
    require_running
    local out="${1:?usage: gui-probe.sh shot <out.png>}"
    # Settle first: the app logs while it renders, so a still-growing log means
    # a capture would catch a half-painted frame (or a black one at startup).
    cmd_settle 500 5
    import -display "$DPY" -window root "$out"
    echo "$out"
}

# Block until the app log has been unchanged for `quiet_ms`, i.e. rendering has
# stopped. More reliable than any single "ready" marker, which fires while
# images are still loading.
cmd_settle() {
    local quiet_ms="${1:-1000}" max_secs="${2:-30}"
    local prev="" cur quiet=0 ticks=0
    while :; do
        cur="$(wc -c <"$APP_LOG" 2>/dev/null || echo 0)"
        if [[ "$cur" == "$prev" ]]; then
            quiet=$((quiet + 250))
            [[ $quiet -ge $quiet_ms ]] && return 0
        else
            quiet=0
        fi
        prev="$cur"
        sleep 0.25
        ticks=$((ticks + 1))
        [[ $((ticks / 4)) -ge $max_secs ]] && return 0
    done
}

cmd_click() {
    require_running
    local x="${1:?usage: gui-probe.sh click <x> <y>}" y="${2:?}"
    xte -x "$DPY" "mousemove $x $y" >/dev/null
    sleep 0.3
    xte -x "$DPY" "mouseclick 1" >/dev/null
}

cmd_key() {
    require_running
    [[ $# -gt 0 ]] || die "usage: gui-probe.sh key <keysym>..."
    local k
    for k in "$@"; do
        xte -x "$DPY" "key $k" >/dev/null
        sleep 0.4
    done
}

cmd_type() {
    require_running
    xte -x "$DPY" "str ${1:?usage: gui-probe.sh type <text>}" >/dev/null
}

# Poll the app log for a regex. Returns non-zero on timeout so callers can fail
# loudly instead of screenshotting a state that never arrived.
cmd_wait() {
    local pattern="${1:?usage: gui-probe.sh wait <regex> [timeout_secs]}"
    local timeout="${2:-15}"
    local waited=0
    while ! grep -qE "$pattern" "$APP_LOG" 2>/dev/null; do
        sleep 0.5
        waited=$((waited + 1))
        if [[ $((waited / 2)) -ge $timeout ]]; then
            echo "gui-probe: timed out after ${timeout}s waiting for: $pattern" >&2
            return 1
        fi
    done
}

case "${1:-}" in
doctor) shift && cmd_doctor "$@" ;;
start) shift && cmd_start "$@" ;;
stop) shift && cmd_stop "$@" ;;
shot) shift && cmd_shot "$@" ;;
click) shift && cmd_click "$@" ;;
key) shift && cmd_key "$@" ;;
type) shift && cmd_type "$@" ;;
wait) shift && cmd_wait "$@" ;;
settle) shift && cmd_settle "$@" ;;
log) echo "$APP_LOG" ;;
tail) tail -n "${2:-20}" "$APP_LOG" ;;
*)
    sed -n '/^# Usage:/,/^# Env overrides/p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
    exit 1
    ;;
esac
