#!/bin/bash
# build.sh - Regular build (uses already-obfuscated modules)

set -eo pipefail

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

# Nuitka's --product-version (and the {VERSION} token in --onefile-tempdir-spec) needs a
# numeric dotted version. Derive one from the git describe: the leading tag numbers plus
# the commit-count. e.g. "v0.9.0.alpha.1-815-g9fce0c9-dirty" -> "0.9.0.815".
NUMERIC_VERSION=$(echo "$VERSION" | sed -E 's/^v//; s/[^0-9.].*$//; s/\.+$//')
COMMITS=$(echo "$VERSION" | grep -oE -- '-[0-9]+-g' | grep -oE '[0-9]+' | head -1 || true)
[[ -n "$COMMITS" ]] && NUMERIC_VERSION="${NUMERIC_VERSION}.${COMMITS}"
[[ -z "$NUMERIC_VERSION" ]] && NUMERIC_VERSION="0.0.0"


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

case "$(uname -s)" in
    Linux*)
        OS="linux"
        EXE="barks-reader-linux"
        ;;
    Darwin*)
        OS="macos"
        ARCH=$(uname -m)
        if [[ "$ARCH" == "arm64" ]]; then
            # Assume most macOS users are arm64.
            EXE="barks-reader-macos"
        else
            EXE="barks-reader-macos-x64"
        fi
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

echo -e "${YELLOW}Building with Nuitka for platform \"${OS}\"...${NC}"

NUITKA_OUT_DIR="build/nuitka"
rm -rf "${NUITKA_OUT_DIR}/${EXE}.build" "${NUITKA_OUT_DIR}/${EXE}.dist" "./${EXE}"
mkdir -p "${NUITKA_OUT_DIR}"

# Nuitka compiles the whole app to native code and bundles Python + all dependencies
# into a single self-contained executable (--onefile). No runtime venv/uv, no first-run
# download. This also compiles the plain-Python get_panel_bytes module (with the embedded
# BARKS_ZIPS_KEY) to native code, so the panel key is not shipped as readable source.
#
# Data files:
#   - Kivy's data (kv lang, fonts, shaders) and each app package's bundled assets
#     (.kv/.ttf/.db/images) are pulled in via --include-package-data.
#   - barks_fantagraphics' INTERNAL_DATA_DIR lives outside the package in the source
#     tree (src/barks-fantagraphics/data); map it alongside the package so the
#     packaged-layout branch of comics_consts.INTERNAL_DATA_DIR resolves it.
#   - cpi.db ships inside comic_utils, so --include-package-data=comic_utils covers it.
#
# .env.runtime is intentionally NOT bundled (it holds secrets); a compiled build reads
# neither it nor the *_CONFIG_DIR/*_DATA_DIR env vars (see config_info.IS_COMPILED).
uv run python -m nuitka \
    --standalone \
    --onefile \
    --assume-yes-for-downloads \
    --enable-plugin=kivy \
    --include-package-data=kivy \
    --include-package-data=barks_reader \
    --include-package-data=okf_reader \
    --include-package-data=comic_utils \
    --include-package-data=pyuca \
    --include-package-data=docutils \
    --include-package=barks_reader \
    --include-package=barks_fantagraphics \
    --include-package=barks_build_comic_images \
    --include-package=barks_kivy_ui \
    --include-package=okf_reader \
    --include-package=comic_utils \
    --include-data-dir=src/barks-fantagraphics/data=barks_fantagraphics/data \
    --output-dir="${NUITKA_OUT_DIR}" \
    --output-filename="${EXE}" \
    --product-name="Barks Reader" \
    --product-version="${NUMERIC_VERSION}" \
    --onefile-tempdir-spec="{CACHE_DIR}/BarksReader/{VERSION}" \
    main.py || {
    echo -e "${RED}ERROR: Nuitka build failed.${NC}"
    exit 1
}

# Move the finished single-file executable to the repo root (where CI uploads it from).
mv -f "${NUITKA_OUT_DIR}/${EXE}" "./${EXE}"
echo -e "Executable written to \"./${EXE}\"."

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
