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
#      JSON array the app stores in AAA_Settings.last_selected_node. Leaf
#      stories go in by enum name (LOST_IN_THE_ANDES), not display title, and
#      the chain has to be exact - the app selects nothing if it is not. The
#      surest way to get one is to navigate there by hand once and read back
#      what the app saved. Booting expands the path, so the node's children are
#      already on screen and a beat can walk straight into them.
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
#   scripts/record-demo.sh --from read_story
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

# Every beat that gets recorded, in canonical order.
BEATS=(
    browse_tree
    series_view
    search_story
    search_words
    open_comic
    read_story
    wiki_jump
    speech_index
    censored_stories
    history
)

# What gets stitched, and from which beats. A beat can appear in more than one
# output; it is only ever recorded once. The short hero loop is what autoplays
# at the top of the intro tab; the walkthrough is the linked long-form tour.
declare -A OUTPUTS=(
    [demo.mp4]="browse_tree open_comic"
    [walkthrough.mp4]="browse_tree series_view search_story search_words read_story wiki_jump speech_index censored_stories history"
)

# Take the poster frame from the end of this beat rather than the end of the
# whole video: the browse view carries the app's chrome, tree and title card,
# which says "this is a reader app" better than a bare comic page does. Empty
# means the last frame of the finished video.
POSTER_BEAT=browse_tree

# Stories the censored_stories beat opens, named by the app's title enum - the
# name the app logs in "New selected node". Change this list to change the demo;
# nothing else needs touching.
#
# They must be listed in TREE order, which is chronological, because the beat
# only ever walks downward. The node holds these seventeen, in this order:
#
#   GOOD_DEEDS FROZEN_GOLD ICEBOX_ROBBER_THE FIREBUG_THE SILENT_NIGHT
#   TERROR_OF_THE_RIVER_THE SWIMMING_SWINDLERS BILL_COLLECTORS_THE
#   GOLDEN_CHRISTMAS_TREE_THE LOST_IN_THE_ANDES VOODOO_HOODOO TRICK_OR_TREAT
#   BACK_TO_THE_KLONDIKE GOLDEN_FLEECING_THE LAND_BENEATH_THE_GROUND
#   LOVELORN_FIREMAN_THE BONGO_ON_THE_CONGO
#
# To regenerate that list after a tag change:
#   uv run python -c "
#   from barks_fantagraphics.barks_tags import BARKS_TAGGED_TITLES
#   from barks_fantagraphics.barks_tags_enums import Tags
#   from barks_fantagraphics.barks_titles import Titles
#   order = {t: i for i, t in enumerate(Titles)}
#   print([t.name for t in sorted(
#       BARKS_TAGGED_TITLES[Tags.CENSORED_STORIES_BUT_FIXED], key=lambda t: order[t])])"
CENSORED_PICKS=(GOOD_DEEDS SILENT_NIGHT BILL_COLLECTORS_THE LOST_IN_THE_ANDES)

# How many pages to read from each opened story, counting the page it opens on.
# 2 means the cued page plus one turn; 1 means open and close without turning.
PAGES_PER_PICK=2
# Seconds to dwell on each page of an opened story.
PICK_DWELL=2.5

# What the two search beats type. Keep them short - every character is typed
# with a visible pause, so a long query makes for a slow beat.
SEARCH_TITLE_QUERY="gold"
SEARCH_WORD_QUERY="egg"

# The story the read_story beat opens. Must be in the censored-but-fixed node,
# same as CENSORED_PICKS, because that is the branch its setup walks.
READ_STORY_PICK=LOST_IN_THE_ANDES

# Caption burned into the bottom of each beat. A walkthrough this long is
# unreadable silent - the viewer can see what happens but not why - and a
# caption keeps the whole thing regenerable in a way a voice-over would not.
# Keep them short and free of ':' and \''' (ffmpeg drawtext metacharacters).
LABEL_browse_tree="Every Barks Disney story, in order"
LABEL_series_view="Or by the series they ran in"
LABEL_search_story="Find a story by name"
LABEL_search_words="Search every word the characters speak"
LABEL_open_comic="Open any story and read it"
LABEL_read_story="Two-page spreads, the way it was printed"
LABEL_wiki_jump="Every story linked to the Carl Barks Wiki"
LABEL_speech_index="A full speech-bubble index, A to Z"
LABEL_censored_stories="Browse by theme - censored stories, restored"
LABEL_history="Pick up where you left off"

