#!/usr/bin/env python

"""Create a grid mosaic from the inset images of a range of one-pagers.

The range is given as the ``--from``/``--to`` 1-based chronological numbers of the
*located* one-pagers (as returned by ``get_located_one_pagers``). Each selected
one-pager's inset file is looked up in the Insets directory; the mosaic is laid
out in that same chronological order.

Usage:
    uv run scripts/make_one_pager_mosaic.py \
        --output one_pagers.png --width 1920 --height 1080 \
        --from 1 --to 24 --columns 6 --gap 8 --background black
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import Annotated

import typer
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE
from barks_fantagraphics.comic_book_info import get_located_one_pagers
from barks_fantagraphics.comics_consts import PNG_INSET_DIR, PNG_INSET_EXT
from cli_setup import init_logging
from comic_utils.common_typer_options import LogLevelArg  # noqa: TC002
from loguru import logger
from mosaic import make_mosaic

APP_LOGGING_NAME = "mosaic"


def _get_one_pager_inset_files(from_num: int, to_num: int) -> list[Path]:
    """Return the inset files for located one-pagers ``from_num``..``to_num`` (1-based).

    Args:
        from_num: 1-based index of the first located one-pager (inclusive).
        to_num: 1-based index of the last located one-pager (inclusive).

    Returns:
        The inset file paths, in chronological order.

    Raises:
        typer.BadParameter: If the range is invalid for the located one-pagers.
        FileNotFoundError: If a selected one-pager has no inset file in the Insets directory.

    """
    located = get_located_one_pagers()
    num_located = len(located)

    if from_num < 1 or to_num < from_num or to_num > num_located:
        msg = (
            f"--from/--to range {from_num}..{to_num} is invalid for "
            f"{num_located} located one-pagers (expected 1 <= from <= to <= {num_located})."
        )
        raise typer.BadParameter(msg)

    selected = located[from_num - 1 : to_num]
    logger.info(f"Selected {len(selected)} located one-pagers (#{from_num}..#{to_num}).")

    inset_files: list[Path] = []
    missing: list[str] = []
    for title in selected:
        title_str = ENUM_TO_STR_TITLE[title]
        inset_file = PNG_INSET_DIR / f"{title_str}{PNG_INSET_EXT}"
        if not inset_file.is_file():
            missing.append(str(inset_file))
        inset_files.append(inset_file)

    if missing:
        missing_list = "\n  ".join(missing)
        msg = (
            f'{len(missing)} one-pager(s) in the range have no inset file in "{PNG_INSET_DIR}":'
            f"\n  {missing_list}"
        )
        raise FileNotFoundError(msg)

    return inset_files


def main(
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
    from_num: Annotated[
        int,
        typer.Option("--from", "-f", help="1-based chronological number of the first one-pager."),
    ],
    to_num: Annotated[
        int,
        typer.Option("--to", "-t", help="1-based chronological number of the last one-pager."),
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
    """Create a grid mosaic from the inset images of a range of one-pagers."""
    init_logging(APP_LOGGING_NAME, "make-one-pager-mosaic.log", log_level_str)

    if gap < 0:
        msg = f"--gap must be non-negative, got {gap}."
        raise typer.BadParameter(msg)

    inset_files = _get_one_pager_inset_files(from_num, to_num)

    make_mosaic(inset_files, output, width, height, columns, gap, background)


if __name__ == "__main__":
    typer.run(main)
