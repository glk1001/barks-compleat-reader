"""Tests for where the keyboard is on the search screen."""

from __future__ import annotations

from barks_reader.core.search_focus import FocusArea, ListPart, RowPart, SearchFocus


def test_a_screen_starts_without_the_keys_on_its_box() -> None:
    focus = SearchFocus()
    assert (focus.active, focus.area) == (False, FocusArea.INPUT)
    assert (focus.chip_index, focus.result_index) == (0, 0)
    assert (focus.list_part, focus.row_part) == (ListPart.ITEM, RowPart.TITLE)


def test_two_screens_do_not_share_a_focus() -> None:
    one, other = SearchFocus(), SearchFocus()
    one.area = FocusArea.RESULTS
    assert other.area == FocusArea.INPUT


def test_an_area_is_logged_by_the_word_the_gui_tests_wait_on() -> None:
    """The panel-row-lost line formats the area; its text is part of that line."""
    assert [f"{area}" for area in FocusArea] == [
        "input",
        "clear",
        "tags",
        "basket",
        "speakers",
        "said_by_list",
        "scope",
        "era",
        "results",
    ]


def test_the_parts_of_a_row_keep_their_words() -> None:
    assert [str(part) for part in ListPart] == ["word", "plus"]
    assert [str(part) for part in RowPart] == ["title", "speech"]
