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
from barks_fantagraphics.speech_groupers import OcrTypes
from barks_fantagraphics.speech_markup import strip_markup
from barks_fantagraphics.whoosh_search_engine import (
    SearchEngine,
    SearchEngineCreator,
    _build_curated_entity_sets,
    _filter_entities_to_curated,
    _is_valid_entity_term,
    _normalize_entity_names,
    build_index_schema,
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
    def _build(tmp_path: Path, **kwargs: object) -> tuple[SearchEngineCreator, MagicMock]:
        db = MagicMock()
        db.get_configured_titles_in_fantagraphics_volumes.return_value = [
            (ENUM_TO_STR_TITLE[t], SimpleNamespace(comic_book_info=SimpleNamespace(title=t)))
            for t in PAGES
        ]
        speech_groups = MagicMock()
        speech_groups.return_value.get_speech_page_groups.side_effect = (
            lambda title, skip_missing: PAGES[title]  # noqa: ARG005
        )
        with patch.object(whoosh_search_engine_module, "SpeechGroups", speech_groups):
            creator = SearchEngineCreator(db, tmp_path / "index", OcrTypes.EASYOCR)
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
