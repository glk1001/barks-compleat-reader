#!/usr/bin/env bash
# cspell:ignore servernum subshell
# Run everything worth a night: the overnight run of the whole repo.
#
# The gates (pre-commit, pre-push, CI) run what is fast and needs no local data.
# This runs the rest - the checks on the real data pack and the sibling repos,
# the whole lint and test suite from a synced venv, the tests in random order and
# against tomorrow's dependencies, a Nuitka build and its smoke test, every GUI
# test every way (run_gui_overnight.sh, against that build), the GUI timings
# against this machine's calibration, and a slice of mutation testing - one
# stage after another, every stage even after one fails. The data checks come
# first: when the data is broken, what fails later is only a symptom.
#
# Stages (name: what it runs):
#   validate       validate-barks-reader-files.py: every title's panels, prebuilt
#                  comic, layout, panel segments and wiki joins, on the real data
#   panel-sources  check-barks-panel-sources.py: every PNG panel belongs to a title
#   censorship     the censorship-fixes CSV against the fixes trees (the
#                  ../barks-comic-building checker, as on pre-push)
#   wiki-order     check_wiki_story_order.py on the sibling barks-wiki bundle;
#                  warns only, as in full-lint (that repo gates its own order)
#   lint           full-lint.sh: every static check, and the benchmarks against
#                  their baseline (a quiet machine is when those numbers mean most)
#   audit          uv audit, the locked dependencies' known CVEs; warns only
#   pytest         uv sync --locked, then the whole suite with coverage
#   random-order   the whole suite shuffled (pytest-randomly, not a dependency:
#                  uv run --with); its seed is in the log, to replay a failure
#   dep-drift      the suite against every dependency upgraded as far as
#                  pyproject.toml allows, in a venv of its own; uv.lock is put back
#   siblings       the tests of the sibling repos that use barks-fantagraphics and
#                  comic-utils (those with tests: ../barks-comic-building)
#   build          scripts/build.sh, the Nuitka executable; skipped with --app
#   smoke          smoke-test-build.sh on that build (or on --app PATH)
#   gui            run_gui_overnight.sh: every GUI stage, the built app's too,
#                  and a longer soak on new seeds each night
#   gui-timings    the GUI suite once more, recording its timings, then each
#                  kind's slowest against .benchmarks/gui-timings.json; warns
#                  when one has drifted, well before its budget would fail
#   graphify       graphify update ., the knowledge graph (gitignored)
#   mutation       mutmut.sh on one seventh of core/, a different one each weekday
#
# Usage: scripts/run_overnight.sh [--list] [--only A,B] [--skip A,B] [--app PATH]
#   --list   print the stages and exit
#   --only   run only these stages (comma-separated)
#   --skip   run every stage but these
#   --app    use this built executable instead of building one (skips build)
# Env: BARKS_OVERNIGHT_SOAK_STEPS (default here 1000) and BARKS_OVERNIGHT_SOAK_SEEDS
# (default: three seeds from the day of the year, so each night walks new paths);
# BARKS_OVERNIGHT_MUTATION_DAY (1-7, default today's weekday) picks the mutation slice.
#
# Linux only (xvfb, systemd-inhibit, the GUI probe). A stage's output goes to
# build/overnight/<stamp>/<stage>.log and summary.txt holds the results so far,
# rewritten after every stage. Results: passed, FAILED, WARNED (a warn-only stage
# found something), skipped (the stage says why) or stopped. The exit status is
# non-zero if any stage FAILED; warnings do not count.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

STAGES=(validate panel-sources censorship wiki-order lint audit pytest random-order
    dep-drift siblings build smoke gui gui-timings graphify mutation)
SIBLINGS=(../barks-comic-building ../barks-ocr)
BUILT_EXE="${REPO_ROOT}/barks-reader-linux" # where scripts/build.sh leaves it on Linux

# Status codes a stage returns besides pass (0) and fail (anything else).
SKIPPED=3
WARNED=4

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
        [[ -x "$app" ]] || { echo "run_overnight: not an executable: $app" >&2; exit 2; }
        app="$(realpath "$app")"
        shift 2
        ;;
    *)
        echo "run_overnight: unknown option $1 (see --list, or the header)" >&2
        exit 2
        ;;
    esac
done

