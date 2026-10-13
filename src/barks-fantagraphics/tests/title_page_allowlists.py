"""The stories allowed a plain "by Carl Barks" byline, shared by the checks that question it.

Two checks ask whether a story's title page may say plain "by Carl Barks": the Misc
series check (``test_misc_series_ini``), for every story in that series, and the credits
check (``test_story_bylines``), for every story whose credits name another scriptwriter.
A story can fall under both, so the allowlist is one, here: reclassifying a story is one
edit, and the two checks cannot contradict each other.

Each check keeps the list honest for what it can see. The Misc check holds every entry
to a byline that is still plain; the credits check holds every entry to still being a
Misc story or still having credits that name another scriptwriter, so an entry neither
check needs is removed.
"""

from __future__ import annotations

from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from barks_fantagraphics.fanta_series_info import SERIES_MISC

# Keyed by enum, not by title string, so a retitling cannot leave a stale entry behind.
PLAIN_BYLINE_ALLOWED: dict[Titles, str] = {
    Titles.RIDDLE_OF_THE_RED_HAT_THE: (
        "Barks wrote and drew it; it's in the Misc series for featuring Mickey Mouse."
    ),
    Titles.CHRISTMAS_CHA_CHA_THE: "Barks drew it all and co-wrote the script with Bob Gregory.",
    Titles.VICTORY_GARDEN_THE: "Barks drew it all and revised the script he was given.",
}


def plain_byline_titles() -> dict[str, str]:
    """Return the titles allowed a plain "by" byline as display strings, mapped to the reason.

    Returns:
        Display title to the reason that title may keep a plain "by".

    """
    return {
        BARKS_TITLE_INFO[title].get_title_str(): reason
        for title, reason in PLAIN_BYLINE_ALLOWED.items()
    }


def misc_titles() -> list[str]:
    """Return the display titles of every story in the Fantagraphics 'Misc' series.

    Returns:
        The story titles, in ``ALL_FANTA_COMIC_BOOK_INFO`` order.

    """
    return [
        info.comic_book_info.get_title_str()
        for info in ALL_FANTA_COMIC_BOOK_INFO.values()
        if info.series_name == SERIES_MISC
    ]
