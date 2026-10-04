# ruff: noqa: PLR2004, SLF001, ERA001, PLC0415

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics import whoosh_search_engine as whoosh_search_engine_module
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.entity_types import EntityType
from barks_fantagraphics.search_ports import CorpusTextTotals
from barks_fantagraphics.search_query import AnyTerm
from barks_fantagraphics.speech_groupers import OcrTypes
from barks_fantagraphics.speech_markup import strip_markup
from barks_fantagraphics.whoosh_search_engine import (
    ENTITY_TYPES,
    SearchEngine,
    SearchEngineCreator,
    _build_curated_entity_sets,
    _filter_entities_to_curated,
    _is_valid_entity_term,
    _normalize_entity_names,
    build_index_schema,
)

if TYPE_CHECKING:
    from collections.abc import Callable
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
# SearchEngineCreator._get_cleaned_terms (static)
# ---------------------------------------------------------------------------


class TestGetCleanedTerms:
    def test_empty_input_returns_extra_terms(self) -> None:
        # With no unstemmed terms and no entity_names, result comes from BARKSIAN_EXTRA_TERMS
        result = SearchEngineCreator._get_cleaned_terms([])
        # Should have some content from the curated Barks terms
        assert isinstance(result, set)

    def test_terms_to_remove_and_fragments_to_suppress_are_left_out(self) -> None:
        from barks_fantagraphics.whoosh_barks_terms import FRAGMENTS_TO_SUPPRESS, TERMS_TO_REMOVE

        removed, fragment = next(iter(TERMS_TO_REMOVE)), next(iter(FRAGMENTS_TO_SUPPRESS))
        result = SearchEngineCreator._get_cleaned_terms([removed, fragment, "lollipop"])
        assert "lollipop" in result
        assert not {removed, fragment, removed.capitalize(), fragment.capitalize()} & result

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
        from whoosh.index import create_in

        # The production schema, so a field change cannot leave this test
        # passing against a stale hand-copied duplicate.
        index = create_in(str(tmp_path), build_index_schema())
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

    def test_conflicting_comic_page_for_same_fanta_page_raises(self) -> None:
        """The same fanta_page mapping to two comic pages is a data error.

        Raised explicitly rather than asserted, so it survives ``python -O``.
        """
        engine = self._engine()
        hits = [
            _hit(fanta_page="002", comic_page="1", content_id="1"),
            _hit(fanta_page="002", comic_page="9", content_id="2"),
        ]

        with pytest.raises(ValueError, match="maps to both comic page"):
            engine._collect_and_sort_results(cast("list[Hit]", hits), "raw")

    def test_non_numeric_group_id_does_not_crash_the_sort(self) -> None:
        """A malformed group id must not take down the whole search."""
        engine = self._engine()
        hits = [
            _hit(fanta_page="002", comic_page="1", content_id="2"),
            _hit(fanta_page="002", comic_page="1", content_id="not-a-number"),
            _hit(fanta_page="002", comic_page="1", content_id="1"),
        ]

        results = engine._collect_and_sort_results(cast("list[Hit]", hits), "raw")

        group_ids = [s.group_id for s in results["A Title"].fanta_pages["002"].speech_info_list]
        assert group_ids == ["1", "2", "not-a-number"]

    def test_speaker_read_from_hit(self) -> None:
        results = self._engine()._collect_and_sort_results(
            cast("list[Hit]", [_hit(speaker="other:Witch Hazel")]), "x"
        )
        assert results["A Title"].fanta_pages["001"].speech_info_list[0].speaker == (
            "other:Witch Hazel"
        )

    @pytest.mark.parametrize("overrides", [{}, {"speaker": ""}])
    def test_missing_or_empty_speaker_is_none(self, overrides: dict[str, str]) -> None:
        """Both an old index (no field) and a group with no call read as None."""
        results = self._engine()._collect_and_sort_results(
            cast("list[Hit]", [_hit(**overrides)]), "x"
        )
        assert results["A Title"].fanta_pages["001"].speech_info_list[0].speaker is None

    def test_result_is_a_plain_dict_not_a_defaultdict(self) -> None:
        """A missing title must raise KeyError, not silently insert a phantom entry."""
        engine = self._engine()
        results = engine._collect_and_sort_results(cast("list[Hit]", [_hit()]), "raw")

        with pytest.raises(KeyError):
            _ = results["No Such Title"]


