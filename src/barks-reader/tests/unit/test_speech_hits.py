"""A speech search's hits as rows (barks_reader.core.speech_hits)."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

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
    assert [row.text for row in rows] == ["Lost in the Andes!, 3", "Old Castle's Secret, 5, The"]


def test_a_long_page_list_is_cut_to_the_length_less_the_count() -> None:
    pages = [str(p) for p in range(1, 40, 2)]
    rows = speech_hit_rows({"A Title": _info(*pages)}, max_len=30, hit_counts={"A Title": 12})
    assert len(rows[0].text) <= 30  # noqa: PLR2004
    assert rows[0].text.endswith(" (12)")
