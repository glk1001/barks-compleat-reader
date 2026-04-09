"""Win32-specific window save/restore backend.

Necessary on Windows because Kivy/SDL2's window-state APIs leave the window
collapsed at its hit-test minimum after fullscreen exit. This backend uses
``MoveWindow`` + ``GetWindowRect`` for atomic, reliable geometry restoration,
with an ``SDL_SetWindowSize``-based recovery path for the cases where
``MoveWindow`` silently no-ops.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import c_long, wintypes
from typing import TYPE_CHECKING, Any, ClassVar

from kivy.clock import Clock
from kivy.core.window import Window
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from .platform_window_utils import WindowState

# Windows needs longer than other platforms: SDL fullscreen-exit fires a resize
# storm that can starve the Kivy Clock and leave the window at its hit-test
# minimum before our scheduled restore runs.
_RESTORE_GEOMETRY_TIMEOUT_WIN = 0.25


class _RECT(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, type[c_long]]]] = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class Win32WindowBackend:
    """Save/restore the window via direct Win32 calls."""

    def __init__(self) -> None:
        self._hwnd: int | None = None
        self._move_window: Any = None
        self._get_window_rect: Any = None
        self._get_client_rect: Any = None
        self._init()

    def is_available(self) -> bool:
        """Return True if Win32 initialization succeeded and the backend can be used."""
        return self._hwnd is not None

    def save_state(self, state: WindowState) -> None:
        """Populate ``state`` from the current Win32 window rectangle."""
        # Local import to avoid a module-level cycle with platform_window_utils.
        from .platform_window_utils import FullscreenEnum  # noqa: PLC0415

        try:
            window_rect = _RECT()
            client_rect = _RECT()
            self._get_window_rect(self._hwnd, window_rect)
            self._get_client_rect(self._hwnd, client_rect)

            state.screen = (
                FullscreenEnum.FULLSCREEN if Window.fullscreen else FullscreenEnum.WINDOWED
            )
            state.pos = (window_rect.left, window_rect.top)
            state.size = (
                window_rect.right - window_rect.left,
                window_rect.bottom - window_rect.top,
            )

            logger.debug(
                f"Win32: Saved window rect size = ({window_rect.right - window_rect.left},"
                f" {window_rect.bottom - window_rect.top}),"
                f" pos = ({window_rect.left}, {window_rect.top}),"
                f" client size = ({client_rect.right}, {client_rect.bottom})."
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Win32 save state failed, falling back to Kivy: {e}")
            state.save_state_now()

    def schedule_restore(
        self,
        state: WindowState,
        on_first_resize: Callable[[], None],
        on_done: Callable[[], None],
    ) -> None:
        """Schedule a restore of the window to ``state``'s saved size and position."""

        def restore(*_args) -> None:  # noqa: ANN002
            # Single atomic Win32 call to set position and size.
            self._set_window_rect(state.pos[0], state.pos[1], state.size[0], state.size[1])

            # Let Kivy sync its internal state, then fire the callbacks.
            def sync_and_finish(*_args) -> None:  # noqa: ANN002
                _ = Window.size  # Read to sync Kivy's internal values.
                on_first_resize()
                on_done()

            Clock.schedule_once(sync_and_finish, 0)

        Clock.schedule_once(restore, _RESTORE_GEOMETRY_TIMEOUT_WIN)

    # --- Private helpers ---

    def _init(self) -> None:
        """Initialize Win32 handles for direct window manipulation."""
        try:
            found_hwnd = ctypes.windll.user32.GetActiveWindow()  # ty: ignore[unresolved-attribute]
            if found_hwnd:
                logger.info(f"Found hwnd using GetActiveWindow: {hex(found_hwnd)}")
            else:
                found_hwnd = self._find_hwnd_by_enum_windows()

            if not found_hwnd:
                logger.warning("Could not get Win32 handle for Kivy window.")
                return

            self._hwnd = found_hwnd

            # Load a fresh instance of user32.dll to avoid conflicts with Kivy's Win32 calls.
            user32 = ctypes.WinDLL("user32", use_last_error=True)  # ty: ignore[unresolved-attribute]

            # Set up Win32 functions with proper type signatures.
            self._move_window = user32.MoveWindow
            self._move_window.argtypes = [
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.BOOL,
            ]
            self._move_window.restype = wintypes.BOOL

            self._get_window_rect = user32.GetWindowRect
            self._get_window_rect.argtypes = [wintypes.HWND, ctypes.POINTER(_RECT)]
            self._get_window_rect.restype = wintypes.BOOL

            self._get_client_rect = user32.GetClientRect
            self._get_client_rect.argtypes = [wintypes.HWND, ctypes.POINTER(_RECT)]
            self._get_client_rect.restype = wintypes.BOOL

            logger.info(f"Win32 window handle initialized: {hex(self._hwnd)}.")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Could not initialize Win32 handles: {e}")
            self._hwnd = None

    @staticmethod
    def _find_hwnd_by_enum_windows() -> Any:  # noqa: ANN401
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

    def _set_window_rect(self, x: int, y: int, width: int, height: int) -> None:
        """Set window position and size using the Win32 ``MoveWindow`` API.

        On Windows, SDL2's fullscreen-exit path can fire a storm of resize events that
        starve the Kivy Clock and leave the window collapsed at its hit-test minimum
        (e.g. ``(136, 45)`` -- the action bar's minimum content size) before our scheduled
        ``MoveWindow`` even runs. In that state ``MoveWindow`` can return success but be
        a no-op.

        Recovery strategy when the post-``MoveWindow`` rect doesn't match the request:
          1. Set ``Window.size`` / ``Window.left`` / ``Window.top`` via Kivy. This goes
             through ``SDL_SetWindowSize`` and bypasses whatever sticky Win32 state was
             blocking ``MoveWindow``.
          2. Schedule a deferred ``MoveWindow`` retry on the next frame so the Win32
             outer rect matches the saved state once SDL has settled.
        """
        if not self._hwnd:
            return

        try:
            result = self._move_window(self._hwnd, x, y, width, height, True)  # noqa: FBT003

            # Verify the operation succeeded.
            actual_rect = _RECT()
            self._get_window_rect(self._hwnd, actual_rect)
            actual_w = actual_rect.right - actual_rect.left
            actual_h = actual_rect.bottom - actual_rect.top

            mismatch = (actual_w, actual_h) != (width, height)
            log_func = logger.warning if mismatch else logger.info

            log_func(
                f"Win32: Requested size = ({width}, {height}); "
                f" Actual size = ({actual_w}, {actual_h}); "
                f" Requested pos = ({x}, {y});"
                f" Actual pos = ({actual_rect.left}, {actual_rect.top}), "
                f"Result = {result}."
            )

            if mismatch:
                self._recover_from_failed_move(x, y, width, height)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Win32 MoveWindow failed: {e}")

    def _recover_from_failed_move(self, x: int, y: int, width: int, height: int) -> None:
        """Fallback when ``MoveWindow`` returns success but the window stays at the wrong size.

        Uses Kivy's Window properties (which go through ``SDL_SetWindowSize``) to break
        the sticky state, then schedules a deferred ``MoveWindow`` retry to confirm the
        outer Win32 rect matches the saved state.
        """
        logger.warning(
            f"Win32 MoveWindow no-op detected; recovering via Window.size = ({width}, {height})."
        )
        try:
            Window.size = (width, height)
            Window.left = x
            Window.top = y
        except Exception as e:  # noqa: BLE001
            logger.error(f"Window.size recovery failed: {e}")

        def retry(_dt: float) -> None:
            if not self._hwnd:
                return
            self._move_window(self._hwnd, x, y, width, height, True)  # noqa: FBT003
            actual_rect = _RECT()
            self._get_window_rect(self._hwnd, actual_rect)
            logger.info(
                f"Win32 retry: Requested size = ({width}, {height}); "
                f" Actual size = ({actual_rect.right - actual_rect.left},"
                f" {actual_rect.bottom - actual_rect.top}); "
                f" Actual pos = ({actual_rect.left}, {actual_rect.top})."
            )

        Clock.schedule_once(retry, 0)
