"""Keep an expanding tree row visually pinned while its children populate.

`TreeScrollPinner` hides the per-frame layout-stabilization loop — the pixel
math that cancels the scroll "jump" when a tree node lazily creates its children,
then scrolls the children into view when they opened below the window's edge —
behind a single call. `TreeViewManager` owns *which* node to expand and *when*;
this module owns *how* the viewport stays put while it happens.

The collaborators arrive as callables so the loop can be driven deterministically
in tests:
- `get_scroll_view` returns the live `ScrollView` whose content height changes.
- `on_settled` is invoked once the row has stabilized (or the attempt gives up);
  `TreeViewManager` wires it to the collapse overlay's `end_suppression`.
- `schedule_once` defaults to Kivy's `Clock.schedule_once`; tests inject a fake.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from comic_utils.timing import Timing
from kivy.clock import Clock
from kivy.metrics import dp
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.reader_formatter import get_clean_text_without_extra
from barks_reader.core.scroll_reveal import REVEAL_PADDING, reveal_distance
from barks_reader.core.tap_targets import settling_began, settling_ended

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.scrollview import ScrollView
    from kivy.uix.widget import Widget

    from .tree_view_nodes import ButtonTreeViewNode


class TreeScrollPinner:
    """Pin an expanding parent row's on-screen position while its children load."""

    # ~3 seconds worst-case @ 60fps before giving up on stabilization.
    _MAX_SETTLE_FRAMES = 180

    def __init__(
        self,
        get_scroll_view: Callable[[], ScrollView],
        on_settled: Callable[[], None],
        *,
        schedule_once: Callable[[Callable[[float], None], float], object] = Clock.schedule_once,
    ) -> None:
        self._get_scroll_view = get_scroll_view
        self._on_settled = on_settled
        self._schedule_once = schedule_once
        # Bumped by each pin and each cancel: only the latest pin, uncancelled, reveals.
        self._reveal_generation = 0

    def cancel_pending_reveals(self) -> None:
        """Keep the pins under way from scrolling their children into view.

        For when the tree is placed otherwise: the app opening a saved or wanted node
        and its parents, or scrolling to one, places the tree as it wants it.
        """
        self._reveal_generation += 1

    def pin_while_populating(
        self, parent_node: ButtonTreeViewNode, *, populate: Callable[[], None] | None
    ) -> None:
        """Keep *parent_node*'s row visually pinned while its children are created.

        Records the parent row's current offset from the top of the viewport,
        optionally runs *populate* to lazily create the children, then schedules a
        settle loop that nudges ``scroll_y`` so the row stays at that same offset
        (making expansion behave like a dropdown rather than jumping the list).
        Children that would open below the viewport are scrolled up into it, as far
        as the row's staying in view allows, unless a later pin or
        `cancel_pending_reveals` has come first.
        `on_settled` runs when the row has stabilized or the attempt gives up.
        """
        scroll_view = self._get_scroll_view()

        # Container inside the ScrollView (the thing whose height changes).
        if not scroll_view.children:
            return

        timing = Timing()
        try:
            # Offset of the parent row's *top* relative to the ScrollView's top.
            sv_top_win_y = scroll_view.to_window(0, scroll_view.top)[1]
            parent_top_win_y = parent_node.to_window(0, parent_node.top)[1]
            target_offset_px = parent_top_win_y - sv_top_win_y  # keep this constant

            # Optionally populate children now (lazy load for first expand).
            if populate is not None:
                populate()

            self._reveal_generation += 1
            checks: dict[str, float] = {
                "count": 0,
                "last_h": -1,
                "stable": 0,
                "reveal_generation": self._reveal_generation,
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
            logger.debug(
                f"Populated node '{get_clean_text_without_extra(parent_node.text)}'"
                f" in {timing.get_elapsed_time_with_unit()}."
            )

    def _stabilize_after_layout(
        self,
        _dt: float,
        parent_node: ButtonTreeViewNode,
        scroll_view: ScrollView,
        target_offset_px: float,
        checks: dict[str, float],
    ) -> None:
        # If user collapsed or navigated away, stop.
        if not parent_node.is_open:
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
        if (cont_h <= 1) or (viewport_h <= 1) or (cont_h <= viewport_h):
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

        # Current offset (parent top relative to SV top) *after* expansion
        sv_top = scroll_view.to_window(0, scroll_view.top)[1]
        new_parent_top = parent_node.to_window(0, parent_node.top)[1]
        current_offset_px = new_parent_top - sv_top

        # How far did the parent drift? Positive means it moved DOWN on screen.
        delta_px = current_offset_px - target_offset_px

        # Then how much further up to show the children, the parent pinned back first.
        reveal_px = (
            self._get_reveal_px(
                parent_node, scroll_view, sv_top, new_parent_top, sv_top + target_offset_px
            )
            if checks["reveal_generation"] == self._reveal_generation
            else 0.0
        )
        delta_px -= reveal_px
        if abs(delta_px) < 0.5:  # noqa: PLR2004
            self._settled(checks)
            return  # nothing to adjust

        # Convert pixel delta to normalized scroll_y delta:
        #  - Kivy uses scroll_y 0..1 where 1 = top, 0 = bottom.
        #  - Moving content up by +delta_px means increase scroll_y.
        # The content is taller than the viewport here (checked above), so this divides
        # by a positive height.
        delta_norm = delta_px / (cont_h - viewport_h)
        new_scroll_y = self._clamp01(scroll_view.scroll_y + delta_norm)

        # Apply in one shot (no animation to avoid visible bounce)
        scroll_view.scroll_y = new_scroll_y
        if reveal_px > 0:
            logger.debug(
                log_markers.TREE_CHILDREN_REVEALED.format(
                    name=get_clean_text_without_extra(parent_node.text)
                )
            )
        self._settled(checks)

    @staticmethod
    def _get_reveal_px(
        parent_node: ButtonTreeViewNode,
        scroll_view: ScrollView,
        sv_top: float,
        parent_top: float,
        pinned_parent_top: float,
    ) -> float:
        """Return how far up to scroll so the parent's shown children are in the viewport.

        Measured with the parent back at its pinned top, `pinned_parent_top`, its
        children (and theirs, where open) the same distance below it as they are now.
        """
        if not parent_node.nodes:
            return 0.0
        last_node = _get_last_shown_node(parent_node)
        items_bottom = last_node.to_window(0, last_node.y)[1] - parent_top + pinned_parent_top
        return reveal_distance(
            view_bottom=scroll_view.to_window(0, scroll_view.y)[1],
            view_top=sv_top,
            items_bottom=items_bottom,
            owner_top=pinned_parent_top,
            padding=dp(REVEAL_PADDING),
        )

    def _settled(self, checks: dict[str, float]) -> None:
        settling_ended(checks)
        self._on_settled()

    @staticmethod
    def _clamp01(v: float) -> float:
        return 0.0 if v < 0.0 else (min(v, 1.0))


def _get_last_shown_node(parent_node: ButtonTreeViewNode) -> Widget:
    """Return the lowest row under an open parent: its last child, or, if open, that one's."""
    node: Widget = parent_node.nodes[-1]
    while node.is_open and node.nodes:
        node = node.nodes[-1]
    return node