for name in ${only//,/ } ${skip//,/ }; do
    if [[ " ${STAGES[*]} " != *" $name "* ]]; then
        echo "run_overnight: no stage called $name (see --list)" >&2
        exit 2
    fi
done

if [[ "$(uname -s)" != Linux* ]]; then
    echo "run_overnight: Linux only (xvfb, systemd-inhibit, the GUI probe)" >&2
    exit 2
fi

# Hold off sleep for the whole run, as run_gui_overnight.sh does (see there).
inhibitor=""
if command -v systemd-inhibit >/dev/null; then
    systemd-inhibit --what=sleep:idle --who="Barks Reader overnight run" \
        --why="The overnight test run" sleep infinity >/dev/null 2>&1 &
    inhibitor=$!
    trap '[[ -n "$inhibitor" ]] && kill "$inhibitor" 2>/dev/null; true' EXIT
fi

on_battery() {
    local supply
    for supply in /sys/class/power_supply/*; do
        [[ -f "$supply/type" && "$(cat "$supply/type")" == Mains ]] || continue
        [[ "$(cat "$supply/online" 2>/dev/null)" == 0 ]] && return 0
    done
    return 1
}
if on_battery; then
    echo "run_overnight: WARNING - on battery: a throttled CPU can fail the timing budgets; plug in"
fi

wanted() {
    local name="$1"
    [[ -n "$only" && ",$only," != *",$name,"* ]] && return 1
    [[ -n "$skip" && ",$skip," == *",$name,"* ]] && return 1
    return 0
}

stamp="$(date +%Y%m%d-%H%M%S)"
log_dir="build/overnight/${stamp}"
mkdir -p "$log_dir"

# The executable the smoke and GUI stages use: --app's, else the one the build
# stage made this run. Empty until there is one.
exe="$app"

# The Kivy tests in the unit suite need a display; a run started from a timer
# or ssh has none, so pytest runs on a throwaway Xvfb, as in CI.
with_display() {
    if command -v xvfb-run >/dev/null; then
        xvfb-run --auto-servernum "$@"
    else
        "$@"
    fi
}

# pyproject.toml pins what may move, so `uv lock --upgrade` moves each
# dependency as far as it allows. The upgraded lock is only needed to sync the
# drift venv, so uv.lock is put back straight after - and on any exit, in case
# the run is stopped in between. A subshell, so its traps are its own.
dep_drift() (
    local drift_env="${REPO_ROOT}/build/overnight/venv-drift"
    local saved="${REPO_ROOT}/${log_dir}/uv.lock.saved"
    cp uv.lock "$saved"
    trap 'cp "$saved" uv.lock' EXIT
    trap 'exit 143' TERM
    trap 'exit 130' INT
    trap 'exit 129' HUP
    local moved
    moved="$(uv lock --upgrade 2>&1)"
    echo "dep-drift: what an upgrade moves:"
    grep -E '^(Updated|Added|Removed) ' <<<"$moved" | sed 's/^/  /' || echo "  nothing"
    export UV_PROJECT_ENVIRONMENT="$drift_env"
    uv sync --locked --quiet
    cp "$saved" uv.lock
    echo "dep-drift: uv.lock put back; running the suite in ${drift_env}"
    with_display uv run --no-sync pytest -q
)

siblings() {
    local repo status=0 ran=0
    for repo in "${SIBLINGS[@]}"; do
        if [[ ! -d "$repo/tests" ]]; then
            echo "siblings: ${repo}: no tests/, nothing to run"
            continue
        fi
        echo "siblings: ${repo}"
        ran=1
        # Their own venv and their lock as it is (--frozen: never rewritten from
        # here); VIRTUAL_ENV unset, since ours is not theirs.
        (cd "$repo" && unset VIRTUAL_ENV && with_display uv run --frozen pytest -q) || status=1
    done
    ((ran)) || return "$SKIPPED"
    return "$status"
}

# One seventh of core/'s modules, by weekday: every module once a week, and a
# night's slice a few hundred mutants instead of a full sweep's six thousand.
# The testing helpers are left out; they are not the code under test.
mutation() {
    local day="${BARKS_OVERNIGHT_MUTATION_DAY:-$(date +%u)}"
    local core="src/barks-reader/src/barks_reader/core"
    local globs=() i=0 path
    while read -r path; do
        (( i % 7 == day - 1 )) && globs+=("*/core/${path#"${core}/"}")
        i=$((i + 1))
    done < <(find "$core" -name '*.py' ! -name '__init__.py' ! -path '*/testing/*' \
        ! -path '*/__pycache__/*' | sort)
    if ((${#globs[@]} == 0)); then
        echo "mutation: no modules in slice ${day} of 7"
        return "$SKIPPED"
    fi
    echo "mutation: slice ${day} of 7, ${#globs[@]} module(s):"
    printf '  %s\n' "${globs[@]}"
    # mutmut.sh writes its argument as setup.cfg's only_mutate, where configparser
    # reads further lines of a value only when they are indented.
    bash "${SCRIPT_DIR}/mutmut.sh" "$(printf '%s\n' "${globs[@]}" | sed -e '2,$s/^/    /')"
}

# Run one stage. It returns SKIPPED (saying why) or WARNED as well as pass/fail.
run_stage() {
    local status=0
    case "$1" in
    validate) uv run scripts/validate-barks-reader-files.py ;;
    panel-sources) uv run scripts/check-barks-panel-sources.py ;;
    censorship)
        env -u VIRTUAL_ENV uv run --offline --project ../barks-comic-building \
            barks-check-build --log-level SUCCESS --censorship-only
        ;;
    wiki-order) uv run scripts/check_wiki_story_order.py --quiet || return "$WARNED" ;;
    lint) bash "${SCRIPT_DIR}/full-lint.sh" ;;
    audit) uv audit || return "$WARNED" ;;
    pytest)
        uv sync --locked
        with_display uv run pytest -q --cov --cov-report=term:skip-covered
        ;;
    # Installed, pytest-randomly shuffles every run; it prints its seed at the top.
    random-order) with_display uv run --with pytest-randomly pytest -q ;;
    dep-drift) dep_drift ;;
    siblings) siblings ;;
    build)
        if [[ -n "$app" ]]; then
            echo "build: skipped - using --app ${app}"
            return "$SKIPPED"
        fi
        bash "${SCRIPT_DIR}/build.sh"
        ;;
    smoke)
        if [[ -z "$exe" ]]; then
            echo "smoke: skipped - no executable (the build stage did not make one; or give --app)"
            return "$SKIPPED"
        fi
        bash "${SCRIPT_DIR}/smoke-test-build.sh" "$exe"
        ;;
    gui)
        local args=()
        [[ -n "$exe" ]] && args=(--app "$exe")
        [[ -z "$exe" ]] && echo "gui: no executable, so no built-app stage"
        BARKS_OVERNIGHT_SOAK_STEPS="${BARKS_OVERNIGHT_SOAK_STEPS:-1000}" \
            BARKS_OVERNIGHT_SOAK_SEEDS="${BARKS_OVERNIGHT_SOAK_SEEDS:-$(soak_seeds)}" \
            bash "${SCRIPT_DIR}/run_gui_overnight.sh" "${args[@]}"
        ;;
    gui-timings)
        local jsonl="${REPO_ROOT}/${log_dir}/gui-timings.jsonl"
        BARKS_GUI_TIMINGS="$jsonl" bash "${SCRIPT_DIR}/run_gui_tests.sh" --headless --progress \
            || status=$?
        # A failed suite outranks drift; drift alone is a warning.
        if ! PYTHONPATH="src/barks-reader/tests/gui:scripts" uv run python -m barks_gui.timings \
            drift "$jsonl" && ((status == 0)); then
            status=$WARNED
        fi
        return "$status"
        ;;
    graphify)
        if ! command -v graphify >/dev/null; then
            echo "graphify: skipped - graphify is not installed"
            return "$SKIPPED"
        fi
        graphify update .
        ;;
    mutation) mutation ;;
    esac
}

