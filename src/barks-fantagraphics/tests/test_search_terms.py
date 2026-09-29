# cspell:ignore dnald duckin makin runnin scroge treasurez xqzv
"""The word search box's matcher: the text itself, then prefixes, then (from 3 letters) inside."""

from __future__ import annotations

import pytest
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


# For typed queries: word forms, wildcards and suggestions (phase 5).
FORM_WORDS = [
    *("duck", "Duck's", "ducked", "ducking", "duckin'", "ducks", "duckling"),
    *("run", "running", "runnin'", "runs", "make", "making", "makin'", "makes"),
    *("city", "cities", "shout", "shouted", "stop", "stopped", "thing", "things", "th"),
    *("Scrooge", "scrounge", "gold", "golden", "goldmines", "Donald", "Don Quixote"),
]
FORMS = TermLexicon(FORM_WORDS)


@pytest.mark.parametrize(
    ("word", "forms"),
    [
        ("duck", ("duck", "duck's", "ducked", "duckin'", "ducking", "ducks")),
        ("ducking", ("duck", "duck's", "ducked", "duckin'", "ducking", "ducks")),  # and back
        ("DUCK", ("duck", "duck's", "ducked", "duckin'", "ducking", "ducks")),
        ("run", ("run", "runnin'", "running", "runs")),  # the doubled n
        ("running", ("run", "runnin'", "running", "runs")),
        ("make", ("make", "makes", "makin'", "making")),  # the dropped e
        ("city", ("cities", "city")),
        ("cities", ("cities", "city")),
        ("stop", ("stop", "stopped")),
        ("shout", ("shout", "shouted")),
        ("thing", ("thing", "things")),  # not "th" + "ing"
        ("golden", ("golden",)),  # a different word, not a form of gold
        ("xyzzy", ()),  # held by nothing: no forms
        ("don quixote", ()),  # several words: a phrase, not a word with forms
        ("", ()),
    ],
)
def test_a_word_s_forms_are_the_ones_the_index_holds(word: str, forms: tuple[str, ...]) -> None:
    assert FORMS.variants(word) == forms


@pytest.mark.parametrize(
    ("pattern", "words"),
    [
        ("gol*", ["gold", "golden", "goldmines"]),
        ("*uck", ["duck"]),
        ("d?ck", ["duck"]),
        ("DUCK*", ["duck", "duck's", "ducked", "duckin'", "ducking", "duckling", "ducks"]),
        ("c*s", ["cities"]),
        ("don*", ["donald"]),  # one word: "Don Quixote" is two
        ("zz*", []),
        ("du.k*", []),  # the dot is itself, not any letter
    ],
)
def test_a_wildcard_is_the_single_words_it_matches(pattern: str, words: list[str]) -> None:
    matches = FORMS.expand_wildcard(pattern)
    assert matches.words == words
    assert matches.total == len(words)


def test_a_broad_wildcard_is_capped_and_counted() -> None:
    many = TermLexicon([f"word{n:04d}" for n in range(250)])
    matches = many.expand_wildcard("word*")
    assert len(matches.words) == 200  # noqa: PLR2004
    assert matches.total == 250  # noqa: PLR2004
    assert many.expand_wildcard("word*", limit=5).words == [f"word{n:04d}" for n in range(5)]


def test_suggestions_are_close_spellings_as_displayed() -> None:
    assert FORMS.suggest("scroge")[:2] == ["Scrooge", "scrounge"]
    assert FORMS.suggest("dnald") == ["Donald"]
    assert FORMS.suggest("xqzv") == []
    assert FORMS.suggest("") == []


def test_a_held_word_is_not_suggested_for_itself() -> None:
    assert "Scrooge" not in FORMS.suggest("scrooge")


def test_suggestions_are_limited() -> None:
    many = TermLexicon([f"treasure{c}" for c in "abcdefgh"])
    assert len(many.suggest("treasurez")) == 5  # noqa: PLR2004
    assert len(many.suggest("treasurez", limit=2)) == 2  # noqa: PLR2004


def test_contains_and_multi_word() -> None:
    assert FORMS.contains("SCROOGE")
    assert FORMS.contains("don quixote")
    assert not FORMS.contains("xyzzy")
    assert TermLexicon.is_multi_word("Don Quixote")
    assert not TermLexicon.is_multi_word("duck")
