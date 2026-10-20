"""Where a press on a reader lands: the left, right, top and bottom margins. Kivy-free."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Callable


class ReaderNavigation:
    """The margins of a reader widget a press turns a page or shows a bar from.

    Left and right of the middle, between the bottom and top margins, turn the page;
    the top and bottom margins are the bars'. In fullscreen the top and bottom
    margins narrow to the middle half of the window.
    """

    def __init__(
        self,
        max_window_width: int,
        top_margin_frac_of_height: float,
        bottom_margin_frac_of_height: float = 1.0,
        *,
        is_fullscreen: Callable[[], bool],
    ) -> None:
        """Make the regions, empty until `update_regions`.

        Args:
            max_window_width: The widest the window gets, which fullscreen fills.
            top_margin_frac_of_height: The top margin's share of the height.
            bottom_margin_frac_of_height: Where the bottom margin ends, as a share of
                the height from the top; 1.0 leaves no bottom margin.
            is_fullscreen: Answers whether the window is fullscreen now.

        """
        self._is_fullscreen = is_fullscreen
        self._max_window_width = max_window_width
        self._top_margin_frac_of_height = top_margin_frac_of_height
        self._bottom_margin_frac_of_height = bottom_margin_frac_of_height

        self._x_mid = -1
        self._y_bottom_margin = -1
        self._y_top_margin = -1
        self._fullscreen_left_margin = -1
        self._fullscreen_right_margin = -1

    @property
    def x_mid(self) -> int:
        return self._x_mid

    @property
    def y_bottom_margin(self) -> int:
        return self._y_bottom_margin

    @property
    def y_top_margin(self) -> int:
        return self._y_top_margin

    def update_regions(
        self, win_width: int, win_height: int, win_left: float, win_top: float
    ) -> None:
        """Work the margins out for a widget of this size at this place in the window."""
        self._x_mid = round((win_width / 2) - win_left)
        self._y_bottom_margin = round(
            (win_height - win_top) - (self._bottom_margin_frac_of_height * win_height)
        )
        self._y_top_margin = round(
            (win_height - win_top) - (self._top_margin_frac_of_height * win_height)
        )
        logger.debug(f"Navigation: win_width = {win_width}, win_height = {win_height}.")
        logger.debug(f"Navigation: win_left = {win_left}, win_top = {win_top}.")
        logger.debug(
            f"Navigation: x_mid = {self._x_mid},"
            f" y_bottom_margin = {self._y_bottom_margin},"
            f" y_top_margin = {self._y_top_margin}."
        )

        self._fullscreen_left_margin = round(self._max_window_width / 4.0)
        self._fullscreen_right_margin = self._max_window_width - self._fullscreen_left_margin
        logger.debug(
            f"Reader navigation: fullscreen_left_margin = {self._fullscreen_left_margin},"
            f" fullscreen_right_margin = {self._fullscreen_right_margin}."
        )

    def is_in_top_margin(self, x: int, y: int) -> bool:
        """Return whether (x, y) is in the top margin."""
        if y < self._y_top_margin:
            return False

        if not self._is_fullscreen():
            return True

        return self._fullscreen_left_margin < x <= self._fullscreen_right_margin

    def is_in_bottom_margin(self, x: int, y: int) -> bool:
        """Return whether (x, y) is in the bottom margin."""
        if self._y_bottom_margin < y:
            return False

        if not self._is_fullscreen():
            return True

        return self._fullscreen_left_margin < x <= self._fullscreen_right_margin

    def is_in_left_margin(self, x: int, y: int) -> bool:
        """Return whether (x, y) is left of the middle, between the top and bottom margins."""
        return (x < self._x_mid) and (self._y_bottom_margin <= y <= self._y_top_margin)

    def is_in_right_margin(self, x: int, y: int) -> bool:
        """Return whether (x, y) is right of the middle, between the top and bottom margins."""
        return (x >= self._x_mid) and (self._y_bottom_margin <= y <= self._y_top_margin)

    def tap_regions(self, width: int, height: int) -> dict[str, tuple[int, int, int, int]]:
        """Return the margins a press acts on, as rectangles a GUI test can tap.

        Each is ``(x, y, w, h)`` in the coordinates the ``is_in_*`` checks take:
        relative to the widget, origin bottom-left, within a `width` x `height`
        widget. A region too thin to press is left out.

        Args:
            width: The widget's width.
            height: The widget's height.

        Returns:
            "left margin", "right margin" and "top margin", by name.

        """
        regions: dict[str, tuple[int, int, int, int]] = {}
        bottom = max(0, self._y_bottom_margin)
        top = min(height - 1, self._y_top_margin)
        mid = min(max(0, self._x_mid), width)
        if top > bottom:
            if mid > 0:
                regions["left margin"] = (0, bottom, mid, top - bottom)
            if width > mid:
                regions["right margin"] = (mid, bottom, width - mid, top - bottom)
        top_start = max(0, self._y_top_margin)
        if height > top_start:
            left, right = 0, width
            if self._is_fullscreen():
                left = min(width, max(0, self._fullscreen_left_margin + 1))
                right = min(width, self._fullscreen_right_margin + 1)
            if right > left:
                regions["top margin"] = (left, top_start, right - left, height - top_start)
        return regions
