from dataclasses import dataclass

from kivy.metrics import cm, dp, inch, sp
from loguru import logger
from screeninfo import get_monitors


@dataclass
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


def get_screen_info() -> list[ScreenInfo]:
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


def log_screen_metrics(scrn_info: list[ScreenInfo]) -> None:
    logger.info("--- Detailed Monitor Metrics ---")

    for info in scrn_info:
        logger.info(
            f"Display {info.display}: {info.width_pixels} x {info.height_pixels} pixels"
            f" at ({info.monitor_x}, {info.monitor_y})."
        )
        logger.info(
            f"  -> Physical Size: {info.width_mm}mm x {info.height_mm}mm"
            f" ({info.width_in:.2f}in x {info.height_in:.2f}in)."
        )
        logger.info(f"  -> Calculated DPI: {info.dpi:.2f}.")
        logger.info(f"  -> Primary: {info.is_primary}.")

    logger.info(f"1 cm = {cm(1):.1f} pixels.")
    logger.info(f"1 in = {inch(1):.1f} pixels.")
    logger.info(f"100 dp = {dp(100):.1f} pixels.")
    logger.info(f"100 sp = {sp(100):.1f} pixels.")

    logger.info("--------------------------------")


if __name__ == "__main__":
    screen_info = get_screen_info()
    assert screen_info
    log_screen_metrics(screen_info)
