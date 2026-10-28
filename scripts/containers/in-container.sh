#!/usr/bin/env bash
# The overnight run's slice that runs inside a distro container: started by
# scripts/run_overnight_container.sh from the root of the container's own clone of the
# commit the host checkout is on, never by hand on the host. The runner mounts this
# script from its own checkout, so the stages are the clone's and this script the host's.
#
# What it runs, each through scripts/run_overnight.sh so the results and logs are the
# usual ones (build/overnight/<stamp>/ in that clone):
#   1. data, pytest, build, smoke, gui and gui-timings: the suite, a Nuitka build made on
#      this distro, its smoke test, the GUI suite and a soak against it (the gui stage's
#      built-app and built-app-soak only, not run_gui_overnight.sh's 3 hours), and the
#      base GUI suite on the workspace app against the host's GUI timing calibration;
#   2. with --host-build PATH, the same smoke test, GUI suite and soak against the
#      executable the host built: the one a user of this distro would download.
#
# Assumes: the data pack is mounted at the same paths as on the host, and the clone has
# .env.runtime (the runner copies both in).
#
# Usage: in-container.sh [--host-build PATH] [run_overnight.sh options]
#   Any further options go to the first run (e.g. --skip gui-timings).
set -euo pipefail

[[ -f scripts/run_overnight.sh ]] || { echo "in-container: not run from the clone's root" >&2; exit 2; }

STAGES=data,pytest,build,smoke,gui,gui-timings
HOST_BUILD_STAGES=smoke,gui
# The GUI stages a distro's libraries can break that the base suite does not reach: the
# packaged executable, which loads them, under the suite and a soak's deeper paths.
export BARKS_OVERNIGHT_GUI_STAGES=built-app,built-app-soak
VERSION_FILE="src/barks-reader/src/barks_reader/_version.py"

host_build=""
if [[ "${1:-}" == --host-build ]]; then
    host_build="${2:?--host-build needs the path of the executable}"
    shift 2
fi

# shellcheck source=/dev/null
source /etc/os-release
echo "in-container: ${PRETTY_NAME}, $(ldd --version | head -1), commit $(git rev-parse --short HEAD)"

# The two gitignored modules every workspace boot imports. The version module is CI's
# stub until the build stage writes the real one: pytest runs before it.
bash scripts/generate-panel-module.sh
[[ -f "$VERSION_FILE" ]] || printf 'COPYRIGHT_YEARS = "2025-2026"\nVERSION = "container"\n' \
    >"$VERSION_FILE"

# A commit older than BARKS_OVERNIGHT_GUI_STAGES would run every GUI stage (3 hours):
# leave the gui stage out there.
if ! grep -q BARKS_OVERNIGHT_GUI_STAGES scripts/run_overnight.sh; then
    echo "in-container: this commit's run_overnight.sh runs every GUI stage; no gui stage"
    STAGES="${STAGES/,gui,/,}"
    HOST_BUILD_STAGES=smoke
fi

status=0
bash scripts/run_overnight.sh --only "$STAGES" "$@" || status=$?

if [[ -n "$host_build" ]]; then
    echo
    echo "in-container: the host's build on ${PRETTY_NAME}"
    bash scripts/run_overnight.sh --only "$HOST_BUILD_STAGES" --app "$host_build" || status=$?
else
    echo "in-container: no host build given, so no tests of it"
fi
exit "$status"
