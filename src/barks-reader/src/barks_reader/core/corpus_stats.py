"""Corpus-wide statistics for the Introduction "By the Numbers" page.

Aggregates the whole Barks Disney corpus from ``barks_fantagraphics`` into a
flat, presentation-ready structure: a two-line opening plus grouped label/value
rows, some of which carry their share of a section's whole. This module is
Kivy-free and does no widget work - the screen in
``barks_reader.ui.corpus_stats_screen`` only renders what it returns.

Two figures here are easy to get wrong, so they are computed deliberately:

* Attribution (art vs. script) comes from Barrier's bibliography
  (``barks_bibliography.Qualifier``), never from ``ComicBookInfo.is_barks_title``
  - that flag means "Barks himself titled it", not "Barks made it".
* The payment ledger uses ``-1`` as an "unknown" sentinel for both the amount
  and the accepted date - and 383 of its 947 records carry it, most of them
  covers. Summing the column blindly *subtracts* a dollar per cover, so every
  payment figure here is computed over the records with a real amount only, and
  the footnote says how many that is.

The text section is separate because it needs the optional Whoosh speech index:
``compute_static_stats`` is instant and always available, while
``compute_text_stats`` does disk I/O and returns ``None`` when no index is
installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_bibliography import TITLE_TO_BIB_ENTRY, Qualifier
from barks_fantagraphics.barks_payments import BARKS_PAYMENTS
from barks_fantagraphics.barks_tags import BARKS_TAGGED_TITLES, get_all_tags_in_tag_category
from barks_fantagraphics.barks_tags_enums import TagCategories
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE
from barks_fantagraphics.comic_book_info import (
    BARKS_TITLE_INFO,
    COVERS_SET,
    NON_COMIC_TITLES,
    ONE_PAGERS,
    SYNTHETIC_TITLES,
)
from barks_fantagraphics.comic_search import ComicSearch
from barks_fantagraphics.entity_types import EntityType
from barks_fantagraphics.fanta_comics_info import FANTA_SOURCE_COMICS
from barks_fantagraphics.search_ports import SearchIndexUnavailableError
from comic_utils.cpi_calculator import CPI_DATABASE_PATH, get_adjusted_usd, get_latest_year

if TYPE_CHECKING:
    from pathlib import Path

    from barks_fantagraphics.barks_payments import PaymentInfo
    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.comic_book_info import ComicBookInfo

# A story is a Barks comic story: not a cover, not a prose article, and not one of
# the synthetic "all one-pagers"/"all covers" collection entries.
_NON_STORY_TITLES: frozenset[Titles] = frozenset(
    COVERS_SET | set(NON_COMIC_TITLES) | set(SYNTHETIC_TITLES)
)

# Page-count bands. A one-page gag and a 32-page adventure are different animals;
# these are the two cuts that separate them.
_SHORT_STORY_MAX_PAGES = 12

# The payment ledger's "not known" sentinel, used for both amount and date.
_UNKNOWN = -1

# Barks retired in 1966. A handful of payments land after it - reprint and script
# work in 1969-71, 13 records worth about $14,000 in current dollars - and the
# per-year average excludes them, so its numerator and denominator cover the same
# span. Dividing the whole ledger by his working years would spread money he
# earned in 1971 across years that ended in 1966.
_RETIREMENT_YEAR = 1966


@dataclass(frozen=True, slots=True)
class StatRow:
    """A single label/value line in a statistics section.

    Args:
        label: The left-hand description.
        value: The right-hand figure, already formatted.
        share: This row's fraction of its section's whole, in ``[0.0, 1.0]``, or
            ``None`` when the row is not part of one. Only set it where every
            other row of the group is a slice of the same total - the screen
            draws it as a bar, and a lone bar has nothing to be read against.
        prose: True when the value is a name or phrase rather than a figure, so
            it needs its own line instead of a right-aligned column.

    """

    label: str
    value: str
    share: float | None = None
    prose: bool = False


@dataclass(frozen=True, slots=True)
class StatSection:
    """A headed group of statistics rows, with an optional caveat line."""

    heading: str
    rows: tuple[StatRow, ...]
    footnote: str | None = None


@dataclass(frozen=True, slots=True)
class SectionShape:
    """How much room a section needs, known before its figures are.

    The page reserves space for the dialogue section up front so that the late
    background scan fills it in place instead of reflowing a fixed-height page.
    """

    num_rows: int
    footnote_lines: int


# The shape of the section `compute_text_stats` returns. Pinned by a test, since a
# row added there without updating this would silently overflow the page.
TEXT_SECTION_SHAPE = SectionShape(num_rows=6, footnote_lines=2)


@dataclass(frozen=True, slots=True)
class Opening:
    """The two lines the page opens with.

    Deliberately not a band of headline figures: every number big enough to
    headline is already a row further down, so a band of them would only repeat
    itself. These two lines instead say the one thing no row says - the shape of
    a whole working life - and hand the reader a rate to judge the rest by.
    """

    headline: str
    standfirst: str


@dataclass(frozen=True, slots=True)
class CorpusStats:
    """Everything the "By the Numbers" page renders."""

    opening: Opening
    sections: tuple[StatSection, ...]


def get_stories() -> list[ComicBookInfo]:
    """Return every Barks comic story, excluding covers, articles and collections.

    Returns:
        The ``ComicBookInfo`` records for all 683 stories, in chronological order.

    """
    return [info for info in BARKS_TITLE_INFO if info.title not in _NON_STORY_TITLES]


def compute_static_stats(cpi_db_path: Path = CPI_DATABASE_PATH) -> CorpusStats:
    """Compute every statistic that needs no index and no disk access.

    Covers the corpus, attribution, length, payment and cast sections. All of it
    is in-memory work over constants that are already imported, so this is fast
    enough to call on the UI thread.

    Args:
        cpi_db_path: The CPI database the payment figures are inflated with. The
            shipped one by default; tests hand in a small fixture, because the real
            file is a git-lfs object that a bare checkout does not have.

    Returns:
        The opening lines and the five always-available sections.

    """
    stories = get_stories()
    story_pages = _story_page_counts(stories)
    total_pages = sum(story_pages.values())
    paid_records = _paid_records()
    adjusted_total = _adjusted_payment_total(paid_records, cpi_db_path)
    paid_pages = sum(payment.num_pages for payment in paid_records)
    script_and_art = _script_and_art_titles(stories)

    return CorpusStats(
        opening=_opening(stories, total_pages, adjusted_total / paid_pages),
        sections=(
            _corpus_section(stories),
            _attribution_section(stories),
            _length_section(story_pages, total_pages, len(stories), script_and_art),
            _payment_section(adjusted_total, paid_records, paid_pages, cpi_db_path),
            _cast_section(),
        ),
    )


def _opening(stories: list[ComicBookInfo], total_pages: int, adjusted_per_page: float) -> Opening:
    """Build the page's opening lines from the span, the page count and the rate."""
    submitted_years = [info.submitted_year for info in stories]

    return Opening(
        # An en dash, not a hyphen: this is a span of years, and the headline is
        # set in the hand-lettered display face, which has the glyph.
        headline=f"{len(stories):,} stories, {min(submitted_years)}–{max(submitted_years)}",  # noqa: RUF001
        standfirst=(
            f"{total_pages:,} pages, at what would today average ${adjusted_per_page:,.0f} a page."
        ),
    )


