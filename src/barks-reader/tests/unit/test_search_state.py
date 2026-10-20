"""The search screen's picked words: added, removed, combined, and run as a query."""

from __future__ import annotations

import pytest
from barks_fantagraphics.barks_titles import Titles
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
from barks_reader.core.search_state import (
    ALL_SPEAKERS,
    ALL_YEARS,
    BASKET_MODE_VALUE,
    EVERYWHERE,
    MAX_SCOPE_LABEL,
    ONLY_IN_TAGS,
    VOLUMES_KEY,
    YEARS_KEY,
    EraChoice,
    TagBasket,
    TagScope,
    TagState,
    WordBasket,
    offered_speakers,
    speaker_story_counts,
)


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


def test_a_typed_years_and_volumes_range_are_chips_of_the_tag_basket() -> None:
    basket = TagBasket()
    basket.fill(TagSelection(("gyro",), years=(1950, 1955), volumes=(7, 7)))
    assert len(basket) == 3  # noqa: PLR2004
    assert basket.selection() == TagSelection(("gyro",), years=(1950, 1955), volumes=(7, 7))
    basket.drop_range(YEARS_KEY)
    assert (basket.years, basket.volumes, len(basket)) == (None, (7, 7), 2)
    basket.drop_range(VOLUMES_KEY)
    assert basket.selection() == TagSelection(("gyro",))
    basket.fill(TagSelection(("gyro",), years=(1950, 1955)))
    basket.clear()
    assert (basket.years, len(basket)) == (None, 0)


_TIMES = chr(0xD7)  # the multiplication sign on a picked word's chip


def test_the_picked_words_row_is_the_mode_then_each_word_with_its_x() -> None:
    basket = WordBasket()
    assert basket.chip_options() == []
    basket.toggle("gold")
    basket.toggle("mine")
    basket.flip()
    assert basket.chip_options() == [
        (BASKET_MODE_VALUE, "ANY"),
        ("gold", f"gold  {_TIMES}"),
        ("mine", f"mine  {_TIMES}"),
    ]


def test_the_picked_tags_row_names_a_left_out_tag_and_the_typed_ranges() -> None:
    basket = TagBasket()
    assert basket.chip_options() == []
    basket.toggle("Gold")
    basket.toggle("Pete")
    basket.cycle("Pete")
    basket.years, basket.volumes = (1950, 1955), (7, 7)
    assert basket.chip_options() == [
        (BASKET_MODE_VALUE, "ALL"),
        ("Gold", "Gold"),
        ("Pete", "not Pete"),
        (YEARS_KEY, "years 1950-55"),
        (VOLUMES_KEY, "vol 7"),
    ]
    basket.volumes = (7, 9)
    assert basket.chip_options()[-1] == (VOLUMES_KEY, "vols 7-9")


def test_the_era_keeps_the_stories_submitted_in_it_in_order() -> None:
    era = EraChoice(ranges=((1942, 1946), (1947, 1950)))
    titles = [Titles.LOST_IN_THE_ANDES, Titles.DONALD_DUCK_FINDS_PIRATE_GOLD]  # 1949, 1942
    assert era.in_era(titles) == titles
    era.select("1942-1946")
    assert era.in_era(titles) == [Titles.DONALD_DUCK_FINDS_PIRATE_GOLD]


def test_the_speakers_offered_are_the_roster_s_the_index_has_in_roster_order() -> None:
    assert offered_speakers({"narrator", "Scrooge", "Donald", "other:Witch Hazel"}) == [
        "Donald",
        "Scrooge",
        "narrator",
    ]
    assert offered_speakers(set()) == []


def test_the_speaker_counts_list_anyone_then_speakers_by_count_the_picked_one_kept() -> None:
    stories = {None: 3, "Donald": 1, "Scrooge": 2, "Gyro": 0}
    counts = speaker_story_counts(lambda s: stories[s], ["Donald", "Scrooge", "Gyro"], "Gyro")
    assert counts == [(ALL_SPEAKERS, 3), ("Scrooge", 2), ("Donald", 1), ("Gyro", 0)]
    counts = speaker_story_counts(lambda s: stories[s], ["Donald", "Scrooge", "Gyro"], "")
    assert counts == [(ALL_SPEAKERS, 3), ("Scrooge", 2), ("Donald", 1)]


class TestTagScope:
    def test_a_scope_narrows_a_list_it_holds_some_of_but_not_all(self) -> None:
        scope = TagScope("Gold", frozenset({"A", "B"}))
        assert scope.count_in(["A", "B", "C"]) == 2  # noqa: PLR2004
        assert scope.narrows(2, 3) is True
        assert scope.narrows(0, 3) is False
        assert scope.narrows(3, 3) is False

    def test_the_chips_are_everywhere_and_only_in_the_tags_cut_to_fit(self) -> None:
        scope = TagScope("Gold + Pete + " + "Uncle Scrooge and the money bin " * 3)
        everywhere, only = scope.options()
        assert everywhere == (EVERYWHERE, "Everywhere")
        assert only[0] == ONLY_IN_TAGS
        assert only[1].startswith("Only in: Gold + Pete")
        assert only[1].endswith("…")
        assert len(only[1]) <= MAX_SCOPE_LABEL

    def test_the_filter_is_the_era_s_years_and_the_scope_s_stories_in_force(self) -> None:
        era = EraChoice(ranges=((1951, 1954),))
        scope = TagScope("Gold", frozenset({"A"}))
        assert scope.search_filter(era, in_force=False) is None
        assert scope.search_filter(era, in_force=True) == SearchFilter(tag_titles=frozenset({"A"}))
        era.select("1951-1954")
        assert scope.search_filter(era, in_force=True) == SearchFilter(
            years=(1951, 1954), tag_titles=frozenset({"A"})
        )
        scope.clear()
        assert scope.tags == ""
        assert scope.titles == frozenset()
