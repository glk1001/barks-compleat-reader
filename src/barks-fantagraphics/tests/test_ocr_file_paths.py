"""The OCR tree's batch-job files and per-page group files, named as barks-ocr expects."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics import ocr_file_paths
from barks_fantagraphics.ocr_file_paths import (
    OCR_PRELIM_DIR_ENV_VAR,
    UNPROCESSED_BATCH_JOBS_DIR,
    get_batch_details_file,
    get_batch_requests_file,
    get_ocr_predicted_groups_filename,
    get_ocr_prelim_groups_json_filename,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_a_titles_batch_job_details_wait_with_the_unprocessed_jobs() -> None:
    assert get_batch_details_file("Lost in the Andes!") == (
        UNPROCESSED_BATCH_JOBS_DIR / "Lost in the Andes!-batch-job-details.json"
    )


def test_a_titles_batch_requests_wait_beside_them() -> None:
    assert get_batch_requests_file("Lost in the Andes!") == (
        UNPROCESSED_BATCH_JOBS_DIR / "Lost in the Andes!-batch-requests-with-image.json"
    )


def test_a_pages_predicted_groups_are_named_by_page_and_ocr_type() -> None:
    assert get_ocr_predicted_groups_filename("042", "easyocr") == (
        "042-easyocr-json-ocr-ai-predicted-groups.json"
    )


def test_the_predicted_and_prelim_group_files_of_a_page_differ() -> None:
    assert get_ocr_predicted_groups_filename("042", "paddleocr") != (
        get_ocr_prelim_groups_json_filename("042", "paddleocr")
    )


def _forget_prelim_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the next ``OCR_PRELIM_DIR`` a fresh look-up, and put any found one back after."""
    monkeypatch.setitem(vars(ocr_file_paths), "OCR_PRELIM_DIR", None)
    del vars(ocr_file_paths)["OCR_PRELIM_DIR"]


def test_a_stale_prelim_override_does_not_stop_the_search_engines_import() -> None:
    """The reader imports the search engine, and never uses the prelim tree."""
    env = {**os.environ, OCR_PRELIM_DIR_ENV_VAR: "/no/such/prelim/dir"}
    done = subprocess.run(
        [sys.executable, "-c", "import barks_fantagraphics.whoosh_search_engine"],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == 0, done.stderr


def test_a_stale_prelim_override_fails_when_the_prelim_dir_is_asked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _forget_prelim_dir(monkeypatch)
    monkeypatch.setenv(OCR_PRELIM_DIR_ENV_VAR, "/no/such/prelim/dir")
    with pytest.raises(NotADirectoryError, match=OCR_PRELIM_DIR_ENV_VAR):
        _ = ocr_file_paths.OCR_PRELIM_DIR


def test_the_prelim_dir_is_looked_up_once_then_kept(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _forget_prelim_dir(monkeypatch)
    monkeypatch.setenv(OCR_PRELIM_DIR_ENV_VAR, str(tmp_path))
    first = ocr_file_paths.OCR_PRELIM_DIR
    monkeypatch.delenv(OCR_PRELIM_DIR_ENV_VAR)
    second = ocr_file_paths.OCR_PRELIM_DIR
    assert (first, second) == (tmp_path, tmp_path)


def test_a_name_the_module_lacks_is_still_an_attribute_error() -> None:
    with pytest.raises(AttributeError, match="NO_SUCH_NAME"):
        getattr(ocr_file_paths, "NO_SUCH_NAME")  # noqa: B009
