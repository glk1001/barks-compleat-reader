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


def find_app_hwnd() -> Any:  # noqa: ANN401
    """Return the app's window: the active one, else the first SDL window of this process."""
    found_hwnd = ctypes.windll.user32.GetActiveWindow()  # ty: ignore[unresolved-attribute]
    if found_hwnd:
        logger.info(f"Found hwnd using GetActiveWindow: {hex(found_hwnd)}")
        return found_hwnd
    return find_hwnd_by_enum_windows()


def find_hwnd_by_enum_windows() -> Any:  # noqa: ANN401
    """Find our SDL window by enumerating all top-level windows and matching PID."""
    GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId  # noqa: N806  # ty: ignore[unresolved-attribute]
    EnumWindows = ctypes.windll.user32.EnumWindows  # noqa: N806  # ty: ignore[unresolved-attribute]
    IsWindowVisible = ctypes.windll.user32.IsWindowVisible  # noqa: N806  # ty: ignore[unresolved-attribute]
    GetClassNameW = ctypes.windll.user32.GetClassNameW  # noqa: N806  # ty: ignore[unresolved-attribute]

    current_pid = os.getpid()
    found_hwnd = 0

    def enum_callback(hwnd_candidate, _lparam) -> bool:  # noqa: ANN001
        nonlocal found_hwnd
        if IsWindowVisible(hwnd_candidate):
            pid = wintypes.DWORD()
            GetWindowThreadProcessId(hwnd_candidate, ctypes.byref(pid))

            if pid.value == current_pid:
                # Check if it's an SDL window (Kivy uses SDL2).
                class_name = ctypes.create_unicode_buffer(256)
                GetClassNameW(hwnd_candidate, class_name, 256)

                if class_name.value.startswith("SDL"):
                    found_hwnd = hwnd_candidate
                    logger.info(
                        f"Found SDL window:"
                        f" HWND = {hex(hwnd_candidate)}, class = {class_name.value}."
                    )
                    return False  # Stop enumeration
        return True  # Continue enumeration

    # Create callback and enumerate windows.
    ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)  # noqa: N806  # ty: ignore[unresolved-attribute]
    callback_ptr = ENUM_WINDOWS_PROC(enum_callback)
    EnumWindows(callback_ptr, 0)

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
