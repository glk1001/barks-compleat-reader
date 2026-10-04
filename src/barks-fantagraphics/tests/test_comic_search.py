# ruff: noqa: SLF001
# cspell:ignore clasics monney scro scroge scrooged

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.barks_tags import TagGroups, Tags
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_search import (
    ComicSearch,
    SearchMode,
    SearchResult,
    clear_alpha_split_cache,
)
from barks_fantagraphics.search_filters import SearchFilter
from barks_fantagraphics.search_ports import (
    CorpusTextTotals,
    SearchIndexUnavailableError,
)
from barks_fantagraphics.search_query import AnyTerm
from barks_fantagraphics.tag_query import TagSelection
from barks_fantagraphics.testing.fake_search import FakeBubble, InMemoryFullTextSearch
from barks_fantagraphics.title_search import BARKS_ISSUE_DICT
from barks_fantagraphics.whoosh_search_engine import TitleInfo

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    """Reset the module-level alpha-split cache, which is keyed by index dir."""
    clear_alpha_split_cache()
    yield
    clear_alpha_split_cache()


def _search_with(fake: InMemoryFullTextSearch, index_dir: str = "idx") -> ComicSearch:
    search = ComicSearch(Path(index_dir))
    search._full_text = fake
    return search


class TestSearch:
    @pytest.mark.parametrize("mode", list(SearchMode))
    def test_empty_query_returns_empty_result_for_every_mode(self, mode: SearchMode) -> None:
        result = _search_with(InMemoryFullTextSearch()).search("", mode)

        assert result == SearchResult(mode=mode)

    def test_word_mode_returns_the_title_dict(self) -> None:
        expected = {"The Golden Helmet": TitleInfo(fanta_vol=7)}
        search = _search_with(InMemoryFullTextSearch(find_words_results={"duck": expected}))

        result = search.search("duck", SearchMode.WORD)

        assert result.mode is SearchMode.WORD
        assert result.title_dict == expected

    def test_title_mode_populates_titles_and_strings(self) -> None:
        result = _search_with(InMemoryFullTextSearch()).search("Golden Helmet", SearchMode.TITLE)

        assert result.mode is SearchMode.TITLE
        assert Titles.GOLDEN_HELMET_THE in result.titles
        assert len(result.title_strings) == len(result.titles)

    def test_title_mode_shows_the_display_form_of_the_canonical_title(self) -> None:
        # Searched by its canonical title; listed with the parentheses the
        # display form adds.
        result = _search_with(InMemoryFullTextSearch()).search(
            "The Victory Garden", SearchMode.TITLE
        )

        assert Titles.VICTORY_GARDEN_THE in result.titles
        assert "(The Victory Garden)" in result.title_strings

    def test_tag_mode_populates_matched_tags(self) -> None:
        result = _search_with(InMemoryFullTextSearch()).search("christmas", SearchMode.TAG)

        assert result.mode is SearchMode.TAG
        assert result.matched_tags

    def test_words_matching_come_from_the_index_s_terms(self) -> None:
        fake = InMemoryFullTextSearch(cleaned_terms=["airline", "airlines", "hair", "stairs"])
        matches = _search_with(fake).get_words_matching("air")
        assert matches.words == ["airline", "airlines", "hair", "stairs"]
        assert matches.total == 4  # noqa: PLR2004

    def test_the_word_list_is_read_once_per_index(self) -> None:
        fake = InMemoryFullTextSearch(cleaned_terms=["airline"])
        _search_with(fake).get_words_matching("air")
        fake.cleaned_terms = ["something else"]
        assert _search_with(fake).get_words_matching("air").words == ["airline"]
        clear_alpha_split_cache()
        assert _search_with(fake).get_words_matching("air").words == []

    def test_tag_mode_lists_each_tag_once_in_a_fixed_order(self) -> None:
        """Deterministic: not a set's order, which the hash seed changes per process."""
        result = _search_with(InMemoryFullTextSearch()).search("sou", SearchMode.TAG)

        names = [str(tag.value) for tag in result.matched_tags]
        assert len(names) > 1
        assert names == sorted(set(names))  # all start with "sou": one rank, by name

    def test_tag_mode_and_the_tag_box_agree(self) -> None:
        search = _search_with(InMemoryFullTextSearch())
        matches = search.get_tags_matching("africa")
        assert search.search("africa", SearchMode.TAG).matched_tags == [m.item for m in matches]
        assert matches[0].exact
        assert search.get_tag_title_count(matches[0].item) == matches[0].title_count

    def test_unhandled_mode_raises_instead_of_returning_none(self) -> None:
        """The match had no catch-all, so an unexpected mode fell off the end."""
        with pytest.raises(ValueError, match="Unhandled search mode"):
            _search_with(InMemoryFullTextSearch()).search("duck", "not-a-mode")  # ty: ignore[invalid-argument-type]


