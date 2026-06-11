"""Sanity checks for the generated ``barks_bibliography`` data module.

The module is generated from Michael Barrier's bibliography by
``experiments/bibliography/parse_bibliography.py``. These tests guard the
invariants the generator guarantees, so an accidental hand-edit or a
regeneration regression is caught.
"""

from barks_fantagraphics.barks_bibliography import (
    BIBLIOGRAPHY,
    TITLE_TO_BIB_ENTRY,
    BibEntry,
    BibIssue,
    BibSeries,
)
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO

# Barrier's bibliography ends with issues bearing 1978 cover dates.
LAST_BIBLIOGRAPHY_YEAR = 1978
MIN_SERIES = 39
MIN_ISSUES = 400
MIN_ENTRIES = 900

# Curated titles with no counterpart in Barrier's 1978 bibliography: later
# reprints/originals (post-1978) and a few documented findings (see
# experiments/bibliography/overrides.py).
EXPECTED_WITHOUT_BIB_ENTRY: frozenset[Titles] = frozenset(
    {
        Titles.SILENT_NIGHT,
        Titles.MOCKING_BIRD_RIDGE,
        Titles.LIGHTS_OUT,
        Titles.ALL_CHOKED_UP,
        Titles.BIRD_CAMERA_THE,
        Titles.UP_AND_AT_IT,
        Titles.IT_HAPPENED_ONE_WINTER,
    }
    | {c.title for c in BARKS_TITLE_INFO if c.issue_year > LAST_BIBLIOGRAPHY_YEAR}
)


def test_structure_is_populated() -> None:
    """The tree has the expected breadth and dataclass types."""
    assert len(BIBLIOGRAPHY) >= MIN_SERIES
    assert all(isinstance(s, BibSeries) for s in BIBLIOGRAPHY)
    issues = [i for s in BIBLIOGRAPHY for i in s.issues]
    entries = [e for i in issues for e in i.entries]
    assert all(isinstance(i, BibIssue) for i in issues)
    assert all(isinstance(e, BibEntry) for e in entries)
    assert len(issues) > MIN_ISSUES
    assert len(entries) > MIN_ENTRIES


def test_title_index_round_trips() -> None:
    """Each index key equals the title stored on its entry."""
    for title, entry in TITLE_TO_BIB_ENTRY.items():
        assert entry.title is title


def test_every_curated_title_maps_or_is_documented() -> None:
    """Every ComicBookInfo title maps to an entry, except the documented set."""
    missing = {c.title for c in BARKS_TITLE_INFO if c.title not in TITLE_TO_BIB_ENTRY}
    assert missing == EXPECTED_WITHOUT_BIB_ENTRY


def test_mapped_entries_have_descriptions() -> None:
    """A matched entry carries descriptive text and is never a front cover."""
    for entry in TITLE_TO_BIB_ENTRY.values():
        assert not entry.is_cover
        assert entry.description or entry.notes
