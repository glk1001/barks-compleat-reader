# cspell:ignore Émile Ögel Ogel Øresund
"""What an index row opens (barks_reader.core.index_items)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.entity_types import EntityType
from barks_fantagraphics.whoosh_barks_terms import CONTEXT_SENSITIVE_WORDS
from barks_reader.core.index_items import (
    IndexItem,
    context_entities,
    entity_index,
    title_row_item,
    word_index_items,
)


def test_a_title_row_opens_at_its_first_page_with_every_page_it_lists() -> None:
    """The title view steps through all of a term's pages, as a tag's, not just the first."""
    pages = {f"fanta-{p}": MagicMock(comic_page=p) for p in ("3", "4", "5", "12")}
    item = title_row_item(
        "Donald Duck Finds Pirate Gold", "3", "Pirate Gold, 3-5,12", MagicMock(fanta_pages=pages)
    )
    assert item.id == Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
    assert item.display_text == "Pirate Gold, 3-5,12"
    assert item.page_to_goto == "3"
    assert item.tagged_pages == ("3", "4", "5", "12")


class TestEntityIndex:
    def test_terms_are_listed_under_their_first_letter_in_order(self) -> None:
        index = entity_index(["Scrooge McDuck", "Donald Duck", "daisy duck", "Sheriff"])
        assert {letter: [i.id for i in items] for letter, items in index.items()} == {
            "S": ["Scrooge McDuck", "Sheriff"],
            "D": ["Donald Duck", "daisy duck"],
        }

    def test_a_first_letter_that_unfolds_into_two_files_under_the_first(self) -> None:
        """A ligature ("ﬁ") comes apart into two letters when its accents are taken off."""
        assert list(entity_index(["ﬁsh Island"])) == ["F"]

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

    @pytest.mark.parametrize("term", ["_Underscore", "[Bracket]", "`Tick"])
    def test_the_signs_between_the_two_alphabets_are_no_letters(self, term: str) -> None:
        with pytest.raises(RuntimeError, match="non-alpha prefix"):
            entity_index([term])

    def test_z_is_a_letter(self) -> None:
        assert [i.id for i in entity_index(["Zinc"])["Z"]] == ["Zinc"]

    def test_an_accented_first_letter_files_under_its_plain_letter(self) -> None:
        """An accented name once raised for the whole index."""
        index = entity_index(["Émile", "Ögel", "Eggs"])
        assert {k: [i.id for i in v] for k, v in index.items()} == {
            "E": ["Émile", "Eggs"],
            "O": ["Ögel"],
        }

    def test_a_letter_with_no_plain_form_is_still_an_error(self) -> None:
        with pytest.raises(RuntimeError, match="non-alpha prefix"):
            entity_index(["Øresund"])


class TestContextEntities:
    def test_every_ambiguous_word_has_its_fallback_and_each_rule_s_entity(self) -> None:
        entities = context_entities()

        assert set(entities) == set(CONTEXT_SENSITIVE_WORDS)
        for word, (fallback_type, fallback_canonical, rules) in CONTEXT_SENSITIVE_WORDS.items():
            assert (fallback_type, fallback_canonical) in entities[word]
            assert len(entities[word]) == 1 + len(rules)

    def test_a_word_s_entities_are_in_their_names_order_whatever_the_case(self) -> None:
        for named in context_entities().values():
            names = [canonical.lower() for _kind, canonical in named]
            assert names == sorted(names)

    def test_daisy_is_a_person_and_a_flower(self) -> None:
        assert context_entities()["daisy"] == [
            (EntityType.PERSON, "Daisy"),
            (EntityType.MISC, "daisy"),
        ]


class TestWordIndexItems:
    _ENTITIES = {  # noqa: RUF012
        "donald": [(EntityType.PERSON, "Donald Duck"), (EntityType.PERSON, "Donald Mallard")]
    }

    def test_a_plain_word_is_one_row_with_no_entity(self) -> None:
        assert word_index_items(["duck"], self._ENTITIES) == [IndexItem("duck", "duck")]

    def test_a_word_that_names_entities_is_listed_as_each_of_them_in_its_place(self) -> None:
        items = word_index_items(["dog", "Donald", "duck"], self._ENTITIES)

        assert [(i.id, i.display_text, i.entity_type) for i in items] == [
            ("dog", "dog", None),
            ("Donald Duck", "Donald Duck", EntityType.PERSON),
            ("Donald Mallard", "Donald Mallard", EntityType.PERSON),
            ("duck", "duck", None),
        ]

    def test_no_terms_make_no_rows(self) -> None:
        assert word_index_items([], self._ENTITIES) == []