class TestSearchTitles:
    def test_prefix_match_wins_and_skips_the_fallbacks(self) -> None:
        search = _search_with(InMemoryFullTextSearch())

        result = search.search("Christmas on Bear", SearchMode.TITLE)

        assert Titles.CHRISTMAS_ON_BEAR_MOUNTAIN in result.titles

    def test_short_query_does_not_fall_back(self) -> None:
        """Fallbacks only run for queries longer than two characters."""
        result = _search_with(InMemoryFullTextSearch()).search("zz", SearchMode.TITLE)

        assert result.titles == []

    def test_containing_fallback_returns_no_duplicates(self) -> None:
        result = _search_with(InMemoryFullTextSearch()).search("helmet", SearchMode.TITLE)

        assert result.titles
        assert len(result.titles) == len(set(result.titles))

    def test_titles_starting_with_the_text_do_not_hide_the_others(self) -> None:
        result = _search_with(InMemoryFullTextSearch()).search("gold", SearchMode.TITLE)

        assert Titles.GOLD_RUSH in result.titles
        assert Titles.FROZEN_GOLD in result.titles

    def test_issue_number_fallback_finds_titles(self) -> None:
        result = _search_with(InMemoryFullTextSearch()).search("FC 29", SearchMode.TITLE)

        assert len(result.titles) > 1

    def test_issue_number_search_does_not_mutate_shared_data(self) -> None:
        """The issue table's lists are shared; a search must not extend them."""
        search = _search_with(InMemoryFullTextSearch())
        before = list(BARKS_ISSUE_DICT["FC 29"])

        first = list(search.search("FC 29", SearchMode.TITLE).titles)
        second = list(search.search("FC 29", SearchMode.TITLE).titles)

        assert first
        assert first == second
        assert BARKS_ISSUE_DICT["FC 29"] == before


class TestAlphaSplitTerms:
    def test_split_is_computed_from_the_flat_term_list(self) -> None:
        fake = InMemoryFullTextSearch(cleaned_terms=["ant", "apple", "bee"])

        split = _search_with(fake).get_alpha_split_terms()

        assert set(split) == {"a", "b"}
        flat = [t for buckets in split.values() for b in buckets.values() for t in b]
        assert sorted(flat) == ["ant", "apple", "bee"]

    def test_the_precomputed_sidecar_is_no_longer_consulted(self) -> None:
        """Presentation is a reader concern now, so a stale sidecar is ignored."""
        fake = InMemoryFullTextSearch(
            cleaned_terms=["ant"],
            cleaned_alpha_split_terms={"z": {"zz": ["stale"]}},
        )

        split = _search_with(fake).get_alpha_split_terms()

        assert "z" not in split

    def test_result_is_shared_between_searches_over_the_same_index(self) -> None:
        fake_a = InMemoryFullTextSearch(cleaned_terms=["ant"])
        fake_b = InMemoryFullTextSearch(cleaned_terms=["bee"])

        first = _search_with(fake_a, "same").get_alpha_split_terms()
        second = _search_with(fake_b, "same").get_alpha_split_terms()

        assert second is first

    def test_different_index_dirs_are_cached_separately(self) -> None:
        fake_a = InMemoryFullTextSearch(cleaned_terms=["ant"])
        fake_b = InMemoryFullTextSearch(cleaned_terms=["bee"])

        first = _search_with(fake_a, "one").get_alpha_split_terms()
        second = _search_with(fake_b, "two").get_alpha_split_terms()

        assert set(first) == {"a"}
        assert set(second) == {"b"}


class TestWordQuery:
    @staticmethod
    def _fake() -> InMemoryFullTextSearch:
        return InMemoryFullTextSearch(
            cleaned_terms=["gold", "golden", "mine", "money", "the"],
            bubbles=[
                FakeBubble("A", "gold in the mine", fanta_vol=1),
                FakeBubble("B", "golden money", fanta_vol=2, speaker="Scrooge"),
            ],
        )

    def test_a_typed_query_runs_against_the_engine(self) -> None:
        result = _search_with(self._fake()).run_word_query("gol* -mine")

        assert list(result.title_dict) == ["B"]
        assert result.hit_counts == {"B": 1}

    def test_the_index_stop_words_are_left_out(self) -> None:
        result = _search_with(self._fake()).run_word_query("the gold")

        assert list(result.title_dict) == ["A"]
        assert result.notices == ('"the" is too common to search for; left out.',)

    def test_the_speaker_and_filter_are_passed_down(self) -> None:
        fake = self._fake()
        search = _search_with(fake)

        result = search.run_word_query(
            "golden", speaker="Scrooge", search_filter=SearchFilter(volumes=(2, 2))
        )

        assert list(result.title_dict) == ["B"]
        assert fake.bubble_calls == [(AnyTerm(("golden",)), "Scrooge", None)]

    def test_suggest_words(self) -> None:
        assert _search_with(self._fake()).suggest_words("monney") == ["money"]


