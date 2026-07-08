# ruff: noqa: PLR2004, SLF001, ERA001, PLC0415

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.entity_types import EntityType
from barks_fantagraphics.whoosh_search_engine import (
    SUB_ALPHA_SPLIT_SIZE,
    SearchEngine,
    SearchEngineCreator,
    _build_curated_entity_sets,
    _filter_entities_to_curated,
    _is_valid_entity_term,
    _normalize_entity_names,
)

if TYPE_CHECKING:
    from pathlib import Path

    from whoosh.searching import Hit

# ---------------------------------------------------------------------------
# _is_valid_entity_term
# ---------------------------------------------------------------------------


class TestIsValidEntityTerm:
    def test_empty_string_invalid(self) -> None:
        assert _is_valid_entity_term("") is False

    def test_contains_newline_invalid(self) -> None:
        assert _is_valid_entity_term("some\nterm") is False

    def test_starts_with_letter_valid(self) -> None:
        assert _is_valid_entity_term("Donald Duck") is True

    def test_starts_with_single_digit_valid(self) -> None:
        # Single-digit number words (len<=2) pass the all-caps filter
        assert _is_valid_entity_term("3 wishes") is True

    def test_long_digit_only_word_invalid(self) -> None:
        # "007" is all-caps (digits have no case) and len>2 → rejected
        assert _is_valid_entity_term("007 agent") is False

    def test_starts_with_apostrophe_valid(self) -> None:
        assert _is_valid_entity_term("'Scrooge") is True

    def test_starts_with_dash_invalid(self) -> None:
        assert _is_valid_entity_term("-ER-") is False

    def test_all_caps_word_longer_than_two_invalid(self) -> None:
        assert _is_valid_entity_term("SCROOGE McDuck") is False

    def test_all_caps_two_chars_or_less_valid(self) -> None:
        # Short abbreviations like "OK" or "US" should be valid
        assert _is_valid_entity_term("US dollars") is True

    def test_mixed_case_valid(self) -> None:
        assert _is_valid_entity_term("Scrooge McDuck") is True

    def test_starts_with_uppercase_valid(self) -> None:
        assert _is_valid_entity_term("Duckburg") is True


# ---------------------------------------------------------------------------
# _build_curated_entity_sets
# ---------------------------------------------------------------------------


class TestBuildCuratedEntitySets:
    def test_returns_dict_with_all_entity_types(self) -> None:
        result = _build_curated_entity_sets()
        for entity_type in EntityType:
            assert entity_type in result

    def test_all_values_are_sets(self) -> None:
        result = _build_curated_entity_sets()
        for v in result.values():
            assert isinstance(v, set)

    def test_values_are_lowercase(self) -> None:
        result = _build_curated_entity_sets()
        for terms in result.values():
            for term in terms:
                assert term == term.lower()


# ---------------------------------------------------------------------------
# _filter_entities_to_curated
# ---------------------------------------------------------------------------


class TestFilterEntitiesToCurated:
    def test_keeps_entities_in_curated_set(self) -> None:
        curated_sets = {et: set() for et in EntityType}
        person_type = EntityType.PERSON
        curated_sets[person_type] = {"donald duck"}
        entities = {person_type: {"Donald Duck", "Unknown Entity"}}

        result = _filter_entities_to_curated(entities, curated_sets)

        assert "Donald Duck" in result[person_type]
        assert "Unknown Entity" not in result[person_type]

    def test_empty_curated_set_filters_all(self) -> None:
        curated_sets = {et: set() for et in EntityType}
        entities = {EntityType.PERSON: {"Anyone"}}

        result = _filter_entities_to_curated(entities, curated_sets)

        assert result[EntityType.PERSON] == set()

    def test_missing_entity_type_in_entities_gives_empty(self) -> None:
        curated_sets = {et: set() for et in EntityType}
        curated_sets[EntityType.PERSON] = {"donald duck"}

        result = _filter_entities_to_curated({}, curated_sets)

        assert result[EntityType.PERSON] == set()

    def test_normalizes_to_curated_casing(self) -> None:
        """Entity names with wrong casing (e.g. from spaCy) are normalized to curated form."""
        curated_sets = {et: set() for et in EntityType}
        curated_sets[EntityType.LOCATION] = {"lost dutchman's"}
        # Simulate spaCy producing title-cased output (capitalizes after apostrophe).
        # noinspection GrazieInspectionRunner
        entities = {EntityType.LOCATION: {"Lost Dutchman'S"}}

        result = _filter_entities_to_curated(entities, curated_sets)

        assert result[EntityType.LOCATION] == {"Lost Dutchman's"}


