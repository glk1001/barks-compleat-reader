from pathlib import Path

from .comics_database import ComicsDatabase
from .comics_utils import get_ocr_type
from .ocr_file_paths import (
    OCR_ANNOTATIONS_DIR,
    OCR_FINAL_DIR,
    OCR_PRELIM_DIR,
    get_ocr_boxes_annotated_filename,
    get_ocr_final_annotated_filename,
    get_ocr_final_groups_json_filename,
    get_ocr_prelim_annotated_filename,
    get_ocr_prelim_groups_json_filename,
)


class JsonFiles:
    def __init__(
        self,
        comics_database: ComicsDatabase,
        title: str,
    ) -> None:
        self.title = title
        self.volume = comics_database.get_fanta_volume_int(title)
        self.volume_dirname = comics_database.get_fantagraphics_volume_title(self.volume)
        self.title_prelim_results_dir = OCR_PRELIM_DIR / self.volume_dirname
        self.title_final_results_dir = OCR_FINAL_DIR / self.volume_dirname
        self.title_annotated_images_dir = OCR_ANNOTATIONS_DIR / self.volume_dirname

        self.page: str = ""
        self.ocr_file: tuple[Path, Path] | None = None
        self.ocr_type: list[str] = []
        self.ocr_prelim_groups_json_file: list[Path] = []
        self.ocr_final_groups_json_file: list[Path] = []
        self.ocr_prelim_groups_annotated_file: list[Path] = []
        self.ocr_final_groups_annotated_file: list[Path] = []
        self.ocr_boxes_annotated_file: list[Path] = []

    def set_ocr_file(self, ocr_file: tuple[Path, Path]) -> None:
        self.page = ocr_file[0].stem[:3]
        self.ocr_file = ocr_file

        self.ocr_type = []
        self.ocr_prelim_groups_json_file = []
        self.ocr_prelim_groups_annotated_file = []
        self.ocr_boxes_annotated_file = []

        for ocr_type_file in ocr_file:
            ocr_type = get_ocr_type(ocr_type_file)
            self.ocr_type.append(ocr_type)

            self.ocr_prelim_groups_json_file.append(
                self.title_prelim_results_dir
                / get_ocr_prelim_groups_json_filename(self.page, ocr_type)
            )
            self.ocr_final_groups_json_file.append(
                self.title_final_results_dir / get_ocr_final_groups_json_filename(self.page)
            )
            self.ocr_prelim_groups_annotated_file.append(
                self.title_annotated_images_dir
                / get_ocr_prelim_annotated_filename(self.page, ocr_type)
            )
            self.ocr_final_groups_annotated_file.append(
                self.title_annotated_images_dir / get_ocr_final_annotated_filename(self.page)
            )
            self.ocr_boxes_annotated_file.append(
                OCR_ANNOTATIONS_DIR
                / self.volume_dirname
                / get_ocr_boxes_annotated_filename(self.page, ocr_type)
            )
