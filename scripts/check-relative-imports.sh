#!/bin/bash
# Enforce relative imports for intra-package references.
# Same-subpackage imports should use "from .module" not "from package.module".

set -euo pipefail

errors=0

check_dir() {
    local dir="$1"
    local pattern="$2"
    shift 2
    # Remaining args are passed directly to grep (e.g. --exclude-dir, --exclude).
    local extra_args=("$@")

    local grep_args=(-rn "$pattern" "$dir" --include='*.py' "${extra_args[@]}")

    local matches
    matches=$(grep "${grep_args[@]}" 2>/dev/null || true)
    if [[ -n "$matches" ]]; then
        echo "$matches"
        errors=1
    fi
}

echo "Checking for absolute intra-package imports that should be relative..."
echo

check_dir \
    "src/barks-reader/src/barks_reader/core" \
    "from barks_reader\.core\."

check_dir \
    "src/barks-reader/src/barks_reader/ui" \
    "from barks_reader\.ui\."

check_dir \
    "src/barks-build-comic-images/src/barks_build_comic_images" \
    "from barks_build_comic_images\."

check_dir \
    "src/barks-fantagraphics/src/barks_fantagraphics" \
    "from barks_fantagraphics\." \
    --exclude-dir="testing"

check_dir \
    "src/comic-utils/src/comic_utils" \
    "from comic_utils\." \
    --exclude="get_panel_bytes.py"

if [[ "$errors" -eq 1 ]]; then
    echo
    echo "FAILED: Use relative imports (from .module) for intra-package references."
    exit 1
else
    echo "All intra-package imports use relative style."
fi
