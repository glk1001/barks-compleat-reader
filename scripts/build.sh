#!/bin/bash
# build.sh - Regular build (uses already-obfuscated modulea)

set -e

echo "=================================================="
echo "Building Barks Compleat Reader"
echo "=================================================="

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

if [[ ! -f pycrucible.toml ]]; then
    echo "ERROR: Could not find \"pycrucible.toml\"."
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
        echo "ERROR: OS unknown."
        exit 1
        ;;
esac

echo -e "${BLUE}Building with pycrucible for platform \"${OS}\"...${NC}"
rm -rf ./pycrucible_payload

if [[ "${OS}" == "windows" ]]; then
    cp -p pycrucible.toml pycrucible.toml.orig
    sed -i '/^PYTHONPATH/s/:/;/g' pycrucible.toml
fi

uv run pycrucible --embed . -o "${EXE}"

if [[ "${OS}" == "windows" ]]; then
    mv pycrucible.toml.orig pycrucible.toml
fi

echo -e "${GREEN}=================================================="
echo -e "Build complete!"
echo -e "==================================================${NC}"
