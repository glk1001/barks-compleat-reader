#!/bin/bash
# build.sh - Regular build (uses already-obfuscated module)

set -e

echo "=================================================="
echo "Building Barks Compleat Reader"
echo "=================================================="

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Building with pycrucible...${NC}"
rm -rf ./pycrucible_payload
uv run pycrucible --embed . -o barks-reader-linux

echo -e "${GREEN}=================================================="
echo -e "Build complete!"
echo -e "==================================================${NC}"
