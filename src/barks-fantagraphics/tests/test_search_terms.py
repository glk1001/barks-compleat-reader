"""The word search box's matcher: the text itself, then prefixes, then (from 3 letters) inside."""

from __future__ import annotations

from barks_fantagraphics.search_terms import (
    MAX_MATCHES_SHOWN,
    SUBSTRING_MIN_CHARS,
    TermLexicon,
)

TERMS = [
    "Don Gaspar",
    "Don Quixote",
    "Donna Duck",
    "abandon",
    "airline",
    "airliner",
    "airlines",
    "don",
    "done",
    "pardon",
    "quixote",
]
LEXICON = TermLexicon(TERMS)


def _words(text: str) -> list[str]:
    return LEXICON.matching(text).words


def test_the_text_itself_then_prefixes_then_inside() -> None:
    assert _words("don") == [
        "don",  # the text itself
        "Don Gaspar",  # then words that start with it, in the box's plain sort
        "Don Quixote",
        "Donna Duck",
        "done",
        "abandon",  # then words with it inside
        "pardon",
    ]


def test_an_exact_word_comes_first_even_when_it_sorts_later() -> None:
    """Return in the box picks the first row, so a word typed whole must be it."""
    assert _words("airline")[0] == "airline"
    assert _words("airline") == ["airline", "airliner", "airlines"]


def test_inside_a_word_only_from_three_letters() -> None:
    assert SUBSTRING_MIN_CHARS == 3  # noqa: PLR2004
    assert "abandon" not in _words("do")
    assert _words("do") == ["Don Gaspar", "Don Quixote", "Donna Duck", "don", "done"]
    assert _words("irl") == ["airline", "airliner", "airlines"]


def test_any_case_and_several_words() -> None:
    """Regression: 'don qu' must match 'Don Quixote', a mixed-case term."""
    assert _words("don qu") == ["Don Quixote"]
    assert _words("DON QUIXOTE") == ["Don Quixote"]
    assert _words("quixote") == ["quixote", "Don Quixote"]


def test_no_match_and_nothing_typed() -> None:
    assert LEXICON.matching("doz").total == 0
    assert LEXICON.matching("").words == []
    assert LEXICON.matching("   ").total == 0


def test_one_letter_matches_every_word_starting_with_it() -> None:
    assert _words("d") == ["Don Gaspar", "Don Quixote", "Donna Duck", "don", "done"]


def test_a_long_list_is_capped_and_the_rest_counted() -> None:
    many = TermLexicon([f"word{n:04d}" for n in range(MAX_MATCHES_SHOWN + 25)])
    matches = many.matching("word")
    assert len(matches.words) == MAX_MATCHES_SHOWN
    assert matches.total == MAX_MATCHES_SHOWN + 25
    assert matches.more == 25  # noqa: PLR2004
    assert many.matching("word", limit=None).more == 0
    assert many.matching("word", limit=10).words == [f"word{n:04d}" for n in range(10)]


def test_its_size_is_the_word_count() -> None:
    assert len(LEXICON) == len(TERMS)
