from loguru import logger

from .platform_window_utils import WindowManager


class ReaderNavigation:
    def __init__(
        self,
        max_window_width: int,
        top_margin_frac_of_height: float,
        bottom_margin_frac_of_height: float = 1.0,
    ) -> None:
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
        if y < self._y_top_margin:
            return False

        if not WindowManager.is_fullscreen_now():
            return True

        return self._fullscreen_left_margin < x <= self._fullscreen_right_margin

    def is_in_bottom_margin(self, x: int, y: int) -> bool:
        if self._y_bottom_margin < y:
            return False

        if not WindowManager.is_fullscreen_now():
            return True

        return self._fullscreen_left_margin < x <= self._fullscreen_right_margin

    def is_in_left_margin(self, x: int, y: int) -> bool:
        return (x < self._x_mid) and (self._y_bottom_margin <= y <= self._y_top_margin)

    def is_in_right_margin(self, x: int, y: int) -> bool:
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
            if WindowManager.is_fullscreen_now():
                left = min(width, max(0, self._fullscreen_left_margin + 1))
                right = min(width, self._fullscreen_right_margin + 1)
            if right > left:
                regions["top margin"] = (left, top_start, right - left, height - top_start)
        return regions