FONT=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
CAPTION_SIZE=30
# Pace of a single Down while walking the tree on camera.
WALK_PAUSE=0.45

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
    # it. It could boot straight onto the title node instead - leaf titles are
    # stored under their enum name, as NODE_wiki_jump does - but repeating the
    # previous beat's four Downs is what makes the two cuts line up.
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
    key_then_wait "Showed page $1" 15 Right
    hold 2.2
}

NODE_censored_stories='["The Stories", "root"]'
beat_censored_stories() {
    # Drill down The Stories > Categories > Themes > censored but fixed stories,
    # then open each configured pick. The drill-down stays on camera: the
    # thematic indexes are the point of the beat, not just the stories.
    hold 1.0
    open_branch Categories
    open_branch Themes
    open_branch "censored but fixed stories"
    hold 1.0

    local title
    for title in "${CENSORED_PICKS[@]}"; do
        select_node "$title"
        hold 0.8
        open_selected_title
    done
}

# Walk down to a collapsed node and expand it.
open_branch() {
    select_node "$1"
    hold 0.3
    probe key Return
    probe settle
    hold 0.4
}

# Open the selected title, dwell on its first page, and come back to the tree.
open_selected_title() {
    probe key Return # focus the title view read portal
    hold 0.6
    key_then_wait "All images loaded" 30 Return
    hold "$PICK_DWELL"
    # Right is next-page. Wait on the bare "Showed page" marker rather than a
    # page number: each story opens on its own cued page, so the number differs
    # per pick and key_then_wait only needs a NEW render, not a specific one.
    local i
    for ((i = 1; i < PAGES_PER_PICK; i++)); do
        key_then_wait "Showed page" 15 Right
        hold "$PICK_DWELL"
    done
    probe key Escape # reader menu mode; Go Back is focused by default
    hold 0.4
    key_then_wait "Main screen is active" 15 Return
    hold 0.5
    # Closing the reader leaves focus in the bottom region, where Down does
    # nothing to the tree. Escape hands it back (main_screen_nav:243).
    probe key Escape
    probe settle
}

NODE_series_view='["Series", "The Stories", "root"]'
beat_series_view() {
    # Booting here has already expanded Series, so the three series are on
    # screen and this only has to walk into them.
    hold 1.2
    select_node "Comics and Stories"
    hold 0.9
    select_node "Donald Duck Adventures"
    hold 0.9
    select_node "Uncle Scrooge Adventures"
    hold 1.0
    probe key Return # expand it to show the volumes
    probe settle
    hold 2.0
}

NODE_search_story='["Titles", "Search", "root"]'
beat_search_story() {
    hold 1.0
    probe key Return # open the title search and focus its box
    probe settle
    hold 0.6
    type_slowly "$SEARCH_TITLE_QUERY"
    probe settle
    hold 1.2
    probe key Down # move focus from the box into the result list
    probe settle
    hold 0.8
    probe key Return # jump the tree to that story
    probe settle
    hold 2.5
}

NODE_search_words='["Words", "Search", "root"]'
beat_search_words() {
    hold 1.0
    probe key Return
    probe settle
    hold 0.6
    type_slowly "$SEARCH_WORD_QUERY"
    probe settle
    hold 1.5
    probe key Down # focus the first matching word chip
    probe settle
    hold 0.6
    key_then_wait "Word search: selected chip" 15 Return
    hold 3.5 # the list of every story the word is spoken in
}

