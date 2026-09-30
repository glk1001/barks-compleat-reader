# cspell:ignore chna goldd scroge scroged
"""The word search's query language: text in, a tree or an error out, never an exception."""

from __future__ import annotations

import pytest
from barks_fantagraphics.search_query import (
    NEAR_DEFAULT_DISTANCE,
    And,
    AnyTerm,
    Combine,
    Near,
    NearQuery,
    Not,
    Or,
    Phrase,
    TagQualifier,
    VolumeQualifier,
    Word,
    YearQualifier,
    has_query_syntax,
    parse_query,
    query_from_words,
    read_range,
    replace_word,
)
from hypothesis import given, settings
from hypothesis import strategies as st

# The grammar's own pieces, joined in any order and number, spaces or none between.
SYNTAX_PIECES = [
    *("gold", "mine", "g*", "gol?", "indo-china", "1950", "55", "7"),
    *("AND", "and", "&", "OR", "or", "|", "NOT", "not", "-", "+", "NEAR", "NEAR/3", "NEAR/0"),
    *("(", ")", '"', "tag:", "year:", "vol:", "foo:", " ", " ", " "),
]
GOLD, MINE, DUCK = Word("gold"), Word("mine"), Word("duck")


@pytest.mark.parametrize(
    ("text", "tree"),
    [
        # words, and the words that stay one word
        ("gold", GOLD),
        ("  gold  ", GOLD),
        ("indo-china", Word("indo-china")),
        ("100-foot", Word("100-foot")),
        ("500,000,000...", Word("500,000,000...")),
        ("G.I.", Word("G.I.")),
        ("near", Word("near")),  # a searchable word: only NEAR is the operator
        # AND: a space, the word, or &
        ("gold mine", And((GOLD, MINE))),
        ("gold AND mine", And((GOLD, MINE))),
        ("gold and mine", And((GOLD, MINE))),
        ("gold & mine", And((GOLD, MINE))),
        ("gold&mine", And((GOLD, MINE))),
        # OR binds looser than AND
        ("gold OR mine", Or((GOLD, MINE))),
        ("gold | mine", Or((GOLD, MINE))),
        ("gold or mine duck", Or((GOLD, And((MINE, DUCK))))),
        ("gold mine | duck", Or((And((GOLD, MINE)), DUCK))),
        # NOT and +
        ("-duck", Not(DUCK)),
        ("gold -duck", And((GOLD, Not(DUCK)))),
        ("gold NOT duck", And((GOLD, Not(DUCK)))),
        ("gold not duck", And((GOLD, Not(DUCK)))),
        ("+gold", GOLD),
        ("gold +mine", And((GOLD, MINE))),
        ("NOT NOT duck", Not(Not(DUCK))),
        # brackets
        ("(gold)", GOLD),
        ("(gold OR mine) duck", And((Or((GOLD, MINE)), DUCK))),
        ("gold (mine | duck)", And((GOLD, Or((MINE, DUCK))))),
        ("-(gold mine)", Not(And((GOLD, MINE)))),
        # quotes: one word exact, several a phrase
        ('"gold"', Word("gold", exact=True)),
        ('"pirate gold"', Phrase(("pirate", "gold"))),
        ('"pirate  gold" mine', And((Phrase(("pirate", "gold")), MINE))),
        ('-"pirate gold"', Not(Phrase(("pirate", "gold")))),
        # NEAR
        ("gold NEAR mine", NearQuery(GOLD, MINE, NEAR_DEFAULT_DISTANCE)),
        ("gold NEAR/3 mine", NearQuery(GOLD, MINE, 3)),
        ("gold NEAR mine duck", And((NearQuery(GOLD, MINE), DUCK))),
        # wildcards
        ("gol*", Word("gol*")),
        ("g?ld", Word("g?ld")),
        ('"gol*"', Word("gol*", exact=True)),  # quoted, still a wildcard
        # qualifiers
        ("tag:scrooge", TagQualifier("scrooge")),
        ('tag:"uncle scrooge"', TagQualifier("uncle scrooge")),
        ("TAG:scrooge gold", And((TagQualifier("scrooge"), GOLD))),
        ("year:1950", YearQualifier(1950, 1950)),
        ("year:1950-55", YearQualifier(1950, 1955)),
        ("year:1950-1955", YearQualifier(1950, 1955)),
        ("year:1948-9", YearQualifier(1948, 1949)),
        ("vol:7", VolumeQualifier(7, 7)),
        ("vol:5-8", VolumeQualifier(5, 8)),
        ("gold -year:1950", And((GOLD, Not(YearQualifier(1950, 1950))))),
    ],
)
def test_a_query_parses_to_its_tree(text: str, tree: object) -> None:
    parsed = parse_query(text)
    assert parsed.error is None, parsed.error
    assert parsed.root == tree
    assert parsed.ok


