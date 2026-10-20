"""The numbers behind the Appendix "Statistics" charts.

Each chart on the Statistics screen is a pre-rendered PNG that
``scripts/generate_stats_images.py`` draws from one ``Series`` computed here. Keeping
the numbers apart from the drawing is what makes them checkable: the unit tests
assert their shape and tie them to the Introduction's "By the Numbers" page, and the
corpus validator recomputes them against the ``chart-data.json`` sidecar the script
writes beside the PNGs, so an edited ledger without a rerun is caught.

The populations are the ones ``corpus_stats`` already vets, for the two traps the
charts fell into: ``is_barks_title`` means "Barks named it", not "Barks made it", and
the payment ledger's ``-1`` sentinel (an unknown amount or date) must never be summed
or charted. This module is Kivy-free and imports no plotting library.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from barks_fantagraphics.barks_payments import BARKS_PAYMENTS
from barks_fantagraphics.barks_tags import BARKS_TAGGED_TITLES, get_all_tags_in_tag_category
from barks_fantagraphics.barks_tags_enums import TagCategories
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from comic_utils.cpi_calculator import get_adjusted_usd

from .corpus_stats import PART_TAGS, get_paid_records, get_stories

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from barks_fantagraphics.comic_book_info import ComicBookInfo

# The sidecar the generator writes beside the PNGs, holding every series below.
CHART_DATA_FILE: Final = "chart-data.json"

# Series name -> the PNG the Statistics screen shows for it.
CHART_FILES: Final[dict[str, str]] = {
    "stories_per_year": "stories_per_year.png",
    "pages_per_year": "pages_per_year.png",
    "payments_per_year": "payments_per_year.png",
    "payment_rate": "payment_rate.png",
    "stories_per_series": "stories_per_series.png",
    "top_characters": "top_characters.png",
    "top_locations": "top_locations.png",
}

# The screen's other images, under its Word Statistics menu: the most-frequent-words
# table the generator draws from the search index, and the era word clouds from
# ``scripts/generate_tfidf_wordcloud.py``.
MOST_FREQUENT_FILE: Final = "most_frequent.png"
WORDCLOUD_GLOB: Final = "tfidf_wordcloud_*.png"
_WORDCLOUD_PERIOD: Final = re.compile(r"^tfidf_wordcloud_(.+)\.png$")

# The Statistics screen's menu: each chart's label and file, in menu order.
CHART_ITEMS: Final[list[tuple[str, str]]] = [
    ("Stories per Year", CHART_FILES["stories_per_year"]),
    ("Pages per Year", CHART_FILES["pages_per_year"]),
    ("Payments per Year", CHART_FILES["payments_per_year"]),
    ("Payment Rate ($/page)", CHART_FILES["payment_rate"]),
    ("Stories per Series", CHART_FILES["stories_per_series"]),
    ("Top Characters", CHART_FILES["top_characters"]),
    ("Top Locations", CHART_FILES["top_locations"]),
]
# The Word Statistics menu's first item; the word clouds found follow it.
MOST_FREQUENT_ITEM: Final = ("Most Frequent", MOST_FREQUENT_FILE)


def wordcloud_items(statistics_dir: Path) -> list[tuple[str, str]]:
    """Return the era word clouds in `statistics_dir`, each labelled by its era.

    ``tfidf_wordcloud_1943-46.png`` is listed as ``"Word Cloud 1943-46"``; a file the
    glob matches but with no era in its name is left out.

    Args:
        statistics_dir: The folder the charts are in.

    Returns:
        ``(label, filename)`` pairs, in file-name order.

    """
    results: list[tuple[str, str]] = []
    for path in sorted(statistics_dir.glob(WORDCLOUD_GLOB)):
        m = _WORDCLOUD_PERIOD.match(path.name)
        if m:
            results.append((f"Word Cloud {m.group(1)}", path.name))
    return results


TOP_N: Final = 20
_CENTS: Final = 2


@dataclass(frozen=True, slots=True)
class Series:
    """One chart's data: a label per bar or point and the value at each.

    Labels are years for the per-year charts and names for the rest. Money is
    rounded to cents so a series survives the JSON sidecar unchanged.
    """

    name: str
    labels: tuple[int | str, ...]
    values: tuple[int | float, ...]

    @property
    def total(self) -> float:
        """Return the sum of the values."""
        return sum(self.values)


def stories_per_year() -> Series:
    """Count the stories Barks submitted each year, by their submitted date."""
    return _per_year("stories_per_year", ((info.submitted_year, 1) for info in get_stories()))


def pages_per_year() -> Series:
    """Sum the stories' pages each year, by the ledger's accepted date.

    Page counts come from the payment ledger, so a story without a record is
    omitted rather than counted as zero (today every story has one).
    """
    return _per_year(
        "pages_per_year",
        (
            (BARKS_PAYMENTS[info.title].accepted_year, BARKS_PAYMENTS[info.title].num_pages)
            for info in get_stories()
            if info.title in BARKS_PAYMENTS
        ),
    )


def payments_per_year() -> Series:
    """Sum what Barks was paid each year, in the latest CPI year's dollars."""
    nominal = _per_year(
        "payments_per_year",
        ((record.accepted_year, record.payment) for record in get_paid_records()),
    )
    return Series(
        nominal.name,
        nominal.labels,
        tuple(
            round(get_adjusted_usd(amount, int(year)), _CENTS)
            for year, amount in zip(nominal.labels, nominal.values, strict=True)
        ),
    )


