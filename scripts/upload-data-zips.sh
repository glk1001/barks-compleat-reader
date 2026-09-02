#!/bin/bash
# upload-data-zips.sh - Publish the two data packs as a new dedicated data-vN
# GitHub release.
#
# The ~2GB of data packs rarely change, so they live on their own data-v*
# release instead of being duplicated onto every app release (see "Deployment"
# in README.md). Run this only when the data packs have actually changed.
#
# Expects barks-reader-data-1.zip and barks-reader-data-2.zip to already exist
# (produced by `bash scripts/build-data-zips.sh`). Then:
#   1. Works out the next tag (highest existing data-vN, plus one).
#   2. Hashes both zips into SHA256SUMS.txt.
#   3. Creates a DRAFT release and uploads both zips plus the checksums to it,
#      so a failed or partial upload is never publicly visible.
#   4. Verifies the uploaded byte sizes match the local files.
#   5. Publishes the release, marked pre-release so it can never become
#      GitHub's "Latest" (the website's version resolver depends on that).
#   6. Points DATA_TAG in website/app.html and the data-pack links in
#      .github/workflows/build.yml at the new tag - review and commit those.
#
# Usage: bash scripts/upload-data-zips.sh [--zips-dir <dir>] [--yes] [--dry-run]

set -eo pipefail

REPO="glk1001/barks-compleat-reader"
DATA1_ZIP="barks-reader-data-1.zip"
DATA2_ZIP="barks-reader-data-2.zip"
# These packs are ~1.2GB each, and a size check cannot see a flipped byte - only a
# truncation. Publish real hashes so a bad copy is identifiable as a bad copy.
CHECKSUMS_FILE="SHA256SUMS.txt"
WEBSITE_FILE="website/app.html"
WORKFLOW_FILE=".github/workflows/build.yml"

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

ZIPS_DIR="."
ASSUME_YES=0
DRY_RUN=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --zips-dir) ZIPS_DIR="$2"; shift 2 ;;
        --yes) ASSUME_YES=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        *) echo -e "${RED}Unknown argument: $1${NC}" >&2; exit 1 ;;
    esac
done

cd "$(dirname "$0")/.."

for zip in "${ZIPS_DIR}/${DATA1_ZIP}" "${ZIPS_DIR}/${DATA2_ZIP}"; do
    if [[ ! -f "$zip" ]]; then
        echo -e "${RED}Missing \"$zip\" - run 'bash scripts/build-data-zips.sh' first," \
            "or point --zips-dir at the directory holding the zips.${NC}" >&2
        exit 1
    fi
done

file_size() {
    # stat's size flag differs between GNU (-c%s) and BSD/macOS (-f%z).
    stat -c%s "$1" 2>/dev/null || stat -f%z "$1"
}
sha256_of() {
    # sha256sum is GNU; macOS ships shasum instead.
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d" " -f1
    else
        shasum -a 256 "$1" | cut -d" " -f1
    fi
}

SIZE1=$(file_size "${ZIPS_DIR}/${DATA1_ZIP}")
SIZE2=$(file_size "${ZIPS_DIR}/${DATA2_ZIP}")

# --- Work out the previous and next data tags ---
LAST_N=$(gh release list --repo "$REPO" --json tagName -q '.[].tagName' \
    | grep -E '^data-v[0-9]+$' | sed 's/^data-v//' | sort -n | tail -1 || true)
if [[ -z "$LAST_N" ]]; then
    OLD_TAG=""
    NEW_TAG="data-v1"
else
    OLD_TAG="data-v${LAST_N}"
    NEW_TAG="data-v$((LAST_N + 1))"
fi

echo -e "${YELLOW}New release:${NC}  ${NEW_TAG} on ${REPO}"
echo -e "${YELLOW}Uploading:${NC}"
echo "  ${ZIPS_DIR}/${DATA1_ZIP} ($((SIZE1 / 1024 / 1024)) MB)"
echo "  ${ZIPS_DIR}/${DATA2_ZIP} ($((SIZE2 / 1024 / 1024)) MB)"

# Uploading unchanged zips is almost always a mistake - the whole point of
# data-v* releases is that a new one means the data actually changed.
if [[ -n "$OLD_TAG" ]]; then
    # Only the zips: the checksums file is expected to differ every release.
    OLD_SIZES=$(gh release view "$OLD_TAG" --repo "$REPO" --json assets \
        -q '.assets[] | select(.name | endswith(".zip")) | "\(.name) \(.size)"' | sort)
    NEW_SIZES=$(printf '%s %s\n%s %s\n' \
        "$DATA1_ZIP" "$SIZE1" "$DATA2_ZIP" "$SIZE2" | sort)
    if [[ "$OLD_SIZES" == "$NEW_SIZES" ]]; then
        echo -e "${YELLOW}WARNING: both zips are byte-for-byte the same SIZE as the ones on" \
            "${OLD_TAG} - are you sure the data packs have changed?${NC}"
    fi
