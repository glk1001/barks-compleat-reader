#!/bin/bash
# Run once initially, or when password changes.

set -e

TARGET_DIR="src/barks-reader/src/barks_reader"
TARGET="${TARGET_DIR}/open_zip_archive.py"
PLAINTEXT="${TARGET}.plaintext"
OBFUSCATED_DIR="dist_obfuscated"
RUNTIME_DIR="pyarmor_runtime_000000"
rm -rf "${TARGET_DIR}/${RUNTIME_DIR}"

if [ ! -f "$PLAINTEXT" ]; then
    echo "Error: $PLAINTEXT not found!"
    echo "Create this file with your password logic first."
    exit 1
fi

echo "Obfuscating password module..."

# Clean
rm -rf "$OBFUSCATED_DIR"
rm -rf "${TARGET_DIR}/${RUNTIME_DIR}"

# Obfuscate with --prefix option to use relative import.
# The --prefix tells PyArmor what package path to use for the runtime.
uv run pyarmor gen --prefix barks_reader -O "$OBFUSCATED_DIR" "$PLAINTEXT"

# Copy obfuscated module
cp -p "${OBFUSCATED_DIR}/open_zip_archive.py.plaintext" "${TARGET}"

# Copy PyArmor runtime to src directory
if [ -d "$OBFUSCATED_DIR/barks_reader/$RUNTIME_DIR" ]; then
    echo "Copying PyArmor runtime..."
    cp -pr "$OBFUSCATED_DIR/barks_reader/$RUNTIME_DIR" "${TARGET_DIR}/"
fi

# Cleanup
rm -rf "${OBFUSCATED_DIR}"

echo "Done! Obfuscated version saved to \"$TARGET\"."
echo "PyArmor runtime copied to \"${TARGET_DIR}/${RUNTIME_DIR}\"."
echo ""
echo "Next steps:"
echo "  1. Test it works: uv run python -c 'from barks_reader.open_zip_archive import get_opened_zip_file; print(\"OK\")'"
echo "  2. Commit: git add \"$TARGET\" \"${TARGET_DIR}/${RUNTIME_DIR}\" && git commit -m 'Added obfuscated password module'"
echo "  3. Push: git push"
