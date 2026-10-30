from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from .comic_book_page_info import PageInfo


@dataclass(frozen=True, slots=True)
class DisplayUnit:
    """Represents one reading unit: either a solo page or a left+right page pair."""

    left_page_index: int
    right_page_index: int | None


def build_display_units(
    page_map: Mapping[str, PageInfo],
) -> tuple[list[DisplayUnit], dict[int, int]]:
    """Group a comic's pages into the units double-page mode shows.

    A solo page stands alone, and so do the page before one and the last page; the
    rest pair off in reading order.

    Args:
        page_map: The comic's pages by name, in reading order, indexed from 0.

    Returns:
        The units in order, and each page index's unit.

    """
    pages = list(page_map.values())
    return _pair_off(len(pages), lambda i: pages[i].is_solo or pages[i + 1].is_solo)


def build_document_units(page_count: int) -> tuple[list[DisplayUnit], dict[int, int]]:
    """Group a document's pages into the units the two-page spread shows.

    The reader's pairing without a page map: the pages pair off in reading order from
    the first (a document has no cover to stand alone), and an odd last page stands
    alone.

    Args:
        page_count: The document's number of pages.

    Returns:
        The units in order, and each page index's unit.

    """
    return _pair_off(page_count, lambda _i: False)


def _pair_off(
    page_count: int, stands_alone: Callable[[int], bool]
) -> tuple[list[DisplayUnit], dict[int, int]]:
    """Walk the pages in order, pairing each with the next unless it stands alone.

    The last page always stands alone, nothing following it; `stands_alone` is asked
    of a page only when one follows, so it may look at the next page.
    """
    units: list[DisplayUnit] = []
    unit_idx_for_index: dict[int, int] = {}

    i = 0
    while i < page_count:
        unit_idx = len(units)
        if i + 1 >= page_count or stands_alone(i):
            units.append(DisplayUnit(i, None))
            unit_idx_for_index[i] = unit_idx
            i += 1
        else:
            units.append(DisplayUnit(i, i + 1))
            unit_idx_for_index[i] = unit_idx
            unit_idx_for_index[i + 1] = unit_idx
            i += 2

    return units, unit_idx_for_index
