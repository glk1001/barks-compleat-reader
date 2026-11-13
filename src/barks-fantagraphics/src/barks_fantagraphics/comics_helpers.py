from configparser import ConfigParser, ExtendedInterpolation
from pathlib import Path

import typer
from intspan import intspan
from loguru import logger
from PIL import Image, ImageDraw, ImageFont

from .barks_titles import ENUM_TO_STR_TITLE, STR_TITLE_TO_ENUM
from .comic_book import get_page_str
from .comic_book_info import (
    COVERS_SET,
    ONE_PAGER_LOCATIONS,
    ONE_PAGERS,
    get_one_pager_fanta_vol_and_page,
    get_title_str_from_filename,
)
from .comics_consts import PageType
from .comics_database import ComicsDatabase, TitleNotFoundError
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
    """Return the titles, with their info, of one title or of whole volumes.

    Args:
        comics_database: The database to look the titles up in.
        volumes: The Fantagraphics volumes to list; empty when ``title`` is given.
        title: A story title or a single-story issue ("FC 9"); empty when ``volumes``
            is given.
        configured_only: Whether to list only the volumes' titles that have an ini file.
        exclude_non_comics: Whether to leave the volumes' articles out.

    Returns:
        ``(story title, info)`` pairs. A title given as an issue comes back as the
        story's own title, so that it can be looked up as one.

    Raises:
        ValueError: If both or neither of ``volumes`` and ``title`` are given.
        TitleNotFoundError: If ``title`` is not a known title.

    """
    if volumes and title:
        msg = "Give volumes or a title, not both."
        raise ValueError(msg)

    if title:
        fanta_info = comics_database.get_fanta_comic_book_info(title)
        return [(fanta_info.comic_book_info.get_title_str(), fanta_info)]

    if not volumes:
        msg = "Give volumes or a title: neither was given."
        raise ValueError(msg)

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
    title = STR_TITLE_TO_ENUM[title_str]
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

    # The story's nth page is the nth BODY page, not the first one's number plus n - 1:
    # the BODY pages of "The Bill Collectors" are not in a row.
    page_index = int(page_num_str) - 1 if page_num_str else 0
    if not 0 <= page_index < len(valid_page_list):
        msg = f'Page {page_num_str} not valid for "{title_str}".'
        raise RuntimeError(msg)

    return volume, valid_page_list[page_index]


def get_title_from_volume_page(
    comics_database: ComicsDatabase, volume: int, page: str
) -> tuple[str, int]:
    # Is it a one-pager?
    try:
        page_num = int(page)
        for title, (vol, fanta_page, comic_page) in ONE_PAGER_LOCATIONS.items():
            if vol == volume and page_num == fanta_page:
                return ENUM_TO_STR_TITLE[title], comic_page
    except ValueError:
        pass

    titles = comics_database.get_all_titles_in_fantagraphics_volumes([volume])

    found_title = ""
    found_page = -1
    for title in titles:
        title_enum = STR_TITLE_TO_ENUM[title[0]]
        if title_enum in ONE_PAGERS:
            logger.debug(f'Skipping one-pager title "{title[0]}".')
            continue
        if title_enum in COVERS_SET:
            # Covers have no ini file, so 'get_comic_book' can't resolve them. They're
            # also excluded from RESTORABLE_PAGE_TYPES, so no page here can be a cover.
            logger.debug(f'Skipping cover title "{title[0]}".')
            continue
        comic_book = comics_database.get_comic_book(title[0])
        srce_and_dest_pages = get_sorted_srce_and_dest_pages(comic_book, get_full_paths=False)
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
        typer.BadParameter: If both or neither of volumes_str and title_str are provided,
            or if title_str is not a known title.

    """
    if volumes_str and title_str:
        msg = "Options --volume and --title are mutually exclusive."
        raise typer.BadParameter(msg)
    if not volumes_str and not title_str:
        msg = "One of the options --volume and --title is required."
        raise typer.BadParameter(msg)

    volumes = list(intspan(volumes_str))
    comics_database = ComicsDatabase()
    try:
        titles = get_titles(
            comics_database, volumes, title_str, exclude_non_comics=exclude_non_comics
        )
    except TitleNotFoundError as e:
        raise typer.BadParameter(str(e)) from e
    return comics_database, titles


def validate_ini_files_against_barks_titles() -> None:
    """Check every story's ini file is named after a title and agrees with it.

    Raises:
        ValueError: If an ini file is not named after a known title, or names another
            title inside.
        KeyError: If an ini file has no ``title`` key in its ``info`` section.

    """
    comics_database = ComicsDatabase()

    for file in comics_database.get_ini_filenames():
        ini_file = comics_database.get_story_titles_dir() / file
        # A parser per file: a shared one keeps the last file's values for a missing key.
        config = ConfigParser(interpolation=ExtendedInterpolation())
        config.read(ini_file, encoding="utf-8")

        story_title = get_title_str_from_filename(file)
        if story_title not in STR_TITLE_TO_ENUM:
            msg = f'Ini story title "{story_title}" not in STR_TITLE_TO_ENUM'
            raise ValueError(msg)

        title_in_ini = get_safe_title(config["info"]["title"])
        if title_in_ini not in ("", story_title):
            msg = f'Ini title "{title_in_ini}" != story title "{story_title}"'
            raise ValueError(msg)
