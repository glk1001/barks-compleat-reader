from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from kivy.clock import Clock
from kivy.core.window import Window, WindowBase
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.main_layout import MainLayoutMode, choose_main_layout, content_aspect_ratio
from barks_reader.core.reader_utils import get_win_dimensions
from barks_reader.core.screen_metrics import (
    SCREEN_METRICS,
    ScreenInfo,
    calculate_fitted_window_height,
    get_best_window_height_fit,
)
from barks_reader.core.window_minimum import minimum_window_size

if TYPE_CHECKING:
    from collections.abc import Callable

MOVE_SETTLE_DELAY = 4.0
RESIZE_CORRECTION_DELAY = 0.1
ROTATION_POLL_INTERVAL = 2.0
ROTATION_FIT_FRACTION = 0.9


@dataclass(frozen=True, slots=True)
class WindowSizeConstraints:
    """Geometry constants the window helper needs, injected at construction time.

    Decoupling these from module-level imports lets the helper be unit-tested with
    arbitrary values and removes the implicit assumption that the action bar is
    always visible (the previous degenerate-size guard hardcoded the bar height).
    """

    aspect_ratio: float
    """A page's aspect ratio, ``content_height / content_width`` (the comic page's).

    The window's content is a page in the single-page layout and a pair with a gutter
    in the two-page spread: `AppWindowGeometryHelper.content_aspect_ratio` is the one
    the window is held to.
    """

    chrome_height: int
    """Pixels of non-content chrome below the content (e.g. action bar)."""

    min_window_width: int
    """Floor for the window width before the helper falls back to a minimum size."""


