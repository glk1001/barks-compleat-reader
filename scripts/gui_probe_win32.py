"""The Windows backend for ``gui_probe.py``: real input through ``SendInput``.

Keys and clicks go into the OS input queue exactly as a keyboard's would, so
they reach the app through Windows, SDL and Kivy - the path a user's keyboard or
remote takes, and the one where the suite's input bugs were found. Nothing is
fed into the app from inside it.

``SendInput`` goes to the foreground window, which is why the probe brings the
app to the front before every burst - without sending any input to do it, so
nothing ever reaches a window other than the app's. A locked screen or a minimized remote
session accepts nothing; ``doctor`` checks for both.

Its calls work only on Windows; the module imports anywhere, so its key table
and structures can be tested on every platform.
"""

# cspell:ignore DEVMODE DPIAWARENESSCONTEXT EXTENDEDKEY KEYBDINPUT KEYEVENTF LEFTDOWN
# cspell:ignore LEFTUP MAPVK MOUSEEVENTF MOUSEINPUT SWITCHDESKTOP HARDWAREINPUT
# cspell:ignore VSC shcore wparam lparam INPUTUNION KEYUP creationflags getwindowsversion
# cspell:ignore taskkill pids

from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from ctypes import wintypes
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from pathlib import Path

_ON_WINDOWS = sys.platform == "win32"
_user32: Any = ctypes.WinDLL("user32", use_last_error=True) if _ON_WINDOWS else None
_kernel32: Any = ctypes.WinDLL("kernel32", use_last_error=True) if _ON_WINDOWS else None

_ULONG_PTR = ctypes.c_size_t

_INPUT_MOUSE = 0
_INPUT_KEYBOARD = 1
_KEYEVENTF_EXTENDEDKEY = 0x0001
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004
_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP = 0x0004
_MAPVK_VK_TO_VSC = 0
_VK_SHIFT = 0x10
_SW_RESTORE = 9
_DESKTOP_SWITCHDESKTOP = 0x0100
_SYNCHRONIZE = 0x00100000
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259
_WAIT_OBJECT_0 = 0
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NO_WINDOW = 0x08000000
_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4

# X11 keysym names (what the suite and gui-probe.sh use) -> Windows virtual keys.
# The arrows and the editing block sit on the extended part of a real keyboard,
# and a key sent without the extended flag reaches SDL as its numeric-pad twin.
VIRTUAL_KEYS: dict[str, tuple[int, bool]] = {
    "Escape": (0x1B, False),
    "Return": (0x0D, False),
    "Tab": (0x09, False),
    "BackSpace": (0x08, False),
    "space": (0x20, False),
    "Up": (0x26, True),
    "Down": (0x28, True),
    "Left": (0x25, True),
    "Right": (0x27, True),
    "Delete": (0x2E, True),
    "Home": (0x24, True),
    "End": (0x23, True),
    "Prior": (0x21, True),
    "Next": (0x22, True),
}


class _MOUSEINPUT(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class _RECT(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


_ENUM_WINDOWS_PROC: Any = (
    ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM) if _ON_WINDOWS else None
)


def _declare() -> None:
    """Give every call its real signature, so 64-bit handles are not cut to 32 bits."""
    u, k = _user32, _kernel32
    u.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
    u.SendInput.restype = wintypes.UINT
    u.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    u.MapVirtualKeyW.restype = wintypes.UINT
    u.VkKeyScanW.argtypes = [wintypes.WCHAR]
    u.VkKeyScanW.restype = ctypes.c_short
    u.EnumWindows.argtypes = [_ENUM_WINDOWS_PROC, wintypes.LPARAM]
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(_RECT)]
    u.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    u.GetForegroundWindow.restype = wintypes.HWND
    u.SetForegroundWindow.argtypes = [wintypes.HWND]
    u.IsIconic.argtypes = [wintypes.HWND]
    u.BringWindowToTop.argtypes = [wintypes.HWND]
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.GetWindowThreadProcessId.restype = wintypes.DWORD
    u.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    u.AttachThreadInput.restype = wintypes.BOOL
    k.GetCurrentThreadId.restype = wintypes.DWORD
    u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    u.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    u.OpenInputDesktop.restype = wintypes.HANDLE
    u.SwitchDesktop.argtypes = [wintypes.HANDLE]
    u.CloseDesktop.argtypes = [wintypes.HANDLE]
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.OpenProcess.restype = wintypes.HANDLE
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.CloseHandle.argtypes = [wintypes.HANDLE]