@pytest.mark.parametrize(
    ("text", "position", "says"),
    [
        ("(gold", 0, "not closed"),
        ("gold)", 4, "no opening"),
        ("()", 0, "empty"),
        ('"gold', 0, "not closed"),
        ('""', 0, "empty"),
        ("gold AND", 5, "nothing to search after"),
        ("gold OR", 5, "nothing to search after"),
        ("-", 0, "nothing to search after"),
        ("gold -", 5, "nothing to search after"),
        ("NOT", 0, "nothing to search after"),
        ("gold | | mine", 5, "nothing to search after"),
        ("AND gold", 0, "needs something"),
        ("gold NEAR", 5, "needs a word after"),
        ('gold NEAR "pirate gold"', 5, "needs a word after"),
        ("gold NEAR/0 mine", 5, "at least 1"),
        ("*", 0, "wildcard"),
        ("g*", 0, "wildcard"),
        ('"*"', 0, "wildcard"),  # quotes do not make it a word: no word holds *
        ('gold "g?"', 5, "wildcard"),
        ("foo:bar", 0, "not a filter"),
        ("tag:", 0, "needs a value"),
        ("year:abc", 0, "a number or a range"),
        ("year:1955-50", 0, "backwards"),
        ('vol:"7"', 0, "not quotes"),
        ("gold year:x-1", 5, "a number or a range"),
    ],
)
def test_bad_syntax_is_an_error_at_its_position(text: str, position: int, says: str) -> None:
    parsed = parse_query(text)
    assert parsed.root is None
    assert parsed.error is not None
    assert parsed.error.position == position
    assert says in parsed.error.message
    assert not parsed.ok


def test_nothing_typed_is_neither_tree_nor_error() -> None:
    for text in ("", "   "):
        parsed = parse_query(text)
        assert (parsed.root, parsed.error, parsed.ok) == (None, None, False)


@given(st.text(max_size=80))
@settings(max_examples=500)
def test_no_text_makes_the_parser_raise(text: str) -> None:
    parsed = parse_query(text)
    assert (parsed.root is None) or (parsed.error is None)


@given(st.lists(st.sampled_from(SYNTAX_PIECES), max_size=25).map("".join))
@settings(max_examples=1000)
def test_no_mix_of_the_syntax_characters_makes_it_raise(text: str) -> None:
    parse_query(text)
    has_query_syntax(text)


@pytest.mark.parametrize(
    ("text", "syntax"),
    [
        ("gold", False),
        ("gold mine", False),  # plain words: the word list is tried first
        ("indo-china", False),
        ("don quixote", False),
        ("", False),
        ('"gold"', True),
        ("(gold)", True),
        ("gold AND mine", True),
        ("gold and mine", True),
        ("gold -duck", True),
        ("gold | mine", True),
        ("gold NEAR mine", True),
        ("gol*", True),
        ("tag:scrooge", True),
        ('"gold', True),  # tried and got wrong: still a query
        ("foo:bar", True),
    ],
)
def test_has_query_syntax(text: str, syntax: bool) -> None:
    assert has_query_syntax(text) is syntax


def test_words_picked_from_the_list_are_exact_and_combined() -> None:
    assert query_from_words([], Combine.ALL) is None
    assert query_from_words(["gold"], Combine.ANY) == Word("gold", exact=True)
    gold, mine = Word("gold", exact=True), Word("mine", exact=True)
    assert query_from_words(["gold", "mine"], Combine.ALL) == And((gold, mine))
    assert query_from_words(["gold", "mine"], Combine.ANY) == Or((gold, mine))


@pytest.mark.parametrize(
    ("lefts", "rights", "near"),
    [
        ([1], [3], True),  # two apart, at most two
        ([3], [1], True),  # either order
        ([1], [4], False),
        ([2], [2], False),  # one word is not a pair
        ([2, 9], [2, 10], True),
        ([], [1], False),
    ],
)
def test_near_holds_two_different_words_at_most_its_distance_apart(
    lefts: list[int], rights: list[int], near: bool
) -> None:
    assert Near(AnyTerm(("gold",)), AnyTerm(("mine",)), 2).is_near(lefts, rights) is near


def test_a_wildcard_word_knows_it_is_one() -> None:
    assert Word("gol*").is_wildcard
    assert Word("g?ld").is_wildcard
    assert not GOLD.is_wildcard


@pytest.mark.parametrize("text", ["(" * 5000 + "gold" + ")" * 5000, "-" * 5000 + "gold"])
def test_nesting_past_the_recursion_limit_is_an_error_not_a_crash(text: str) -> None:
    parsed = parse_query(text)
    assert parsed.error is not None
    assert parsed.root is None


@pytest.mark.parametrize(
    ("text", "word", "replacement", "result"),
    [
        ("scroge", "scroge", "Scrooge", "Scrooge"),
        ("SCROGE -gold", "scroge", "Scrooge", "Scrooge -gold"),
        ("(scroge OR gold) scroge", "scroge", "Scrooge", "(Scrooge OR gold) Scrooge"),
        ("scroged scroge's scroge", "scroge", "Scrooge", "scroged scroge's Scrooge"),
        ('"pirate goldd"', "goldd", "gold", '"pirate gold"'),
        ("indo-chna", "indo-chna", "indo-china", "indo-china"),
        ("a.b a.b", "a.b", "x", "x x"),
    ],
)
def test_replace_word_swaps_the_whole_word_only(
    text: str, word: str, replacement: str, result: str
) -> None:
    assert replace_word(text, word, replacement) == result


def test_read_range_is_the_qualifiers_range_for_other_parsers() -> None:
    assert read_range("1948-9", years=True) == (1948, 1949)
    assert read_range("5-8", years=False) == (5, 8)
    with pytest.raises(ValueError, match="runs backwards"):
        read_range("8-5", years=False)
