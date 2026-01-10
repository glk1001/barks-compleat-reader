from __future__ import annotations

import io
import os
import zipfile
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from barks_fantagraphics.comic_book import ComicBook, ModifiedType, get_page_str
from barks_fantagraphics.comics_consts import FANTA_VOLUME_OVERRIDES_ROOT
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.fanta_comics_info import (
    FANTA_OVERRIDE_ZIPS,
    get_volume_page_resolution,
)
from barks_fantagraphics.pages import get_page_mod_type, get_sorted_srce_and_dest_pages
from comic_utils.comic_consts import JPG_FILE_EXT
from comic_utils.common_typer_options import LogLevelArg, VolumesArg  # noqa: TC002
from comic_utils.pil_image_utils import get_downscaled_jpg, get_pil_image_as_jpg_bytes
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from intspan import intspan
from loguru import logger
from loguru_config import LoguruConfig
from PIL import Image

if TYPE_CHECKING:
    from barks_fantagraphics.page_classes import CleanPage

load_dotenv(Path(__file__).parent.parent / ".env.runtime")

APP_LOGGING_NAME = "wmod"

Image.MAX_IMAGE_PIXELS = None
PANEL_KEY = os.environ["BARKS_ZIPS_KEY"]
FERNET = Fernet(PANEL_KEY)

app = typer.Typer()
log_level = ""


class FileType(Enum):
    ORIGINAL = auto()
    UPSCAYLED = auto()
    TITLE = auto()


def get_srce_mod_files(comic: ComicBook) -> list[tuple[Path, FileType]]:
    """Find all modified source files for a given comic book."""
    srce_and_dest_pages = get_sorted_srce_and_dest_pages(comic, get_full_paths=True)

    return [
        get_mod_file(comic, srce)
        for srce in srce_and_dest_pages.srce_pages
        if get_page_mod_type(comic, srce) != ModifiedType.ORIGINAL
    ]


def get_mod_file(comic: ComicBook, srce: CleanPage) -> tuple[Path, FileType]:
    page_num = get_page_str(srce.page_num)

    if comic.get_srce_original_fixes_story_file(page_num).is_file():
        return comic.get_srce_original_fixes_story_file(page_num), FileType.ORIGINAL
    if comic.get_srce_upscayled_fixes_story_file(page_num).is_file():
        return comic.get_srce_upscayled_fixes_story_file(page_num), FileType.UPSCAYLED

    msg = f'Expected to find a fixes file for "{srce.page_filename}".'
    raise FileNotFoundError(msg)


def downscale_and_zip(
    srce_file: Path,
    override_archive: zipfile.ZipFile,
    arcname: Path,
    res_width: int,
    res_height: int,
) -> None:
    arcname = arcname.with_suffix(JPG_FILE_EXT)

    logger.info(f'Downscale "{srce_file}" to "{arcname}" in zip...')

    resized_image = get_downscaled_jpg(res_width, res_height, srce_file)
    buffer = get_pil_image_as_jpg_bytes(resized_image)
    buffer = io.BytesIO(FERNET.encrypt(buffer.getvalue()))
    buffer.seek(0)

    override_archive.writestr(str(arcname), buffer.read())


def just_zip(srce_file: Path, override_archive: zipfile.ZipFile, arcname: Path) -> None:
    logger.debug(f'Zip "{srce_file}" to jpg "{arcname}" in zip...')
    with srce_file.open("rb") as f:
        original = f.read()

    buffer = io.BytesIO(FERNET.encrypt(original))
    buffer.seek(0)

    override_archive.writestr(str(arcname), buffer.read())


def process_comic_book(
    comic_book: ComicBook, override_archive: zipfile.ZipFile, res_width: int, res_height: int
) -> int:
    """Process a single comic book, copying or downscaling its modified files."""
    srce_mod_files = get_srce_mod_files(comic_book)
    if not srce_mod_files:
        return 0

    for mod_file, file_type in srce_mod_files:
        mod_arcname = Path(mod_file.name)

        if file_type == FileType.UPSCAYLED:
            downscale_and_zip(mod_file, override_archive, mod_arcname, res_width, res_height)
        elif file_type == FileType.ORIGINAL:
            just_zip(mod_file, override_archive, mod_arcname)
        else:
            err_msg = f'Wrong file type, {file_type}, for file "{mod_file}".'
            raise ValueError(err_msg)

    return len(srce_mod_files)


def process_volume(comics_database: ComicsDatabase, volume: int) -> None:
    """Process all comics in a given volume, preparing the override zip."""
    override_zip = FANTA_VOLUME_OVERRIDES_ROOT / Path(FANTA_OVERRIDE_ZIPS[volume])
    logger.info(f'Preparing overrides zip for volume {volume}: "{override_zip}"')

    logger.info("Deleting existing zip.")
    override_zip.unlink(missing_ok=True)

    res_width, res_height = get_volume_page_resolution(volume)

    titles = [t[0] for t in comics_database.get_configured_titles_in_fantagraphics_volume(volume)]

    with zipfile.ZipFile(override_zip, "w", compression=zipfile.ZIP_STORED) as override_archive:
        total_files_zipped = 0
        for title in titles:
            comic_book = comics_database.get_comic_book(title)
            total_files_zipped += process_comic_book(
                comic_book, override_archive, res_width, res_height
            )

    logger.success(f"Volume {volume}: Zipped a total of {total_files_zipped} modified files.")


def process_volumes(comics_database: ComicsDatabase, volumes_to_process: list[int]) -> None:
    for volume in volumes_to_process:
        process_volume(comics_database, volume)


@app.command(help="Write Fantagraphics edited files to overrides directory")
def main(volumes_str: VolumesArg = "", log_level_str: LogLevelArg = "DEBUG") -> None:
    volumes = list(intspan(volumes_str))

    # Global variable accessed by loguru-config.
    global log_level  # noqa: PLW0603
    log_level = log_level_str
    LoguruConfig.load(Path(__file__).parent / "log-config.yaml")

    process_volumes(ComicsDatabase(for_building_comics=True), volumes)


if __name__ == "__main__":
    app()
