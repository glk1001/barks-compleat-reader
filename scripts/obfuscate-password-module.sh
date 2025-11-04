#!/bin/bash
# Run once initially, or when password changes.

set -e

BUILD_ENV_FILE=".build-env"
TARGET_DIR="src/barks-reader/src/barks_reader"
TARGET="${TARGET_DIR}/open_zip_archive.py"
TEMPLATE="${TARGET}.template"
PLAINTEXT="${TARGET}.plaintext"
OBFUSCATED_DIR="dist_obfuscated"
RUNTIME_DIR="pyarmor_runtime_000000"
rm -rf "${TARGET_DIR}/${RUNTIME_DIR}"

if [ ! -f "$TEMPLATE" ]; then
    echo "Error: TEMPLATE \"$TEMPLATE\" not found!"
    exit 1
fi

echo "Obfuscating password module..."

# Clean
rm -rf "$OBFUSCATED_DIR"
rm -rf "${TARGET_DIR}/${RUNTIME_DIR}"
rm -rf "$PLAINTEXT"

set -a && source ${BUILD_ENV_FILE} && set +a
if [[ "$BARKS_ZIPS_PW" == "" ]]; then
    echo "Error: Could not find BARKS_ZIPS_PW env var!"
    exit 1
fi
sed "s/{{ZIP_PASSWORD}}/$BARKS_ZIPS_PW/g" <$TEMPLATE >$PLAINTEXT
if [ ! -f "$PLAINTEXT" ]; then
    echo "Error: Plaintext \"$PLAINTEXT\" not found!"
    exit 1
fi

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
rm -rf "$PLAINTEXT"

echo "Done! Obfuscated version saved to \"$TARGET\"."
echo "PyArmor runtime copied to \"${TARGET_DIR}/${RUNTIME_DIR}\"."
echo ""
echo "Next steps:"
echo "  1. Test it works: uv run --env-file .env python -c 'from barks_reader.open_zip_archive import get_opened_zip_file; z = \"hello\"; get_opened_zip_file(z); print(\"OK\")'"
echo "  2. Commit: git add \"$TARGET\" && git commit -m 'Added obfuscated password module'"
echo "  3. Push: git push"
