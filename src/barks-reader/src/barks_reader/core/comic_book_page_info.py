from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from barks_fantagraphics.comic_book_info import is_covers_collection
from barks_fantagraphics.comics_consts import SOLO_PAGE_TYPES, PageType
from barks_fantagraphics.pages import FRONT_MATTER_PAGES, ROMAN_NUMERALS

from .display_unit import DisplayUnit
from .reader_consts_and_types import FIRST_BODY_PAGE
from .saved_page_info import SavedPageInfo

if TYPE_CHECKING:
    from barks_fantagraphics.comic_book import ComicBook
    from barks_fantagraphics.page_classes import CleanPage, RequiredDimensions, SrceAndDestPages

    from .page_info_ports import RequiredDimensionsPort, SortedPagesPort


@dataclass(frozen=True, slots=True)
class PageInfo:
    page_index: int
    display_page_num: str
    page_type: PageType
    srce_page: CleanPage
    dest_page: CleanPage
    is_solo: bool = False


def slice_page_map(
    page_map: OrderedDict[str, PageInfo], first_page_num: int, last_page_num: int
) -> OrderedDict[str, PageInfo]:
    """Return the sub-map of pages whose global number is in ``[first, last]``.

    Used to open only a contiguous slice of a large synthetic collection (a
    year-range group of "All Covers" / "All One-Pagers") without loading the
    whole thing. ``page_index`` is renumbered ``0..n-1`` so the slice satisfies
    the reader's contiguity requirement, while ``display_page_num`` (the map key
    and the global position each page maps back to a title through) is kept
    unchanged.

    Args:
        page_map: The full collection page map, keyed by global 1-based
            ``display_page_num``.
        first_page_num: Inclusive first global page number to keep.
        last_page_num: Inclusive last global page number to keep.

    Returns:
        A new ``OrderedDict`` with only the selected pages, ``page_index``
        renumbered from 0, preserving order and keys.

    """
    sliced: OrderedDict[str, PageInfo] = OrderedDict()
    for display_page_num, page_info in page_map.items():
        if first_page_num <= int(display_page_num) <= last_page_num:
            sliced[display_page_num] = replace(page_info, page_index=len(sliced))
    return sliced


class ComicLayout:
    """Immutable view of a paginated comic.

    Owns page lookups (by display number, by index), the ordered list of
    display units for double-page mode, the "inside body pages" predicate,
    and ``SavedPageInfo`` conversion.
    """

    __slots__ = (
        "_display_units",
        "_index_to_page",
        "_last_body_page",
        "_page_map",
        "_unit_idx_for_index",
    )

    def __init__(
        self,
        page_map: OrderedDict[str, PageInfo],
        last_body_page: str,
    ) -> None:
        self._page_map = page_map
        self._last_body_page = last_body_page
        self._index_to_page: dict[int, PageInfo] = {p.page_index: p for p in page_map.values()}
        self._display_units, self._unit_idx_for_index = _build_display_units(page_map)

    @property
    def page_map(self) -> OrderedDict[str, PageInfo]:
        return self._page_map

    @property
    def last_body_page(self) -> str:
        return self._last_body_page

    @property
    def display_units(self) -> list[DisplayUnit]:
        return self._display_units

    def page_by_display(self, display_page_num: str) -> PageInfo:
        return self._page_map[display_page_num]

    def page_by_index(self, page_index: int) -> PageInfo | None:
        return self._index_to_page.get(page_index)

    def unit_idx_for(self, page_index: int) -> int | None:
        return self._unit_idx_for_index.get(page_index)

    def is_inside_body(self, page: PageInfo) -> bool:
        return page.page_type == PageType.BODY and page.display_page_num not in (
            FIRST_BODY_PAGE,
            self._last_body_page,
        )

    def to_saved(self, page: PageInfo) -> SavedPageInfo:
        return SavedPageInfo(
            page.page_index,
            page.display_page_num,
            page.page_type,
            self._last_body_page,
        )

    def resolve_last_read(
        self,
        current_page_display_num: str,
        current_display_unit: DisplayUnit | None,
        double_page_mode: bool,
    ) -> SavedPageInfo:
        """Pick the saved page for the current reading position.

        In double-page mode with a full pair, prefer the right page (furthest
        progress) unless the left page is an edge page (cover, first body page,
        last body page, back matter) — in that case pick left so the save
        logic resets to the beginning.
        """
        last_read = self._page_map[current_page_display_num]
        if (
            double_page_mode
            and current_display_unit is not None
            and current_display_unit.right_page_index is not None
        ):
            left = self.page_by_index(current_display_unit.left_page_index)
            right = self.page_by_index(current_display_unit.right_page_index)
            if left is not None and not self.is_inside_body(left):
                last_read = left
            elif right is not None:
                last_read = right
        return self.to_saved(last_read)


