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
from comic_utils.cpi_calculator import get_adjusted_usd, get_latest_year

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
_SHORT_STORY_MAX_PAGES = 15

# The payment ledger's "not known" sentinel, used for both amount and date.
_UNKNOWN = -1


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


def compute_static_stats() -> CorpusStats:
    """Compute every statistic that needs no index and no disk access.

    Covers the corpus, attribution, length, payment and cast sections. All of it
    is in-memory work over constants that are already imported, so this is fast
    enough to call on the UI thread.

    Returns:
        The opening lines and the five always-available sections.

    """
    stories = get_stories()
    story_pages = _story_page_counts(stories)
    total_pages = sum(story_pages.values())
    paid_records = _paid_records()
    adjusted_total = _adjusted_payment_total(paid_records)
    paid_pages = sum(payment.num_pages for payment in paid_records)

    return CorpusStats(
        opening=_opening(stories, total_pages, adjusted_total / paid_pages),
        sections=(
            _corpus_section(stories),
            _attribution_section(stories),
            _length_section(story_pages, total_pages, len(stories)),
            _payment_section(adjusted_total, paid_records, paid_pages),
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
        StatRow("Balloons, captions and sound effects", f"{totals.num_text_entities:,}"),
        StatRow("Words spoken", f"{totals.num_words:,}"),
        StatRow("Distinct words", f"{distinct_words:,}"),
        StatRow("Panels with dialogue", f"{totals.num_panels:,}"),
        StatRow("Pages with dialogue", f"{totals.num_pages:,}"),
        StatRow("Person names in dialogue", f"{num_person_names:,}"),
    )

    num_stories = len(get_stories())
    footnote = (
        f"Text figures cover {totals.num_titles:,} of {num_stories:,} stories currently indexed."
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
            StatRow("Fantagraphics volumes", f"{len(FANTA_SOURCE_COMICS):,}"),
            # En dashes throughout, to match the span in the opening headline.
            StatRow("Submitted to Western", f"{min(submitted_years)}–{max(submitted_years)}"),  # noqa: RUF001
        ),
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
            _row(
                "Art and rewritten script",
                counts.get(Qualifier.ART_AND_REWRITING_OF_SCRIPT, 0),
            ),
            _row("Not in Barrier's bibliography", len(stories) - num_with_entry),
        ),
        footnote="Attribution as stated in Michael Barrier's bibliography.",
    )


def _length_section(
    story_pages: dict[Titles, int], total_pages: int, num_stories: int
) -> StatSection:
    """Build the story-length distribution section."""
    num_one_page = sum(1 for pages in story_pages.values() if pages == 1)
    num_short = sum(1 for pages in story_pages.values() if 1 < pages <= _SHORT_STORY_MAX_PAGES)
    num_long = sum(1 for pages in story_pages.values() if pages > _SHORT_STORY_MAX_PAGES)

    longest_title, longest_pages = max(story_pages.items(), key=lambda item: item[1])
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
            _band("One page", num_one_page),
            _band(f"Short (2–{_SHORT_STORY_MAX_PAGES} pages)", num_short),  # noqa: RUF001
            _band(f"Long ({_SHORT_STORY_MAX_PAGES + 1}+ pages)", num_long),
            StatRow("Story pages", f"{total_pages:,}"),
            StatRow("Mean pages per story", f"{mean_pages:.1f}"),
            StatRow(
                "Longest story",
                f"{ENUM_TO_STR_TITLE[longest_title]}, {longest_pages} pages",
                prose=True,
            ),
        ),
        footnote=footnote,
    )


def _payment_section(
    adjusted_total: float, paid_records: list[PaymentInfo], paid_pages: int
) -> StatSection:
    """Build the what-Barks-was-paid section."""
    nominal_total = sum(payment.payment for payment in paid_records)
    latest_year = get_latest_year()

    return StatSection(
        heading="Payment",
        rows=(
            StatRow("Total paid", f"${nominal_total:,.0f}"),
            StatRow(f"In {latest_year} dollars", f"${adjusted_total:,.0f}"),
            StatRow(f"Per page, {latest_year} dollars", f"${adjusted_total / paid_pages:,.0f}"),
            StatRow("Paid pages", f"{paid_pages:,}"),
            StatRow("Largest single payment", f"${max(p.payment for p in paid_records):,.0f}"),
        ),
        footnote=(
            f"From the {len(paid_records):,} of {len(BARKS_PAYMENTS):,} payment records with a"
            " recorded amount; the rest, mostly covers, have none."
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


def _adjusted_payment_total(paid_records: list[PaymentInfo]) -> float:
    """Sum the given payments in current dollars.

    Args:
        paid_records: Payments with a known amount and accepted year.

    Returns:
        The inflation-adjusted total.

    """
    latest_year = get_latest_year()
    return sum(
        get_adjusted_usd(payment.payment, payment.accepted_year, latest_year)
        for payment in paid_records
    )
