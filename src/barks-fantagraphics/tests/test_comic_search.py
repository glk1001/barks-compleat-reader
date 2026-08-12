# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_search import (
    ComicSearch,
    SearchMode,
    SearchResult,
    clear_alpha_split_cache,
)
from barks_fantagraphics.testing.fake_search import InMemoryFullTextSearch
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

    def test_tag_mode_populates_matched_tags(self) -> None:
        result = _search_with(InMemoryFullTextSearch()).search("christmas", SearchMode.TAG)

        assert result.mode is SearchMode.TAG
        assert result.matched_tags

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

    def test_issue_number_fallback_finds_titles(self) -> None:
        result = _search_with(InMemoryFullTextSearch()).search("FC 29", SearchMode.TITLE)

        assert len(result.titles) > 1

    def test_issue_number_fallback_does_not_mutate_shared_data(self) -> None:
        """get_titles_from_issue_num hands back a shared list; it must not be extended."""
        search = _search_with(InMemoryFullTextSearch())

        first = list(search.search("FC 29", SearchMode.TITLE).titles)
        second = list(search.search("FC 29", SearchMode.TITLE).titles)

        assert first
        assert first == second
        # Prove the shared source list itself is untouched.
        assert BARKS_ISSUE_DICT["FC 29"] == first


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


class TestPassThroughs:
    def test_find_words(self) -> None:
        expected = {"A Title": TitleInfo(fanta_vol=1)}
        search = _search_with(InMemoryFullTextSearch(find_words_results={"money": expected}))

        assert search.find_words("money") == expected

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

    def test_full_text_engine_is_not_built_for_title_only_searches(self) -> None:
        """Title/tag callers must pay no Whoosh or disk cost."""
        search = ComicSearch(Path("does-not-exist"))

        search.search("Christmas", SearchMode.TITLE)
        search.search("christmas", SearchMode.TAG)

        assert search._full_text is None