def _make_dpi_aware() -> None:
    """Work in physical pixels, so window rectangles and screenshots agree on a scaled display."""
    try:
        _user32.SetProcessDpiAwarenessContext.argtypes = [wintypes.HANDLE]
        if _user32.SetProcessDpiAwarenessContext(_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
            return
    except AttributeError:
        pass
    try:
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)  # ty: ignore[unresolved-attribute]
    except (AttributeError, OSError):
        _user32.SetProcessDPIAware()


def _key_input(vk: int, *, extended: bool, up: bool) -> _INPUT:
    flags = (_KEYEVENTF_EXTENDEDKEY if extended else 0) | (_KEYEVENTF_KEYUP if up else 0)
    scan = _user32.MapVirtualKeyW(vk, _MAPVK_VK_TO_VSC)
    item = _INPUT(type=_INPUT_KEYBOARD)
    item.u.ki = _KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    return item


def _unicode_input(char: str, *, up: bool) -> _INPUT:
    item = _INPUT(type=_INPUT_KEYBOARD)
    flags = _KEYEVENTF_UNICODE | (_KEYEVENTF_KEYUP if up else 0)
    item.u.ki = _KEYBDINPUT(wVk=0, wScan=ord(char), dwFlags=flags, time=0, dwExtraInfo=0)
    return item


def _mouse_input(flags: int) -> _INPUT:
    item = _INPUT(type=_INPUT_MOUSE)
    item.u.mi = _MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=0)
    return item


def _send(*items: _INPUT) -> None:
    """Queue the events in one call, so nothing else can land between them."""
    array = (_INPUT * len(items))(*items)
    sent = _user32.SendInput(len(items), array, ctypes.sizeof(_INPUT))
    if sent != len(items):
        error = ctypes.get_last_error()  # ty: ignore[unresolved-attribute]
        msg = (
            f"SendInput queued {sent} of {len(items)} events (error {error}):"
            " a locked screen, a minimized remote session, or a window of higher"
            " integrity in front refuses injected input"
        )
        raise RuntimeError(msg)


def find_window_of_processes(pids: set[int]) -> int | None:
    """Return the first visible, titled top-level window owned by one of `pids`.

    For a window that has no title of its own to find it by (the first-run
    installer's). Call after a ``Win32Backend`` exists, which declares the calls.
    """
    found: list[int] = []

    def visit(hwnd: int, _lparam: int) -> bool:
        if not _user32.IsWindowVisible(hwnd) or _user32.GetWindowTextLengthW(hwnd) == 0:
            return True
        owner = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value in pids:
            found.append(hwnd)
            return False
        return True

    _user32.EnumWindows(_ENUM_WINDOWS_PROC(visit), 0)
    return found[0] if found else None


