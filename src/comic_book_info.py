from dataclasses import dataclass
from typing import List, Tuple

from barks_fantagraphics.comics_database import ComicsDatabase


@dataclass
class ComicTitleInfo:
    chronological_number: int
    title: str
    issue_title: str
    filename: str


def get_all_comic_titles(
    comics_database: ComicsDatabase, titles: List[str]
) -> Tuple[List[ComicTitleInfo], str]:
    titles_with_issue_nums = []
    longest_title = ""

    for title in titles:
        comic_book = comics_database.get_comic_book(title)

        display_title = title if comic_book.is_barks_title() else f"({title})"

        if len(display_title) > len(longest_title):
            longest_title = display_title

        titles_with_issue_nums.append(
            ComicTitleInfo(
                comic_book.chronological_number,
                display_title,
                comic_book.get_comic_issue_title(),
                comic_book.get_title_with_issue_num(),
            )
        )

    return titles_with_issue_nums, longest_title
