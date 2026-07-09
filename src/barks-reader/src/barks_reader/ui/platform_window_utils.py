from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol

from kivy.clock import Clock
from kivy.core.window import Window
from loguru import logger

from barks_reader.core.platform_info import PLATFORM, Platform
from barks_reader.core.screen_metrics import SCREEN_METRICS

if TYPE_CHECKING:
    from collections.abc import Callable

# Small timeout for non-Windows platforms to let the window system settle.
_RESTORE_GEOMETRY_TIMEOUT = 0.05


class FullscreenEnum(Enum):
    FULLSCREEN = "fullscreen"
    WINDOWED = "windowed"


@dataclass(slots=True)
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

    def is_unsaved(self) -> bool:
        """Return True while no geometry has been captured (still the defaults).

        ``goto_fullscreen_mode`` skips its save when the window is *already*
        fullscreen (e.g. at app start), so a later windowed restore can be
        reached with nothing to restore. Restoring the sentinel would apply a
        nonsense size/position, so the restore guards on this.
        """
        return self.size == (0, 0) or self.pos == (-1, -1)

    @staticmethod
    def get_current_screen_mode() -> FullscreenEnum:
        return FullscreenEnum.FULLSCREEN if Window.fullscreen else FullscreenEnum.WINDOWED


class WindowBackend(Protocol):
    """Platform-specific save/restore for the application window."""

    def save_state(self, state: WindowState) -> None:
        """Populate ``state`` with the current window geometry."""
        ...

    def schedule_restore(
        self,
        state: WindowState,
        on_first_resize: Callable[[], None],
        on_done: Callable[[], None],
    ) -> None:
        """Schedule a restore of the window to ``state``'s saved geometry.

        ``on_first_resize`` is invoked once the resize has been issued (used by callers
        to apply size hints), and ``on_done`` is invoked once the restore has settled.
        """
        ...


class KivyWindowBackend:
    """Default backend that uses Kivy's ``Window`` properties.

    Used on Linux/Mac and as a fallback when Win32 initialization fails.
    """

    @staticmethod
    def save_state(state: WindowState) -> None:
        state.save_state_now()

    @staticmethod
    def schedule_restore(
        state: WindowState,
        on_first_resize: Callable[[], None],
        on_done: Callable[[], None],
    ) -> None:
        def restore(*_args) -> None:  # noqa: ANN002
            Window.size = state.size
            Window.left, Window.top = state.pos
            on_first_resize()
            on_done()

        Clock.schedule_once(restore, _RESTORE_GEOMETRY_TIMEOUT)


def _create_window_backend() -> WindowBackend:
    """Return the best available backend for the current platform."""
    if PLATFORM == Platform.WIN:
        # Lazy import to keep the Win32 module out of import graphs on other platforms.
        from .platform_window_win32 import Win32WindowBackend  # noqa: PLC0415

        win32_backend = Win32WindowBackend()
        if win32_backend.is_available():
            return win32_backend
        logger.warning("Win32 backend unavailable; falling back to Kivy backend.")
    return KivyWindowBackend()


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
        self._backend: WindowBackend = _create_window_backend()

    @staticmethod
    def is_fullscreen_now() -> bool:
        return Window.fullscreen

    @staticmethod
    def get_screen_mode_now() -> str:
        return WindowState.get_current_screen_mode().value

    def clear_state(self) -> None:
        self._saved_window_state = WindowState()

    def save_state_now(self) -> None:
        self._backend.save_state(self._saved_window_state)
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
        state = self._saved_window_state
        if state.is_unsaved():
            # Nothing was captured before going fullscreen (the app started
            # already fullscreen, so goto_fullscreen_mode's save was skipped).
            # Restoring the sentinel would move the window to a nonsense
            # size/position, so leave the current geometry untouched and just
            # finish the windowed transition: apply the windowed size hints and
            # fire the completion callback, as the settled restore path does.
            logger.warning(
                f"{self._client}: No saved window state to restore "
                f"(size = {state.size}, pos = {state.pos}); leaving current geometry."
            )
            self._on_goto_windowed_mode_first_resize()
            Clock.schedule_once(lambda _dt: self._on_finished_goto_windowed_mode(), 0)
            return

        logger.info(
            f"{self._client}: Restoring window: target size = {state.size}, pos = {state.pos}"
        )
        logger.info(
            f"{self._client}: At the start of restoring window state,"
            f" Window.size = {Window.size}, pos = ({Window.left}, {Window.top})."
        )

        self._backend.schedule_restore(
            state,
            self._on_goto_windowed_mode_first_resize,
            self._finish_restore,
        )

    def _finish_restore(self) -> None:
        """Log final state and call the windowed-mode completion callback."""
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


def log_screen_metrics() -> None:
    from kivy.metrics import cm, dp, inch, sp  # noqa: PLC0415

    logger.info("--- Detailed Monitor Metrics ---")

    for info in SCREEN_METRICS.SCREEN_INFO:
        logger.info(
            f"Display {info.display}: {info.width_pixels} x {info.height_pixels} pixels"
            f" at ({info.monitor_x}, {info.monitor_y})."
        )
        logger.info(
            f"  -> Physical Size: {info.width_mm}mm x {info.height_mm}mm"
            f" ({info.width_in:.2f}in x {info.height_in:.2f}in)."
        )
        logger.info(f"  -> Calculated DPI: {info.dpi:.2f}.")
        logger.info(f"  -> Primary: {info.is_primary}.")

    logger.info(f"1 cm = {cm(1):.1f} pixels.")
    logger.info(f"1 in = {inch(1):.1f} pixels.")
    logger.info(f"100 dp = {dp(100):.1f} pixels.")
    logger.info(f"100 sp = {sp(100):.1f} pixels.")

    logger.info("--------------------------------")


if __name__ == "__main__":
    log_screen_metrics()
