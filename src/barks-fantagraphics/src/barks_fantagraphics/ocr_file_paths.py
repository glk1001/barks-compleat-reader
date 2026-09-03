import os
from pathlib import Path

from .comics_consts import BARKS_ROOT_DIR

OCR_ROOT_DIR = BARKS_ROOT_DIR / "Fantagraphics-restored-ocr"
OCR_ANNOTATIONS_DIR = OCR_ROOT_DIR / "Annotations"
OCR_FINAL_DIR = OCR_ROOT_DIR / "Final"
OCR_FIXES_DIR = OCR_ROOT_DIR / "Fixes"
OCR_FIXES_BACKUP_DIR = OCR_ROOT_DIR / "Fixes-bak"

# Set this to point every tool at a different checkout of the prelim repo -- a git work
# tree, say, so that hand edits stay out of the tree another session is working
# in. Only the prelim root moves: images, annotations and backups stay where they are.
OCR_PRELIM_DIR_ENV_VAR = "BARKS_OCR_PRELIM_DIR"


def get_ocr_prelim_dir(ocr_root_dir: Path = OCR_ROOT_DIR) -> Path:
    """Return the prelim OCR root, honouring the ``BARKS_OCR_PRELIM_DIR`` override.

    Args:
        ocr_root_dir: The restored-OCR root the default prelim dir sits under.

    Returns:
        The override path when the variable is set, else ``ocr_root_dir / "Prelim"``.

    Raises:
        NotADirectoryError: If the override is set but does not name a directory.
            Failing here beats every page silently reporting as a missing prelim.

    """
    override = os.environ.get(OCR_PRELIM_DIR_ENV_VAR)
    if not override:
        return ocr_root_dir / "Prelim"

    prelim_dir = Path(override).expanduser()
    if not prelim_dir.is_dir():
        msg = f'{OCR_PRELIM_DIR_ENV_VAR} is set but is not a directory: "{prelim_dir}".'
        raise NotADirectoryError(msg)

    return prelim_dir


OCR_PRELIM_DIR = get_ocr_prelim_dir()
OCR_PRELIM_BACKUP_DIR = OCR_ROOT_DIR / "Prelim-backups"
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


# TODO: Remove JSON from inside name
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
