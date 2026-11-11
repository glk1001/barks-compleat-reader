"""The app's window on Windows, by its Win32 handle: found, and its calls typed. Kivy-free.

Direct ``user32`` calls, for the window backend that puts the window back after a
fullscreen exit (``ui/platform_window_win32.py``), which keeps the Kivy clock and
window parts. Nothing here is called on another platform, and the module imports
everywhere: ``user32`` is loaded only when a window is bound.
"""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import c_long, wintypes
from typing import Any, ClassVar

from loguru import logger

# cspell:ignore NOMOVE NOSIZE WINDOWPOS
# cspell:ignore ERASEBKGND WINDOWPOSCHANGED STYLECHANGING STYLECHANGED SETICON NCPAINT
# cspell:ignore THEMECHANGED DWMCOMPOSITIONCHANGED DWMNCRENDERINGCHANGED
# cspell:ignore GWLP WINDOWPOSCHANGING NCACTIVATE NCUAHDRAWCAPTION NCUAHDRAWFRAME wndproc


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


def _callback_type(result: Any, *args: Any) -> Any:  # noqa: ANN401
    """Return the type of a function Windows calls back, from its result and argument types."""
    return ctypes.WINFUNCTYPE(result, *args)  # ty: ignore[unresolved-attribute]


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

    enum_windows_proc = _callback_type(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
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


# The messages whose default handling paints the desktop's own caption straight onto
# the window, over an app that draws its own title bar in the client area.
WM_NCPAINT = 0x0085
WM_NCACTIVATE = 0x0086
WM_NCUAHDRAWCAPTION = 0x00AE  # undocumented; sent by the theme code
WM_NCUAHDRAWFRAME = 0x00AF  # undocumented; sent by the theme code
# As WM_NCACTIVATE's lParam: change the active state, repaint nothing.
NO_FRAME_REPAINT = -1
_GWLP_WNDPROC = -4

# Sent before a window is moved or sized, with the WINDOWPOS it is about to take.
WM_WINDOWPOSCHANGING = 0x0046
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
# A rectangle is held for no longer than this, whoever forgets to let it go.
_HELD_RECT_SECONDS = 2.0

# The messages that change or paint a window's frame, logged for a window held
# through a fullscreen exit: what could paint the desktop's caption during one.
_FRAME_MESSAGE_NAMES = {
    0x000C: "WM_SETTEXT",
    0x000F: "WM_PAINT",
    0x0014: "WM_ERASEBKGND",
    0x0046: "WM_WINDOWPOSCHANGING",
    0x0047: "WM_WINDOWPOSCHANGED",
    0x007C: "WM_STYLECHANGING",
    0x007D: "WM_STYLECHANGED",
    0x0080: "WM_SETICON",
    0x0083: "WM_NCCALCSIZE",
    0x0085: "WM_NCPAINT",
    0x0086: "WM_NCACTIVATE",
    0x00AE: "WM_NCUAHDRAWCAPTION",
    0x00AF: "WM_NCUAHDRAWFRAME",
    0x031A: "WM_THEMECHANGED",
    0x031E: "WM_DWMCOMPOSITIONCHANGED",
    0x031F: "WM_DWMNCRENDERINGCHANGED",
}
_MAX_FRAME_MESSAGES_LOGGED = 200


class WINDOWPOS(ctypes.Structure):
    """A Win32 ``WINDOWPOS``: where a window is about to be put."""

    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("hwnd", wintypes.HWND),
        ("hwndInsertAfter", wintypes.HWND),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("cx", ctypes.c_int),
        ("cy", ctypes.c_int),
        ("flags", wintypes.UINT),
    ]


def put_at_held_rect(window_pos: WINDOWPOS, held: tuple[int, int, int, int]) -> None:
    """Change where a window is about to be put to the rectangle held for it.

    Only what the move changes is replaced: a move that keeps the size keeps it,
    and one that keeps the position keeps that.

    Args:
        window_pos: The ``WINDOWPOS`` of a ``WM_WINDOWPOSCHANGING``, changed in place.
        held: The rectangle to put the window at: left, top, width, height.

    """
    left, top, width, height = held
    if not window_pos.flags & SWP_NOMOVE:
        window_pos.x, window_pos.y = left, top
    if not window_pos.flags & SWP_NOSIZE:
        window_pos.cx, window_pos.cy = width, height


def guarded_frame_message(msg: int, lparam: int) -> int | None:
    """Say what becomes of a window message, so the desktop never paints its caption.

    A window with a custom title bar keeps its caption style, with a client area
    that covers it. On losing or gaining the focus, the default handling of
    ``WM_NCACTIVATE`` repaints the caption it thinks is there, in the old unthemed
    look, over the top of the client area; the two theme messages do the same.

    Args:
        msg: The window message.
        lparam: Its lParam.

    Returns:
        The lParam to pass the message on with, or None to answer it here with 0.

    """
    if msg in (WM_NCUAHDRAWCAPTION, WM_NCUAHDRAWFRAME):
        return None
    if msg == WM_NCACTIVATE:
        return NO_FRAME_REPAINT
    return lparam


