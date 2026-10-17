"""Keep an expanding or collapsing tree row visually pinned.

`TreeScrollPinner` hides the pixel math that cancels the scroll "jump" when a tree
node lazily creates its children or collapses them — a hold that moves ``scroll_y``
in the very layout pass that changes the tree's height, then a per-frame
stabilization loop that checks the row settled where it was — and then glides the
first children into view when they opened below the window's edge, behind a single
call. `TreeViewManager` owns *which*
node to expand and *when*; this module owns *how* the viewport stays put while it
happens.

The collaborators arrive as callables so the loop can be driven deterministically
in tests:
- `get_scroll_view` returns the live `ScrollView` whose content height changes.
- `on_settled` is invoked once the row has stabilized (or the attempt gives up);
  `TreeViewManager` wires it to the collapse overlay's `end_suppression`.
- `schedule_once` defaults to Kivy's `Clock.schedule_once`; tests inject a fake.
- `glide` animates ``scroll_y`` to a value, then calls back with whether it got
  there; tests inject one that jumps there.
- `stop_glides` stops every ``scroll_y`` animation on the view (a glide of ours
  then calls back that it did not get there); tests inject a fake.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from comic_utils.timing import Timing
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.reader_formatter import get_clean_text_without_extra
from barks_reader.core.scroll_reveal import (
    REVEAL_PADDING,
    reveal_distance,
    scroll_y_keeping_row,
)
from barks_reader.core.tap_targets import settling_began, settling_ended

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.scrollview import ScrollView
    from kivy.uix.widget import Widget

    from .tree_view_nodes import ButtonTreeViewNode


# How many of a node's rows an expansion near the viewport's bottom scrolls into view,
# and how long that scroll takes: a glide shows where the rows went, a jump would not.
REVEAL_ROWS = 3
REVEAL_GLIDE_SECONDS = 0.2
# How near its target a glide's last `scroll_y` must come to count as having got there.
_REACHED_TOL = 1e-6


class TreeScrollPinner:
    """Pin an expanding or collapsing parent row's on-screen position."""

    # ~3 seconds worst-case @ 60fps before giving up on stabilization.
    _MAX_SETTLE_FRAMES = 180

    def __init__(
        self,
        get_scroll_view: Callable[[], ScrollView],
        on_settled: Callable[[], None],
        *,
        schedule_once: Callable[[Callable[[float], None], float], object] = Clock.schedule_once,
        glide: Callable[[ScrollView, float, Callable[[bool], None]], None] | None = None,
        stop_glides: Callable[[ScrollView], None] | None = None,
    ) -> None:
        self._get_scroll_view = get_scroll_view
        self._on_settled = on_settled
        self._schedule_once = schedule_once
        self._glide = glide or _glide_scroll_y
        self._stop_glides = stop_glides or _stop_scroll_y_animations
        # Bumped by each pin and each cancel: only the latest pin, uncancelled, reveals.
        self._reveal_generation = 0
        # Bumped by `cancel_pending_pins`: a pin from before it neither corrects nor reveals.
        self._pin_generation = 0
        # Counts the pins: only the latest one's settling has `on_settled` to say.
        self._pin_serial = 0
        # The latest pin's hold on the tree's height: the container and the binding's uid.
        self._hold: tuple[Widget, int] | None = None

    def cancel_pending_reveals(self) -> None:
        """Keep the pins under way from scrolling their children into view.

        For when the tree is placed otherwise: the app opening a saved or wanted node
        and its parents places the tree as it wants it. The pins still keep their
        rows where they were.
        """
        self._reveal_generation += 1

    def cancel_pending_pins(self) -> None:
        """Let the pins under way go: they neither keep their rows put nor reveal.

        For a scroll to a node, which places the tree itself: a pin's one-shot
        correction would land in the middle of the scroll, and the scroll's animation
        would write over it. A glide of ours still in flight stops where it is.
        """
        self._pin_generation += 1
        self._reveal_generation += 1
        self._release_hold()
        self._stop_glides(self._get_scroll_view())

    def pin_while_populating(
        self, parent_node: ButtonTreeViewNode, *, populate: Callable[[], None] | None
    ) -> None:
        """Keep *parent_node*'s row visually pinned while its children are created.

        Records the parent row's current offset from the top of the viewport, holds
        the row at that offset through the tree's height change (see `_hold_row`),
        optionally runs *populate* to lazily create the children, then schedules a
        settle loop that checks the row stayed there and corrects any drift (making
        expansion behave like a dropdown rather than jumping the list).
        Should even the first child open below the viewport, the tree then glides up
        to show the first `REVEAL_ROWS` rows, as far as the row's staying in view
        allows, unless a later pin or `cancel_pending_reveals` has come first.
        `on_settled` runs when the row has stabilized or the attempt gives up.
        """
        self._pin(parent_node, populate=populate, expanding=True)

    def pin_while_collapsing(self, parent_node: ButtonTreeViewNode) -> None:
        """Keep *parent_node*'s row where it is on screen as its children go.

        Kivy keeps the scroll position as a share of the content's height, so a
        shorter tree would otherwise move every row, the collapsed one too. Only the
        end of the tree, when there is no longer enough below it, moves it down.
        """
        self._pin(parent_node, populate=None, expanding=False)

    def _pin(
        self,
        parent_node: ButtonTreeViewNode,
        *,
        populate: Callable[[], None] | None,
        expanding: bool,
    ) -> None:
        scroll_view = self._get_scroll_view()

        # Container inside the ScrollView (the thing whose height changes).
        if not scroll_view.children:
            return

        self._pin_serial += 1
        # A glide or scroll still in flight would write over this pin's correction,
        # frame by frame: the row stays where the stop leaves it.
        self._stop_glides(scroll_view)

        timing = Timing()
        try:
            # Offset of the parent row's *top* relative to the ScrollView's top.
            sv_top_win_y = scroll_view.to_window(0, scroll_view.top)[1]
            parent_top_win_y = parent_node.to_window(0, parent_node.top)[1]
            target_offset_px = parent_top_win_y - sv_top_win_y  # keep this constant
            self._hold_row(parent_node, scroll_view, -target_offset_px)

            # Optionally populate children now (lazy load for first expand).
            if populate is not None:
                try:
                    populate()
                except BaseException:
                    # No settle loop will let the hold go: left, it would put the row
                    # back at this offset on the tree's next change of height.
                    self._release_hold()
                    raise

            self._reveal_generation += 1
            checks: dict[str, float] = {
                "count": 0,
                "last_h": -1,
                "stable": 0,
                "expanding": expanding,
                "reveal_generation": self._reveal_generation,
                "pin_generation": self._pin_generation,
                "serial": self._pin_serial,
            }
            # Until the correction lands the tree is not where it will be: a GUI
            # test's tap-targets request waits (barks_reader.core.tap_targets).
            settling_began(checks)

            self._schedule_once(
                lambda dt: self._stabilize_after_layout(
                    dt, parent_node, scroll_view, target_offset_px, checks
                ),
                0,
            )
        finally:
            if expanding:
                logger.debug(
                    f"Populated node '{get_clean_text_without_extra(parent_node.text)}'"
                    f" in {timing.get_elapsed_time_with_unit()}."
                )

    def _hold_row(
        self, parent_node: ButtonTreeViewNode, scroll_view: ScrollView, row_from_view_top: float
    ) -> None:
        """Keep *parent_node*'s row `row_from_view_top` below the view's top as the tree resizes.

        Kivy keeps ``scroll_y`` as a share of the content's height, so a taller or shorter
        tree moves every row for the frames until a correction lands: a jump, and back.
        Moved in the tree's height change instead, ``scroll_y`` reaches the screen with
        the layout that changed it: the tree lays its rows out, then sets its height, and
        the scroll view places it after, all before the frame is drawn.
        """
        self._release_hold()
        cont = scroll_view.children[0]
        last_height = cont.height

        def on_height(_cont: Widget, height: float) -> None:
            nonlocal last_height
            old_height, last_height = last_height, height
            if parent_node.parent is None:  # gone from the tree, repopulated
                return
            # The rows were just laid out down from the tree's old top.
            scroll_y = scroll_y_keeping_row(
                row_from_content_top=cont.y + old_height - parent_node.top,
                row_from_view_top=row_from_view_top,
                content_height=height,
                view_height=scroll_view.height,
            )
            if scroll_y is not None:
                scroll_view.scroll_y = scroll_y

        self._hold = (cont, cont.fbind("height", on_height))

    def _release_hold(self) -> None:
        if self._hold is not None:
            cont, uid = self._hold
            cont.unbind_uid("height", uid)
            self._hold = None

    def _stabilize_after_layout(
        self,
        _dt: float,
        parent_node: ButtonTreeViewNode,
        scroll_view: ScrollView,
        target_offset_px: float,
        checks: dict[str, float],
    ) -> None:
        expanding = bool(checks["expanding"])
        # Let go (the tree is being placed otherwise), or toggled back: stop.
        if checks["pin_generation"] != self._pin_generation or parent_node.is_open != expanding:
            self._settled(checks)
            return

        def _resched() -> None:
            checks["count"] += 1
            if checks["count"] < self._MAX_SETTLE_FRAMES:
                self._schedule_once(
                    lambda dt: self._stabilize_after_layout(
                        dt, parent_node, scroll_view, target_offset_px, checks
                    ),
                    0,
                )
            else:
                self._settled(checks)

        if not scroll_view.children:
            _resched()
            return

        cont = scroll_view.children[0]
        viewport_h = scroll_view.height
        cont_h = cont.height

        # Require non-trivial content to avoid div-by-zero and false positives.
        if (cont_h <= 1) or (viewport_h <= 1):
            _resched()
            return

        # Check stabilization of container height
        if abs(cont_h - checks["last_h"]) < 0.5:  # noqa: PLR2004
            checks["stable"] += 1
        else:
            checks["stable"] = 0
        checks["last_h"] = cont_h

        if checks["stable"] < 2:  # noqa: PLR2004
            _resched()
            return

        self._correct_and_reveal(parent_node, scroll_view, target_offset_px, checks)

    def _correct_and_reveal(
        self,
        parent_node: ButtonTreeViewNode,
        scroll_view: ScrollView,
        target_offset_px: float,
        checks: dict[str, float],
    ) -> None:
        """Move the settled tree's parent row back to its pinned offset, then reveal."""
        cont = scroll_view.children[0]
        viewport_h = scroll_view.height
        cont_h = cont.height
        expanding = bool(checks["expanding"])

        # Where the parent's row is now, before any correction moves the tree.
        sv_top = scroll_view.to_window(0, scroll_view.top)[1]
        new_parent_top = parent_node.to_window(0, parent_node.top)[1]

        # The tree has settled: its rows are laid out down from its top as it is. Read
        # from the tree, not the window: a correction this frame has moved scroll_y,
        # not yet the rows, so pins settling together each place the tree afresh.
        scroll_y = scroll_y_keeping_row(
            row_from_content_top=cont.y + cont_h - parent_node.top,
            row_from_view_top=-target_offset_px,
            content_height=cont_h,
            view_height=viewport_h,
        )
        # A tree no taller than the viewport does not scroll: nothing to pin.
        if scroll_y is None:
            self._settled(checks)
            return

        scrollable_px = cont_h - viewport_h
        if abs(scroll_y - scroll_view.scroll_y) * scrollable_px >= 0.5:  # noqa: PLR2004
            # Apply in one shot: the drift is the layout's, not the reader's to see.
            scroll_view.scroll_y = scroll_y

        # Then, the parent pinned back, how far up to show the first children.
        reveal_px = (
            self._get_reveal_px(
                parent_node, scroll_view, sv_top, new_parent_top, sv_top + target_offset_px
            )
            if expanding and checks["reveal_generation"] == self._reveal_generation
            else 0.0
        )
        if reveal_px < 0.5:  # noqa: PLR2004
            self._settled(checks)
            return

        name = get_clean_text_without_extra(parent_node.text)

        def _revealed(reached: bool) -> None:
            # A glide stopped short (a scroll to a node, a new pin) showed nothing.
            if reached:
                logger.debug(log_markers.TREE_CHILDREN_REVEALED.format(name=name))
            self._settled(checks)

        self._glide(
            scroll_view,
            self._clamp01(scroll_view.scroll_y - reveal_px / scrollable_px),
            _revealed,
        )

    @staticmethod
    def _get_reveal_px(
        parent_node: ButtonTreeViewNode,
        scroll_view: ScrollView,
        sv_top: float,
        parent_top: float,
        pinned_parent_top: float,
    ) -> float:
        """Return how far up to scroll so the parent's first shown rows are in the viewport.

        Nothing while its first row shows whole: the parent then need not move. Else
        enough for the first `REVEAL_ROWS` rows (its children, and theirs where open),
        measured with the parent back at its pinned top, `pinned_parent_top`, its rows
        the same distance below it as they are now.
        """
        rows = _get_first_shown_rows(parent_node, REVEAL_ROWS)
        if not rows:
            return 0.0
        view_bottom = scroll_view.to_window(0, scroll_view.y)[1]

        def pinned_bottom(row: Widget) -> float:
            return row.to_window(0, row.y)[1] - parent_top + pinned_parent_top

        if pinned_bottom(rows[0]) >= view_bottom:
            return 0.0
        return reveal_distance(
            view_bottom=view_bottom,
            view_top=sv_top,
            items_bottom=pinned_bottom(rows[-1]),
            owner_top=pinned_parent_top,
            padding=dp(REVEAL_PADDING),
        )

    def _settled(self, checks: dict[str, float]) -> None:
        settling_ended(checks)
        # A pin a newer one has stopped leaves the overlay's suppression to that one:
        # lifted now, the overlay would check the tree before its layout has settled.
        if checks["serial"] == self._pin_serial:
            self._release_hold()
            self._on_settled()

    @staticmethod
    def _clamp01(v: float) -> float:
        return 0.0 if v < 0.0 else (min(v, 1.0))


