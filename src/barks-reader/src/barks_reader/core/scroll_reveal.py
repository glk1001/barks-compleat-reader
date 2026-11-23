"""How far to scroll a list so the rows opened under a row show, the row kept in view.

Shared by the tree view and the index screens through `ui/tree_scroll_pinner.py`: a
row opened near the bottom of the view put its new rows below it, out of sight, and
the press seemed to do nothing; and Kivy keeps the scroll position as a share of the
content's height, so the rows opening or shutting under a row moved it.
The pinner's own sums are here too: when a list's height has settled (`HeightSettle`),
whether a correction is worth a move, where a reveal's glide ends, and which rows are
the first shown under an open one.
Kivy-free, so the arithmetic can be tested without a window.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

# The space, in dp, left under opened items scrolled into view.
REVEAL_PADDING = 10

# How far Up or Down moves a popup's scrolling text, as a share of what shows of it.
KEY_SCROLL_SHARE = 0.25

# A list's height has settled once it has held, to within this, for this many frames
# running; a pin waits this many frames for that (about 3 seconds at 60 a second).
SETTLE_HEIGHT_TOLERANCE = 0.5
SETTLE_STABLE_FRAMES = 2
MAX_SETTLE_FRAMES = 180
# The least a correction or a reveal moves the list: under it, nothing shows for it.
LEAST_MOVE_PX = 0.5


class OpenableRow(Protocol):
    """A row with rows under it, shown when it is open (a tree view's node)."""

    @property
    def nodes(self) -> list:  # the rows under it, in the order shown
        """The rows under it."""
        ...

    @property
    def is_open(self) -> bool:
        """Whether they show."""
        ...


@dataclass(slots=True)
class HeightSettle:
    """Watches a list's height, frame by frame, until it has stopped changing.

    Attributes:
        frames_waited: How many frames the watch has waited on.
        last_height: The height at the last frame looked at; -1 before the first.
        stable_frames: How many frames running the height has held.

    """

    frames_waited: int = 0
    last_height: float = -1.0
    stable_frames: int = 0

    def has_settled(self, content_height: float, view_height: float) -> bool:
        """Return whether the list's height has held for enough frames, this one counted.

        A list or a view with no height yet is neither stable nor a change: it is
        waited on, and dividing by it would be an error.
        """
        if content_height <= 1 or view_height <= 1:
            return False
        held = abs(content_height - self.last_height) < SETTLE_HEIGHT_TOLERANCE
        self.stable_frames = self.stable_frames + 1 if held else 0
        self.last_height = content_height
        return self.stable_frames >= SETTLE_STABLE_FRAMES

    def may_wait_another_frame(self) -> bool:
        """Count a frame waited, and return whether the watch goes on or gives up."""
        self.frames_waited += 1
        return self.frames_waited < MAX_SETTLE_FRAMES


def is_worth_a_move(scroll_y: float, wanted_scroll_y: float, scrollable_px: float) -> bool:
    """Return whether moving a list from `scroll_y` to `wanted_scroll_y` moves it a pixel's half."""
    return abs(wanted_scroll_y - scroll_y) * scrollable_px >= LEAST_MOVE_PX


def scroll_y_after_reveal(scroll_y: float, reveal_px: float, scrollable_px: float) -> float:
    """Return the ``scroll_y`` a reveal glides to: the content `reveal_px` further up."""
    return held_in_scroll_range(scroll_y - reveal_px / scrollable_px)


def first_shown_rows[R: OpenableRow](owner: R, count: int) -> list[R]:
    """Return the first `count` rows under an open row, in the order the list shows them.

    A row under it that is open itself is followed by its own rows, and so on down.
    """
    rows: list[R] = []

    def walk(row: R) -> None:
        for child in row.nodes:
            if len(rows) >= count:
                return
            rows.append(child)
            if child.is_open:
                walk(child)

    walk(owner)
    return rows


def held_in_scroll_range(scroll_y: float) -> float:
    """Return `scroll_y` held within a scroll view's range: 0, its foot, to 1, its top."""
    return min(1.0, max(0.0, scroll_y))


def scroll_y_after_key(
    *, scroll_y: float, view_height: float, content_height: float, up: bool
) -> float:
    """Return the ``scroll_y`` after Up or Down moves scrolling text a share of what shows.

    Args:
        scroll_y: Where the text is now: 1 at its top, 0 at its foot.
        view_height: The height that shows of the text.
        content_height: The text's whole height.
        up: Whether the key was Up, towards the text's top.

    Returns:
        The ``scroll_y``, 0 to 1; the one given when the text all shows.

    """
    hidden = content_height - view_height
    if hidden <= 0:
        return scroll_y
    step = KEY_SCROLL_SHARE * view_height / hidden
    return held_in_scroll_range(scroll_y + (step if up else -step))


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


def reveal_distance_with_owner_pinned(
    *,
    view_bottom: float,
    view_top: float,
    first_item_bottom: float,
    last_item_bottom: float,
    owner_top: float,
    pinned_owner_top: float,
    padding: float,
) -> float:
    """Return how far up to move a list so the first items under a pinned row show.

    The row is not yet back where it is pinned: the items are measured as they will be
    once it is, the same distance below it as they are now.

    Args:
        view_bottom: The scroll view's bottom.
        view_top: The scroll view's top.
        first_item_bottom: The bottom, as it is now, of the first item under the row.
        last_item_bottom: The bottom, as it is now, of the last item to show.
        owner_top: The row's top as it is now.
        pinned_owner_top: The row's top once it is back where it is pinned.
        padding: The space to leave under the items.

    Returns:
        Nothing while the first item shows whole, the row then having no need to move;
        else the distance that shows them all (`reveal_distance`).

    """
    back_to_the_pin = pinned_owner_top - owner_top
    if first_item_bottom + back_to_the_pin >= view_bottom:
        return 0.0
    return reveal_distance(
        view_bottom=view_bottom,
        view_top=view_top,
        items_bottom=last_item_bottom + back_to_the_pin,
        owner_top=pinned_owner_top,
        padding=padding,
    )


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
    return held_in_scroll_range(1.0 - scrolled / scrollable)
