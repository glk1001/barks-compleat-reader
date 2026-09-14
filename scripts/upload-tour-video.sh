#!/bin/bash
# upload-tour-video.sh - Publish website/walkthrough.mp4 to its GitHub release.
#
# The tour video is deliberately not in the repository. It is ~12MB and is
# re-recorded whenever the app changes, so committing it would leave a permanent
# copy in history every time - and none of that history is ever wanted back.
#
# It lives instead on a release under a FIXED tag, re-uploaded in place with
# --clobber. That is the whole point of this script rather than a data-v* style
# versioned release: the URL in website/app.html never changes, so re-recording
# the tour needs no commit at all. Compare scripts/upload-data-zips.sh, which mints
# a new data-vN release each time because those ~2GB packs almost never change and
# a stale copy would be a real problem.
#
# The video plays from a release asset even though GitHub serves it as
# application/octet-stream with Content-Disposition: attachment. That header
# governs navigations and downloads, not media subresources - a <video> sniffs the
# container - and Range requests are honoured (206), so chapter seeking works.
#
# Only the video goes here. walkthrough-chapters.json and walkthrough-poster.jpg
# stay in git: they are a few KB, the page needs the poster immediately for layout,
# and the manifest has to match the code that reads it.
#
# Usage: bash scripts/upload-tour-video.sh [--video <file>] [--yes] [--dry-run]

set -eo pipefail

REPO="glk1001/barks-compleat-reader"
TAG="website-assets"
VIDEO="website/walkthrough.mp4"
WEBSITE_FILE="website/app.html"

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

ASSUME_YES=0
DRY_RUN=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --video) VIDEO="$2"; shift 2 ;;
        --yes) ASSUME_YES=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        *) echo -e "${RED}Unknown argument: $1${NC}" >&2; exit 1 ;;
    esac
done

cd "$(dirname "$0")/.."

if [[ ! -f "$VIDEO" ]]; then
    echo -e "${RED}Missing \"$VIDEO\" - record it first with scripts/record_demo.py.${NC}" >&2
    exit 1
fi

file_size() {
    # stat's size flag differs between GNU (-c%s) and BSD/macOS (-f%z).
    stat -c%s "$1" 2>/dev/null || stat -f%z "$1"
}

SIZE=$(file_size "$VIDEO")
NAME=$(basename "$VIDEO")

# The page builds its URL from TOUR_TAG, so a tag that has drifted from this script
# would upload to one place and play from another.
PAGE_TAG=$(grep -oE "const TOUR_TAG = '[^']+'" "$WEBSITE_FILE" | cut -d"'" -f2)
if [[ "$PAGE_TAG" != "$TAG" ]]; then
    echo -e "${RED}${WEBSITE_FILE} plays the tour from tag \"${PAGE_TAG}\"," \
        "but this script uploads to \"${TAG}\".${NC}" >&2
    exit 1
fi

# The manifest is what the chapter buttons seek by, so a video whose length has
# moved without it being regenerated would put every chapter out of step.
MANIFEST="website/${NAME%.mp4}-chapters.json"
if [[ -f "$MANIFEST" ]]; then
    LAST_END=$(grep -oE '"end": [0-9.]+' "$MANIFEST" | tail -1 | grep -oE '[0-9.]+')
    DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VIDEO")
    DRIFT=$(awk -v a="$LAST_END" -v b="$DURATION" 'BEGIN { d = a - b; print (d < 0 ? -d : d) }')
    if awk -v d="$DRIFT" 'BEGIN { exit !(d > 1.0) }'; then
        echo -e "${RED}${MANIFEST} ends at ${LAST_END}s but ${NAME} runs ${DURATION}s." \
            "Re-stitch before uploading, or the chapter buttons will be wrong.${NC}" >&2
        exit 1
    fi
fi

echo -e "${YELLOW}Uploading:${NC}  ${VIDEO} ($((SIZE / 1024 / 1024)) MB)"
echo -e "${YELLOW}To:${NC}         ${REPO} release ${TAG} (in place)"

if [[ $DRY_RUN == 1 ]]; then
    echo -e "${GREEN}Dry run - stopping before touching the release.${NC}"
    exit 0
fi

if [[ $ASSUME_YES != 1 ]]; then
    read -r -p "Upload ${NAME} to ${TAG}? [y/N] " answer
    [[ "$answer" == "y" || "$answer" == "Y" ]] || { echo "Aborted."; exit 1; }
fi

# Create the release once, on first use. It is a pre-release so it can never become
# GitHub's "Latest" - the website's version resolver depends on that.
if ! gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
    echo -e "${YELLOW}Creating the ${TAG} release...${NC}"
    gh release create "$TAG" --repo "$REPO" --target main --prerelease \
        --title "Website assets" \
        --notes "Large files the website serves but the repository does not carry.

These are re-uploaded in place, so the URLs on the site never change and
re-recording needs no commit. Nothing here is part of a Barks Reader release -
see the app releases for that."
fi

echo -e "${YELLOW}Uploading ${NAME}...${NC}"
gh release upload "$TAG" --repo "$REPO" --clobber "$VIDEO"

echo -e "${YELLOW}Verifying the uploaded size...${NC}"
UPLOADED=$(gh release view "$TAG" --repo "$REPO" --json assets \
    -q ".assets[] | select(.name == \"${NAME}\") | .size")
if [[ "$UPLOADED" != "$SIZE" ]]; then
    echo -e "${RED}Uploaded ${UPLOADED} bytes, expected ${SIZE}. Re-run before the site" \
        "is left serving a truncated video.${NC}" >&2
    exit 1
fi

echo
echo -e "${GREEN}=================================================="
echo -e "Done: https://github.com/${REPO}/releases/download/${TAG}/${NAME}"
echo -e "==================================================${NC}"
echo -e "The site picks this up with no commit - the URL did not change."
echo -e "${YELLOW}A browser that already watched the tour may hold the old copy in cache.${NC}"
