#!/usr/bin/env bash
#
# Drive a fullscreen Firefox comic reader: capture one screenshot per page,
# turning the page between shots with a mouse click (or a key).
#
#   scripts/comic-capture.sh --pages 40 'https://read.amazon.com/...'
#   scripts/comic-capture.sh --pages 40          # comic already open? just run it
#   scripts/comic-capture.sh --probe             # one shot + click targets, no turn
#   scripts/comic-capture.sh --out ~/comics/vol11 --pages 40
#   scripts/comic-capture.sh --split-spreads --pages 40   # spreads become two pages
#   scripts/comic-capture.sh --calibrate         # measure the pointer on a new machine
#
# Output is 001.png, 002.png, ... numbered by PAGE: a split spread takes two
# numbers, so the sequence is continuous and in reading order. --pages counts
# SCREENS to capture, which with spreads is about half the page count.
#
# Open the comic, press F11 for fullscreen, press Enter here, then click back
# on the Firefox window. Capture starts by itself once the window is fullscreen
# and has stopped changing -- that wait matters, because clicking the reader
# drops its toolbar over the page, and this way it has hidden again first.
#
# --- capturing, and why not the obvious ways ---------------------------------
# Host is GNOME Shell 50 on Wayland. The packaged gnome-screenshot is 41.0: its
# Shell D-Bus path is refused and its X11 fallback finds nothing, so it hangs
# and writes no file. grim needs wlr-screencopy, which Mutter does not
# implement. `import -window` cannot see Firefox at all -- the snap is a native
# Wayland client, absent from `wmctrl -l`.
#
# What works is GNOME's own `screenshot-window` keybinding (<Alt>Print) pressed
# via ydotool: it writes straight to the XDG Pictures/Screenshots folder, with
# no dialog and no portal. Verified fullscreen: exactly monitor-sized, edge to
# edge, no top bar, no decoration, no notification banner, and repeated grabs
# are always fresh.
#
# --- clicking, and the coordinate trap ---------------------------------------
# Kindle Cloud Reader turns pages on a CLICK, not on any key, so the script
# clicks by default. ydotool's device has NO absolute axes (EV=7: SYN|KEY|REL),
# so `mousemove -a` is a corner-pin plus a RELATIVE move that GNOME's pointer
# acceleration then scales -- a request of N pixels lands CLICK_DIV * N away.
# That factor is a property of the machine's POINTER SETTINGS, not its
# resolution, so it does not follow from the monitor size: run --calibrate on
# new hardware. Measured exactly 2.0 here; correct after dividing (want
# 2304,720 -> got 2304,720). Absolute clicks reach the primary monitor only, so
# a window on a second monitor cannot be clicked at all. Getting either wrong
# is silent -- the pointer just pins to an edge and every turn misses.
# `xdotool getmouselocation` cannot help -- it returns a frozen value here.
#
# Which monitor the window is on is found by capturing the whole desktop and
# the window, then testing which monitor-sized tile of the desktop matches the
# window pixel for pixel.
#
# --- other traps this script exists to avoid ---------------------------------
# * Capture follows KEYBOARD FOCUS, and pressing Enter focuses the terminal.
#   Alt+Tab does NOT fix it: GNOME's Alt+Tab switches *applications*, so with
#   several Firefox windows it raises the wrong one. The script polls instead.
# * Frames are compared by PIXEL signature, never by file checksum. GNOME
#   stamps a png:tIME chunk into every capture, so pixel-identical frames have
#   different md5s -- a checksum test silently never matches, and a reader that
#   ignores the page turn yields 40 copies of page 1.
#
set -euo pipefail

# --- CONFIGURATION ---------------------------------------------------------
PAGES="${PAGES:-40}"                 # SCREENS to capture (or --pages N)
OUTPUT_DIR="${OUTPUT_DIR:-$HOME/Pictures/comic_pages}"
# Output files are 001.png, 002.png, ... numbered by PAGE, not by capture: a
# spread that gets split consumes two numbers, so the sequence stays continuous
# and in reading order. Set PREFIX (or --prefix) for <PREFIX>_001.png instead.
PREFIX="${PREFIX:-}"

# How to turn the page: "click" (default) or "key".
FLIP_MODE="${FLIP_MODE:-click}"

# Click targets, as fractions of the window, tried in order until one changes
# the page. Kindle's forward zone is the right-hand side; the last entry is the
# "next" chevron at the right edge. Override with --click X,Y in window pixels.
CLICK_TARGETS="${CLICK_TARGETS:-0.92,0.50 0.97,0.50 0.80,0.50}"

# Where to leave the pointer after each click, as a fraction of the window.
# Mid-page keeps it off both edge chevrons. "none" leaves it on the click spot.
PARK="${PARK:-0.5,0.5}"

