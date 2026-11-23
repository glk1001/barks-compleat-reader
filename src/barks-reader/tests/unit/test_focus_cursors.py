"""Where keyboard focus goes next (barks_reader.core.focus_cursors)."""

# ruff: noqa: PLR2004

from __future__ import annotations

import pytest
from barks_reader.core.focus_cursors import (
    GridCursor,
    choice_over_a_button_after,
    clamped,
    deal_into_columns,
    list_index_after_key,
    next_index_toward,
    stripe_indexes,
    wrapped,
)
from barks_reader.core.keys import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_LEFT,
    KEY_PAGE_DOWN,
    KEY_PAGE_UP,
    KEY_UP,
)


def test_clamped_holds_an_index_within_the_list_and_at_0_for_none() -> None:
    assert [clamped(i, 3) for i in (-1, 0, 2, 3, 9)] == [0, 0, 2, 2, 2]
    assert clamped(5, 0) == 0


def test_wrapped_goes_round_the_ring_both_ways() -> None:
    assert wrapped(2, 1, 3) == 0
    assert wrapped(0, -1, 3) == 2


def test_an_empty_ring_or_list_gives_0_not_an_error() -> None:
    """An index with no letters, say: a step must not divide by zero or land on -1."""
    assert wrapped(0, 1, 0) == 0
    assert next_index_toward(0, None, -1) == 0
    assert next_index_toward(0, None, 1) == 0


def test_a_step_with_nothing_selected_lands_on_an_end() -> None:
    assert next_index_toward(5, None, 1) == 0
    assert next_index_toward(5, None, -1) == 4
    assert next_index_toward(5, 4, 1) == 4
    assert next_index_toward(5, 2, -3) == 0


@pytest.mark.parametrize(
    ("count", "columns", "lengths"),
    [(7, 3, [3, 2, 2]), (8, 3, [3, 3, 2]), (2, 3, [1, 1, 0]), (0, 2, [0, 0]), (6, 2, [3, 3])],
)
def test_items_are_dealt_into_columns_fullest_first(
    count: int, columns: int, lengths: list[int]
) -> None:
    dealt = deal_into_columns(list(range(count)), columns)
    assert [len(c) for c in dealt] == lengths
    assert [i for c in dealt for i in c] == list(range(count))


def test_the_stripe_index_restarts_at_each_group() -> None:
    assert stripe_indexes(["Mon", "Mon", "Tue", "Tue", "Tue"]) == [0, 1, 0, 1, 2]
    assert stripe_indexes([None, None]) == [0, 1]  # one unnamed group runs on
    assert stripe_indexes([]) == []


class TestGridCursor:
    """Three columns of 3, 2 and 0 items."""

    @staticmethod
    def _len(col: int) -> int:
        return [3, 2, 0][col]

    def test_up_a_row_then_to_the_bottom_of_the_column_before_then_out(self) -> None:
        cursor = GridCursor(1, 1).up(self._len)
        assert cursor == GridCursor(1, 0)
        assert cursor is not None
        cursor = cursor.up(self._len)
        assert cursor == GridCursor(0, 2)
        assert GridCursor(0, 0).up(self._len) is None

    def test_up_from_an_empty_column_stays_put(self) -> None:
        cursor = GridCursor(2, 1)
        assert cursor.up(self._len) is cursor

    def test_down_a_row_then_to_the_top_of_the_next_then_nowhere(self) -> None:
        cursor = GridCursor(0, 1).down(3, self._len)
        assert cursor == GridCursor(0, 2)
        assert cursor is not None
        assert cursor.down(3, self._len) == GridCursor(1, 0)
        assert GridCursor(1, 1).down(3, self._len) is None  # the next column is empty
        assert GridCursor(2, 0).down(3, self._len) is None

    def test_sideways_keeps_the_row_or_takes_the_columns_last(self) -> None:
        assert GridCursor(0, 2).sideways(1, 3, self._len) == GridCursor(1, 1)
        assert GridCursor(1, 1).sideways(-1, 3, self._len) == GridCursor(0, 1)
        assert GridCursor(1, 0).sideways(1, 3, self._len) is None  # empty
        assert GridCursor(0, 0).sideways(-1, 3, self._len) is None  # off the grid

    def test_resync_lands_on_the_first_row_opened_under_the_button(self) -> None:
        assert GridCursor(0, 0).resync(0, old_count=2, new_count=5) == GridCursor(0, 1)
        assert GridCursor(0, 5).resync(1, old_count=2, new_count=5) == GridCursor(0, 2)

    def test_resync_stays_on_the_button_when_rows_closed(self) -> None:
        assert GridCursor(0, 3).resync(0, old_count=3, new_count=1) == GridCursor(0, 0)

    def test_resync_holds_the_cursor_within_the_column_when_the_button_is_gone(self) -> None:
        assert GridCursor(0, 5).resync(None, old_count=3, new_count=2) == GridCursor(0, 1)
        assert GridCursor(0, 5).resync(None, old_count=1, new_count=3) == GridCursor(0, 2)