fi

if [[ $DRY_RUN == 1 ]]; then
    echo -e "${GREEN}Dry run - stopping before creating the release.${NC}"
    exit 0
fi

if [[ $ASSUME_YES != 1 ]]; then
    read -r -p "Create and publish ${NEW_TAG}? [y/N] " answer
    [[ "$answer" == "y" || "$answer" == "Y" ]] || { echo "Aborted."; exit 1; }
fi

# --- Checksums ---
# Written with bare filenames, in sha256sum's own format, so a user who downloads
# all three assets into one directory can run "sha256sum -c SHA256SUMS.txt".
echo -e "${YELLOW}Hashing both zips (~2GB, takes a moment)...${NC}"
printf '%s  %s\n%s  %s\n' \
    "$(sha256_of "${ZIPS_DIR}/${DATA1_ZIP}")" "$DATA1_ZIP" \
    "$(sha256_of "${ZIPS_DIR}/${DATA2_ZIP}")" "$DATA2_ZIP" \
    > "${ZIPS_DIR}/${CHECKSUMS_FILE}"
cat "${ZIPS_DIR}/${CHECKSUMS_FILE}"
SIZE_SUMS=$(file_size "${ZIPS_DIR}/${CHECKSUMS_FILE}")

# --- Create draft, upload, verify, publish ---
echo -e "${YELLOW}Creating draft release ${NEW_TAG}...${NC}"
gh release create "$NEW_TAG" --repo "$REPO" --target main --draft --prerelease \
    --title "Barks Reader Data Packs (v$((LAST_N + 1)))" \
    --notes "The two data packs required by every Barks Reader release. They rarely change, so they live on this dedicated release instead of being duplicated onto each app release.

Download **both** zips and place them beside the app executable before first launch (see the [installation guide](https://glk1001.github.io/barks-compleat-reader/website/app.html#installation)).

- ${DATA1_ZIP}
- ${DATA2_ZIP}

\`${CHECKSUMS_FILE}\` lists the SHA-256 of both zips. A download of this size can truncate silently, so if the reader reports a bad or empty archive, check the zips against it first (`sha256sum -c ${CHECKSUMS_FILE}`)."

echo -e "${YELLOW}Uploading both zips (this is ~2GB - be patient)...${NC}"
gh release upload "$NEW_TAG" --repo "$REPO" \
    "${ZIPS_DIR}/${DATA1_ZIP}" "${ZIPS_DIR}/${DATA2_ZIP}" "${ZIPS_DIR}/${CHECKSUMS_FILE}"

echo -e "${YELLOW}Verifying uploaded sizes...${NC}"
UPLOADED=$(gh release view "$NEW_TAG" --repo "$REPO" --json assets \
    -q '.assets[] | "\(.name) \(.size)"' | sort)
EXPECTED=$(printf '%s %s\n%s %s\n%s %s\n' \
    "$DATA1_ZIP" "$SIZE1" "$DATA2_ZIP" "$SIZE2" "$CHECKSUMS_FILE" "$SIZE_SUMS" | sort)
if [[ "$UPLOADED" != "$EXPECTED" ]]; then
    echo -e "${RED}Uploaded assets don't match the local files:${NC}" >&2
    diff <(echo "$EXPECTED") <(echo "$UPLOADED") >&2 || true
    echo -e "${RED}Draft ${NEW_TAG} left unpublished - fix and re-upload, or delete it with:" \
        "gh release delete ${NEW_TAG} --repo ${REPO} --cleanup-tag${NC}" >&2
    exit 1
fi

echo -e "${YELLOW}Publishing ${NEW_TAG} (as pre-release)...${NC}"
gh release edit "$NEW_TAG" --repo "$REPO" --draft=false --prerelease

# --- Point the website and CI workflow at the new tag ---
perl -pi -e "s/const DATA_TAG = 'data-v[0-9]+'/const DATA_TAG = '${NEW_TAG}'/" "$WEBSITE_FILE"
perl -pi -e "s|releases/download/data-v[0-9]+/|releases/download/${NEW_TAG}/|g" "$WORKFLOW_FILE"

echo
echo -e "${GREEN}=================================================="
echo -e "Done: https://github.com/${REPO}/releases/tag/${NEW_TAG}"
echo -e "==================================================${NC}"
echo -e "Updated DATA_TAG in ${WEBSITE_FILE} and the data-pack links in ${WORKFLOW_FILE}."
echo -e "Review and commit those changes (git diff), then consider deleting the"
echo -e "old ${OLD_TAG:-data-v?} release once nothing links to it."