# Key mode: "auto" tries each candidate on the first turn and keeps what works.
FLIP_KEYCODE="${FLIP_KEYCODE:-auto}"
FLIP_CANDIDATES="${FLIP_CANDIDATES:-106 109 57 108}"   # Right PageDown Space Down

# Pointer calibration. ydotool's virtual device has NO absolute axes (EV=7:
# SYN|KEY|REL), so `mousemove -a` is really a corner-pin plus a RELATIVE move,
# and GNOME's pointer acceleration then scales that delta. The upshot is that
# a request of N pixels lands CLICK_DIV * N pixels away, and the factor belongs
# to the machine's pointer settings -- not to its resolution. Measured 2.0 on
# the dual-2560x1440 host this was written on; run --calibrate on any other
# machine rather than trusting that. Getting it wrong is silent: the pointer
# simply pins to a screen edge and every page turn misses.
CLICK_DIV_X="${CLICK_DIV_X:-2.0}"
CLICK_DIV_Y="${CLICK_DIV_Y:-2.0}"

LOAD_WAIT="${LOAD_WAIT:-6}"          # seconds to wait after opening the URL
REQUIRE_FULLSCREEN="${REQUIRE_FULLSCREEN:-1}"
READY_TIMEOUT="${READY_TIMEOUT:-90}" # how long to wait for a settled fullscreen window
POLL_INTERVAL="${POLL_INTERVAL:-3}"  # seconds between readiness probes
SWITCH_DELAY="${SWITCH_DELAY:-5}"    # REQUIRE_FULLSCREEN=0: seconds to switch back

TURN_WAIT="${TURN_WAIT:-1.5}"        # seconds after a turn before the first capture
SETTLE_TRIES="${SETTLE_TRIES:-8}"    # captures allowed while waiting for the toolbar to hide
SETTLE_GAP="${SETTLE_GAP:-1.5}"      # seconds between settle captures

# Cropping.
#
# "ui" is the default and the safe one. It removes only the reader's own
# furniture -- uniform white bands at the edges, i.e. the gutter -- and keeps
# everything else, so the printed page arrives with its margins intact.
#
# "auto" trims to CONTENT, and content means ink. Where a book's page margin is
# the same colour as the reader's background (Fantagraphics cream on Kindle's
# cream) there is no edge to find, so auto cuts flush to the outermost panel
# and the page margins are lost -- by differing amounts per page, since it
# follows whatever the panels happen to do. Use it only when the page really
# does sit on a contrasting background, e.g. black letterboxing.
#
#   ui           strip uniform edge bands only; keep the page as displayed (default)
#   auto         trim to ink (see the warning above)
#   auto-locked  measure an auto box on page 1 and force it on every page
#   none         keep the full frame
#   WxH+X+Y      explicit ImageMagick crop geometry -- best when you know the
#                page rectangle: read it off a --probe capture once
CROP="${CROP:-ui}"
TRIM_FUZZ="${TRIM_FUZZ:-2%}"

# Readers put a plain gutter down the side of the page (Kindle's is white while
# the book background is cream). A single -trim cannot remove it: the corner
# pixel is the cream background, so the white band counts as content. A second
# pass against a white reference border takes it off, and is a no-op when there
# is no such band. Only perfectly uniform edge bands go, so page art is safe.
TRIM_GUTTER="${TRIM_GUTTER:-1}"
GUTTER_FUZZ="${GUTTER_FUZZ:-1%}"

# Split double-page spreads into two single pages (--split-spreads). A capture
# whose INKED area is wider than SPLIT_RATIO (w/h) is treated as a spread and
# cut down the middle, taking two numbers from the output sequence rather than
# one -- so a cover then two spreads gives 001, 002+003, 004+005. Pages are
# portrait
# and spreads landscape, so the default 1.0 separates them cleanly. Odd widths
# are fine -- the left half takes the extra column.
SPLIT_SPREADS="${SPLIT_SPREADS:-0}"
SPLIT_RATIO="${SPLIT_RATIO:-1.0}"

STALL_ABORT="${STALL_ABORT:-3}"      # abort after N unchanged pages in a row (0=never)
MUTE_SHUTTER="${MUTE_SHUTTER:-1}"
DISABLE_HOT_CORNER="${DISABLE_HOT_CORNER:-1}"   # see the cleanup block for why
SHOT_TIMEOUT="${SHOT_TIMEOUT:-10}"
# ---------------------------------------------------------------------------

# Where GNOME drops its screenshots. Not configurable in the Shell, but the
# Pictures folder itself is localised, so ask xdg rather than assuming English.
SHOT_DIR="${SHOT_DIR:-$(xdg-user-dir PICTURES 2>/dev/null || true)}"
SHOT_DIR="${SHOT_DIR:-$HOME/Pictures}/Screenshots"
YDOTOOL_SOCKET="${YDOTOOL_SOCKET:-/run/user/$(id -u)/.ydotool_socket}"
export YDOTOOL_SOCKET

