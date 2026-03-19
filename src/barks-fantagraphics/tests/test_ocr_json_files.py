# ruff: noqa: PLR2004

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from barks_fantagraphics.ocr_file_paths import OCR_ANNOTATIONS_DIR, OCR_FINAL_DIR, OCR_PRELIM_DIR
from barks_fantagraphics.ocr_json_files import JsonFiles

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(volume: int = 3, volume_dirname: str = "Carl-Barks-Vol-03") -> MagicMock:
    db = MagicMock()
    db.get_fanta_volume_int.return_value = volume
    db.get_fantagraphics_volume_title.return_value = volume_dirname
    return db


def _make_json_files(
    volume: int = 3, volume_dirname: str = "Carl-Barks-Vol-03"
) -> tuple[JsonFiles, MagicMock]:
    db = _make_db(volume=volume, volume_dirname=volume_dirname)
    jf = JsonFiles(db, "Some Title")
    return jf, db


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestJsonFilesInit:
    def test_stores_title(self) -> None:
        jf, _ = _make_json_files()
        assert jf.title == "Some Title"

    def test_calls_db_for_volume(self) -> None:
        db = _make_db()
        JsonFiles(db, "My Title")
        db.get_fanta_volume_int.assert_called_once_with("My Title")

    def test_calls_db_for_volume_dirname(self) -> None:
        db = _make_db(volume=5)
        JsonFiles(db, "My Title")
        db.get_fantagraphics_volume_title.assert_called_once_with(5)

    def test_stores_volume_and_dirname(self) -> None:
        jf, _ = _make_json_files(volume=7, volume_dirname="Carl-Barks-Vol-07")
        assert jf.volume == 7
        assert jf.volume_dirname == "Carl-Barks-Vol-07"

    def test_prelim_dir_uses_volume_dirname(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        assert jf.title_prelim_results_dir == OCR_PRELIM_DIR / "Vol-03"

    def test_final_dir_uses_volume_dirname(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        assert jf.title_final_results_dir == OCR_FINAL_DIR / "Vol-03"

    def test_annotated_dir_uses_volume_dirname(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        assert jf.title_annotated_images_dir == OCR_ANNOTATIONS_DIR / "Vol-03"

    def test_initial_state_empty(self) -> None:
        jf, _ = _make_json_files()
        assert jf.page == ""
        assert jf.ocr_file is None
        assert jf.ocr_type == []
        assert jf.ocr_prelim_groups_json_file == []
        assert jf.ocr_final_groups_json_file == []
        assert jf.ocr_prelim_groups_annotated_file == []
        assert jf.ocr_final_groups_annotated_file == []
        assert jf.ocr_boxes_annotated_file == []


# ---------------------------------------------------------------------------
# set_ocr_file
# ---------------------------------------------------------------------------


class TestSetOcrFile:
    @staticmethod
    def _ocr_pair(
        page: str = "001",
        types: tuple[str, str] = ("hires", "lores"),
    ) -> tuple[Path, Path]:
        return Path(f"{page}.{types[0]}.json"), Path(f"{page}.{types[1]}.json")

    def test_sets_page_from_first_file_stem(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        jf.set_ocr_file(self._ocr_pair(page="042"))
        assert jf.page == "042"

    def test_sets_ocr_file(self) -> None:
        jf, _ = _make_json_files()
        pair = self._ocr_pair()
        jf.set_ocr_file(pair)
        assert jf.ocr_file == pair

    def test_extracts_ocr_types(self) -> None:
        jf, _ = _make_json_files()
        jf.set_ocr_file(self._ocr_pair(types=("hires", "lores")))
        assert jf.ocr_type == ["hires", "lores"]

    def test_builds_two_prelim_json_files(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        jf.set_ocr_file(self._ocr_pair(page="007", types=("hires", "lores")))
        assert len(jf.ocr_prelim_groups_json_file) == 2
        assert jf.ocr_prelim_groups_json_file[0].name == "007-hires-gemini-prelim-groups.json"
        assert jf.ocr_prelim_groups_json_file[1].name == "007-lores-gemini-prelim-groups.json"

    def test_prelim_json_files_in_prelim_dir(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        jf.set_ocr_file(self._ocr_pair(page="007"))
        for f in jf.ocr_prelim_groups_json_file:
            assert f.parent == OCR_PRELIM_DIR / "Vol-03"

    def test_builds_two_final_json_files(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        jf.set_ocr_file(self._ocr_pair(page="007"))
        assert len(jf.ocr_final_groups_json_file) == 2
        # final filename doesn't depend on ocr_type — both entries are the same
        assert jf.ocr_final_groups_json_file[0].name == "007-gemini-final-groups.json"
        assert jf.ocr_final_groups_json_file[1].name == "007-gemini-final-groups.json"

    def test_final_json_files_in_final_dir(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        jf.set_ocr_file(self._ocr_pair(page="007"))
        for f in jf.ocr_final_groups_json_file:
            assert f.parent == OCR_FINAL_DIR / "Vol-03"

    def test_builds_prelim_annotated_files(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        jf.set_ocr_file(self._ocr_pair(page="007", types=("hires", "lores")))
        assert len(jf.ocr_prelim_groups_annotated_file) == 2
        assert (
            jf.ocr_prelim_groups_annotated_file[0].name
            == "007-hires-ocr-gemini-prelim-annotated.png"
        )
        assert (
            jf.ocr_prelim_groups_annotated_file[1].name
            == "007-lores-ocr-gemini-prelim-annotated.png"
        )

    def test_prelim_annotated_files_in_annotations_dir(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        jf.set_ocr_file(self._ocr_pair(page="007"))
        for f in jf.ocr_prelim_groups_annotated_file:
            assert f.parent == OCR_ANNOTATIONS_DIR / "Vol-03"

    def test_builds_final_annotated_files(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        jf.set_ocr_file(self._ocr_pair(page="007"))
        assert len(jf.ocr_final_groups_annotated_file) == 2
        assert jf.ocr_final_groups_annotated_file[0].name == "007-ocr-gemini-final-annotated.png"
        assert jf.ocr_final_groups_annotated_file[1].name == "007-ocr-gemini-final-annotated.png"

    def test_final_annotated_files_in_annotations_dir(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        jf.set_ocr_file(self._ocr_pair(page="007"))
        for f in jf.ocr_final_groups_annotated_file:
            assert f.parent == OCR_ANNOTATIONS_DIR / "Vol-03"

    def test_builds_boxes_annotated_files(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        jf.set_ocr_file(self._ocr_pair(page="007", types=("hires", "lores")))
        assert len(jf.ocr_boxes_annotated_file) == 2
        assert jf.ocr_boxes_annotated_file[0].name == "007-hires-ocr-gemini-boxes-annotated.png"
        assert jf.ocr_boxes_annotated_file[1].name == "007-lores-ocr-gemini-boxes-annotated.png"

    def test_boxes_annotated_files_in_annotations_dir(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        jf.set_ocr_file(self._ocr_pair(page="007"))
        for f in jf.ocr_boxes_annotated_file:
            assert f.parent == OCR_ANNOTATIONS_DIR / "Vol-03"

    def test_resets_lists_on_second_call(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        jf.set_ocr_file(self._ocr_pair(page="001"))
        jf.set_ocr_file(self._ocr_pair(page="002"))
        # After second call, lists have exactly 2 entries (not 4)
        assert len(jf.ocr_prelim_groups_json_file) == 2
        assert len(jf.ocr_prelim_groups_annotated_file) == 2
        assert len(jf.ocr_boxes_annotated_file) == 2
        assert jf.page == "002"
