"""Find a story's splash pages from its panel bounding boxes.

A splash panel takes the space of four of the story's normal panels: half a page in a
story laid out eight panels to a page, two-thirds of one laid out six to a page.
"""

from __future__ import annotations

from statistics import median
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# How many normal panels' space a page's largest panel must cover to be a splash.
# Measured over every Fantagraphics story (2026-10-11): off page 1 it divides cleanly,
# each splash covering at least 3.9 and no other panel more than 3.1. Page 1 has no
# such gap: dozens of title panels cover 3.45 to 3.56 (one 3.95), among page-1
# splashes from 3.53 up. The 35 title panels over the line are left out by hand
# (SPLASH_EXCEPTIONS), and Phase 12 of validate-barks-reader-files.py fails on any
# page that crosses it either way.
SPLASH_PANEL_UNITS: Final = 3.5


def get_panel_area_fractions(segments: Mapping[str, Any]) -> list[float]:
    """Return each panel's area as a fraction of the area its page's panels span.

    Args:
        segments: A page's panel-segments JSON: "panels" as [x, y, width, height]
            boxes and "overall_bounds" as [x0, y0, x1, y1].

    Returns:
        One fraction per panel, in the JSON's order; empty for a page with no panels.

    """
    x0, y0, x1, y1 = segments["overall_bounds"]
    page_area = (x1 - x0) * (y1 - y0)
    if page_area <= 0:
        return []
    return [width * height / page_area for _x, _y, width, height in segments["panels"]]


def get_splash_pages(pages: Mapping[str, Sequence[float]]) -> list[str]:
    """Return the pages whose largest panel is a splash.

    A normal panel is the median panel of the whole story, so the same rule finds a
    half-page splash among eight panels to a page and a two-thirds one among six.

    Args:
        pages: Each page's number and its panels' area fractions (see
            `get_panel_area_fractions`), in page order.

    Returns:
        The splash pages' numbers, in page order.

    """
    areas = [area for panels in pages.values() for area in panels]
    if not areas:
        return []
    normal_panel = median(areas)
    return [
        page
        for page, panels in pages.items()
        if panels and max(panels) >= SPLASH_PANEL_UNITS * normal_panel
    ]
