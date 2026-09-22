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
#   scripts/gui-probe.sh start [X,Y]      # Xephyr + app, waits until ready; the
#                                         # window opens at host pixel X,Y (default:
#                                         # the top-left of the second monitor)
#   BARKS_PROBE_HEADLESS=1 scripts/gui-probe.sh start   # same, on an invisible Xvfb
#   scripts/gui-probe.sh shot out.png     # fresh full-screen capture
#   scripts/gui-probe.sh geometry         # app window WxH+X+Y on the nested display
#   scripts/gui-probe.sh click 840 74     # click at screenshot coordinates
#   scripts/gui-probe.sh key Down Down Return
#   scripts/gui-probe.sh type "pirate gold"
#   scripts/gui-probe.sh wait 'Goto title' 10
#   scripts/gui-probe.sh settle           # block until rendering has stopped
#   scripts/gui-probe.sh log              # print the app log path
#   scripts/gui-probe.sh config           # print the app config (json) path
#   scripts/gui-probe.sh tail 20          # last N app log lines
#   scripts/gui-probe.sh stop             # kill both, restore the user config
#   scripts/gui-probe.sh stop-xserver     # kill an X server `stop` kept (see below)
#
# Env overrides: BARKS_PROBE_DISPLAY (:2), BARKS_PROBE_SCREEN (900x1300),
# BARKS_PROBE_ORIGIN (X,Y where the Xephyr window opens; `start X,Y` beats it),
# BARKS_PROBE_HEADLESS=1 (run on Xvfb instead of Xephyr: no host window, no
# graphical session needed; the app draws through Mesa's software renderer),
# BARKS_PROBE_KEY_GAP (seconds after each injected key, default 0.4),
# BARKS_READER_CONFIG_DIR (the profile to boot from, as for the app itself),
# BARKS_PROBE_NO_RESTORE=1 (do not back up and restore that profile around a run),
# BARKS_PROBE_KEEP_XSERVER=1 (`stop` leaves the X server up and `start` reuses it,
# so a run of many boots opens one Xephyr window - which takes the host keyboard
# focus once, not once per boot; `stop-xserver` ends it),
# BARKS_PROBE_APP (a built executable to run instead of `uv run main.py`; it gets
# the same config and data dir env vars, which the app honours when set).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DPY="${BARKS_PROBE_DISPLAY:-:2}"
SCREEN="${BARKS_PROBE_SCREEN:-900x1300}"
# Where the Xephyr window opens on the host display, as "X,Y" in host pixels.
# Empty means the top-left of the second (non-primary) monitor, so the probe
# stays off the screen being worked on. `start X,Y` overrides both.
ORIGIN="${BARKS_PROBE_ORIGIN:-}"
# Headless: Xvfb is the same kind of X server as Xephyr minus the host window,
# so every other command here (xte, xwininfo, import) works on it unchanged.
HEADLESS="${BARKS_PROBE_HEADLESS:-}"
KEEP_XSERVER="${BARKS_PROBE_KEEP_XSERVER:-}"
XSERVER="Xephyr"
[[ -n "$HEADLESS" ]] && XSERVER="Xvfb"
# One run directory per display, so several probes (parallel test workers on
# :2, :3, ...) never share a log, a pid file or a backup.
RUN_DIR="${XDG_RUNTIME_DIR:-/tmp}/barks-gui-probe-${DPY#:}"
# Every injected key and click, with the time it was sent, so a test failure
# can tell "the app ignored it" from "it was never sent" against app.log.
INPUT_LOG="$RUN_DIR/input.log"
# The pause after every injected key. The app drops keys pressed while it is
# rendering, so this is a floor the driver's own pacing sits on top of; the GUI
# test harness lowers it (BARKS_PROBE_KEY_GAP) to what a pacing study found safe.
KEY_GAP="${BARKS_PROBE_KEY_GAP:-0.4}"
APP_LOG="$RUN_DIR/app.log"
XEPHYR_LOG="$RUN_DIR/xephyr.log"
XEPHYR_PID_FILE="$RUN_DIR/xephyr.pid"
APP_PID_FILE="$RUN_DIR/app.pid"
CONFIG_BACKUP="$RUN_DIR/barks-reader.json.bak"
# The reading history is a separate store the app appends to on every comic
# open, so a probe session that opens comics permanently edits the user's
# reading journal unless it is saved and put back alongside the config.
HISTORY_BACKUP="$RUN_DIR/barks-reader-history.json.bak"

# The tree build finishing and the loading popup being dismissed is the last
# thing that happens before the app is interactive.
# The window is shown two seconds after the build finishes, and a key sent
# before then goes nowhere; under load that gap stretched and lost the first key.
READY_MARKER="Main window shown."