class TestAnOpenListsKeys:
    @pytest.mark.parametrize(
        ("key", "index", "landed"),
        [(KEY_DOWN, 0, 1), (KEY_DOWN, 4, 4), (KEY_UP, 4, 3), (KEY_UP, 0, 0)],
    )
    def test_up_and_down_step_a_row_and_stop_at_the_ends(
        self, key: int, index: int, landed: int
    ) -> None:
        assert list_index_after_key(key, index, 5, wraps=False) == landed

    @pytest.mark.parametrize(
        ("key", "index", "landed"),
        [(KEY_DOWN, 0, 1), (KEY_DOWN, 4, 0), (KEY_UP, 4, 3), (KEY_UP, 0, 4)],
    )
    def test_in_a_list_that_wraps_they_go_round(self, key: int, index: int, landed: int) -> None:
        assert list_index_after_key(key, index, 5, wraps=True) == landed

    @pytest.mark.parametrize("wraps", [True, False])
    @pytest.mark.parametrize(
        ("key", "index", "landed"),
        [(KEY_PAGE_DOWN, 0, 3), (KEY_PAGE_DOWN, 6, 7), (KEY_PAGE_UP, 7, 4), (KEY_PAGE_UP, 1, 0)],
    )
    def test_the_page_keys_jump_a_step_and_stop_at_the_ends_wrapping_or_not(
        self, key: int, index: int, landed: int, wraps: bool
    ) -> None:
        assert list_index_after_key(key, index, 8, wraps=wraps, page_step=3) == landed

    @pytest.mark.parametrize("key", [KEY_PAGE_DOWN, KEY_PAGE_UP])
    def test_with_no_page_step_the_page_keys_are_not_the_list_s(self, key: int) -> None:
        assert list_index_after_key(key, 2, 8, wraps=False) is None
        assert list_index_after_key(key, 2, 8, wraps=False, page_step=0) is None

    @pytest.mark.parametrize("key", [KEY_ENTER, KEY_LEFT, ord("a")])
    def test_no_other_key_moves_the_focus(self, key: int) -> None:
        assert list_index_after_key(key, 2, 8, wraps=True, page_step=3) is None


class TestChoicesOverAButton:
    """A column of choices with Cancel under it: None is the button."""

    def test_down_goes_through_the_choices_onto_the_button_and_stays(self) -> None:
        assert choice_over_a_button_after(0, 3, up=False) == 1
        assert choice_over_a_button_after(1, 3, up=False) == 2
        assert choice_over_a_button_after(2, 3, up=False) is None
        assert choice_over_a_button_after(None, 3, up=False) is None

    def test_up_from_the_button_is_the_last_choice_and_stops_at_the_first(self) -> None:
        assert choice_over_a_button_after(None, 3, up=True) == 2
        assert choice_over_a_button_after(2, 3, up=True) == 1
        assert choice_over_a_button_after(0, 3, up=True) == 0

    def test_with_no_choices_the_focus_stays_on_the_button(self) -> None:
        assert choice_over_a_button_after(None, 0, up=True) is None
        assert choice_over_a_button_after(None, 0, up=False) is None

    def test_a_single_choice_is_first_and_last(self) -> None:
        assert choice_over_a_button_after(0, 1, up=False) is None
        assert choice_over_a_button_after(None, 1, up=True) == 0
        assert choice_over_a_button_after(0, 1, up=True) == 0