die() { echo "ERROR: $*" >&2; exit 1; }

key_name() {
    case "$1" in
        106) echo "Right" ;; 109) echo "PageDown" ;; 57) echo "Space" ;;
        108) echo "Down"  ;; 105) echo "Left"     ;; 104) echo "PageUp" ;;
        *)   echo "keycode $1" ;;
    esac
}

# --- args ------------------------------------------------------------------
PROBE=0; URL=""; FORCED_CLICK=""; CALIBRATE=0
while (( $# )); do
    case "$1" in
        --probe)  PROBE=1; shift ;;
        --calibrate) CALIBRATE=1; shift ;;
        --pages)  PAGES="${2:?--pages needs a number}"; shift 2 ;;
        -o|--out) OUTPUT_DIR="${2:?--out needs a directory}"; shift 2 ;;
        --prefix) PREFIX="${2:?--prefix needs a name}"; shift 2 ;;
        --mode)   FLIP_MODE="${2:?--mode needs click|key}"; shift 2 ;;
        --key)    FLIP_MODE=key; FLIP_KEYCODE="${2:?--key needs a keycode or 'auto'}"; shift 2 ;;
        --click)  FORCED_CLICK="${2:?--click needs X,Y in window pixels}"; shift 2 ;;
        --split-spreads) SPLIT_SPREADS=1; shift ;;
        -h|--help) sed -n '2,15p' "$0" | sed 's/^# \?//'; exit 0 ;;
        -*)       die "unknown option '$1' (try --help)" ;;
        *)        URL="$1"; shift ;;
    esac
done

# --- preflight -------------------------------------------------------------
[[ "${XDG_SESSION_TYPE:-}" == "wayland" ]] || echo "WARN: session is ${XDG_SESSION_TYPE:-unknown}, not wayland."
command -v ydotool >/dev/null || die "ydotool not installed."
command -v magick  >/dev/null || die "ImageMagick 7 (magick) not installed."
command -v compare >/dev/null || die "ImageMagick 'compare' not installed."
command -v firefox >/dev/null || die "firefox not installed."
[[ -S "$YDOTOOL_SOCKET" ]] || die "no ydotool socket at $YDOTOOL_SOCKET. Try: systemctl --user start ydotool"

BINDING=$(gsettings get org.gnome.shell.keybindings screenshot-window)
[[ "$BINDING" == *Print* ]] || die "GNOME's screenshot-window keybinding is not <Alt>Print (got: $BINDING).
Restore it with: gsettings reset org.gnome.shell.keybindings screenshot-window"

mkdir -p "$OUTPUT_DIR" "$SHOT_DIR"

# Monitors: "W H OX OY PRIMARY" per line.
MONITORS=$(xrandr --listmonitors 2>/dev/null | awk 'NR>1{
    prim = ($2 ~ /\*/) ? 1 : 0
    split($3, g, "+"); split(g[1], wh, "x")
    split(wh[1], w, "/"); split(wh[2], h, "/")
    print w[1], h[1], g[2], g[3], prim }')
[[ -n "$MONITORS" ]] || die "could not read the monitor layout from xrandr."
read -r PRIM_W PRIM_H PRIM_OX PRIM_OY _ <<< "$(awk '$5==1' <<< "$MONITORS" | head -1)"
[[ -n "${PRIM_W:-}" ]] || read -r PRIM_W PRIM_H PRIM_OX PRIM_OY _ <<< "$(head -1 <<< "$MONITORS")"
is_fullscreen() { awk -v g="$1" '{ if (($1 "x" $2) == g) f=1 } END { exit !f }' <<< "$MONITORS"; }

# --- cleanup ---------------------------------------------------------------
SOUND_WAS=""; HOTCORNER_WAS=""
cleanup() {
    [[ -n "$SOUND_WAS" ]] && gsettings set org.gnome.desktop.sound event-sounds "$SOUND_WAS" 2>/dev/null
    [[ -n "$HOTCORNER_WAS" ]] && gsettings set org.gnome.desktop.interface enable-hot-corners "$HOTCORNER_WAS" 2>/dev/null
    true
}
trap cleanup EXIT INT TERM
if [[ "$MUTE_SHUTTER" == "1" ]]; then
    SOUND_WAS=$(gsettings get org.gnome.desktop.sound event-sounds)
    gsettings set org.gnome.desktop.sound event-sounds false
fi

# ydotool's `mousemove -a` pins the pointer to the TOP-LEFT corner before its
# relative move, which is GNOME's hot corner -- so every click risks throwing
# up the Activities overview. That steals focus, and a window-scoped
# screenshot then has nothing to grab and silently produces no file. Disable
# the hot corner for the run and put it back on the way out.
if [[ "$DISABLE_HOT_CORNER" == "1" ]]; then
    HOTCORNER_WAS=$(gsettings get org.gnome.desktop.interface enable-hot-corners)
    gsettings set org.gnome.desktop.interface enable-hot-corners false