class CaptionGuard:
    """A window procedure put before a window's own, keeping the desktop's caption off it.

    The window keeps this object's callback as its procedure, so the object must
    live as long as the window: `guard_against_native_caption` sees to that.
    """

    def __init__(self, hwnd: int) -> None:
        """Put the guard before the window procedure of `hwnd`.

        Raises:
            OSError: When ``user32`` cannot be loaded (not Windows), or the window
                would not take the new procedure.

        """
        user32 = ctypes.WinDLL("user32", use_last_error=True)  # ty: ignore[unresolved-attribute]
        lresult = wintypes.LPARAM

        self._call_window_proc: Any = user32.CallWindowProcW
        self._call_window_proc.argtypes = [
            ctypes.c_void_p,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        self._call_window_proc.restype = lresult

        set_window_long_ptr: Any = user32.SetWindowLongPtrW
        set_window_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        set_window_long_ptr.restype = ctypes.c_void_p

        wndproc_type = _callback_type(
            lresult, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        )
        self._wndproc = wndproc_type(self._on_message)  # held: the window calls it

        self.hwnd = hwnd
        self._held_rect: tuple[int, int, int, int] | None = None
        self._held_from = 0.0
        self._held_until = 0.0
        self._frame_messages: list[tuple[int, str]] = []

        self._next_proc: int | None = None
        next_proc = set_window_long_ptr(
            hwnd, _GWLP_WNDPROC, ctypes.cast(self._wndproc, ctypes.c_void_p).value
        )
        if not next_proc:
            msg = f"SetWindowLongPtrW refused window {hex(hwnd)} a new procedure."
            raise OSError(msg)
        self._next_proc = next_proc

    def hold_rect(self, rect: tuple[int, int, int, int]) -> None:
        """Put the window at `rect` (left, top, width, height) wherever it is next sent.

        For a move the app does not make itself and knows to be wrong: SDL's
        fullscreen exit sizes the window for a frame that the custom title bar
        hides. Held until `release_rect`, and never longer than a couple of seconds.
        """
        self._held_rect = rect
        self._held_from = time.monotonic()
        self._held_until = self._held_from + _HELD_RECT_SECONDS
        self._frame_messages = []

    def release_rect(self) -> None:
        """Let the window go where it is sent again, and log the frame messages it had."""
        self._held_rect = None
        if self._frame_messages:
            seen = ", ".join(f"+{ms}ms {name}" for ms, name in self._frame_messages)
            logger.debug(f"Frame messages while the window was held: {seen}.")
            self._frame_messages = []

    def _on_message(self, hwnd: int | None, msg: int, wparam: int, lparam: int) -> int:
        if self._held_rect is not None:
            # Kept, not logged: this runs inside the window procedure.
            name = _FRAME_MESSAGE_NAMES.get(msg)
            if name and len(self._frame_messages) < _MAX_FRAME_MESSAGES_LOGGED:
                elapsed_ms = round((time.monotonic() - self._held_from) * 1000)
                self._frame_messages.append((elapsed_ms, name))
            if msg == WM_NCPAINT and time.monotonic() <= self._held_until:
                # A fullscreen exit puts the caption style back, and for a moment
                # the desktop does not draw this window's frame itself (it sends
                # WM_DWMNCRENDERINGCHANGED when it does again). A WM_NCPAINT
                # passed on in that moment paints the old unthemed caption, a
                # flash of silver along the top of the window.
                return 0

        if msg == WM_WINDOWPOSCHANGING and self._held_rect is not None and lparam:
            if time.monotonic() > self._held_until:
                self._held_rect = None
            else:
                put_at_held_rect(WINDOWPOS.from_address(lparam), self._held_rect)

        passed_on = guarded_frame_message(msg, lparam)
        if passed_on is None:
            return 0
        return self._call_window_proc(self._next_proc, hwnd, msg, wparam, passed_on)


# Each guard's callback is its window's procedure until the window is gone.
_caption_guards: list[CaptionGuard] = []


def guard_against_native_caption(hwnd: int) -> bool:
    """Keep the desktop from painting its caption over the window `hwnd`.

    For a window with a custom title bar. The guard stays for the life of the process.

    Args:
        hwnd: The window handle.

    Returns:
        Whether the guard is in place; a failure is logged, and the window is as it was.

    """
    try:
        _caption_guards.append(CaptionGuard(hwnd))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Could not guard the window against the desktop's caption: {e}")
        return False

    logger.info(f"Guarding window {hex(hwnd)} against the desktop's caption.")
    return True


def hold_window_rect(hwnd: int, rect: tuple[int, int, int, int]) -> bool:
    """Hold the window `hwnd` at `rect` through moves the app does not make itself.

    Args:
        hwnd: The window handle.
        rect: Where to keep the window: left, top, width, height.

    Returns:
        Whether the window has a guard to hold it; without one nothing is held.

    """
    for guard in _caption_guards:
        if guard.hwnd == hwnd:
            guard.hold_rect(rect)
            return True
    return False


def release_window_rect(hwnd: int) -> None:
    """Let the window `hwnd` go where it is sent again. Safe when nothing is held."""
    for guard in _caption_guards:
        if guard.hwnd == hwnd:
            guard.release_rect()
