"""Where a title sits in the reader tree: which year-range group holds its row."""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_fantagraphics.comic_book_info import COVERS_SET, ONE_PAGERS

from barks_reader.core.collection_page_groups import year_range_group
from barks_reader.core.reader_consts_and_types import (
    CHRONO_YEAR_RANGES,
    COVER_YEAR_RANGES,
    ONE_PAGER_YEAR_RANGES,
)

from .destinations import YearRangeKind

if TYPE_CHECKING:
    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo

type YearRangeKey = tuple[YearRangeKind, tuple[int, int]]
"""A year-range group of the tree: its section and its inclusive years."""


def title_year_range(title: Titles, fanta_info: FantaComicBookInfo) -> YearRangeKey:
    """Return the year-range group of the tree that holds `title`'s row.

    One-pagers and covers live under their own series node, each split into
    year-range groups; an undated one folds into the last group. Every other title
    lives under its chronological year-range group.

    Args:
        title: The title to place.
        fanta_info: The title's Fantagraphics info, for its submitted year.

    Returns:
        The group's section (one-pager, cover or chronological) and its years.

    Raises:
        RuntimeError: A chronological title's year is in no group. Chronological
            ranges do not fold a stray year into a group: a miss is a data problem.

    """
    submitted_year = fanta_info.comic_book_info.submitted_year
    if title in ONE_PAGERS:
        return YearRangeKind.ONE_PAGER, year_range_group(submitted_year, ONE_PAGER_YEAR_RANGES)
    if title in COVERS_SET:
        return YearRangeKind.COVER, year_range_group(submitted_year, COVER_YEAR_RANGES)

    for year_range in CHRONO_YEAR_RANGES:
        if year_range[0] <= submitted_year <= year_range[1]:
            return YearRangeKind.CHRONO, year_range

    msg = f"No year range found for {fanta_info.comic_book_info.get_title_str()}."
    raise RuntimeError(msg)
