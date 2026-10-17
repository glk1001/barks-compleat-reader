"""How far to scroll a list so the rows opened under a row show, the row kept in view.

Shared by the tree view and the Main Index: a row opened near the bottom of the view
put its new rows below it, out of sight, and the press seemed to do nothing. Also the
scroll that keeps a row where it is while the rows under it open or shut.
Kivy-free, so the distance can be tested without a window.
"""

from __future__ import annotations

# The space, in dp, left under opened items scrolled into view.
REVEAL_PADDING = 10


def reveal_distance(
    *, view_bottom: float, view_top: float, items_bottom: float, owner_top: float, padding: float
) -> float:
    """Return how far to move a list's content up to show the items opened below a row.

    Enough to bring the items' bottom (and `padding`) into view, but never so far that
    their row leaves it: items taller than the view end with the row at its top.

    Args:
        view_bottom: The scroll view's bottom.
        view_top: The scroll view's top.
        items_bottom: The opened items' bottom.
        owner_top: The top of the row they opened under.
        padding: The space to leave under the items.

    Returns:
        The distance, in pixels, or 0 when the items already show.

    """
    hidden_below = view_bottom - items_bottom + padding
    return max(0.0, min(hidden_below, view_top - owner_top))


def scroll_y_keeping_row(
    *,
    row_from_content_top: float,
    row_from_view_top: float,
    content_height: float,
    view_height: float,
) -> float | None:
    """Return the ``scroll_y`` that shows a row its same distance below the view's top.

    Kivy keeps ``scroll_y`` as a share of the scrollable height, so content that grows or
    shrinks under a row moves every row on screen, the row too, unless ``scroll_y`` moves
    with it. Clamped: too near the content's end, the row can only move.

    Args:
        row_from_content_top: The row's top, measured down from the content's top.
        row_from_view_top: Where the row's top is to be, measured down from the view's top.
        content_height: The content's height.
        view_height: The view's height.

    Returns:
        The ``scroll_y``, 0 to 1, or None when content no taller than the view does not
        scroll (Kivy shows it from its top, whatever the ``scroll_y``).

    """
    scrollable = content_height - view_height
    if scrollable <= 0:
        return None
    scrolled = row_from_content_top - row_from_view_top
    return min(1.0, max(0.0, 1.0 - scrolled / scrollable))
