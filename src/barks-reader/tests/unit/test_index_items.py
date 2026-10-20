"""What an index row opens (barks_reader.core.index_items)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.index_items import entity_index, title_row_item


def test_a_title_row_opens_at_its_first_page_with_every_page_it_lists() -> None:
    """The title view steps through all of a term's pages, as a tag's, not just the first."""
    pages = {f"fanta-{p}": MagicMock(comic_page=p) for p in ("3", "4", "5", "12")}
    item = title_row_item(
        "Donald Duck Finds Pirate Gold", "3", "Pirate Gold, 3-5,12", MagicMock(fanta_pages=pages)
    )
    assert item.id == Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
    assert item.page_to_goto == "3"
    assert item.tagged_pages == ("3", "4", "5", "12")


class TestEntityIndex:
    def test_terms_are_listed_under_their_first_letter_in_order(self) -> None:
        index = entity_index(["Scrooge McDuck", "Donald Duck", "daisy duck", "Sheriff"])
        assert {letter: [i.id for i in items] for letter, items in index.items()} == {
            "S": ["Scrooge McDuck", "Sheriff"],
            "D": ["Donald Duck", "daisy duck"],
        }

    def test_a_row_shows_its_term(self) -> None:
        (item,) = entity_index(["Gladstone Gander"])["G"]
        assert item.id == "Gladstone Gander"
        assert item.display_text == "Gladstone Gander"
        assert item.page_to_goto == ""
        assert item.tagged_pages == ()

    def test_a_long_term_is_shortened_for_its_row(self) -> None:
        term = "A" * 60
        (item,) = entity_index([term])["A"]
        assert item.id == term
        assert len(item.display_text) < len(term)

    def test_an_empty_term_is_left_out(self) -> None:
        assert {k: [i.id for i in v] for k, v in entity_index(["", "Alice"]).items()} == {
            "A": ["Alice"]
        }

    def test_a_term_not_starting_with_a_letter_is_an_error(self) -> None:
        with pytest.raises(RuntimeError, match="non-alpha prefix"):
            entity_index(["Alice", "-ER-"])
