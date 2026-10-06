from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

from loguru import logger
from screeninfo import get_monitors

from .platform_info import IS_MACOS, PLATFORM, Platform

_WINDOWS_TASKBAR_HEIGHT = 60
_OTHER_TASKBAR_HEIGHT = 55


def get_approximate_taskbar_height() -> int:
    """Return how much of the screen's height the desktop keeps for itself.

    On macOS that is measured: the menu bar and the Dock, which a fixed guess left the
    bottom of the window under. Elsewhere it is a fixed allowance for a taskbar or panel.
    """
    if PLATFORM == Platform.WIN:
        return _WINDOWS_TASKBAR_HEIGHT
    if IS_MACOS:
        reserved = _macos_reserved_height()
        if reserved is not None:
            return reserved
    return _OTHER_TASKBAR_HEIGHT


def _macos_reserved_height() -> int | None:
    """Return the height the menu bar and the Dock take on the primary screen, or None.

    The screen's frame less its visible frame, in points, as screeninfo reports the
    screen. A Dock at the side, or hidden, takes no height. None if AppKit cannot say.
    """
    try:
        # By name: pyobjc is a macOS-only dependency, with no stubs for the type checkers.
        app_kit: Any = importlib.import_module("AppKit")
        screens = app_kit.NSScreen.screens()
        if not screens:
            return None
        primary = screens[0]  # the one with the menu bar, as screeninfo's primary
        reserved = round(primary.frame().size.height - primary.visibleFrame().size.height)
    except (ImportError, AttributeError) as exc:
        logger.warning(f"Could not measure the menu bar and Dock: {exc}.")
        return None
    return max(reserved, 0)


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
            # screeninfo reports None for a size it does not know, and some displays 0.
            width_mm = monitor.width_mm or 0
            height_mm = monitor.height_mm or 0
            if not (width_mm > 0 and height_mm > 0):
                width_mm = 0
                height_mm = 0
                width_in = 0
                height_in = 0
                avg_dpi = 0
            else:
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

        # A warning, not an error: every caller copes with no monitor, and on Windows a
        # window leaving fullscreen passes through a position above the screen (for
        # ~0.3s, with a frame) before its restore puts it back.
        logger.warning(
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