fi

# --- capture ---------------------------------------------------------------
# Signature of the PIXELS only -- never a file checksum (see png:tIME above).
pixel_sig() { magick "$1" -format '%#' info:; }

RAW_GEOM=""
# _grab <dest> <keycodes...> -- press a screenshot keybinding, collect the file.
_grab() {
    local dest="$1"; shift
    local stamp shot deadline sz prev_sz
    stamp=$(mktemp); sleep 0.05
    ydotool key "$@" >/dev/null
    deadline=$(( SECONDS + SHOT_TIMEOUT ))
    while (( SECONDS < deadline )); do
        shot=$(find "$SHOT_DIR" -maxdepth 1 -name '*.png' -newer "$stamp" -print 2>/dev/null | head -1)
        [[ -n "$shot" ]] && break
        sleep 0.2
    done
    rm -f "$stamp"
    [[ -n "$shot" ]] || return 1
    prev_sz=-1; sz=$(stat -c%s "$shot")
    while [[ "$sz" != "$prev_sz" ]]; do prev_sz=$sz; sleep 0.2; sz=$(stat -c%s "$shot"); done
    mv -f "$shot" "$dest"
    RAW_GEOM=$(magick identify -format '%wx%h' "$dest")
}
capture_raw()    { _grab "$1" 56:1 99:1 99:0 56:0; }   # Alt+Print   -> focused window
capture_screen() { _grab "$1" 42:1 99:1 99:0 42:0; }   # Shift+Print -> whole desktop

# capture_settled <dest> -- capture until two consecutive frames are identical,
# so the reader's toolbar has faded before the page is written.
SETTLED_SIG=""
capture_settled() {
    local dest="$1" prev="" sig n
    for (( n = 0; n < SETTLE_TRIES; n++ )); do
        capture_raw "$dest" || return 1
        sig=$(pixel_sig "$dest")
        [[ "$sig" == "$prev" ]] && { SETTLED_SIG="$sig"; return 0; }
        prev="$sig"
        sleep "$SETTLE_GAP"
    done
    SETTLED_SIG="$sig"      # gave up waiting; use the last frame
    return 0
}

# --- display scale ---------------------------------------------------------
# xrandr reports LOGICAL geometry while GNOME screenshots arrive in PHYSICAL
# pixels, so on a scaled display -- 200% on a 4K panel being the usual case --
# the two disagree and every size test here would fail (the fullscreen check
# would never match, and the run would stall waiting for a window that is
# already fullscreen). Measure the ratio once and restate the monitor table in
# capture pixels, the unit everything else works in. The click maths divides
# two capture-pixel quantities, so it comes out the same either way.
DISPLAY_SCALE=1
detect_display_scale() {
    local cap="$OUTPUT_DIR/.scale.png" phys_w logical_w
    capture_screen "$cap" || return 1
    phys_w=${RAW_GEOM%x*}
    rm -f "$cap"
    logical_w=$(awk 'BEGIN{m=0} {v=$3+$1; if (v>m) m=v} END{print m}' <<< "$MONITORS")
    (( logical_w > 0 )) || return 1
    DISPLAY_SCALE=$(awk -v p="$phys_w" -v l="$logical_w" 'BEGIN{printf "%.4f", p/l}')
    if awk -v s="$DISPLAY_SCALE" 'BEGIN{exit !(s < 0.99 || s > 1.01)}'; then
        echo "Display scaling ${DISPLAY_SCALE}x detected (xrandr says ${logical_w}px wide, captures are ${phys_w}px)."
        MONITORS=$(awk -v s="$DISPLAY_SCALE" '{printf "%d %d %d %d %d\n", $1*s, $2*s, $3*s, $4*s, $5}' <<< "$MONITORS")
        read -r PRIM_W PRIM_H PRIM_OX PRIM_OY _ <<< "$(awk '$5==1' <<< "$MONITORS" | head -1)"
        [[ -n "${PRIM_W:-}" ]] || read -r PRIM_W PRIM_H PRIM_OX PRIM_OY _ <<< "$(head -1 <<< "$MONITORS")"
    fi
}
detect_display_scale || echo "WARN: could not measure display scale; assuming 1:1."

