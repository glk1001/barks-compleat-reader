"""Press one key in a running program through the OS's real input path.

For the build smoke test (`smoke-test-build.sh --press-escape`), which presses a
key in a built executable's first window on every CI build leg. The key goes in
the way a keyboard's would, so it crosses the OS, SDL and Kivy:

- Linux: `xdotool`, through the X test extension, on the display in $DISPLAY (the
  smoke test's own Xvfb). The program's window is focused first when it can be
  found by process; the display holds nothing else.
- Windows: `SendInput`, after bringing the program's window to the front (from
  gui_probe_win32.py, the GUI suite's Windows backend). The window is found as the
  visible one owned by a process running the named executable.
- macOS: `CGEventPostToPid`, straight to each given process; it needs no focus.
  GitHub's macOS runners allow it (the process is trusted for Accessibility).

Usage:
  python scripts/send_os_key.py Escape --pids 1234 1235      # Linux, macOS
  python scripts/send_os_key.py Escape --image app.exe       # Windows

Only the standard library is used (plus the probe's backend on Windows).
"""

# cspell:ignore xdotool onlyvisible windowfocus IMAGENAME tasklist pids

from __future__ import annotations

import argparse
import csv
import ctypes
import ctypes.util
import io
import shutil
import subprocess
import sys
import time

# macOS virtual key codes (HIToolbox Events.h) for the keys the smoke test presses.
MACOS_KEY_CODES = {"Escape": 53, "Return": 36}


class SendKeyError(RuntimeError):
    """The key could not be sent; the message says why."""


def _send_linux(key: str, pids: list[int]) -> None:
    xdotool = shutil.which("xdotool")
    if xdotool is None:
        msg = "xdotool is not installed"
        raise SendKeyError(msg)
    for pid in pids:
        found = subprocess.run(  # noqa: S603
            [xdotool, "search", "--onlyvisible", "--pid", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.split()
        if found:
            subprocess.run([xdotool, "windowfocus", "--sync", found[0]], check=False)  # noqa: S603
            break
    subprocess.run([xdotool, "key", key], check=True)  # noqa: S603


def _windows_pids(image: str) -> list[int]:
    listing = subprocess.run(  # noqa: S603 (fixed argv; the image name is ours)
        ["tasklist", "/FO", "CSV", "/NH", "/FI", f"IMAGENAME eq {image}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return [int(row[1]) for row in csv.reader(io.StringIO(listing)) if len(row) > 1]


def _send_windows(key: str, image: str) -> None:
    import gui_probe_win32  # noqa: PLC0415 (Windows only)

    backend = gui_probe_win32.Win32Backend()
    pids = set(_windows_pids(image))
    if not pids:
        msg = f"no process is running {image}"
        raise SendKeyError(msg)
    window = gui_probe_win32.find_window_of_processes(pids)
    if window is None:
        msg = f"no visible window belongs to {image} (processes {sorted(pids)})"
        raise SendKeyError(msg)
    if not backend.bring_to_front(window):
        msg = "the window would not come to the front, so the key would go elsewhere"
        raise SendKeyError(msg)
    backend.send_key(key)


def _send_macos(key: str, pids: list[int]) -> None:
    quartz = ctypes.CDLL(ctypes.util.find_library("ApplicationServices"))
    core = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
    quartz.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
    quartz.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
    quartz.CGEventPostToPid.argtypes = [ctypes.c_int, ctypes.c_void_p]
    core.CFRelease.argtypes = [ctypes.c_void_p]
    code = MACOS_KEY_CODES[key]
    for pid in pids:
        for down in (True, False):
            event = quartz.CGEventCreateKeyboardEvent(None, code, down)
            quartz.CGEventPostToPid(pid, event)
            core.CFRelease(event)
            time.sleep(0.05)


def main(argv: list[str]) -> int:
    """Press the key; return 0, or 1 with the reason on stderr."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("key", choices=sorted(MACOS_KEY_CODES))
    parser.add_argument("--pids", type=int, nargs="*", default=[], help="Linux, macOS")
    parser.add_argument("--image", help="Windows: the executable's file name")
    options = parser.parse_args(argv)
    if sys.platform == "win32" and not options.image:
        parser.error("--image is needed on Windows")
    if sys.platform == "darwin" and not options.pids:
        parser.error("--pids is needed on macOS")
    try:
        if sys.platform == "win32":
            _send_windows(options.key, options.image)
        elif sys.platform == "darwin":
            _send_macos(options.key, options.pids)
        else:
            _send_linux(options.key, options.pids)
    except (SendKeyError, subprocess.CalledProcessError) as exc:
        print(f"send_os_key: {exc}", file=sys.stderr)  # noqa: T201
        return 1
    print(f"send_os_key: pressed {options.key}")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
