"""The popup frame's size classes and buttons, free of Kivy: how big a popup is.

Every popup the app owns is one of three sizes (``docs/plans/popup-consistency.md``).
A size is measured in comic pages across and in the window's height down, a page being
the window's height over the page aspect, as the two-page spread lays its pages out
(``core/main_layout.py``). So a popup comes out the same size on the single page and on
the spread at the same height, as the fonts do (they are sized from the height alone),
rather than stretching across the spread's two pages.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from .reader_utils import COMIC_PAGE_ASPECT_RATIO

if TYPE_CHECKING:
    from collections.abc import Callable


class PopupSize(StrEnum):
    """A popup's size class."""

    SMALL = "small"  # a question: Quit, Delete, Clear
    MEDIUM = "medium"  # a message, an error, a setting
    LARGE = "large"  # a long list or text: About, speech bubbles, the installers


@dataclass(frozen=True, slots=True)
class FrameButton:
    """A button on the frame's row: its label, and what pressing it does.

    A button closes the popup before its action runs, unless it is one that leaves the
    popup up (Save to File, Copy to Clipboard). Free of Kivy, so the popups that are
    their own window can name their buttons before Kivy is imported.
    """

    text: str
    on_press: Callable[[], None]
    closes: bool = True


@dataclass(frozen=True, slots=True)
class SizeClass:
    """A size class: its width in pages, its height as a fraction of the window's."""

    pages_wide: float
    window_high: float


SIZE_CLASSES: dict[PopupSize, SizeClass] = {
    PopupSize.SMALL: SizeClass(pages_wide=0.70, window_high=0.28),
    PopupSize.MEDIUM: SizeClass(pages_wide=0.85, window_high=0.42),
    PopupSize.LARGE: SizeClass(pages_wide=0.95, window_high=0.80),
}

# However wide a page would be, a popup leaves this much of a narrow window showing.
MAX_WINDOW_WIDTH_FRACTION = 0.95


def popup_size(
    size: PopupSize,
    window_width: float,
    window_height: float,
    page_aspect_ratio: float = COMIC_PAGE_ASPECT_RATIO,
) -> tuple[float, float]:
    """Return a popup's width and height on a window of the given size.

    Args:
        size: The popup's size class.
        window_width: The window's width.
        window_height: The window's height.
        page_aspect_ratio: A page's height over its width.

    Returns:
        The popup's width and height, in the window's units.

    """
    size_class = SIZE_CLASSES[size]
    page_width = window_height / page_aspect_ratio
    width = min(size_class.pages_wide * page_width, MAX_WINDOW_WIDTH_FRACTION * window_width)
    return width, size_class.window_high * window_height
