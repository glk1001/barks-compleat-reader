"""What a missing or misconfigured piece of data says: a clear stop, naming the fix.

Each of these is a failure no run meets while the data is whole, so no run had
reached them: a search index without its sidecar files, a story ini whose title
disagrees with whether the story is Barks's, and an OCR prelim override that
names no directory.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.comics_database import _build_comic_book
from barks_fantagraphics.ocr_file_paths import OCR_PRELIM_DIR_ENV_VAR, get_ocr_prelim_dir
from barks_fantagraphics.whoosh_search_engine import SearchEngine, build_index_schema
from whoosh.index import create_in

if TYPE_CHECKING:
    from pathlib import Path


class TestIndexSidecars:
    @pytest.fixture
    def engine(self, tmp_path: Path) -> SearchEngine:
        create_in(str(tmp_path), build_index_schema())
        return SearchEngine(tmp_path)

    @pytest.mark.parametrize("getter", ["get_cleaned_terms", "get_cleaned_alpha_split_terms"])
    def test_a_missing_sidecar_asks_for_a_rebuild(self, engine: SearchEngine, getter: str) -> None:
        with pytest.raises(FileNotFoundError, match="The search index needs rebuilding"):
            getattr(engine, getter)()

    def test_the_sidecars_are_read_when_there(self, engine: SearchEngine, tmp_path: Path) -> None:
        (tmp_path / "cleaned-unstemmed-terms.json").write_text(json.dumps(["quack"]))
        split = {"q": {"qu": ["quack"]}}
        (tmp_path / "cleaned-alpha-split-unstemmed-terms.json").write_text(json.dumps(split))
        assert engine.get_cleaned_terms() == ["quack"]
        assert engine.get_cleaned_alpha_split_terms() == split


class TestStoryIniTitle:
    @staticmethod
    def _build(tmp_path: Path, ini_title: str, *, is_barks_title: bool) -> None:
        ini_file = tmp_path / "story.ini"
        ini_file.write_text(f"[info]\ntitle = {ini_title}\n", encoding="utf-8")
        fanta_info = MagicMock()
        fanta_info.comic_book_info.is_barks_title = is_barks_title
        _build_comic_book(
            "Lost in the Andes!",
            ini_file,
            fanta_info,
            MagicMock(),
            MagicMock(),
            MagicMock(),
            for_building_comics=False,
        )

    def test_a_barks_story_must_name_its_title(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="is a barks title and should be set"):
            self._build(tmp_path, "", is_barks_title=True)

    def test_a_story_not_by_barks_must_not(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="is a not barks title and should not be set"):
            self._build(tmp_path, "Lost in the Andes!", is_barks_title=False)


class TestOcrPrelimOverride:
    def test_without_the_override_the_prelim_dir_is_under_the_ocr_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(OCR_PRELIM_DIR_ENV_VAR, raising=False)
        assert get_ocr_prelim_dir(tmp_path) == tmp_path / "Prelim"

    def test_the_override_names_the_prelim_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(OCR_PRELIM_DIR_ENV_VAR, str(tmp_path))
        assert get_ocr_prelim_dir(tmp_path / "unused") == tmp_path

    def test_an_override_that_is_no_dir_stops_at_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Better than every page reporting a missing prelim."""
        monkeypatch.setenv(OCR_PRELIM_DIR_ENV_VAR, str(tmp_path / "missing"))
        with pytest.raises(NotADirectoryError, match=OCR_PRELIM_DIR_ENV_VAR):
            get_ocr_prelim_dir(tmp_path)
