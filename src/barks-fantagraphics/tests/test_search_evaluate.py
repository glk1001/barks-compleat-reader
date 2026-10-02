# cspell:ignore monney clasics bearz
"""A typed word query, run: AND and NOT by story, phrases and NEAR by bubble, filters, notices.

Against the fake engine over a small corpus of real stories (their years and tags
are the title tables' own), tokenized by the index's analyzer.
"""

from __future__ import annotations

import pytest
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.search_evaluate import Suggestion, evaluate_query, run_query_text
from barks_fantagraphics.search_filters import SearchFilter, tag_titles, titles_in_years
from barks_fantagraphics.search_query import (
    AnyTerm,
    Combine,
    Phrase,
    Word,
    query_from_words,
)
from barks_fantagraphics.search_results import TitleInfo
from barks_fantagraphics.search_terms import MAX_WILDCARD_TERMS, TermLexicon
from barks_fantagraphics.testing.fake_search import FakeBubble, InMemoryFullTextSearch
from barks_fantagraphics.whoosh_search_engine import MY_STOP_WORDS, build_index_schema

PIRATE = ENUM_TO_STR_TITLE[Titles.DONALD_DUCK_FINDS_PIRATE_GOLD]  # 1942, volume 1
BEAR = ENUM_TO_STR_TITLE[Titles.CHRISTMAS_ON_BEAR_MOUNTAIN]  # 1947, volume 5
ANDES = ENUM_TO_STR_TITLE[Titles.LOST_IN_THE_ANDES]  # 1948, volume 7, a classic
HELMET = ENUM_TO_STR_TITLE[Titles.GOLDEN_HELMET_THE]  # 1951, volume 11, a classic
POOR = ENUM_TO_STR_TITLE[Titles.ONLY_A_POOR_OLD_MAN]  # 1951, volume 12, a classic

CORPUS = [
    FakeBubble(PIRATE, "Pirate gold! A mine of gold in the old mine!", 1, "001", speaker="Donald"),
    FakeBubble(PIRATE, "The ducks are ducking the parrot.", 1, "002", group_id="2"),
    FakeBubble(BEAR, "A bear in the mine? Ducking bears!", 5, "040", speaker="Scrooge"),
    FakeBubble(ANDES, "Square eggs! Gold is nowhere in the Andes.", 7, "010", speaker="Donald"),
    FakeBubble(ANDES, "Gold far away here buried in the mine", 7, "011", speaker="Scrooge"),
    FakeBubble(HELMET, "The golden helmet belongs to the finder", 11, "030"),
    FakeBubble(POOR, "My money! My gold coins! The Beagle Boys!", 12, "020", speaker="Scrooge"),
]


def _tokens(text: str) -> list[str]:
    analyzer = build_index_schema()["unstemmed"].analyzer
    return [token.text for token in analyzer(text)]


@pytest.fixture
def fake() -> InMemoryFullTextSearch:
    return InMemoryFullTextSearch(bubbles=list(CORPUS), tokenize=_tokens)


@pytest.fixture
def lexicon() -> TermLexicon:
    return TermLexicon(sorted({t for b in CORPUS for t in _tokens(b.text)}))


def _stories(text: str, fake: InMemoryFullTextSearch, lexicon: TermLexicon) -> list[str]:
    result = run_query_text(text, fake, lexicon, stop_words=MY_STOP_WORDS)
    assert result.error is None, result.error
    return list(result.title_dict)