class Win32Backend:
    """The ``gui_probe.Backend`` for Windows."""

    # A group of its own, so the probe's console never forwards its Ctrl+C to the
    # app, and no console window pops up for the uv or python child.
    creation_flags = _CREATE_NEW_PROCESS_GROUP | _CREATE_NO_WINDOW

    def __init__(self) -> None:
        _declare()
        _make_dpi_aware()

    def find_window(self, title: str) -> int | None:
        found: list[int] = []

        def visit(hwnd: int, _lparam: int) -> bool:
            if not _user32.IsWindowVisible(hwnd):
                return True
            length = _user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            text = ctypes.create_unicode_buffer(length + 1)
            _user32.GetWindowTextW(hwnd, text, length + 1)
            if title in text.value:
                found.append(hwnd)
                return False
            return True

        _user32.EnumWindows(_ENUM_WINDOWS_PROC(visit), 0)
        return found[0] if found else None

    def client_geometry(self, window: int) -> tuple[int, int, int, int]:
        rect = _RECT()
        if not _user32.GetClientRect(window, ctypes.byref(rect)):
            msg = "GetClientRect failed: the app window has gone"
            raise RuntimeError(msg)
        origin = wintypes.POINT(0, 0)
        _user32.ClientToScreen(window, ctypes.byref(origin))
        return rect.right - rect.left, rect.bottom - rect.top, origin.x, origin.y

    def bring_to_front(self, window: int) -> bool:
        if _user32.GetForegroundWindow() == window:
            return True
        if _user32.IsIconic(window):
            _user32.ShowWindow(window, _SW_RESTORE)
        # Windows lets only the thread that owns the foreground hand it on. Joining
        # that thread's input for the moment of the switch makes this probe one of
        # its own, without sending a key anywhere: a key sent to take the foreground
        # would land in whatever window had it.
        foreground = _user32.GetForegroundWindow()
        owner = _user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
        this = _kernel32.GetCurrentThreadId()
        attached = (
            bool(owner)
            and owner != this
            and bool(
                _user32.AttachThreadInput(this, owner, True)  # noqa: FBT003
            )
        )
        try:
            _user32.BringWindowToTop(window)
            _user32.SetForegroundWindow(window)
        finally:
            if attached:
                _user32.AttachThreadInput(this, owner, False)  # noqa: FBT003
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if _user32.GetForegroundWindow() == window:
                return True
            time.sleep(0.05)
        return False

    def move_pointer(self, x: int, y: int) -> None:
        _user32.SetCursorPos(x, y)

    def click(self, x: int, y: int) -> None:
        _user32.SetCursorPos(x, y)
        _send(_mouse_input(_MOUSEEVENTF_LEFTDOWN), _mouse_input(_MOUSEEVENTF_LEFTUP))

    def send_key(self, name: str) -> None:
        if name in VIRTUAL_KEYS:
            vk, extended = VIRTUAL_KEYS[name]
            _send(
                _key_input(vk, extended=extended, up=False),
                _key_input(vk, extended=extended, up=True),
            )
        elif len(name) == 1:
            self.send_char(name)
        else:
            msg = f"no Windows key for the name {name!r}; add it to VIRTUAL_KEYS"
            raise ValueError(msg)

    def send_char(self, char: str) -> None:
        # A character the keyboard layout has goes as its real key (with Shift if
        # it needs it), as a person typing would send it; any other as Unicode.
        scan = _user32.VkKeyScanW(char)
        if scan == -1:
            _send(_unicode_input(char, up=False), _unicode_input(char, up=True))
            return
        vk, shift = scan & 0xFF, bool(scan & 0x100)
        events = [
            _key_input(vk, extended=False, up=False),
            _key_input(vk, extended=False, up=True),
        ]
        if shift:
            events = [
                _key_input(_VK_SHIFT, extended=False, up=False),
                *events,
                _key_input(_VK_SHIFT, extended=False, up=True),
            ]
        _send(*events)

    def capture(self, rect: tuple[int, int, int, int], out: Path) -> None:
        from PIL import ImageGrab  # noqa: PLC0415 (only a screenshot needs Pillow)

        width, height, x, y = rect
        ImageGrab.grab(bbox=(x, y, x + width, y + height), all_screens=True).save(out)

    def process_alive(self, pid: int) -> bool:
        handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)  # noqa: FBT003
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            _kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return code.value == _STILL_ACTIVE
        finally:
            _kernel32.CloseHandle(handle)

    def kill_tree(self, pid: int, max_secs: float) -> None:
        # The app has no close handler to ask, and on Linux the probe ends it with
        # a signal it does not catch either: the same outcome, a forced end.
        handle = _kernel32.OpenProcess(_SYNCHRONIZE, False, pid)  # noqa: FBT003
        subprocess.run(  # noqa: S603
            ["taskkill", "/PID", str(pid), "/T", "/F"],  # noqa: S607 (a system tool, on PATH)
            capture_output=True,
            check=False,
        )
        if handle:
            try:
                _kernel32.WaitForSingleObject(handle, int(max_secs * 1000))
            finally:
                _kernel32.CloseHandle(handle)

    def doctor_checks(self) -> list[tuple[str, str]]:
        checks: list[tuple[str, str]] = [("OK", f"Windows {sys.getwindowsversion().major}")]  # ty: ignore[unresolved-attribute]
        desktop = _user32.OpenInputDesktop(0, False, _DESKTOP_SWITCHDESKTOP)  # noqa: FBT003
        unlocked = bool(desktop) and bool(_user32.SwitchDesktop(desktop))
        if desktop:
            _user32.CloseDesktop(desktop)
        checks.append(
            ("OK", "an unlocked, connected desktop")
            if unlocked
            else ("FAIL", "the desktop is locked or disconnected: injected input would go nowhere")
        )
        if self.find_window("Compleat Barks Disney Reader") is not None:
            checks.append(("FAIL", "a Barks Reader window is open - close it before a run"))
        try:
            from PIL import ImageGrab  # noqa: F401, PLC0415

            checks.append(("OK", "Pillow (screenshots)"))
        except ImportError:
            checks.append(
                ("FAIL", "Pillow not importable - run the probe with the workspace's Python")
            )
        return checks
