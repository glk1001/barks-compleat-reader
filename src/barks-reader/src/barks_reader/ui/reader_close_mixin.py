"""The window-mode close the comic and document readers share.

Both readers close by returning the window to the mode they opened in, and leave
only once laid out for it: one copy of the wait, so a timing fix reaches both.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from kivy.clock import Clock
from kivy.core.window import Window
from loguru import logger

from .action_bar_helpers import (
    ActionBarVisibility,
    is_action_bar_visible,
    set_action_bar_visibility,
)
from .platform_window_utils import WindowManager

if TYPE_CHECKING:
    from kivy.uix.actionbar import ActionBar


class ReaderCloseMixin:
    """The close-once-laid-out wait, the fullscreen check and the bar's show and hide.

    Mixed into a reader `Screen`, which provides `_finish_closing` (leave the screen)
    and `_reader_action_bar` (the bar fullscreen hides).
    """

    # A close waits for the reader to fill the window it closes into (see
    # `_finish_closing_once_laid_out`), a frame at a time, but never longer than this.
    _CLOSE_LAYOUT_MAX_FRAMES: ClassVar[int] = 10
    # How near the window's size the reader counts as filling it: a resize can land a
    # pixel apart (2561 against 2560 on the Mac guest).
    _FILLS_WINDOW_TOLERANCE_PX: ClassVar[int] = 2

    if TYPE_CHECKING:
        # The Screen's.
        width: float
        height: float
        size_hint: Any
        pos_hint: Any

    # --- Hooks the reader provides ---

    def _finish_closing(self) -> None:
        """Leave the reader screen, the window now in the mode the reader opened in."""
        raise NotImplementedError

    def _reader_action_bar(self) -> ActionBar:
        """Return the bar fullscreen hides."""
        raise NotImplementedError

    # --- The close ---

    def _set_hints_for_windowed_mode(self) -> None:
        # Restore the layout properties so the screen fills the window again.
        self.size_hint = (1, 1)
        self.pos_hint = {"center_x": 0.5, "center_y": 0.5}

    def _finish_closing_once_laid_out(self, frames_left: int = _CLOSE_LAYOUT_MAX_FRAMES) -> None:
        """Close once the reader fills the window it closes into, and a frame more.

        The closing animation (a shader transition) draws the reader as it stands
        when it starts. Closing returns the window to the mode the reader opened in,
        and the reader is laid out for a new window size a frame or more after the
        mode change reports itself done: closed at once, the reader fell out at the
        old size, its page pinned to the screen's left edge. The extra frame lets
        the page inside it follow. At most _CLOSE_LAYOUT_MAX_FRAMES frames: a reader
        that never fills the window must still close.
        """
        if frames_left > 0 and not self._fills_window():
            Clock.schedule_once(lambda _dt: self._finish_closing_once_laid_out(frames_left - 1))
            return
        if frames_left > 0:
            Clock.schedule_once(lambda _dt: self._finish_closing())
            return
        self._finish_closing()

    def _fills_window(self) -> bool:
        tolerance = self._FILLS_WINDOW_TOLERANCE_PX
        return (
            abs(self.width - Window.width) <= tolerance
            and abs(self.height - Window.height) <= tolerance
        )

    def _is_fullscreen_now_after_goto(self) -> bool:
        """Return whether the window is fullscreen, logging an error when a goto missed.

        The actual mode, not an assumed True: if the transition failed, the button and
        the bar must keep matching the real window.
        """
        is_fullscreen_now = bool(WindowManager.is_fullscreen_now())
        if not is_fullscreen_now:
            logger.error(
                f"Finishing goto fullscreen on {type(self).__name__} but Window fullscreen"
                f" = '{WindowManager.get_screen_mode_now()}'."
            )
        return is_fullscreen_now

    # --- The bar ---

    def _show_action_bar(self) -> None:
        """Show the action bar if currently hidden. No-op if already visible."""
        action_bar = self._reader_action_bar()
        if not is_action_bar_visible(action_bar):
            set_action_bar_visibility(action_bar, ActionBarVisibility.VISIBLE)

    def _hide_action_bar(self) -> None:
        """Hide the action bar if currently visible. No-op if already hidden."""
        action_bar = self._reader_action_bar()
        if is_action_bar_visible(action_bar):
            set_action_bar_visibility(action_bar, ActionBarVisibility.HIDDEN)
