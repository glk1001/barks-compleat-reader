#!/bin/bash
# Generate the plain-Python panel-key module from the encrypted template.
#
# The generated module embeds an XOR-masked copy of BARKS_ZIPS_KEY. In a standalone
# build, Nuitka compiles this .py to native machine code (so the key/logic is not
# shipped as readable source); in development it runs as ordinary Python.
#
# Run once initially, when the panel key changes, or on every CI build.
#
# Locally: reads BARKS_ZIPS_KEY from .env.runtime.
# In GitHub Actions: BARKS_ZIPS_KEY must be set in the environment from the repo secret.

set -eo pipefail

PACKAGE_DIR="src/comic-utils/src/comic_utils"
MODULE_BASENAME="get_panel_bytes"
TEMPLATE_IN="${PACKAGE_DIR}/${MODULE_BASENAME}.pyx.template.in"
TEMPLATE_PLAINTEXT="${PACKAGE_DIR}/${MODULE_BASENAME}.pyx.template"
PY_FILE="${PACKAGE_DIR}/${MODULE_BASENAME}.py"

cleanup() {
    rm -f "$TEMPLATE_PLAINTEXT"
}
trap cleanup EXIT

# Clean prior artifacts: any previously generated module and stale Cython leftovers.
# The .pyx/.c matter for security: a stale Cython-generated .c holds the masked key as
# readable byte literals, and Nuitka's --include-package-data would bundle a .c file.
rm -f "$PY_FILE"
rm -f "${PACKAGE_DIR}/${MODULE_BASENAME}.pyx"
rm -f "${PACKAGE_DIR}/${MODULE_BASENAME}.c"
rm -f "${PACKAGE_DIR}/${MODULE_BASENAME}".*.so
rm -f "${PACKAGE_DIR}/${MODULE_BASENAME}".*.pyd
rm -f "${PACKAGE_DIR}/${MODULE_BASENAME}.pyd"
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

echo "Generating XOR-masked key and writing plain-Python module..."
uv run python - "$TEMPLATE_PLAINTEXT" "$PY_FILE" <<'PYEOF'
import os
import re
import secrets
import sys

template_path, py_path = sys.argv[1], sys.argv[2]
key = os.environ["BARKS_ZIPS_KEY"].encode("ascii")
mask = secrets.token_bytes(len(key))
masked = bytes(k ^ m for k, m in zip(key, mask))

with open(template_path, encoding="utf-8") as f:
    template = f.read()

template = template.replace("{{PANEL_KEY_XOR_BYTES}}", repr(list(masked)))
template = template.replace("{{PANEL_KEY_XOR_MASK}}", repr(list(mask)))

# The template is written in Cython (.pyx). Strip the Cython-only syntax so the result
# is valid Python (Nuitka compiles it to native code; dev imports it directly). The only
# Cython-specific constructs here are the module-level ``cdef <type> name = ...`` typed
# declarations and the ``# cython:`` directive line.
lines = []
for line in template.splitlines():
    if line.startswith("# cython:"):
        continue
    line = re.sub(r"^cdef (list|tuple|dict|set|str|bytes|int|float|bool|object) ", "", line)
    lines.append(line)

with open(py_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
PYEOF

# Sanity check: the generated module must import and expose get_decrypted_bytes.
echo "Verifying generated module imports..."
uv run python -c \
    "from comic_utils.get_panel_bytes import get_decrypted_bytes; assert callable(get_decrypted_bytes)"

echo ""
echo "Done! Plain-Python panel module written to \"${PY_FILE}\"."
echo "In a standalone build Nuitka compiles this to native code."
