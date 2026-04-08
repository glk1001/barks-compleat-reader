#!/bin/bash
# Compile the panel-key module to a native Cython extension.
# Run once initially, when the panel key changes, or on every CI build.
#
# Locally: reads BARKS_ZIPS_KEY from .env.runtime.
# In GitHub Actions: BARKS_ZIPS_KEY must be set in the environment from the repo secret.

set -eo pipefail

PACKAGE_DIR="src/comic-utils/src/comic_utils"
MODULE_BASENAME="get_panel_bytes"
TEMPLATE_IN="${PACKAGE_DIR}/${MODULE_BASENAME}.pyx.template.in"
TEMPLATE_PLAINTEXT="${PACKAGE_DIR}/${MODULE_BASENAME}.pyx.template"
PYX_FILE="${PACKAGE_DIR}/${MODULE_BASENAME}.pyx"
C_FILE="${PACKAGE_DIR}/${MODULE_BASENAME}.c"
PY_FILE="${PACKAGE_DIR}/${MODULE_BASENAME}.py"

cleanup() {
    rm -f "$TEMPLATE_PLAINTEXT" "$PYX_FILE" "$C_FILE"
    # cythonize -i leaves a build/ tree with a duplicate of the compiled extension.
    rm -rf src/comic-utils/src/build
}
trap cleanup EXIT

# Clean prior build artifacts (including any PyArmor leftovers).
rm -f "$PY_FILE"
rm -f "${PACKAGE_DIR}/${MODULE_BASENAME}".*.so
rm -f "${PACKAGE_DIR}/${MODULE_BASENAME}".*.pyd
rm -f "${PACKAGE_DIR}/${MODULE_BASENAME}.pyd"
rm -rf "${PACKAGE_DIR}/pyarmor_runtime_000000"
rm -rf "${PACKAGE_DIR}/__pycache__"

if [ ! -f "$TEMPLATE_IN" ]; then
    echo "Error: encrypted template \"$TEMPLATE_IN\" not found!" >&2
    exit 1
fi

# Source .env.runtime if present (local dev); CI sets BARKS_ZIPS_KEY directly from a secret.
if [ -f .env.runtime ]; then
    set -a && source .env.runtime && set +a
fi

if [ -z "${BARKS_ZIPS_KEY:-}" ]; then
    echo "Error: BARKS_ZIPS_KEY env var is not set." >&2
    exit 1
fi

echo "Decrypting panel module template..."
uv run scripts/fernet-crypt.py decrypt "$TEMPLATE_IN" "$TEMPLATE_PLAINTEXT"

echo "Generating XOR-masked key and writing .pyx..."
uv run python - "$TEMPLATE_PLAINTEXT" "$PYX_FILE" <<'PYEOF'
import os
import secrets
import sys

template_path, pyx_path = sys.argv[1], sys.argv[2]
key = os.environ["BARKS_ZIPS_KEY"].encode("ascii")
mask = secrets.token_bytes(len(key))
masked = bytes(k ^ m for k, m in zip(key, mask))

with open(template_path, encoding="utf-8") as f:
    template = f.read()

template = template.replace("{{PANEL_KEY_XOR_BYTES}}", repr(list(masked)))
template = template.replace("{{PANEL_KEY_XOR_MASK}}", repr(list(mask)))

with open(pyx_path, "w", encoding="utf-8") as f:
    f.write(template)
PYEOF

echo "Compiling with Cython..."
uv run cythonize -i -3 "$PYX_FILE"

# Sanity check: verify at least one compiled artifact exists.
if ! ls "${PACKAGE_DIR}/${MODULE_BASENAME}".*.so >/dev/null 2>&1 \
    && ! ls "${PACKAGE_DIR}/${MODULE_BASENAME}".*.pyd >/dev/null 2>&1 \
    && [ ! -f "${PACKAGE_DIR}/${MODULE_BASENAME}.pyd" ]; then
    echo "Error: Cython build produced no extension module." >&2
    exit 1
fi

echo ""
echo "Done! Cython extension built in \"${PACKAGE_DIR}/\"."
echo ""
echo "Verify with:"
echo "  uv run python -c 'from comic_utils.get_panel_bytes import get_decrypted_bytes; print(get_decrypted_bytes)'"
