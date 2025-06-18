import logging
import os.path
import sys
from pathlib import Path
from typing import List

from barks_fantagraphics.comic_book import ComicBook
from barks_fantagraphics.comics_cmd_args import CmdArgs, CmdArgNames
from barks_fantagraphics.comics_consts import PageType, JPG_FILE_EXT
from barks_fantagraphics.comics_image_io import open_pil_image_for_reading, SAVE_JPG_COMPRESS_LEVEL
from barks_fantagraphics.comics_utils import setup_logging, get_abbrev_path
from file_paths import get_comic_inset_files_dir, get_comic_cover_files_dir


def export_reader_files_for_title(ttl: str) -> None:
    comic = comics_database.get_comic_book(ttl)
    ini_file = comic.ini_file

    # export_inset_file(ttl, comic.intro_inset_file)

    # export_page_files_to_title_dirs(ttl, comic, get_comic_splash_files_dir(), [PageType.SPLASH])
    export_page_files_as_title_files(ttl, comic, get_comic_cover_files_dir(), [PageType.COVER])


def export_inset_file(ttl: str, inset_file: str) -> None:
    dest_file = os.path.join(get_comic_inset_files_dir(), ttl + JPG_FILE_EXT)

    logging.info(f'Exporting "{get_abbrev_path(inset_file)}" to "{get_abbrev_path(dest_file)}".')

    copy_image_file(inset_file, dest_file)


def export_page_files_as_title_files(
    ttl: str, comic: ComicBook, dest_dir: str, page_types: List[PageType]
) -> None:
    pages = comic.get_final_srce_story_files(page_types)
    if len(pages) == 0:
        return

    assert len(pages) == 1

    os.makedirs(dest_dir, exist_ok=True)
    srce_file, is_modified = pages[0]
    dest_file = os.path.join(dest_dir, ttl + JPG_FILE_EXT)

    logging.info(
        f'Exporting {page_types} file "{get_abbrev_path(srce_file)}"'
        f' to "{get_abbrev_path(dest_file)}".'
    )

    copy_image_file(srce_file, dest_file)


def export_page_files_to_title_dirs(
    ttl: str, comic: ComicBook, dest_dir: str, page_types: List[PageType]
) -> None:
    pages = comic.get_final_srce_story_files(page_types)
    if len(pages) == 0:
        return

    ttl_dir = os.path.join(dest_dir, ttl)
    os.makedirs(ttl_dir, exist_ok=True)

    for srce_file, is_modified in pages:
        dest_file = os.path.join(ttl_dir, Path(srce_file).stem + JPG_FILE_EXT)

        logging.info(
            f'Exporting {page_types} file "{get_abbrev_path(srce_file)}"'
            f' to "{get_abbrev_path(dest_file)}".'
        )

        copy_image_file(srce_file, dest_file)


def copy_image_file(srce: str, dest: str) -> None:
    image = open_pil_image_for_reading(srce).convert("RGB")

    image.save(
        dest,
        optimize=True,
        compress_level=SAVE_JPG_COMPRESS_LEVEL,
        quality=90,
    )


cmd_args = CmdArgs("Export reader files", CmdArgNames.VOLUME)
args_ok, error_msg = cmd_args.args_are_valid()
if not args_ok:
    logging.error(error_msg)
    sys.exit(1)

setup_logging(cmd_args.get_log_level())

comics_database = cmd_args.get_comics_database()

for title in cmd_args.get_titles():
    export_reader_files_for_title(title)