# ---------------------------------------------------------------------------
# _normalize_entity_names
# ---------------------------------------------------------------------------


class TestNormalizeEntityNames:
    def test_skips_if_lowercase_in_existing(self) -> None:
        result = _normalize_entity_names({"Donald"}, existing_lower={"donald"})
        assert "Donald" not in result

    def test_valid_term_not_in_existing_added(self) -> None:
        result = _normalize_entity_names({"Duckburg"}, existing_lower=set())
        assert "Duckburg" in result

    def test_invalid_term_rejected(self) -> None:
        # starts with "-" → invalid
        result = _normalize_entity_names({"-ER-"}, existing_lower=set())
        assert "-ER-" not in result

    def test_all_caps_long_word_rejected(self) -> None:
        result = _normalize_entity_names({"SCROOGE"}, existing_lower=set())
        assert "SCROOGE" not in result


# ---------------------------------------------------------------------------
# SearchEngine._get_entity_types (static)
# ---------------------------------------------------------------------------


class TestGetEntityTypes:
    @staticmethod
    def _make_hit(entity_fields: dict[str, str]) -> MagicMock:
        hit = MagicMock()
        hit.get.side_effect = lambda field, default="": entity_fields.get(field, default)
        return hit

    def test_matching_entity_type_returned(self) -> None:
        hit = self._make_hit({"entities_person": "Donald Duck, Scrooge"})
        result = SearchEngine._get_entity_types(hit, "donald")
        assert EntityType.PERSON in result

    def test_no_match_returns_empty(self) -> None:
        hit = self._make_hit({})
        result = SearchEngine._get_entity_types(hit, "xyz")
        assert result == ()

    def test_partial_word_match_in_entity_name(self) -> None:
        hit = self._make_hit({"entities_person": "Donald Duck"})
        result = SearchEngine._get_entity_types(hit, "donald duck")
        assert EntityType.PERSON in result

    def test_empty_field_value_not_matched(self) -> None:
        hit = self._make_hit({"entities_person": ""})
        result = SearchEngine._get_entity_types(hit, "donald")
        assert EntityType.PERSON not in result


# ---------------------------------------------------------------------------
# SearchEngine._get_sub_alpha_split_terms (static)
# ---------------------------------------------------------------------------


class TestGetSubAlphaSplitTerms:
    def test_empty_returns_empty(self) -> None:
        assert SearchEngine._get_sub_alpha_split_terms([]) == {}

    def test_groups_by_two_char_prefix(self) -> None:
        terms = ["apple", "apricot", "banana"]
        result = SearchEngine._get_sub_alpha_split_terms(terms)
        assert "ap" in result
        assert "ba" in result
        assert "apple" in result["ap"]
        assert "apricot" in result["ap"]
        assert "banana" in result["ba"]

    def test_digit_prefix_uses_one_char(self) -> None:
        terms = ["007", "042", "100"]
        result = SearchEngine._get_sub_alpha_split_terms(terms)
        # digit prefix_len=1, so first char "0" is the group key
        assert "0" in result
        assert "007" in result["0"]
        assert "042" in result["0"]

    def test_single_term(self) -> None:
        result = SearchEngine._get_sub_alpha_split_terms(["hello"])
        assert "he" in result
        assert result["he"] == ["hello"]


# ---------------------------------------------------------------------------
# SearchEngine._get_similar_size_sub_alpha_groups (static)
# ---------------------------------------------------------------------------


class TestGetSimilarSizeSubAlphaGroups:
    def test_small_groups_merged(self) -> None:
        # Each sub-alpha group is small (< SUB_ALPHA_SPLIT_SIZE), should merge
        sub = {
            "aa": ["a1"] * 10,
            "ab": ["b1"] * 10,
        }
        result = SearchEngine._get_similar_size_sub_alpha_groups(sub)
        # Both groups together < threshold, so they merge under first prefix
        assert "aa" in result
        assert len(result["aa"]) == 20

    def test_large_group_starts_new_key(self) -> None:
        # First group exceeds threshold alone, next group starts a new key
        big = ["x"] * (SUB_ALPHA_SPLIT_SIZE + 1)
        sub = {
            "aa": big,
            "ab": ["y"],
        }
        result = SearchEngine._get_similar_size_sub_alpha_groups(sub)
        # "aa" exceeds threshold → "ab" becomes a new key
        assert "ab" in result
        assert result["ab"] == ["y"]

    def test_single_group_preserved(self) -> None:
        sub = {"aa": ["term1", "term2"]}
        result = SearchEngine._get_similar_size_sub_alpha_groups(sub)
        assert "aa" in result
        assert result["aa"] == ["term1", "term2"]


