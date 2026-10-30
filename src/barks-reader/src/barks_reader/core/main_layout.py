"""The main screen's layout on a screen: the single page, or a two-page spread.

The main screen was laid out for a portrait screen: the tree above the current view,
the window locked to the comic page's shape. On a landscape screen it becomes an open
book: the tree is the left page, the current view the right page, each page at the
comic page's shape, a gutter between them, the action bar across the pair. A page in
the spread is exactly as wide as the single column is on the same screen, so nothing
gets smaller and the fonts, keyed to the window's height, do not change.

The "Layout" setting chooses: the single page, the spread, or, by default,
whichever matches the screen. Matching the screen is one measurement, `spread_fits`:
the spread when two pages fit side by side at full height, decided from the monitor's
full size in both windowed and fullscreen mode so a monitor gets one answer (a usable
area less the taskbar would let a 5:4 screen flip between the two). The pair fits down
to a width-to-height of about 1.28: 4:3 qualifies, 5:4 just misses, and no screen shape
sits near the boundary, so there is no hysteresis.

The gutter is a fraction of a page's width, which makes the spread's content aspect
(`content_aspect_ratio`) a constant per mode rather than a function of the screen: the
window lock stays one number. Kivy-free, so the rule can be tested without a window.
The design and its decisions: ``docs/plans/two-page-spread.md``.
"""

from __future__ import annotations

from enum import Enum

from .reader_utils import COMIC_PAGE_ASPECT_RATIO

# The setting's values, as the settings panel shows them and the ini stores them.
MATCH_THE_SCREEN = "Match the screen"
SINGLE_PAGE = "Single page"
TWO_PAGE_SPREAD = "Two-page spread"
MAIN_SCREEN_LAYOUT_OPTIONS: tuple[str, ...] = (MATCH_THE_SCREEN, SINGLE_PAGE, TWO_PAGE_SPREAD)

# The gutter between the two pages, as a fraction of a page's width (about 20 px at
# 1080p, 28 px at 1440p).
GUTTER_FRACTION = 0.03
# The spread's width in pages: two pages and the gutter.
SPREAD_WIDTH_IN_PAGES = 2 + GUTTER_FRACTION


class MainLayoutMode(Enum):
    """How the main screen is laid out: the tree above the view, or beside it."""

    SINGLE = "single"
    SPREAD = "spread"


def content_aspect_ratio(
    mode: MainLayoutMode, page_aspect_ratio: float = COMIC_PAGE_ASPECT_RATIO
) -> float:
    """Return the shape of the main window's content (height over width) in a layout mode.

    Args:
        mode: The layout mode.
        page_aspect_ratio: A page's height over its width.

    Returns:
        The page's shape in single mode; the pair's, gutter included, in the spread.

    """
    if mode is MainLayoutMode.SPREAD:
        return page_aspect_ratio / SPREAD_WIDTH_IN_PAGES
    return page_aspect_ratio


def spread_fits(
    screen_width: int,
    screen_height: int,
    chrome_height: int,
    page_aspect_ratio: float = COMIC_PAGE_ASPECT_RATIO,
) -> bool:
    """Return whether two pages fit side by side at full height on a screen.

    Args:
        screen_width: The monitor's width.
        screen_height: The monitor's height.
        chrome_height: The window's height besides its content (the action bar).
        page_aspect_ratio: A page's height over its width.

    Returns:
        True when a pair of pages as tall as the screen allows, with the gutter between
        them, is no wider than the screen.

    """
    page_width = (screen_height - chrome_height) / page_aspect_ratio
    return page_width * SPREAD_WIDTH_IN_PAGES <= screen_width


def choose_main_layout(
    setting: str,
    screen_width: int,
    screen_height: int,
    chrome_height: int,
    page_aspect_ratio: float = COMIC_PAGE_ASPECT_RATIO,
) -> MainLayoutMode:
    """Return the layout mode the setting asks for on a screen.

    Args:
        setting: One of `MAIN_SCREEN_LAYOUT_OPTIONS`; anything else matches the screen.
        screen_width: The monitor's width.
        screen_height: The monitor's height.
        chrome_height: The window's height besides its content (the action bar).
        page_aspect_ratio: A page's height over its width.

    Returns:
        The single page or the spread: as the setting says, or as the screen's shape
        decides when it asks to match the screen.

    """
    if setting == SINGLE_PAGE:
        return MainLayoutMode.SINGLE
    if setting == TWO_PAGE_SPREAD:
        return MainLayoutMode.SPREAD
    if spread_fits(screen_width, screen_height, chrome_height, page_aspect_ratio):
        return MainLayoutMode.SPREAD
    return MainLayoutMode.SINGLE


def gutter_width(spread_width: float) -> float:
    """Return the gutter's width in a spread this wide (two pages and the gutter)."""
    return spread_width * GUTTER_FRACTION / SPREAD_WIDTH_IN_PAGES


def page_width(spread_width: float) -> float:
    """Return one page's width in a spread this wide (two pages and the gutter)."""
    return spread_width / SPREAD_WIDTH_IN_PAGES
