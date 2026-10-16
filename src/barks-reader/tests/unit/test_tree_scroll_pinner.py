"""Tests for `TreeScrollPinner` — the tree-expansion scroll-stabilization loop.

Extracted from `TreeViewManager`, the pinner's per-frame settle loop is now
driven deterministically through an injected `schedule_once` fake instead of
Kivy's `Clock`, so the previously-untested pixel math is exercised directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from barks_reader.core.scroll_reveal import REVEAL_PADDING
from barks_reader.core.tap_targets import layout_settling
from barks_reader.core.testing import FakeClock
from barks_reader.ui.tree_scroll_pinner import TreeScrollPinner
from kivy.metrics import dp

if TYPE_CHECKING:
    from collections.abc import Callable


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
    node.nodes = []
    return node


def test_no_children_returns_without_scheduling() -> None:
    clock = FakeClock()
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
    clock = FakeClock()
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
    clock = FakeClock()
    pinner = TreeScrollPinner(
        get_scroll_view=_make_scroll_view,
        on_settled=MagicMock(),
        schedule_once=clock.schedule_once,
    )

    pinner.pin_while_populating(_make_parent_node(), populate=None)

    assert len(clock.pending) == 1


def test_settle_stops_when_parent_closed() -> None:
    clock = FakeClock()
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
    clock = FakeClock()
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


def test_tap_target_answers_wait_until_the_pin_settles() -> None:
    """Between an expand and its scroll correction the tree is not where it will be."""
    clock = FakeClock()
    pinner = TreeScrollPinner(
        get_scroll_view=_make_scroll_view,
        on_settled=MagicMock(),
        schedule_once=clock.schedule_once,
    )
    parent = _make_parent_node()
    assert not layout_settling()

    pinner.pin_while_populating(parent, populate=None)
    assert layout_settling()

    parent.is_open = False
    clock.run_next()
    assert not layout_settling()


def test_a_pin_that_never_starts_holds_nothing() -> None:
    pinner = TreeScrollPinner(
        get_scroll_view=lambda: _make_scroll_view(has_children=False),
        on_settled=MagicMock(),
        schedule_once=FakeClock().schedule_once,
    )
    pinner.pin_while_populating(_make_parent_node(), populate=None)
    assert not layout_settling()


def test_a_container_that_goes_missing_is_waited_for_then_given_up_on() -> None:
    """The tree's container can be swapped out mid-settle: wait, but not for ever."""
    clock = FakeClock()
    on_settled = MagicMock()
    scroll_view = _make_scroll_view()
    pinner = TreeScrollPinner(
        get_scroll_view=lambda: scroll_view,
        on_settled=on_settled,
        schedule_once=clock.schedule_once,
    )
    pinner.pin_while_populating(_make_parent_node(), populate=None)
    scroll_view.children = []

    frames = 0
    while clock.run_next():
        frames += 1

    assert frames == TreeScrollPinner._MAX_SETTLE_FRAMES  # noqa: SLF001
    on_settled.assert_called_once()
    assert not layout_settling()


def _make_node_at(y: float, *, is_open: bool = False, nodes: list | None = None) -> MagicMock:
    """Return a tree row whose bottom is at window y `y`."""
    node = MagicMock(y=y, is_open=is_open, nodes=nodes or [])
    node.to_window = lambda x, y: (x, y)
    return node


def _jump(scroll_view: MagicMock, scroll_y: float, on_done: Callable[[], None]) -> None:
    scroll_view.scroll_y = scroll_y
    on_done()


def _settle_with(
    parent: MagicMock, between_pins: Callable[[TreeScrollPinner], None] | None = None
) -> MagicMock:
    """Expand `parent` in a view over window y 0-100 of 500px of content; return the view.

    `between_pins(pinner)`, if given, runs after the pin and before the layout settles.
    """
    clock = FakeClock()
    scroll_view = _make_scroll_view()
    scroll_view.y, scroll_view.top = 0.0, 100.0
    scroll_view.to_window = lambda x, y: (x, y)
    pinner = TreeScrollPinner(
        get_scroll_view=lambda: scroll_view,
        on_settled=MagicMock(),
        schedule_once=clock.schedule_once,
        glide=_jump,
    )
    pinner.pin_while_populating(parent, populate=None)
    if between_pins is not None:
        between_pins(pinner)
    while clock.run_next():
        pass
    return scroll_view


def _parent_at_top(top: float, nodes: list) -> MagicMock:
    parent = _make_parent_node()
    parent.top = top
    parent.to_window = lambda x, y: (x, y)
    parent.nodes = nodes
    return parent


# Rows 20 high: a parent whose top is at 25 has its children's bottoms at -15, -35, ...
_HIDDEN_ROWS = [-15.0, -35.0, -55.0, -75.0]


def test_children_opened_below_the_view_glide_up_to_show_three() -> None:
    parent = _parent_at_top(25.0, [_make_node_at(y) for y in _HIDDEN_ROWS])

    scroll_view = _settle_with(parent)

    # Up to the third row's bottom, 55 below the view, and the padding: not the fourth.
    assert scroll_view.scroll_y == pytest.approx(0.5 - ((55 + dp(REVEAL_PADDING)) / 400))