WINDOW_NAME="Compleat Barks Disney Reader"

# Tool -> Debian/Ubuntu package providing it.
declare -A TOOL_PKGS=(
    [Xephyr]=xserver-xephyr
    [Xvfb]=xvfb
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

# A failed `start` that has already written pid files must not leave the X
# server and half-booted app behind: the next `start` would refuse with
# "already running", and a test harness booting once per test would then fail
# every remaining test the same way.
abort_start() {
    # Everything goes, the X server included: a kept one may be the thing that failed.
    KEEP_XSERVER="" cmd_stop >&2 || true
    die "$@"
}

xserver_alive() {
    [[ -f "$XEPHYR_PID_FILE" ]] && kill -0 "$(cat "$XEPHYR_PID_FILE")" 2>/dev/null
}

app_alive() {
    [[ -f "$APP_PID_FILE" ]] && kill -0 "$(cat "$APP_PID_FILE")" 2>/dev/null
}

# The host-pixel origin of the second monitor, "X,Y". xrandr lists monitors as
# " 1: +HDMI-1 2560/600x1440/330+0+0  HDMI-1", the primary marked "+*"; take the
# first non-primary, else the first, else 0,0 (no xrandr, or one monitor).
second_monitor_origin() {
    local line
    line="$(xrandr --listmonitors 2>/dev/null | grep -E '^ *[0-9]+: \+[^*]' | head -1 || true)"
    [[ -z "$line" ]] && line="$(xrandr --listmonitors 2>/dev/null | grep -E '^ *[0-9]+:' | head -1 || true)"
    if [[ "$line" =~ \+(-?[0-9]+)\+(-?[0-9]+) ]]; then
        echo "${BASH_REMATCH[1]},${BASH_REMATCH[2]}"
    else
        echo "0,0"
    fi
}

# Turn "X,Y" into Xephyr's "+X+Y" screen offset, or die on anything else.
screen_offset() {
    local origin="$1"
    [[ "$origin" =~ ^(-?[0-9]+),(-?[0-9]+)$ ]] ||
        die "start position must be X,Y in host pixels, got '$origin'"
    echo "+${BASH_REMATCH[1]}+${BASH_REMATCH[2]}"
}

history_file() {
    echo "$(dirname "$(config_file)")/barks-reader-history.json"
}

config_file() {
    # An exported BARKS_READER_CONFIG_DIR wins, exactly as it does for the app
    # (main.py loads .env.runtime without overriding the environment), so a
    # harness can point a whole run at a scratch config dir.
    local dir="${BARKS_READER_CONFIG_DIR:-}"
    if [[ -z "$dir" ]]; then
        dir="$(grep -oP '(?<=^BARKS_READER_CONFIG_DIR=").*(?="$)' "$REPO_ROOT/.env.runtime" 2>/dev/null || true)"
    fi
    dir="${dir/\$\{HOME\}/$HOME}"
    echo "${dir:-$HOME/opt/barks-reader/config}/barks-reader.json"
}

# The app data directory: an exported BARKS_READER_DATA_DIR, else .env.runtime's.
data_dir() {
    local dir="${BARKS_READER_DATA_DIR:-}"
    if [[ -z "$dir" ]]; then
        dir="$(grep -oP '(?<=^BARKS_READER_DATA_DIR=").*(?="$)' "$REPO_ROOT/.env.runtime" 2>/dev/null || true)"
    fi
    dir="${dir/\$\{HOME\}/$HOME}"
    echo "${dir:-$HOME/opt/barks-reader}"
}

# The app window's geometry on the nested display as WxH+X+Y, or nothing.
app_geometry() {
    DISPLAY="$DPY" xwininfo -root -children |
        grep -F "$WINDOW_NAME" | grep -oP '\d+x\d+\+\d+\+\d+' | head -1 || true
}

require_running() {
    [[ -f "$XEPHYR_PID_FILE" ]] || die "not started - run 'gui-probe.sh start' first"
    kill -0 "$(cat "$XEPHYR_PID_FILE")" 2>/dev/null || die "$XSERVER died; see $XEPHYR_LOG"
}

# Check everything a fresh machine needs. Tools and secrets are hard failures;
# a missing data directory only limits what can be verified, so it warns.
cmd_doctor() {
    local fail=0 warn=0 missing_pkgs=()

    echo "== host display =="
    if [[ -n "$HEADLESS" ]]; then
        echo "  OK   headless (Xvfb needs no host display)"
    elif [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]; then
        echo "  OK   graphical session (Xephyr needs one to open its window in)"
    else
        echo "  FAIL no DISPLAY or WAYLAND_DISPLAY - run from a desktop session, or headless"
        fail=1
    fi

    echo "== tools =="
    local tool
    for tool in "$XSERVER" xte xdpyinfo xwininfo import convert uv; do
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
    local origin="${1:-${ORIGIN:-$(second_monitor_origin)}}"
    local offset
    offset="$(screen_offset "$origin")"
    for tool in "$XSERVER" xte import; do
        command -v "$tool" >/dev/null ||
            die "missing required tool: $tool (run 'gui-probe.sh doctor')"
    done
    # A live X server is reused only in keep mode and only without a live app.
    local xserver_up=""
    if xserver_alive; then
        if app_alive || [[ -z "$KEEP_XSERVER" ]]; then
            die "already running (stop it first)"
        fi
        xserver_up=1
    fi

    mkdir -p "$RUN_DIR"
    : >"$APP_LOG"
    : >"$INPUT_LOG"

    # The app rewrites its config on exit; keep the user's copy intact. A
    # harness booting from a throwaway profile sets BARKS_PROBE_NO_RESTORE=1
    # instead, so that what the app wrote on exit is still there to assert on.
    if [[ -z "${BARKS_PROBE_NO_RESTORE:-}" ]]; then
        local cfg
        cfg="$(config_file)"
        [[ -f "$cfg" ]] && cp "$cfg" "$CONFIG_BACKUP"
        local hist
        hist="$(history_file)"
        [[ -f "$hist" ]] && cp "$hist" "$HISTORY_BACKUP"
    fi

    if [[ -n "$xserver_up" ]]; then
        echo "gui-probe: reusing $XSERVER on $DPY"
    else
        start_xserver "$offset" "$origin"
    fi

    # A built executable reads no .env.runtime, so it gets the data dir the
    # workspace run would read from there (the config dir env var, when set, is
    # already in the environment for both).
    if [[ -n "${BARKS_PROBE_APP:-}" ]]; then
        setsid env DISPLAY="$DPY" BARKS_READER_DATA_DIR="$(data_dir)" "$BARKS_PROBE_APP" \
            </dev/null >>"$APP_LOG" 2>&1 &
    else
        setsid env DISPLAY="$DPY" uv run --directory "$REPO_ROOT" main.py \
            </dev/null >>"$APP_LOG" 2>&1 &
    fi
    echo $! >"$APP_PID_FILE"
    disown

    echo "gui-probe: waiting for the app to become interactive..."
    cmd_wait "$READY_MARKER" 120 || abort_start "app never became ready; see $APP_LOG"
    # The marker fires when the tree is built, ~1s before the first paint finishes.
    cmd_settle 1000 30

    # No window manager runs on the nested display, so X input focus follows the
    # pointer (PointerRoot). Park it inside the window or keystrokes go nowhere.
    park_pointer
    echo "gui-probe: ready. Log: $APP_LOG"
}

# Launch the X server for this display and wait until it answers.
start_xserver() {
    local offset="$1" origin="$2"
    # Detach fully (stdin included). A background child that still holds the
    # caller's stdin/stdout keeps the calling shell's pipeline open, so `start`
    # would appear to hang until the app exits.
    if [[ -n "$HEADLESS" ]]; then
        # Colour depth 24 gives Mesa a GLX visual the app's window can use.
        setsid Xvfb "$DPY" -screen 0 "${SCREEN}x24" </dev/null >"$XEPHYR_LOG" 2>&1 &
    else
        # The +X+Y offset is where the host window opens; Mutter honours it.
        setsid Xephyr "$DPY" -screen "${SCREEN}${offset}" -resizeable -title "barks-gui-probe" \
            </dev/null >"$XEPHYR_LOG" 2>&1 &
    fi
    echo $! >"$XEPHYR_PID_FILE"
    disown

    local waited=0
    until DISPLAY="$DPY" xdpyinfo >/dev/null 2>&1; do
        sleep 0.5
        waited=$((waited + 1))
        [[ $waited -gt 20 ]] && abort_start "$XSERVER did not come up; see $XEPHYR_LOG"
    done
    if [[ -n "$HEADLESS" ]]; then
        echo "gui-probe: Xvfb up on $DPY ($SCREEN, headless)"
    else
        echo "gui-probe: Xephyr up on $DPY ($SCREEN at $origin)"
    fi
}

park_pointer() {
    local geom w h
    geom="$(app_geometry)"
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

# Terminate a setsid process group and wait for its leader to exit, escalating
# to SIGKILL after `max_secs`. Waiting on the pid rather than a fixed sleep is
# what lets the app finish writing its config on the way out, and what stops a
# `start` issued straight after a `stop` from finding the old Xephyr still up.
stop_group() {
    local pid="$1" max_secs="${2:-10}" waited=0
    kill -TERM -- "-$pid" 2>/dev/null || true
    while kill -0 "$pid" 2>/dev/null; do
        sleep 0.25
        waited=$((waited + 1))
        if [[ $((waited / 4)) -ge $max_secs ]]; then
            kill -KILL -- "-$pid" 2>/dev/null || true
            break
        fi
    done
}

cmd_stop() {
    # setsid made each child its own process-group leader, so a negative pid
    # takes the whole group (uv wrapper plus the python process it execs).
    if [[ -f "$APP_PID_FILE" ]]; then
        stop_group "$(cat "$APP_PID_FILE")"
    fi
    if [[ -f "$XEPHYR_PID_FILE" ]] && [[ -z "$KEEP_XSERVER" ]]; then
        stop_group "$(cat "$XEPHYR_PID_FILE")"
    fi

    local cfg
    cfg="$(config_file)"
    if [[ -f "$CONFIG_BACKUP" ]]; then
        cp "$CONFIG_BACKUP" "$cfg"
        echo "gui-probe: restored $cfg"
    fi
    local hist
    hist="$(history_file)"
    if [[ -f "$HISTORY_BACKUP" ]]; then
        cp "$HISTORY_BACKUP" "$hist"
        echo "gui-probe: restored $hist"
    fi
    # The backups are spent once applied. `start` takes a fresh pair; one left
    # here would be re-applied by every later `stop`, on top of whatever the
    # caller (record_demo restores its own pristine copy) had since put back.
    rm -f "$CONFIG_BACKUP" "$HISTORY_BACKUP"
    rm -f "$APP_PID_FILE"
    if [[ -n "$KEEP_XSERVER" ]] && xserver_alive; then
        echo "gui-probe: stopped (the $XSERVER on $DPY is kept)"
    else
        rm -f "$XEPHYR_PID_FILE"
        echo "gui-probe: stopped"
    fi
}

# End an X server that `stop` kept. Safe when nothing is up.
cmd_stop_xserver() {
    if app_alive; then
        die "the app is still running on $DPY - stop it first"
    fi
    if [[ -f "$XEPHYR_PID_FILE" ]]; then
        stop_group "$(cat "$XEPHYR_PID_FILE")"
        rm -f "$XEPHYR_PID_FILE"
        echo "gui-probe: $XSERVER on $DPY stopped"
    else
        echo "gui-probe: no $XSERVER on $DPY"
    fi
}

# Print the app window's geometry (WxH+X+Y). Pixel-driven callers check this
# against the size their coordinates were measured at before clicking.
cmd_geometry() {
    require_running
    local geom
    geom="$(app_geometry)"
    [[ -n "$geom" ]] || die "app window ($WINDOW_NAME) not found on $DPY"
    echo "$geom"
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
    echo "$(date +%H:%M:%S.%3N) click $x $y" >>"$INPUT_LOG"
    xte -x "$DPY" "mousemove $x $y" >/dev/null
    sleep 0.3
    xte -x "$DPY" "mouseclick 1" >/dev/null
}

cmd_key() {
    require_running
    [[ $# -gt 0 ]] || die "usage: gui-probe.sh key <keysym>..."
    local k
    for k in "$@"; do
        echo "$(date +%H:%M:%S.%3N) key $k" >>"$INPUT_LOG"
        xte -x "$DPY" "key $k" >/dev/null
        sleep "$KEY_GAP"
    done
}

cmd_type() {
    require_running
    local text="${1:?usage: gui-probe.sh type <text>}"
    # Logged like keys are: the harness counts one key press per character.
    echo "$(date +%H:%M:%S.%3N) type $text" >>"$INPUT_LOG"
    xte -x "$DPY" "str $text" >/dev/null
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
stop-xserver) shift && cmd_stop_xserver "$@" ;;
shot) shift && cmd_shot "$@" ;;
geometry) shift && cmd_geometry "$@" ;;
click) shift && cmd_click "$@" ;;
key) shift && cmd_key "$@" ;;
type) shift && cmd_type "$@" ;;
wait) shift && cmd_wait "$@" ;;
settle) shift && cmd_settle "$@" ;;
log) echo "$APP_LOG" ;;
config) config_file ;;
tail) tail -n "${2:-20}" "$APP_LOG" ;;
*)
    sed -n '/^# Usage:/,/^# Env overrides/p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
    exit 1
    ;;
esac
