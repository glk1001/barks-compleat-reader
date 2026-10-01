"""The macOS backend for ``gui_probe.py``: real input through Quartz events.

Keys and clicks are Quartz events, as a keyboard's and a mouse's are, so they
reach the app through the window server, SDL and Kivy - the path a user's input
takes. Nothing is fed into the app from inside it.

Keys are posted to the app's process alone, so a key can reach nothing else even
if another app takes the front mid-run; clicks land by position, which is why
the probe activates the app before every burst and checks its window is in front.
Posting events needs the Accessibility permission, and window titles and
screenshots need Screen Recording, both granted to the terminal the probe runs
from (System Preferences, Security & Privacy, Privacy); ``doctor`` checks both.

Coordinates are the window server's: points, from the top left of the main
display. On a display with no scaling (the VirtualBox guest this was written on)
a point is a pixel, and the app's logged geometry, the window list and a
screenshot agree; a Retina display would need the backing scale applied.

Its calls work only on macOS; the module imports anywhere, so its key tables and
its window picking can be tested on every platform.
"""

# cspell:ignore CGHID CGSS pgid killpg screencapture objc msgsend autorelease
# cspell:ignore frontmost UniChar keycode keycodes mac_ver appsvc libobjc waitpid WNOHANG
# cspell:ignore asdfhgzxcv bqweryt

from __future__ import annotations

import contextlib
import ctypes
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

_ON_MACOS = sys.platform == "darwin"


def _framework(name: str) -> Any:  # noqa: ANN401 (a ctypes library, attributes made on use)
    return ctypes.CDLL(f"/System/Library/Frameworks/{name}.framework/{name}") if _ON_MACOS else None


_cf: Any = _framework("CoreFoundation")
_cg: Any = _framework("CoreGraphics")
_appsvc: Any = _framework("ApplicationServices")
_objc: Any = ctypes.CDLL("/usr/lib/libobjc.A.dylib") if _ON_MACOS else None
if _ON_MACOS:
    _framework("AppKit")  # loaded for NSRunningApplication, which _activate looks up by name

_WINDOW_LIST_ON_SCREEN_ONLY = 1 << 0
_WINDOW_LIST_INCLUDING_WINDOW = 1 << 3
_WINDOW_LIST_EXCLUDE_DESKTOP = 1 << 4
_HID_EVENT_TAP = 0
_EVENT_LEFT_MOUSE_DOWN = 1
_EVENT_LEFT_MOUSE_UP = 2
_EVENT_MOUSE_MOVED = 5
_MOUSE_BUTTON_LEFT = 0
_EVENT_FLAG_SHIFT = 0x00020000
_CF_STRING_UTF8 = 0x08000100
_CF_NUMBER_SINT64 = 4
_NS_ACTIVATE_IGNORING_OTHER_APPS = 1 << 1
# A process signalled to stop gets this long before it is killed outright.
_TERM_GRACE_SECS = 3
# How long the app gets to come to the front, asked again this often.
_FRONT_WAIT_SECS = 5
_FRONT_ASK_EVERY_SECS = 1

_LOCKED = "the screen is locked, or there is no desktop session: input would go nowhere"
_NO_ACCESSIBILITY = (
    "no Accessibility permission: keys and clicks would be dropped - grant it to the"
    " terminal in System Preferences, Security & Privacy, Privacy"
)
_NO_SCREEN_RECORDING = (
    "no Screen Recording permission: the app's window has no title to find it by, and"
    " screenshots show the wallpaper - grant it to the terminal, as Accessibility"
)

# X11 keysym names (what the suite and gui-probe.sh use) -> macOS virtual key codes
# (Carbon's kVK_* values, which name physical keys, whatever the keyboard layout).
VIRTUAL_KEYS: dict[str, int] = {
    "Escape": 53,
    "Return": 36,
    "Tab": 48,
    "BackSpace": 51,
    "space": 49,
    "Up": 126,
    "Down": 125,
    "Left": 123,
    "Right": 124,
    # Forward delete: the Mac's Delete key is BackSpace.
    "Delete": 117,
    "Home": 115,
    "End": 119,
    "Prior": 116,
    "Next": 121,
}

