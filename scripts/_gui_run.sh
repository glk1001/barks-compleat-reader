#!/usr/bin/env bash
# Sourced by the GUI runners (run_gui_tests.sh, run_gui_matrix.sh,
# run_gui_overnight.sh): run a child so that stopping the runner stops it too.
#
# bash runs a trap only between commands, so a runner sitting in a foreground
# pipeline would not act on a TERM or HUP sent to it alone until the whole
# suite had finished. `gui_run` runs the child in the background and waits for
# it, which a trapped signal interrupts at once; `gui_trap_signals` installs
# the traps, which stop the child's whole process tree and record the signal.
# A background child ignores Ctrl-C's SIGINT (bash does that to async commands in
# a script), so the traps are also what makes Ctrl-C stop it: they TERM the child's
# whole tree, for Ctrl-C, a `kill` of the runner and a closed terminal alike. What
# the probe started lives in sessions of its own, which no signal here reaches:
# each runner's exit runs `gui-probe.sh cleanup` for that.

GUI_CHILD=""
GUI_INTERRUPTED=""
GUI_TREE=""
# How long an interrupted runner waits for its child's tree to finish cleaning up.
GUI_STOP_WAIT_SECS=60

_gui_descendants() {
    local child
    for child in $(pgrep -P "$1" 2>/dev/null); do
        _gui_descendants "$child"
        echo "$child"
    done
}

# TERM a process and everything under it, deepest first.
gui_kill_tree() {
    local pids
    pids="$(_gui_descendants "$1")"
    # shellcheck disable=SC2086  # one pid per word
    [[ -n "$pids" ]] && kill -TERM $pids 2>/dev/null
    kill -TERM "$1" 2>/dev/null
    return 0
}

_gui_on_signal() {
    GUI_INTERRUPTED="$1"
    # The child first: the terminal (or the tee the output went through) may be
    # gone, and a runner must not fall before it has stopped what it runs.
    if [[ -n "$GUI_CHILD" ]]; then
        GUI_TREE="$(_gui_descendants "$GUI_CHILD") $GUI_CHILD"
        gui_kill_tree "$GUI_CHILD"
    fi
    echo "${GUI_RUNNER:-gui}: interrupted - stopping the run..." >&2 || true
    return 0
}

# INT, TERM and HUP stop the child and set GUI_INTERRUPTED to the exit code a
# runner should end with (130, 143, 129). SIGPIPE is ignored: once the terminal
# or a tee is gone, a write fails instead of killing the runner mid-cleanup.
gui_trap_signals() {
    trap '' PIPE
    trap '_gui_on_signal 130' INT
    trap '_gui_on_signal 143' TERM
    trap '_gui_on_signal 129' HUP
}

# Run "$@" in the background and return its exit status, waiting it out even
# when a signal interrupts the wait (the child is then on its way down).
gui_run() {
    local status=0
    "$@" &
    GUI_CHILD=$!
    wait "$GUI_CHILD" || status=$?
    while kill -0 "$GUI_CHILD" 2>/dev/null; do
        wait "$GUI_CHILD" || status=$?
    done
    GUI_CHILD=""
    # Interrupted: the child's own shell may be gone at once while a runner under
    # it is still stopping what it started. Wait for the whole tree, so that when
    # this runner says it has stopped, it has.
    if [[ -n "$GUI_INTERRUPTED" ]]; then
        local deadline=$((SECONDS + GUI_STOP_WAIT_SECS)) pid alive
        while ((SECONDS < deadline)); do
            alive=""
            for pid in $GUI_TREE; do
                kill -0 "$pid" 2>/dev/null && alive=1 && break
            done
            [[ -z "$alive" ]] && break
            sleep 0.2
        done
    fi
    return "$status"
}