NODE_read_story="$NODE_censored_stories"
setup_read_story() {
    # Off camera: reach the story this beat reads, so the recording opens on it.
    open_branch Categories
    open_branch Themes
    open_branch "censored but fixed stories"
    select_node "$READ_STORY_PICK"
}
beat_read_story() {
    hold 1.0
    probe settle
    probe key Return # focus the title view read portal
    hold 0.6
    key_then_wait "All images loaded" 30 Return
    hold "$PICK_DWELL"
    key_then_wait "Showed page" 15 Right
    hold "$PICK_DWELL"
    # Reader action bar order is fullscreen, double page, start, end, goto, close,
    # and menu mode opens focused on close - so two Rights wrap round to the
    # double-page button. Fullscreen is deliberately not shown: with no window
    # manager on the nested display it resizes the window, and the recorder is
    # grabbing a fixed region.
    probe key Escape
    hold 0.5
    probe key Right
    hold 0.4
    probe key Right
    hold 0.4
    probe key Return
    probe settle
    hold 3.5
}

NODE_wiki_jump='["LOST_IN_THE_ANDES", "censored but fixed stories", "Themes", "Categories", "The Stories", "root"]'
beat_wiki_jump() {
    hold 1.5
    # Right enters the title view at its first nav widget; the wiki button is
    # always the second when a story has a wiki page, so one Down reaches it
    # whatever else the title view is showing.
    probe key Right
    probe settle
    hold 0.5
    probe key Down
    probe settle
    hold 0.8
    key_then_wait "Wiki reader screen is active" 30 Return
    hold 2.5
    local i
    for ((i = 0; i < 3; i++)); do
        probe key Down
        hold 0.9
    done
    hold 1.0
}

NODE_speech_index='["Speech Bubble Index", "Indexes", "root"]'
beat_speech_index() {
    hold 1.2
    probe key Return # open the index screen
    probe settle
    hold 2.5
    # Walk the A-Z letters; each one repopulates the word grid.
    local i
    for ((i = 0; i < 3; i++)); do
        key_then_wait "Populated index page for letter" 15 Down
        hold 1.6
    done
    hold 1.0
}

