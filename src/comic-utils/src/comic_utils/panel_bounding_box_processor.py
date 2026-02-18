import json
from pathlib import Path
from typing import Any

from loguru import logger
from PIL.Image import Image

from .comic_consts import JPG_FILE_EXT, PNG_FILE_EXT
from .panel_segmentation import KumikoPanelSegmentation, get_min_max_panel_values
from .pil_image_utils import load_pil_image_for_reading


class BoundingBoxProcessor:
    def __init__(
        self, work_dir: Path, comic_building_dir: Path, no_panel_expansion: bool = False
    ) -> None:
        self._kumiko = KumikoPanelSegmentation(work_dir, comic_building_dir, no_panel_expansion)

    def get_panels_segment_info_from_kumiko(
        self,
        srce_file: Path,
        srce_bounded_override_dir: Path,
    ) -> dict[str, Any]:
        logger.debug("Getting panels segment info from kumiko.")

        bounds_override_file, overall_bounds_override_file = self._get_bounds_override_files(
            srce_bounded_override_dir, srce_file
        )

        if not bounds_override_file.is_file():
            srce_bounded_image = load_pil_image_for_reading(srce_file)
        else:
            logger.warning(f'Using panels bounds override file "{bounds_override_file}".')
            srce_bounded_image = load_pil_image_for_reading(bounds_override_file)

        if not overall_bounds_override_file.is_file():
            srce_overall_bounded_image = None
        else:
            logger.warning(
                f'Using overall panels bounds override file "{overall_bounds_override_file}".'
            )
            srce_overall_bounded_image = load_pil_image_for_reading(overall_bounds_override_file)

        bounds_segment_info = self._get_segment_info(srce_bounded_image, srce_file)

        if srce_overall_bounded_image:
            overall_bounds_segment_info = self._get_segment_info(
                srce_overall_bounded_image, srce_file
            )
            bounds_segment_info["overall_bounds"] = overall_bounds_segment_info["overall_bounds"]

        return bounds_segment_info

    def _get_segment_info(self, srce_bounded_image: Image, srce_file: Path) -> dict[str, Any]:
        srce_bounded_image = srce_bounded_image.convert("RGB")

        segment_info = self._kumiko.get_panels_segment_info(srce_bounded_image, srce_file)

        segment_info["overall_bounds"] = get_min_max_panel_values(segment_info)

        return segment_info

    @staticmethod
    def _get_bounds_override_files(
        srce_bounded_override_dir: Path, srce_file: Path
    ) -> tuple[Path, Path]:
        bad_override_file = srce_bounded_override_dir / (srce_file.stem + PNG_FILE_EXT)
        if bad_override_file.is_file():
            msg = f'Override panels bounds files should not be .png: "{bad_override_file}".'
            raise RuntimeError(msg)

        bounds_override_file = srce_bounded_override_dir / (Path(srce_file).stem + JPG_FILE_EXT)
        overall_bounds_override_file = srce_bounded_override_dir / (
            Path(srce_file).stem + "-overall-bounds-only" + JPG_FILE_EXT
        )

        if overall_bounds_override_file.is_file() and not bounds_override_file.is_file():
            msg = (
                f'Cannot have an overall bounds file "{overall_bounds_override_file}"'
                f' AND NOT a bounds file "{bounds_override_file}".'
            )
            raise RuntimeError(msg)

        return bounds_override_file, overall_bounds_override_file

    @staticmethod
    def save_panels_segment_info(segment_info_filename: Path, segment_info: dict[str, Any]) -> None:
        logger.debug(f'Saving panel segment info to "{segment_info_filename}".')

        segment_info_filtered = {k: v for k, v in segment_info.items() if k != "processing_time"}
        with segment_info_filename.open("w") as f:
            json.dump(segment_info_filtered, f, indent=4)
