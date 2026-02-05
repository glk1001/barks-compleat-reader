from pathlib import Path

from .comics_consts import BARKS_ROOT_DIR

OCR_ROOT_DIR = BARKS_ROOT_DIR / "Fantagraphics-restored-ocr"
OCR_ANNOTATIONS_DIR = OCR_ROOT_DIR / "Annotations"
OCR_FINAL_DIR = OCR_ROOT_DIR / "Final"
OCR_FIXES_DIR = OCR_ROOT_DIR / "Fixes"
OCR_FIXES_BACKUP_DIR = OCR_ROOT_DIR / "Fixes-bak"
OCR_PRELIM_DIR = OCR_ROOT_DIR / "Prelim"
OCR_RAW_DIR = OCR_ROOT_DIR / "Raw"

OCR_PROJECT_ROOT = BARKS_ROOT_DIR / "Projects" / "OCR"
BATCH_JOBS_DIR = OCR_PROJECT_ROOT / "batch-jobs"
UNPROCESSED_BATCH_JOBS_DIR = BATCH_JOBS_DIR / "unprocessed"
FINISHED_BATCH_JOBS_DIR = BATCH_JOBS_DIR / "finished"
BATCH_JOBS_OUTPUT_DIR = BATCH_JOBS_DIR / "output"


def get_batch_details_file(title: str) -> Path:
    return UNPROCESSED_BATCH_JOBS_DIR / f"{title}-batch-job-details.json"


def get_batch_requests_file(title: str) -> Path:
    return UNPROCESSED_BATCH_JOBS_DIR / f"{title}-batch-requests-with-image.json"


# TODO: Remove json from inside name
def get_ocr_predicted_groups_filename(fanta_page: str, ocr_type: str) -> str:
    return f"{fanta_page}-{ocr_type}-json-ocr-ai-predicted-groups.json"


def get_ocr_prelim_groups_json_filename(fanta_page: str, ocr_type: str) -> str:
    return fanta_page + f"-{ocr_type}-gemini-prelim-groups.json"


def get_ocr_prelim_annotated_filename(fanta_page: str, ocr_type: str) -> str:
    return fanta_page + f"-{ocr_type}-ocr-gemini-prelim-annotated.png"


def get_ocr_boxes_annotated_filename(fanta_page: str, ocr_type: str) -> str:
    return fanta_page + f"-{ocr_type}-ocr-gemini-boxes-annotated.png"


def get_ocr_final_groups_json_filename(fanta_page: str) -> str:
    return fanta_page + "-gemini-final-groups.json"


def get_ocr_final_annotated_filename(fanta_page: str) -> str:
    return fanta_page + "-ocr-gemini-final-annotated.png"
