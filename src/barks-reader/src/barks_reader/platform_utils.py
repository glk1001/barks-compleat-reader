import ctypes
import os
from collections.abc import Callable
from ctypes import c_long, wintypes
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from kivy.clock import Clock
from kivy.core.window import Window
from loguru import logger

from barks_reader.platform_info import PLATFORM, Platform

# Small timeout for non-Windows platforms to let the window system settle.
_RESTORE_GEOMETRY_TIMEOUT = 0.05


class FullscreenEnum(Enum):
    FULLSCREEN = "fullscreen"
    WINDOWED = "windowed"


@dataclass
class WindowState:
    screen: FullscreenEnum = FullscreenEnum.WINDOWED
    size: tuple[int, int] = (0, 0)
    pos: tuple[int, int] = (-1, -1)

    def save_state_now(self) -> None:
        self.screen = FullscreenEnum.FULLSCREEN if Window.fullscreen else FullscreenEnum.WINDOWED
        self.size = Window.size
        self.pos = (Window.left, Window.top)

    def is_saved_state_same_as_current(self) -> bool:
        return Window.size == self.size and (Window.left, Window.top) == self.pos

    @staticmethod
    def get_current_screen_mode() -> FullscreenEnum:
        return FullscreenEnum.FULLSCREEN if Window.fullscreen else FullscreenEnum.WINDOWED


