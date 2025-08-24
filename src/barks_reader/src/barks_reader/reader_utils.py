from pathlib import Path
from random import randrange

from barks_fantagraphics.barks_titles import BARKS_TITLE_DICT, Titles
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.pages import CleanPage

EMPTY_PAGE_KEY = "empty_page"


def prob_rand_less_equal(percent: int) -> bool:
    return randrange(1, 101) < percent


def get_rand_int(min_max: tuple[int, int]) -> int:
    return randrange(min_max[0], min_max[1] + 1)


def is_title_page(page: CleanPage) -> bool:
    return (Path(page.page_filename).stem == EMPTY_PAGE_KEY) and (page.page_type == PageType.TITLE)


def is_blank_page(page_filename: str, page_type: PageType) -> bool:
    return (Path(page_filename).stem == EMPTY_PAGE_KEY) and (page_type != PageType.TITLE)


def get_all_files_in_dir(dir_path: Path, recurse: bool = False) -> list[Path]:
    files = []
    for filename in dir_path.iterdir():
        filepath = dir_path / filename
        if filepath.is_file():
            files.append(filepath)
        elif recurse:
            files.extend(get_all_files_in_dir(filepath))

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