def test_a_parent_whose_first_child_shows_does_not_move() -> None:
    parent = _parent_at_top(45.0, [_make_node_at(5.0), _make_node_at(-15.0)])

    scroll_view = _settle_with(parent)

    assert scroll_view.scroll_y == pytest.approx(0.5)


def test_the_parent_stays_in_view_however_tall_its_rows() -> None:
    parent = _parent_at_top(70.0, [_make_node_at(-10.0), _make_node_at(-200.0)])

    scroll_view = _settle_with(parent)

    assert scroll_view.scroll_y == pytest.approx(0.5 - (30 / 400))


def test_the_rows_of_an_open_child_count_among_the_three() -> None:
    open_child = _make_node_at(-15.0, is_open=True, nodes=[_make_node_at(y) for y in (-35, -55)])
    parent = _parent_at_top(25.0, [open_child, _make_node_at(-100.0)])

    scroll_view = _settle_with(parent)

    assert scroll_view.scroll_y == pytest.approx(0.5 - ((55 + dp(REVEAL_PADDING)) / 400))


def test_a_reveal_glides() -> None:
    clock = FakeClock()
    scroll_view = _make_scroll_view()
    scroll_view.y, scroll_view.top = 0.0, 100.0
    scroll_view.to_window = lambda x, y: (x, y)
    glide = MagicMock()
    on_settled = MagicMock()
    pinner = TreeScrollPinner(
        get_scroll_view=lambda: scroll_view,
        on_settled=on_settled,
        schedule_once=clock.schedule_once,
        glide=glide,
    )
    pinner.pin_while_populating(
        _parent_at_top(25.0, [_make_node_at(y) for y in _HIDDEN_ROWS]), populate=None
    )
    while clock.run_next():
        pass

    glide.assert_called_once()
    assert scroll_view.scroll_y == pytest.approx(0.5)  # not yet: the glide moves it
    on_settled.assert_not_called()  # settled only once the glide is done
    assert layout_settling()
    glide.call_args.args[2]()
    on_settled.assert_called_once()
    assert not layout_settling()


def test_a_cancelled_reveal_leaves_the_tree_where_the_app_put_it() -> None:
    parent = _parent_at_top(25.0, [_make_node_at(y) for y in _HIDDEN_ROWS])

    scroll_view = _settle_with(parent, TreeScrollPinner.cancel_pending_reveals)

    assert scroll_view.scroll_y == pytest.approx(0.5)


def test_only_the_latest_pin_reveals() -> None:
    """A chain opened at once (a saved node and its parents) reveals only the last."""
    first = _parent_at_top(25.0, [_make_node_at(y) for y in _HIDDEN_ROWS])
    last = _parent_at_top(45.0, [_make_node_at(5.0)])

    def pin_another(pinner: TreeScrollPinner) -> None:
        pinner.pin_while_populating(last, populate=None)

    scroll_view = _settle_with(first, pin_another)

    assert scroll_view.scroll_y == pytest.approx(0.5)


# ------------------------------------------------------------------ collapsing --


def _collapse(parent: MagicMock, scroll_view: MagicMock) -> tuple[MagicMock, int]:
    """Collapse `parent` and let the layout settle; return on_settled and the frames run."""
    clock = FakeClock()
    on_settled = MagicMock()
    pinner = TreeScrollPinner(
        get_scroll_view=lambda: scroll_view,
        on_settled=on_settled,
        schedule_once=clock.schedule_once,
        glide=_jump,
    )
    parent.is_open = False
    pinner.pin_while_collapsing(parent)
    frames = 0
    while clock.run_next():
        frames += 1
    return on_settled, frames


def test_a_collapsed_parent_stays_where_it_was() -> None:
    scroll_view = _make_scroll_view()
    scroll_view.to_window.return_value = (0, 0)
    parent = _make_parent_node()
    # 140 below the view's top before, 100 after: the shorter tree moved it up 40.
    parent.to_window.side_effect = [(0, 140), (0, 100)]

    on_settled, _ = _collapse(parent, scroll_view)

    assert scroll_view.scroll_y == pytest.approx(0.4)
    on_settled.assert_called_once()


def test_a_collapse_reveals_nothing() -> None:
    scroll_view = _make_scroll_view()
    scroll_view.y, scroll_view.top = 0.0, 100.0
    scroll_view.to_window = lambda x, y: (x, y)
    parent = _parent_at_top(25.0, [_make_node_at(y) for y in _HIDDEN_ROWS])

    _collapse(parent, scroll_view)

    assert scroll_view.scroll_y == pytest.approx(0.5)


def test_a_tree_that_fits_the_view_settles_at_once() -> None:
    """Too short to scroll, it has nothing to pin, and does not wait the frames out."""
    scroll_view = _make_scroll_view(cont_height=80.0)

    on_settled, frames = _collapse(_make_parent_node(), scroll_view)

    on_settled.assert_called_once()
    assert frames < TreeScrollPinner._MAX_SETTLE_FRAMES  # noqa: SLF001
    assert not layout_settling()
