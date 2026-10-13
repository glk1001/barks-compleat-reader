#!/bin/bash
# cspell:ignore softgl libsoftgl dylib dyld clang otool codesign libexec Dconstructor
# cspell:ignore dynamiclib headerpad sectname multisampling KCFG MULTISAMPLES
# Run a built app bundle (CI's macOS zip, unzipped) on Apple's software OpenGL renderer,
# for an Intel Mac with no GPU driver (a VirtualBox guest), as a user would start it after
# installing: a first run goes through the first-run installer and its success window.
#
#   bash scripts/macos/run-app-soft-gl.sh ~/BarksReader/barks-reader-macos-x64.app [ARGS...]
#
# Run it in Terminal on the Mac's own screen. Double-clicking the .app, or `open`, starts
# it without the library (no environment is passed), and its first window fails with
# "Failed creating OpenGL pixel format".
#
# with-soft-gl.sh does this for the workspace app; this builds the same softgl.c, but
# linked against the bundle's OWN SDL2, since it hooks only the SDL2 it was linked to. One
# library per app path, in build/macos, rebuilt when the bundle's SDL2, softgl.c or this
# script is newer, so a freshly unzipped build needs nothing by hand.
#
# Built with softgl.c's constructor switched off: it takes the library out of
# DYLD_INSERT_LIBRARIES once loaded, but a first run re-runs the app as a child process for
# the installer (main.py, --run-first-run-installer), whose success window then had no
# library and failed. So here every child inherits it. Harmless on an Intel Mac; on Apple
# silicon dyld kills Apple's own arm64e programs asked to load it, so this refuses there.
#
# Assumes the bundle is not signed with the hardened runtime, which drops the library
# (CI's builds are ad-hoc signed; this warns), and Xcode's command-line tools (clang).

set -euo pipefail

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "x86_64" ]]; then
    echo "run-app-soft-gl.sh: Intel macOS only (see the header)" >&2
    exit 1
fi
if [[ $# -lt 1 || ! -d "$1" || ("$1" != *.app && "$1" != *.app/) ]]; then
    echo "usage: bash scripts/macos/run-app-soft-gl.sh PATH/TO/APP.app [APP ARGS...]" >&2
    exit 2
fi
APP="$(cd "$1" && pwd)"
shift

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE="${REPO_ROOT}/scripts/macos/softgl.c"
EXE="${APP}/Contents/MacOS/$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' \
    "${APP}/Contents/Info.plist")"
SDL="${APP}/Contents/MacOS/SDL2"
if [[ ! -f "$SDL" ]]; then
    SDL="$(find "${APP}/Contents" -name SDL2 -type f | head -1)"
fi
for f in "$EXE" "$SDL"; do
    if [[ -z "$f" || ! -f "$f" ]]; then
        echo "run-app-soft-gl.sh: no ${f:-SDL2} in ${APP}" >&2
        exit 1
    fi
done
if codesign -dv "$EXE" 2>&1 | grep -q 'flags=.*runtime'; then
    echo "run-app-soft-gl.sh: warning: ${EXE} has the hardened runtime;" \
        "macOS may drop the library" >&2
fi

LIB="${REPO_ROOT}/build/macos/libsoftgl-app-$(printf '%s' "$SDL" | md5 -q | cut -c1-12).dylib"
if [[ ! -f "$LIB" || "$SOURCE" -nt "$LIB" || "$SDL" -nt "$LIB" || "$0" -nt "$LIB" ]]; then
    echo "building ${LIB} against ${SDL}"
    mkdir -p "$(dirname "$LIB")"
    # -Dconstructor=used: softgl.c's __attribute__((constructor)) becomes a plain unused
    # function, so nothing runs at load (checked below: no initializer section).
    clang -dynamiclib -O2 -Wl,-headerpad_max_install_names -Dconstructor=used \
        -o "$LIB" "$SOURCE" "$SDL"
    if otool -l "$LIB" | grep -qE 'sectname __(mod_init_func|init_offsets)'; then
        rm -f "$LIB"
        echo "run-app-soft-gl.sh: the library still has a constructor; softgl.c changed?" >&2
        exit 1
    fi
    # The bundle's SDL2 names itself by its build path; point at the real file, so dyld
    # loads the same image the app's Kivy does (@executable_path/SDL2).
    install_name_tool -change "$(otool -D "$SDL" | tail -1)" "$SDL" "$LIB"
    codesign --force --sign - "$LIB"
fi

# Exported only now, inside a running bash: macOS strips DYLD_* as a protected program such
# as /bin/bash starts, not from what it then runs. No multisampling: the software renderer
# crashed with it on (see with-soft-gl.sh).
export DYLD_INSERT_LIBRARIES="$LIB"
export KCFG_GRAPHICS_MULTISAMPLES="${KCFG_GRAPHICS_MULTISAMPLES:-0}"
echo "starting ${EXE}"
exec "$EXE" "$@"
