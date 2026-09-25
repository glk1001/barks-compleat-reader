"""How the index screens write a title or tag (barks_reader.core.index_text)."""

from __future__ import annotations

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.index_text import (
    MAX_TITLE_AND_PAGES_LEN,
    indexable_title,
    indexable_title_from_str,
    sortable_string,
)


@pytest.mark.parametrize(
    ("text", "listed"),
    [
        ("The Ghost of the Grotto", "Ghost of the Grotto, The"),
        ("A Christmas for Shacktown", "Christmas for Shacktown, A"),
        ("Lost in the Andes!", "Lost in the Andes!"),
        ("Theatre Trouble", "Theatre Trouble"),  # "The" only as a word of its own
    ],
)
def test_a_leading_article_moves_to_the_end(text: str, listed: str) -> None:
    assert sortable_string(text) == listed


def test_a_long_title_is_shortened_to_fit_a_row() -> None:
    listed = indexable_title_from_str("The " + "word " * 20)
    assert len(listed) <= MAX_TITLE_AND_PAGES_LEN + len(", The")
    assert "..." in listed


def test_a_title_enum_is_listed_by_its_title() -> None:
    assert indexable_title(Titles.GHOST_OF_THE_GROTTO_THE) == "Ghost of the Grotto, The"
