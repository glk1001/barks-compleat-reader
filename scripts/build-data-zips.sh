#!/bin/bash
# build-data-zips.sh - Create the reader data zips (no exe build).
#
# Standalone extraction of the zip step from build.sh, so the data zips can be
# rebuilt without the (slow) Nuitka compile. build.sh --include-zips calls this.

set -eo pipefail

# Zips are always written to the repo root (where upload-data-zips.sh looks).
cd "$(dirname "$0")/.."

DATA_FILES_PARENT_DIR="${HOME}/Books/Carl Barks/Compleat Barks Disney Reader"
CONFIG_FILES_SUBDIR="Configs"
DATA_FILES_SUBDIR="Reader Files"
DATA1_ZIP="barks-reader-data-1.zip"
DATA2_ZIP="barks-reader-data-2.zip"

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

format_elapsed() {
    printf '%dm%02ds' $(($1 / 60)) $(($1 % 60))
}

echo -e "${YELLOW}Creating data zips \"${DATA1_ZIP}\" and \"${DATA2_ZIP}\"...${NC}"
DATA_ZIPS_START=$SECONDS
rm -f "${DATA1_ZIP}" "${DATA2_ZIP}"
THIS_DIR=${PWD}
pushd "${DATA_FILES_PARENT_DIR}" >/dev/null
zip -rq "${THIS_DIR}/${DATA1_ZIP}" "${DATA_FILES_SUBDIR}" "${CONFIG_FILES_SUBDIR}" -x "${DATA_FILES_SUBDIR}/Barks Panels.zip"
zip -rq "${THIS_DIR}/${DATA2_ZIP}" "${DATA_FILES_SUBDIR}/Barks Panels.zip"
popd >/dev/null
echo -e "Data zips took $(format_elapsed $((SECONDS - DATA_ZIPS_START)))."
echo -e "${GREEN}Data zips complete.${NC}"