CROP_BOX=""
apply_crop() {
    local f="$1"
    case "$CROP" in
        none) ;;
        ui)
            # Uniform white edge bands only -- the gutter. Nothing content-based,
            # so cream page margins survive untouched.
            magick "$f" -bordercolor white -border 1 -fuzz "$GUTTER_FUZZ" -trim +repage "$f" ;;
        auto)
            # Gutter FIRST. The gutter runs the full height of the window, so
            # trimming the background first yields a box stretched to full
            # height, and the gutter pass can then only take columns off it --
            # leaving background bands above and below the page.
            if (( TRIM_GUTTER )); then
                magick "$f" -bordercolor white -border 1 -fuzz "$GUTTER_FUZZ" -trim +repage "$f"
            fi
            magick "$f" -fuzz "$TRIM_FUZZ" -trim +repage "$f" ;;
        auto-locked)
            if [[ -z "$CROP_BOX" ]]; then
                CROP_BOX=$(magick "$f" -fuzz "$TRIM_FUZZ" -format '%@' info:)
                echo "  crop box locked to $CROP_BOX (from page 1)"
            fi
            magick "$f" -crop "$CROP_BOX" +repage "$f" ;;
        *)    magick "$f" -crop "$CROP" +repage "$f" ;;
    esac
}

# out_name <n> -- path for output page n.
out_name() {
    if [[ -n "$PREFIX" ]]; then printf '%s/%s_%03d.png' "$OUTPUT_DIR" "$PREFIX" "$1"
    else                        printf '%s/%03d.png'    "$OUTPUT_DIR" "$1"; fi
}

