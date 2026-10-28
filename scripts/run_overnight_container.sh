#!/usr/bin/env bash
# Run a slice of the overnight run on another distro, in a rootless podman container on
# this machine: what this distro's own run (scripts/run_overnight.sh) does not show - a
# distro's own libraries (glibc, Mesa, the X libraries, fonts) under the suite, a Nuitka
# build and the base GUI suite, and whether the executable built here runs there.
#
#   1. builds the distro's image (scripts/containers/<distro>.Containerfile) with
#      --pull=newer, so a new release or update of the base image comes in;
#   2. brings the container's own clone of this repo, in ~/overnight-containers/<distro>
#      (the container's home), to the commit this checkout is on - uncommitted changes
#      here are not tested - and copies in .env.runtime and this machine's GUI timing
#      calibration (.benchmarks/gui-timings.json, so the budgets are this hardware's);
#   3. runs scripts/containers/in-container.sh there (the stages it runs: its header),
#      with the data pack mounted read-only at the same paths as here, so the profile's
#      absolute paths resolve, and the executable built here (barks-reader-linux, when
#      there is one) for its smoke test.
# The container's home keeps its venv, uv's Python and the caches between runs. Results:
# build/overnight/<stamp>/summary.txt in that clone, one run for the stages and one for
# the smoke test of the build from here; the last lines of this script's output say where.
#
# Assumes: podman, rootless (sudo apt install podman); the data pack where
# copy-to-overnight-host.sh puts it; the sibling barks-wiki checkout (the profile's
# wiki_bundle_dir). The network, for the image, uv's Python and the packages.
# Not while this machine's own overnight run is going: both are timed.
#
# Usage: scripts/run_overnight_container.sh DISTRO [run_overnight.sh options]
#   DISTRO   fedora (a scripts/containers/<name>.Containerfile)
#   Any further options go to its run_overnight.sh (e.g. --skip gui-timings).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

distro="${1:?usage: run_overnight_container.sh DISTRO [run_overnight.sh options]}"
shift
containerfile="${SCRIPT_DIR}/containers/${distro}.Containerfile"
[[ -f "$containerfile" ]] || { echo "run_overnight_container: no ${containerfile}" >&2; exit 2; }
command -v podman >/dev/null || { echo "run_overnight_container: no podman" >&2; exit 2; }

image="barks-overnight-${distro}"
container_home="${HOME}/overnight-containers/${distro}"
repo_path="${REPO_ROOT#"${HOME}/"}" # this checkout under the home, the clone's path too
clone="${container_home}/${repo_path}"
built_exe="${REPO_ROOT}/barks-reader-linux" # where scripts/build.sh leaves it
host_build=/opt/host-build/barks-reader-linux

# What the run reads beyond the clone, as paths under the home: the data pack as
# copy-to-overnight-host.sh lays it out (Reader Files, under opt/barks-reader, is a link
# into the Books tree) and the wiki bundle the profile names.
MOUNTS=(
    "opt/barks-reader"
    "Books/Carl Barks"
    "Documents/Fantagraphics Complete Carl Barks Disney Library"
    "$(dirname "$repo_path")/barks-wiki"
)

sha="$(git rev-parse HEAD)"
echo "run_overnight_container: ${distro}, commit $(git rev-parse --short HEAD)"
[[ -z "$(git status --porcelain --untracked-files=no)" ]] \
    || echo "run_overnight_container: this checkout has uncommitted changes; they are not tested"

uv_version="$(uv --version | awk '{print $2}')"
podman build --pull=newer --build-arg "UV_VERSION=${uv_version}" -t "$image" \
    -f "$containerfile" "${SCRIPT_DIR}/containers"

if [[ ! -d "${clone}/.git" ]]; then
    mkdir -p "$(dirname "$clone")"
    git clone --quiet "$REPO_ROOT" "$clone"
fi
git -C "$clone" fetch --quiet --tags --force "$REPO_ROOT" HEAD
git -C "$clone" checkout --quiet --detach --force "$sha"
# The venv and earlier runs' results stay; everything else untracked goes.
git -C "$clone" clean -ffdxq -e /.venv -e /build/overnight/
install -m 600 .env.runtime "${clone}/.env.runtime"
if [[ -f .benchmarks/gui-timings.json ]]; then
    cp .benchmarks/gui-timings.json "${clone}/.benchmarks/gui-timings.json"
fi

# This checkout's scripts/containers, read-only: in-container.sh is this one's, not the
# clone's (which, at an older commit, may not have it).
volumes=(-v "${container_home}:${HOME}" -v "${SCRIPT_DIR}/containers:/opt/barks-overnight:ro")
for path in "${MOUNTS[@]}"; do
    [[ -d "${HOME}/${path}" ]] || { echo "run_overnight_container: no ~/${path}" >&2; exit 2; }
    mkdir -p "${container_home}/${path}" # the mount point, inside the container's home
    volumes+=(-v "${HOME}/${path}:${HOME}/${path}:ro")
done
in_container=(bash /opt/barks-overnight/in-container.sh)
if [[ -x "$built_exe" ]]; then
    volumes+=(-v "${built_exe}:${host_build}:ro")
    in_container+=(--host-build "$host_build")
else
    echo "run_overnight_container: no ${built_exe}, so no smoke test of this machine's build"
fi

# Hold off sleep for the run, as run_overnight.sh does on the host (there is no
# systemd-inhibit inside the container).
inhibit=()
command -v systemd-inhibit >/dev/null && inhibit=(systemd-inhibit --what=sleep:idle
    --who="Barks Reader ${distro} overnight run" --why="The ${distro} container's test run")

status=0
"${inhibit[@]}" podman run --rm --init --name "$image" --userns=keep-id --tz=local \
    --shm-size=1g --hostname "${distro}-$(hostname)" -e HOME="$HOME" \
    "${volumes[@]}" -w "${HOME}/${repo_path}" "$image" "${in_container[@]}" "$@" || status=$?

echo
echo "run_overnight_container: ${distro} finished with status ${status}; the summaries:"
find "${clone}/build/overnight" -mindepth 2 -maxdepth 2 -name summary.txt -newer "${clone}/.env.runtime" \
    | sort
exit "$status"
