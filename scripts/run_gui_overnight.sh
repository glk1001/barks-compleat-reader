#!/usr/bin/env bash
# Run every GUI test there is, every way it can run: the overnight run.
#
# The default GUI run is one pass of the suite on this machine's settings. Each
# stage below is another pass the default never makes - the other comic and
# panel sources, the settings matrix, another screen shape, real touch, the
# random-walk soak, and a built executable when one is given - run one after
# another, headless, every stage even after one fails. The summary at the end
# says which passed, which failed and how long each took; the exit status is
# non-zero if any failed.
#
# Stages (name: what it runs):
#   suite          the whole suite, as this machine is configured
#   png-panels     the suite viewing images from the PNG panels (--png-images 1)
#   jpg-panels     ... and from the encrypted JPG panels zip (--png-images 0)
#   volumes        the suite reading comics from the Fantagraphics volumes (--prebuilt 0)
#   prebuilt       ... and from the prebuilt comic archives (--prebuilt 1)
#   matrix         run_gui_matrix.sh: the suite once per settings variant (themes,
#                  double-page, virtual keyboard, title info off, censorship fixes)
#   screen-1080p   the suite on a landscape 1920x1080 nested screen
#   touch          the tap tests by real touch (--touch); skipped, and said so,
#                  when the machine lacks the udev rule (scripts/udev/)
#   soak           the random walk, SOAK_STEPS keys from each of SOAK_SEEDS
#   built-app      the suite against a Nuitka build; only with --app PATH
#
# Usage: scripts/run_gui_overnight.sh [--list] [--only A,B] [--skip A,B] [--app PATH]
#   --list   print the stages and exit
#   --only   run only these stages (comma-separated)
#   --skip   run every stage but these
#   --app    also run the suite against this built executable (the built-app stage)
# Env: BARKS_OVERNIGHT_SOAK_STEPS (default 500), BARKS_OVERNIGHT_SOAK_SEEDS
# (default "1 2 3").
#
# A laptop left overnight goes to sleep, and a run on battery is throttled, which
# the timing budgets can fail. So the run holds off sleep while it lasts (through
# systemd-inhibit, when there is one) and warns when on battery. Each stage says
# its number and start time, then a line per test as it finishes; summary.txt
# holds the results so far, rewritten after every stage. Each stage's output goes
# to build/gui-tests/overnight-<stamp>/<stage>.log, pytest's whole verbose output
# to that run's build/gui-tests/<run>/pytest.log, and a failing test's artifacts
# land where run_gui_tests.sh always puts them.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

SOAK_STEPS="${BARKS_OVERNIGHT_SOAK_STEPS:-500}"
SOAK_SEEDS="${BARKS_OVERNIGHT_SOAK_SEEDS:-1 2 3}"
STAGES=(suite png-panels jpg-panels volumes prebuilt matrix screen-1080p touch soak built-app)

only=""
skip=""
app=""
while [[ "${1:-}" == --* ]]; do
    case "$1" in
    --list)
        sed -n '/^# Stages/,/^# Usage/p' "${BASH_SOURCE[0]}" | sed '$d' | sed 's/^# \{0,1\}//'
        exit 0
        ;;
    --only)
        only="${2:?--only needs stage names (see --list)}"
        shift 2
        ;;
    --skip)
        skip="${2:?--skip needs stage names (see --list)}"
        shift 2
        ;;
    --app)
        app="${2:?--app needs the path of the executable}"
        [[ -x "$app" ]] || { echo "run_gui_overnight: not an executable: $app" >&2; exit 2; }
        shift 2
        ;;
    *)
        echo "run_gui_overnight: unknown option $1 (see --list, or the header)" >&2
        exit 2
        ;;
    esac
done

