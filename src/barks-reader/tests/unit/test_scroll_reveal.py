"""Tests for how far a list scrolls to reveal its opened items, and to keep a row put."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from barks_reader.core.scroll_reveal import (
    LEAST_MOVE_PX,
    MAX_SETTLE_FRAMES,
    HeightSettle,
    first_shown_rows,
    held_in_scroll_range,
    is_worth_a_move,
    reveal_distance,
    reveal_distance_with_owner_pinned,
    scroll_y_after_key,
    scroll_y_after_reveal,
    scroll_y_keeping_row,
)


def _keeping(row_from_content_top: float, content_height: float) -> float | None:
    # A 100-high view, the row 40 below its top.
    return scroll_y_keeping_row(
        row_from_content_top=row_from_content_top,
        row_from_view_top=40.0,
        content_height=content_height,
        view_height=100.0,
    )


def test_a_shorter_list_scrolls_by_a_bigger_share() -> None:
    # Scrolled 100 of 400 before, 100 of 200 after.
    assert _keeping(140.0, 500.0) == pytest.approx(0.75)
    assert _keeping(140.0, 300.0) == pytest.approx(0.5)


def test_a_taller_list_scrolls_by_a_smaller_share() -> None:
    assert _keeping(140.0, 900.0) == pytest.approx(0.875)


def test_a_row_at_the_view_top_of_a_list_at_its_top_keeps_it_there() -> None:
    assert _keeping(40.0, 900.0) == pytest.approx(1.0)


def test_too_near_the_end_to_stay_the_list_shows_its_end() -> None:
    assert _keeping(440.0, 300.0) == pytest.approx(0.0)


def test_a_row_nearer_the_list_top_than_it_is_to_sit_shows_the_list_top() -> None:
    assert _keeping(20.0, 500.0) == pytest.approx(1.0)


def test_a_list_one_pixel_taller_than_the_view_scrolls() -> None:
    # Half a pixel scrolled of the one there is.
    assert _keeping(40.5, 101.0) == pytest.approx(0.5)


@pytest.mark.parametrize("content_height", [100.0, 80.0])
def test_a_list_no_taller_than_the_view_does_not_scroll(content_height: float) -> None:
    assert _keeping(40.0, content_height) is None


def test_a_reveal_brings_the_padding_under_the_items_into_view() -> None:
    # The items end 50 below the view, so the padding makes it 60; the row has 400 to spare.
    distance = reveal_distance(
        view_bottom=0.0, view_top=500.0, items_bottom=-50.0, owner_top=100.0, padding=10.0
    )
    assert distance == pytest.approx(60.0)


@pytest.mark.parametrize(
    ("scroll_y", "held"), [(-0.25, 0.0), (0.0, 0.0), (0.4, 0.4), (1.0, 1.0), (1.25, 1.0)]
)
def test_a_scroll_position_is_held_between_the_foot_and_the_top(
    scroll_y: float, held: float
) -> None:
    assert held_in_scroll_range(scroll_y) == held


class TestScrollYAfterKey:
    """Up and Down move a popup's text a quarter of what shows of it."""

    def test_down_moves_towards_the_foot_and_up_back(self) -> None:
        # 400 of 800 show, so 400 are hidden: a press moves 100 of them.
        down = scroll_y_after_key(scroll_y=1.0, view_height=400, content_height=800, up=False)
        assert down == pytest.approx(0.75)
        up = scroll_y_after_key(scroll_y=down, view_height=400, content_height=800, up=True)
        assert up == pytest.approx(1.0)

    def test_it_stops_at_the_top_and_at_the_foot(self) -> None:
        # 100 hidden, and a press is 100: the whole of it.
        assert scroll_y_after_key(scroll_y=1.0, view_height=400, content_height=500, up=True) == 1.0
        assert (
            scroll_y_after_key(scroll_y=0.5, view_height=400, content_height=500, up=False) == 0.0
        )

    @pytest.mark.parametrize("content_height", [400.5, 401])
    def test_text_a_pixel_or_less_too_tall_still_scrolls(self, content_height: float) -> None:
        assert (
            scroll_y_after_key(
                scroll_y=1.0, view_height=400, content_height=content_height, up=False
            )
            == 0.0
        )

    @pytest.mark.parametrize("content_height", [300, 400])
    def test_text_that_all_shows_stays_where_it_is(self, content_height: int) -> None:
        moved = scroll_y_after_key(
            scroll_y=1.0, view_height=400, content_height=content_height, up=False
        )
        assert moved == 1.0