# Three walks a night, new ones each night (10#: day 008 is not octal).
soak_seeds() {
    local day=$((10#$(date +%j)))
    echo "$((day * 10 + 1)) $((day * 10 + 2)) $((day * 10 + 3))"
}

elapsed() {
    printf '%dh%02dm' $(($1 / 3600)) $(($1 % 3600 / 60))
}

# The results so far, to summary.txt - rewritten after every stage, so a run
# stopped part way still leaves what it found.
write_summary() {
    {
        echo "==== overnight run, ${stamp} ($(git rev-parse --short HEAD)): $1 ===="
        for i in "${!names[@]}"; do
            printf '%-14s %-8s %4dm%02ds\n' "${names[$i]}" "${results[$i]}" \
                "$((durations[i] / 60))" "$((durations[i] % 60))"
        done
        echo "logs: ${log_dir}/"
    } >"${log_dir}/summary.txt"
}

selected=()
for name in "${STAGES[@]}"; do
    wanted "$name" && selected+=("$name")
done
echo "run_overnight: ${#selected[@]} stages: ${selected[*]}"
echo "run_overnight: to stop it and everything it started: Ctrl-C, or kill $$"
echo "run_overnight: results so far in ${log_dir}/summary.txt"

# A stage, its output to the screen and its log; the status is run_stage's
# (pipefail: tee's own never masks it).
log_stage() {
    run_stage "$1" 2>&1 | tee "${log_dir}/$1.log"
}

# Stopping the run stops the stage running, and the stages after it are not
# started: the same signal handling as the GUI runners (see _gui_run.sh).
GUI_RUNNER=run_overnight
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
        "$SKIPPED") results+=("skipped") ;;
        "$WARNED") results+=("WARNED") ;;
        *)
            results+=("FAILED")
            failed=1
            ;;
        esac
    fi
    # The build stage runs in a child, so its executable is picked up here.
    if [[ "$name" == build && "$status" -eq 0 && -x "$BUILT_EXE" ]]; then
        exe="$BUILT_EXE"
    fi
    names+=("$name")
    durations+=("$((SECONDS - started))")
    echo "==== ${name}: ${results[-1]} in $((durations[-1] / 60))m$((durations[-1] % 60))s ===="
    if [[ -n "$GUI_INTERRUPTED" ]]; then
        write_summary "stopped during ${name}, $(elapsed $((SECONDS - run_started))) in"
        # A GUI stage's runner cleans up what it started on its way out; this
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
