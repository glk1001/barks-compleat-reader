"""The stories whose title page may read as wholly Barks's, shared by the checks that ask.

Two checks ask whether a story's title page may say plain "by Carl Barks": the Misc
series check (``test_misc_series_ini``), for every story in that series, and the credits
check (``test_story_bylines``), for every story whose credits name another scriptwriter.
A story can fall under both, so the allowlist is one, here: reclassifying a story is one
edit, and the two checks cannot contradict each other.

The Misc check also asks whether a story's ini must credit the other hand at all. A Misc
story that is wholly Barks's work, there for another reason, needs no such credit, and
for the same reason may keep the plain byline: ``ATTRIBUTION_NOT_REQUIRED`` says which,
and ``PLAIN_BYLINE_ALLOWED`` includes it, so that too is one edit.

Each check keeps the lists honest for what it can see. The Misc check holds every
plain-byline entry to a byline that is still plain, and every attribution exemption to
still being a Misc story whose ini names no credit; the credits check holds every
plain-byline entry to still being a Misc story or still having credits that name another
scriptwriter, so an entry neither check needs is removed.
"""

from __future__ import annotations

from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from barks_fantagraphics.fanta_series_info import SERIES_MISC

# Both lists are keyed by enum, not by title string, so a retitling cannot leave a stale
# entry behind.

# Misc stories that need no authorship credit in their ini: they are wholly Barks's work,
# in the Misc series for some other reason, so there is no other hand to record.
ATTRIBUTION_NOT_REQUIRED: dict[Titles, str] = {
    Titles.RIDDLE_OF_THE_RED_HAT_THE: (
        "Barks wrote and drew it; it's in the Misc series for featuring Mickey Mouse."
    ),
}

# Stories allowed a plain "by Carl Barks" byline: the wholly-Barks Misc stories above, and
# those where his part was the whole of the art and most of the script.
PLAIN_BYLINE_ALLOWED: dict[Titles, str] = {
    **ATTRIBUTION_NOT_REQUIRED,
    Titles.VICTORY_GARDEN_THE: (
        "Barks drew it all and revised the script (by Eleanor Packer or Dorothy Strebe)."
    ),
    Titles.TOO_MANY_PETS: "Barks drew it all and rewrote the script by Merrill De Maris.",
    Titles.CRAZY_QUIZ_SHOW_THE: "Barks drew it all and rewrote the script he was given.",
    Titles.PIZEN_SPRING_DUDE_RANCH: "Barks drew it all and rewrote the script he was given.",
    Titles.CHRISTMAS_CHA_CHA_THE: "Barks drew it all and co-wrote the script with Bob Gregory.",
    Titles.LEMONADE_FLING_THE: "Barks drew it all and probably rewrote the script he was given.",
    Titles.BOXED_IN: "Barks drew it all and rewrote the script he was given.",
    Titles.DUCK_LUCK: "Barks drew it all and rewrote the script he was given.",
}


def _as_display_titles(allowlist: dict[Titles, str]) -> dict[str, str]:
    return {BARKS_TITLE_INFO[title].get_title_str(): reason for title, reason in allowlist.items()}


def plain_byline_titles() -> dict[str, str]:
    """Return the titles allowed a plain "by" byline as display strings, mapped to the reason.

    Returns:
        Display title to the reason that title may keep a plain "by".

    """
    return _as_display_titles(PLAIN_BYLINE_ALLOWED)


def attribution_exempt_titles() -> dict[str, str]:
    """Return the Misc titles needing no authorship credit as display strings, with the reason.

    Returns:
        Display title to the reason that title's ini need name no other hand.

    """
    return _as_display_titles(ATTRIBUTION_NOT_REQUIRED)


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