for name in ${only//,/ } ${skip//,/ }; do
    if [[ " ${STAGES[*]} " != *" $name "* ]]; then
        echo "run_gui_overnight: no stage called $name (see --list)" >&2
        exit 2
    fi
done

# Hold off sleep for the whole run: a background systemd-inhibit holds the lock
# until this script exits. (Not re-running the script under it: this script
# stays the process you started, so a `kill` of it is what stops the run.)
inhibitor=""
if command -v systemd-inhibit >/dev/null; then
    systemd-inhibit --what=sleep:idle --who="Barks Reader GUI tests" \
        --why="The overnight GUI test run" sleep infinity >/dev/null 2>&1 &
    inhibitor=$!
    trap '[[ -n "$inhibitor" ]] && kill "$inhibitor" 2>/dev/null; true' EXIT
fi

wanted() {
    local name="$1"
    [[ -n "$only" && ",$only," != *",$name,"* ]] && return 1
    [[ -n "$skip" && ",$skip," == *",$name,"* ]] && return 1
    [[ "$name" == built-app && -z "$app" ]] && return 1
    return 0
}

on_battery() {
    local supply
    for supply in /sys/class/power_supply/*; do
        [[ -f "$supply/type" && "$(cat "$supply/type")" == Mains ]] || continue
        [[ "$(cat "$supply/online" 2>/dev/null)" == 0 ]] && return 0
    done
    return 1
}
if on_battery; then
    echo "run_gui_overnight: WARNING - on battery: a throttled CPU can fail the timing budgets; plug in"
fi

stamp="$(date +%Y%m%d-%H%M%S)"
log_dir="build/gui-tests/overnight-${stamp}"
mkdir -p "$log_dir"
# --progress: a line per test as it finishes, so a long stage is not silent.
gui=(bash "${SCRIPT_DIR}/run_gui_tests.sh" --headless --progress)

# Run one stage's command, its output to the screen and its log. A stage that
# returns 3 was skipped (it says why); anything else non-zero failed.
run_stage() {
    case "$1" in
    suite) "${gui[@]}" ;;
    png-panels) "${gui[@]}" --png-images 1 ;;
    jpg-panels) "${gui[@]}" --png-images 0 ;;
    volumes) "${gui[@]}" --prebuilt 0 ;;
    prebuilt) "${gui[@]}" --prebuilt 1 ;;
    matrix) bash "${SCRIPT_DIR}/run_gui_matrix.sh" --progress ;;
    screen-1080p) "${gui[@]}" --screen 1920x1080 ;;
    touch)
        if ! BARKS_PROBE_TOUCH=1 BARKS_PROBE_HEADLESS=1 bash "${SCRIPT_DIR}/gui-probe.sh" doctor >/dev/null 2>&1; then
            echo "touch: skipped - this machine is not set up for touch mode;"
            echo "       see: BARKS_PROBE_TOUCH=1 bash scripts/gui-probe.sh doctor"
            return 3
        fi
        "${gui[@]}" --touch -k test_taps
        ;;
    soak)
        local seed status=0
        for seed in $SOAK_SEEDS; do
            echo "soak: seed ${seed}, ${SOAK_STEPS} keys"
            BARKS_GUI_WALK_SEED="$seed" BARKS_GUI_WALK_STEPS="$SOAK_STEPS" \
                "${gui[@]}" --soak || status=1
        done
        return "$status"
        ;;
    built-app) "${gui[@]}" --app "$app" ;;
    esac
}

elapsed() {
    printf '%dh%02dm' $(($1 / 3600)) $(($1 % 3600 / 60))
}

# The results so far, to the screen and to summary.txt - rewritten after every
# stage, so a run stopped part way still leaves what it found.
write_summary() {
    {
        echo "==== overnight GUI run, ${stamp}: $1 ===="
        for i in "${!names[@]}"; do
            printf '%-13s %-8s %3dm%02ds\n' "${names[$i]}" "${results[$i]}" \
                "$((durations[i] / 60))" "$((durations[i] % 60))"
        done
        echo "logs: ${log_dir}/"
    } >"${log_dir}/summary.txt"
}

selected=()
for name in "${STAGES[@]}"; do
    wanted "$name" && selected+=("$name")
done
echo "run_gui_overnight: ${#selected[@]} stages: ${selected[*]}"
echo "run_gui_overnight: to stop it and everything it started: Ctrl-C, or kill $$"
echo "run_gui_overnight: results so far in ${log_dir}/summary.txt"

# A stage, its output to the screen and its log; the status is run_stage's
# (pipefail: tee's own never masks it).
log_stage() {
    run_stage "$1" 2>&1 | tee "${log_dir}/$1.log"
}

# Stopping the run stops the stage running, whose runner cleans up what it
# started (see _gui_run.sh); the stages after it are not started.
GUI_RUNNER=run_gui_overnight
# shellcheck source=scripts/_gui_run.sh
source "${SCRIPT_DIR}/_gui_run.sh"
gui_trap_signals

names=()
results=()
durations=()
failed=0
run_started=$SECONDS
for n in "${!selected[@]}"; do
    name="${selected[$n]}"
    echo
    echo "==== [$((n + 1))/${#selected[@]}] ${name}, started $(date +%H:%M)" \
        "($(elapsed $((SECONDS - run_started))) into the run) ===="
    started=$SECONDS
    status=0
    gui_run log_stage "$name" || status=$?
    if [[ -n "$GUI_INTERRUPTED" ]]; then
        results+=("stopped")
    else
        case "$status" in
        0) results+=("passed") ;;
        3) results+=("skipped") ;;
        *)
            results+=("FAILED")
            failed=1
            ;;
        esac
    fi
    names+=("$name")
    durations+=("$((SECONDS - started))")
    echo "==== ${name}: ${results[-1]} in $((durations[-1] / 60))m$((durations[-1] % 60))s ===="
    if [[ -n "$GUI_INTERRUPTED" ]]; then
        write_summary "stopped during ${name}, $(elapsed $((SECONDS - run_started))) in"
        # The stage's runner cleans up what it started on its way out; this
        # catches anything a runner that died outright left behind.
        bash "${SCRIPT_DIR}/gui-probe.sh" cleanup --quiet
        echo
        cat "${log_dir}/summary.txt"
        exit "$GUI_INTERRUPTED"
    fi
    write_summary "$((n + 1)) of ${#selected[@]} stages done"
done

write_summary "finished in $(elapsed $((SECONDS - run_started)))"
echo
cat "${log_dir}/summary.txt"
exit "$failed"
