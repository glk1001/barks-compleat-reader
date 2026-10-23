"""Find a story's splash pages from its panel bounding boxes.

A splash panel covers half the page or more, whatever the story's layout.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# How much of the area a page's panels span its largest panel must cover to be a
# splash: half, less the gutters, which bring a half-page panel to about 0.49.
# Measured over every story (2026-10-23): off page 1 each splash covers at least 0.493
# and no other panel more than 0.353. On page 1 the title panels fall in two groups,
# 0.40 to 0.459 (left out) and half-page ones from 0.472 up; the one of those left out
# by hand is in SPLASH_EXCEPTIONS. Phase 12 of validate-barks-reader-files.py fails on
# any page that crosses the line either way.
SPLASH_MIN_FRACTION: Final = 0.47


def get_panel_area_fractions(segments: Mapping[str, Any]) -> list[float]:
    """Return each panel's area as a fraction of the area its page's panels span.

    Args:
        segments: A page's panel-segments JSON: "panels" as [x, y, width, height]
            boxes and "overall_bounds" as inclusive [x0, y0, x1, y1] pixel coordinates.

    Returns:
        One fraction per panel, in the JSON's order; empty for a page with no panels.

    """
    x0, y0, x1, y1 = segments["overall_bounds"]
    page_area = (x1 - x0 + 1) * (y1 - y0 + 1)
    if page_area <= 0:
        return []
    return [width * height / page_area for _x, _y, width, height in segments["panels"]]


def get_splash_pages(pages: Mapping[str, Sequence[float]]) -> list[str]:
    """Return the pages whose largest panel is a splash.

    Args:
        pages: Each page's number and its panels' area fractions (see
            `get_panel_area_fractions`), in page order.

    Returns:
        The splash pages' numbers, in page order.

    """
    return [
        page for page, panels in pages.items() if max(panels, default=0.0) >= SPLASH_MIN_FRACTION
    ]
