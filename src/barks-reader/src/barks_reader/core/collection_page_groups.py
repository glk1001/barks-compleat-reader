"""Year-range page groups for the synthetic one-pager / cover collections.

The "All One-Pagers" and "All Covers" collections are large (128 / 186 pages).
Loading the whole collection to view a single member is expensive in RAM, so the
reader opens only the member's *year-range group* — the same grouping the tree
uses. Each group is a contiguous run of 1-based collection page positions (the
located-list order is chronological, and the year ranges partition it).

This module maps a collection member's page number to its group's page range.
Pure ``barks_reader.core`` — no Kivy, no UI.
"""

from __future__ import annotations

from functools import cache
from itertools import pairwise

from barks_fantagraphics.barks_covers import COVER_BY_TITLE, get_located_covers
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import get_located_one_pagers
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO

from .reader_consts_and_types import COVER_YEAR_RANGES, ONE_PAGER_YEAR_RANGES


def year_range_group_index(submitted_year: int, year_ranges: list[tuple[int, int]]) -> int:
    """Index of the year-range group containing *submitted_year*.

    Undated (``-1``) or otherwise out-of-range years fold into the **final**
    group. This is the single source of truth for the fold rule, shared by the
    tree goto-navigation and the collection page-group slicing.
    """
    for index, (start, end) in enumerate(year_ranges):
        if start <= submitted_year <= end:
            return index
    return len(year_ranges) - 1


def year_range_group(submitted_year: int, year_ranges: list[tuple[int, int]]) -> tuple[int, int]:
    """Return the ``(start, end)`` range containing *submitted_year* (undated → final)."""
    return year_ranges[year_range_group_index(submitted_year, year_ranges)]


def _submitted_year(title: Titles) -> int:
    return ALL_FANTA_COMIC_BOOK_INFO[title].comic_book_info.submitted_year


def _group_ranges(
    located_titles: list[Titles], year_ranges: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    """Contiguous 1-based ``(first, last)`` page ranges, one per non-empty group.

    *located_titles* is the collection's page order (position 1..N). The ranges
    must tile ``1..N`` exactly (asserted), so no member can silently fall outside
    every group.
    """
    first_last: dict[int, tuple[int, int]] = {}
    for position, title in enumerate(located_titles, start=1):
        group = year_range_group_index(_submitted_year(title), year_ranges)
        low, high = first_last.get(group, (position, position))
        first_last[group] = (min(low, position), max(high, position))

    ranges = [first_last[group] for group in sorted(first_last)]
    _assert_tiling(ranges, len(located_titles))
    return ranges


def _assert_tiling(ranges: list[tuple[int, int]], total: int) -> None:
    assert ranges, "no collection page groups"
    assert ranges[0][0] == 1, f"groups must start at page 1, got {ranges[0][0]}"
    assert ranges[-1][1] == total, f"groups must end at page {total}, got {ranges[-1][1]}"
    for (_, prev_end), (start, _) in pairwise(ranges):
        assert start == prev_end + 1, (
            f"collection page groups are not contiguous: {prev_end} -> {start}"
        )


@cache
def get_cover_collection_group_ranges() -> list[tuple[int, int]]:
    """Contiguous page ranges of the cover collection's year-range groups."""
    title_by_cover = {cover: title for title, cover in COVER_BY_TITLE.items()}
    located = [title_by_cover[cover] for cover in get_located_covers()]
    return _group_ranges(located, COVER_YEAR_RANGES)


@cache
def get_one_pager_collection_group_ranges() -> list[tuple[int, int]]:
    """Contiguous page ranges of the one-pager collection's year-range groups."""
    return _group_ranges(list(get_located_one_pagers()), ONE_PAGER_YEAR_RANGES)


def get_collection_group_page_range(collection_title: Titles, page_num: int) -> tuple[int, int]:
    """Return the ``(first, last)`` page range of *page_num*'s year-range group.

    Args:
        collection_title: ``Titles.ALL_COVERS`` or ``Titles.ALL_ONE_PAGERS``.
        page_num: The member's 1-based page number within the collection.

    Returns:
        The inclusive 1-based page range of the group containing *page_num*.

    Raises:
        ValueError: If *collection_title* is not a supported collection, or
            *page_num* is outside every group.

    """
    if collection_title == Titles.ALL_COVERS:
        ranges = get_cover_collection_group_ranges()
    elif collection_title == Titles.ALL_ONE_PAGERS:
        ranges = get_one_pager_collection_group_ranges()
    else:
        msg = f"Not a grouped collection: {collection_title}."
        raise ValueError(msg)

    for first, last in ranges:
        if first <= page_num <= last:
            return first, last

    msg = f"Page {page_num} is outside every group of {collection_title}."
    raise ValueError(msg)
