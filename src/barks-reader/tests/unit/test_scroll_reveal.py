"""Tests for how far a list scrolls to reveal its opened items, and to keep a row put."""

from __future__ import annotations

import pytest
from barks_reader.core.scroll_reveal import reveal_distance, scroll_y_keeping_row


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
