#!/usr/bin/env bash
# Run the GUI suite once per settings variant: the whole suite, headless, on
# each setting the default run never sees. The suite itself runs on one
# profile (the live ini with the harness's pins and defaults); a bug that only
# a setting brings out - the JPG panels zip was one - stays hidden until
# someone runs with that setting. This is the someone, for a nightly or a
# release: each variant is one `run_gui_tests.sh --headless --quiet --ini ...`
# run, every variant runs even after one fails, and the summary at the end
# says which passed, which failed and how long each took.
#
# The variants are listed below, one per line: a name, then the settings for
# that run as "key=value;key=value" (what run_gui_tests.sh --ini takes, and the
# BARKS_GUI_INI form the harness reads), then, for a variant that wants another
# nested screen, its size after a second bar (the spread's landscape screen; the
# harness checks each boot came up on the layout the setting names). Settings the
# harness pins (fullscreen on start, quit confirm, ...) cannot be a variant;
# double-page mode and the main screen layout are harness defaults rather than
# pins, so they can. Add a variant by adding a line.
#
# Usage: scripts/run_gui_matrix.sh [--list] [--only NAME[,NAME...]] [--visible]
#                                  [--screen WxH] [--progress] [--app PATH] [pytest args]
#   --list      print the variants and exit
#   --only      run only the named variants
#   --visible   on the Xephyr window, serially, instead of headless on Xvfb
#   --screen    nested screen size for every run without its own (run_gui_tests.sh --screen)
#   --progress  a line per test as it finishes (run_gui_tests.sh --progress)
#   --app       every variant against this built executable (run_gui_tests.sh --app):
#               a setting that loads files only it needs (the virtual keyboard's
#               layouts, say) is also a packaging test
#   anything else goes to pytest through run_gui_tests.sh, e.g. -k reader or -x
#
# Each variant's full output goes to build/gui-tests/matrix-<stamp>/<name>.log;
# a failing test's artifacts land where run_gui_tests.sh always puts them.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

# name|settings. Names are what --only takes and what the log files are called.
VARIANTS=(
    "duckburg-theme|color_theme=Duckburg"
    "four-color-theme|color_theme=Four Color"
    "virtual-keyboard|use_virtual_keyboard=1"
    "no-title-info|show_tree_view_title_info=0;show_fun_view_title_info=0"
    "censorship-fixes|use_harpies=1;use_deah=1;use_blank_eyeballs=1;use_glk_firebug_ending=1"
    "spread|main_screen_layout=Two-page spread|1920x1080"
)

# The three fields of a variant line: its name, its settings and its own screen size
# (empty for most), into the variables named.
split_variant() {
    local line="$1" rest
    name="${line%%|*}"
    rest="${line#*|}"
    settings="${rest%%|*}"
    variant_screen=""
    if [[ "$rest" == *"|"* ]]; then
        variant_screen="${rest#*|}"
    fi
}

only=""
output=--quiet
mode=(--headless)
screen=()
app=()
while [[ "${1:-}" == --* ]]; do
    case "$1" in
    --list)
        for variant in "${VARIANTS[@]}"; do
            split_variant "$variant"
            printf '%-18s %s%s\n' "$name" "$settings" \
                "${variant_screen:+ (on a ${variant_screen} screen)}"
        done
        exit 0
        ;;
    --only)
        only="${2:?--only needs a variant name (see --list)}"
        shift 2
        ;;
    --visible)
        mode=()
        shift
        ;;
    --screen)
        screen=(--screen "${2:?--screen needs WxH}")
        shift 2
        ;;
    --progress)
        output=--progress
        shift
        ;;
    --app)
        app=(--app "${2:?--app needs the path of the executable}")
        shift 2
        ;;
    *) break ;;
    esac
done

selected=()
for variant in "${VARIANTS[@]}"; do
    split_variant "$variant"
    if [[ -n "$only" ]] && ! [[ ",$only," == *",$name,"* ]]; then
        continue
    fi
    selected+=("$variant")
done
if [[ ${#selected[@]} -eq 0 ]]; then
    echo "run_gui_matrix: no variant matches --only $only (see --list)" >&2
    exit 2
fi

stamp="$(date +%Y%m%d-%H%M%S)"
log_dir="build/gui-tests/matrix-${stamp}"
mkdir -p "$log_dir"

names=()
results=()
durations=()
failed=0
# One variant's run. BARKS_GUI_INI is what --ini appends to; setting it here is
# the same as one --ini per key. A variant's own screen size beats --screen.
run_variant() {
    local name="$1" settings="$2" variant_screen="$3"
    shift 3
    local -a run_screen=("${screen[@]}")
    [[ -n "$variant_screen" ]] && run_screen=(--screen "$variant_screen")
    BARKS_GUI_INI="$settings" bash "${SCRIPT_DIR}/run_gui_tests.sh" "${mode[@]}" "$output" \
        "${run_screen[@]}" "${app[@]}" "$@" 2>&1 | tee "${log_dir}/${name}.log"
}

# Stopping the matrix stops the variant running, whose own exit cleans up what
# it started (see _gui_run.sh); the rest are not started.
GUI_RUNNER=run_gui_matrix
# shellcheck source=scripts/_gui_run.sh
source "${SCRIPT_DIR}/_gui_run.sh"
gui_trap_signals

for variant in "${selected[@]}"; do
    split_variant "$variant"
    echo
    echo "==== ${name}: ${settings}${variant_screen:+ (on a ${variant_screen} screen)} ===="
    started=$SECONDS
    # A failure is recorded and the loop goes on; an interrupt ends it.
    if gui_run run_variant "$name" "$settings" "$variant_screen" "$@"; then
        results+=("passed")
    elif [[ -n "$GUI_INTERRUPTED" ]]; then
        results+=("stopped")
    else
        results+=("FAILED")
        failed=1
    fi
    names+=("$name")
    durations+=("$((SECONDS - started))")
    [[ -n "$GUI_INTERRUPTED" ]] && break
done

echo
echo "==== settings matrix ===="
for i in "${!names[@]}"; do
    printf '%-18s %-7s %3dm%02ds\n' "${names[$i]}" "${results[$i]}" \
        "$((durations[i] / 60))" "$((durations[i] % 60))"
done
echo "logs: ${log_dir}/"
[[ -n "$GUI_INTERRUPTED" ]] && exit "$GUI_INTERRUPTED"
exit "$failed"