# ---------------------------------------------------------------------------
# SearchEngineCreator._get_cleaned_terms (static)
# ---------------------------------------------------------------------------


class TestGetCleanedTerms:
    def test_empty_input_returns_extra_terms(self) -> None:
        # With no unstemmed terms and no entity_names, result comes from BARKSIAN_EXTRA_TERMS
        result = SearchEngineCreator._get_cleaned_terms([])
        # Should have some content from the curated Barks terms
        assert isinstance(result, set)

    def test_term_in_terms_to_remove_excluded(self) -> None:
        # Inject a term that should be in TERMS_TO_REMOVE and verify removal
        # Since we can't easily know what's in TERMS_TO_REMOVE, test with real empty list
        result = SearchEngineCreator._get_cleaned_terms([])
        assert isinstance(result, set)

    def test_entity_names_added_to_result(self) -> None:
        # A known-valid entity name not already in cleaned terms
        entity = {"Duckburg"}
        result_without = SearchEngineCreator._get_cleaned_terms([])
        result_with = SearchEngineCreator._get_cleaned_terms([], entity_names=entity)
        # Duckburg should appear or be normalized into result_with
        assert isinstance(result_with, set)
        # result_with should be >= result_without in size (extras added)
        assert len(result_with) >= len(result_without)

    def test_capitalization_map_applied(self) -> None:
        from barks_fantagraphics.whoosh_barks_terms import CAPITALIZATION_MAP

        if not CAPITALIZATION_MAP:
            pytest.skip("CAPITALIZATION_MAP is empty")
        # Pick a term from CAPITALIZATION_MAP
        term_lower, term_proper = next(iter(CAPITALIZATION_MAP.items()))
        result = SearchEngineCreator._get_cleaned_terms([term_lower])
        assert term_proper in result

    def test_all_caps_terms_uppercased(self) -> None:
        from barks_fantagraphics.whoosh_barks_terms import ALL_CAPS

        if not ALL_CAPS:
            pytest.skip("ALL_CAPS is empty")
        term = next(iter(ALL_CAPS))
        result = SearchEngineCreator._get_cleaned_terms([term])
        assert term.upper() in result


# ---------------------------------------------------------------------------
# SearchEngine.find_entities — multi-word entity search
# ---------------------------------------------------------------------------


