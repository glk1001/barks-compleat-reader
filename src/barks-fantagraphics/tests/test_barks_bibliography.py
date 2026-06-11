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
    Disposition,
)
from barks_fantagraphics.barks_covers import BARKS_COVER_BY_KEY, BARKS_COVERS
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
        Titles.MILKMAN_THE,
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


def _all_entries() -> list[BibEntry]:
    return [e for s in BIBLIOGRAPHY for i in s.issues for e in i.entries]


def test_every_entry_has_exactly_one_disposition() -> None:
    """Zero undisposed entries - the permanent one-to-one invariant."""
    for entry in _all_entries():
        assert isinstance(entry.disposition, Disposition)
        # The disposition's payload fields agree with the disposition kind.
        assert (entry.disposition == Disposition.MATCHED_TITLE) == (entry.title is not None)
        assert (entry.disposition == Disposition.COVER) == (entry.cover_key is not None)
        if entry.disposition in (Disposition.EXCLUDED_SECTION, Disposition.EXCLUDED_ENTRY):
            assert entry.disposition_reason


def test_matched_story_entries_have_unique_titles() -> None:
    """Story/gag entry <-> Titles member is one-to-one."""
    matched = [e for e in _all_entries() if e.disposition == Disposition.MATCHED_TITLE]
    assert len(matched) == len(TITLE_TO_BIB_ENTRY)


def test_matched_entries_sit_in_the_curated_issue() -> None:
    """A matched entry's enclosing issue agrees with ComicBookInfo's issue.

    Compares issue name and number only: the issue *number* is the join key the
    generator matches on, while Barrier's cover-date years are known to differ
    from comic_book_info by a year for some issues. Barrier records unnumbered
    giveaway issues (March of Comics, Firestone, Kite Fun Book) as number -1
    where the curated data assigns the conventional number, so -1 skips the
    number comparison.
    """
    cbi_by_title = {c.title: c for c in BARKS_TITLE_INFO}
    for series in BIBLIOGRAPHY:
        for issue in series.issues:
            for entry in issue.entries:
                if entry.disposition != Disposition.MATCHED_TITLE:
                    continue
                assert entry.title is not None
                cbi = cbi_by_title[entry.title]
                assert issue.issue_name is cbi.issue_name, entry.title.name
                if issue.issue_number != -1:
                    assert issue.issue_number == cbi.issue_number, entry.title.name


def test_cover_entries_match_registry_one_to_one() -> None:
    """Cover entry <-> BarksCover record is one-to-one."""
    cover_entries = [e for e in _all_entries() if e.disposition == Disposition.COVER]
    keys = [e.cover_key for e in cover_entries]
    assert len(keys) == len(set(keys)), "duplicate cover keys among bibliography entries"
    for key in keys:
        assert key in BARKS_COVER_BY_KEY, f"no BarksCover for bibliography cover {key}"
    assert len(cover_entries) == len(BARKS_COVERS), (
        "BarksCover records with no bibliography cover entry"
    )


def test_cover_registry_keys_are_consistent() -> None:
    """Each registry record's key property round-trips through BARKS_COVER_BY_KEY."""
    assert len(BARKS_COVER_BY_KEY) == len(BARKS_COVERS)
    for cover in BARKS_COVERS:
        assert BARKS_COVER_BY_KEY[cover.key] is cover
        if cover.illustrates is not None:
            assert isinstance(cover.illustrates, Titles)
