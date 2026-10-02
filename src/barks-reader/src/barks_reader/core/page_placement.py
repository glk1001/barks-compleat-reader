"""Where the comic reader drew its page, for the log (``log_markers.PAGE_PLACED``).

The reader's page image is fitted ("contain") inside its widget, so the page is
drawn smaller than the widget and centred in it. The rectangle here is the page
itself, in window pixels from the bottom left: what the GUI harness checks is
centred in the window, as nothing else the app logs says where a page went.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from . import log_markers


@dataclass(frozen=True, slots=True)
class PagePlacement:
    """The page's rectangle and the window it is in, all in window pixels."""

    x: int
    y: int
    width: int
    height: int
    win_width: int
    win_height: int


def fitted_page_rect(
    center_x: float, center_y: float, fitted_width: float, fitted_height: float
) -> tuple[int, int, int, int]:
    """Return the (x, y, width, height) of a page of the fitted size centred at (x, y)."""
    width, height = round(fitted_width), round(fitted_height)
    return round(center_x - fitted_width / 2), round(center_y - fitted_height / 2), width, height


def log_page_placement(placement: PagePlacement, last: PagePlacement | None) -> PagePlacement:
    """Log `placement` unless it is `last`; return it, as the new last one."""
    if placement != last:
        logger.debug(
            log_markers.PAGE_PLACED.format(
                width=placement.width,
                height=placement.height,
                x=placement.x,
                y=placement.y,
                win_width=placement.win_width,
                win_height=placement.win_height,
            )
        )
    return placement
