"""Integrity checks for the story-title ini files of the Fantagraphics 'Misc' series.

Titles in the 'Misc' series are the Barks-adjacent stories where Barks was not the sole
author: someone else wrote the script, or Barks scripted but someone else drew it. That
fact reaches the reader only through the ``extra_pub_info`` key in the story's ini file,
which ``ComicBook.__post_init__`` appends to the title page publication blurb. Nothing
else ties series membership (``fanta_series_data.py``) to the ini files, so these tests
enforce the link.

Note the implication only runs one way: a non-Misc title may legitimately carry an
attribution too (restoration credits, guest artists), so the converse is not asserted.
"""

from __future__ import annotations

import re
from configparser import ConfigParser, ExtendedInterpolation

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from barks_fantagraphics.fanta_series_info import SERIES_MISC

# An attribution names who did the script and/or the art. The wording varies a lot -- from a
# bare 'Script not by Barks', through 'Script by Vic Lockman', to the Daan Jippes titles that
# credit Barks with the script and layout but Jippes with the pencils and inks, and the
# per-page breakdowns used for Pirate Gold and The Pied Piper of Duckburg. Every form names
# at least one of these roles, so match on the roles rather than on any fixed phrase. A
# restoration-only note (dialogue restored by GLK, and so on) is deliberately not enough.
_ATTRIBUTION_RE = re.compile(r"\b(script|art|pencils|inks)\b", re.IGNORECASE)

_EXAMPLE_ATTRIBUTION = "extra_pub_info = Script not by Barks"

# Misc titles that are exempt from needing an authorship credit, mapped to the reason why.
# These are stories that are in the Misc series for some reason other than not being Barks's
# work, so there is no non-Barks credit to record. Keyed by enum, not by title string, so a
# retitling cannot leave a stale entry behind.
_ATTRIBUTION_NOT_REQUIRED: dict[Titles, str] = {
    Titles.RIDDLE_OF_THE_RED_HAT_THE: (
        "It's a Barks script, but it's in the Misc series because it's an atypical Barks"
        " story: it features Mickey Mouse."
    ),
}


def _exempt_titles() -> dict[str, str]:
    """Return the exempt story titles as display strings, mapped to their reason.

    Returns:
        Display title to the reason that title needs no authorship credit.

    """
    return {
        BARKS_TITLE_INFO[title].get_title_str(): reason
        for title, reason in _ATTRIBUTION_NOT_REQUIRED.items()
    }


def _misc_titles() -> list[str]:
    """Return the display titles of every story in the Fantagraphics 'Misc' series.

    Returns:
        The story titles, in ``ALL_FANTA_COMIC_BOOK_INFO`` order.

    """
    return [
        info.comic_book_info.get_title_str()
        for info in ALL_FANTA_COMIC_BOOK_INFO.values()
        if info.series_name == SERIES_MISC
    ]


def _misc_titles_needing_attribution() -> list[str]:
    """Return the Misc titles whose ini file must carry an authorship credit.

    Returns:
        The story titles of ``_misc_titles`` less those in ``_ATTRIBUTION_NOT_REQUIRED``.

    """
    exempt = _exempt_titles()
    return [title for title in _misc_titles() if title not in exempt]


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


@pytest.fixture(scope="module")
def db() -> ComicsDatabase:
    """Real ComicsDatabase (reads story-titles INI files, no filesystem comic dirs needed)."""
    return ComicsDatabase(for_building_comics=False)


class TestMiscSeriesAttribution:
    def test_misc_series_is_not_empty(self) -> None:
        # Guards the parametrize source below: if this ever returns nothing, the
        # per-title tests would silently collect zero cases and pass vacuously.
        assert _misc_titles(), f'No titles found for the "{SERIES_MISC}" series.'

    @pytest.mark.parametrize("story_title", _misc_titles_needing_attribution())
    def test_misc_title_ini_declares_authorship(self, db: ComicsDatabase, story_title: str) -> None:
        extra_pub_info = _get_extra_pub_info(db, story_title)

        assert extra_pub_info, (
            f'{SERIES_MISC} title "{story_title}" has no "extra_pub_info" in its ini file.'
            f" Stories in the {SERIES_MISC} series were not solely authored by Barks, so the"
            f' ini file must say who wrote or drew them, e.g. "{_EXAMPLE_ATTRIBUTION}".'
            f" If this title is an exception, add it to _ATTRIBUTION_NOT_REQUIRED with a"
            f" reason."
        )

        assert _ATTRIBUTION_RE.search(extra_pub_info), (
            f'{SERIES_MISC} title "{story_title}" has an "extra_pub_info" that names no script'
            f" or art credit: {extra_pub_info!r}. Add the actual credit, or failing that a"
            f' line like "{_EXAMPLE_ATTRIBUTION}".'
        )


class TestAttributionExemptions:
    """Keep ``_ATTRIBUTION_NOT_REQUIRED`` honest, so an exemption cannot quietly rot."""

    @pytest.mark.parametrize("story_title", _exempt_titles())
    def test_exempt_title_is_still_in_misc_series(self, story_title: str) -> None:
        assert story_title in _misc_titles(), (
            f'"{story_title}" is exempt from the {SERIES_MISC} authorship check but is no'
            f" longer in the {SERIES_MISC} series. Remove it from _ATTRIBUTION_NOT_REQUIRED."
        )

    @pytest.mark.parametrize("story_title", _exempt_titles())
    def test_exempt_title_still_has_no_attribution(
        self, db: ComicsDatabase, story_title: str
    ) -> None:
        extra_pub_info = _get_extra_pub_info(db, story_title)

        assert not _ATTRIBUTION_RE.search(extra_pub_info), (
            f'"{story_title}" is exempt from the {SERIES_MISC} authorship check, but its ini'
            f" file now names a script or art credit: {extra_pub_info!r}. The exemption is"
            f" obsolete -- remove it from _ATTRIBUTION_NOT_REQUIRED so the credit is checked."
        )

    def test_every_exemption_has_a_reason(self) -> None:
        for story_title, reason in _exempt_titles().items():
            assert reason.strip(), (
                f'"{story_title}" is exempt from the {SERIES_MISC} authorship check but gives'
                f" no reason. Every entry in _ATTRIBUTION_NOT_REQUIRED must say why."
            )