def slice_comic_layout(layout: ComicLayout, first_page_num: int, last_page_num: int) -> ComicLayout:
    """Return a layout holding only pages ``[first, last]`` of a collection.

    Used to open a year-range group of a large single-page-only collection ("All
    Covers"/"All One-Pagers") instead of the whole thing. Both the reader and the
    last-read-page tracker consume this one layout, so slicing here keeps their
    page indices consistent. Those collections are all body/cover pages, so the
    slice's last body page is simply its last page.
    """
    sliced_map = slice_page_map(layout.page_map, first_page_num, last_page_num)
    assert sliced_map, f"empty collection slice for page range [{first_page_num}, {last_page_num}]"
    last_body_page = next(reversed(sliced_map))
    return ComicLayout(sliced_map, last_body_page)


class ComicLayoutBuilder:
    """Builds a :class:`ComicLayout` for a comic.

    Takes a :class:`SortedPagesPort` (required) and an optional
    :class:`RequiredDimensionsPort`. The dimensions port is queried via
    :meth:`get_required_dimensions` and is split out so prebuilt-comic flows
    can skip the panel-segment I/O entirely by omitting the port.
    """

    def __init__(
        self,
        sorted_pages_port: SortedPagesPort,
        required_dimensions_port: RequiredDimensionsPort | None = None,
    ) -> None:
        self._sorted_pages_port = sorted_pages_port
        self._required_dimensions_port = required_dimensions_port

    def build(self, comic: ComicBook) -> ComicLayout:
        srce_and_dest_pages = self._sorted_pages_port.get_sorted_pages(comic)
        page_map, last_body_page = _build_page_map(comic, srce_and_dest_pages)
        return ComicLayout(page_map, last_body_page)

    def get_required_dimensions(self, comic: ComicBook) -> RequiredDimensions:
        if self._required_dimensions_port is None:
            msg = "RequiredDimensionsPort was not wired"
            raise RuntimeError(msg)
        return self._required_dimensions_port.get_required_dimensions(comic)


def _build_page_map(
    comic: ComicBook,
    srce_and_dest_pages: SrceAndDestPages,
) -> tuple[OrderedDict[str, PageInfo], str]:
    page_map: OrderedDict[str, PageInfo] = OrderedDict()
    last_body_page = ""
    body_start_page_num = -1
    orig_page_num = 0 if srce_and_dest_pages.srce_pages[0].page_type == PageType.FRONT else 1

    # The "All Covers" collection is all COVER pages (a COVER is normally front
    # matter), but each cover is a numbered entry, so number them 1..N like body
    # pages - the deep-link from a cover node navigates to "1".."N".
    is_covers = is_covers_collection(comic.fanta_info.comic_book_info.title)

    for index, (srce_page, dest_page) in enumerate(
        zip(srce_and_dest_pages.srce_pages, srce_and_dest_pages.dest_pages, strict=False)
    ):
        page_starts_body = is_covers or dest_page.page_type not in FRONT_MATTER_PAGES
        if page_starts_body and body_start_page_num == -1:
            body_start_page_num = orig_page_num

        if body_start_page_num == -1:
            display_page_num = "0" if orig_page_num == 0 else ROMAN_NUMERALS[orig_page_num]
        else:
            display_page_num = str(orig_page_num - body_start_page_num + 1)
            if is_covers or dest_page.page_type == PageType.BODY:
                last_body_page = display_page_num

        page_key = Path(srce_page.page_filename).stem
        is_solo = dest_page.page_type in SOLO_PAGE_TYPES or page_key in comic.solo_page_keys
        page_map[display_page_num] = PageInfo(
            index,
            display_page_num,
            dest_page.page_type,
            srce_page,
            dest_page,
            is_solo,
        )

        orig_page_num += 1

    return page_map, last_body_page


def _build_display_units(
    page_map: OrderedDict[str, PageInfo],
) -> tuple[list[DisplayUnit], dict[int, int]]:
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
