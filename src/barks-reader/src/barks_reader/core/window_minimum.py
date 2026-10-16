"""The smallest window the reader allows, and the screens too small for it.

The reader is laid out for a 1920x1080 screen: its window, locked to the comic page's
shape, is then the screen's height less the taskbar, and about 660 wide. That is the
smallest window the layouts are tested at (the overnight run's screen-1080p stage), so
it is the window's minimum size. A smaller screen gets its own largest window instead,
and a warning, once, that some text may be cut short.

Sizes are in the units screeninfo gives the monitors in (``Window.system_size``'s).
Kivy-free, so the sizes can be tested without a window.
"""

from __future__ import annotations

import os

from .screen_metrics import get_best_window_height_fit

SUPPORTED_SCREEN_WIDTH = 1920
SUPPORTED_SCREEN_HEIGHT = 1080

# Set (to anything) to boot without the too-small-screen popup: the GUI probe sets it,
# as the tests' nested screens may be smaller and a popup would take their keys.
NO_SCREEN_WARNING_ENV_VAR = "BARKS_READER_NO_SCREEN_WARNING"


def minimum_window_size(
    screen_height: int, aspect_ratio: float, chrome_height: int
) -> tuple[int, int]:
    """Return the smallest window the reader allows on a screen `screen_height` tall.

    Args:
        screen_height: The screen's height.
        aspect_ratio: The window content's height over its width.
        chrome_height: The window's height besides its content (the action bar).

    Returns:
        The window (width, height) a 1080-tall screen gives, or this screen's own
        largest window when it is shorter.

    """
    height = get_best_window_height_fit(min(screen_height, SUPPORTED_SCREEN_HEIGHT))
    width = round((height - chrome_height) / aspect_ratio)
    return width, height


def is_screen_too_small(screen_width: int, screen_height: int) -> bool:
    """Return whether a screen is smaller than the reader is laid out for.

    The window is portrait and about 660 wide, so only the height counts: any screen
    1080 tall holds it, portrait monitors and all.

    Args:
        screen_width: The screen's width (any width holds the window).
        screen_height: The screen's height.

    Returns:
        True when the screen is too short for the reader's minimum window.

    """
    del screen_width
    return screen_height < SUPPORTED_SCREEN_HEIGHT


def screen_size_key(screen_width: int, screen_height: int) -> str:
    """Return the name a screen size is remembered by: "1366x768"."""
    return f"{screen_width}x{screen_height}"


def screen_warning_text(screen_width: int, screen_height: int) -> str:
    """Return the popup's text for a screen smaller than the reader is laid out for."""
    return (
        f"This screen ({screen_width} x {screen_height}) is smaller than the Compleat Barks"
        f" Disney Reader is designed for ({SUPPORTED_SCREEN_WIDTH} x"
        f" {SUPPORTED_SCREEN_HEIGHT}).\n\n"
        "The reader will run, but some titles may be cut short and some screens crowded."
    )


def is_screen_warning_suppressed() -> bool:
    """Return whether the environment asks for no too-small-screen popup."""
    return bool(os.environ.get(NO_SCREEN_WARNING_ENV_VAR))