# The US keyboard's key for each character it types: (key code, with Shift). A
# typed character goes as this key with the character itself attached, so the
# text is exact whatever the layout and the key is the one a person would press.
_US_KEYS = "asdfhgzxcv\0bqweryt123465=97-80]ou[ip\0lj'k;\\,/nm."
_US_SHIFTED = 'ASDFHGZXCV\0BQWERYT!@#$^%+(&_*)}OU{IP\0LJ"K:|<?NM>'
CHAR_KEYS: dict[str, tuple[int, bool]] = {
    **{c: (code, False) for code, c in enumerate(_US_KEYS) if c != "\0"},
    **{c: (code, True) for code, c in enumerate(_US_SHIFTED) if c != "\0"},
    " ": (49, False),
    "`": (50, False),
    "~": (50, True),
}


@dataclass(frozen=True)
class WindowInfo:
    """One window from the window server's list, in front-to-back order there."""

    number: int
    owner_pid: int
    owner_name: str
    title: str
    layer: int
    bounds: tuple[int, int, int, int]  # width, height, x, y


def is_app_window(window: WindowInfo, title: str) -> bool:
    """Return whether `window` is the reader's: a normal window of a Python or reader process.

    The owner check keeps out a terminal or an editor whose window title names the
    app (a tab showing the repo, a file open in it), which would otherwise take
    the keys meant for the app.
    """
    owner = window.owner_name.lower()
    return window.layer == 0 and title in window.title and owner.startswith(("python", "barks"))


def pick_app_window(windows: Iterable[WindowInfo], title: str) -> WindowInfo | None:
    """Return the frontmost of `windows` that is the app's, or None."""
    return next((w for w in windows if is_app_window(w, title)), None)


def frontmost_normal_window(windows: Iterable[WindowInfo]) -> WindowInfo | None:
    """Return the frontmost ordinary (layer 0) window: the one the active app is showing."""
    return next((w for w in windows if w.layer == 0), None)


class _CGPoint(ctypes.Structure):
    _fields_ = (("x", ctypes.c_double), ("y", ctypes.c_double))


class _CGRect(ctypes.Structure):
    _fields_ = (
        ("x", ctypes.c_double),
        ("y", ctypes.c_double),
        ("width", ctypes.c_double),
        ("height", ctypes.c_double),
    )


def _declare() -> None:
    """Give every call its real signature, so pointers are not cut to 32 bits."""
    cf, cg, ax, objc = _cf, _cg, _appsvc, _objc
    vp = ctypes.c_void_p
    cf.CFArrayGetCount.argtypes = [vp]
    cf.CFArrayGetCount.restype = ctypes.c_long
    cf.CFArrayGetValueAtIndex.argtypes = [vp, ctypes.c_long]
    cf.CFArrayGetValueAtIndex.restype = vp
    cf.CFDictionaryGetValue.argtypes = [vp, vp]
    cf.CFDictionaryGetValue.restype = vp
    cf.CFStringCreateWithCString.argtypes = [vp, ctypes.c_char_p, ctypes.c_uint32]
    cf.CFStringCreateWithCString.restype = vp
    cf.CFStringGetCString.argtypes = [vp, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
    cf.CFStringGetCString.restype = ctypes.c_bool
    cf.CFNumberGetValue.argtypes = [vp, ctypes.c_int, vp]
    cf.CFNumberGetValue.restype = ctypes.c_bool
    cf.CFBooleanGetValue.argtypes = [vp]
    cf.CFBooleanGetValue.restype = ctypes.c_bool
    cf.CFRelease.argtypes = [vp]
    cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    cg.CGWindowListCopyWindowInfo.restype = vp
    cg.CGRectMakeWithDictionaryRepresentation.argtypes = [vp, ctypes.POINTER(_CGRect)]
    cg.CGRectMakeWithDictionaryRepresentation.restype = ctypes.c_bool
    cg.CGEventCreateMouseEvent.argtypes = [vp, ctypes.c_uint32, _CGPoint, ctypes.c_uint32]
    cg.CGEventCreateMouseEvent.restype = vp
    cg.CGEventCreateKeyboardEvent.argtypes = [vp, ctypes.c_uint16, ctypes.c_bool]
    cg.CGEventCreateKeyboardEvent.restype = vp
    cg.CGEventKeyboardSetUnicodeString.argtypes = [
        vp,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_uint16),
    ]
    cg.CGEventSetFlags.argtypes = [vp, ctypes.c_uint64]
    cg.CGEventPost.argtypes = [ctypes.c_uint32, vp]
    cg.CGEventPostToPid.argtypes = [ctypes.c_int, vp]
    cg.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
    cg.CGSessionCopyCurrentDictionary.restype = vp
    ax.AXIsProcessTrusted.restype = ctypes.c_bool
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.objc_getClass.restype = vp
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = vp
    objc.objc_autoreleasePoolPush.restype = vp
    objc.objc_autoreleasePoolPop.argtypes = [vp]


