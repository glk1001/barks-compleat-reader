#!/usr/bin/env bash
#
# Record the website demo clip by driving the app on the nested Xephyr display.
#
# For each beat in BEATS: boot the app onto that beat's start node via
# gui-probe.sh, record the app window with ffmpeg x11grab while the beat
# function injects keystrokes, then concatenate the beat clips into
# website/demo.mp4 and write a poster frame beside it.
#
# Why beats rather than one long take
#   Every beat is an independent clip encoded with identical parameters, so the
#   concatenation is a stream copy (lossless, instant) and re-shooting or adding
#   one beat costs only that beat's runtime instead of a whole re-record. Beat
#   clips persist in build/demo-beats/, so `--only <beat>` re-shoots one and
#   still rebuilds the complete video.
#
# To add a beat
#   1. Append its name to BEATS (order here is the order on screen).
#   2. Define NODE_<name> - the tree node to boot onto, leaf-to-root, as the
#      JSON array the app stores in AAA_Settings.last_selected_node.
#   3. Define beat_<name> - the keystrokes, using probe/hold/wait_for below.
#   Optionally define setup_<name>, which runs after the app is up but BEFORE
#   the recording starts, for navigation that should not appear on screen.
#   Keep anything that must play without a cut inside a single beat.
#
# Assumes
#   - `scripts/gui-probe.sh doctor` passes (Xephyr, xte, the app's data dirs).
#   - A graphical session for the nested display to open in, and nothing else
#     already on BARKS_PROBE_DISPLAY.
#   - ffmpeg built with libx264.
#
# The app rewrites its config on exit, so this backs up barks-reader.json before
# touching last_selected_node and restores it on any exit, including a failure
# or a Ctrl-C. It never writes to barks-reader.ini.
#
# Usage:
#   scripts/record-demo.sh                  # all beats -> website/demo.mp4
#   scripts/record-demo.sh --list
#   scripts/record-demo.sh --only browse_tree
#   scripts/record-demo.sh --from open_title
#   scripts/record-demo.sh --stitch         # rebuild from cached beats, no app
#   scripts/record-demo.sh --out /tmp/preview
#   scripts/record-demo.sh --clean          # drop cached beat clips first
#
# Env overrides: BARKS_PROBE_DISPLAY (:2), BARKS_PROBE_SCREEN (900x1300) - both
# are passed straight through to gui-probe.sh.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROBE="$REPO_ROOT/scripts/gui-probe.sh"
DPY="${BARKS_PROBE_DISPLAY:-:2}"

OUT_DIR="$REPO_ROOT/website"
WORK_DIR="$REPO_ROOT/build/demo-beats"
ONLY=""
FROM=""
CLEAN=0
STITCH_ONLY=0

# Encode settings, shared by every beat so the concat can be a stream copy.
# CRF 30 holds up on flat comic art and keeps a 15s clip under a megabyte; the
# 2-second keyframe interval gives the browser somewhere to seek to.
FPS=30
CRF=30
GOP=60

# ---------------------------------------------------------------- the beats --

BEATS=(browse_tree open_comic)

# Take the poster frame from the end of this beat rather than the end of the
# whole video: the browse view carries the app's chrome, tree and title card,
# which says "this is a reader app" better than a bare comic page does. Empty
# means the last frame of the finished video.
POSTER_BEAT=browse_tree

NODE_browse_tree='["1947-1950", "Comics and Stories", "Series", "The Stories", "root"]'
beat_browse_tree() {
    # Arrow down the chronological list and settle on a title, letting the
    # bottom panel render its title view. Keyboard only: this doubles as the
    # 10-foot/remote story, and it keeps the pointer out of the frame.
    hold 1.2
    local i
    for i in 1 2 3 4; do
        probe key Down
        hold 0.75
    done
    probe settle
    hold 2.2
}

