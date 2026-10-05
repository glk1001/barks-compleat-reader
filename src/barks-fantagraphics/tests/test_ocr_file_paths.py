"""The OCR tree's batch-job files and per-page group files, named as barks-ocr expects."""

from __future__ import annotations

from barks_fantagraphics.ocr_file_paths import (
    UNPROCESSED_BATCH_JOBS_DIR,
    get_batch_details_file,
    get_batch_requests_file,
    get_ocr_predicted_groups_filename,
    get_ocr_prelim_groups_json_filename,
)


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
