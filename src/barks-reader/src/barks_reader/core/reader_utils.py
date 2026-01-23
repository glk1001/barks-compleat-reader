from __future__ import annotations

import json
import re
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path
from random import randrange
from typing import TYPE_CHECKING, Any

from barks_fantagraphics.barks_titles import BARKS_TITLE_DICT, Titles
from barks_fantagraphics.comic_issues import Issues
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.fanta_comics_info import US_CENSORED_TITLE_ENUMS, FantaComicBookInfo
from comic_utils.comic_consts import ROMAN_NUMERALS
from comic_utils.pil_image_utils import PNG_PIL_FORMAT
from intspan import intspan

if TYPE_CHECKING:
    from barks_fantagraphics.pages import CleanPage
    from comic_utils.comic_consts import PanelPath

COMIC_PAGE_ASPECT_RATIO = 3200.0 / 2120.0

EMPTY_PAGE_KEY = "empty_page"
PNG_EXT_FOR_KIVY = PNG_PIL_FORMAT.lower()
ROMAN_NUMERALS_SET = set(ROMAN_NUMERALS.values())


def get_win_width_from_height(win_height: int) -> int:
    return round(win_height / COMIC_PAGE_ASPECT_RATIO)


def get_title_str_from_reader_icon_file(icon_path: Path) -> str:
    # Use a regular expression to split the stem at the beginning of the
    # trailing numeric suffix (e.g., "-1-1"). This correctly handles
    # titles that contain hyphens or other special characters.
    parts = re.split(r"(-\d+)+$", icon_path.stem)

    return parts[0]


def title_needs_footnote(fanta_info: FantaComicBookInfo) -> bool:
    return (
        (not fanta_info.comic_book_info.is_barks_title)
        and (fanta_info.comic_book_info.issue_name == Issues.CS)
        and (fanta_info.comic_book_info.title in US_CENSORED_TITLE_ENUMS)
    )


def prob_rand_less_equal(percent: int) -> bool:
    return randrange(1, 101) < percent


def get_rand_int(min_max: tuple[int, int]) -> int:
    return randrange(min_max[0], min_max[1] + 1)


def is_title_page(page: CleanPage) -> bool:
    return (Path(page.page_filename).stem == EMPTY_PAGE_KEY) and (page.page_type == PageType.TITLE)


def is_blank_page(page_filename: str, page_type: PageType) -> bool:
    return (Path(page_filename).stem == EMPTY_PAGE_KEY) and (page_type != PageType.TITLE)


def get_all_files_in_dir(dir_path: PanelPath, recurse: bool = False) -> list[PanelPath]:
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


def read_title_list(filepath: PanelPath) -> list[Titles]:
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


# Assumes 'original_list' and 'extra_list' have no duplicates.
def unique_extend(original_list: list[Titles], extras_list: list[Titles]) -> None:
    seen = set(original_list)

    original_list.extend([item for item in extras_list if item not in seen])


def get_paths_from_directory(root_path: Path) -> set[str]:
    """Recursively get all file paths relative to the root, without extensions.

    This function ignores empty directories.
    """
    paths = set()
    if not root_path.is_dir():
        return paths

    for path in root_path.rglob("*"):
        if path.is_file():
            # Normalize path separators and remove extension
            relative_path = path.relative_to(root_path)
            paths.add(str(relative_path.with_suffix("")).replace("\\", "/"))

    return paths


def get_paths_from_zip(zip_path: Path) -> set[str]:
    """Get all file paths from a zip archive, without extensions."""
    paths = set()
    if not zip_path.is_file():
        return paths

    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            # Ignore directory entries
            if not name.endswith("/"):
                path = Path(name)
                paths.add(str(path.with_suffix("")))

    return paths


def get_concat_page_nums_str(page_nums_str: list[str]) -> str:
    def get_abbrev_page_list(pg_list: list[str]) -> str:
        try:
            page_nums = [int(p) for p in pg_list]
        except ValueError as e:
            msg = f"Could not convert page nums list to list of ints: {pg_list}."
            raise ValueError(msg) from e
        else:
            return str(intspan(page_nums))

    page_set = set(page_nums_str)
    if page_set & ROMAN_NUMERALS_SET:
        roman_pages = sorted({p for p in page_nums_str if p in ROMAN_NUMERALS_SET})
        int_pages = get_abbrev_page_list([p for p in page_nums_str if p not in ROMAN_NUMERALS_SET])
        if int_pages:
            return ",".join(roman_pages) + "," + int_pages
        return ",".join(roman_pages)

    return get_abbrev_page_list(page_nums_str)


def quote_and_join_with_and(items: list[Any]) -> str:
    return join_with_and(get_quoted_items(items))


def get_quoted_items(items: list[Any]) -> list[str]:
    return [f'"{item}"' for item in items]


def join_with_and(items: list[Any]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return str(items[0])
    if len(items) == 2:  # noqa: PLR2004
        return f"{items[0]} and {items[1]}"

    # Join all but the last element with ', '.
    beginning = ", ".join(map(str, items[:-1]))
    return f"{beginning}, and {items[-1]}"


def get_centred_position_on_primary_monitor(win_width: int, win_height: int) -> tuple[int, int]:
    """Position window on primary monitor, centered."""
    import screeninfo  # noqa: PLC0415

    # noinspection PyBroadException
    try:
        monitors = screeninfo.get_monitors()
        primary = next((m for m in monitors if m.is_primary), monitors[0] if monitors else None)
        if primary:
            return (
                primary.x + (primary.width - win_width) // 2,
                primary.y + (primary.height - win_height) // 2,
            )

    except Exception:  # noqa: BLE001, S110
        pass

    return 100, 100


def safe_import_check(module_name: str, timeout: float = 5.0) -> bool:
    """Safely check if a Python module can be imported without crashing Python.

    This spawns a sandbox subprocess to avoid segfaults from obfuscated modules.

    Returns True if the import succeeded, False otherwise.
    """
    check_code = textwrap.dedent(f"""
    import importlib, json, sys
    try:
        importlib.import_module("{module_name}")
        print(json.dumps({{"ok": True}}))
    except Exception as e:
        print(json.dumps({{"ok": False, "err": str(e)}}))
        sys.exit(2)
    """)

    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", check_code],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    ok = False
    if proc.returncode == 0:
        # noinspection PyBroadException
        try:
            result = json.loads(proc.stdout.strip().splitlines()[-1])
            ok = result.get("ok", False)
        except Exception:  # noqa: BLE001, S110
            pass

    return ok
