"""How far to scroll a list so the rows opened under a row show, the row kept in view.

Shared by the tree view and the Main Index: a row opened near the bottom of the view
put its new rows below it, out of sight, and the press seemed to do nothing.
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
