from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

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
    units: list[DisplayUnit] = []
    unit_idx_for_index: dict[int, int] = {}

    i = 0
    while i < len(pages):
        if pages[i].is_solo or (i + 1 >= len(pages)) or pages[i + 1].is_solo:
            unit_idx = len(units)
            units.append(DisplayUnit(i, None))
            unit_idx_for_index[i] = unit_idx
            i += 1
        else:
            unit_idx = len(units)
            units.append(DisplayUnit(i, i + 1))
            unit_idx_for_index[i] = unit_idx
            unit_idx_for_index[i + 1] = unit_idx
            i += 2

    return units, unit_idx_for_index
