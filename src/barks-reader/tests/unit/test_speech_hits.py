"""A speech search's hits as rows (barks_reader.core.speech_hits)."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest
from barks_reader.core.index_text import MAX_TITLE_AND_PAGES_LEN
from barks_reader.core.speech_hits import (
    MAX_WORD_SEARCH_TITLE_AND_PAGES_LEN,
    SpeechHitRow,
    comic_pages,
    speech_hit_rows,
)

if TYPE_CHECKING:
    from barks_fantagraphics.whoosh_search_engine import TitleInfo


def _info(*pages: str) -> TitleInfo:
    pages_found = {f"fanta-{p}": MagicMock(comic_page=p) for p in pages}
    return cast("TitleInfo", MagicMock(fanta_pages=pages_found))


def test_the_comic_pages_are_the_pages_in_order() -> None:
    assert comic_pages(_info("3", "4", "12")) == ("3", "4", "12")


def test_each_story_is_a_row_opening_at_its_first_page_sorted_by_text() -> None:
    found = {"The Old Castle's Secret": _info("5", "6"), "Lost in the Andes!": _info("3")}

    rows = speech_hit_rows(found, max_len=MAX_WORD_SEARCH_TITLE_AND_PAGES_LEN)

    assert rows == [
        SpeechHitRow(
            "Lost in the Andes!", "3", "Lost in the Andes!, 3", found["Lost in the Andes!"]
        ),
        SpeechHitRow(
            "The Old Castle's Secret",
            "5",
            "The Old Castle's Secret, 5-6",
            found["The Old Castle's Secret"],
        ),
    ]


def test_a_query_s_hit_count_ends_each_row() -> None:
    rows = speech_hit_rows(
        {"Lost in the Andes!": _info("3", "5")},
        max_len=MAX_WORD_SEARCH_TITLE_AND_PAGES_LEN,
        hit_counts={"Lost in the Andes!": 4},
    )
    assert rows[0].text == "Lost in the Andes!, 3,5 (4)"
    assert rows[0][2] == rows[0].text  # a row unpacks as the tuple it was


def test_a_story_the_counts_do_not_name_counts_none() -> None:
    rows = speech_hit_rows({"A Title": _info("1")}, max_len=50, hit_counts={})
    assert rows[0].text == "A Title, 1 (0)"


def test_an_index_row_lists_by_the_word_after_the_article() -> None:
    rows = speech_hit_rows(
        {"The Old Castle's Secret": _info("5"), "Lost in the Andes!": _info("3")},
        max_len=MAX_TITLE_AND_PAGES_LEN,
        sortable=True,
    )
    assert [row.text for row in rows] == ["Lost in the Andes!, 3", "Old Castle's Secret, The, 5"]


def test_a_long_page_list_is_cut_to_the_length_less_the_count() -> None:
    pages = [str(p) for p in range(1, 40, 2)]
    rows = speech_hit_rows({"A Title": _info(*pages)}, max_len=30, hit_counts={"A Title": 12})
    assert len(rows[0].text) <= 30  # noqa: PLR2004
    assert rows[0].text.endswith(" (12)")


def test_the_count_comes_out_of_the_title_and_pages_room() -> None:
    rows = speech_hit_rows(
        {"A Title": _info("1", "3", "5", "7", "9", "11")}, max_len=24, hit_counts={"A Title": 4}
    )
    # "A Title, 1,3,5,7,9,11" fits 24 alone, but with " (4)" the title is cut to make room.
    assert rows[0].text == "Title, 1,3,5,7,9,11 (4)"


def test_a_sortable_rows_article_stays_with_its_title_before_the_pages() -> None:
    # Moved after the row was built, it trailed the pages: "Apple Tree, 1, The".
    rows = speech_hit_rows({"The Apple Tree": _info("1")}, max_len=50, sortable=True)
    assert rows[0].text == "Apple Tree, The, 1"


def test_a_sortable_row_with_a_as_its_article_lists_the_same_way() -> None:
    rows = speech_hit_rows({"A Christmas for Shacktown": _info("5")}, max_len=50, sortable=True)
    assert rows[0].text == "Christmas for Shacktown, A, 5"


@pytest.mark.parametrize("title", ["The Old Castle's Secret", "A Christmas for Shacktown"])
def test_a_sortable_row_never_runs_past_its_length(title: str) -> None:
    pages = ["5", "9", "12", "13", "14", "20"]
    for max_len in range(12, 50):
        rows = speech_hit_rows({title: _info(*pages)}, max_len=max_len, sortable=True)
        assert len(rows[0].text) <= max_len, (max_len, rows[0].text)
        assert rows[0].first_page == "5"


def test_a_sortable_row_with_no_article_fitted_exactly_is_kept_whole() -> None:
    row = "Lost in the Andes!, 3,5"
    rows = speech_hit_rows({"Lost in the Andes!": _info("3", "5")}, max_len=len(row), sortable=True)
    assert rows[0].text == row


def test_a_sortable_row_too_long_gives_up_its_article_before_any_of_its_title() -> None:
    pages = ["5", "9", "12", "13", "14", "20"]
    rows = speech_hit_rows({"The Riddle of the Red Hat": _info(*pages)}, max_len=32, sortable=True)
    assert rows[0].text == "Riddle of the Red Hat, 5,..."


def test_a_sortable_row_shorter_still_cuts_the_title_with_no_stray_article() -> None:
    pages = ["5", "9", "12", "13", "14", "20"]
    rows = speech_hit_rows({"The Riddle of the Red Hat": _info(*pages)}, max_len=24, sortable=True)
    assert rows[0].text == "Riddle of the..., 5,..."


@pytest.mark.parametrize(
    ("max_len", "text"),
    [(30, "Long, Long Road Home, 5,..."), (26, "Long, Long Road..., 5,...")],
    ids=["the title kept", "the title cut"],
)
def test_a_sortable_row_gives_up_only_its_article_from_a_title_with_its_own_comma(
    max_len: int, text: str
) -> None:
    # The article is what follows the last comma, not everything after the first.
    pages = ["5", "9", "12", "13", "14", "20"]
    rows = speech_hit_rows(
        {"The Long, Long Road Home": _info(*pages)}, max_len=max_len, sortable=True
    )
    assert rows[0].text == text


def test_rows_sort_by_their_text_not_their_title() -> None:
    rows = speech_hit_rows(
        {"Lost in the Andes!": _info("3"), "The Apple Tree": _info("1")},
        max_len=MAX_TITLE_AND_PAGES_LEN,
        sortable=True,
    )
    assert [row.text for row in rows] == ["Apple Tree, The, 1", "Lost in the Andes!, 3"]