def payment_rate() -> Series:
    """Give the pay per page each year, in the latest CPI year's dollars."""
    pages = _per_year(
        "pages", ((record.accepted_year, record.num_pages) for record in get_paid_records())
    )
    paid = payments_per_year()
    assert pages.labels == paid.labels
    return Series(
        "payment_rate",
        pages.labels,
        tuple(
            round(amount / num_pages, _CENTS)
            for amount, num_pages in zip(paid.values, pages.values, strict=True)
        ),
    )


def stories_per_series() -> Series:
    """Count the Fantagraphics entries in each series, most numerous first."""
    counts: dict[str, int] = {}
    for info in ALL_FANTA_COMIC_BOOK_INFO.values():
        series = info.series_name or "Unknown"
        counts[series] = counts.get(series, 0) + 1
    return _ranked("stories_per_series", counts, len(counts))


def top_characters(top_n: int = TOP_N) -> Series:
    """Rank the characters by the number of stories they are tagged in."""
    return _ranked("top_characters", _tag_counts(TagCategories.CHARACTERS), top_n)


def top_locations(top_n: int = TOP_N) -> Series:
    """Rank the places by the number of stories they are tagged in."""
    return _ranked("top_locations", _tag_counts(TagCategories.PLACES), top_n)


def all_series() -> list[Series]:
    """Compute every chart's series, in the order the screen lists the charts."""
    return [
        stories_per_year(),
        pages_per_year(),
        payments_per_year(),
        payment_rate(),
        stories_per_series(),
        top_characters(),
        top_locations(),
    ]


def stories_submitted_in(start_year: int, end_year: int) -> list[ComicBookInfo]:
    """Return the stories submitted in the years from start_year to end_year inclusive.

    The word-cloud eras are cut from this, so they cover every story and not only
    the ones Barks titled himself.
    """
    return [info for info in get_stories() if start_year <= info.submitted_year <= end_year]


def dump_series(series: list[Series]) -> str:
    """Serialize the series as the JSON text of the sidecar."""
    return json.dumps(
        [{"name": s.name, "labels": s.labels, "values": s.values} for s in series], indent=2
    )


def load_series(text: str) -> list[Series]:
    """Read the series back from the sidecar's JSON text."""
    return [
        Series(item["name"], tuple(item["labels"]), tuple(item["values"]))
        for item in json.loads(text)
    ]


def _per_year(name: str, items: Iterable[tuple[int, int | float]]) -> Series:
    """Sum the (year, amount) pairs by year, ascending; the amounts' type is kept."""
    totals: dict[int, int | float] = {}
    for year, amount in items:
        totals[year] = totals.get(year, 0) + amount
    years = sorted(totals)
    return Series(name, tuple(years), tuple(totals[year] for year in years))


def _ranked(name: str, counts: dict[str, int], top_n: int) -> Series:
    """Order the counts largest first, ties by name so the series is stable run to run."""
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:top_n]
    return Series(name, tuple(k for k, _ in ranked), tuple(v for _, v in ranked))


def _tag_counts(category: TagCategories) -> dict[str, int]:
    """Count the titles tagged with each tag of a category, leaving out untagged tags."""
    return {
        tag.value: len(BARKS_TAGGED_TITLES[tag])
        for tag in get_all_tags_in_tag_category(category) - PART_TAGS
        if BARKS_TAGGED_TITLES.get(tag)
    }