NODE_open_comic="$NODE_browse_tree"
setup_open_comic() {
    # Land on the title browse_tree settles on, off camera, so this beat opens
    # already on the title view and reads as a continuation of the cut before
    # it. Driving here rather than booting straight onto the title node is
    # deliberate: last_selected_node for a leaf title did not restore in
    # testing (the app came up with nothing selected), whereas the range node
    # plus four Downs is exactly what the previous beat already does.
    probe key Down Down Down Down
    probe settle
}
beat_open_comic() {
    hold 0.8
    probe key Return # focus the title view's read portal
    hold 0.7
    probe key Return # open the comic
    wait_for "All images loaded" 30
    hold 2.0
    turn_page 1
    turn_page 2
    hold 0.8
}

# Right is next-page in the reader (reader_keyboard_nav._handle_reading_key).
# Waiting on the render keeps the dwell honest when a page loads slowly.
turn_page() {
    probe key Right
    wait_for "Showed page $1" 15
    hold 2.2
}

# --------------------------------------------------------- beat primitives --

# Inject keys on the nested display.
probe() {
    "$PROBE" "$@" >/dev/null
}

# Dwell on the current frame. Pacing only - never use this to wait for the app
# to reach a state; use `probe wait '<log regex>' <secs>` for that, which fails
# loudly instead of silently recording the wrong screen.
hold() {
    sleep "$1"
}

# Block until the app log shows a state was reached. Unlike `hold`, this fails
# the run instead of recording whatever happened to be on screen.
wait_for() {
    "$PROBE" wait "$1" "${2:-15}" >/dev/null ||
        die "beat stalled: never saw /$1/ in the app log"
}

die() {
    echo "record-demo: $*" >&2
    exit 1
}

# --------------------------------------------------------------- machinery --

usage() {
    sed -n '/^# Usage:/,/^# Env overrides/p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --list)
            printf '%s\n' "${BEATS[@]}"
            exit 0
            ;;
        --only) ONLY="${2:?--only needs a beat name}"; shift 2 ;;
        --from) FROM="${2:?--from needs a beat name}"; shift 2 ;;
        --out) OUT_DIR="${2:?--out needs a directory}"; shift 2 ;;
        --stitch) STITCH_ONLY=1; shift ;;
        --clean) CLEAN=1; shift ;;
        -h | --help) usage ;;
        *) die "unknown option: $1 (try --help)" ;;
    esac
done

has_beat() {
    local want="$1" b
    for b in "${BEATS[@]}"; do [[ "$b" == "$want" ]] && return 0; done
    return 1
}

[[ -n "$ONLY" ]] && ! has_beat "$ONLY" && die "no such beat: $ONLY"
[[ -n "$FROM" ]] && ! has_beat "$FROM" && die "no such beat: $FROM"

command -v ffmpeg >/dev/null || die "ffmpeg not found (sudo apt install ffmpeg)"
[[ -x "$PROBE" ]] || die "missing $PROBE"

FF_PID=""
CONFIG_JSON="$("$PROBE" config)"
MY_BACKUP="$(mktemp -t barks-demo-config.XXXXXX.json)"

cleanup() {
    [[ -n "$FF_PID" ]] && kill -INT "$FF_PID" 2>/dev/null && wait "$FF_PID" 2>/dev/null
    "$PROBE" stop >/dev/null 2>&1 || true
    # gui-probe restores its own backup, which is the file we edited; put the
    # user's original back on top of it.
    [[ -s "$MY_BACKUP" ]] && cp "$MY_BACKUP" "$CONFIG_JSON"
    rm -f "$MY_BACKUP"
}
trap cleanup EXIT

[[ -f "$CONFIG_JSON" ]] || die "app config not found: $CONFIG_JSON"
cp "$CONFIG_JSON" "$MY_BACKUP"

