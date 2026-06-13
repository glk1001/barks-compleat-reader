"""Tests for `TreeScrollPinner` — the tree-expansion scroll-stabilization loop.

Extracted from `TreeViewManager`, the pinner's per-frame settle loop is now
driven deterministically through an injected `schedule_once` fake instead of
Kivy's `Clock`, so the previously-untested pixel math is exercised directly.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from barks_reader.ui.tree_scroll_pinner import TreeScrollPinner


class _FakeClock:
    """Captures scheduled callbacks so the settle loop can be ticked by hand."""

    def __init__(self) -> None:
        self.pending: list = []

    def schedule_once(self, callback, _timeout) -> object:  # noqa: ANN001
        self.pending.append(callback)
        return object()

    def run_next(self) -> bool:
        """Run the next scheduled callback. Returns False if nothing was pending."""
        if not self.pending:
            return False
        self.pending.pop(0)(0.0)
        return True


def _make_scroll_view(*, has_children: bool = True, cont_height: float = 500.0) -> MagicMock:
    scroll_view = MagicMock()
    scroll_view.children = [MagicMock()] if has_children else []
    if has_children:
        scroll_view.children[0].height = cont_height
    scroll_view.height = 100.0
    scroll_view.scroll_y = 0.5
    scroll_view.top = 0.0
    return scroll_view


def _make_parent_node() -> MagicMock:
    node = MagicMock()
    node.text = "Parent Node"
    node.is_open = True
    return node


def test_no_children_returns_without_scheduling() -> None:
    clock = _FakeClock()
    pinner = TreeScrollPinner(
        get_scroll_view=lambda: _make_scroll_view(has_children=False),
        on_settled=MagicMock(),
        schedule_once=clock.schedule_once,
    )
    populate = MagicMock()

    pinner.pin_while_populating(_make_parent_node(), populate=populate)

    populate.assert_not_called()
    assert clock.pending == []


def test_populate_runs_and_settle_loop_is_scheduled() -> None:
    clock = _FakeClock()
    pinner = TreeScrollPinner(
        get_scroll_view=_make_scroll_view,
        on_settled=MagicMock(),
        schedule_once=clock.schedule_once,
    )
    populate = MagicMock()

    pinner.pin_while_populating(_make_parent_node(), populate=populate)

    populate.assert_called_once()
    assert len(clock.pending) == 1


def test_populate_none_skips_populate_but_still_schedules() -> None:
    clock = _FakeClock()
    pinner = TreeScrollPinner(
        get_scroll_view=_make_scroll_view,
        on_settled=MagicMock(),
        schedule_once=clock.schedule_once,
    )

    pinner.pin_while_populating(_make_parent_node(), populate=None)

    assert len(clock.pending) == 1


def test_settle_stops_when_parent_closed() -> None:
    clock = _FakeClock()
    on_settled = MagicMock()
    pinner = TreeScrollPinner(
        get_scroll_view=_make_scroll_view,
        on_settled=on_settled,
        schedule_once=clock.schedule_once,
    )
    parent = _make_parent_node()

    pinner.pin_while_populating(parent, populate=None)
    parent.is_open = False  # user collapsed before the layout settled
    clock.run_next()

    on_settled.assert_called_once()
    assert clock.pending == []  # loop did not reschedule


def test_settle_adjusts_scroll_y_to_cancel_drift() -> None:
    clock = _FakeClock()
    on_settled = MagicMock()
    scroll_view = _make_scroll_view()
    # sv top stays at window-y 0; parent starts 140px below at pin, ends 100px below
    # after layout -> a 40px upward drift that must be cancelled.
    scroll_view.to_window.return_value = (0, 0)
    parent = _make_parent_node()
    parent.to_window.side_effect = [(0, 140), (0, 100)]

    pinner = TreeScrollPinner(
        get_scroll_view=lambda: scroll_view,
        on_settled=on_settled,
        schedule_once=clock.schedule_once,
    )

    pinner.pin_while_populating(parent, populate=None)  # captures target_offset = 140
    # Container height must read stable for two consecutive frames before adjusting.
    clock.run_next()  # frame 1: last_h initialized, stable=0 -> reschedule
    clock.run_next()  # frame 2: height stable=1 -> reschedule
    clock.run_next()  # frame 3: stable=2 -> compute drift and adjust

    # delta_px = 100 - 140 = -40; denominator = 500 - 100 = 400; delta_norm = -0.1.
    assert scroll_view.scroll_y == pytest.approx(0.4)
    on_settled.assert_called_once()
    assert clock.pending == []