def compute_text_stats(indexes_dir: Path) -> StatSection | None:
    """Compute the dialogue statistics from the Whoosh speech index.

    Makes one pass over every indexed speech group, so it does real disk I/O
    (roughly half a second for the full corpus) and should be called off the UI
    thread.

    Args:
        indexes_dir: The Barks Reader ``Indexes`` directory.

    Returns:
        The "The words" section, or ``None`` if no usable index is installed.

    """
    if not indexes_dir.is_dir():
        return None

    search = ComicSearch(indexes_dir)
    try:
        # Cheap sidecar reads first: they are what fails on a partial index, and
        # there is no point paying for the full-index scan only to bail out.
        distinct_words = len(search.get_cleaned_terms())
        num_person_names = len(search.get_entity_terms(EntityType.PERSON))
        totals = search.get_corpus_text_totals()
    except (SearchIndexUnavailableError, OSError, ValueError):
        # No index, a partial index, or missing term sidecars. The page is still
        # worth showing without this section.
        return None

    rows = (
        StatRow("Balloons and captions", f"{totals.num_text_entities:,}"),
        StatRow("Words spoken", f"{totals.num_words:,}"),
        StatRow("Distinct words", f"{distinct_words:,}"),
        StatRow("Panels with text", f"{totals.num_panels:,}"),
        StatRow("Pages with text", f"{totals.num_pages:,}"),
        StatRow("Person names", f"{num_person_names:,}"),
    )

    num_stories = len(get_stories())
    # The first row counts sound effects too; the label has no room to say so.
    footnote = (
        "Balloons include captions and sound effects."
        f" Text figures cover {totals.num_titles:,} of {num_stories:,} stories currently indexed."
    )

    return StatSection(heading="The words", rows=rows, footnote=footnote)


