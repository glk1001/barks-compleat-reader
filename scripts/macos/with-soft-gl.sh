#!/bin/bash
# cspell:ignore softgl libsoftgl dylib dylibs dynamiclib otool codesign dyld clang Xcode headerpad
# Run a command in the workspace's venv with Kivy free to draw on Apple's software OpenGL
# renderer, for a macOS machine with no GPU driver (a VirtualBox guest): see softgl.c.
#
#   bash scripts/macos/with-soft-gl.sh pytest -n auto
#   bash scripts/macos/with-soft-gl.sh python main.py
#
# A leading "uv run" is accepted and dropped (`with-soft-gl.sh uv run main.py`), as
# long as no uv option follows it.
#
# Builds build/macos/libsoftgl.dylib against the workspace's Kivy SDL2 when it is
# missing or older than either, so a Kivy upgrade rebuilds it.
#
# The library goes in DYLD_INSERT_LIBRARIES, which macOS strips from the environment of
# any program signed with the hardened runtime as it starts - uv since 0.12 among them -
# and of its own protected ones (/bin/bash, /usr/bin/env). So it is not exported to uv:
# `uv run env VAR=... COMMAND` has env set it after both have started, for the command
# alone. Loaded, the library takes itself out of it again (see softgl.c), so the
# command's own children never inherit it.

set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "with-soft-gl.sh: macOS only" >&2
    exit 1
fi
if [[ $# -ge 2 && "$1" == "uv" && "$2" == "run" ]]; then
    shift 2
    if [[ $# -gt 0 && "$1" == -* ]]; then
        echo "with-soft-gl.sh: give the command without uv's options (it runs uv run itself)" >&2
        exit 2
    fi
    # `uv run main.py` runs a script; through env it needs its interpreter named.
    if [[ $# -gt 0 && "$1" == *.py ]]; then
        set -- python "$@"
    fi
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
    # Room for the longer SDL2 path written in below: on arm64 the linker leaves
    # none, and a CI runner's venv path did not fit ("larger updated load commands
    # do not fit").
    clang -dynamiclib -O2 -Wl,-headerpad_max_install_names -o "$LIB" "$SOURCE" "$SDL"
    # The wheel's SDL2 names itself by its build path; point the library at the real file,
    # so dyld loads the same image Kivy does.
    install_name="$(otool -D "$SDL" | tail -1)"
    install_name_tool -change "$install_name" "$SDL" "$LIB"
    codesign --force --sign - "$LIB"
fi

# No multisampling (Kivy's graphics.multisamples, 2 by default): Apple's software
# renderer does it by supersampling, and crashed in glsDownsample2x2_BGRA8888 as it
# presented the first frame after a fullscreen window went back to its size (a soak
# walk, 2026-10-02). Already set in the environment, the setting is left as it is.
exec uv run env "DYLD_INSERT_LIBRARIES=${LIB}${DYLD_INSERT_LIBRARIES:+:$DYLD_INSERT_LIBRARIES}" \
    "KCFG_GRAPHICS_MULTISAMPLES=${KCFG_GRAPHICS_MULTISAMPLES:-0}" "$@"
