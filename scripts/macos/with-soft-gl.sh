#!/bin/bash
# cspell:ignore softgl libsoftgl dylib dylibs dynamiclib otool codesign dyld clang Xcode
# Run a command with Kivy drawing on Apple's software OpenGL renderer, for a macOS
# machine with no GPU driver (a VirtualBox guest): see softgl.c.
#
#   bash scripts/macos/with-soft-gl.sh uv run pytest -n auto
#
# Builds build/macos/libsoftgl.dylib against the workspace's Kivy SDL2 when it is
# missing or older than either, so a Kivy upgrade rebuilds it. The command must start a
# program of the repo's (uv, .venv/bin/python), not /bin/bash or /usr/bin/env: macOS
# drops DYLD_INSERT_LIBRARIES when it starts one of its own protected programs.

set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "with-soft-gl.sh: macOS only" >&2
    exit 1
fi
if [[ $# -eq 0 ]]; then
    echo "usage: bash scripts/macos/with-soft-gl.sh COMMAND [ARGS...]" >&2
    exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE="${REPO_ROOT}/scripts/macos/softgl.c"
LIB="${REPO_ROOT}/build/macos/libsoftgl.dylib"

SDL="$(cd "$REPO_ROOT" && uv run --quiet python -c \
    'import kivy, pathlib; print(pathlib.Path(kivy.__file__).parent / ".dylibs" / "SDL2")')"
if [[ ! -f "$SDL" ]]; then
    echo "with-soft-gl.sh: no SDL2 in the workspace's Kivy at ${SDL}" >&2
    exit 1
fi

if [[ ! -f "$LIB" || "$SOURCE" -nt "$LIB" || "$SDL" -nt "$LIB" ]]; then
    mkdir -p "$(dirname "$LIB")"
    clang -dynamiclib -O2 -o "$LIB" "$SOURCE" "$SDL"
    # The wheel's SDL2 names itself by its build path; point the library at the real file,
    # so dyld loads the same image Kivy does.
    install_name="$(otool -D "$SDL" | tail -1)"
    install_name_tool -change "$install_name" "$SDL" "$LIB"
    codesign --force --sign - "$LIB"
fi

export DYLD_INSERT_LIBRARIES="$LIB${DYLD_INSERT_LIBRARIES:+:$DYLD_INSERT_LIBRARIES}"
exec "$@"
