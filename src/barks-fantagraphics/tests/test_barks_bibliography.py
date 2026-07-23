"""Sanity checks for the generated ``barks_bibliography`` data module.

The module is generated from Michael Barrier's bibliography by
``experiments/bibliography/parse_bibliography.py``. These tests guard the
invariants the generator guarantees, so an accidental hand-edit or a
regeneration regression is caught.
"""

import re

from barks_fantagraphics.barks_bibliography import (
    BIBLIOGRAPHY,
    TITLE_TO_BIB_ENTRY,
    BibEntry,
    BibIssue,
    BibSeries,
    Disposition,
)
from barks_fantagraphics.barks_covers import BARKS_COVER_BY_KEY, BARKS_COVERS, get_cover_title
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO, COVERS_SET

# Barrier's bibliography ends with issues bearing 1978 cover dates.
LAST_BIBLIOGRAPHY_YEAR = 1978
MIN_SERIES = 39
MIN_ISSUES = 400
MIN_ENTRIES = 900

# Curated titles with no counterpart in Barrier's 1978 bibliography: later
# reprints/originals (post-1978) and a few documented findings (see
# experiments/bibliography/overrides.py). Cover titles are included: each cover
# entry carries its cover's title (and its cover_key - see the cover tests below).
EXPECTED_WITHOUT_BIB_ENTRY: frozenset[Titles] = frozenset(
    {
        Titles.SILENT_NIGHT,
        Titles.MILKMAN_THE,
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
    """A matched entry carries descriptive text; only cover titles map to covers."""
    for title, entry in TITLE_TO_BIB_ENTRY.items():
        assert entry.is_cover == (title in COVERS_SET)
        assert entry.description or entry.notes


def test_cover_entries_carry_their_cover_title() -> None:
    """A cover entry's title and cover_key identify the same BARKS_COVERS record."""
    for entry in _all_entries():
        if entry.cover_key is not None:
            assert entry.title is get_cover_title(BARKS_COVER_BY_KEY[entry.cover_key])
        else:
            assert entry.title not in COVERS_SET


def _all_entries() -> list[BibEntry]:
    return [e for s in BIBLIOGRAPHY for i in s.issues for e in i.entries]


def test_every_entry_has_exactly_one_disposition() -> None:
    """Zero undisposed entries - the permanent one-to-one invariant."""
    for entry in _all_entries():
        assert isinstance(entry.disposition, Disposition)
        # The disposition's payload fields agree with the disposition kind:
        # matched stories and covers both carry a title; only covers a cover_key.
        title_dispositions = (Disposition.MATCHED_TITLE, Disposition.COVER)
        assert (entry.disposition in title_dispositions) == (entry.title is not None)
        assert (entry.disposition == Disposition.COVER) == (entry.cover_key is not None)
        if entry.disposition in (Disposition.EXCLUDED_SECTION, Disposition.EXCLUDED_ENTRY):
            assert entry.disposition_reason


def test_matched_story_entries_have_unique_titles() -> None:
    """Story/gag entry <-> Titles member is one-to-one (covers indexed separately)."""
    matched = [e for e in _all_entries() if e.disposition == Disposition.MATCHED_TITLE]
    story_titles = [t for t in TITLE_TO_BIB_ENTRY if t not in COVERS_SET]
    assert len(matched) == len(story_titles)


_MONTH_SPAN_RE = re.compile(r"([A-Za-z]{3,9})\.?\s*-\s*([A-Za-z]{3,9})\.?")
_YEAR_RE = re.compile(r"19\d{2}")
_MONTH_PREFIXES = (
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
)


def _month_number(token: str) -> int:
    prefix = token.lower()[:3]
    return _MONTH_PREFIXES.index(prefix) + 1 if prefix in _MONTH_PREFIXES else -1


def _expected_curated_year(issue: BibIssue) -> int:
    """Curated issue year implied by Barrier's issue date.

    Dell dated quarterly issues with a cover-date span; when the span crosses a
    year boundary with a single printed year ("Dec.-Feb. 1956", "Nov.-Jan.
    1960"), that year belongs to the *end* month while comic_book_info dates
    the issue by the start month - so expect Barrier's year minus one. A
    bracketed code date ("[(November) 1960]") already carries the true year,
    and a two-year span ("Dec. 1953-Feb. 1954") parses to the start year -
    both agree with the curated year as-is.
    """
    if "[" not in issue.raw_date:
        span = _MONTH_SPAN_RE.search(issue.raw_date)
        if span and len(_YEAR_RE.findall(issue.raw_date)) == 1:
            start, end = (_month_number(t) for t in span.groups())
            if start > end > 0:
                return issue.issue_year - 1
    return issue.issue_year


def test_matched_entries_sit_in_the_curated_issue() -> None:
    """A matched entry's enclosing issue agrees with ComicBookInfo's issue.

    The issue *number* is the join key the generator matches on; Barrier
    records unnumbered giveaway issues (March of Comics, Firestone, Kite Fun
    Book) as number -1 where the curated data assigns the conventional number,
    so -1 skips the number comparison. The year is compared after normalizing
    Barrier's boundary-crossing cover-date spans (see _expected_curated_year).
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
                # -1 = an unnumbered giveaway (March of Comics 4, the Firestone
                # Christmas books, the Kite Fun Book): Barrier has no number to
                # compare, while the curated data assigns the conventional one.
                if issue.issue_number != -1:
                    assert issue.issue_number == cbi.issue_number, entry.title.name
                assert issue.issue_year != -1, entry.title.name
                assert cbi.issue_year == _expected_curated_year(issue), entry.title.name


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


def test_cover_registry_and_bibliography_covers_are_bijective() -> None:
    """The BARKS_COVERS registry and the bibliography's cover entries are one-to-one.

    Every ``BarksCover.key`` matches exactly one ``Disposition.COVER`` entry's
    ``cover_key`` and vice versa - no registry record without a bibliography
    cover entry, and no cover entry without a registry record.
    """
    registry_keys = {cover.key for cover in BARKS_COVERS}
    assert len(registry_keys) == len(BARKS_COVERS), "duplicate keys in BARKS_COVERS"

    cover_entries = [e for e in _all_entries() if e.disposition == Disposition.COVER]
    bib_keys = [e.cover_key for e in cover_entries]
    assert len(bib_keys) == len(set(bib_keys)), "duplicate cover keys among bibliography entries"
    bib_key_set = set(bib_keys)

    assert bib_key_set == registry_keys, (
        f"bibliography covers with no BARKS_COVERS record: {sorted(bib_key_set - registry_keys)}; "
        f"BARKS_COVERS records with no bibliography cover entry: "
        f"{sorted(registry_keys - bib_key_set)}"
    )


def test_cover_registry_keys_are_consistent() -> None:
    """Each registry record's key property round-trips through BARKS_COVER_BY_KEY."""
    assert len(BARKS_COVER_BY_KEY) == len(BARKS_COVERS)
    for cover in BARKS_COVERS:
        assert BARKS_COVER_BY_KEY[cover.key] is cover
        if cover.illustrates is not None:
            assert isinstance(cover.illustrates, Titles)