# emit_pages <workfile> -- turn one capture into one or two numbered pages,
# advancing OUT_N. Splitting therefore consumes two numbers and the sequence
# stays continuous: a cover then two spreads gives 001, 002+003, 004+005.
# Consumes the work file, and reports what it wrote in EMIT_NOTE -- a global
# rather than stdout because $(emit_pages ...) would run in a subshell and the
# OUT_N increment would be thrown away.
OUT_N=1
EMIT_NOTE=""
emit_pages() {
    local f="$1" w h box bw bh bx rest cx first
    w=$(magick identify -format '%w' "$f"); h=$(magick identify -format '%h' "$f")

    if (( SPLIT_SPREADS )); then
        # Judge by the INKED area, never the frame. Under CROP=ui every capture
        # is the whole landscape viewport, so a frame-aspect test would call the
        # portrait cover a spread and cut it in half. Ink is portrait on a single
        # page and landscape on a spread whatever the crop mode.
        box=$(magick "$f" -fuzz "$TRIM_FUZZ" -format '%@' info:)   # WxH+X+Y
        bw=${box%%x*}; rest=${box#*x}; bh=${rest%%+*}; bx=${rest#*+}; bx=${bx%+*}
        if awk -v w="$bw" -v h="$bh" -v r="$SPLIT_RATIO" 'BEGIN{exit !(w/h > r)}'; then
            # Cut at the centre of the ink, not of the frame: stripping a
            # one-sided UI gutter leaves the frame asymmetric, and a frame-centre
            # cut would slice into one of the two pages.
            cx=$(( bx + bw / 2 ))
            first=$OUT_N
            magick "$f" -crop "${cx}x${h}+0+0"            +repage "$(out_name "$OUT_N")"
            OUT_N=$(( OUT_N + 1 ))
            magick "$f" -crop "$(( w - cx ))x${h}+${cx}+0" +repage "$(out_name "$OUT_N")"
            OUT_N=$(( OUT_N + 1 ))
            rm -f "$f"
            EMIT_NOTE=$(printf ' -> split into %03d+%03d' "$first" "$(( first + 1 ))")
            return 0
        fi
    fi

    mv -f "$f" "$(out_name "$OUT_N")"
    EMIT_NOTE=$(printf ' -> %03d' "$OUT_N")
    OUT_N=$(( OUT_N + 1 ))
}

# --- locate the window on the desktop --------------------------------------
WIN_OX=""; WIN_OY=""
locate_window() {
    local win="$OUTPUT_DIR/.win.png" screen="$OUTPUT_DIR/.screen.png"
    local w h ox oy ae best=1e18 wgeom
    capture_raw "$win" || return 1
    wgeom="$RAW_GEOM"            # capture_screen overwrites RAW_GEOM -- keep the window's
    capture_screen "$screen" || return 1
    while read -r w h ox oy _; do
        [[ "${w}x${h}" == "$wgeom" ]] || continue
        magick "$screen" -crop "${w}x${h}+${ox}+${oy}" +repage "$OUTPUT_DIR/.tile.png"
        ae=$(compare -metric AE "$win" "$OUTPUT_DIR/.tile.png" null: 2>&1 | awk '{print $1+0}')
        if awk -v a="$ae" -v b="$best" 'BEGIN{exit !(a<b)}'; then best=$ae; WIN_OX=$ox; WIN_OY=$oy; fi
    done <<< "$MONITORS"
    rm -f "$win" "$screen" "$OUTPUT_DIR/.tile.png"
    RAW_GEOM="$wgeom"
    [[ -n "$WIN_OX" ]]
}

# move_pointer <win_x> <win_y> -- window pixels to what ydotool must be asked
# for, dividing out the acceleration factor (see CLICK_DIV_* above).
move_pointer() {
    local ax ay
    ax=$(awk -v v="$(( WIN_OX + $1 - PRIM_OX ))" -v d="$CLICK_DIV_X" 'BEGIN{printf "%d", v/d}')
    ay=$(awk -v v="$(( WIN_OY + $2 - PRIM_OY ))" -v d="$CLICK_DIV_Y" 'BEGIN{printf "%d", v/d}')
    ydotool mousemove -a -x "$ax" -y "$ay" >/dev/null
}

# click_at <win_x> <win_y> -- click, then get the pointer off the edge. Left
# resting on the forward zone it keeps the reader's chevron drawn, which lands
# in every capture and also blocks the gutter trim (the band stops being
# uniform). PARK is a fraction of the window, or "none" to leave it be.
click_at() {
    move_pointer "$1" "$2"
    sleep 0.3
    ydotool click 0xC0 >/dev/null
    [[ "$PARK" == "none" ]] && return 0
    sleep 0.2
    move_pointer \
        "$(awk -v w="$WIN_W" -v f="${PARK%,*}" 'BEGIN{printf "%d", w*f}')" \
        "$(awk -v h="$WIN_H" -v f="${PARK#*,}" 'BEGIN{printf "%d", h*f}')"
}

# --- calibration -----------------------------------------------------------
# Clicks at two known ydotool values and measures where the pointer actually
# landed, by finding a magenta marker the test page drops at the click point.
# Two points give the divisor and cancel any fixed offset. No OCR, no reading
# numbers off a screen.
find_marker() {   # echoes "cx cy" in window pixels
    local box w h x y rest
    box=$(magick "$1" -fuzz 20% -fill white -opaque '#ff00ff' -fill black +opaque white \
                 -format '%@' info: 2>/dev/null)
    [[ -n "$box" && "$box" != "0x0+0+0" ]] || return 1
    w=${box%%x*}; rest=${box#*x}; h=${rest%%+*}; x=${rest#*+}; x=${x%+*}; y=${box##*+}
    (( w > 4 && w < 200 )) || return 1        # sanity: that is a marker, not a page
    echo "$(( x + w / 2 )) $(( y + h / 2 ))"
}

run_calibration() {
    local dir="$HOME/comic-capture-calib" page cap ff v c cx cy
    local -a xs=() ys=()
    page="$dir/calib.html"; cap="$dir/cap.png"
    rm -rf "$dir"; mkdir -p "$dir/profile"
    cat > "$page" <<'HTML'
<html><body style="margin:0;background:#101010;overflow:hidden">
<div id="m" style="position:fixed;width:24px;height:24px;background:#ff00ff;display:none"></div>
<div style="color:#555;font:28px sans-serif;padding:24px">comic-capture calibration</div>
<script>addEventListener('click',e=>{m.style.left=(e.clientX-12)+'px';
m.style.top=(e.clientY-12)+'px';m.style.display='block';});</script>
</body></html>
HTML
    echo "Opening a fullscreen calibration page (do not touch the mouse)..."
    firefox --kiosk --new-instance --profile "$dir/profile" "file://$page" >/dev/null 2>&1 &
    ff=$!
    sleep "$LOAD_WAIT"

    # Poll rather than grab once. While Firefox is starting there is a spell
    # with no focused window at all, and a window-scoped screenshot then
    # produces no file -- which looks exactly like ydotool being broken.
    local deadline=$(( SECONDS + READY_TIMEOUT )) ready=0
    while (( SECONDS < deadline )); do
        if capture_raw "$cap" && is_fullscreen "$RAW_GEOM"; then ready=1; break; fi
        sleep 2
    done
    if (( ! ready )); then
        kill "$ff" 2>/dev/null; rm -rf "$dir"
        die "the calibration window never became a focused fullscreen window.
Last capture: ${RAW_GEOM:-none}. Something else may be holding focus. Nothing was changed."
    fi
    locate_window || { kill "$ff" 2>/dev/null; rm -rf "$dir"; die "could not locate the window."; }
    if (( WIN_OX != PRIM_OX || WIN_OY != PRIM_OY )); then
        kill "$ff" 2>/dev/null; rm -rf "$dir"
        die "the calibration window opened on a non-primary monitor, and absolute clicks
only reach the primary one. Mutter puts a new window on the monitor of the currently
FOCUSED window (not the one under the pointer), so click a window on the primary
monitor first, then re-run -- or make this monitor primary in Settings > Displays.
Nothing was changed."
    fi

    for v in 200 600; do
        ydotool mousemove -a -x "$v" -y "$v" >/dev/null; sleep 0.4
        ydotool click 0xC0 >/dev/null; sleep 0.8
        capture_raw "$cap" || continue
        if c=$(find_marker "$cap"); then
            xs+=("${c% *}"); ys+=("${c#* }")
            echo "  asked for $v,$v -> landed at ${c% *},${c#* }"
        else
            echo "  asked for $v,$v -> marker not found (click may have missed the window)"
        fi
    done
    kill "$ff" 2>/dev/null; sleep 1; rm -rf "$dir"

    (( ${#xs[@]} == 2 )) || die "calibration failed: needed two measurements, got ${#xs[@]}.
Nothing was changed. Make sure nothing steals focus while it runs."

    cx=$(awk -v a="${xs[0]}" -v b="${xs[1]}" 'BEGIN{printf "%.3f", (b-a)/400}')
    cy=$(awk -v a="${ys[0]}" -v b="${ys[1]}" 'BEGIN{printf "%.3f", (b-a)/400}')
    echo
    echo "Measured pointer divisors:  CLICK_DIV_X=$cx  CLICK_DIV_Y=$cy"
    echo "(currently configured: $CLICK_DIV_X / $CLICK_DIV_Y)"
    echo
    echo "If those differ from the configured values, put them in your environment:"
    echo "  export CLICK_DIV_X=$cx CLICK_DIV_Y=$cy"
    echo "or edit the defaults at the top of this script."
}

if (( CALIBRATE )); then run_calibration; exit 0; fi

# --- open the comic --------------------------------------------------------
if [[ -n "$URL" ]]; then
    echo "Opening $URL in a new Firefox window..."
    firefox --new-window "$URL" >/dev/null 2>&1 &
    sleep "$LOAD_WAIT"
fi

echo "========================================================="
echo "  1. Get the comic to page 1 (sign in / navigate if needed)"
echo "  2. Press F11 so Firefox is FULLSCREEN"
echo "  3. Press Enter here, then click back on the Firefox window"
echo "========================================================="
read -r -p "Enter when ready... " _

if [[ "$REQUIRE_FULLSCREEN" == "1" ]]; then
    echo "Switch to Firefox now -- starting once the window is fullscreen and still (up to ${READY_TIMEOUT}s)."
    probe="$OUTPUT_DIR/.ready.png"; deadline=$(( SECONDS + READY_TIMEOUT )); ready=0; last=""
    while (( SECONDS < deadline )); do
        sleep "$POLL_INTERVAL"
        capture_raw "$probe" || continue
        if ! is_fullscreen "$RAW_GEOM"; then
            printf '  focused window is %s, waiting for fullscreen...\n' "$RAW_GEOM"
            last=""; continue
        fi
        sig=$(pixel_sig "$probe")
        [[ -n "$last" && "$sig" == "$last" ]] && { ready=1; break; }
        [[ -n "$last" ]] && echo "  fullscreen, waiting for the toolbar to hide..."
        last="$sig"
    done
    rm -f "$probe"
    (( ready )) || die "no settled fullscreen window within ${READY_TIMEOUT}s.
Press F11 in Firefox, or re-run with REQUIRE_FULLSCREEN=0 to capture the window as-is."
    echo "Ready ($RAW_GEOM)."
else
    echo "Switch to Firefox now -- starting in ${SWITCH_DELAY}s..."
    sleep "$SWITCH_DELAY"
fi

WIN_W=${RAW_GEOM%x*}; WIN_H=${RAW_GEOM#*x}

# --- click setup -----------------------------------------------------------
declare -a TARGETS=()
if [[ "$FLIP_MODE" == "click" ]]; then
    locate_window || die "could not work out which monitor the window is on."
    echo "Window at desktop +${WIN_OX}+${WIN_OY}; primary monitor is ${PRIM_W}x${PRIM_H}+${PRIM_OX}+${PRIM_OY}."
    if (( WIN_OX != PRIM_OX || WIN_OY != PRIM_OY )); then
        die "the comic is not on your PRIMARY monitor, and ydotool's absolute pointer
maps only to the primary one -- clicks cannot reach it. Move the Firefox window to the
primary monitor (or make this one primary in Settings > Displays), or use --mode key."
    fi
    if [[ -n "$FORCED_CLICK" ]]; then
        TARGETS=("${FORCED_CLICK/,/ }")
    else
        for t in $CLICK_TARGETS; do
            fx=${t%,*}; fy=${t#*,}
            TARGETS+=("$(awk -v w="$WIN_W" -v f="$fx" 'BEGIN{printf "%d", w*f}') $(awk -v h="$WIN_H" -v f="$fy" 'BEGIN{printf "%d", h*f}')")
        done
    fi
fi

# --- probe -----------------------------------------------------------------
if (( PROBE )); then
    out="$OUTPUT_DIR/${PREFIX:+${PREFIX}_}probe.png"
    capture_settled "$out" || die "no screenshot appeared within ${SHOT_TIMEOUT}s."
    apply_crop "$out"
    echo "Wrote $out"
    echo "  captured $RAW_GEOM, saved $(magick identify -format '%wx%h' "$out") after crop=$CROP"
    if (( SPLIT_SPREADS )); then
        pw=$(magick identify -format '%w' "$out"); ph=$(magick identify -format '%h' "$out")
        if awk -v w="$pw" -v h="$ph" -v r="$SPLIT_RATIO" 'BEGIN{exit !(w/h > r)}'; then
            echo "  landscape: --split-spreads would cut this into two $(( pw / 2 ))x${ph} pages"
        else
            echo "  portrait: --split-spreads would leave this page whole"
        fi
    fi
    if [[ "$FLIP_MODE" == "click" ]]; then
        echo "  click targets that would be tried (window pixels):"
        for t in "${TARGETS[@]}"; do echo "    $t"; done
        echo "  pick your own from the saved image with: --click X,Y"
    fi
    exit 0
fi

# --- run -------------------------------------------------------------------
echo "Capturing $PAGES screens -> $OUTPUT_DIR"
if [[ "$FLIP_MODE" == "click" ]]; then
    echo "Turning pages by click; trying ${#TARGETS[@]} target(s) on the first turn."
    locked=$(( ${#TARGETS[@]} == 1 ))
    cand=0
else
    if [[ "$FLIP_KEYCODE" == "auto" ]]; then
        read -ra KEYS <<< "$FLIP_CANDIDATES"; locked=0
        echo "Turning pages by key; trying $(for c in "${KEYS[@]}"; do printf '%s ' "$(key_name "$c")"; done)"
    else
        KEYS=("$FLIP_KEYCODE"); locked=1
        echo "Turning pages by key: $(key_name "$FLIP_KEYCODE")"
    fi
    cand=0
fi

turn_page() {
    if [[ "$FLIP_MODE" == "click" ]]; then
        # shellcheck disable=SC2086
        click_at ${TARGETS[cand]}
    else
        ydotool key "${KEYS[cand]}:1" "${KEYS[cand]}:0" >/dev/null
    fi
}
cand_desc() {
    if [[ "$FLIP_MODE" == "click" ]]; then echo "click ${TARGETS[cand]}"
    else echo "$(key_name "${KEYS[cand]}")"; fi
}
cand_count() {
    if [[ "$FLIP_MODE" == "click" ]]; then echo "${#TARGETS[@]}"; else echo "${#KEYS[@]}"; fi
}

# Every capture lands here first; emit_pages then names the output(s).
out="$OUTPUT_DIR/.capture.png"
printf 'Screen 1/%d ... ' "$PAGES"
capture_settled "$out" || die "no screenshot within ${SHOT_TIMEOUT}s on screen 1."
expect_geom="$RAW_GEOM"; prev_sig="$SETTLED_SIG"
apply_crop "$out"
page_geom=$(magick identify -format '%wx%h' "$out")
emit_pages "$out"
echo "${page_geom}${EMIT_NOTE} ok"

stall=0
for (( i = 2; i <= PAGES; i++ )); do
    printf 'Screen %d/%d ... ' "$i" "$PAGES"

    turned=0
    while true; do
        turn_page
        sleep "$TURN_WAIT"
        capture_settled "$out" || die "no screenshot within ${SHOT_TIMEOUT}s on screen $i."
        if [[ "$RAW_GEOM" != "$expect_geom" ]]; then
            rm -f "$out"
            die "screen $i captured at $RAW_GEOM, expected $expect_geom -- focus moved to another window.
Pages up to $(printf '%03d' $(( OUT_N - 1 ))) are in $OUTPUT_DIR."
        fi
        [[ "$SETTLED_SIG" != "$prev_sig" ]] && { turned=1; break; }
        if (( ! locked )) && (( cand + 1 < $(cand_count) )); then
            printf '%s did nothing, trying ' "$(cand_desc)"
            cand=$(( cand + 1 )); printf '%s ... ' "$(cand_desc)"
            continue
        fi
        break
    done

    if (( turned )); then
        (( locked )) || { locked=1; printf '[using %s] ' "$(cand_desc)"; }
        stall=0
    else
        stall=$(( stall + 1 )); printf '[page did not change] '
        if (( STALL_ABORT > 0 && stall >= STALL_ABORT )); then
            echo
            die "$stall unchanged screens in a row; stopping at screen $i.
Nothing turned the page. In click mode, run --probe, look at the saved image, and
pass the exact forward-arrow position with --click X,Y.
Pages up to $(printf '%03d' $(( OUT_N - 1 ))) are in $OUTPUT_DIR."
        fi
    fi
    prev_sig="$SETTLED_SIG"
    apply_crop "$out"
    page_geom=$(magick identify -format '%wx%h' "$out")
    emit_pages "$out"
    printf '%s%s ok\n' "$page_geom" "$EMIT_NOTE"
done

echo "========================================================="
echo "Done. $(( OUT_N - 1 )) pages from $PAGES screens, in: $OUTPUT_DIR"
echo "========================================================="