def _corpus_section(stories: list[ComicBookInfo]) -> StatSection:
    """Build the overall size-of-the-corpus section."""
    submitted_years = [info.submitted_year for info in stories]

    return StatSection(
        heading="The corpus",
        rows=(
            StatRow("Stories", f"{len(stories):,}"),
            StatRow("One-pagers", f"{len(ONE_PAGERS):,}"),
            StatRow("Covers", f"{len(COVERS_SET):,}"),
            StatRow("Fantagraphics Volumes", f"{len(FANTA_SOURCE_COMICS):,}"),
            # En dashes throughout, to match the span in the opening headline.
            StatRow("Submitted to Western", f"{min(submitted_years)}–{max(submitted_years)}"),  # noqa: RUF001
        ),
    )


def _script_and_art_titles(stories: list[ComicBookInfo]) -> frozenset[Titles]:
    """Return the stories Barks both wrote and drew.

    An unqualified entry in Barrier's bibliography means the whole story is his;
    every other entry carries a `Qualifier` saying which half was not.

    Args:
        stories: The corpus stories to filter.

    Returns:
        The titles with an unqualified bibliography entry.

    """
    return frozenset(
        info.title
        for info in stories
        if (entry := TITLE_TO_BIB_ENTRY.get(info.title)) is not None and entry.qualifier is None
    )


def _attribution_section(stories: list[ComicBookInfo]) -> StatSection:
    """Build the "how much of this is Barks" section from Barrier's bibliography."""
    counts: dict[Qualifier | None, int] = {}
    num_with_entry = 0
    for info in stories:
        entry = TITLE_TO_BIB_ENTRY.get(info.title)
        if entry is None:
            continue
        num_with_entry += 1
        counts[entry.qualifier] = counts.get(entry.qualifier, 0) + 1

    # Every story falls into exactly one of these five buckets, so each one is a
    # slice of the same whole and carries a share.
    def _row(label: str, count: int) -> StatRow:
        return StatRow(label, f"{count:,}", share=count / len(stories))

    return StatSection(
        heading="Barks's hand",
        rows=(
            _row("Script and art", counts.get(None, 0)),
            _row("Art only", counts.get(Qualifier.ART_ONLY, 0)),
            _row("Script only", counts.get(Qualifier.SCRIPT_ONLY, 0)),
            _row("Art, script rewritten", counts.get(Qualifier.ART_AND_REWRITING_OF_SCRIPT, 0)),
            _row("Not in the bibliography", len(stories) - num_with_entry),
        ),
        footnote="Attribution as stated in Michael Barrier's bibliography.",
    )


def _length_section(
    story_pages: dict[Titles, int],
    total_pages: int,
    num_stories: int,
    script_and_art: frozenset[Titles],
) -> StatSection:
    """Build the story-length distribution section.

    Args:
        story_pages: Page count per story, from the payment ledger.
        total_pages: The sum of those page counts.
        num_stories: The corpus story count, for the shortfall footnote.
        script_and_art: The stories Barks both wrote and drew, which is the set
            the longest-story row is drawn from.

    """
    num_one_page = sum(1 for pages in story_pages.values() if pages == 1)
    num_short = sum(1 for pages in story_pages.values() if 1 < pages <= _SHORT_STORY_MAX_PAGES)
    num_long = sum(1 for pages in story_pages.values() if pages > _SHORT_STORY_MAX_PAGES)

    # Drawn from the stories that are wholly Barks's, so the row is a fact about
    # his own longest work. The corpus's longest story overall is a 64-page one he
    # drew to someone else's script, which is a different claim.
    longest_title, longest_pages = min(
        ((title, pages) for title, pages in story_pages.items() if title in script_and_art),
        # Longest first, then alphabetical, so a tie cannot vary between runs.
        key=lambda item: (-item[1], ENUM_TO_STR_TITLE[item[0]]),
    )
    mean_pages = total_pages / len(story_pages)

    # The payment ledger is the only per-story page source, and it covers every
    # story today. If that ever stops being true, say so rather than quietly
    # counting fewer stories here than the "Stories" row two sections above.
    num_counted = len(story_pages)
    footnote = (
        None
        if num_counted == num_stories
        else (
            f"Page figures cover {num_counted:,} of {num_stories:,} stories;"
            " the rest are absent from the payment ledger."
        )
    )

    # The three length bands partition the counted stories; the rows after them
    # are totals and a single named story, so they are not slices of anything.
    def _band(label: str, count: int) -> StatRow:
        return StatRow(label, f"{count:,}", share=count / num_counted)

    return StatSection(
        heading="Length",
        rows=(
            _band(f"Short (2–{_SHORT_STORY_MAX_PAGES} pages)", num_short),  # noqa: RUF001
            _band(f"Long ({_SHORT_STORY_MAX_PAGES + 1}+ pages)", num_long),
            _band("One page", num_one_page),
            StatRow("Story pages", f"{total_pages:,}"),
            StatRow("Mean pages", f"{mean_pages:.1f}"),
            StatRow(
                # Qualified deliberately: the corpus holds a longer story that
                # Barks drew but did not write.
                "Longest (script and art)",
                f"{ENUM_TO_STR_TITLE[longest_title]}, {longest_pages} pages",
                prose=True,
            ),
        ),
        footnote=footnote,
    )


