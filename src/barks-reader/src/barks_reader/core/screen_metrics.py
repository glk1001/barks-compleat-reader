from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from screeninfo import get_monitors

from barks_reader.core.platform_info import PLATFORM, Platform


def get_approximate_taskbar_height() -> int:
    if PLATFORM != Platform.WIN:
        return 55
    return 60


def get_best_window_height_fit(screen_height: int) -> int:
    return screen_height - get_approximate_taskbar_height()


@dataclass(frozen=True, slots=True)
class ScreenInfo:
    display: int
    monitor_x: int
    monitor_y: int
    width_pixels: int
    height_pixels: int
    width_mm: int
    height_mm: int
    width_in: int
    height_in: int
    dpi: int
    is_primary: bool


class ScreenMetrics:
    def __init__(self) -> None:
        self.SCREEN_INFO = self._get_screen_info()
        self.NUM_MONITORS = len(self.SCREEN_INFO)

    @staticmethod
    def _get_screen_info() -> list[ScreenInfo]:
        monitors = get_monitors()
        if not monitors:
            logger.warning("No monitors found by screeninfo.")
            return []

        inch_in_mm = 25.4
        screens = []
        for i, monitor in enumerate(monitors):
            if not (
                monitor.width_mm
                and monitor.height_mm
                and monitor.width_mm > 0
                and monitor.height_mm > 0
            ):
                width_mm = 0
                height_mm = 0
                width_in = 0
                height_in = 0
                avg_dpi = 0
            else:
                width_mm = monitor.width_mm
                height_mm = monitor.height_mm

                width_in = round(width_mm / inch_in_mm)
                height_in = round(height_mm / inch_in_mm)

                dpi_x = (monitor.width / width_mm) * inch_in_mm
                dpi_y = (monitor.height / height_mm) * inch_in_mm

                avg_dpi = (dpi_x + dpi_y) / 2

            screens.append(
                ScreenInfo(
                    i,
                    monitor.x,
                    monitor.y,
                    monitor.width,
                    monitor.height,
                    width_mm,
                    height_mm,
                    width_in,
                    height_in,
                    int(avg_dpi),
                    monitor.is_primary or False,
                )
            )

        return screens

    def get_primary_screen_info(self) -> ScreenInfo:
        for info in self.SCREEN_INFO:
            if info.is_primary:
                return info

        return self.SCREEN_INFO[0]

    def get_monitor_for_pos(self, x: int, y: int) -> ScreenInfo | None:
        for info in self.SCREEN_INFO:
            if (
                info.monitor_x <= x < info.monitor_x + info.width_pixels
                and info.monitor_y <= y < info.monitor_y + info.height_pixels
            ):
                return info

        logger.error(
            f"Could not find monitor for pos ({x},{y})."
            f" (There are {len(self.SCREEN_INFO)} monitors.)"
        )
        return None

    def refresh(self) -> bool:
        """Re-query monitors and return True if any dimensions changed."""
        old_dims = {(s.display, s.width_pixels, s.height_pixels) for s in self.SCREEN_INFO}
        self.SCREEN_INFO = self._get_screen_info()
        self.NUM_MONITORS = len(self.SCREEN_INFO)
        new_dims = {(s.display, s.width_pixels, s.height_pixels) for s in self.SCREEN_INFO}
        return old_dims != new_dims


def calculate_fitted_window_height(
    screen_width: int,
    screen_height: int,
    aspect_ratio: float,
    action_bar_height: int,
    fit_fraction: float = 0.9,
) -> int:
    """Calculate the largest window height that fits within fit_fraction of the screen.

    The window's content area has the given aspect_ratio (height / width). The total
    window height includes action_bar_height. Both the total width and total height
    must fit within fit_fraction of the respective screen dimension.

    Args:
        screen_width: Screen width in pixels.
        screen_height: Screen height in pixels.
        aspect_ratio: Content height / content width (e.g. 3200 / 2120).
        action_bar_height: Additional fixed height for the action bar.
        fit_fraction: Fraction of screen to use (default 0.9).

    Returns:
        Total window height (content + action bar), in pixels.

    """
    max_total_h = int(fit_fraction * screen_height)
    max_total_w = int(fit_fraction * screen_width)

    # Try height-limited: use max_total_h, derive width.
    content_h = max_total_h - action_bar_height
    content_w = round(content_h / aspect_ratio)

    if content_w <= max_total_w:
        return max_total_h

    # Width-limited: use max_total_w, derive height.
    content_h = round(max_total_w * aspect_ratio)
    return content_h + action_bar_height


SCREEN_METRICS = ScreenMetrics()
