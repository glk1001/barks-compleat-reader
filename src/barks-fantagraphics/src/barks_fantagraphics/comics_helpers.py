from barks_fantagraphics.barks_titles import get_safe_title
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.comics_utils import get_titles_sorted_by_submission_date
from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo


def get_titles_and_info(
    comics_database: ComicsDatabase, volumes: list[int], title: str, configured_only: bool = True
) -> list[tuple[str, FantaComicBookInfo]]:
    assert not (volumes and title)

    if title:
        fanta_info = comics_database.get_fanta_comic_book_info(title)
        return [(title, fanta_info)]

    assert volumes
    if configured_only:
        return comics_database.get_configured_titles_in_fantagraphics_volumes(volumes)

    return comics_database.get_all_titles_in_fantagraphics_volumes(volumes)


def get_titles(
    comics_database: ComicsDatabase,
    volumes: list[int],
    title: str,
    submission_date_sorted: bool = True,
    configured_only: bool = True,
) -> list[str]:
    titles_and_info = get_titles_and_info(comics_database, volumes, title, configured_only)

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
