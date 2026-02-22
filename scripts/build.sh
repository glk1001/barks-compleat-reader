#!/bin/bash
# build.sh - Regular build (uses already-obfuscated modules)

set -e

if [[ "$1" == "--include-zips" ]]; then
  declare -r DO_ZIPS=1
else
  declare -r DO_ZIPS=0
fi

VERSION_FILE="src/barks-reader/src/barks_reader/_version.py"
DATA_FILES_PARENT_DIR="${HOME}/Books/Carl Barks/Compleat Barks Disney Reader"
CONFIG_FILES_SUBDIR="Configs"
DATA_FILES_SUBDIR="Reader Files"
DATA1_ZIP="barks-reader-data-1.zip"
DATA2_ZIP="barks-reader-data-2.zip"

# --- Get version from git ---
get_git_version() {
    if git rev-parse --git-dir > /dev/null 2>&1; then
        git describe --tags --dirty --always
    else
        echo "0.0.0-dev"
    fi
}

VERSION=$(get_git_version)
COPYRIGHT_YEARS="2025"


echo "=================================================="
echo "Building Barks Compleat Reader"
echo "=================================================="

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

# --- Write version file ---
echo -e "${YELLOW}Writing version: $VERSION ...${NC}"

echo "COPYRIGHT_YEARS = \"${COPYRIGHT_YEARS}\"" > "$VERSION_FILE"
echo "" >> "$VERSION_FILE"
echo "# noinspection SpellCheckingInspection" >> "$VERSION_FILE"
echo "VERSION = \"${VERSION}\"" >> "$VERSION_FILE"
echo "" >> "$VERSION_FILE"

echo -e "Successfully wrote version to \"${VERSION_FILE}\"."
echo

if [[ ! -f pycrucible.toml ]]; then
    echo "${RED}ERROR: Could not find \"pycrucible.toml\".${NC}"
    exit 1
fi

case "$(uname -s)" in
    Linux*)
        OS="linux"
        EXE="barks-reader-linux"
        ;;
    Darwin*)
        OS="macos"
        EXE="barks-reader-macos"
        ;;
    CYGWIN*|MINGW*|MSYS*|Windows_NT*)
        OS="windows"
        EXE="barks-reader-win.exe"
        ;;
    *)
        echo "${RED}ERROR: OS unknown.${NC}"
        exit 1
        ;;
esac

echo -e "${YELLOW}Building with pycrucible for platform \"${OS}\"...${NC}"
rm -rf ./pycrucible_payload

# Strip workspace config from pyproject.toml before bundling.
# Workspace member pyproject.toml files cannot be bundled (pycrucible flat archive limitation),
# so uv would fail trying to find them. PYTHONPATH in pycrucible.toml handles package discovery.
cp -p pyproject.toml pyproject.toml.bundle_bak
trap 'mv -f pyproject.toml.bundle_bak pyproject.toml 2>/dev/null' EXIT
python3 <<'PYEOF'
import re
with open('pyproject.toml') as f:
    content = f.read()
for pkg in ['barks-reader', 'barks-fantagraphics', 'barks-build-comic-images', 'comic-utils']:
    content = re.sub('\n    "' + pkg + '",', '', content)
content = re.sub(r'\n\[tool\.uv\.workspace\]\n.*?(?=\n\[)', '', content, flags=re.DOTALL)
content = re.sub(r'\n\[tool\.uv\.sources\]\n.*?(?=\n\[|\Z)', '', content, flags=re.DOTALL)
with open('pyproject.toml', 'w') as f:
    f.write(content)
PYEOF

if [[ "${OS}" == "windows" ]]; then
    cp -p pycrucible.toml pycrucible.toml.orig
    sed -i '/^PYTHONPATH/s/:/;/g' pycrucible.toml
fi

uv run pycrucible --embed . -o "${EXE}"

if [[ "${OS}" == "windows" ]]; then
    mv pycrucible.toml.orig pycrucible.toml
fi

mv pyproject.toml.bundle_bak pyproject.toml
trap - EXIT

if [[ $DO_ZIPS == 1 ]]; then
  echo
  echo -e "${YELLOW}Creating data zips \"${DATA1_ZIP}\" and \"${DATA2_ZIP}\"...${NC}"
  rm -f "${DATA1_ZIP}" "${DATA2_ZIP}"
  THIS_DIR=${PWD}
  pushd "${DATA_FILES_PARENT_DIR}" >/dev/null
  zip -rq "${THIS_DIR}/${DATA1_ZIP}" "${DATA_FILES_SUBDIR}" "${CONFIG_FILES_SUBDIR}" -x "${DATA_FILES_SUBDIR}/Barks Panels.zip"
  zip -rq "${THIS_DIR}/${DATA2_ZIP}" "${DATA_FILES_SUBDIR}/Barks Panels.zip"
  popd >/dev/null
  echo
fi

echo -e "${GREEN}=================================================="
echo -e "Build complete!"
echo -e "==================================================${NC}"
