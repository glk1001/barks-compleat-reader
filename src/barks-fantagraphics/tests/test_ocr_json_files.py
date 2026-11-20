from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from barks_fantagraphics.ocr_file_paths import OCR_ANNOTATIONS_DIR, OCR_FINAL_DIR, OCR_PRELIM_DIR
from barks_fantagraphics.ocr_json_files import JsonFiles
from spec_mocks import mock_comics_database

if TYPE_CHECKING:
    from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(volume: int = 3, volume_dirname: str = "Carl-Barks-Vol-03") -> MagicMock:
    db = mock_comics_database()
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
    def test_the_volume_and_its_dirname_come_from_the_database(self) -> None:
        jf, db = _make_json_files(volume=7, volume_dirname="Carl-Barks-Vol-07")

        db.get_fanta_volume_int.assert_called_once_with("Some Title")
        db.get_fantagraphics_volume_title.assert_called_once_with(7)
        assert (jf.title, jf.volume, jf.volume_dirname) == ("Some Title", 7, "Carl-Barks-Vol-07")

    def test_each_results_dir_is_the_volume_s_under_its_own_root(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")

        assert jf.title_prelim_results_dir == OCR_PRELIM_DIR / "Vol-03"
        assert jf.title_final_results_dir == OCR_FINAL_DIR / "Vol-03"
        assert jf.title_annotated_images_dir == OCR_ANNOTATIONS_DIR / "Vol-03"

    def test_no_page_is_set_to_begin_with(self) -> None:
        jf, _ = _make_json_files()

        assert jf.page == ""
        assert jf.ocr_file is None
        assert _per_page_lists(jf) == [[], [], [], [], [], []]


# ---------------------------------------------------------------------------
# set_ocr_file
# ---------------------------------------------------------------------------


def _per_page_lists(jf: JsonFiles) -> list[list[str] | list[Path]]:
    return [
        jf.ocr_type,
        jf.ocr_prelim_groups_json_file,
        jf.ocr_final_groups_json_file,
        jf.ocr_prelim_groups_annotated_file,
        jf.ocr_final_groups_annotated_file,
        jf.ocr_boxes_annotated_file,
    ]


def _ocr_pair(page: str) -> tuple[Path, Path]:
    return Path(f"{page}.hires.json"), Path(f"{page}.lores.json")


def _expected_per_page_lists(page: str) -> list[list[str] | list[Path]]:
    """Each list for a page of "Vol-03": one entry per engine, in the engines' order.

    The final files do not depend on the engine, so both of their entries are the same.
    """
    prelim, final, annotations = (
        root / "Vol-03" for root in (OCR_PRELIM_DIR, OCR_FINAL_DIR, OCR_ANNOTATIONS_DIR)
    )
    return [
        ["hires", "lores"],
        [
            prelim / f"{page}-hires-gemini-prelim-groups.json",
            prelim / f"{page}-lores-gemini-prelim-groups.json",
        ],
        [final / f"{page}-gemini-final-groups.json"] * 2,
        [
            annotations / f"{page}-hires-ocr-gemini-prelim-annotated.png",
            annotations / f"{page}-lores-ocr-gemini-prelim-annotated.png",
        ],
        [annotations / f"{page}-ocr-gemini-final-annotated.png"] * 2,
        [
            annotations / f"{page}-hires-ocr-gemini-boxes-annotated.png",
            annotations / f"{page}-lores-ocr-gemini-boxes-annotated.png",
        ],
    ]


class TestSetOcrFile:
    def test_the_page_and_every_per_page_file_are_set(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        pair = _ocr_pair("007")

        jf.set_ocr_file(pair)

        assert jf.page == "007"
        assert jf.ocr_file == pair
        assert _per_page_lists(jf) == _expected_per_page_lists("007")

    def test_a_second_page_replaces_the_first(self) -> None:
        jf, _ = _make_json_files(volume_dirname="Vol-03")
        jf.set_ocr_file(_ocr_pair("001"))

        jf.set_ocr_file(_ocr_pair("002"))

        assert jf.page == "002"
        assert _per_page_lists(jf) == _expected_per_page_lists("002")
