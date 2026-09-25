"""What a capture of the app window looks like, in numbers: enough to tell a blank render.

The suite clicks nothing by pixel and never compares a capture to a reference;
a screenshot is only asked whether anything was drawn. A window that is one
flat colour, or nearly so, is a render that failed while the log went on as
usual - the one failure the log cannot see.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path

# Sample every Nth pixel in each direction: statistics, not a comparison, so a
# 782x1225 window needs no more than a few thousand samples.
SAMPLE_STEP = 4

# What counts as blank. Calibrated on the final frame of all 62 tests on
# 2026-09-22 (headless, 900x1300): the most common colour covered 3% to 26% of
# the window and the samples held 4,600 to 25,000 distinct colours. A flat or
# two-tone frame is 100% and a handful; these sit far from both.
BLANK_DOMINANT_FRACTION = 0.9
BLANK_MIN_COLOURS = 64


@dataclass(frozen=True)
class RenderStats:
    """How much of a window is its most common colour, and how many colours it has."""

    dominant_fraction: float
    distinct_colours: int
    samples: int


def render_stats(capture: Path, window: tuple[int, int, int, int]) -> RenderStats:
    """Return the colour statistics of the app window's part of a nested-display capture.

    Args:
        capture: The PNG the probe captured (the whole nested screen).
        window: The app window's ``(width, height, x, y)`` on that screen.

    """
    width, height, left, top = window
    with Image.open(capture) as image:
        region = image.convert("RGB").crop((left, top, left + width, top + height))
        pixels = [
            region.getpixel((x, y))
            for y in range(0, region.height, SAMPLE_STEP)
            for x in range(0, region.width, SAMPLE_STEP)
        ]
    if not pixels:
        return RenderStats(dominant_fraction=1.0, distinct_colours=0, samples=0)
    counts: dict[object, int] = {}
    for pixel in pixels:
        counts[pixel] = counts.get(pixel, 0) + 1
    return RenderStats(
        dominant_fraction=max(counts.values()) / len(pixels),
        distinct_colours=len(counts),
        samples=len(pixels),
    )


def looks_blank(stats: RenderStats) -> bool:
    """Return whether a window with these statistics was not really drawn."""
    return (
        stats.dominant_fraction > BLANK_DOMINANT_FRACTION
        or stats.distinct_colours < BLANK_MIN_COLOURS
    )