NODE_history='["History", "Reading", "root"]'
beat_history() {
    hold 1.2
    probe key Return # open the reading journal
    probe settle
    hold 4.0
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

# Type into a focused text box one character at a time.
#
# `gui-probe type` sends the whole string through `xte str`, and the app's
# search-as-you-type handler drops most of it - "square egg" arrived as "squa".
# Per-character with a gap is both reliable and a more natural pace on video.
type_slowly() {
    local text="$1" i ch
    for ((i = 0; i < ${#text}; i++)); do
        ch="${text:i:1}"
        "$PROBE" type "$ch" >/dev/null
        sleep "${TYPE_PAUSE:-0.4}"
    done
}

# The node the app last logged as selected. Title nodes log their enum name
# (FROZEN_GOLD), category nodes their text ("Themes").
current_node() {
    grep -oP '(?<=New selected node: ")[^"]+' "$APP_LOG" | tail -1
}

# Walk the tree downward until `want` is the selected node. Name-driven rather
# than a counted run of Downs, so a title added upstream shifts the walk instead
# of silently landing the demo on the wrong story. Only ever goes down, so picks
# have to be in tree order.
select_node() {
    local want="$1" max="${2:-60}" i cur prev stalled=0
    cur="$(current_node)"
    for ((i = 0; i < max; i++)); do
        [[ "$cur" == "$want" ]] && return 0
        prev="$cur"
        probe key Down
        sleep "$WALK_PAUSE"
        cur="$(current_node)"
        if [[ "$cur" == "$prev" ]]; then
            # One swallowed keypress during a render is normal; two in a row
            # means the selection cannot move any further down.
            stalled=$((stalled + 1))
            if [[ $stalled -ge 2 ]]; then
                die "tree stopped at \"$cur\" before reaching \"$want\" - is it above the current position, or in another branch?"
            fi
        else
            stalled=0
        fi
    done
    die "never reached node \"$want\" in $max steps"
}

# How many times `pattern` has appeared in the log so far.
match_count() {
    grep -cE "$1" "$APP_LOG" 2>/dev/null || true
}

# Press keys, then block until a NEW occurrence of `pattern` lands. gui-probe's
# own `wait` greps the whole log, so a marker that fires once per comic matches
# the previous comic and returns instantly - which would cut away from a story
# before it had drawn.
key_then_wait() {
    local pattern="$1" timeout="$2"
    shift 2
    local before waited=0
    before="$(match_count "$pattern")"
    probe key "$@"
    while [[ "$(match_count "$pattern")" -le "$before" ]]; do
        sleep 0.5
        waited=$((waited + 1))
        if [[ $((waited / 2)) -ge $timeout ]]; then
            die "beat stalled: no new /$pattern/ in the app log after ${timeout}s"
        fi
    done
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
APP_LOG="$("$PROBE" log)"
MY_BACKUP="$(mktemp -t barks-demo-config.XXXXXX.json)"

cleanup() {
    # No `set -e` in here: a failure part way through would skip the config
    # restore below and leave the user's saved node pointing at a beat's start.
    set +e
    if [[ -n "$FF_PID" ]]; then
        kill -INT "$FF_PID" 2>/dev/null
        wait "$FF_PID" 2>/dev/null
    fi
    "$PROBE" stop >/dev/null 2>&1
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
    # The caption is burned in at record time, not at stitch time, because the
    # stitch is a stream copy - there is no re-encode later to draw it into.
    local label_var="LABEL_$name" vf=()
    if [[ -n "${!label_var:-}" ]]; then
        vf=(-vf "drawtext=fontfile=$FONT:text='${!label_var}':fontcolor=white:fontsize=$CAPTION_SIZE:box=1:boxcolor=black@0.6:boxborderw=16:x=(w-text_w)/2:y=h-th-36")
    fi
    ffmpeg -y -loglevel error -nostdin \
        -f x11grab -framerate "$FPS" -draw_mouse 0 \
        -video_size "${w}x${h}" -i "${DPY}+${x},${y}" \
        "${vf[@]+"${vf[@]}"}" \
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
        if [[ $started -eq 1 ]]; then
            to_record+=("$b")
        fi
    done
else
    to_record=("${BEATS[@]}")
fi

for b in ${to_record[@]+"${to_record[@]}"}; do
    record_beat "$b"
done

# ------------------------------------------------------------------ stitch --

# One concat per output. Beats are shared between outputs and recorded once.
stitch_output() {
    local out_name="$1" beat_list="$2"
    local final="$OUT_DIR/$out_name"
    local list_file="$WORK_DIR/concat-${out_name%.mp4}.txt"
    local missing=() b

    : >"$list_file"
    for b in $beat_list; do
        if [[ -s "$WORK_DIR/$b.mp4" ]]; then
            echo "file '$WORK_DIR/$b.mp4'" >>"$list_file"
        else
            missing+=("$b")
        fi
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        die "$out_name: no clip for ${missing[*]} - record them first, or drop them from OUTPUTS"
    fi

    # Stream copy: the beats already share an encode, so this re-muxes without
    # re-compressing. +faststart puts the index first so the browser can start
    # playing before the whole file has arrived.
    ffmpeg -y -loglevel error -f concat -safe 0 -i "$list_file" \
        -c copy -movflags +faststart "$final"

    local dur
    dur="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$final")"
    echo "record-demo: $final  ($(du -h "$final" | cut -f1), ${dur%.*}s)"
}

echo
for out_name in "${!OUTPUTS[@]}"; do
    stitch_output "$out_name" "${OUTPUTS[$out_name]}"
done

poster="$OUT_DIR/demo-poster.jpg"
poster_src="$OUT_DIR/demo.mp4"
[[ -n "$POSTER_BEAT" && -s "$WORK_DIR/$POSTER_BEAT.mp4" ]] &&
    poster_src="$WORK_DIR/$POSTER_BEAT.mp4"
ffmpeg -y -loglevel error -sseof -0.5 -i "$poster_src" -update 1 -q:v 4 "$poster"
echo "record-demo: $poster ($(du -h "$poster" | cut -f1))"
