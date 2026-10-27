"""Integrity checks for the story-title ini files of the Fantagraphics 'Misc' series.

Titles in the 'Misc' series are the Barks-adjacent stories where Barks was not the sole
author: someone else wrote the script, or Barks scripted but someone else drew it. That
fact reaches the reader only through the ``extra_pub_info`` key in the story's ini file,
which ``ComicBook.__post_init__`` appends to the title page publication blurb. Nothing
else ties series membership (``fanta_series_data.py``) to the ini files, so these tests
enforce the link.

Note the implication only runs one way: a non-Misc title may legitimately carry an
attribution too (restoration credits, guest artists), so the converse is not asserted.

The title page's byline must agree: a Misc story is not "by Carl Barks" outright, so its
ini must name his part in ``byline`` ("art by", "story by" and the like).
"""

from __future__ import annotations

from configparser import ConfigParser, ExtendedInterpolation
from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics.comic_book import INTRO_DEFAULT_BYLINE
from barks_fantagraphics.fanta_series_info import SERIES_MISC
from story_credits import read_credits
from title_page_allowlists import attribution_exempt_titles, misc_titles, plain_byline_titles

if TYPE_CHECKING:
    from barks_fantagraphics.comics_database import ComicsDatabase

# An attribution names who did the script and/or the art, in any of the wordings
# story_credits.py reads: from a bare 'Script not by Barks', through 'Script by Vic
# Lockman', to the Daan Jippes titles' script-and-layout and pencils-and-inks credits and
# the per-page breakdowns of Pirate Gold and The Pied Piper of Duckburg. A restoration-only
# note (dialogue restored by GLK, and so on) is deliberately not enough.
_EXAMPLE_ATTRIBUTION = "extra_pub_info = Script not by Barks"


def _misc_titles_needing_attribution() -> list[str]:
    """Return the Misc titles whose ini file must carry an authorship credit.

    Returns:
        The story titles of ``misc_titles`` less those in ``ATTRIBUTION_NOT_REQUIRED``.

    """
    exempt = attribution_exempt_titles()
    return [title for title in misc_titles() if title not in exempt]


def _get_extra_pub_info(db: ComicsDatabase, story_title: str) -> str:
    """Return the ``extra_pub_info`` value from a story's ini file.

    Args:
        db: The comics database used to locate the ini file.
        story_title: The story title to look up.

    Returns:
        The ``extra_pub_info`` value, or an empty string if the key is absent.

    """
    ini_file = db.get_ini_file(story_title)
    assert ini_file.is_file(), f'{SERIES_MISC} title "{story_title}" has no ini file: "{ini_file}".'

    config = ConfigParser(interpolation=ExtendedInterpolation())
    config.read(ini_file)

    return config["info"].get("extra_pub_info", "")


class TestMiscSeriesAttribution:
    def test_misc_series_is_not_empty(self) -> None:
        # Guards the parametrize source below: if this ever returns nothing, the
        # per-title tests would silently collect zero cases and pass vacuously.
        assert misc_titles(), f'No titles found for the "{SERIES_MISC}" series.'

    @pytest.mark.parametrize("story_title", _misc_titles_needing_attribution())
    def test_misc_title_ini_declares_authorship(self, db: ComicsDatabase, story_title: str) -> None:
        extra_pub_info = _get_extra_pub_info(db, story_title)

        assert extra_pub_info, (
            f'{SERIES_MISC} title "{story_title}" has no "extra_pub_info" in its ini file.'
            f" Stories in the {SERIES_MISC} series were not solely authored by Barks, so the"
            f' ini file must say who wrote or drew them, e.g. "{_EXAMPLE_ATTRIBUTION}".'
            f" If this title is an exception, add it to ATTRIBUTION_NOT_REQUIRED in"
            f" title_page_allowlists.py with a reason."
        )

        assert read_credits(extra_pub_info).any, (
            f'{SERIES_MISC} title "{story_title}" has an "extra_pub_info" that names no script'
            f" or art credit: {extra_pub_info!r}. Add the actual credit, or failing that a"
            f' line like "{_EXAMPLE_ATTRIBUTION}".'
        )


class TestAttributionExemptions:
    """Keep ``ATTRIBUTION_NOT_REQUIRED`` honest, so an exemption cannot quietly rot."""

    @pytest.mark.parametrize("story_title", attribution_exempt_titles())
    def test_exempt_title_is_still_in_misc_series(self, story_title: str) -> None:
        assert story_title in misc_titles(), (
            f'"{story_title}" is exempt from the {SERIES_MISC} authorship check but is no'
            f" longer in the {SERIES_MISC} series. Remove it from ATTRIBUTION_NOT_REQUIRED"
            f" in title_page_allowlists.py."
        )

    @pytest.mark.parametrize("story_title", attribution_exempt_titles())
    def test_exempt_title_still_has_no_attribution(
        self, db: ComicsDatabase, story_title: str
    ) -> None:
        extra_pub_info = _get_extra_pub_info(db, story_title)

        assert not read_credits(extra_pub_info).any, (
            f'"{story_title}" is exempt from the {SERIES_MISC} authorship check, but its ini'
            f" file now names a script or art credit: {extra_pub_info!r}. The exemption is"
            f" obsolete -- remove it from ATTRIBUTION_NOT_REQUIRED in title_page_allowlists.py"
            f" so the credit is checked."
        )


class TestMiscSeriesByline:
    """A Misc story's byline names Barks's part, unless ``title_page_allowlists`` says why not."""

    @pytest.mark.parametrize(
        "story_title", [t for t in misc_titles() if t not in plain_byline_titles()]
    )
    def test_misc_title_byline_names_his_part(self, db: ComicsDatabase, story_title: str) -> None:
        byline = db.get_comic_book(story_title).byline

        assert byline != INTRO_DEFAULT_BYLINE, (
            f'{SERIES_MISC} title "{story_title}" has the plain byline "{byline} Carl Barks".'
            f" Stories in the {SERIES_MISC} series were not solely his, so its ini file must"
            f' name his part, e.g. "byline = art by". If this title is an exception, add it'
            f" to PLAIN_BYLINE_ALLOWED in title_page_allowlists.py with a reason."
        )

    # Whether an entry is still needed at all is test_story_bylines's check, which sees
    # the credits as well as the series.
    @pytest.mark.parametrize("story_title", plain_byline_titles())
    def test_plain_byline_title_still_has_a_plain_byline(
        self, db: ComicsDatabase, story_title: str
    ) -> None:
        byline = db.get_comic_book(story_title).byline

        assert byline == INTRO_DEFAULT_BYLINE, (
            f'"{story_title}" is allowed a plain byline but its ini file now names'
            f' "{byline}". Remove it from PLAIN_BYLINE_ALLOWED in title_page_allowlists.py.'
        )
