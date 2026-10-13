"""A story whose credits name another scriptwriter must not be bylined "by Carl Barks".

A title page's byline is plain "by" unless the story's ini names Barks's part in
``byline`` ("art by", "story by" and the like). The credits are in the ini's
``extra_pub_info``, so the two can disagree: a story another wrote, still bylined as if
Barks had done it all. The Misc series check catches that for Misc stories; this one
catches it wherever the credits say so, Misc or not.
"""

from __future__ import annotations

import re

import pytest
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.comic_book import INTRO_DEFAULT_BYLINE
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO, NON_COMIC_TITLES, SYNTHETIC_TITLES
from barks_fantagraphics.comics_database import ComicsDatabase

# A credit naming another scriptwriter: "Script not by Barks", "Script by Vic Lockman",
# "Script: Bob Karp", or "script and finished art by Don Rosa"; but not "Script and layout
# by Carl Barks", nor "script by Carl Barks".
_OTHER_SCRIPT_RE = re.compile(
    r"\bscript not by barks\b|\bscript(?: and [a-z ]+?)?(?: by|:)\s+(?!(?:carl\s+)?barks\b)",
    re.IGNORECASE,
)

# Stories whose credits name another scriptwriter but whose title page may still say
# plain "by Carl Barks", mapped to the reason why.
_PLAIN_BYLINE_ALLOWED: dict[Titles, str] = {
    Titles.CHRISTMAS_CHA_CHA_THE: "Barks drew it all and co-wrote the script with Bob Gregory.",
    Titles.VICTORY_GARDEN_THE: "Barks drew it all and revised the script he was given.",
}

# The essays and the collections have no title page.
_NO_TITLE_PAGE = {ENUM_TO_STR_TITLE[title] for title in [*NON_COMIC_TITLES, *SYNTHETIC_TITLES]}


def _plain_byline_titles() -> dict[str, str]:
    return {
        BARKS_TITLE_INFO[title].get_title_str(): reason
        for title, reason in _PLAIN_BYLINE_ALLOWED.items()
    }


@pytest.fixture(scope="module")
def other_script_bylines() -> dict[str, str]:
    """Each story whose credits name another scriptwriter, mapped to its byline."""
    db = ComicsDatabase(for_building_comics=False)
    bylines = {}
    for title in db.get_all_story_titles():
        if title in _NO_TITLE_PAGE:
            continue
        comic = db.get_comic_book(title)
        if _OTHER_SCRIPT_RE.search(comic.extra_pub_info):
            bylines[title] = comic.byline
    return bylines


class TestTheCreditPattern:
    @pytest.mark.parametrize(
        "credit",
        [
            "Script not by Barks",
            "Script by Vic Lockman",
            "Script by Bob Gregory and Barks",
            "Script: Bob Karp\nArt: Carl Barks (pages 1, 2, 5, 12-40)",
            "Pages 1-3, script by Carl Barks\nPages 4-8 script and finished art by Don Rosa",
        ],
    )
    def test_a_credit_naming_another_scriptwriter_is_found(self, credit: str) -> None:
        assert _OTHER_SCRIPT_RE.search(credit)

    @pytest.mark.parametrize(
        "credit",
        [
            "Script and layout by Carl Barks\nPencils and inks by Daan Jippes",
            "Pages 1-3, script by Carl Barks",
            "New opening half-page written by David Gerstein",
            "Original dialogue on page 4 restored by GLK, Aug 2025",
        ],
    )
    def test_a_credit_naming_no_other_scriptwriter_is_not(self, credit: str) -> None:
        assert not _OTHER_SCRIPT_RE.search(credit)


class TestEveryStoryByline:
    def test_the_stories_are_found(self, other_script_bylines: dict[str, str]) -> None:
        # Guards the check below: with no stories it would pass vacuously.
        assert len(other_script_bylines) > 30  # noqa: PLR2004

    def test_another_scriptwriters_story_names_his_part(
        self, other_script_bylines: dict[str, str]
    ) -> None:
        allowed = _plain_byline_titles()
        problems = [
            title
            for title, byline in other_script_bylines.items()
            if byline == INTRO_DEFAULT_BYLINE and title not in allowed
        ]

        assert not problems, (
            "These stories' credits name another scriptwriter, but their title page says"
            ' plain "by Carl Barks". Name his part in the ini, e.g. "byline = art by", or'
            " add the story to _PLAIN_BYLINE_ALLOWED with a reason:\n" + "\n".join(problems)
        )

    @pytest.mark.parametrize("title", _plain_byline_titles())
    def test_an_allowed_plain_byline_still_needs_allowing(
        self, other_script_bylines: dict[str, str], title: str
    ) -> None:
        assert other_script_bylines.get(title) == INTRO_DEFAULT_BYLINE, (
            f'"{title}" is allowed a plain byline, but its credits no longer name another'
            " scriptwriter, or its ini now names Barks's part. Remove it from"
            " _PLAIN_BYLINE_ALLOWED."
        )