def _cf_string(text: str) -> int:
    return _cf.CFStringCreateWithCString(None, text.encode(), _CF_STRING_UTF8)


def _dict_get(info: int, key: str) -> int | None:
    name = _cf_string(key)
    try:
        return _cf.CFDictionaryGetValue(info, name)
    finally:
        _cf.CFRelease(name)


def _dict_int(info: int, key: str) -> int:
    value = _dict_get(info, key)
    out = ctypes.c_int64(0)
    if value:
        _cf.CFNumberGetValue(value, _CF_NUMBER_SINT64, ctypes.byref(out))
    return out.value


def _dict_str(info: int, key: str) -> str:
    value = _dict_get(info, key)
    if not value:
        return ""
    buffer = ctypes.create_string_buffer(1024)
    _cf.CFStringGetCString(value, buffer, len(buffer), _CF_STRING_UTF8)
    return buffer.value.decode("utf-8", errors="replace")


def _dict_bounds(info: int) -> tuple[int, int, int, int]:
    rect = _CGRect()
    value = _dict_get(info, "kCGWindowBounds")
    if value:
        _cg.CGRectMakeWithDictionaryRepresentation(value, ctypes.byref(rect))
    return round(rect.width), round(rect.height), round(rect.x), round(rect.y)


def window_list(*, only: int | None = None) -> list[WindowInfo]:
    """Return the on-screen windows front to back, or just window `only` if it exists."""
    if only is None:
        options, relative = _WINDOW_LIST_ON_SCREEN_ONLY | _WINDOW_LIST_EXCLUDE_DESKTOP, 0
    else:
        options, relative = _WINDOW_LIST_INCLUDING_WINDOW, only
    array = _cg.CGWindowListCopyWindowInfo(options, relative)
    if not array:
        return []
    try:
        windows = []
        for index in range(_cf.CFArrayGetCount(array)):
            info = _cf.CFArrayGetValueAtIndex(array, index)
            windows.append(
                WindowInfo(
                    number=_dict_int(info, "kCGWindowNumber"),
                    owner_pid=_dict_int(info, "kCGWindowOwnerPID"),
                    owner_name=_dict_str(info, "kCGWindowOwnerName"),
                    title=_dict_str(info, "kCGWindowName"),
                    layer=_dict_int(info, "kCGWindowLayer"),
                    bounds=_dict_bounds(info),
                )
            )
        return windows
    finally:
        _cf.CFRelease(array)


def _activate(pid: int) -> bool:
    """Ask app `pid` to become the active app; return whether macOS took the request."""
    send = _objc.objc_msgSend
    pool = _objc.objc_autoreleasePoolPush()
    try:
        cls = _objc.objc_getClass(b"NSRunningApplication")
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
        send.restype = ctypes.c_void_p
        app = send(cls, _objc.sel_registerName(b"runningApplicationWithProcessIdentifier:"), pid)
        if not app:
            return False
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        send.restype = ctypes.c_bool
        return bool(
            send(
                app,
                _objc.sel_registerName(b"activateWithOptions:"),
                _NS_ACTIVATE_IGNORING_OTHER_APPS,
            )
        )
    finally:
        _objc.objc_autoreleasePoolPop(pool)


