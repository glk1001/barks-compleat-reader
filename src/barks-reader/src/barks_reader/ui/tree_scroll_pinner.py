"""Keep an expanding tree row visually pinned while its children populate.

`TreeScrollPinner` hides the per-frame layout-stabilization loop — the pixel
math that cancels the scroll "jump" when a tree node lazily creates its children
— behind a single call. `TreeViewManager` owns *which* node to expand and *when*;
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
from loguru import logger

from barks_reader.core.reader_formatter import get_clean_text_without_extra

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.scrollview import ScrollView

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

    def pin_while_populating(
        self, parent_node: ButtonTreeViewNode, *, populate: Callable[[], None] | None
    ) -> None:
        """Keep *parent_node*'s row visually pinned while its children are created.

        Records the parent row's current offset from the top of the viewport,
        optionally runs *populate* to lazily create the children, then schedules a
        settle loop that nudges ``scroll_y`` so the row stays at that same offset
        (making expansion behave like a dropdown rather than jumping the list).
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

            checks: dict[str, float] = {"count": 0, "last_h": -1, "stable": 0}

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
            self._on_settled()
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
                self._on_settled()

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
        if abs(delta_px) < 0.5:  # noqa: PLR2004
            self._on_settled()
            return  # nothing to adjust

        # Convert pixel delta to normalized scroll_y delta:
        #  - Kivy uses scroll_y 0..1 where 1 = top, 0 = bottom.
        #  - Moving content up by +delta_px means increase scroll_y.
        denominator = cont_h - viewport_h
        if denominator <= 0:
            self._on_settled()
            return

        delta_norm = delta_px / denominator
        new_scroll_y = self._clamp01(scroll_view.scroll_y + delta_norm)

        # Apply in one shot (no animation to avoid visible bounce)
        scroll_view.scroll_y = new_scroll_y
        self._on_settled()

    @staticmethod
    def _clamp01(v: float) -> float:
        return 0.0 if v < 0.0 else (min(v, 1.0))
