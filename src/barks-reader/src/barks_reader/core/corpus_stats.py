"""Corpus-wide statistics for the Introduction "By the Numbers" page.

Aggregates the whole Barks Disney corpus from ``barks_fantagraphics`` into a
flat, presentation-ready structure: a hero band of headline figures plus grouped
label/value rows. This module is Kivy-free and does no widget work - the screen
in ``barks_reader.ui.corpus_stats_screen`` only renders what it returns.

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
    """A single label/value line in a statistics section."""

    label: str
    value: str


@dataclass(frozen=True, slots=True)
class StatSection:
    """A headed group of statistics rows, with an optional caveat line."""

    heading: str
    rows: tuple[StatRow, ...]
    footnote: str | None = None


@dataclass(frozen=True, slots=True)
class HeroStat:
    """One oversized headline figure in the band at the top of the page."""

    value: str
    caption: str


@dataclass(frozen=True, slots=True)
class CorpusStats:
    """Everything the "By the Numbers" page renders."""

    hero: tuple[HeroStat, ...]
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
        The hero band and the five always-available sections.

    """
    stories = get_stories()
    story_pages = _story_page_counts(stories)
    total_pages = sum(story_pages.values())
    paid_records = _paid_records()
    adjusted_total = _adjusted_payment_total(paid_records)

    hero = (
        HeroStat(f"{len(stories):,}", "stories"),
        HeroStat(f"{total_pages:,}", "story pages"),
        HeroStat(_compact_usd(adjusted_total), f"in {get_latest_year()} dollars"),
    )

    return CorpusStats(
        hero=hero,
        sections=(
            _corpus_section(stories),
            _attribution_section(stories),
            _length_section(story_pages, total_pages),
            _payment_section(adjusted_total, paid_records),
            _cast_section(),
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
        The "The Words" section, or ``None`` if no usable index is installed.

    """
    if not indexes_dir.is_dir():
        return None

    search = ComicSearch(indexes_dir)
    try:
        totals = search.get_corpus_text_totals()
        distinct_words = len(search.get_cleaned_terms())
        num_person_names = len(search.get_entity_terms(EntityType.PERSON))
    except (SearchIndexUnavailableError, OSError, ValueError):
        # No index, a partial index, or missing term sidecars. The page is still
        # worth showing without this section.
        return None

    rows = (
        StatRow("Text entities", f"{totals.num_text_entities:,}"),
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

    return StatSection(heading="The Words", rows=rows, footnote=footnote)


def _corpus_section(stories: list[ComicBookInfo]) -> StatSection:
    """Build the overall size-of-the-corpus section."""
    submitted_years = [info.submitted_year for info in stories]

    return StatSection(
        heading="The Corpus",
        rows=(
            StatRow("Stories", f"{len(stories):,}"),
            StatRow("One-pagers", f"{len(ONE_PAGERS):,}"),
            StatRow("Covers", f"{len(COVERS_SET):,}"),
            StatRow("Fantagraphics volumes", f"{len(FANTA_SOURCE_COMICS):,}"),
            StatRow("Submitted to Western", f"{min(submitted_years)} - {max(submitted_years)}"),
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

    return StatSection(
        heading="Barks's Hand",
        rows=(
            StatRow("Script and art", f"{counts.get(None, 0):,}"),
            StatRow("Art only", f"{counts.get(Qualifier.ART_ONLY, 0):,}"),
            StatRow("Script only", f"{counts.get(Qualifier.SCRIPT_ONLY, 0):,}"),
            StatRow(
                "Art and rewritten script",
                f"{counts.get(Qualifier.ART_AND_REWRITING_OF_SCRIPT, 0):,}",
            ),
            StatRow("Not in Barrier's bibliography", f"{len(stories) - num_with_entry:,}"),
        ),
        footnote="Attribution as stated in Michael Barrier's bibliography.",
    )


def _length_section(story_pages: dict[Titles, int], total_pages: int) -> StatSection:
    """Build the story-length distribution section."""
    num_one_page = sum(1 for pages in story_pages.values() if pages == 1)
    num_short = sum(1 for pages in story_pages.values() if 1 < pages <= _SHORT_STORY_MAX_PAGES)
    num_long = sum(1 for pages in story_pages.values() if pages > _SHORT_STORY_MAX_PAGES)

    longest_title, longest_pages = max(story_pages.items(), key=lambda item: item[1])
    mean_pages = total_pages / len(story_pages)

    return StatSection(
        heading="Length",
        rows=(
            StatRow("One page", f"{num_one_page:,}"),
            StatRow(f"Short (2 - {_SHORT_STORY_MAX_PAGES} pages)", f"{num_short:,}"),
            StatRow(f"Long ({_SHORT_STORY_MAX_PAGES + 1}+ pages)", f"{num_long:,}"),
            StatRow("Story pages", f"{total_pages:,}"),
            StatRow("Mean pages per story", f"{mean_pages:.1f}"),
            StatRow(
                "Longest story",
                f"{ENUM_TO_STR_TITLE[longest_title]}, {longest_pages} pages",
            ),
        ),
    )


def _payment_section(adjusted_total: float, paid_records: list[PaymentInfo]) -> StatSection:
    """Build the what-Barks-was-paid section."""
    nominal_total = sum(payment.payment for payment in paid_records)
    paid_pages = sum(payment.num_pages for payment in paid_records)
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

    top_tag, top_count = max(
        (
            (tag, len(titles))
            for tag in get_all_tags_in_tag_category(TagCategories.CHARACTERS)
            if (titles := BARKS_TAGGED_TITLES.get(tag))
        ),
        key=lambda item: item[1],
    )
    rows.append(StatRow("Most-tagged character", f"{top_tag.value}, {top_count} stories"))

    return StatSection(heading="The Cast", rows=tuple(rows))


def _num_tags_with_stories(category: TagCategories) -> int:
    """Count the tags in a category that are attached to at least one story."""
    return sum(1 for tag in get_all_tags_in_tag_category(category) if BARKS_TAGGED_TITLES.get(tag))


def _story_page_counts(stories: list[ComicBookInfo]) -> dict[Titles, int]:
    """Map each story to its page count from the payment ledger."""
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


def _compact_usd(amount: float) -> str:
    """Format a dollar amount for the hero band, e.g. ``$2.67M``."""
    million = 1_000_000
    thousand = 1_000
    if amount >= million:
        return f"${amount / million:.2f}M"
    if amount >= thousand:
        return f"${amount / thousand:.0f}K"
    return f"${amount:,.0f}"