def _post(event: int, pid: int | None = None) -> None:
    """Post `event` to process `pid` alone, or at the HID tap (where it lands by position)."""
    if not event:
        msg = "Quartz would not make the input event"
        raise RuntimeError(msg)
    try:
        if pid is None:
            _cg.CGEventPost(_HID_EVENT_TAP, event)
        else:
            _cg.CGEventPostToPid(pid, event)
    finally:
        _cf.CFRelease(event)


def _mouse(kind: int, x: int, y: int) -> None:
    _post(_cg.CGEventCreateMouseEvent(None, kind, _CGPoint(x, y), _MOUSE_BUTTON_LEFT))


def _key(pid: int, code: int, *, down: bool, shift: bool = False, char: str = "") -> None:
    event = _cg.CGEventCreateKeyboardEvent(None, code, down)
    if event and shift:
        _cg.CGEventSetFlags(event, _EVENT_FLAG_SHIFT)
    if event and char:
        units = char.encode("utf-16-le")
        buffer = (ctypes.c_uint16 * (len(units) // 2)).from_buffer_copy(units)
        _cg.CGEventKeyboardSetUnicodeString(event, len(buffer), buffer)
    _post(event, pid)


def _screen_locked() -> bool:
    session = _cg.CGSessionCopyCurrentDictionary()
    if not session:
        # No window server session at all (an ssh login): nothing can be shown or sent.
        return True
    try:
        locked = _dict_get(session, "CGSSessionScreenIsLocked")
        return bool(locked) and bool(_cf.CFBooleanGetValue(locked))
    finally:
        _cf.CFRelease(session)


def _reap(pid: int) -> None:
    """Collect `pid` if it is this process's own finished child, so it is not seen as alive."""
    with contextlib.suppress(ChildProcessError):
        os.waitpid(pid, os.WNOHANG)


def _group_alive(pgid: int) -> bool:
    """Return whether any process of group `pgid` is left (its leader reaped first)."""
    _reap(pgid)
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class DarwinBackend:
    """The ``gui_probe.Backend`` for macOS."""

    # The app in a session of its own, so the probe's terminal never forwards its
    # Ctrl+C to it, and the whole tree (uv, then Python) ends with one signal.
    creation_flags = 0
    start_new_session = True

    def __init__(self) -> None:
        _declare()
        # The app's process, once bring_to_front has found it: keys go to it alone.
        self._app_pid: int | None = None

    @staticmethod
    def workspace_app_argv(repo_root: Path) -> list[str]:
        # Through with-soft-gl.sh: a guest with no GPU driver draws on Apple's
        # software renderer, and a Mac with one still draws on its GPU.
        script = repo_root / "scripts" / "macos" / "with-soft-gl.sh"
        return ["bash", str(script), "python", str(repo_root / "main.py")]

    def find_window(self, title: str) -> int | None:
        window = pick_app_window(window_list(), title)
        return window.number if window else None

    def _info(self, window: int) -> WindowInfo:
        found = [w for w in window_list(only=window) if w.number == window]
        if not found:
            msg = "the app window has gone"
            raise RuntimeError(msg)
        return found[0]

    def client_geometry(self, window: int) -> tuple[int, int, int, int]:
        # The app's window has no title bar of the system's: its frame is its drawable
        # area, and matches the geometry the app logs.
        return self._info(window).bounds

    def bring_to_front(self, window: int) -> bool:
        owner = self._info(window).owner_pid
        # A slow machine (software drawing on two cores) can take seconds to hand an
        # app just started the front; asking again at once only queues more requests.
        now = time.monotonic()
        deadline, asked = now + _FRONT_WAIT_SECS, now - _FRONT_ASK_EVERY_SECS
        while time.monotonic() < deadline:
            front = frontmost_normal_window(window_list())
            if front is not None and front.owner_pid == owner:
                self._app_pid = owner
                return True
            if time.monotonic() - asked >= _FRONT_ASK_EVERY_SECS:
                _activate(owner)
                asked = time.monotonic()
            time.sleep(0.1)
        return False

    def move_pointer(self, x: int, y: int) -> None:
        _mouse(_EVENT_MOUSE_MOVED, x, y)

    def click(self, x: int, y: int) -> None:
        _mouse(_EVENT_MOUSE_MOVED, x, y)
        _mouse(_EVENT_LEFT_MOUSE_DOWN, x, y)
        _mouse(_EVENT_LEFT_MOUSE_UP, x, y)

    def _key_target(self) -> int:
        """Return the process keys go to: the app's, and never whatever is in front.

        A key posted where a keyboard's go lands in the frontmost app, and a run's
        Escape, Return or Left that reached a terminal instead (the app quitting, a
        click elsewhere) interrupted the Claude session running there, submitted its
        prompt or sent it to the background. Posted to the app's process, a key can
        reach nothing else.
        """
        if self._app_pid is None:
            msg = "no app process to send keys to: bring its window to the front first"
            raise RuntimeError(msg)
        return self._app_pid

    def send_key(self, name: str) -> None:
        if name in VIRTUAL_KEYS:
            pid, code = self._key_target(), VIRTUAL_KEYS[name]
            _key(pid, code, down=True)
            _key(pid, code, down=False)
        elif len(name) == 1:
            self.send_char(name)
        else:
            msg = f"no macOS key for the name {name!r}; add it to VIRTUAL_KEYS"
            raise ValueError(msg)

    def send_char(self, char: str) -> None:
        # The US key for it, with the character attached, so the text is exact on
        # any layout; a character no key types goes on the A key, as its text alone.
        pid, (code, shift) = self._key_target(), CHAR_KEYS.get(char, (0, False))
        _key(pid, code, down=True, shift=shift, char=char)
        _key(pid, code, down=False, shift=shift, char=char)

    def capture(self, rect: tuple[int, int, int, int], out: Path) -> None:
        width, height, x, y = rect
        subprocess.run(  # noqa: S603
            ["screencapture", "-x", "-t", "png", "-R", f"{x},{y},{width},{height}", str(out)],  # noqa: S607 (a system tool)
            check=True,
            capture_output=True,
        )

    def process_alive(self, pid: int) -> bool:
        _reap(pid)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def kill_tree(self, pid: int, max_secs: float) -> None:
        # The app was started as the leader of its own process group (start_new_session),
        # so the group's id is its pid, and uv and the Python under it go together.
        for sig, wait in (
            (signal.SIGTERM, min(_TERM_GRACE_SECS, max_secs)),
            (signal.SIGKILL, max_secs),
        ):
            try:
                os.killpg(pid, sig)
            except ProcessLookupError:
                return
            deadline = time.monotonic() + wait
            while time.monotonic() < deadline:
                # The whole group, not its leader: uv exits first, and the app under it
                # can still be closing then.
                if not _group_alive(pid):
                    return
                time.sleep(0.1)

    def doctor_checks(self) -> list[tuple[str, str]]:
        checks: list[tuple[str, str]] = [("OK", f"macOS {platform.mac_ver()[0]}")]
        checks.append(("FAIL", _LOCKED) if _screen_locked() else ("OK", "an unlocked desktop"))
        checks.append(
            ("OK", "Accessibility (posting keys and clicks)")
            if _appsvc.AXIsProcessTrusted()
            else ("FAIL", _NO_ACCESSIBILITY)
        )
        checks.append(
            ("OK", "Screen Recording (window titles, screenshots)")
            if _cg.CGPreflightScreenCaptureAccess()
            else ("FAIL", _NO_SCREEN_RECORDING)
        )
        if self.find_window("Compleat Barks Disney Reader") is not None:
            checks.append(("FAIL", "a Barks Reader window is open - close it before a run"))
        checks.append(
            ("OK", "clang (builds the software-OpenGL library)")
            if shutil.which("clang")
            else ("FAIL", "clang not found - install the Xcode command-line tools")
        )
        return checks
