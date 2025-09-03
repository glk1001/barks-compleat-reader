# ruff: noqa: ERA001, INP001

from __future__ import annotations

import os
import sys
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

from barks_fantagraphics.comic_book import ComicBook, ModifiedType, get_page_str
from barks_fantagraphics.comics_cmd_args import CmdArgNames, CmdArgs
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.comics_utils import delete_all_files_in_directory
from barks_fantagraphics.fanta_comics_info import (
    FANTA_OVERRIDE_DIRECTORIES,
    FANTA_VOLUME_OVERRIDES_ROOT,
)
from barks_fantagraphics.pages import get_page_mod_type, get_sorted_srce_and_dest_pages
from comic_utils.comic_consts import JPG_FILE_EXT
from comic_utils.pil_image_utils import copy_file_to_jpg, downscale_jpg
from loguru import logger
from loguru_config import LoguruConfig
from PIL import Image

if TYPE_CHECKING:
    from barks_fantagraphics.page_classes import CleanPage

Image.MAX_IMAGE_PIXELS = None

APP_LOGGING_NAME = "wmod"

# TODO: Put these somewhere else
SRCE_STANDARD_WIDTH = 2175
SRCE_STANDARD_HEIGHT = 3000


class FileType(Enum):
    ORIGINAL = auto()
    UPSCAYLED = auto()
    TITLE = auto()


def get_srce_mod_files(comic: ComicBook) -> None | list[tuple[str, FileType]]:
    srce_and_dest_pages = get_sorted_srce_and_dest_pages(comic, get_full_paths=True)

    return [
        get_mod_file(comic, srce)
        for srce in srce_and_dest_pages.srce_pages
        if get_page_mod_type(comic, srce) != ModifiedType.ORIGINAL
    ]


def get_title_file(dest_pages: list[CleanPage]) -> tuple[str, FileType]:
    for page in dest_pages:
        if page.page_type == PageType.TITLE:
            return page.page_filename, FileType.TITLE

    raise AssertionError


def get_mod_file(comic: ComicBook, srce: CleanPage) -> tuple[str, FileType]:
    page_num = get_page_str(srce.page_num)

    if os.path.isfile(comic.get_srce_original_fixes_story_file(page_num)):
        return comic.get_srce_original_fixes_story_file(page_num), FileType.ORIGINAL
    if os.path.isfile(comic.get_srce_upscayled_fixes_story_file(page_num)):
        return comic.get_srce_upscayled_fixes_story_file(page_num), FileType.UPSCAYLED

    msg = f'Expected to find a fixes file for "{srce.page_filename}".'
    raise FileNotFoundError(msg)


def downscale(srce_file: str, dest_file: str) -> None:
    logger.info(f'Downscale "{srce_file}" to "{dest_file}"')
    downscale_jpg(SRCE_STANDARD_WIDTH, SRCE_STANDARD_HEIGHT, srce_file, dest_file)


def copy_file(srce_file: str, dest_file: str) -> None:
    logger.info(f'Copy "{srce_file}" to jpg "{dest_file}"...')
    copy_file_to_jpg(srce_file, dest_file)


if __name__ == "__main__":
    # TODO(glk): Some issue with type checking inspection?
    # noinspection PyTypeChecker
    cmd_args = CmdArgs(
        "Write Fantagraphics edited files to overrides directory",
        CmdArgNames.VOLUME,
    )
    args_ok, error_msg = cmd_args.args_are_valid()
    if not args_ok:
        logger.error(error_msg)
        sys.exit(1)

    # Global variable accessed by loguru-config.
    log_level = cmd_args.get_log_level()
    LoguruConfig.load(Path(__file__).parent / "log-config.yaml")

    comics_database = cmd_args.get_comics_database()

    volumes = [int(v) for v in cmd_args.get_volumes()]

    for volume in volumes:
        override_dir = FANTA_VOLUME_OVERRIDES_ROOT / FANTA_OVERRIDE_DIRECTORIES[volume]
        logger.info(f'Deleting all files in overrides directory "{override_dir}".')
        delete_all_files_in_directory(override_dir)

        titles = [
            t[0] for t in comics_database.get_configured_titles_in_fantagraphics_volume(volume)
        ]

        num_copied = 0
        for title in titles:
            comic_book = comics_database.get_comic_book(title)

            srce_mod_files = get_srce_mod_files(comic_book)
            if not srce_mod_files:
                continue

            for srce_mod_file in srce_mod_files:
                mod_file = srce_mod_file[0]
                file_type = srce_mod_file[1]

                mod_basename = Path(mod_file).stem + JPG_FILE_EXT
                override_file = override_dir / mod_basename

                if file_type == FileType.UPSCAYLED:
                    downscale(mod_file, override_file)
                elif file_type == FileType.ORIGINAL:
                    copy_file(mod_file, override_file)
                else:
                    err_msg = f'Wrong file type, {file_type}, for file "{mod_file}".'
                    raise ValueError(err_msg)
                    # assert file_type == FileType.TITLE
                    # override_file = os.path.join(override_dir, title + JPG_FILE_EXT)
                    # copy_file(mod_file, override_file)

                num_copied += 1

        logger.info(f"For volume {volume}, copied {num_copied} files.")
