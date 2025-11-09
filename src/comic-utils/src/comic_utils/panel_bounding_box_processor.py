import json
from pathlib import Path
from typing import Any

from loguru import logger

from .comic_consts import JPG_FILE_EXT, PNG_FILE_EXT
from .panel_segmentation import KumikoPanelSegmentation, get_min_max_panel_values
from .pil_image_utils import load_pil_image_for_reading


class BoundingBoxProcessor:
    def __init__(self, work_dir: Path, no_panel_expansion: bool = False) -> None:
        self._kumiko = KumikoPanelSegmentation(work_dir, no_panel_expansion)

    def get_panels_segment_info_from_kumiko(
        self,
        srce_file: Path,
        srce_bounded_override_dir: Path,
    ) -> dict[str, Any]:
        logger.debug("Getting panels segment info from kumiko.")

        override_file_with_bbox = self._get_override_filename(srce_bounded_override_dir, srce_file)

        if not override_file_with_bbox.is_file():
            srce_bounded_image = load_pil_image_for_reading(srce_file)
        else:
            logger.warning(f'Using panels bounds override file "{override_file_with_bbox}".')
            srce_bounded_image = load_pil_image_for_reading(override_file_with_bbox)

        srce_bounded_image = srce_bounded_image.convert("RGB")

        segment_info = self._kumiko.get_panels_segment_info(srce_bounded_image, srce_file)

        segment_info["overall_bounds"] = get_min_max_panel_values(segment_info)

        return segment_info

    @staticmethod
    def _get_override_filename(srce_bounded_override_dir: Path, srce_filename: Path) -> Path:
        bad_override_filename = srce_filename.stem + PNG_FILE_EXT
        bad_override_file = srce_bounded_override_dir / bad_override_filename
        if bad_override_file.is_file():
            msg = f'Override panels bounds files should not be .png: "{bad_override_file}".'
            raise RuntimeError(msg)

        override_filename = Path(srce_filename).stem + JPG_FILE_EXT
        return srce_bounded_override_dir / override_filename

    @staticmethod
    def save_panels_segment_info(segment_info_filename: Path, segment_info: dict[str, Any]) -> None:
        logger.debug(f'Saving panel segment info to "{segment_info_filename}".')

        segment_info_filtered = {k: v for k, v in segment_info.items() if k != "processing_time"}
        with segment_info_filename.open("w") as f:
            json.dump(segment_info_filtered, f, indent=4)
