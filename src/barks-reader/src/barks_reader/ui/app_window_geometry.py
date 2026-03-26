from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kivy.clock import Clock
from kivy.core.window import Window, WindowBase
from loguru import logger

from barks_reader.core.reader_utils import COMIC_PAGE_ASPECT_RATIO, get_win_width_from_height
from barks_reader.core.screen_metrics import (
    SCREEN_METRICS,
    ScreenInfo,
    calculate_fitted_window_height,
    get_best_window_height_fit,
)
from barks_reader.ui.reader_ui_classes import ACTION_BAR_SIZE_Y

if TYPE_CHECKING:
    from collections.abc import Callable

MOVE_SETTLE_DELAY = 4.0
MIN_WINDOW_WIDTH = 900
RESIZE_CORRECTION_DELAY = 0.1
ROTATION_POLL_INTERVAL = 2.0
ROTATION_FIT_FRACTION = 0.9


class AppWindowGeometryHelper:
    """Manages window geometry: monitor changes, aspect ratio, rotation, and resize guarding."""

    def __init__(self) -> None:
        initial_monitor = SCREEN_METRICS.get_monitor_for_pos(Window.left, Window.top)
        assert initial_monitor is not None
        self._current_monitor: ScreenInfo = initial_monitor
        self._resize_event: Any = None
        self._resize_requested_size = 0, 0
        self._window_ready = False
        self._correction_event: Any = None
        self._suppress_correction = False
        self._suppress_correction_event: Any = None
        self._rotation_poll_event: Any = None

        self._update_fonts: Callable[[int], None] | None = None

    def set_main_screen_callbacks(self, update_fonts: Callable[[int], None]) -> None:
        """Set callbacks that require the main screen to be built first.

        Args:
            update_fonts: Callback to update font sizes for a given window height.

        """
        self._update_fonts = update_fonts

    def set_window_ready(self) -> None:
        """Mark the window as ready to accept resize corrections."""
        self._window_ready = True

    # --- Window event handlers (bound by the app) ---

    def on_window_pos_change(self, _window: WindowBase) -> None:
        """Handle window move events — detect monitor changes and rescale."""
        if Window.fullscreen:
            return

        monitor = SCREEN_METRICS.get_monitor_for_pos(Window.left, Window.top)
        assert monitor is not None
        if monitor.display == self._current_monitor.display:
            return

        old_height = Window.height
        old_max_height = get_best_window_height_fit(self._current_monitor.height_pixels)
        scale_factor = old_height / old_max_height
        logger.debug(
            f"Changed to monitor {monitor.display} from monitor {self._current_monitor.display}:"
            f" old size = {Window.size}, old_max_height = {old_max_height},"
            f" scale_factor = {scale_factor:.2f}."
        )

        self._current_monitor = monitor

        new_max_height = get_best_window_height_fit(monitor.height_pixels)
        new_height = min(round(scale_factor * new_max_height), new_max_height)

        if new_height != old_height:
            new_width = get_win_width_from_height(new_height - ACTION_BAR_SIZE_Y)
            self._schedule_guarded_resize(new_width, new_height)

    # ruff: noqa: ERA001
    def on_window_resize(self, _window: WindowBase, width: int, height: int) -> None:
        """Handle window resize events — enforce aspect ratio and guard against OS overrides."""
        # logger.debug(
        #     f"Main window resize event:"
        #     f" width, height = {width},{height},"
        #     f" Window.fullscreen = {Window.fullscreen},"
        #     f" self._resize_event = {self._resize_event},"
        #     f" self._resize_requested_size = {self._resize_requested_size},"
        # )

        if Window.fullscreen:
            return

        # Monitor-change guard: re-apply our requested size if the OS overrides it, then
        # update fonts. Skip aspect-ratio enforcement entirely while the guard is active —
        # calling _enforce_aspect_ratio during a monitor transition can interfere with the
        # resize sequence and leave widgets at the old monitor's dimensions.
        if self._resize_event:
            if (width, height) != self._resize_requested_size:
                assert self._resize_requested_size != (0, 0)
                Window.size = self._resize_requested_size
                logger.debug(f"Forced reset main window size after resize event: {Window.size}.")
            assert self._update_fonts is not None
            self._update_fonts(Window.height)
            return

        if not self._window_ready:
            return

        # Suppress corrections during/after comic reader close to avoid DPI-scaling
        # feedback loops on Windows where spurious resize events fire during the transition.
        if self._suppress_correction:
            return

        self._enforce_aspect_ratio(width, height)

    def suppress_aspect_ratio_correction(self, duration: float = 2.0) -> None:
        """Temporarily suppress aspect ratio corrections.

        Args:
            duration: How long to suppress, in seconds.

        Call this before a programmatic window resize (e.g., closing the comic reader) to
        prevent the correction from firing on spurious OS resize events and creating a loop.

        """
        if self._suppress_correction_event is not None:
            self._suppress_correction_event.cancel()
        if self._correction_event is not None:
            self._correction_event.cancel()
            self._correction_event = None
        self._suppress_correction = True

        def clear_suppress(_dt: float) -> None:
            self._suppress_correction = False
            self._suppress_correction_event = None

        self._suppress_correction_event = Clock.schedule_once(clear_suppress, duration)

    # --- Rotation polling ---

    def start_rotation_polling(self) -> None:
        """Begin periodic checks for screen rotation."""
        self._rotation_poll_event = Clock.schedule_interval(
            self._check_for_rotation, ROTATION_POLL_INTERVAL
        )

    def stop_polling(self) -> None:
        """Cancel rotation polling."""
        if self._rotation_poll_event:
            self._rotation_poll_event.cancel()
            self._rotation_poll_event = None

    # --- Private helpers ---

    def _enforce_aspect_ratio(self, width: int, height: int) -> None:
        """Enforce a fixed aspect ratio (height drives width) with a minimum width floor.

        Args:
            width: Current window width reported by the resize event.
            height: Current window height reported by the resize event.

        """
        correct_width = get_win_width_from_height(height - ACTION_BAR_SIZE_Y)
        correct_height = height
        if correct_width < MIN_WINDOW_WIDTH:
            min_height = round(MIN_WINDOW_WIDTH * COMIC_PAGE_ASPECT_RATIO) + ACTION_BAR_SIZE_Y
            monitor = SCREEN_METRICS.get_monitor_for_pos(Window.left, Window.top)
            monitor_max_h = get_best_window_height_fit(monitor.height_pixels) if monitor else 0
            if min_height <= monitor_max_h:
                correct_width = MIN_WINDOW_WIDTH
                correct_height = min_height

        if (correct_width, correct_height) != (width, height):
            # User resize: debounce so only one correction fires after the drag settles.
            if self._correction_event:
                self._correction_event.cancel()

            def apply_correction(_dt: float) -> None:
                self._correction_event = None
                Window.size = (correct_width, correct_height)

            self._correction_event = Clock.schedule_once(apply_correction, RESIZE_CORRECTION_DELAY)
            return

        assert self._update_fonts is not None
        self._update_fonts(height)

    def _check_for_rotation(self, _dt: float) -> None:
        """Poll screeninfo for dimension changes indicating rotation."""
        if Window.fullscreen:
            return
        if SCREEN_METRICS.refresh():
            logger.info("Screen rotation detected -- resizing window to fit new dimensions.")
            self._handle_rotation()

    def _handle_rotation(self) -> None:
        """Resize and reposition the window after a screen rotation."""
        monitor = SCREEN_METRICS.get_monitor_for_pos(Window.left, Window.top)
        if monitor is None:
            monitor = SCREEN_METRICS.get_primary_screen_info()

        self._current_monitor = monitor

        new_height = calculate_fitted_window_height(
            screen_width=monitor.width_pixels,
            screen_height=monitor.height_pixels,
            aspect_ratio=COMIC_PAGE_ASPECT_RATIO,
            action_bar_height=ACTION_BAR_SIZE_Y,
            fit_fraction=ROTATION_FIT_FRACTION,
        )
        new_width = get_win_width_from_height(new_height - ACTION_BAR_SIZE_Y)

        center_x = monitor.monitor_x + (monitor.width_pixels - new_width) // 2
        center_y = monitor.monitor_y + (monitor.height_pixels - new_height) // 2

        logger.info(
            f"Rotation resize: ({new_width}, {new_height}) at ({center_x}, {center_y})"
            f" on monitor {monitor.display}"
            f" ({monitor.width_pixels}x{monitor.height_pixels})."
        )

        self._schedule_guarded_resize(new_width, new_height, reposition=(center_x, center_y))

    def _schedule_guarded_resize(
        self,
        new_width: int,
        new_height: int,
        reposition: tuple[int, int] | None = None,
    ) -> None:
        """Schedule a window resize with a guard that prevents the OS from overriding it.

        The OS window manager may fire a resize event at the end of a drag operation using
        the old monitor's size, which would override our programmatic resize. This method
        sets up a guard (``_resize_event`` / ``_resize_requested_size``) that is checked in
        ``on_window_resize`` to re-apply our intended size.

        Args:
            new_width: Target window width.
            new_height: Target window height.
            reposition: Optional (x, y) to also reposition the window.

        """
        self._resize_requested_size = new_width, new_height

        def do_resize(_dt: float) -> None:
            logger.debug(f"Executing guarded resize to ({new_width}, {new_height}).")
            Window.size = (new_width, new_height)
            if reposition is not None:
                Window.left, Window.top = reposition

        def do_reset_resize(_dt: float) -> None:
            logger.debug("Clearing resize guard.")
            self._resize_event = None
            self._resize_requested_size = 0, 0

        Clock.schedule_once(do_resize, 0)
        self._resize_event = Clock.schedule_once(do_reset_resize, MOVE_SETTLE_DELAY)