class TestTagSelection:
    def test_a_typed_selection_s_names_are_checked(self) -> None:
        search = _search_with(InMemoryFullTextSearch())
        parsed = search.parse_tag_query("andes + the classics")
        assert parsed.selection == TagSelection(("andes", "the classics"))

    def test_a_name_that_is_no_tag_is_an_error_naming_the_closest(self) -> None:
        parsed = _search_with(InMemoryFullTextSearch()).parse_tag_query("andes + clasics")
        assert parsed.selection is None
        assert parsed.error == 'No tag is called "clasics". Closest: the classics.'

    def test_bad_syntax_is_the_parser_s_error(self) -> None:
        parsed = _search_with(InMemoryFullTextSearch()).parse_tag_query("a + b | c")
        assert parsed.error == "Use + or | between tags, not both."

    def test_the_stories_of_a_selection(self) -> None:
        search = _search_with(InMemoryFullTextSearch())
        titles = search.titles_for_tag_selection(TagSelection(("andes",)))
        assert Titles.LOST_IN_THE_ANDES in titles


class TestPassThroughs:
    def test_find_words(self) -> None:
        expected = {"A Title": TitleInfo(fanta_vol=1)}
        search = _search_with(InMemoryFullTextSearch(find_words_results={"money": expected}))

        assert search.find_words("money") == expected

    def test_find_words_passes_speaker_through(self) -> None:
        fake = MagicMock(spec=InMemoryFullTextSearch)
        fake.find_words.return_value = {}

        _search_with(fake).find_words("money", speaker="Scrooge")

        fake.find_words.assert_called_once_with("money", speaker="Scrooge")

    def test_get_speakers(self) -> None:
        fake = InMemoryFullTextSearch(speakers={"Scrooge": 7})

        assert _search_with(fake).get_speakers() == {"Scrooge": 7}

    def test_find_entities(self) -> None:
        expected = {"A Title": TitleInfo(fanta_vol=1)}
        fake = InMemoryFullTextSearch(find_entities_results={("person", "Scrooge"): expected})

        assert _search_with(fake).find_entities("person", "Scrooge") == expected

    def test_search_entity_wraps_find_entities(self) -> None:
        expected = {"A Title": TitleInfo(fanta_vol=1)}
        fake = InMemoryFullTextSearch(find_entities_results={("person", "Scrooge"): expected})

        result = _search_with(fake).search_entity("person", "Scrooge")

        assert result.title_dict == expected

    def test_get_entity_terms(self) -> None:
        fake = InMemoryFullTextSearch(entity_terms={"person": ["Scrooge", "Donald"]})

        assert _search_with(fake).get_entity_terms("person") == ["Scrooge", "Donald"]

    def test_get_cleaned_terms(self) -> None:
        fake = InMemoryFullTextSearch(cleaned_terms=["ant", "bee"])

        assert _search_with(fake).get_cleaned_terms() == ["ant", "bee"]

    def test_get_corpus_text_totals(self) -> None:
        totals = CorpusTextTotals(
            num_text_entities=4, num_words=6, num_titles=2, num_pages=3, num_panels=3
        )
        fake = InMemoryFullTextSearch(corpus_text_totals=totals)

        assert _search_with(fake).get_corpus_text_totals() == totals

    def test_missing_index_raises_search_index_unavailable(self) -> None:
        """Callers get one search-specific error, not a raw Whoosh/OS error."""
        search = ComicSearch(Path("does-not-exist"))

        with pytest.raises(SearchIndexUnavailableError):
            search.get_corpus_text_totals()

    def test_full_text_engine_is_not_built_for_title_only_searches(self) -> None:
        """Title/tag callers must pay no Whoosh or disk cost."""
        search = ComicSearch(Path("does-not-exist"))

        search.search("Christmas", SearchMode.TITLE)
        search.search("christmas", SearchMode.TAG)

        assert search._full_text is None


