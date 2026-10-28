#!/bin/bash
# build-data-zips.sh - Create the two reader data packs (no exe build).
#
# Standalone extraction of the zip step from build.sh, so the packs can be rebuilt
# without the (slow) Nuitka compile. build.sh --include-zips calls this.
#
# Each pack carries "Reader Files/data-pack.json" (written by scripts/data_manifest.py
# --write-pack-manifest): its version N - the N of the data-vN release that
# upload-data-zips.sh will publish it as, which reads N back from the pack - and the
# fingerprint of each Reader Files folder it holds. N is the newest data-vN release on
# GitHub plus one, or --version N (offline, or to rebuild a number). The packs hold
# exactly the folders data_manifest.py lists (--list-entries), so the backup folders
# beside them (Indexes-old and the like) stay home.
#
# Usage: bash scripts/build-data-zips.sh [--version N]

set -eo pipefail

# Zips are always written to the repo root (where upload-data-zips.sh looks).
cd "$(dirname "$0")/.."
# shellcheck source=scripts/_data_release.sh
source scripts/_data_release.sh

DATA_FILES_PARENT_DIR="${HOME}/Books/Carl Barks/Compleat Barks Disney Reader"
CONFIG_FILES_SUBDIR="Configs"
DATA_FILES_SUBDIR="Reader Files"
PANELS_ZIP="Barks Panels.zip"

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

format_elapsed() {
    printf '%dm%02ds' $(($1 / 60)) $(($1 % 60))
}

VERSION=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --version) VERSION="$2"; shift 2 ;;
        *) echo -e "${RED}Unknown argument: $1${NC}" >&2; exit 1 ;;
    esac
done
if [[ -z "$VERSION" ]]; then
    LAST_N=$(latest_data_version) || {
        echo -e "${RED}Cannot list the data-vN releases on GitHub (gh offline or not logged in):" \
            "pass --version N.${NC}" >&2
        exit 1
    }
    VERSION=$((LAST_N + 1))
fi
if [[ ! "$VERSION" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}--version takes a number, not \"${VERSION}\".${NC}" >&2
    exit 1
fi

mapfile -t ENTRIES < <(uv run scripts/data_manifest.py --list-entries)
PACK1_PATHS=("${CONFIG_FILES_SUBDIR}")
for entry in "${ENTRIES[@]}"; do
    [[ "$entry" == "$PANELS_ZIP" ]] && continue
    PACK1_PATHS+=("${DATA_FILES_SUBDIR}/${entry}")
done

# The version file is staged outside the data tree and zipped in from there, so the
# build never writes into the folders it packs.
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
echo -e "${YELLOW}Writing the version file for data pack ${VERSION}...${NC}"
uv run scripts/data_manifest.py --write-pack-manifest "${STAGE}/${PACK_MEMBER}" \
    --version "$VERSION" --reader-files "${DATA_FILES_PARENT_DIR}/${DATA_FILES_SUBDIR}"

echo -e "${YELLOW}Creating data packs \"${DATA1_ZIP}\" and \"${DATA2_ZIP}\"...${NC}"
DATA_ZIPS_START=$SECONDS
rm -f "${DATA1_ZIP}" "${DATA2_ZIP}"
THIS_DIR=${PWD}
pushd "${DATA_FILES_PARENT_DIR}" >/dev/null
zip -rq "${THIS_DIR}/${DATA1_ZIP}" "${PACK1_PATHS[@]}"
zip -q "${THIS_DIR}/${DATA2_ZIP}" "${DATA_FILES_SUBDIR}/${PANELS_ZIP}"
popd >/dev/null
pushd "${STAGE}" >/dev/null
zip -q "${THIS_DIR}/${DATA1_ZIP}" "${PACK_MEMBER}"
zip -q "${THIS_DIR}/${DATA2_ZIP}" "${PACK_MEMBER}"
popd >/dev/null
echo -e "Data zips took $(format_elapsed $((SECONDS - DATA_ZIPS_START)))."
echo -e "${GREEN}Data pack ${VERSION} complete.${NC}"
