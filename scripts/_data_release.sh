#!/usr/bin/env bash
# Sourced by build-data-zips.sh and upload-data-zips.sh: what the two share about
# the data packs and their data-vN GitHub releases.
REPO="glk1001/barks-compleat-reader"
DATA1_ZIP="barks-reader-data-1.barkspack"
DATA2_ZIP="barks-reader-data-2.barkspack"
# The version file inside each pack (core/data_pack.py reads it).
PACK_MEMBER="Reader Files/data-pack.json"

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
