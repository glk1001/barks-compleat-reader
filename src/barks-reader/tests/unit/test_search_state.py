"""The search screen's picked words: added, removed, combined, and run as a query."""

from __future__ import annotations

import pytest
from barks_fantagraphics.search_filters import SearchFilter
from barks_fantagraphics.search_query import (
    And,
    Combine,
    Phrase,
    Word,
    parse_query,
    query_from_words,
)
from barks_fantagraphics.tag_query import TagSelection
from barks_reader.core.search_state import ALL_YEARS, EraChoice, TagBasket, TagState, WordBasket


def test_a_word_is_picked_then_put_back_by_the_same_toggle() -> None:
    basket = WordBasket()
    assert basket.toggle("gold") is True
    assert basket.toggle("mine") is True
    assert (basket.words, len(basket), "gold" in basket) == (["gold", "mine"], 2, True)
    assert basket.toggle("gold") is False
    assert basket.words == ["mine"]


def test_remove_and_clear() -> None:
    basket = WordBasket(["gold", "mine"], Combine.ANY)
    basket.remove("gold")
    basket.remove("not picked")
    assert basket.words == ["mine"]
    basket.clear()
    assert (basket.words, basket.combine, bool(basket)) == ([], Combine.ALL, False)


def test_flip_switches_all_and_any() -> None:
    basket = WordBasket(["gold"])
    assert basket.flip() is Combine.ANY
    assert basket.flip() is Combine.ALL


def test_the_query_text_quotes_each_word() -> None:
    assert WordBasket().query_text() == ""
    assert WordBasket(["gold", "don quixote"]).query_text() == '"gold" "don quixote"'
    assert WordBasket(["gold", "mine"], Combine.ANY).query_text() == '"gold" | "mine"'


@pytest.mark.parametrize("combine", list(Combine))
@pytest.mark.parametrize(
    "words",
    [["gold"], ["gold", "mine"], ["gold", "duck's", "500,000,000...", "g.i."]],
)
def test_the_query_text_parses_to_the_tree_picked_words_make(
    words: list[str], combine: Combine
) -> None:
    """A basket runs as typed text, and that text is exactly the picked words' query."""
    parsed = parse_query(WordBasket(words, combine).query_text())
    assert parsed.error is None
    assert parsed.root == query_from_words(words, combine)


def test_a_picked_term_of_several_words_runs_as_its_phrase() -> None:
    """Quoted, it parses as the phrase the evaluator makes of an exact term of several words."""
    parsed = parse_query(WordBasket(["gold", "don quixote"]).query_text())
    assert parsed.root == And((Word("gold", exact=True), Phrase(("don", "quixote"))))


def test_a_tag_is_picked_to_include_then_put_back_by_the_same_toggle() -> None:
    basket = TagBasket()
    assert basket.toggle("Scrooge") is True
    assert basket.tags == {"Scrooge": TagState.INCLUDED}
    assert ("Scrooge" in basket, len(basket)) == (True, 1)
    assert basket.toggle("Scrooge") is False
    assert not basket


def test_a_picked_tag_cycles_included_left_out_put_back() -> None:
    basket = TagBasket()
    basket.toggle("Gyro")
    assert basket.cycle("Gyro") is TagState.EXCLUDED
    assert basket.cycle("Gyro") is None
    assert "Gyro" not in basket
    assert basket.cycle("Gyro") is None  # not picked: nothing to do


def test_the_toggle_puts_back_a_left_out_tag_too() -> None:
    basket = TagBasket()
    basket.toggle("Gyro")
    basket.cycle("Gyro")
    assert basket.toggle("Gyro") is False


def test_the_selection_keeps_the_order_picked_and_the_mode() -> None:
    basket = TagBasket()
    for tag in ("Scrooge", "Christmas", "Gyro"):
        basket.toggle(tag)
    basket.cycle("Christmas")
    basket.flip()
    assert basket.selection() == TagSelection(("Scrooge", "Gyro"), ("Christmas",), Combine.ANY)
    basket.clear()
    assert (basket.tags, basket.combine) == ({}, Combine.ALL)


def test_a_typed_selection_fills_the_basket_with_the_labels_known() -> None:
    basket = TagBasket()
    basket.toggle("Donald")
    basket.fill(
        TagSelection(("scrooge", "gyro"), ("andes",), Combine.ANY), labels={"scrooge": "Scrooge"}
    )
    assert basket.tags == {
        "Scrooge": TagState.INCLUDED,
        "gyro": TagState.INCLUDED,
        "andes": TagState.EXCLUDED,
    }
    assert basket.combine is Combine.ANY


RANGES = ((1942, 1946), (1951, 1954), (1962, 1971))


def test_the_era_chips_are_all_years_then_each_range() -> None:
    assert EraChoice(RANGES).options() == [
        ("", "All years"),
        ("1942-1946", "1942-46"),
        ("1951-1954", "1951-54"),
        ("1962-1971", "1962-71"),
    ]


def test_picking_an_era_and_lifting_it() -> None:
    era = EraChoice(RANGES)
    assert (era.years, era.value, era.label, era.search_filter()) == (
        None,
        ALL_YEARS,
        "All years",
        None,
    )
    assert era.allows(1942)
    era.select("1951-1954")
    assert (era.years, era.value, era.label) == ((1951, 1954), "1951-1954", "1951-54")
    assert era.search_filter() == SearchFilter(years=(1951, 1954))
    assert era.allows(1951)
    assert era.allows(1954)
    assert not era.allows(1955)
    era.select(ALL_YEARS)
    assert era.years is None
    era.select("1900-1901")  # not offered
    assert era.years is None
