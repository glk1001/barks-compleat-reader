from configparser import ConfigParser, ExtendedInterpolation
from pathlib import Path

import typer
from intspan import intspan
from PIL import Image, ImageDraw, ImageFont

from .barks_titles import BARKS_TITLES
from .comic_book import get_page_str
from .comic_book_info import (
    BARKS_TITLE_DICT,
    ONE_PAGER_LOCATIONS,
    ONE_PAGERS,
    get_one_pager_fanta_vol_and_page,
    get_title_str_from_filename,
)
from .comics_consts import PageType
from .comics_database import ComicsDatabase
from .comics_utils import get_safe_title, get_titles_sorted_by_submission_date
from .fanta_comics_info import FantaComicBookInfo
from .pages import get_sorted_srce_and_dest_pages
from .panel_boxes import PagePanelBoxes


def get_titles_and_info(
    comics_database: ComicsDatabase,
    volumes: list[int],
    title: str,
    configured_only: bool = True,
    exclude_non_comics: bool = False,
) -> list[tuple[str, FantaComicBookInfo]]:
    assert not (volumes and title)

    if title:
        fanta_info = comics_database.get_fanta_comic_book_info(title)
        return [(title, fanta_info)]

    assert volumes
    if configured_only:
        return comics_database.get_configured_titles_in_fantagraphics_volumes(
            volumes, exclude_non_comics
        )

    return comics_database.get_all_titles_in_fantagraphics_volumes(volumes)


def get_titles(
    comics_database: ComicsDatabase,
    volumes: list[int],
    title: str,
    submission_date_sorted: bool = True,
    configured_only: bool = True,
    exclude_non_comics: bool = False,
) -> list[str]:
    titles_and_info = get_titles_and_info(
        comics_database, volumes, title, configured_only, exclude_non_comics
    )

    if submission_date_sorted:
        return get_titles_sorted_by_submission_date(titles_and_info)

    return [t[0] for t in titles_and_info]


def get_issue_titles(
    comics_database: ComicsDatabase,
    title_info_list: list[tuple[str, FantaComicBookInfo]],
) -> list[tuple[str, str, FantaComicBookInfo, bool]]:
    comic_issue_title_info_list = []
    for title_info in title_info_list:
        ttl = title_info[0]
        cb_info = title_info[1]
        title_is_configured, _ = comics_database.is_story_title(ttl)
        comic_issue_title = cb_info.get_short_issue_title()
        comic_issue_title_info_list.append(
            (ttl, comic_issue_title, title_info[1], title_is_configured)
        )

    return comic_issue_title_info_list


def get_display_title(comics_database: ComicsDatabase, ttl: str) -> str:
    title_is_configured, _ = comics_database.is_story_title(ttl)
    if not title_is_configured:
        disp_title = ttl
    else:
        fanta_info = comics_database.get_fanta_comic_book_info(ttl)
        disp_title = ttl if fanta_info.comic_book_info.is_barks_title else f"({ttl})"

    return disp_title


def get_issue_title(comics_database: ComicsDatabase, ttl: str) -> str:
    title_is_configured, _ = comics_database.is_story_title(ttl)
    if not title_is_configured:
        comic_issue_title = ttl
    else:
        comic = comics_database.get_comic_book(ttl)
        comic_issue_title = get_safe_title(comic.get_comic_issue_title())

    return comic_issue_title


def get_volume_and_page(
    comics_database: ComicsDatabase, title_str: str, page_num_str: str
) -> tuple[int, str]:
    title = BARKS_TITLE_DICT[title_str]
    if title in ONE_PAGERS:
        volume, page = get_one_pager_fanta_vol_and_page(title)
        if volume is None or page is None:
            msg = f'Could not find one-pager\'s volume and page for "{title_str}".'
            raise RuntimeError(msg)
        return volume, get_page_str(page)

    comic = comics_database.get_comic_book(title_str)
    volume = comic.get_fanta_volume()
    valid_page_list = [
        p.page_filenames for p in comic.page_images_in_order if p.page_type == PageType.BODY
    ]

    first_page = int(valid_page_list[0])
    page = first_page if not page_num_str else first_page + int(page_num_str) - 1
    page = get_page_str(page)

    if page not in valid_page_list:
        msg = f'Page {page_num_str} not valid for "{title_str}".'
        raise RuntimeError(msg)

    return volume, page


def get_title_from_volume_page(
    comics_database: ComicsDatabase, volume: int, page: str
) -> tuple[str, int]:
    # Is it a one-pager?
    try:
        page_num = int(page)
        for title, (vol, fanta_page, comic_page) in ONE_PAGER_LOCATIONS.items():
            if vol == volume and page_num == fanta_page:
                return BARKS_TITLES[title], comic_page
    except ValueError:
        pass

    titles = comics_database.get_all_titles_in_fantagraphics_volumes([volume])

    found_title = ""
    found_page = -1
    for title in titles:
        comic_book = comics_database.get_comic_book(title[0])
        srce_and_dest_pages = get_sorted_srce_and_dest_pages(
            comic_book, get_full_paths=False, check_srce_page_timestamps=False
        )
        srce_pages = [Path(p.page_filename).stem for p in srce_and_dest_pages.srce_pages]
        if page in srce_pages:
            page_index = srce_pages.index(page)
            found_title = title[0]
            found_page = srce_and_dest_pages.dest_pages[page_index].page_num
            break

    return found_title, found_page


def draw_panel_bounds_on_image(
    image: Image.Image,
    page_panel_boxes: PagePanelBoxes,
    bounds_color: tuple[int, int, int, int] = (0, 128, 0, 255),
    include_overall_bound: bool = True,
) -> bool:
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=80)
    for panel in page_panel_boxes.panel_boxes:
        draw.rectangle(panel.box, outline=bounds_color, width=10)
        draw.text((panel.x1 - 80, panel.y0 + 20), str(panel.panel_num), fill="red", font=font)

    if include_overall_bound:
        draw.rectangle(page_panel_boxes.overall_bounds.box, outline="red", width=2)

    return True


def get_comic_titles(
    volumes_str: str, title_str: str, exclude_non_comics: bool = False
) -> tuple[ComicsDatabase, list[str]]:
    """Validate volume/title mutual exclusivity, parse args, and return database + titles.

    Raises:
        typer.BadParameter: If both volumes_str and title_str are provided.

    """
    if volumes_str and title_str:
        msg = "Options --volume and --title are mutually exclusive."
        raise typer.BadParameter(msg)

    volumes = list(intspan(volumes_str))
    comics_database = ComicsDatabase()
    titles = get_titles(comics_database, volumes, title_str, exclude_non_comics=exclude_non_comics)
    return comics_database, titles


def validate_ini_files_against_barks_titles() -> None:
    comics_database = ComicsDatabase()
    config = ConfigParser(interpolation=ExtendedInterpolation())

    for file in comics_database._ini_files:  # noqa: SLF001
        ini_file = comics_database.get_story_titles_dir() / file
        config.read(ini_file)

        story_title = get_title_str_from_filename(file)
        if story_title not in BARKS_TITLE_DICT:
            msg = f'Ini story title "{story_title}" not in BARKS_TITLE_DICT'
            raise ValueError(msg)

        title_in_ini = get_safe_title(config["info"]["title"])
        if title_in_ini not in ("", story_title):
            msg = f'Ini title "{title_in_ini}" != story title "{story_title}"'
            raise ValueError(msg)
