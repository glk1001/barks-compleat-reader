#!/bin/bash
# upload-website-videos.sh - Publish the website's videos to their GitHub release.
#
# Neither video is in the repository. Both are re-recorded whenever the app
# changes, so committing them would leave a permanent copy in history every time,
# and none of that history is ever wanted back. The hero is the smaller file but
# it autoplays on the landing tab, which makes it the heaviest thing most visitors
# ever fetch - so serving it from the release CDN keeps that off Pages entirely.
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
# Only the videos go here. The posters and walkthrough-chapters.json stay in git:
# they are a few KB, the page needs the posters immediately for layout, and the
# manifest has to match the code that reads it.
#
# Usage: bash scripts/upload-website-videos.sh [--only <file>] [--yes] [--dry-run]

set -eo pipefail

REPO="glk1001/barks-compleat-reader"
TAG="website-assets"
VIDEOS=("website/demo.mp4" "website/walkthrough.mp4")
WEBSITE_FILE="website/app.html"

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

ASSUME_YES=0
DRY_RUN=0
ONLY=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --only) ONLY="$2"; shift 2 ;;
        --yes) ASSUME_YES=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        *) echo -e "${RED}Unknown argument: $1${NC}" >&2; exit 1 ;;
    esac
done

cd "$(dirname "$0")/.."

if [[ -n "$ONLY" ]]; then
    VIDEOS=("$ONLY")
fi

for video in "${VIDEOS[@]}"; do
    if [[ ! -f "$video" ]]; then
        echo -e "${RED}Missing \"$video\" - record it first with scripts/record_demo.py.${NC}" >&2
        exit 1
    fi
done

file_size() {
    # stat's size flag differs between GNU (-c%s) and BSD/macOS (-f%z).
    stat -c%s "$1" 2>/dev/null || stat -f%z "$1"
}

# The page builds both player URLs from VIDEO_TAG, so a tag that has drifted from
# this script would upload to one place and play from another.
PAGE_TAG=$(grep -oE "const VIDEO_TAG = '[^']+'" "$WEBSITE_FILE" | cut -d"'" -f2)
if [[ "$PAGE_TAG" != "$TAG" ]]; then
    echo -e "${RED}${WEBSITE_FILE} plays its videos from tag \"${PAGE_TAG}\"," \
        "but this script uploads to \"${TAG}\".${NC}" >&2
    exit 1
fi

# The noscript fallbacks cannot use that constant - they are markup, not script - so
# they spell the URL out and can drift from it on their own. Anything built from a
# JS variable still reads as "${...}" here and is skipped, so this only sees the
# literal ones.
WRONG_TAG_URLS=$(grep -oE "releases/download/[A-Za-z0-9._-]+/" "$WEBSITE_FILE" \
    | grep -v "^releases/download/${TAG}/$" | sort -u || true)
if [[ -n "$WRONG_TAG_URLS" ]]; then
    echo -e "${RED}${WEBSITE_FILE} spells out release URLs on another tag:${NC}" >&2
    echo "$WRONG_TAG_URLS" >&2
    echo -e "${RED}They would 404 once this uploads to \"${TAG}\".${NC}" >&2
    exit 1
fi

echo -e "${YELLOW}To:${NC}  ${REPO} release ${TAG} (in place)"
for video in "${VIDEOS[@]}"; do
    name=$(basename "$video")
    size=$(file_size "$video")
    echo -e "${YELLOW}Uploading:${NC}  ${video} ($((size / 1024 / 1024)) MB)"

    # A chapter manifest is what the buttons seek by, so a video whose length has
    # moved without the manifest being regenerated puts every chapter out of step.
    manifest="website/${name%.mp4}-chapters.json"
    [[ -f "$manifest" ]] || continue
    last_end=$(grep -oE '"end": [0-9.]+' "$manifest" | tail -1 | grep -oE '[0-9.]+')
    duration=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$video")
    drift=$(awk -v a="$last_end" -v b="$duration" 'BEGIN { d = a - b; print (d < 0 ? -d : d) }')
    if awk -v d="$drift" 'BEGIN { exit !(d > 1.0) }'; then
        echo -e "${RED}${manifest} ends at ${last_end}s but ${name} runs ${duration}s." \
            "Re-stitch before uploading, or the chapter buttons will be wrong.${NC}" >&2
        exit 1
    fi
done

if [[ $DRY_RUN == 1 ]]; then
    echo -e "${GREEN}Dry run - stopping before touching the release.${NC}"
    exit 0
fi

if [[ $ASSUME_YES != 1 ]]; then
    read -r -p "Upload to ${TAG}? [y/N] " answer
    [[ "$answer" == "y" || "$answer" == "Y" ]] || { echo "Aborted."; exit 1; }
fi

# Create the release once, on first use. It is a pre-release so it can never become
# GitHub's "Latest" - the website's version resolver depends on that.
if ! gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
    echo -e "${YELLOW}Creating the ${TAG} release...${NC}"
    gh release create "$TAG" --repo "$REPO" --target main --prerelease \
        --title "Website assets" \
        --notes "Videos the website plays but the repository does not carry.

These are re-uploaded in place, so the URLs on the site never change and
re-recording needs no commit. Nothing here is part of a Barks Reader release -
see the app releases for that."
fi

echo -e "${YELLOW}Uploading...${NC}"
gh release upload "$TAG" --repo "$REPO" --clobber "${VIDEOS[@]}"

echo -e "${YELLOW}Verifying the uploaded sizes...${NC}"
for video in "${VIDEOS[@]}"; do
    name=$(basename "$video")
    expected=$(file_size "$video")
    uploaded=$(gh release view "$TAG" --repo "$REPO" --json assets \
        -q ".assets[] | select(.name == \"${name}\") | .size")
    if [[ "$uploaded" != "$expected" ]]; then
        echo -e "${RED}${name}: uploaded ${uploaded} bytes, expected ${expected}." \
            "Re-run before the site is left serving a truncated video.${NC}" >&2
        exit 1
    fi
done

echo
echo -e "${GREEN}=================================================="
echo -e "Done: https://github.com/${REPO}/releases/tag/${TAG}"
echo -e "==================================================${NC}"
echo -e "The site picks this up with no commit - the URL did not change."
echo -e "${YELLOW}A browser that has already seen them may hold the old copies in cache.${NC}"