class TestHeightSettle:
    def test_a_height_that_holds_for_two_frames_after_the_first_has_settled(self) -> None:
        watch = HeightSettle()
        assert [watch.has_settled(500.0, 100.0) for _ in range(3)] == [False, False, True]

    def test_a_change_of_height_starts_the_count_again(self) -> None:
        watch = HeightSettle()
        heights = [500.0, 500.0, 620.0, 620.0, 620.0]
        settled = [watch.has_settled(h, 100.0) for h in heights]
        assert settled == [False, False, False, False, True]

    def test_under_half_a_pixel_is_no_change_and_half_a_pixel_is_one(self) -> None:
        watch = HeightSettle()
        assert [watch.has_settled(h, 100.0) for h in (500.0, 500.4, 500.0)] == [False, False, True]
        watch = HeightSettle()
        assert [watch.has_settled(h, 100.0) for h in (500.0, 500.5, 500.0)] == [False] * 3

    @pytest.mark.parametrize(("content", "view"), [(1.0, 100.0), (0.0, 100.0), (500.0, 1.0)])
    def test_a_list_or_view_with_no_height_is_waited_on_and_counts_for_nothing(
        self, content: float, view: float
    ) -> None:
        watch = HeightSettle()
        watch.has_settled(500.0, 100.0)
        watch.has_settled(500.0, 100.0)  # one stable frame so far

        assert watch.has_settled(content, view) is False
        assert (watch.last_height, watch.stable_frames) == (500.0, 1)
        assert watch.has_settled(500.0, 100.0) is True

    def test_a_height_just_over_a_pixel_is_a_height(self) -> None:
        watch = HeightSettle()
        assert [watch.has_settled(1.5, 1.5) for _ in range(3)] == [False, False, True]

    def test_the_watch_gives_up_after_its_frames(self) -> None:
        watch = HeightSettle()
        waits = [watch.may_wait_another_frame() for _ in range(MAX_SETTLE_FRAMES)]
        assert waits == [True] * (MAX_SETTLE_FRAMES - 1) + [False]
        assert watch.frames_waited == MAX_SETTLE_FRAMES


class TestAMoveWorthMaking:
    def test_half_a_pixel_is_and_less_is_not(self) -> None:
        assert LEAST_MOVE_PX == 0.5  # noqa: PLR2004
        assert is_worth_a_move(0.0, 0.125, 4.0) is True  # half a pixel of the 4 scrollable
        assert is_worth_a_move(0.0, 0.1, 4.0) is False

    def test_either_way(self) -> None:
        assert is_worth_a_move(0.5, 0.25, 400.0) is True
        assert is_worth_a_move(0.25, 0.5, 400.0) is True
        assert is_worth_a_move(0.5, 0.5, 400.0) is False


class TestAReveal:
    def test_the_glide_ends_with_the_content_that_far_up(self) -> None:
        assert scroll_y_after_reveal(0.5, 100.0, 400.0) == pytest.approx(0.25)

    def test_it_stops_at_the_list_s_foot(self) -> None:
        assert scroll_y_after_reveal(0.1, 100.0, 400.0) == 0.0

    def _pinned(self, *, first: float, last: float, owner_top: float) -> float:
        # A view from 0 up to 300; the row is pinned with its top at 100.
        return reveal_distance_with_owner_pinned(
            view_bottom=0.0,
            view_top=300.0,
            first_item_bottom=first,
            last_item_bottom=last,
            owner_top=owner_top,
            pinned_owner_top=100.0,
            padding=10.0,
        )

    def test_nothing_while_the_first_item_shows_whole(self) -> None:
        assert self._pinned(first=40.0, last=-80.0, owner_top=100.0) == 0.0
        assert self._pinned(first=0.0, last=-80.0, owner_top=100.0) == 0.0

    def test_enough_to_show_the_last_item_and_the_padding(self) -> None:
        assert self._pinned(first=-10.0, last=-70.0, owner_top=100.0) == 80.0  # noqa: PLR2004

    def test_the_items_are_measured_with_the_row_back_at_its_pin(self) -> None:
        """The layout moved the row and its items 60 up; pinned back, they are 60 lower."""
        assert self._pinned(first=50.0, last=-10.0, owner_top=160.0) == 80.0  # noqa: PLR2004
        # And a first item hidden only by the drift shows once the row is back.
        assert self._pinned(first=-20.0, last=-40.0, owner_top=60.0) == 0.0

    def test_never_so_far_that_the_row_leaves_the_view(self) -> None:
        assert self._pinned(first=-10.0, last=-900.0, owner_top=100.0) == 200.0  # noqa: PLR2004


@dataclass
class _Row:
    name: str
    nodes: list[_Row] = field(default_factory=list)
    is_open: bool = False


class TestTheFirstRowsShown:
    def test_they_are_the_row_s_own_in_their_order(self) -> None:
        owner = _Row("owner", [_Row("a"), _Row("b"), _Row("c"), _Row("d")], is_open=True)
        assert [row.name for row in first_shown_rows(owner, 3)] == ["a", "b", "c"]

    def test_an_open_row_among_them_is_followed_by_its_own(self) -> None:
        open_child = _Row("a", [_Row("a1", [_Row("a1x")], is_open=True), _Row("a2")], is_open=True)
        owner = _Row("owner", [open_child, _Row("b")], is_open=True)
        names = [row.name for row in first_shown_rows(owner, 5)]
        assert names == ["a", "a1", "a1x", "a2", "b"]

    def test_a_shut_row_s_own_are_not_shown(self) -> None:
        owner = _Row("owner", [_Row("a", [_Row("a1")]), _Row("b")], is_open=True)
        assert [row.name for row in first_shown_rows(owner, 3)] == ["a", "b"]

    def test_the_count_stops_the_walk_inside_an_open_row(self) -> None:
        open_child = _Row("a", [_Row("a1"), _Row("a2"), _Row("a3")], is_open=True)
        owner = _Row("owner", [open_child, _Row("b")], is_open=True)
        assert [row.name for row in first_shown_rows(owner, 2)] == ["a", "a1"]

    def test_fewer_rows_than_asked_for_are_all_there_are_and_none_is_none(self) -> None:
        assert [row.name for row in first_shown_rows(_Row("o", [_Row("a")]), 3)] == ["a"]
        assert first_shown_rows(_Row("o"), 3) == []
        assert first_shown_rows(_Row("o", [_Row("a")]), 0) == []