def _glide_scroll_y(
    scroll_view: ScrollView, scroll_y: float, on_done: Callable[[bool], None]
) -> None:
    """Scroll `scroll_view` to `scroll_y` over `REVEAL_GLIDE_SECONDS`, then call `on_done`.

    `on_done` gets whether the glide reached `scroll_y`: Kivy completes a stopped
    animation too (its own `scroll_to` stops every one on the view), short of its end.
    """
    _stop_scroll_y_animations(scroll_view)
    glide = Animation(scroll_y=scroll_y, duration=REVEAL_GLIDE_SECONDS, transition="out_quad")
    glide.bind(
        on_complete=lambda *_args: on_done(abs(scroll_view.scroll_y - scroll_y) < _REACHED_TOL)
    )
    glide.start(scroll_view)


def _stop_scroll_y_animations(scroll_view: ScrollView) -> None:
    """Stop every ``scroll_y`` animation on `scroll_view` where it is.

    Stopped, not cancelled: a glide of ours still completes, and settles its pin.
    """
    Animation.stop_all(scroll_view, "scroll_y")


def _get_first_shown_rows(parent_node: ButtonTreeViewNode, count: int) -> list[Widget]:
    """Return the first `count` rows under an open parent, in the order the tree shows them."""
    rows: list[Widget] = []

    def walk(node: Widget) -> None:
        for child in node.nodes:
            if len(rows) >= count:
                return
            rows.append(child)
            if child.is_open:
                walk(child)

    walk(parent_node)
    return rows