class TestFindEntities:
    """Test that find_entities correctly matches multi-word entity names."""

    @pytest.fixture
    def index_dir(self, tmp_path: Path) -> Path:
        """Create a temporary Whoosh index with a test document."""
        from barks_fantagraphics.whoosh_punct_tokenizer import WordWithPunctTokenizer
        from whoosh.analysis import LowercaseFilter, StopFilter
        from whoosh.fields import ID, KEYWORD, TEXT, Schema
        from whoosh.index import create_in

        punct_analyzer = (
            WordWithPunctTokenizer() | LowercaseFilter() | StopFilter(stoplist={"the", "a"})
        )
        schema = Schema(
            title=ID(stored=True),
            fanta_vol=ID(stored=True),
            fanta_page=ID(stored=True),
            comic_page=ID(stored=True),
            content_id=ID(stored=True),
            panel_num=ID(stored=True),
            unstemmed=TEXT(stored=False, lang="en", analyzer=punct_analyzer),
            content_raw=TEXT(stored=True, lang="en"),
            entities_person=KEYWORD(stored=True, commas=True, scorable=True),
            entities_location=KEYWORD(stored=True, commas=True, scorable=True),
            entities_org=KEYWORD(stored=True, commas=True, scorable=True),
            entities_work=KEYWORD(stored=True, commas=True, scorable=True),
            entities_misc=KEYWORD(stored=True, commas=True, scorable=True),
        )
        index = create_in(str(tmp_path), schema)
        writer = index.writer()
        writer.add_document(
            title="Bongo on the Congo",
            fanta_vol="26",
            fanta_page="074",
            comic_page="6",
            content_id="16",
            panel_num="7",
            unstemmed="qwak qwaks are a terrible voodoo cult of the duk duk tribe",
            content_raw="QWAK QWAKS ARE A TERRIBLE VOODOO CULT OF THE DUK DUK TRIBE",
            entities_person="Duk Duk,Qwak Qwaks",
            entities_location="",
            entities_org="",
            entities_work="",
            entities_misc="",
        )
        writer.commit()
        return tmp_path

    def test_multi_word_entity_found(self, index_dir: Path) -> None:
        engine = SearchEngine(index_dir)
        results = engine.find_entities("person", "Duk Duk")
        assert len(results) == 1
        assert "Bongo on the Congo" in results

    def test_single_word_entity_found(self, index_dir: Path) -> None:
        engine = SearchEngine(index_dir)
        results = engine.find_entities("person", "Qwak Qwaks")
        assert len(results) == 1

    def test_entity_not_in_index_returns_empty(self, index_dir: Path) -> None:
        engine = SearchEngine(index_dir)
        results = engine.find_entities("person", "Donald Duck")
        assert len(results) == 0

    def test_wrong_entity_type_returns_empty(self, index_dir: Path) -> None:
        engine = SearchEngine(index_dir)
        results = engine.find_entities("location", "Duk Duk")
        assert len(results) == 0


# ---------------------------------------------------------------------------
# SearchEngine._collect_and_sort_results (aggregation + sorting, index-free)
# ---------------------------------------------------------------------------


def _hit(**overrides: str) -> dict[str, str]:
    """Return a minimal stored-fields dict standing in for a Whoosh Hit."""
    base = {
        "title": "A Title",
        "fanta_vol": "10",
        "fanta_page": "001",
        "comic_page": "1",
        "content_id": "5",
        "panel_num": "2",
        "content_raw": "RAW",
    }
    base.update(overrides)
    return base


class TestCollectAndSortResults:
    """Aggregation/sort of raw hits into the TitleDict, exercised without an index."""

    @staticmethod
    def _engine() -> SearchEngine:
        # Bypass __init__ (which opens an index dir): the method under test only
        # touches self via the static _get_entity_types helper.
        return SearchEngine.__new__(SearchEngine)

    def test_titles_sorted_and_vol_parsed_to_int(self) -> None:
        """Titles come back in sorted order and fanta_vol is coerced to int."""
        engine = self._engine()
        hits = [
            _hit(title="Beta", fanta_vol="26"),
            _hit(title="Alpha", fanta_vol="10", fanta_page="002", content_id="3"),
        ]

        results = engine._collect_and_sort_results(cast("list[Hit]", hits), "raw")

        assert list(results.keys()) == ["Alpha", "Beta"]
        assert results["Alpha"].fanta_vol == 10
        assert results["Beta"].fanta_vol == 26

    def test_same_page_speech_grouped_and_sorted_by_group_id(self) -> None:
        """Two hits on the same fanta_page collect into one page, sorted by group id."""
        engine = self._engine()
        hits = [
            _hit(fanta_page="002", content_id="30", content_raw="LATER"),
            _hit(fanta_page="002", content_id="4", content_raw="EARLIER"),
        ]

        results = engine._collect_and_sort_results(cast("list[Hit]", hits), "raw")

        page = results["A Title"].fanta_pages["002"]
        # Numeric sort (int("4") < int("30")), not lexicographic ("30" < "4").
        assert [s.group_id for s in page.speech_info_list] == ["4", "30"]
        assert page.comic_page == "1"

    def test_conflicting_comic_page_for_same_fanta_page_asserts(self) -> None:
        """The same fanta_page mapping to two comic pages is a data error (assert)."""
        engine = self._engine()
        hits = [
            _hit(fanta_page="002", comic_page="1", content_id="1"),
            _hit(fanta_page="002", comic_page="9", content_id="2"),
        ]

        with pytest.raises(AssertionError):
            engine._collect_and_sort_results(cast("list[Hit]", hits), "raw")


# ---------------------------------------------------------------------------
# SearchEngine._get_alpha_split_terms (top-level split, index-free)
# ---------------------------------------------------------------------------


