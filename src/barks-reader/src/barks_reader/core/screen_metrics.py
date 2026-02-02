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
                    avg_dpi,
                    monitor.is_primary,
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

        return None


SCREEN_METRICS = ScreenMetrics()