class WindowManager:
    def __init__(
        self,
        client: str,
        on_goto_windowed_mode_first_resize_func: Callable[[], None],
        on_finished_goto_windowed_mode: Callable[[], None],
        on_finished_goto_fullscreen_mode: Callable[[], None],
    ) -> None:
        self._client = client
        self._on_goto_windowed_mode_first_resize = on_goto_windowed_mode_first_resize_func
        self._on_finished_goto_windowed_mode = on_finished_goto_windowed_mode
        self._on_finished_goto_fullscreen_mode = on_finished_goto_fullscreen_mode

        assert self._on_goto_windowed_mode_first_resize is not None
        assert self._on_finished_goto_windowed_mode is not None
        assert self._on_finished_goto_fullscreen_mode is not None

        self._saved_window_state = WindowState()
        self._win32_hwnd = None

        if PLATFORM == Platform.WIN:
            self._init_win32()

    @staticmethod
    def is_fullscreen_now() -> bool:
        return Window.fullscreen

    @staticmethod
    def get_screen_mode_now() -> str:
        return WindowState.get_current_screen_mode().value

    def clear_state(self) -> None:
        self._saved_window_state = WindowState()

    def save_state_now(self) -> None:
        # On Windows with Win32, save the actual window rectangle (including decorations).
        # On other platforms, use Kivy's reported values.
        if PLATFORM == Platform.WIN and self._win32_hwnd:
            self._save_state_win32()
        else:
            self._saved_window_state.save_state_now()

        logger.info(
            f"{self._client}: Saved window state: size = {self._saved_window_state.size}, "
            f"pos = {self._saved_window_state.pos}"
        )

    def goto_fullscreen_mode(self) -> None:
        if self.is_fullscreen_now():
            self._on_finished_goto_fullscreen_mode()
            return

        self.save_state_now()

        def do_fullscreen() -> None:
            Window.fullscreen = "auto"  # Use 'auto' for best platform behavior
            Clock.schedule_once(lambda _dt: self._on_finished_goto_fullscreen_mode(), 0)

        Clock.schedule_once(lambda _dt: do_fullscreen(), 0)

    def goto_windowed_mode(self) -> None:
        if not self.is_fullscreen_now():
            self._on_finished_goto_windowed_mode()
            return

        def do_windowed() -> None:
            Window.borderless = False  # safest thing to do for MS Windows
            Window.fullscreen = False
            Clock.schedule_once(lambda _dt: self.restore_saved_size_and_position(), 0)

        Clock.schedule_once(lambda _dt: do_windowed(), 0)

    def restore_saved_size_and_position(self) -> None:
        assert self._saved_window_state.size != (0, 0)
        assert self._saved_window_state.pos != (-1, -1)

        logger.info(
            f"{self._client}: Restoring window: target size = {self._saved_window_state.size}, "
            f"pos = {self._saved_window_state.pos}"
        )
        logger.info(
            f"{self._client}: At the start of restoring window state,"
            f" Window.size = {Window.size}, pos = ({Window.left}, {Window.top})."
        )

        if PLATFORM == Platform.WIN and self._win32_hwnd:
            self._restore_window_win32()
        else:
            self._restore_window_kivy()

    def _restore_window_kivy(self) -> None:
        """Restore window using Kivy API - simple for non-Windows platforms."""

        def restore(*_args) -> None:  # noqa: ANN002
            Window.size = self._saved_window_state.size
            Window.left, Window.top = self._saved_window_state.pos

            if self._on_goto_windowed_mode_first_resize:
                self._on_goto_windowed_mode_first_resize()

            self._finish_restore()

        Clock.schedule_once(restore, _RESTORE_GEOMETRY_TIMEOUT)

    def _finish_restore(self) -> None:
        """Log final state and call completion callback."""
        log_func = (
            logger.info
            if self._saved_window_state.is_saved_state_same_as_current()
            else logger.warning
        )

        log_func(
            f"{self._client}: Window restore complete: size = {Window.size},"
            f" pos = ({Window.left}, {Window.top}); "
            f"Target was size = {self._saved_window_state.size},"
            f" pos = {self._saved_window_state.pos}"
        )

        Clock.schedule_once(lambda _dt: self._on_finished_goto_windowed_mode(), 0)

    # noinspection PyPep8Naming,PyUnresolvedReferences
    def _init_win32(self) -> None:
        """Initialize Win32 handles for direct window manipulation."""
        try:
            # Define RECT structure
            class RECT(ctypes.Structure):
                _fields_: ClassVar[list[tuple[str, type[c_long]]]] = [
                    ("left", wintypes.LONG),
                    ("top", wintypes.LONG),
                    ("right", wintypes.LONG),
                    ("bottom", wintypes.LONG),
                ]

            self.RECT = RECT

            found_hwnd = ctypes.windll.user32.GetActiveWindow()  # ty: ignore[unresolved-attribute]
            if found_hwnd:
                logger.info(f"Found hwnd using GetActiveWindow: {hex(found_hwnd)}")
            else:
                found_hwnd = self._find_win32_hwnd_by_enum_windows()

            if not found_hwnd:
                logger.warning("Could not get Win32 handle for Kivy window.")
                return

            self._win32_hwnd = found_hwnd

            # Load a fresh instance of user32.dll to avoid conflicts with Kivy's Win32 calls,
            user32 = ctypes.WinDLL("user32", use_last_error=True)  # ty: ignore[unresolved-attribute]

            # Set up Win32 functions with proper type signatures
            self._MoveWindow = user32.MoveWindow
            self._MoveWindow.argtypes = [
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.BOOL,
            ]
            self._MoveWindow.restype = wintypes.BOOL

            self._GetWindowRect = user32.GetWindowRect
            self._GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
            self._GetWindowRect.restype = wintypes.BOOL

            self._GetClientRect = user32.GetClientRect
            self._GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
            self._GetClientRect.restype = wintypes.BOOL

            logger.info(f"Win32 window handle initialized: {hex(self._win32_hwnd)}.")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Could not initialize Win32 handles: {e}")
            self._win32_hwnd = None

    # noinspection PyPep8Naming,PyUnresolvedReferences
    @staticmethod
    def _find_win32_hwnd_by_enum_windows() -> Any:  # noqa: ANN401
        # Find our window by enumerating all windows and matching process ID.
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
                    # Check if it's an SDL window (Kivy uses SDL2)
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

    def _save_state_win32(self) -> None:
        """Save window state using Win32 to get accurate window rectangle."""
        try:
            window_rect = self.RECT()
            client_rect = self.RECT()
            self._GetWindowRect(self._win32_hwnd, window_rect)
            self._GetClientRect(self._win32_hwnd, client_rect)

            self._saved_window_state.screen = (
                FullscreenEnum.FULLSCREEN if Window.fullscreen else FullscreenEnum.WINDOWED
            )
            self._saved_window_state.pos = (window_rect.left, window_rect.top)
            self._saved_window_state.size = (
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
            self._saved_window_state.save_state_now()

    def _restore_window_win32(self) -> None:
        """Restore window using direct Win32 calls - atomic and reliable."""

        def restore(*_args) -> None:  # noqa: ANN002
            # Single atomic Win32 call to set position and size.
            self._win32_set_window_rect(
                self._saved_window_state.pos[0],
                self._saved_window_state.pos[1],
                self._saved_window_state.size[0],
                self._saved_window_state.size[1],
            )

            # Let Kivy sync its internal state
            def sync_and_finish(*_args) -> None:  # noqa: ANN002
                # Trigger Kivy to update its internal values from the actual window
                _ = Window.size  # Read to sync

                if self._on_goto_windowed_mode_first_resize:
                    self._on_goto_windowed_mode_first_resize()

                self._finish_restore()

            Clock.schedule_once(sync_and_finish, 0)

        Clock.schedule_once(restore, _RESTORE_GEOMETRY_TIMEOUT)

    def _win32_set_window_rect(self, x: int, y: int, width: int, height: int) -> None:
        """Set window position and size using Win32 MoveWindow API."""
        if not self._win32_hwnd:
            return

        try:
            result = self._MoveWindow(self._win32_hwnd, x, y, width, height, True)  # noqa: FBT003

            # Verify the operation succeeded.
            actual_rect = self.RECT()
            self._GetWindowRect(self._win32_hwnd, actual_rect)

            log_func = (
                logger.info
                if self._saved_window_state.is_saved_state_same_as_current()
                else logger.warning
            )

            log_func(
                f"Win32: Requested size = ({width}, {height}); "
                f" Actual size = ({(actual_rect.right - actual_rect.left)},"
                f" {(actual_rect.bottom - actual_rect.top)}); "
                f" Requested pos = ({x}, {y});"
                f" Actual pos = ({actual_rect.left}, {actual_rect.top}), "
                f"Result = {result}."
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Win32 MoveWindow failed: {e}")