def _payment_section(
    adjusted_total: float,
    paid_records: list[PaymentInfo],
    paid_pages: int,
    cpi_db_path: Path,
) -> StatSection:
    """Build the what-Barks-was-paid section."""
    nominal_total = sum(payment.payment for payment in paid_records)
    latest_year = get_latest_year(cpi_db_path)

    working = [p for p in paid_records if p.accepted_year <= _RETIREMENT_YEAR]
    first_year = min(p.accepted_year for p in working)
    num_working_years = _RETIREMENT_YEAR - first_year + 1
    per_year = _adjusted_payment_total(working, cpi_db_path) / num_working_years

    return StatSection(
        heading="Payment",
        rows=(
            StatRow("Total paid", f"${nominal_total:,.0f}"),
            StatRow(f"In {latest_year} dollars", f"${adjusted_total:,.0f}"),
            StatRow(f"Per page ({latest_year} dollars)", f"${adjusted_total / paid_pages:,.0f}"),
            StatRow(f"Per year ({latest_year} dollars)", f"${per_year:,.0f}"),
            StatRow("Paid pages", f"{paid_pages:,}"),
        ),
        footnote=(
            f"From the {len(paid_records):,} of {len(BARKS_PAYMENTS):,} payment records with an"
            f" amount; the rest, mostly covers, have none. Yearly average runs"
            f" {first_year}-{_RETIREMENT_YEAR}."
        ),
    )


def _cast_section() -> StatSection:
    """Build the characters/places/themes section from the curated tag tables."""
    rows = [
        StatRow(label, f"{_num_tags_with_stories(category):,}")
        for label, category in (
            ("Named characters", TagCategories.CHARACTERS),
            ("Places", TagCategories.PLACES),
            ("Themes", TagCategories.THEMES),
            ("Things", TagCategories.THINGS),
        )
    ]

    # The tag category is an unordered set, so a tie has to break on the name or the
    # winner changes between runs.
    top_tag, top_count = min(
        (
            (tag, len(titles))
            for tag in get_all_tags_in_tag_category(TagCategories.CHARACTERS)
            if (titles := BARKS_TAGGED_TITLES.get(tag))
        ),
        key=lambda item: (-item[1], item[0].value),
    )
    rows.append(
        StatRow("Most-tagged character", f"{top_tag.value}, {top_count} stories", prose=True)
    )

    return StatSection(heading="The cast", rows=tuple(rows))


def _num_tags_with_stories(category: TagCategories) -> int:
    """Count the tags in a category that are attached to at least one story."""
    return sum(1 for tag in get_all_tags_in_tag_category(category) if BARKS_TAGGED_TITLES.get(tag))


def _story_page_counts(stories: list[ComicBookInfo]) -> dict[Titles, int]:
    """Map each story to its page count from the payment ledger.

    Stories with no ledger record are omitted rather than counted as zero pages;
    ``_length_section`` footnotes the shortfall when there is one.
    """
    return {
        info.title: BARKS_PAYMENTS[info.title].num_pages
        for info in stories
        if info.title in BARKS_PAYMENTS
    }


def _paid_records() -> list[PaymentInfo]:
    """Return the payment records that carry a real amount and a real date.

    Returns:
        Every ``PaymentInfo`` whose amount and accepted year are both known.
        Covers and a handful of late stories are recorded without an amount.

    """
    return [
        payment
        for payment in BARKS_PAYMENTS.values()
        if payment.payment > 0 and payment.accepted_year != _UNKNOWN
    ]


def _adjusted_payment_total(paid_records: list[PaymentInfo], cpi_db_path: Path) -> float:
    """Sum the given payments in current dollars.

    Args:
        paid_records: Payments with a known amount and accepted year.
        cpi_db_path: The CPI database to inflate with.

    Returns:
        The inflation-adjusted total.

    """
    latest_year = get_latest_year(cpi_db_path)
    return sum(
        get_adjusted_usd(payment.payment, payment.accepted_year, latest_year, cpi_db_path)
        for payment in paid_records
    )
