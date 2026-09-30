"""The search screen's picked words: added, removed, combined, and run as a query."""

from __future__ import annotations

import pytest
from barks_fantagraphics.search_query import (
    And,
    Combine,
    Phrase,
    Word,
    parse_query,
    query_from_words,
)
from barks_reader.core.search_state import WordBasket


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
