"""Page metrics for the "By the Numbers" page, in design pixels.

The page is a fixed-aspect comic-page box, like the Introduction document reader,
and it must fit on one screen with nothing to scroll. That is guaranteed
arithmetically rather than by measurement: **every dimension is a constant times
one scalar**, and the scalar is the page's width over a reference width. Because
the box has a fixed aspect ratio, a layout that fits at the reference width fits
at every width, and on a 4K TV the whole page scales up together.

Two conventions here are deliberate and differ from the rest of the app:

* The numbers are plain floats, never ``dp()`` or ``sp()``. Kivy's window
  dimensions are already physical pixels, so the width ratio absorbs display
  density on its own; applying ``sp()`` on top would count DPI twice and break
  the exact fit. The cost is that this one page ignores the user's system font
  scale - like a comic page, its composition sets its own scale.
* The type sizes are not read from ``FontManager``. That is a two-step ladder
  (``LOW_RES``/``HI_RES``), and two steps cannot make a fixed composition fit at
  an arbitrary window height. The ``DESIGN`` values below are instead copied from
  the ``LOW_RES_FONTS`` role that plays the same part elsewhere in the app, so the
  page stays a strict similarity transform of the app's own scale. The comments
  record which role each came from, and a test pins them.

This module is deliberately Kivy-free: it is what lets the "does it fit" check be
an ordinary unit test instead of something only a running window can answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .corpus_stats import SectionShape, StatSection

# The page box width this design was measured at, in pixels. The app window is
# locked to the comic-page aspect ratio, so the page box width is effectively the
# window width; this is the narrow end of the range seen in practice.
REFERENCE_PAGE_WIDTH = 782.0

# Fractions of the page width. The column figure is what every label and value has
# to fit inside, and is the constraint that decides the type size.
PAGE_PADDING_FRACTION = 0.025
COLUMN_GUTTER_FRACTION = 0.03


@dataclass(frozen=True, slots=True)
class PageMetrics:
    """Every size on the page, in design pixels at ``REFERENCE_PAGE_WIDTH``."""

    headline: float
    standfirst: float
    heading: float
    row: float
    footnote: float

    headline_height: float
    standfirst_height: float
    opening_gap: float
    heading_height: float
    row_height: float
    footnote_line_height: float
    section_gap: float
    label_value_gap: float


DESIGN = PageMetrics(
    # Type sizes. These started as the LOW_RES_FONTS roles that play the same part
    # elsewhere in the app, then came down a notch: at the sizes the two-column
    # layout allows, matching the app's roles exactly read heavier than the rest of
    # the reader. They keep the app's proportions, a step down in absolute size.
    headline=30.0,
    standfirst=14.0,
    heading=18.0,
    # The body size has a hard ceiling as well as a look: the longest label and its
    # value must sit side by side in one column. At the reference width, 22.0 already
    # measured 341px of the 360px available, so this can come down but not up.
    row=19.0,
    footnote=12.0,
    # Vertical rhythm.
    headline_height=60.0,
    standfirst_height=34.0,
    opening_gap=16.0,
    heading_height=44.0,
    row_height=38.0,
    footnote_line_height=22.0,
    section_gap=18.0,
    label_value_gap=16.0,
)

# A prose row - one whose value is a name rather than a figure - stacks a quiet
# label over a value that wraps to two lines in a column this narrow.
PROSE_ROW_HEIGHT_UNITS = 3.0

# The floor below which the page stops shrinking and is allowed to clip rather
# than become unreadable. Well under any window the app itself permits.
MIN_SCALE = 0.5


def scale_for(page_width: float) -> float:
    """Return the scalar every design pixel on the page is multiplied by.

    Args:
        page_width: The width of the page box, in pixels.

    Returns:
        The scale factor, floored at ``MIN_SCALE``.

    """
    return max(MIN_SCALE, page_width / REFERENCE_PAGE_WIDTH)


def column_width(page_width: float) -> float:
    """Return the width of one of the two columns, in pixels.

    Args:
        page_width: The width of the page box, in pixels.

    Returns:
        The usable width of a single column, after page padding and the gutter.

    """
    padding = 2.0 * PAGE_PADDING_FRACTION * page_width
    gutter = COLUMN_GUTTER_FRACTION * page_width
    return (page_width - padding - gutter) / 2.0


# The left column takes the first three sections and the right the rest, which keeps
# the reading order of the single-column page and happens to balance the two columns
# to within about 5%.
COLUMN_SPLIT = 3


def split_columns(
    sections: Sequence[StatSection],
) -> tuple[Sequence[StatSection], Sequence[StatSection]]:
    """Split the sections into the left and right columns.

    Args:
        sections: Every section to render, in reading order.

    Returns:
        The ``(left, right)`` column contents.

    """
    return sections[:COLUMN_SPLIT], sections[COLUMN_SPLIT:]


def opening_height() -> float:
    """Return the height of the two opening lines plus the gap beneath them."""
    return DESIGN.headline_height + DESIGN.standfirst_height + DESIGN.opening_gap


def section_height(section: StatSection) -> float:
    """Return the design height of one rendered section.

    Args:
        section: The section to measure.

    Returns:
        Its height in design pixels, counting a two-line footnote so that a
        footnote which happens to wrap cannot push a column past the fold.

    """
    height = DESIGN.heading_height
    for row in section.rows:
        height += DESIGN.row_height * (PROSE_ROW_HEIGHT_UNITS if row.prose else 1.0)
    if section.footnote:
        height += 2.0 * DESIGN.footnote_line_height
    return height


def reserved_height(shape: SectionShape) -> float:
    """Return the design height to reserve for a section not yet computed.

    Args:
        shape: The declared shape of the pending section.

    Returns:
        Its height in design pixels. The dialogue section is reserved at this
        height up front so the late background scan fills the slot in place
        rather than reflowing a page that cannot scroll.

    """
    return (
        DESIGN.heading_height
        + (DESIGN.row_height * shape.num_rows)
        + (DESIGN.footnote_line_height * shape.footnote_lines)
    )


def column_height(sections: Sequence[StatSection], reserved: float = 0.0) -> float:
    """Return the design height of one column of sections.

    Args:
        sections: The sections stacked in this column, in order.
        reserved: Extra height for a section whose figures have not arrived yet.

    Returns:
        The column's height in design pixels, including the gap after each
        section.

    """
    height = sum(section_height(s) + DESIGN.section_gap for s in sections)
    if reserved:
        height += reserved + DESIGN.section_gap
    return height


def content_height(
    left: Sequence[StatSection], right: Sequence[StatSection], reserved: float = 0.0
) -> float:
    """Return the design height the whole page needs.

    Args:
        left: The sections in the left column.
        right: The sections in the right column.
        reserved: Height reserved in the right column for the pending section.

    Returns:
        The opening plus the taller of the two columns, plus page padding.

    """
    columns = max(column_height(left), column_height(right, reserved))
    padding = 2.0 * PAGE_PADDING_FRACTION * REFERENCE_PAGE_WIDTH
    return opening_height() + columns + padding
