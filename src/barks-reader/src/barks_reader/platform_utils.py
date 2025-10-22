from collections.abc import Callable

from kivy.clock import Clock
from kivy.core.window import Window
from loguru import logger

from barks_reader.platform_info import PLATFORM, Platform

MS_WIN_X_ADJ_AFTER_WINDOW_RESTORE = 16
MS_WIN_Y_ADJ_AFTER_WINDOW_RESTORE = 31


class WindowRestorer:
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

        self.is_restoring_window = False
        self._pre_event_size: tuple[int, int] = 0, 0
        self._pre_event_pos: tuple[int, int] = -1, -1

    def set_pre_event_dimensions(self, size: tuple[int, int], pos: tuple[int, int]) -> None:
        self._pre_event_size = size
        self._pre_event_pos = pos

        logger.info(
            f"Saved window info before event:"
            f" Window size = {self._pre_event_size}, pos = {self._pre_event_pos}."
        )

    def post_event_restore(self) -> None:
        assert self._pre_event_size != (0, 0)
        assert self._pre_event_pos != (-1, -1)

        logger.info(
            f"At the start of post event Window restore,"
            f" Window.size = {Window.size}, pos = ({Window.left}, {Window.top})."
        )

        self._restore_pre_event_window()

        self._schedule_summary()

    def _restore_pre_event_window(self) -> None:
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

        Clock.schedule_once(restore_geometry, 0.2)

    def _do_first_resize(self) -> None:
        logger.info("Starting first resize...")
        Window.size = self._pre_event_size

        if PLATFORM == Platform.WIN:
            # Force ONLY the size multiple times.
            def do_resize(*_args) -> None:  # noqa: ANN002
                Window.size = self._pre_event_size
                logger.info(f"MS Windows: after forced resize, Window.size = {Window.size}.")

            for resize_delay in [0.05, 0.1, 0.15]:
                Clock.schedule_once(do_resize, resize_delay)

    def _do_set_size_and_position(self) -> None:
        if PLATFORM != Platform.WIN:
            Window.left, Window.top = self._pre_event_pos
        else:
            self._set_win11_size_and_position()

    def _set_win11_size_and_position(self) -> None:
        # On MS Windows, setting position triggers resize due to DPI scaling!?
        # So we need to set BOTH position and size together, repeatedly.
        def fix_position_and_size(*_args) -> None:  # noqa: ANN002
            # Set them together atomically.
            Window.left = self._pre_event_pos[0] + MS_WIN_X_ADJ_AFTER_WINDOW_RESTORE
            Window.top = self._pre_event_pos[1] + MS_WIN_Y_ADJ_AFTER_WINDOW_RESTORE
            # Immediately fix size after position change.
            Window.size = self._pre_event_size
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

        Clock.schedule_once(rebind_events, 0.3)

    def _do_schedule_restoring_flag_reset(self) -> None:
        # Keep the flag True a bit longer to block the resize events from position changes.
        Clock.schedule_once(lambda _dt: setattr(self, "is_restoring_window", False), 1)

    def _schedule_summary(self) -> None:
        def summary(*_args) -> None:  # noqa: ANN002
            logger.info(
                f"Final setting:"
                f" Window.size = {Window.size}, pos = ({Window.left}, {Window.top});"
                f" Pre-event size = {self._pre_event_size},"
                f" pos = {self._pre_event_pos}."
            )

            if self._notify_finished_restore:
                self._notify_finished_restore()

        Clock.schedule_once(summary, 2.5)
