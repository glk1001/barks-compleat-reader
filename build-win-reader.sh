rm -rf pycrucible_payload
git checkout pycrucible.toml
git pull
cp pycrucible.toml.win pycrucible.toml


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
COPYRIGHT_YEARS="2026"


# --- Write version file ---
echo -e "${YELLOW}Writing version: $VERSION ...${NC}"

echo "COPYRIGHT_YEARS = \"${COPYRIGHT_YEARS}\"" > "$VERSION_FILE"
echo "" >> "$VERSION_FILE"
echo "VERSION = \"${VERSION}\"" >> "$VERSION_FILE"
echo "" >> "$VERSION_FILE"

echo -e "Successfully wrote version to \"${VERSION_FILE}\"."
echo

bash scripts/obfuscate-password-module.sh

uv run pycrucible --embed . -o barks-reader-win.exe
