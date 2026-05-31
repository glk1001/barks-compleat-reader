#!/usr/bin/env python

"""Create a grid mosaic image from a list of image files.

Each image is scaled and center-cropped to completely fill its grid cell
(crop-to-fill), so the mosaic has no gaps within cells. The grid is laid out
left-to-right, top-to-bottom in the order the files are given.

Usage:
    uv run scripts/make_mosaic.py \
        --output mosaic.png --width 1920 --height 1080 \
        img1.png img2.png img3.png ...

If ``--columns`` is omitted, a near-square column count is chosen automatically
from the number of images.
"""

from __future__ import annotations

import math
from pathlib import Path  # noqa: TC003
from typing import Annotated

import typer
from cli_setup import init_logging
from comic_utils.common_typer_options import LogLevelArg  # noqa: TC002
from comic_utils.pil_image_utils import load_pil_image_for_reading
from loguru import logger
from PIL import Image, ImageOps

APP_LOGGING_NAME = "mosaic"


def _grid_columns(num_images: int, columns: int | None) -> int:
    """Return the column count, falling back to a near-square layout."""
    if columns is not None:
        if columns < 1:
            msg = f"--columns must be at least 1, got {columns}."
            raise typer.BadParameter(msg)
        return min(columns, num_images)
    return max(1, math.ceil(math.sqrt(num_images)))


def _cell_box(index: int, columns: int, cell_w: int, cell_h: int, gap: int) -> tuple[int, int]:
    """Return the top-left ``(x, y)`` paste position for the cell at ``index``."""
    row, col = divmod(index, columns)
    x = gap + col * (cell_w + gap)
    y = gap + row * (cell_h + gap)
    return x, y


def make_mosaic(
    image_files: list[Path],
    output: Path,
    width: int,
    height: int,
    columns: int | None,
    gap: int,
    background: str,
) -> None:
    """Build the mosaic and save it to ``output``."""
    num_images = len(image_files)
    cols = _grid_columns(num_images, columns)
    rows = math.ceil(num_images / cols)
    logger.info(f"Laying out {num_images} images in a {rows}x{cols} (rows x cols) grid.")

    cell_w = (width - (cols + 1) * gap) // cols
    cell_h = (height - (rows + 1) * gap) // rows
    if cell_w < 1 or cell_h < 1:
        msg = (
            f"Output {width}x{height} with gap {gap} is too small for a "
            f"{rows}x{cols} grid (computed cell size {cell_w}x{cell_h})."
        )
        raise typer.BadParameter(msg)
    logger.info(f"Each cell is {cell_w}x{cell_h} pixels.")

    canvas = Image.new("RGB", (width, height), background)

    for index, image_file in enumerate(image_files):
        if not image_file.is_file():
            msg = f'Could not find image file "{image_file}".'
            raise FileNotFoundError(msg)
        logger.debug(f'Placing image {index + 1}/{num_images}: "{image_file}".')
        image = load_pil_image_for_reading(image_file).convert("RGB")
        cell = ImageOps.fit(image, (cell_w, cell_h), centering=(0.5, 0.5))
        canvas.paste(cell, _cell_box(index, cols, cell_w, cell_h, gap))

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    logger.success(f'Wrote {width}x{height} mosaic to "{output}".')


def main(
    image_files: Annotated[
        list[Path],
        typer.Argument(help="Image files to place in the mosaic, in order."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output mosaic image file."),
    ],
    width: Annotated[
        int,
        typer.Option("--width", "-w", help="Output image width in pixels."),
    ],
    height: Annotated[
        int,
        typer.Option("--height", "-h", help="Output image height in pixels."),
    ],
    columns: Annotated[
        int | None,
        typer.Option("--columns", "-c", help="Number of columns (default: near-square)."),
    ] = None,
    gap: Annotated[
        int,
        typer.Option("--gap", "-g", help="Gap in pixels between cells and the border."),
    ] = 0,
    background: Annotated[
        str,
        typer.Option("--background", "-b", help="Background/gap color (name or #hex)."),
    ] = "black",
    log_level_str: LogLevelArg = "INFO",
) -> None:
    """Create a grid mosaic image from a list of image files."""
    init_logging(APP_LOGGING_NAME, "make-mosaic.log", log_level_str)

    if not image_files:
        msg = "At least one image file is required."
        raise typer.BadParameter(msg)
    if gap < 0:
        msg = f"--gap must be non-negative, got {gap}."
        raise typer.BadParameter(msg)

    make_mosaic(image_files, output, width, height, columns, gap, background)


if __name__ == "__main__":
    typer.run(main)
