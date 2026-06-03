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

from pathlib import Path  # noqa: TC003
from typing import Annotated

import typer
from cli_setup import init_logging
from comic_utils.common_typer_options import LogLevelArg  # noqa: TC002
from mosaic import make_mosaic

APP_LOGGING_NAME = "mosaic"


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
