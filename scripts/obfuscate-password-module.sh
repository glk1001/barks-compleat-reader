#!/bin/bash
# Run once initially, or when panel key changes.

set -e

BUILD_ENV_FILE=".env.runtime"
TARGET_DIR="src/barks-reader/src/barks_reader"
TARGET="${TARGET_DIR}/get_panel_bytes.py"
TEMPLATE="${TARGET}.template"
TEMPLATE_IN="${TARGET}.template.in"
PLAINTEXT="${TARGET}.plaintext"
OBFUSCATED_DIR="dist_obfuscated"
RUNTIME_DIR="pyarmor_runtime_000000"
rm -rf "${TARGET_DIR}/${RUNTIME_DIR}"

if [ ! -f "$TEMPLATE_IN" ]; then
    echo "Error: TEMPLATE \"$TEMPLATE_IN\" not found!"
    exit 1
fi

echo "Obfuscating panel key module..."

# Clean
rm -rf "$OBFUSCATED_DIR"
rm -rf "${TARGET_DIR}/${RUNTIME_DIR}"
rm -f "$TEMPLATE"
rm -f "$PLAINTEXT"

set -a && source ${BUILD_ENV_FILE} && set +a
if [[ "$BARKS_ZIPS_KEY" == "" ]]; then
    echo "Error: Could not find BARKS_ZIPS_KEY env var!"
    exit 1
fi

uv run scripts/fernet-crypt.py --srce "$TEMPLATE_IN" --dest "$TEMPLATE" decrypt

sed "s/{{PANEL_KEY}}/$BARKS_ZIPS_KEY/g" <$TEMPLATE >$PLAINTEXT
if [ ! -f "$PLAINTEXT" ]; then
    echo "Error: Plaintext \"$PLAINTEXT\" not found!"
    exit 1
fi

# Obfuscate with --prefix option to use relative import.
# The --prefix tells PyArmor what package path to use for the runtime.
uv run pyarmor gen --prefix barks_reader -O "$OBFUSCATED_DIR" "$PLAINTEXT"

# Copy the obfuscated module.
cp -p "${OBFUSCATED_DIR}/get_panel_bytes.py.plaintext" "${TARGET}"

# Copy the PyArmor runtime to the src directory.
if [ -d "$OBFUSCATED_DIR/barks_reader/$RUNTIME_DIR" ]; then
    echo "Copying PyArmor runtime..."
    cp -pr "$OBFUSCATED_DIR/barks_reader/$RUNTIME_DIR" "${TARGET_DIR}/"
fi

# Cleanup
rm -rf "${OBFUSCATED_DIR}"
rm -f "$TEMPLATE"
rm -f "$PLAINTEXT"

echo "Done! Obfuscated version saved to \"$TARGET\"."
echo "PyArmor runtime copied to \"${TARGET_DIR}/${RUNTIME_DIR}\"."
echo ""
echo "Next steps:"
echo "  1. Test it works: uv run --env-file .env python -c 'from barks_reader.get_panel_bytes import get_decrypted_bytes; z = b\"hello\"; get_decrypted_bytes(z); print(\"OK\")'"
echo "  2. Commit: git add \"$TARGET\" && git commit -m 'Added obfuscated panel key module'"
echo "  3. Push: git push"
