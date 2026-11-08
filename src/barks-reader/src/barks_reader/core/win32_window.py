"""The app's window on Windows, by its Win32 handle: found, and its calls typed. Kivy-free.

Direct ``user32`` calls, for the window backend that puts the window back after a
fullscreen exit (``ui/platform_window_win32.py``), which keeps the Kivy clock and
window parts. Nothing here is called on another platform, and the module imports
everywhere: ``user32`` is loaded only when a window is bound.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import c_long, wintypes
from typing import Any, ClassVar

from loguru import logger


class RECT(ctypes.Structure):
    """A Win32 ``RECT``: left, top, right, bottom."""

    _fields_: ClassVar[list[tuple[str, type[c_long]]]] = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


_CLASS_NAME_LENGTH = 256


def _typed_user32() -> Any:  # noqa: ANN401
    """Load a fresh ``user32`` with the lookup's calls typed for 64-bit handles.

    Untyped, a handle above 2**31 cannot be passed in (ctypes converts a Python int
    to a C int) and ``GetActiveWindow`` returns it truncated. A fresh load leaves the
    shared ``ctypes.windll.user32`` that Kivy calls as it is.
    """
    user32 = ctypes.WinDLL("user32", use_last_error=True)  # ty: ignore[unresolved-attribute]

    user32.GetActiveWindow.argtypes = []
    user32.GetActiveWindow.restype = wintypes.HWND
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL

    return user32


def find_app_hwnd() -> int:
    """Return the app's window: the active one, else the first SDL window of this process.

    Returns:
        The window handle, or 0 when there is none.

    """
    found_hwnd = _typed_user32().GetActiveWindow()
    if found_hwnd:
        logger.info(f"Found hwnd using GetActiveWindow: {hex(found_hwnd)}")
        return found_hwnd
    return find_hwnd_by_enum_windows()


def _sdl_class_name(user32: Any, hwnd: int, pid: int) -> str | None:  # noqa: ANN401
    """Return the window's class name if it is a visible SDL window of process `pid`."""
    if not user32.IsWindowVisible(hwnd):
        return None

    window_pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
    if window_pid.value != pid:
        return None

    # Kivy's window is SDL's.
    class_name = ctypes.create_unicode_buffer(_CLASS_NAME_LENGTH)
    user32.GetClassNameW(hwnd, class_name, _CLASS_NAME_LENGTH)
    return class_name.value if class_name.value.startswith("SDL") else None


def find_hwnd_by_enum_windows() -> int:
    """Find our SDL window by enumerating all top-level windows and matching PID.

    Returns:
        The window handle, or 0 when there is none.

    """
    user32 = _typed_user32()
    current_pid = os.getpid()
    found_hwnd = 0

    def enum_callback(hwnd_candidate: int | None, _lparam: int) -> bool:
        nonlocal found_hwnd
        if not hwnd_candidate:
            return True
        class_name = _sdl_class_name(user32, hwnd_candidate, current_pid)
        if class_name is None:
            return True  # Continue enumeration
        found_hwnd = hwnd_candidate
        logger.info(f"Found SDL window: HWND = {hex(hwnd_candidate)}, class = {class_name}.")
        return False  # Stop enumeration

    enum_windows_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)  # ty: ignore[unresolved-attribute]
    user32.EnumWindows(enum_windows_proc(enum_callback), 0)

    if found_hwnd:
        logger.info(f"Found window via EnumWindows: {hex(found_hwnd)}.")

    return found_hwnd


class Win32Window:
    """A window by its handle, with ``user32``'s calls on it typed for 64-bit handles.

    Attributes:
        hwnd: The window handle.
        move_window: ``MoveWindow``: ``(hwnd, x, y, width, height, repaint) -> BOOL``.
        get_window_rect: ``GetWindowRect``: ``(hwnd, byref(RECT)) -> BOOL``.
        get_client_rect: ``GetClientRect``: ``(hwnd, byref(RECT)) -> BOOL``.

    """

    def __init__(self, hwnd: int) -> None:
        """Bind to `hwnd`, loading a fresh ``user32`` so Kivy's own calls are not disturbed.

        Raises:
            OSError: When ``user32`` cannot be loaded (not Windows).

        """
        self.hwnd = hwnd

        user32 = ctypes.WinDLL("user32", use_last_error=True)  # ty: ignore[unresolved-attribute]

        self.move_window: Any = user32.MoveWindow
        self.move_window.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.BOOL,
        ]
        self.move_window.restype = wintypes.BOOL

        self.get_window_rect: Any = user32.GetWindowRect
        self.get_window_rect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
        self.get_window_rect.restype = wintypes.BOOL

        self.get_client_rect: Any = user32.GetClientRect
        self.get_client_rect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
        self.get_client_rect.restype = wintypes.BOOL
