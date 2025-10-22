from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from kivy.clock import Clock
from kivy.core.window import Window
from loguru import logger

from barks_reader.platform_info import PLATFORM, Platform

MS_WIN_X_ADJ_AFTER_WINDOW_RESTORE = 16
MS_WIN_Y_ADJ_AFTER_WINDOW_RESTORE = 31

_RESTORE_GEOMETRY_TIMEOUT = 0.2 if PLATFORM == Platform.WIN else 0.05
_REBIND_TIMEOUT = 0.3 if PLATFORM == Platform.WIN else 0.05
_SUMMARY_TIMEOUT = 2.5 if PLATFORM == Platform.WIN else 0.05
_RESET_RESTORING_FLAG_TIMEOUT = 1 if PLATFORM == Platform.WIN else 0.05


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
        resize_unbind_func: Callable[[], None],
        resize_rebind_func: Callable[[], None],
        after_first_resize_func: Callable[[], None],
        notify_finished_restore: Callable[[], None] | None = None,
    ) -> None:
        self._resize_unbind_func = resize_unbind_func
        self._resize_rebind_func = resize_rebind_func
        self._notify_finished_restore = notify_finished_restore
        self._after_first_resize_func = after_first_resize_func

        assert not self._resize_unbind_func or self._resize_rebind_func

        self._saved_window_state = WindowState()
        self.is_restoring_window = False

    @staticmethod
    def is_fullscreen_now() -> bool:
        return Window.fullscreen

    @staticmethod
    def get_screen_mode_now() -> str:
        return WindowState.get_current_screen_mode().value

    def clear_state(self) -> None:
        self._saved_window_state = WindowState()

    def save_state_now(self) -> None:
        self._saved_window_state.save_state_now()

        logger.info(
            f"Saved window info before event:"
            f" Window size = {self._saved_window_state.size}, pos = {self._saved_window_state.pos}."
        )

    def restore_saved_state(self) -> None:
        assert self._saved_window_state.size != (0, 0)
        assert self._saved_window_state.pos != (-1, -1)

        logger.info(
            f"At the start of post event Window restore,"
            f" Window.size = {Window.size}, pos = ({Window.left}, {Window.top})."
        )

        self._restore_saved_window()

        self._schedule_summary()

    def _restore_saved_window(self) -> None:
        self.is_restoring_window = True

        # Then, schedule the restoration of size and position after a delay.
        # This gives the OS window manager time to complete the transition.
        def restore_geometry(*_args) -> None:  # noqa: ANN002
            if self._resize_unbind_func:
                # Unbind resize events until everything settles.
                logger.info("Unbinding before starting window restore...")
                self._resize_unbind_func()

            # Set size first.
            self._do_first_resize()

            # Do the in between stuff.
            if self._after_first_resize_func:
                self._after_first_resize_func()

            # Do the rebind events after everything settles.
            self._do_rebind_events()

        Clock.schedule_once(restore_geometry, _RESTORE_GEOMETRY_TIMEOUT)

    def _do_first_resize(self) -> None:
        logger.info("Starting first resize...")
        Window.size = self._saved_window_state.size

        if PLATFORM == Platform.WIN:
            # Force ONLY the size multiple times.
            def do_resize(*_args) -> None:  # noqa: ANN002
                Window.size = self._saved_window_state.size
                logger.info(f"MS Windows: after forced resize, Window.size = {Window.size}.")

            for resize_delay in [0.05, 0.1, 0.15]:
                Clock.schedule_once(do_resize, resize_delay)

    def _do_set_size_and_position(self) -> None:
        if PLATFORM != Platform.WIN:
            Window.left, Window.top = self._saved_window_state.pos
        else:
            self._set_ms_win_size_and_position()

    def _set_ms_win_size_and_position(self) -> None:
        # On MS Windows, setting position triggers resize due to DPI scaling!?
        # So we need to set BOTH position and size together, repeatedly.
        def fix_position_and_size(*_args) -> None:  # noqa: ANN002
            # Set them together atomically.
            Window.left = self._saved_window_state.pos[0] + MS_WIN_X_ADJ_AFTER_WINDOW_RESTORE
            Window.top = self._saved_window_state.pos[1] + MS_WIN_Y_ADJ_AFTER_WINDOW_RESTORE
            # Immediately fix size after position change.
            Window.size = self._saved_window_state.size
            logger.info(
                f"MS Windows: after forced pos and resize, Window.size = {Window.size},"
                f" pos = ({Window.left}, {Window.top})."
            )

        # Do it multiple times to override Windows' attempts to resize.
        for fix_pos_delay in [0.0, 0.05, 0.1, 0.15]:
            Clock.schedule_once(fix_position_and_size, fix_pos_delay)

    def _do_rebind_events(self) -> None:
        def rebind_events(*_args) -> None:  # noqa: ANN002
            logger.info("Rebinding after post event window restore...")

            self._do_set_size_and_position()

            if self._resize_rebind_func:
                self._resize_rebind_func()

            self._do_schedule_restoring_flag_reset()

            logger.info(
                f"After rebinding, Window size = {Window.size},"
                f" pos = ({Window.left}, {Window.top})."
            )

        Clock.schedule_once(rebind_events, _REBIND_TIMEOUT)

    def _do_schedule_restoring_flag_reset(self) -> None:
        def reset_flag(*_args) -> None:  # noqa: ANN002
            self.is_restoring_window = False

            self._schedule_summary()

        # Keep the flag True a bit longer to block the resize events from position changes.
        Clock.schedule_once(reset_flag, _RESET_RESTORING_FLAG_TIMEOUT)

    def _schedule_summary(self) -> None:
        def summary(*_args) -> None:  # noqa: ANN002
            log_func = (
                logger.info
                if self._saved_window_state.is_saved_state_same_as_current()
                else logger.warning
            )

            log_func(
                f"Final setting:"
                f" Window.size = {Window.size}, pos = ({Window.left}, {Window.top});"
                f" Pre-event size = {self._saved_window_state.size},"
                f" pos = {self._saved_window_state.pos}."
            )

            if self._notify_finished_restore:
                self._notify_finished_restore()

        Clock.schedule_once(summary, _SUMMARY_TIMEOUT)
