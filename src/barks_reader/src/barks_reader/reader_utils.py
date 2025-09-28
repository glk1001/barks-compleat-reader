from __future__ import annotations

import io
from pathlib import Path
from random import randrange
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import BARKS_TITLE_DICT, Titles
from barks_fantagraphics.comics_consts import PageType
from comic_utils.pil_image_utils import PNG_PIL_FORMAT
from kivy.core.image import Image as CoreImage

if TYPE_CHECKING:
    import zipfile

    from barks_fantagraphics.pages import CleanPage

    from barks_reader.reader_consts_and_types import PanelPath

EMPTY_PAGE_KEY = "empty_page"
PNG_EXT_FOR_KIVY = PNG_PIL_FORMAT.lower()


def get_image_stream(file: PanelPath) -> io.BytesIO:
    if isinstance(file, Path):
        return CoreImage(str(file)).texture

    zip_bytes = file.read_bytes()
    image_stream = io.BytesIO(zip_bytes)
    image_stream.seek(0)
    return CoreImage(image_stream, ext=PNG_EXT_FOR_KIVY).texture


def prob_rand_less_equal(percent: int) -> bool:
    return randrange(1, 101) < percent


def get_rand_int(min_max: tuple[int, int]) -> int:
    return randrange(min_max[0], min_max[1] + 1)


def is_title_page(page: CleanPage) -> bool:
    return (Path(page.page_filename).stem == EMPTY_PAGE_KEY) and (page.page_type == PageType.TITLE)


def is_blank_page(page_filename: str, page_type: PageType) -> bool:
    return (Path(page_filename).stem == EMPTY_PAGE_KEY) and (page_type != PageType.TITLE)


def get_all_files_in_dir(dir_path: Path | zipfile.Path, recurse: bool = False) -> list[Path]:
    assert dir_path.is_dir()

    files = []
    for filename in dir_path.iterdir():
        if filename.is_file():
            files.append(filename)
        elif recurse:
            files.extend(get_all_files_in_dir(filename))

    return files


def read_text_paragraphs(filepath: Path) -> str:
    with filepath.open("r") as f:
        lines = f.readlines()

    text = ""
    for ln in lines:
        line = ln.rstrip(" ")
        if len(line) > 1 and line[-2] != "\\":
            line = line.replace("\n", " ")
        else:
            line = line.replace("\\", "")

        if len(line.strip()) == 0:
            line = "\n\n"

        text += line

    return text


def read_title_list(filepath: Path) -> list[Titles]:
    # Return the list of titles in 'filepath', in submission date order.

    with filepath.open("r") as f:
        lines = f.readlines()

    titles = []
    for line in lines:
        title_str = line.strip()
        if title_str not in BARKS_TITLE_DICT:
            msg = f'Unknown title "{title_str}" in favourites file "{filepath}".'
            raise RuntimeError(msg)
        titles.append(BARKS_TITLE_DICT[title_str])

    # Now sort these in enum order (which is guaranteed to be submission date order).
    return sorted(titles)


def get_range_str(year_range: tuple[int, int]) -> str:
    return f"{year_range[0]}-{year_range[1]}"


def get_cs_range_str_from_str(year_range_str: str) -> str:
    return f"CS-{year_range_str}"


def get_us_range_str_from_str(year_range_str: str) -> str:
    return f"US-{year_range_str}"


# Assumes 'original_list' and 'extra_list' have no duplicates.
def unique_extend(original_list: list[Titles], extras_list: list[Titles]) -> None:
    seen = set(original_list)

    original_list.extend([item for item in extras_list if item not in seen])