@pytest.mark.parametrize(
    ("text", "stories"),
    [
        ("gold", [PIRATE, ANDES, POOR]),  # golden is not a form of gold
        # AND: the same story, not the same bubble
        ("gold mine", [PIRATE, ANDES]),
        ("gold AND mine", [PIRATE, ANDES]),
        # a phrase: one bubble, in order
        ('"gold mine"', [PIRATE]),
        ('"gold pirate"', []),
        ('"mine of gold"', [PIRATE]),  # stop words are dropped from a phrase too
        # NEAR: one bubble, either order, five words by default (stop words not counted)
        ("gold NEAR mine", [PIRATE, ANDES]),
        ("mine NEAR gold", [PIRATE, ANDES]),
        ("gold NEAR/1 mine", [PIRATE]),
        # OR and NOT
        ("gold OR helmet", [PIRATE, ANDES, HELMET, POOR]),
        ("gold -mine", [POOR]),
        ("gold NOT mine", [POOR]),
        ("gold -(mine OR coins)", []),
        ("gold NOT NOT mine", [PIRATE, ANDES]),
        ("(gold OR bear) mine", [PIRATE, BEAR, ANDES]),
        # word forms, for bare words only
        ("duck", [PIRATE, BEAR]),
        ("bear", [BEAR]),
        ('"duck"', []),
        ("gol*", [PIRATE, ANDES, HELMET, POOR]),
        ("go?d", [PIRATE, ANDES, POOR]),
        # filters beside words
        ("gold year:1948-1951", [ANDES, POOR]),
        ("gold -year:1948", [PIRATE, POOR]),
        ("gold vol:12", [POOR]),
        ("gold vol:1-7", [PIRATE, ANDES]),
        ('gold tag:"the classics"', [ANDES, POOR]),
        ('gold -tag:"the classics"', [PIRATE]),
        ("mine (year:1942 OR year:1947)", [PIRATE, BEAR]),
        ('gol* tag:"the classics" -vol:7', [HELMET, POOR]),
    ],
)
def test_a_query_finds_its_stories(
    text: str, stories: list[str], fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    assert sorted(_stories(text, fake, lexicon)) == sorted(stories)


def test_the_corpus_stories_have_the_years_and_tags_the_tests_assume() -> None:
    classics = tag_titles("the classics")
    assert classics is not None
    assert {ANDES, HELMET, POOR} <= classics
    assert not {PIRATE, BEAR} & classics
    assert titles_in_years(1948, 1951) >= {ANDES, HELMET, POOR}
    assert not {PIRATE, BEAR} & titles_in_years(1948, 1951)


def test_and_keeps_every_parts_bubbles_and_counts_them(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text("gold mine", fake, lexicon, stop_words=MY_STOP_WORDS)
    assert result.hit_counts == {ANDES: 2, PIRATE: 1}
    assert list(result.title_dict[ANDES].fanta_pages) == ["010", "011"]


def test_the_terms_searched_are_highlighted_but_not_those_taken_away(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text('duck "pirate gold" -mine', fake, lexicon, stop_words=MY_STOP_WORDS)
    assert set(result.highlight_terms) == {"ducks", "ducking", "pirate", "gold"}


def test_phrases_run_first_and_each_part_searches_only_the_stories_found(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    run_query_text('gold "pirate gold" -parrot', fake, lexicon, stop_words=MY_STOP_WORDS)
    leaves = [(leaf, titles) for leaf, _, titles in fake.bubble_calls]
    assert leaves == [
        (Phrase(("pirate", "gold")), None),
        (AnyTerm(("gold",)), frozenset({PIRATE})),
        (AnyTerm(("parrot",)), frozenset({PIRATE})),
    ]


def test_a_phrase_of_stop_words_only_finds_nothing_as_in_the_index(
    fake: InMemoryFullTextSearch,
) -> None:
    assert fake.find_bubbles(Phrase(("of", "the"))) == {}


def test_a_quoted_wildcard_runs_after_the_words_it_is_as_broad_as_any_wildcard(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    run_query_text('"gol*" parrot', fake, lexicon, stop_words=MY_STOP_WORDS)
    leaves = [leaf for leaf, _, _ in fake.bubble_calls]
    assert leaves == [AnyTerm(("parrot",)), AnyTerm(("gold", "golden"))]


def test_an_and_stops_searching_once_no_story_is_left(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text('"square mine" gold -bear', fake, lexicon, stop_words=MY_STOP_WORDS)
    assert result.title_dict == {}
    assert len(fake.bubble_calls) == 1


def test_a_filter_narrows_the_stories_searched(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    run_query_text('gold tag:"the classics"', fake, lexicon, stop_words=MY_STOP_WORDS)
    ((_, _, titles),) = fake.bubble_calls
    assert titles == tag_titles("the classics")


def test_the_screens_filter_applies_to_the_whole_query(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    only_1951 = SearchFilter(years=(1951, 1951))
    result = run_query_text(
        "gold OR helmet", fake, lexicon, search_filter=only_1951, stop_words=MY_STOP_WORDS
    )
    assert list(result.title_dict) == [POOR, HELMET]  # alphabetical, as the engine sorts
    assert all(titles == titles_in_years(1951, 1951) for _, _, titles in fake.bubble_calls)


def test_a_volume_filter_cannot_list_its_stories_but_still_filters(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text("gold", fake, lexicon, search_filter=SearchFilter(volumes=(7, 7)))
    assert list(result.title_dict) == [ANDES]
    assert fake.bubble_calls[0][2] is None


def test_a_speaker_applies_to_every_word(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text("gold mine", fake, lexicon, speaker="Scrooge")
    assert list(result.title_dict) == [ANDES]
    assert {speaker for _, speaker, _ in fake.bubble_calls} == {"Scrooge"}


def test_a_word_in_no_story_brings_suggestions(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text("monney", fake, lexicon, stop_words=MY_STOP_WORDS)
    assert result.title_dict == {}
    assert Suggestion("monney", "money") in result.suggestions
    assert result.notices == ('"monney" is in no story.',)


def test_each_suggestion_names_the_word_it_is_for(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text("gold OR monney OR bearz", fake, lexicon)
    assert {s.word for s in result.suggestions} == {"monney", "bearz"}
    assert Suggestion("bearz", "bears") in result.suggestions


def test_a_quoted_word_brings_no_suggestions(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text('"monney"', fake, lexicon)
    assert (result.title_dict, result.suggestions) == ({}, ())


def test_a_word_the_index_holds_brings_no_suggestions_when_the_and_finds_nothing(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text("helmet coins", fake, lexicon)
    assert (result.title_dict, result.suggestions) == ({}, ())


def test_every_word_in_no_story_brings_suggestions_though_the_and_stops_at_the_first(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text("monney bearz", fake, lexicon)
    assert result.title_dict == {}
    assert {s.word for s in result.suggestions} == {"monney", "bearz"}
    assert result.notices == ('"monney" is in no story.', '"bearz" is in no story.')
    assert len(fake.bubble_calls) == 1  # the words left are not searched, only looked up


def test_a_word_not_searched_after_held_words_still_brings_suggestions(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text("helmet coins monney", fake, lexicon)
    assert {s.word for s in result.suggestions} == {"monney"}


def test_words_in_a_near_pair_or_bracket_left_unread_still_bring_suggestions(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    # The phrase finds nothing, so the AND searches no further: the NEAR pair, the
    # bracketed OR and the second phrase are only looked up.
    result = run_query_text(
        '"square mine" monney NEAR gold (bearz OR helmet) "gold pirate"', fake, lexicon
    )
    assert result.title_dict == {}
    assert {s.word for s in result.suggestions} == {"monney", "bearz"}
    assert len(fake.bubble_calls) == 1


def test_a_word_whose_forms_are_held_is_not_in_no_story_when_the_and_finds_nothing(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    # ducked is not in the index, but ducks and ducking are: in stories helmet is not.
    result = run_query_text("helmet ducked", fake, lexicon)
    assert (result.title_dict, result.suggestions, result.notices) == ({}, (), ())


def test_a_stop_word_is_left_out_of_an_and_with_a_notice(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text("the gold -of", fake, lexicon, stop_words=MY_STOP_WORDS)
    assert list(result.title_dict) == [PIRATE, ANDES, POOR]
    assert result.notices == (
        '"the" is too common to search for; left out.',
        '"of" is too common to search for; left out.',
    )


def test_a_stop_word_alone_finds_nothing_and_says_why(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text("the", fake, lexicon, stop_words=MY_STOP_WORDS)
    assert (result.title_dict, result.error) == ({}, None)
    assert result.notices == ('"the" is too common to search for.',)
    assert fake.bubble_calls == []


def test_a_wildcard_matching_too_many_words_searches_the_first_ones(
    fake: InMemoryFullTextSearch,
) -> None:
    lexicon = TermLexicon([f"gold{i:03}" for i in range(MAX_WILDCARD_TERMS + 50)])
    result = run_query_text("gold*", fake, lexicon)
    assert result.notices == (
        (
            f'"gold*" matches {MAX_WILDCARD_TERMS + 50} words;'
            f" searched for the first {MAX_WILDCARD_TERMS}."
        ),
    )
    ((leaf, _, _),) = fake.bubble_calls
    assert isinstance(leaf, AnyTerm)
    assert len(leaf.terms) == MAX_WILDCARD_TERMS


def test_a_wildcard_matching_nothing_says_so(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text("zz*", fake, lexicon)
    assert (result.title_dict, result.notices) == ({}, ('No word matches "zz*".',))
    assert fake.bubble_calls == []


def test_an_unknown_tag_matches_nothing_and_names_the_closest(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text("gold tag:clasics", fake, lexicon)
    assert result.title_dict == {}
    assert result.notices == ('No tag is called "clasics". Closest: the classics.',)


def test_words_picked_from_the_list_are_exact_and_a_term_of_several_words_is_a_phrase(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    node = query_from_words(["pirate gold", "ducks"], Combine.ALL)
    assert node is not None
    result = evaluate_query(node, fake, lexicon)
    assert list(result.title_dict) == [PIRATE]
    assert {leaf for leaf, _, _ in fake.bubble_calls} == {
        Phrase(("pirate", "gold")),
        AnyTerm(("ducks",)),
    }
    assert evaluate_query(Word("duck", exact=True), fake, lexicon).title_dict == {}


@pytest.mark.parametrize(
    ("text", "says"),
    [
        ("tag:bear", "needs a word or phrase"),
        ("year:1950 -vol:3", "needs a word or phrase"),
        ("-gold", "needs a word or phrase"),
        ("-gold -mine", "needs a word or phrase"),
        ("gold OR year:1950", "cannot be joined to words with OR"),
        ("gold OR -mine", "NOT needs words beside it"),
    ],
)
def test_a_query_that_cannot_run_is_an_error_not_a_search(
    text: str, says: str, fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text(text, fake, lexicon)
    assert result.error is not None
    assert says in result.error
    assert result.title_dict == {}
    assert not result.used_literal_fallback


def test_text_that_does_not_parse_is_searched_as_it_stands(lexicon: TermLexicon) -> None:
    literal = {PIRATE: TitleInfo(fanta_vol=1), ANDES: TitleInfo(fanta_vol=7)}
    fake = InMemoryFullTextSearch(find_words_results={"(gold": literal})
    result = run_query_text("(gold", fake, lexicon, search_filter=SearchFilter(volumes=(7, 7)))
    assert result.used_literal_fallback
    assert list(result.title_dict) == [ANDES]
    assert result.error is not None
    assert "not closed" in result.error
    assert result.error_position == 0
    assert result.notices[0].endswith("searched for the text as it stands.")


def test_nothing_typed_finds_nothing(fake: InMemoryFullTextSearch, lexicon: TermLexicon) -> None:
    result = run_query_text("   ", fake, lexicon)
    assert (result.title_dict, result.error, result.notices) == ({}, None, ())
    assert fake.bubble_calls == []


def test_near_with_a_too_common_word_finds_nothing_and_says_why(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    result = run_query_text("the NEAR gold", fake, lexicon, stop_words=MY_STOP_WORDS)
    assert (result.title_dict, result.notices) == ({}, ('"the" is too common to search for.',))


def test_near_with_a_wildcard_matching_no_word_finds_nothing(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    """A word in no story is still searched as typed; a wildcard that matches none is not."""
    result = run_query_text("gold NEAR zz*", fake, lexicon, stop_words=MY_STOP_WORDS)
    assert result.title_dict == {}
    assert not fake.bubble_calls  # nothing left to search for


def test_filters_grouped_inside_an_or_all_apply(
    fake: InMemoryFullTextSearch, lexicon: TermLexicon
) -> None:
    """(year:1947 vol:5) holds only where both do: Bear Mountain; or else 1942's Pirate Gold."""
    assert set(_stories("mine (year:1942 OR (year:1947 vol:5))", fake, lexicon)) == {PIRATE, BEAR}
    assert _stories("mine (year:1942 OR (year:1947 vol:7))", fake, lexicon) == [PIRATE]


def test_only_a_filter_is_made_into_one() -> None:
    """The evaluator calls it only on filters; anything else is a bug, and says so."""
    from barks_fantagraphics.search_evaluate import _Evaluator  # noqa: PLC0415

    evaluator = _Evaluator(InMemoryFullTextSearch(), TermLexicon([]), None, MY_STOP_WORDS)
    with pytest.raises(ValueError, match="Not a filter"):
        evaluator._filter_of(Word("gold"))  # noqa: SLF001