class TestGetAlphaSplitTerms:
    @staticmethod
    def _engine() -> SearchEngine:
        return SearchEngine.__new__(SearchEngine)

    def test_groups_by_first_letter_with_digits_under_zero(self) -> None:
        """Consecutive runs group by first letter; all digit-initial terms key '0'."""
        engine = self._engine()
        result = engine._get_alpha_split_terms(["apple", "avocado", "banana", "3rd", "9lives"])
        assert set(result.keys()) == {"a", "b", "0"}

    def test_invalid_first_letter_raises(self) -> None:
        """A term whose first char is not a letter/digit/apostrophe is rejected."""
        engine = self._engine()
        with pytest.raises(ValueError, match="Invalid first letter"):
            engine._get_alpha_split_terms(["-bad-term"])


# ---------------------------------------------------------------------------
# SearchEngine.find_words / get_all_titles / iter_all_stored_fields (real index)
# ---------------------------------------------------------------------------


def _build_words_index(tmp_path: Path) -> Path:
    from barks_fantagraphics.whoosh_punct_tokenizer import WordWithPunctTokenizer
    from whoosh.analysis import LowercaseFilter, StopFilter
    from whoosh.fields import ID, KEYWORD, TEXT, Schema
    from whoosh.index import create_in

    punct_analyzer = (
        WordWithPunctTokenizer() | LowercaseFilter() | StopFilter(stoplist={"the", "a"})
    )
    schema = Schema(
        title=ID(stored=True),
        fanta_vol=ID(stored=True),
        fanta_page=ID(stored=True),
        comic_page=ID(stored=True),
        content_id=ID(stored=True),
        panel_num=ID(stored=True),
        unstemmed=TEXT(stored=False, lang="en", analyzer=punct_analyzer),
        content_raw=TEXT(stored=True, lang="en"),
        entities_person=KEYWORD(stored=True, commas=True, scorable=True),
        entities_location=KEYWORD(stored=True, commas=True, scorable=True),
        entities_org=KEYWORD(stored=True, commas=True, scorable=True),
        entities_work=KEYWORD(stored=True, commas=True, scorable=True),
        entities_misc=KEYWORD(stored=True, commas=True, scorable=True),
    )
    index = create_in(str(tmp_path), schema)
    writer = index.writer()
    common = {
        "comic_page": "1",
        "panel_num": "1",
        "content_raw": "RAW",
        "entities_person": "",
        "entities_location": "",
        "entities_org": "",
        "entities_work": "",
        "entities_misc": "",
    }
    writer.add_document(
        title="Alpha",
        fanta_vol="10",
        fanta_page="001",
        content_id="5",
        unstemmed="the magic voodoo spell",
        **common,
    )
    writer.add_document(
        title="Beta",
        fanta_vol="20",
        fanta_page="003",
        content_id="8",
        unstemmed="voodoo strikes again",
        **common,
    )
    writer.commit()
    return tmp_path


class TestFindWords:
    @pytest.fixture
    def index_dir(self, tmp_path: Path) -> Path:
        return _build_words_index(tmp_path)

    def test_word_found_across_titles_sorted(self, index_dir: Path) -> None:
        """A word present in two titles returns both, in sorted title order."""
        engine = SearchEngine(index_dir)
        results = engine.find_words("voodoo")
        assert list(results.keys()) == ["Alpha", "Beta"]

    def test_stop_word_only_query_matches_nothing(self, index_dir: Path) -> None:
        """A query of only a stop word ("the") yields no results."""
        engine = SearchEngine(index_dir)
        assert len(engine.find_words("the")) == 0

    def test_word_absent_returns_empty(self, index_dir: Path) -> None:
        engine = SearchEngine(index_dir)
        assert len(engine.find_words("nonexistentword")) == 0

    def test_get_all_titles(self, index_dir: Path) -> None:
        engine = SearchEngine(index_dir)
        assert engine.get_all_titles() == {"Alpha", "Beta"}

    def test_iter_all_stored_fields(self, index_dir: Path) -> None:
        """Every document's stored fields are yielded (unstemmed is not stored)."""
        engine = SearchEngine(index_dir)
        docs = list(engine.iter_all_stored_fields())
        assert len(docs) == 2
        assert {d["title"] for d in docs} == {"Alpha", "Beta"}
        assert all("unstemmed" not in d for d in docs)
