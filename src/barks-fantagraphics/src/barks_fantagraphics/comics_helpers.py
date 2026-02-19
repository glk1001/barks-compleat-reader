from pathlib import Path

from PIL import Image, ImageDraw

from barks_fantagraphics.barks_titles import get_safe_title
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.comics_utils import get_titles_sorted_by_submission_date
from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
from barks_fantagraphics.pages import get_sorted_srce_and_dest_pages
from barks_fantagraphics.panel_boxes import PagePanelBoxes


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


def get_title_from_volume_page(
    comics_database: ComicsDatabase, volume: int, page: str
) -> tuple[str, int]:
    titles = comics_database.get_all_titles_in_fantagraphics_volumes([volume])

    found_title = ""
    found_page = -1
    for title in titles:
        comic_book = comics_database.get_comic_book(title[0])
        srce_and_dest_pages = get_sorted_srce_and_dest_pages(
            comic_book, get_full_paths=False, check_srce_page_timestamps=False
        )
        # noinspection PyUnresolvedReferences
        srce_pages = [Path(p.page_filename).stem for p in srce_and_dest_pages.srce_pages]
        if page in srce_pages:
            page_index = srce_pages.index(page)
            found_title = title[0]
            found_page = srce_and_dest_pages.dest_pages[page_index].page_num
            break

    return found_title, found_page


def draw_panel_bounds_on_image(
    image: Image.Image, page_panel_boxes: PagePanelBoxes, include_overall_bound: bool = True
) -> bool:
    draw = ImageDraw.Draw(image)
    for panel in page_panel_boxes.panel_boxes:
        draw.rectangle(panel.box, outline="green", width=10)

    if include_overall_bound:
        draw.rectangle(page_panel_boxes.overall_bounds.box, outline="red", width=2)

    return True
