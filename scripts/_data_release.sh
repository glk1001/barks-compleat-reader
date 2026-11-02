#!/usr/bin/env bash
# Sourced by build-data-zips.sh and upload-data-zips.sh: what the two share about
# the data packs and their data-vN GitHub releases.
REPO="glk1001/barks-compleat-reader"
DATA1_ZIP="barks-reader-data-1.barkspack"
DATA2_ZIP="barks-reader-data-2.barkspack"
# The version file inside each pack (core/data_pack.py reads it).
PACK_MEMBER="Reader Files/data-pack.json"
# GitHub refuses a release asset of 2 GiB or more; a pack past 90% of that warns, so
# a split into a third pack is planned before a build fails. Pack 2 is Barks Panels.zip
# alone, so it grows with the panels.
ASSET_LIMIT_BYTES=2147483648
ASSET_WARN_BYTES=$((ASSET_LIMIT_BYTES / 10 * 9))

# Print the N of the newest data-vN release (0 when there is none). Fails, printing
# nothing, when gh cannot list the releases (offline, not logged in).
latest_data_version() {
    local tags n
    tags=$(gh release list --repo "$REPO" --limit 200 --json tagName -q '.[].tagName') || return 1
    n=$(grep -E '^data-v[0-9]+$' <<<"$tags" | sed 's/^data-v//' | sort -n | tail -1)
    echo "${n:-0}"
}

# Print the version a pack's version file names; fails when the pack has none.
pack_version() {
    unzip -p "$1" "$PACK_MEMBER" 2>/dev/null \
        | python3 -I -c 'import json, sys; print(json.load(sys.stdin)["version"])' 2>/dev/null
}

file_size() {
    # stat's size flag differs between GNU (-c%s) and BSD/macOS (-f%z).
    stat -c%s "$1" 2>/dev/null || stat -f%z "$1"
}

# Fail, saying so on stderr, when a pack is too big to be a release asset; warn on
# stderr (and succeed) when it is close to that.
check_pack_size() {
    local size
    size=$(file_size "$1") || return 1
    if ((size >= ASSET_LIMIT_BYTES)); then
        echo "\"$1\" is ${size} bytes: GitHub refuses a release asset of" \
            "${ASSET_LIMIT_BYTES} (2 GiB) or more. Split the pack." >&2
        return 1
    fi
    if ((size >= ASSET_WARN_BYTES)); then
        echo "WARNING: \"$1\" is ${size} bytes, $((size * 100 / ASSET_LIMIT_BYTES))% of" \
            "GitHub's 2 GiB limit on a release asset: plan a split into a third pack." >&2
    fi
}
