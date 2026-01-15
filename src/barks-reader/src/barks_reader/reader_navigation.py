from loguru import logger

from barks_reader.platform_utils import WindowManager


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