mkdir -p "$WORK_DIR" "$OUT_DIR"
[[ $CLEAN -eq 1 ]] && rm -f "$WORK_DIR"/*.mp4

# Point the app at a start node so each beat opens on a known screen instead of
# inheriting wherever the previous beat left the selection.
boot_at() {
    local node_json="$1"
    python3 - "$CONFIG_JSON" "$node_json" <<'PY'
import json
import sys

path, node = sys.argv[1], json.loads(sys.argv[2])
with open(path) as f:
    cfg = json.load(f)
cfg.setdefault("AAA_Settings", {})["last_selected_node"] = node
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
PY
    "$PROBE" start >/dev/null
}

# The app window on the nested display, as an even-sized x11grab region. There
# is no window manager there, so this is the app's own geometry with no
# decorations - cropping to it drops the Xephyr letterboxing.
app_region() {
    local geom w h x y
    geom="$(DISPLAY="$DPY" xwininfo -root -children |
        grep -F "Compleat Barks Disney Reader" |
        grep -oP '\d+x\d+\+\d+\+\d+' | head -1)" ||
        die "could not find the app window on $DPY"
    w="${geom%%x*}"
    geom="${geom#*x}"
    h="${geom%%+*}"
    x="$(cut -d+ -f2 <<<"$geom")"
    y="$(cut -d+ -f3 <<<"$geom")"
    # libx264 needs even dimensions.
    echo "$((w / 2 * 2)) $((h / 2 * 2)) $x $y"
}

record_beat() {
    local name="$1" node_var="NODE_$1" clip="$WORK_DIR/$1.mp4"
    local w h x y region

    echo "record-demo: [$name] booting"
    boot_at "${!node_var}"
    if declare -F "setup_$name" >/dev/null; then
        echo "record-demo: [$name] setup"
        "setup_$name"
    fi
    region="$(app_region)" || exit 1
    read -r w h x y <<<"$region"

    echo "record-demo: [$name] recording ${w}x${h} at +${x}+${y}"
    ffmpeg -y -loglevel error -nostdin \
        -f x11grab -framerate "$FPS" -draw_mouse 0 \
        -video_size "${w}x${h}" -i "${DPY}+${x},${y}" \
        -c:v libx264 -preset slow -crf "$CRF" -g "$GOP" \
        -pix_fmt yuv420p -an "$clip" &
    FF_PID=$!

    sleep 0.5 # let the first frames land before anything moves
    "beat_$name"

    # SIGINT makes ffmpeg stop cleanly and write the trailer; killing it outright
    # leaves an unplayable file.
    kill -INT "$FF_PID"
    wait "$FF_PID" || true
    FF_PID=""

    "$PROBE" stop >/dev/null
    echo "record-demo: [$name] $(du -h "$clip" | cut -f1)"
}

# Which beats to shoot this run. Beats not shot are reused from build/demo-beats.
to_record=()
if [[ $STITCH_ONLY -eq 1 ]]; then
    to_record=()
elif [[ -n "$ONLY" ]]; then
    to_record=("$ONLY")
elif [[ -n "$FROM" ]]; then
    started=0
    for b in "${BEATS[@]}"; do
        [[ "$b" == "$FROM" ]] && started=1
        [[ $started -eq 1 ]] && to_record+=("$b")
    done
else
    to_record=("${BEATS[@]}")
fi

for b in ${to_record[@]+"${to_record[@]}"}; do
    record_beat "$b"
done

# ------------------------------------------------------------------ stitch --

missing=()
list_file="$WORK_DIR/concat.txt"
: >"$list_file"
for b in "${BEATS[@]}"; do
    if [[ -s "$WORK_DIR/$b.mp4" ]]; then
        echo "file '$WORK_DIR/$b.mp4'" >>"$list_file"
    else
        missing+=("$b")
    fi
done
[[ ${#missing[@]} -gt 0 ]] &&
    die "no clip for: ${missing[*]} - run without --only/--from, or record them first"

final="$OUT_DIR/demo.mp4"
poster="$OUT_DIR/demo-poster.jpg"

# Stream copy: the beats already share an encode, so this re-muxes without
# re-compressing. +faststart puts the index first so the browser can start
# playing before the whole file has arrived.
ffmpeg -y -loglevel error -f concat -safe 0 -i "$list_file" \
    -c copy -movflags +faststart "$final"
poster_src="$final"
[[ -n "$POSTER_BEAT" && -s "$WORK_DIR/$POSTER_BEAT.mp4" ]] &&
    poster_src="$WORK_DIR/$POSTER_BEAT.mp4"
ffmpeg -y -loglevel error -sseof -0.5 -i "$poster_src" -update 1 -q:v 4 "$poster"

dur="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$final")"
echo
echo "record-demo: $final  ($(du -h "$final" | cut -f1), ${dur%.*}s)"
echo "record-demo: $poster ($(du -h "$poster" | cut -f1))"
