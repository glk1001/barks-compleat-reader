import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger
from PIL.Image import Image as PilImage

BIG_NUM = 10000


@dataclass
class KumikoBound:
    left: int
    top: int
    width: int
    height: int


def get_kumiko_panel_bound(raw_bound: tuple[int, int, int, int]) -> KumikoBound:
    return KumikoBound(raw_bound[0], raw_bound[1], raw_bound[2], raw_bound[3])


def get_min_max_panel_values(segment_info: dict[str, Any]) -> tuple[int, int, int, int]:
    x_min = BIG_NUM
    y_min = BIG_NUM
    x_max = 0
    y_max = 0

    for raw_kumiko_bound in segment_info["panels"]:
        kumiko_bound = get_kumiko_panel_bound(raw_kumiko_bound)

        assert kumiko_bound.left >= 0
        assert kumiko_bound.top >= 0
        assert kumiko_bound.width > 0
        assert kumiko_bound.height > 0

        x0 = kumiko_bound.left
        y0 = kumiko_bound.top
        x1 = x0 + (kumiko_bound.width - 1)
        y1 = y0 + (kumiko_bound.height - 1)

        x_min = min(x_min, x0)
        y_min = min(y_min, y0)
        x_max = max(x_max, x1)
        y_max = max(y_max, y1)

    assert x_min != BIG_NUM
    assert y_min != BIG_NUM
    assert x_max != 0
    assert y_max != 0

    return x_min, y_min, x_max, y_max


class KumikoPanelSegmentation:
    def __init__(self, work_dir: str, no_panel_expansion: bool = False) -> None:
        self._work_dir = work_dir
        self._no_panel_expansion = no_panel_expansion

    def get_panels_segment_info(self, srce_image: PilImage, srce_filename: str) -> dict[str, Any]:
        logger.debug(f'Getting panel bounding box for "{srce_filename}" using kumiko.')

        work_filename = str(
            os.path.join(
                self._work_dir,
                os.path.splitext(os.path.basename(srce_filename))[0] + "_orig.jpg",
            ),
        )
        srce_image.save(work_filename, optimize=True, compress_level=9)
        logger.debug(f'Saved srce image to work file "{work_filename}".')

        logger.debug(f'Getting segment info for "{work_filename}".')
        return self._run_kumiko(work_filename)

    def _run_kumiko(self, page_filename: str) -> dict[str, Any]:
        kumiko_home_dir = os.path.join(str(Path.home()), "Prj/github/kumiko")
        kumiko_python_path = os.path.join(kumiko_home_dir, ".venv/bin/python3")
        kumiko_script_path = os.path.join(kumiko_home_dir, "kumiko")
        run_args = [kumiko_python_path, kumiko_script_path, "-i", page_filename]
        if self._no_panel_expansion:
            run_args.append("--no-panel-expansion")
        logger.debug(f"Running kumiko: {' '.join(run_args)}.")
        result = subprocess.run(
            run_args,
            capture_output=True,
            text=True,
            check=True,
        )

        segment_info = json.loads(result.stdout)
        assert len(segment_info) == 1

        return segment_info[0]