# ---------------------------------------------------------------------------
# SearchEngine.find_words / get_all_titles / iter_all_stored_fields (real index)
# ---------------------------------------------------------------------------


def _build_words_index(tmp_path: Path) -> Path:
    from whoosh.index import create_in

    # The production schema, so a field change cannot leave this test passing
    # against a stale hand-copied duplicate.
    index = create_in(str(tmp_path), build_index_schema())
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
        speaker="Scrooge",
        unstemmed="the magic voodoo spell",
        **common,
    )
    writer.add_document(
        title="Beta",
        fanta_vol="20",
        fanta_page="003",
        content_id="8",
        speaker="Donald",
        unstemmed="voodoo strikes again",
        **common,
    )
    writer.add_document(
        title="Beta",
        fanta_vol="20",
        fanta_page="004",
        content_id="2",
        speaker="",  # no speaker call on this group
        unstemmed="voodoo once more",
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
        assert len(docs) == 3
        assert {d["title"] for d in docs} == {"Alpha", "Beta"}
        assert all("unstemmed" not in d for d in docs)

    def test_speaker_carried_into_speech_info(self, index_dir: Path) -> None:
        engine = SearchEngine(index_dir)
        results = engine.find_words("voodoo")

        assert results["Alpha"].fanta_pages["001"].speech_info_list[0].speaker == "Scrooge"
        assert results["Beta"].fanta_pages["004"].speech_info_list[0].speaker is None

    def test_speaker_filter_narrows_to_that_speaker(self, index_dir: Path) -> None:
        engine = SearchEngine(index_dir)
        results = engine.find_words("voodoo", speaker="Scrooge")

        assert list(results.keys()) == ["Alpha"]
        assert list(results["Alpha"].fanta_pages.keys()) == ["001"]

    def test_speaker_filter_with_no_such_speaker_is_empty(self, index_dir: Path) -> None:
        engine = SearchEngine(index_dir)
        assert engine.find_words("voodoo", speaker="Gyro") == {}

    def test_empty_speaker_filter_means_everyone(self, index_dir: Path) -> None:
        engine = SearchEngine(index_dir)
        assert engine.find_words("voodoo", speaker="") == engine.find_words("voodoo")

    def test_speaker_filter_ignored_on_index_without_the_field(self, tmp_path: Path) -> None:
        """An index built before speakers existed still answers, unfiltered, with a warning."""
        from whoosh.index import create_in

        schema = build_index_schema()
        schema.remove("speaker")
        index = create_in(str(tmp_path), schema)
        writer = index.writer()
        writer.add_document(
            title="Old",
            fanta_vol="1",
            fanta_page="001",
            comic_page="1",
            content_id="0",
            panel_num="1",
            unstemmed="voodoo",
            content_raw="VOODOO",
        )
        writer.commit()
        engine = SearchEngine(tmp_path)

        with patch.object(whoosh_search_engine_module, "logger") as mock_logger:
            results = engine.find_words("voodoo", speaker="Scrooge")

        assert list(results.keys()) == ["Old"]
        assert results["Old"].fanta_pages["001"].speech_info_list[0].speaker is None
        mock_logger.warning.assert_called_once()

    def test_a_query_leaf_ignores_the_speaker_on_an_index_without_the_field(
        self, tmp_path: Path
    ) -> None:
        """As find_words does: a typed query's leaf finds its bubbles unfiltered, and warns."""
        from whoosh.index import create_in

        schema = build_index_schema()
        schema.remove("speaker")
        writer = create_in(str(tmp_path), schema).writer()
        writer.add_document(
            title="Old",
            fanta_vol="1",
            fanta_page="001",
            comic_page="1",
            content_id="0",
            panel_num="1",
            unstemmed="voodoo",
            content_raw="VOODOO",
        )
        writer.commit()

        with patch.object(whoosh_search_engine_module, "logger") as mock_logger:
            results = SearchEngine(tmp_path).find_bubbles(AnyTerm(("voodoo",)), speaker="Scrooge")

        assert list(results) == ["Old"]
        mock_logger.warning.assert_called_once()

    def test_get_speakers_without_sidecar_is_empty(self, index_dir: Path) -> None:
        """Unlike the term sidecars, a missing speakers file is not an error."""
        engine = SearchEngine(index_dir)
        assert engine.get_speakers() == {}

    def test_get_speakers_reads_sidecar(self, index_dir: Path) -> None:
        (index_dir / "speakers.json").write_text(json.dumps({"Donald": 5, "Scrooge": 2}))
        engine = SearchEngine(index_dir)
        assert engine.get_speakers() == {"Donald": 5, "Scrooge": 2}

    def test_speaker_counts_skip_groups_without_a_call(self, index_dir: Path) -> None:
        engine = SearchEngine(index_dir)
        assert engine._get_speaker_counts() == {"Scrooge": 1, "Donald": 1}


# ---------------------------------------------------------------------------
# SearchEngine.get_corpus_text_totals
# ---------------------------------------------------------------------------


class TestGetCorpusTextTotals:
    @pytest.fixture
    def index_dir(self, tmp_path: Path) -> Path:
        """Build a small index shaped the way the real writer shapes one.

        `content_raw` is indexed stripped and stored marked up (Whoosh's
        `_stored_<field>` convention), so a totals pass that forgets to strip
        counts the markup as words.
        """
        from whoosh.index import create_in

        index = create_in(str(tmp_path), build_index_schema())
        writer = index.writer()
        common = {
            "entities_person": "",
            "entities_location": "",
            "entities_org": "",
            "entities_work": "",
            "entities_misc": "",
        }

        def add(title: str, vol: str, page: str, panel: str, raw: str, group: str) -> None:
            writer.add_document(
                title=title,
                fanta_vol=vol,
                fanta_page=page,
                comic_page="1",
                content_id=group,
                panel_num=panel,
                unstemmed=strip_markup(raw),
                content_raw=strip_markup(raw),
                _stored_content_raw=raw,
                **common,
            )

        # Two groups share a page and a panel; the third is a second page.
        add("Alpha", "10", "001", "1", "[b] ONE TWO [/b]", "1")
        add("Alpha", "10", "001", "1", "THREE", "2")
        add("Alpha", "10", "002", "3", "FOUR FIVE", "3")
        add("Beta", "20", "001", "1", "SIX", "4")
        writer.commit()
        return tmp_path

    def test_totals_over_the_whole_index(self, index_dir: Path) -> None:
        totals = SearchEngine(index_dir).get_corpus_text_totals()

        assert totals.num_text_entities == 4
        assert totals.num_titles == 2
        assert totals.num_pages == 3
        assert totals.num_panels == 3

    def test_words_are_counted_without_markup(self, index_dir: Path) -> None:
        """A bracketed emphasis tag is markup, not two extra words."""
        assert SearchEngine(index_dir).get_corpus_text_totals().num_words == 6

    def test_empty_index_totals_are_zero(self, tmp_path: Path) -> None:
        from whoosh.index import create_in

        create_in(str(tmp_path), build_index_schema())

        totals = SearchEngine(tmp_path).get_corpus_text_totals()

        assert totals == CorpusTextTotals(0, 0, 0, 0, 0)


# ---------------------------------------------------------------------------
# SearchEngineCreator.index_volumes: the build the reader's search index comes from
# ---------------------------------------------------------------------------


def _speech(text: str, panel: int = 1, speaker: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        ai_text=strip_markup(text).lower(),
        raw_ai_text=text,
        panel_num=panel,
        speaker=SimpleNamespace(speaker=speaker) if speaker else None,
    )


def _page(ocr: OcrTypes, fanta_page: str, groups: dict[str, SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(
        ocr_index=ocr, fanta_vol=5, fanta_page=fanta_page, comic_page="1", speech_groups=groups
    )


PAGES = {
    Titles.LOST_IN_THE_ANDES: [
        _page(
            OcrTypes.EASYOCR,
            "041",
            {
                "0": _speech("[b]SQUARE[/b] eggs in the Andes!", speaker="Donald Duck"),
                "1": _speech("Square chickens, square eggs, square eggs!", panel=2),
            },
        ),
        # The other OCR engine's reading of the same page: never indexed.
        _page(OcrTypes.PADDLEOCR, "041", {"0": _speech("paddleocr only words")}),
    ],
    Titles.GOOD_DEEDS: [
        _page(OcrTypes.EASYOCR, "007", {"0": _speech("A good deed in Acapulco.", speaker="Huey")}),
    ],
}


class TestSearchEngineCreator:
    @staticmethod
    def _build(
        tmp_path: Path,
        pages: dict[Titles, list[SimpleNamespace]] | None = None,
        index_dir: Path | None = None,
        **kwargs: object,
    ) -> tuple[SearchEngineCreator, MagicMock]:
        pages = PAGES if pages is None else pages
        db = MagicMock()
        db.get_configured_titles_in_fantagraphics_volumes.return_value = [
            (ENUM_TO_STR_TITLE[t], SimpleNamespace(comic_book_info=SimpleNamespace(title=t)))
            for t in pages
        ]
        speech_groups = MagicMock()
        speech_groups.return_value.get_speech_page_groups.side_effect = (
            lambda title, skip_missing: pages[title]  # noqa: ARG005
        )
        with patch.object(whoosh_search_engine_module, "SpeechGroups", speech_groups):
            creator = SearchEngineCreator(db, index_dir or tmp_path / "index", OcrTypes.EASYOCR)
            creator.index_volumes([5, 6], **kwargs)  # ty: ignore[invalid-argument-type]
        return creator, speech_groups

    def test_the_built_index_answers_searches(self, tmp_path: Path) -> None:
        engine, _ = self._build(tmp_path)
        engine = engine.get_search_engine()
        assert set(engine.find_words("eggs")) == {ENUM_TO_STR_TITLE[Titles.LOST_IN_THE_ANDES]}
        assert engine.get_all_titles() == {
            ENUM_TO_STR_TITLE[Titles.LOST_IN_THE_ANDES],
            ENUM_TO_STR_TITLE[Titles.GOOD_DEEDS],
        }

    def test_only_the_chosen_ocr_engines_reading_is_indexed(self, tmp_path: Path) -> None:
        engine, _ = self._build(tmp_path)
        assert engine.find_words("paddleocr") == {}

    def test_markup_is_stored_for_the_reader_but_not_indexed(self, tmp_path: Path) -> None:
        engine, _ = self._build(tmp_path)
        stored = [f["content_raw"] for f in engine.iter_all_stored_fields()]
        assert "[b]SQUARE[/b] eggs in the Andes!" in stored
        assert "b" not in engine.get_cleaned_terms()

    def test_the_sidecars_the_reader_reads_are_written(self, tmp_path: Path) -> None:
        engine, _ = self._build(tmp_path)
        folder = tmp_path / "index"
        assert json.loads((folder / "volumes.json").read_text()) == [5, 6]
        assert "eggs" in engine.get_cleaned_terms()
        # Split by first letter, then into ranges ("ea-el") sized by the letter's terms.
        assert any(
            "eggs" in terms for terms in engine.get_cleaned_alpha_split_terms()["e"].values()
        )
        assert engine.get_speakers() == {"Donald Duck": 1, "Huey": 1}

    def test_word_frequencies_count_every_use(self, tmp_path: Path) -> None:
        self._build(tmp_path)
        folder = tmp_path / "index"
        most = dict(json.loads(next(folder.glob("*most*common*")).read_text()))
        assert most["square"] == 4
        assert most["eggs"] == 3
        # The least-common list leaves out words used once.
        least = dict(json.loads(next(folder.glob("*least*common*")).read_text()))
        assert "acapulco" not in least
        assert least["square"] == 4

    def test_entity_terms_split_by_first_letter_without_the_garbage(self, tmp_path: Path) -> None:
        """A term must start with a letter, a digit or an apostrophe; "-ER-" is OCR garbage."""
        engine = SearchEngine(_build_words_index(tmp_path))
        assert engine.get_alpha_split_entity_terms("location") == {}  # no sidecar
        path = engine._entity_terms_paths[EntityType("location")]
        path.write_text(json.dumps(["-ER-", ""]))
        assert engine.get_alpha_split_entity_terms("location") == {}  # garbage only
        path.write_text(json.dumps(["-ER-", "Acapulco", "'Frisco"]))
        split = engine.get_alpha_split_entity_terms("location")
        listed = [term for groups in split.values() for terms in groups.values() for term in terms]
        assert sorted(listed) == ["'Frisco", "Acapulco"]

    def test_without_entities_there_are_no_entity_terms(self, tmp_path: Path) -> None:
        engine, _ = self._build(tmp_path)
        assert engine.get_entity_terms("location") == []

    def test_provided_entities_are_kept_only_when_curated(self, tmp_path: Path) -> None:
        """A curated name is kept, in its curated casing; anything else is dropped."""

        def provider(title: str, page: str, group: str) -> dict[str, set[str]]:
            if (title, page, group) == (ENUM_TO_STR_TITLE[Titles.GOOD_DEEDS], "007", "0"):
                return {"person": {"duk duk", "Nobody Special"}, "location": {"Acapulco"}}
            return {}

        engine, _ = self._build(tmp_path, entity_provider=provider)
        assert engine.get_entity_terms("person") == ["Duk Duk"]
        assert engine.get_entity_terms("location") == ["Acapulco"]
        assert set(engine.find_entities("person", "Duk Duk")) == {
            ENUM_TO_STR_TITLE[Titles.GOOD_DEEDS]
        }

    def test_a_tagger_is_used_when_there_is_no_provider(self, tmp_path: Path) -> None:
        tagger = MagicMock(return_value={"location": {"Acapulco"}})
        engine, _ = self._build(tmp_path, entity_tagger=tagger)
        tagger.assert_any_call("a good deed in acapulco.")
        assert engine.get_entity_terms("location") == ["Acapulco"]

    def test_skipping_missing_pages_is_passed_to_the_speech_groups(self, tmp_path: Path) -> None:
        _, speech_groups = self._build(tmp_path, skip_missing_pages=True)
        calls = speech_groups.return_value.get_speech_page_groups.call_args_list
        assert calls
        assert all(call.kwargs == {"skip_missing": True} for call in calls)


# ---------------------------------------------------------------------------
# What mutation testing found unchecked: the builder's calls and sidecars, the
# entity types a found bubble names, limits, messages, and the term rules.
# ---------------------------------------------------------------------------

_ANDES = ENUM_TO_STR_TITLE[Titles.LOST_IN_THE_ANDES]
_GOOD_DEEDS = ENUM_TO_STR_TITLE[Titles.GOOD_DEEDS]
_NO_SPEAKER_FIELD = (
    "Search index has no speaker field; ignoring speaker filter. The search index needs rebuilding."
)


def _good_deeds_entities(title: str, page: str, group: str) -> dict[str, set[str]]:
    if (title, page, group) == (_GOOD_DEEDS, "007", "0"):
        return {"person": {"abie", "adam"}, "location": {"acapulco"}}
    return {}


class TestTheBuilderMore:
    _build = staticmethod(TestSearchEngineCreator._build)

    def test_it_asks_for_the_volumes_comics_and_their_pages(self, tmp_path: Path) -> None:
        creator, speech_groups = self._build(tmp_path)
        db = cast("MagicMock", creator._comics_database)
        db.get_configured_titles_in_fantagraphics_volumes.assert_called_once_with(
            [5, 6], exclude_non_comics=True
        )
        speech_groups.assert_called_once_with(db)
        calls = speech_groups.return_value.get_speech_page_groups.call_args_list
        assert all(call.kwargs == {"skip_missing": False} for call in calls)  # by default

    def test_a_page_read_by_the_other_ocr_engine_does_not_end_the_story(
        self, tmp_path: Path
    ) -> None:
        pages = {
            Titles.LOST_IN_THE_ANDES: [
                _page(OcrTypes.PADDLEOCR, "040", {"0": _speech("paddleocr only words")}),
                _page(OcrTypes.EASYOCR, "041", {"0": _speech("Square eggs!")}),
            ]
        }
        engine, _ = self._build(tmp_path, pages)
        assert set(engine.find_words("eggs")) == {_ANDES}

    def test_its_folder_is_made_with_its_parents_and_built_again_in_place(
        self, tmp_path: Path
    ) -> None:
        deep = tmp_path / "a" / "b" / "index"
        self._build(tmp_path, index_dir=deep)
        engine, _ = self._build(tmp_path, index_dir=deep)  # again: no error
        assert set(engine.find_words("eggs")) == {_ANDES}

    def test_the_sidecar_files_have_the_names_their_readers_open(self, tmp_path: Path) -> None:
        """generate_stats_images.py opens most-common-unstemmed-terms.json by name."""
        engine, _ = self._build(tmp_path)
        folder = tmp_path / "index"
        with engine._index.reader() as reader:
            lexicon = [t.decode("utf-8") for t in reader.lexicon("unstemmed")]
        assert json.loads((folder / "unstemmed-terms.json").read_text()) == lexicon
        assert (folder / "most-common-unstemmed-terms.json").is_file()
        assert (folder / "least-common-unstemmed-terms.json").is_file()

    def test_the_cleaned_terms_are_in_collated_order_not_code_points(self, tmp_path: Path) -> None:
        engine, _ = self._build(tmp_path)
        cleaned = engine.get_cleaned_terms()
        assert cleaned.index("Cattail Slough") < cleaned.index("chickens")
        assert cleaned.index("chickens") < cleaned.index("Chickie Biddy")

    def test_entity_names_join_the_cleaned_terms(self, tmp_path: Path) -> None:
        engine, _ = self._build(tmp_path, entity_provider=_good_deeds_entities)
        assert {"abie", "adam"} <= set(engine.get_cleaned_terms())

    def test_each_of_a_bubbles_entities_is_found_by_its_own_name(self, tmp_path: Path) -> None:
        engine, _ = self._build(tmp_path, entity_provider=_good_deeds_entities)
        assert set(engine.find_entities("person", "abie")) == {_GOOD_DEEDS}
        assert set(engine.find_entities("person", "adam")) == {_GOOD_DEEDS}

    def test_a_bubble_with_no_entities_stores_none(self, tmp_path: Path) -> None:
        engine, _ = self._build(tmp_path)
        for fields in engine.iter_all_stored_fields():
            assert not any(fields.get(f"entities_{t}") for t in ENTITY_TYPES), fields

    def test_a_speakers_bubbles_are_all_counted(self, tmp_path: Path) -> None:
        pages = {
            Titles.LOST_IN_THE_ANDES: [
                _page(
                    OcrTypes.EASYOCR,
                    "041",
                    {
                        "0": _speech("Eggs!", speaker="Scrooge"),
                        "1": _speech("Square!", speaker="Scrooge"),
                    },
                )
            ]
        }
        engine, _ = self._build(tmp_path, pages)
        assert engine.get_speakers() == {"Scrooge": 2}

    def test_the_least_common_list_keeps_words_used_twice_and_stops_at_200(
        self, tmp_path: Path
    ) -> None:
        words = " ".join(f"word{i:03d}" for i in range(205))
        pages = {
            Titles.LOST_IN_THE_ANDES: [
                _page(OcrTypes.EASYOCR, "041", {"0": _speech(words), "1": _speech(words)})
            ]
        }
        self._build(tmp_path, pages)
        least = json.loads((tmp_path / "index" / "least-common-unstemmed-terms.json").read_text())
        assert len(least) == 200
        assert all(count == 2 for _, count in least)


class TestWhatAFoundBubbleCarries:
    _build = staticmethod(TestSearchEngineCreator._build)

    def test_its_text_with_its_markup(self, tmp_path: Path) -> None:
        engine, _ = self._build(tmp_path)
        speech = engine.find_words("eggs")[_ANDES].fanta_pages["041"].speech_info_list[0]
        assert speech.speech_text_markup == "[b]SQUARE[/b] eggs in the Andes!"

    def test_the_entity_types_whose_names_hold_a_word_searched(self, tmp_path: Path) -> None:
        engine, _ = self._build(tmp_path, entity_provider=_good_deeds_entities)
        [speech] = engine.find_words("acapulco")[_GOOD_DEEDS].fanta_pages["007"].speech_info_list
        assert speech.entity_types == ("location",)  # its people are named, but not searched

    def test_a_name_after_a_comma_is_matched_whole(self, tmp_path: Path) -> None:
        """The person field holds "abie,adam": adam is its own name, not "abie,adam"."""
        engine, _ = self._build(tmp_path, entity_provider=_good_deeds_entities)
        found = engine.find_bubbles(AnyTerm(("adam", "deed")))
        [speech] = found[_GOOD_DEEDS].fanta_pages["007"].speech_info_list
        assert speech.entity_types == ("person",)


class TestLimitsAndMessages:
    _build = staticmethod(TestSearchEngineCreator._build)

    def test_each_search_stops_at_the_result_limit(self, tmp_path: Path) -> None:
        """Each search past the limit returns fewer than it would: Whoosh's own default is 10."""

        def abie_twice(_title: str, _page: str, group: str) -> dict[str, set[str]]:
            return {"person": {"abie"}} if group == "0" else {}

        engine, _ = self._build(tmp_path, entity_provider=abie_twice)
        with patch.object(whoosh_search_engine_module, "_SEARCH_RESULT_LIMIT", 1):
            square = engine.find_words("square")  # in two of the Andes' bubbles
            assert len(square[_ANDES].fanta_pages["041"].speech_info_list) == 1
            hits = engine.find_bubbles(AnyTerm(("square", "deed")))  # three bubbles, two stories
            assert (
                sum(len(p.speech_info_list) for t in hits.values() for p in t.fanta_pages.values())
                == 1
            )
            assert len(engine.find_entities("person", "abie")) == 1  # in both stories
        assert len(engine.find_entities("person", "abie")) == 2

    def test_the_old_index_warning_says_what_to_do(self, tmp_path: Path) -> None:
        from whoosh.index import create_in

        schema = build_index_schema()
        schema.remove("speaker")
        writer = create_in(str(tmp_path), schema).writer()
        writer.add_document(
            title="Old",
            fanta_vol="1",
            fanta_page="001",
            comic_page="1",
            content_id="0",
            panel_num="1",
            unstemmed="voodoo",
            content_raw="VOODOO",
        )
        writer.commit()
        engine = SearchEngine(tmp_path)
        with patch.object(whoosh_search_engine_module, "logger") as mock_logger:
            engine.find_words("voodoo", speaker="Scrooge")
            engine.find_bubbles(AnyTerm(("voodoo",)), speaker="Scrooge")
        assert [c.args[0] for c in mock_logger.warning.call_args_list] == [_NO_SPEAKER_FIELD] * 2

    @pytest.mark.parametrize(
        ("read", "name"),
        [
            (SearchEngine.get_cleaned_terms, "cleaned-unstemmed-terms.json"),
            (
                SearchEngine.get_cleaned_alpha_split_terms,
                "cleaned-alpha-split-unstemmed-terms.json",
            ),
        ],
    )
    def test_a_missing_sidecar_says_which_and_what_to_do(
        self, tmp_path: Path, read: Callable[[SearchEngine], object], name: str
    ) -> None:
        engine = SearchEngine(_build_words_index(tmp_path))
        with pytest.raises(FileNotFoundError) as raised:
            read(engine)
        assert str(raised.value) == (
            f"Index sidecar file is missing: {engine._index.storage.folder / name}."
            " The search index needs rebuilding."
        )

    def test_quotes_and_backslashes_in_a_search_are_searched_as_text(self, tmp_path: Path) -> None:
        engine, _ = self._build(tmp_path)
        for text in ('square "eggs"', "square\\", '"eggs', 'eggs\\"x'):
            assert set(engine.find_words(text)) == {_ANDES}, text


class TestTermRules:
    @pytest.mark.parametrize(
        ("term", "valid"),
        [
            ("apple", True),
            ("zebra", True),
            ("Zebra", True),  # its first letter is read lower-cased
            ("00 agent", True),  # a word of capitals is two letters at most
            ("9 lives", True),
            ("'frisco", True),
            ("_bad", False),
            ("[bracket", False),
            ("@home", False),
            ("-er-", False),
            ("", False),
        ],
    )
    def test_an_entity_term_starts_with_a_letter_a_digit_or_an_apostrophe(
        self, term: str, valid: bool
    ) -> None:
        assert _is_valid_entity_term(term) is valid

    def test_the_letters_split_keeps_the_same_terms(self, tmp_path: Path) -> None:
        engine = SearchEngine(_build_words_index(tmp_path))
        terms = ["apple", "zebra", "00 agent", "9 lives", "'frisco", "_bad", "[x", "@home", "-ER-"]
        engine._entity_terms_paths[EntityType("person")].write_text(json.dumps(terms))
        split = engine.get_alpha_split_entity_terms("person")
        listed = sorted(t for groups in split.values() for ts in groups.values() for t in ts)
        assert listed == ["'frisco", "00 agent", "9 lives", "apple", "zebra"]

    def test_a_term_already_a_word_is_not_added_again_and_the_rest_still_are(self) -> None:
        assert _normalize_entity_names({"Gold", "Zebra Land"}, {"gold"}) == {"Zebra Land"}

    def test_a_curated_name_takes_its_casing_and_the_rest_still_follow(self) -> None:
        normalized = _normalize_entity_names({"alice in wonderland", "Zebra Land"}, set())
        assert normalized == {"Alice in Wonderland", "Zebra Land"}

    def test_cleaning_capitalizes_drops_what_a_word_covers_and_suppresses(self) -> None:
        from barks_fantagraphics.whoosh_barks_terms import (
            MULTI_WORD_TERMS_TO_SUPPRESS,
            TERMS_TO_CAPITALIZE,
        )

        to_capitalize = min(TERMS_TO_CAPITALIZE)
        suppressed = min(MULTI_WORD_TERMS_TO_SUPPRESS)
        cleaned = SearchEngineCreator._get_cleaned_terms(
            [to_capitalize, "gold"], entity_names={"Gold", suppressed.lower(), "Zebra Land"}
        )
        assert to_capitalize.capitalize() in cleaned
        assert "Gold" not in cleaned  # "gold" covers it
        assert "Zebra Land" in cleaned
        assert not {t for t in cleaned if t.lower() == suppressed.lower()}

    def test_near_finds_the_pair_when_a_form_is_not_in_the_index(self, tmp_path: Path) -> None:
        from barks_fantagraphics.search_query import Near

        engine, _ = self._build_index(tmp_path)
        near = Near(AnyTerm(("aardvark", "square")), AnyTerm(("eggs",)), 3)
        assert set(engine.find_bubbles(near)) == {_ANDES}

    @staticmethod
    def _build_index(tmp_path: Path) -> tuple[SearchEngineCreator, MagicMock]:
        return TestSearchEngineCreator._build(tmp_path)
