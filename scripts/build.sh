#!/bin/bash
# build.sh - Regular build (uses already-obfuscated modules)

set -eo pipefail

if [[ "$1" == "--include-zips" ]]; then
  declare -r DO_ZIPS=1
else
  declare -r DO_ZIPS=0
fi

# Guard: the plain-Python panel module is a generated, gitignored artifact that Nuitka
# compiles to native code (with the embedded BARKS_ZIPS_KEY). It is NOT regenerated here
# - CI runs scripts/generate-panel-module.sh as a separate step first. Fail fast with a
# clear message rather than deep inside the Nuitka run if it is missing.
PANEL_MODULE="src/comic-utils/src/comic_utils/get_panel_bytes.py"
if [[ ! -f "$PANEL_MODULE" ]]; then
    echo "ERROR: generated panel module \"$PANEL_MODULE\" not found." >&2
    echo "       Run 'bash scripts/generate-panel-module.sh' first (needs BARKS_ZIPS_KEY)." >&2
    exit 1
fi

VERSION_FILE="src/barks-reader/src/barks_reader/_version.py"

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
# numeric dotted version of AT MOST 4 integer fields (Nuitka hard-fails on more). Derive
# one from the git describe: the leading tag numbers plus the commit-count, truncated to
# 4 fields. e.g. "v0.9.0.alpha.1-815-g9fce0c9-dirty" -> "0.9.0.815". A non-tag-shaped
# describe (bare commit hash from an untagged clone) falls back to a 0.0.0 base.
if [[ "$VERSION" =~ ^v?[0-9]+\. ]]; then
    NUMERIC_VERSION=$(echo "$VERSION" | sed -E 's/^v//; s/[^0-9.].*$//; s/\.+$//')
else
    NUMERIC_VERSION="0.0.0"
fi
COMMITS=$(echo "$VERSION" | grep -oE -- '-[0-9]+-g' | grep -oE '[0-9]+' | head -1 || true)
[[ -n "$COMMITS" ]] && NUMERIC_VERSION="${NUMERIC_VERSION}.${COMMITS}"
NUMERIC_VERSION=$(echo "$NUMERIC_VERSION" | cut -d. -f1-4)


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
# Work/bundle dirs are named from --output-folder-name=${EXE} (without it Nuitka would
# name them after the compiled script, i.e. main.build/main.dist/main.app).
rm -rf "${NUITKA_OUT_DIR}/${EXE}.build" "${NUITKA_OUT_DIR}/${EXE}.dist" \
    "${NUITKA_OUT_DIR}/${EXE}.onefile-build" "${NUITKA_OUT_DIR}/${EXE}.app" \
    "./${EXE}" "./${EXE}.zip"
mkdir -p "${NUITKA_OUT_DIR}"

# Nuitka compiles the whole app to native code and bundles Python + all dependencies
# (--mode=app: a single self-extracting onefile executable on Linux/Windows, a macOS
# .app bundle on macOS - pyobjc/Foundation, pulled in by screeninfo, requires a bundle
# there). No runtime venv/uv, no first-run download. This also compiles the plain-Python
# get_panel_bytes module (with the embedded BARKS_ZIPS_KEY) to native code, so the panel
# key is not shipped as readable source.
#
# Data files:
#   - Kivy's data (kv lang, fonts, shaders) and each app package's bundled assets
#     (.kv/.ttf/.db/images) are pulled in via --include-package-data.
#   - barks_fantagraphics' INTERNAL_DATA_DIR lives outside the package in the source
#     tree (src/barks-fantagraphics/data); map it alongside the package so the
#     packaged-layout branch of comics_consts.INTERNAL_DATA_DIR resolves it.
#     (--include-package-data=barks_fantagraphics separately covers the in-package
#     empty_page.png.)
#   - cpi.db ships inside comic_utils, so --include-package-data=comic_utils covers it.
#
# .env.runtime is intentionally NOT bundled (it holds secrets); a compiled build reads
# neither it nor the *_CONFIG_DIR/*_DATA_DIR env vars (see config_info.IS_COMPILED).

# Platform-specific Nuitka args. The onefile extraction-dir spec only applies where
# --mode=app means onefile (a macOS .app bundle is standalone-layout, and Nuitka warns
# on the unused option); the .app bundle wants a dock icon (Nuitka warns without one).
PLATFORM_ARGS=()
if [[ "${OS}" == "macos" ]]; then
    PLATFORM_ARGS+=(--macos-app-icon="assets/app-icon.icns")
else
    PLATFORM_ARGS+=(--onefile-tempdir-spec="{CACHE_DIR}/BarksReader/{VERSION}")
fi

format_elapsed() {
    printf '%dm%02ds' $(($1 / 60)) $(($1 % 60))
}

NUITKA_LOG=$(mktemp)
trap 'rm -f "$NUITKA_LOG"' EXIT
NUITKA_START=$SECONDS

# (No kivy flags needed: the kivy plugin is always enabled, and Nuitka's built-in kivy
# package config bundles the whole kivy/data dir - adding --include-package-data=kivy
# would only produce duplicate-data-file warnings.)
uv run python -m nuitka \
    --mode=app \
    --assume-yes-for-downloads \
    --include-package-data=barks_reader \
    --include-package-data=barks_fantagraphics \
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
    --output-folder-name="${EXE}" \
    --product-name="Barks Reader" \
    --product-version="${NUMERIC_VERSION}" \
    "${PLATFORM_ARGS[@]}" \
    main.py 2>&1 | tee "$NUITKA_LOG" || {
    echo -e "${RED}ERROR: Nuitka build failed.${NC}"
    exit 1
}

echo -e "Nuitka build took $(format_elapsed $((SECONDS - NUITKA_START)))."

# Nuitka reports some real packaging degradation as warnings while still exiting 0
# (e.g. an --include-package-data name that no longer resolves, or an empty
# --include-data-dir). Fail the build on those specific patterns - NOT on all warnings,
# since e.g. the kivy plugin emits a benign one every build.
if grep -qE "No matching data file|No data files in directory|Failed to locate package directory|Did not follow import to unused" "$NUITKA_LOG"; then
    echo -e "${RED}ERROR: Nuitka reported missing packages/data (see warnings above) — build would be broken.${NC}"
    exit 1
fi

# Move the finished artifact to the repo root (where CI uploads it from):
# a single-file executable on Linux/Windows, a zipped .app bundle on macOS.
if [[ "${OS}" == "macos" ]]; then
    ZIP_START=$SECONDS
    ditto -c -k --keepParent "${NUITKA_OUT_DIR}/${EXE}.app" "./${EXE}.zip"
    echo -e "App bundle written to \"./${EXE}.zip\"" \
        "(zip took $(format_elapsed $((SECONDS - ZIP_START))))."
else
    mv -f "${NUITKA_OUT_DIR}/${EXE}" "./${EXE}"
    echo -e "Executable written to \"./${EXE}\"."
fi

if [[ $DO_ZIPS == 1 ]]; then
  echo
  bash "$(dirname "$0")/build-data-zips.sh"
  echo
fi

echo -e "${GREEN}=================================================="
echo -e "Build complete!"
echo -e "==================================================${NC}"