class AppWindowGeometryHelper:
    """Manages window geometry: monitor changes, aspect ratio, rotation, and resize guarding.

    It also decides the main screen's layout, single page or two-page spread, from the
    "Main screen layout" setting and the monitor the window is on (core.main_layout):
    at boot, on a monitor change, on a rotation and on a change of the setting. The
    window is held to the layout's shape, and the main screen is told of a change
    through the callback given to `set_main_screen_callbacks`.
    """

    def __init__(self, constraints: WindowSizeConstraints, layout_setting: str) -> None:
        self._constraints = constraints

        # Window.left/top can be off-screen at startup on Windows; fall back to primary.
        initial_monitor = SCREEN_METRICS.get_monitor_for_pos(Window.left, Window.top)
        if initial_monitor is None:
            initial_monitor = SCREEN_METRICS.get_primary_screen_info()
        self._current_monitor: ScreenInfo = initial_monitor
        self._layout_setting = layout_setting
        # The layout main.py sized the window for, decided as main.py did, on the
        # primary screen, and silently: `set_window_ready` decides for the monitor the
        # window is on, logs that, and refits the window when the two differ (a saved
        # position on a second monitor of another shape, 2026-10-30).
        self._layout_mode = self._decide_layout_on(SCREEN_METRICS.get_primary_screen_info())
        self._layout_mode_changed: Callable[[MainLayoutMode], None] | None = None
        self._resize_event: Any = None
        self._resize_requested_size = 0, 0
        self._window_ready = False
        self._correction_event: Any = None
        self._suppress_correction = False
        self._suppress_correction_event: Any = None
        self._rotation_poll_event: Any = None

        self._update_fonts: Callable[[int], None] | None = None

    def set_main_screen_callbacks(
        self,
        update_fonts: Callable[[int], None],
        layout_mode_changed: Callable[[MainLayoutMode], None] | None = None,
    ) -> None:
        """Set callbacks that require the main screen to be built first.

        Args:
            update_fonts: Callback to update font sizes for a given window height.
            layout_mode_changed: Callback for a change of the main screen's layout.

        """
        self._update_fonts = update_fonts
        self._layout_mode_changed = layout_mode_changed

    def set_window_ready(self) -> None:
        """Mark the window as ready to accept resize corrections, and set its minimum size."""
        self._window_ready = True
        self.evaluate_layout("boot")
        self.apply_minimum_size()

    @property
    def current_monitor(self) -> ScreenInfo:
        """The monitor the window is on."""
        return self._current_monitor

    # --- The main screen's layout ---

    @property
    def layout_mode(self) -> MainLayoutMode:
        """The main screen's layout on the monitor the window is on."""
        return self._layout_mode

    @property
    def content_aspect_ratio(self) -> float:
        """The shape (height over width) the window's content is held to in this layout."""
        return content_aspect_ratio(self._layout_mode, self._constraints.aspect_ratio)

    def set_layout_setting(self, setting: str) -> None:
        """Take a new value of the "Main screen layout" setting, and lay the window out for it.

        Args:
            setting: One of `MAIN_SCREEN_LAYOUT_OPTIONS` (core.main_layout).

        """
        self._layout_setting = setting
        if not self._window_ready:
            self._layout_mode = self._decide_layout()  # logged at `set_window_ready`
            return
        self.evaluate_layout("setting")

    def evaluate_layout(self, reason: str, *, refit: bool = True) -> bool:
        """Decide the layout for the monitor the window is on, and log the decision.

        Args:
            reason: Why it is decided now: "boot", "monitor change", "rotation", "setting".
            refit: Resize the window to the new layout's shape when it changes (a caller
                about to resize the window anyway passes False).

        Returns:
            True when the layout changed.

        """
        mode = self._decide_layout()
        monitor = self._current_monitor
        logger.info(
            log_markers.MAIN_LAYOUT_MODE.format(
                mode=mode.value,
                reason=reason,
                screen=f"{monitor.width_pixels}x{monitor.height_pixels}",
            )
        )
        if mode is self._layout_mode:
            return False
        self._layout_mode = mode
        if self._layout_mode_changed is not None:
            self._layout_mode_changed(mode)
        if refit and not Window.fullscreen:
            self._refit_to_layout()
        return True

    def _decide_layout(self) -> MainLayoutMode:
        return self._decide_layout_on(self._current_monitor)

    def _decide_layout_on(self, monitor: ScreenInfo) -> MainLayoutMode:
        return choose_main_layout(
            self._layout_setting,
            monitor.width_pixels,
            monitor.height_pixels,
            self._chrome_in_size_units(),
            self._constraints.aspect_ratio,
        )

    def _refit_to_layout(self) -> None:
        """Give the window the layout's width at its height, centred on its monitor."""
        monitor = self._current_monitor
        chrome = self._chrome_in_size_units()
        height = Window.system_size[1]
        new_width, content_h = get_win_dimensions(
            height - chrome, monitor.width_pixels, self.content_aspect_ratio
        )
        new_width, new_height = self._no_smaller_than_minimum(new_width, content_h + chrome)
        left = monitor.monitor_x + (monitor.width_pixels - new_width) // 2
        logger.info(
            f"Layout refit: ({new_width}, {new_height}) at ({left}, {Window.top})"
            f" on monitor {monitor.display} ({monitor.width_pixels}x{monitor.height_pixels})."
        )
        self._schedule_guarded_resize(new_width, new_height, reposition=(left, Window.top))
        self.apply_minimum_size()  # the layout's; after the guard, as on a move

    def apply_minimum_size(self) -> None:
        """Stop the window being made smaller than the reader is laid out for, on its monitor.

        A 1080p screen's window, or this monitor's largest when it is smaller (see
        `minimum_window_size`); in ``Window.system_size`` units, as SDL takes them.
        """
        monitor = self._current_monitor
        width, height = self._minimum_size()
        _set_window_minimum_size(width, height)
        logger.info(
            log_markers.WINDOW_MINIMUM_SET.format(
                width=width,
                height=height,
                screen=f"{monitor.width_pixels}x{monitor.height_pixels}",
            )
        )

    # --- Window units ---
    #
    # Kivy reads ``Window.size`` (and gives resize events) in pixels, but takes a
    # ``Window.size =`` in ``Window.system_size`` units, the units screeninfo gives the
    # monitors in. They differ on a Retina Mac, two pixels to a point: a correction
    # worked out in pixels and set as points doubled the window, again on each
    # correction after (2026-10-14). So the geometry below is worked out in
    # ``system_size`` units; elsewhere the factor is 1.

    @staticmethod
    def _pixels_per_size_unit() -> float:
        system_width = Window.system_size[0]
        return Window.size[0] / system_width if system_width > 0 else 1.0

    def _in_size_units(self, width: int, height: int) -> tuple[int, int]:
        scale = self._pixels_per_size_unit()
        return round(width / scale), round(height / scale)

    def _chrome_in_size_units(self) -> int:
        return round(self._constraints.chrome_height / self._pixels_per_size_unit())

    def _minimum_size(self) -> tuple[int, int]:
        monitor = self._current_monitor
        return minimum_window_size(
            monitor.width_pixels,
            monitor.height_pixels,
            self._chrome_in_size_units(),
            self.content_aspect_ratio,
        )

    def _no_smaller_than_minimum(self, width: int, height: int) -> tuple[int, int]:
        """Return a size to ask for, raised to the minimum when it is below it.

        SDL would hold the window at the minimum anyway, and the resize guard then
        fought it, forcing the smaller size back on every resize event until it expired.
        """
        min_width, min_height = self._minimum_size()
        if width >= min_width and height >= min_height:
            return width, height
        logger.debug(
            f"Window size ({width}, {height}) raised to the minimum ({min_width}, {min_height})."
        )
        return min_width, min_height

    # --- Window event handlers (bound by the app) ---

    def on_window_pos_change(self, _window: WindowBase) -> None:
        """Handle window move events — detect monitor changes and rescale."""
        if Window.fullscreen:
            return

        # On Windows, on_move can fire with a position that doesn't map to any monitor
        # (e.g. during shutdown or while the OS is repositioning the window). Skip those.
        monitor = SCREEN_METRICS.get_monitor_for_pos(Window.left, Window.top)
        if monitor is None:
            return
        if monitor.display == self._current_monitor.display:
            return

        old_height = Window.system_size[1]
        old_max_height = get_best_window_height_fit(self._current_monitor.height_pixels)
        scale_factor = old_height / old_max_height
        logger.debug(
            f"Changed to monitor {monitor.display} from monitor {self._current_monitor.display}:"
            f" old size = {Window.size}, old_max_height = {old_max_height},"
            f" scale_factor = {scale_factor:.2f}."
        )

        self._current_monitor = monitor
        self.evaluate_layout("monitor change", refit=False)  # the resize below is the refit

        new_max_height = get_best_window_height_fit(monitor.height_pixels)
        new_height = min(round(scale_factor * new_max_height), new_max_height)
        chrome = self._chrome_in_size_units()
        new_width, content_h = get_win_dimensions(
            new_height - chrome, monitor.width_pixels, self.content_aspect_ratio
        )
        new_width, new_height = self._no_smaller_than_minimum(new_width, content_h + chrome)

        if new_height != old_height:
            self._schedule_guarded_resize(new_width, new_height)
        # After the guard is armed: a window the new minimum enlarges gets a resize
        # event, which the guard answers, not the aspect-ratio correction.
        self.apply_minimum_size()

    def on_window_resize(self, _window: WindowBase, width: int, height: int) -> None:
        """Handle window resize events — enforce aspect ratio and guard against OS overrides."""
        # Every event, since a transient size here is what a later correction
        # acts on; they are rare (not per frame), so this is cheap.
        logger.debug(
            f"{log_markers.WINDOW_RESIZED.format(width=width, height=height)}"
            f" Window.fullscreen = {Window.fullscreen},"
            f" guard = {self._resize_requested_size if self._resize_event else None},"
            f" correction suppressed = {self._suppress_correction}."
        )

        if Window.fullscreen:
            return

        # Monitor-change guard: re-apply our requested size if the OS overrides it, then
        # update fonts. Skip aspect-ratio enforcement entirely while the guard is active —
        # calling _enforce_aspect_ratio during a monitor transition can interfere with the
        # resize sequence and leave widgets at the old monitor's dimensions.
        if self._resize_event:
            if self._in_size_units(width, height) != self._resize_requested_size:
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
            width: Current window width reported by the resize event, in pixels.
            height: Current window height reported by the resize event, in pixels.

        """
        chrome = self._chrome_in_size_units()
        min_width = self._constraints.min_window_width

        # Bail out on degenerate transient sizes (e.g. ``(0, 45)`` events that fire during
        # the Windows fullscreen-exit resize storm). Without this guard we would compute
        # a degenerate correction and schedule ``Window.size = (0, 45)``, which Win32 then
        # clamps to its hit-test minimum and the window stays tiny.
        unit_width, unit_height = self._in_size_units(width, height)
        if unit_width <= 0 or unit_height <= chrome:
            return

        monitor = SCREEN_METRICS.get_monitor_for_pos(Window.left, Window.top)
        monitor_w = monitor.width_pixels if monitor else 0
        aspect_ratio = self.content_aspect_ratio
        correct_width, content_h = get_win_dimensions(unit_height - chrome, monitor_w, aspect_ratio)
        correct_height = content_h + chrome
        if correct_width < min_width:
            min_height = round(min_width * aspect_ratio) + chrome
            monitor = SCREEN_METRICS.get_monitor_for_pos(Window.left, Window.top)
            monitor_max_h = get_best_window_height_fit(monitor.height_pixels) if monitor else 0
            if min_height <= monitor_max_h:
                correct_width = min_width
                correct_height = min_height

        # Refuse to schedule a degenerate correction. Can happen when ``Window.left``/``top``
        # is off-screen (monitor lookup returns ``None``) and the recovery branch above
        # was unable to fall back to a valid (min_width, min_height) pair.
        if correct_width <= 0 or correct_height <= chrome:
            logger.debug(
                f"Skipping aspect-ratio correction:"
                f" width = {width}, height = {height},"
                f" correct = ({correct_width}, {correct_height}),"
                f" Window.left/top = ({Window.left}, {Window.top})."
            )
            return

        if (correct_width, correct_height) != (unit_width, unit_height):
            # User resize: debounce so only one correction fires after the drag settles.
            if self._correction_event:
                self._correction_event.cancel()

            def apply_correction(_dt: float) -> None:
                self._correction_event = None
                # The window moved on since this event: leaving fullscreen, the restore
                # to the saved size lands between a transient size's event and this
                # correction, which then resized a window already right (a second
                # resize the software OpenGL renderer crashed drawing through).
                if tuple(Window.size) != (width, height):
                    logger.debug(
                        f"Aspect-ratio correction dropped: it was for {width},{height},"
                        f" and the window is now {tuple(Window.size)}."
                    )
                    return
                logger.info(
                    f"Aspect-ratio correction: resize event {width},{height}"
                    f" -> Window.size = ({correct_width}, {correct_height});"
                    f" Window.left/top = ({Window.left}, {Window.top}),"
                    f" monitor width = {monitor_w}."
                )
                Window.size = (correct_width, correct_height)

            self._correction_event = Clock.schedule_once(apply_correction, RESIZE_CORRECTION_DELAY)
            return

        # Already in proportion: a correction still pending for an earlier, transient
        # size is not wanted any more.
        if self._correction_event:
            self._correction_event.cancel()
            self._correction_event = None
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
        self.evaluate_layout("rotation", refit=False)  # the resize below is the refit

        chrome = self._chrome_in_size_units()
        aspect_ratio = self.content_aspect_ratio
        new_height = calculate_fitted_window_height(
            screen_width=monitor.width_pixels,
            screen_height=monitor.height_pixels,
            aspect_ratio=aspect_ratio,
            action_bar_height=chrome,
            fit_fraction=ROTATION_FIT_FRACTION,
        )
        new_width, content_h = get_win_dimensions(
            new_height - chrome, monitor.width_pixels, aspect_ratio
        )
        new_width, new_height = self._no_smaller_than_minimum(new_width, content_h + chrome)

        center_x = monitor.monitor_x + (monitor.width_pixels - new_width) // 2
        center_y = monitor.monitor_y + (monitor.height_pixels - new_height) // 2

        logger.info(
            f"Rotation resize: ({new_width}, {new_height}) at ({center_x}, {center_y})"
            f" on monitor {monitor.display}"
            f" ({monitor.width_pixels}x{monitor.height_pixels})"
            f" at ({center_x},{center_y})."
        )

        self._schedule_guarded_resize(new_width, new_height, reposition=(center_x, center_y))
        self.apply_minimum_size()  # the rotated monitor's; after the guard, as on a move

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

        def do_reposition(_dt: float) -> None:
            if reposition is not None:
                logger.debug(f"Repositioning window to {reposition}.")
                Window.left, Window.top = reposition

        def do_reset_resize(_dt: float) -> None:
            logger.debug("Clearing resize guard.")
            self._resize_event = None
            self._resize_requested_size = 0, 0

        Clock.schedule_once(do_resize, 0)
        Clock.schedule_once(do_reposition, RESIZE_CORRECTION_DELAY)
        self._resize_event = Clock.schedule_once(do_reset_resize, MOVE_SETTLE_DELAY)


def _set_window_minimum_size(width: int, height: int) -> None:
    """Set the window's minimum size, both sides at once.

    Kivy's SDL window applies the minimum whenever either side changes, and warns while
    the other is still 0, as it is on the first setting. So its handler is held off
    while both are set, then run once.
    """
    apply = getattr(Window, "_set_minimum_size", None)
    if apply is None:  # a window provider with no minimum size
        Window.minimum_width, Window.minimum_height = width, height
        return
    Window.unbind(minimum_width=apply, minimum_height=apply)
    try:
        Window.minimum_width, Window.minimum_height = width, height
    finally:
        Window.bind(minimum_width=apply, minimum_height=apply)
    apply()