class TestTagAndTitlePassThroughs:
    """What the screens ask of the tag data and the titles, through the facade."""

    def test_a_tag_alias_resolves_to_its_tag_and_stories(self) -> None:
        item, titles = ComicSearch(Path("idx")).resolve_tag("gyro")
        assert item is Tags.GYRO_GEARLOOSE
        assert Titles.GLADSTONES_TERRIBLE_SECRET in titles

    def test_a_group_lists_its_direct_members_subgroups_too(self) -> None:
        members = ComicSearch(Path("idx")).get_tag_group_members(TagGroups.CHEMISTRY)
        assert TagGroups.CHEMICAL_NAMES in members
        assert Tags.DUCKMITE in members

    def test_titles_become_their_display_strings(self) -> None:
        strings = ComicSearch(Path("idx")).get_title_display_strings([Titles.GOLDEN_HELMET_THE])
        assert len(strings) == 1
        assert "Golden Helmet" in strings[0]

    def test_alpha_split_entity_terms_come_from_the_full_text_search(self) -> None:
        split = {"a": {"ac": ["Acapulco"]}}
        fake = InMemoryFullTextSearch()
        fake.alpha_split_entity_terms = {"location": split}
        assert _search_with(fake).get_alpha_split_entity_terms("location") == split


class TestFacadePassesItsArgumentsOn:
    """What the facade is asked, it asks its parts: limits, filters, and its own index."""

    BUBBLES: ClassVar[list[FakeBubble]] = [
        FakeBubble("Donald Duck Finds Pirate Gold", "gold and gold coins", 1, "001"),
        FakeBubble("The Golden Helmet", "the golden helmet", 11, "030"),
    ]

    @staticmethod
    def _fake(terms: list[str]) -> InMemoryFullTextSearch:
        return InMemoryFullTextSearch(
            cleaned_terms=terms,
            bubbles=list(TestFacadePassesItsArgumentsOn.BUBBLES),
            tokenize=str.split,
        )

    def test_an_entity_search_is_a_word_search(self) -> None:
        assert _search_with(InMemoryFullTextSearch()).search_entity("person", "x").mode is (
            SearchMode.WORD
        )

    def test_the_words_matching_stop_at_the_limit_asked_for(self) -> None:
        search = _search_with(self._fake(["gold", "golden", "goldfish"]))
        matches = search.get_words_matching("gold", limit=1)
        assert (matches.words, matches.total) == (["gold"], 3)

    def test_the_suggestions_stop_at_the_limit_asked_for(self) -> None:
        search = _search_with(self._fake(["Scrooge", "scrounge", "scrooged"]))
        assert len(search.suggest_words("scroge", limit=1)) == 1

    def test_a_typed_query_is_run_in_the_filter_given(self) -> None:
        search = _search_with(self._fake(["gold", "golden"]))
        only_1951 = SearchFilter(years=(1951, 1951))
        assert list(search.run_word_query("gold OR golden").title_dict) == [
            "Donald Duck Finds Pirate Gold",
            "The Golden Helmet",
        ]
        assert list(
            search.run_word_query("gold OR golden", search_filter=only_1951).title_dict
        ) == ["The Golden Helmet"]

    def test_each_index_has_its_own_word_list(self) -> None:
        """The word lists are cached by index folder: one index's is not another's."""
        first = _search_with(self._fake(["gold"]), index_dir="one")
        second = _search_with(self._fake(["Scrooge"]), index_dir="two")
        # The first index's list is built (and cached) by each way of asking first.
        assert first.get_words_matching("scro").words == []
        assert first.suggest_words("scroge") == []
        assert first.run_word_query("scroge").suggestions == ()
        assert second.get_words_matching("scro").words == ["Scrooge"]
        assert second.suggest_words("scroge") == ["Scrooge"]
        assert second.run_word_query("scroge").suggestions[0].spelling == "Scrooge"

    def test_a_missing_index_names_its_folder(self) -> None:
        with pytest.raises(SearchIndexUnavailableError) as raised:
            ComicSearch(Path("does-not-exist")).get_corpus_text_totals()
        assert str(raised.value) == 'No usable search index in "does-not-exist".'

    def test_an_index_there_is_opened_from_its_folder(self, tmp_path: Path) -> None:
        from barks_fantagraphics.whoosh_search_engine import build_index_schema  # noqa: PLC0415
        from whoosh.index import create_in  # noqa: PLC0415

        create_in(str(tmp_path), build_index_schema())
        assert ComicSearch(tmp_path).get_speakers() == {}  # opened, and empty

    def test_three_letters_no_title_starts_fall_back_to_titles_holding_them(self) -> None:
        result = ComicSearch(Path("idx")).search("ost", SearchMode.TITLE)
        assert result.titles  # none starts "ost"; "Lost in the Andes!" holds it
