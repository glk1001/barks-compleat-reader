"""Which page of a comic is current, and the moves between them. Kivy-free."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from . import log_markers
from .display_unit import DisplayUnit
from .reader_consts_and_types import COMIC_BEGIN_PAGE

if TYPE_CHECKING:
    from collections import OrderedDict
    from collections.abc import Callable

    from .comic_book_page_info import PageInfo


class ComicPageManager:
    """The state and navigation logic of a comic book's pages.

    Which page is current, the first and last, the one to open at, and the page
    pairs of double-page mode. `on_page_change` is called whenever the current page
    index changes (not when it is set to what it already is), as a Kivy property
    would tell its bound callback.
    """

    def __init__(self, on_page_change: Callable[[], None]) -> None:
        """Start with no comic: no page map, and no page current.

        Args:
            on_page_change: Called after every change of the current page index.

        """
        self._on_page_change = on_page_change
        self._current_page_index_value = -1

        self.page_map: OrderedDict[str, PageInfo] | None = None
        self._index_to_page_map: dict[int, str] = {}
        self._first_page_to_read_index = -1

        self._first_page_index = -1
        self._last_page_index = -1

        self._display_units: list[DisplayUnit] = []
        self._page_index_to_unit_idx: dict[int, int] = {}
        self.double_page_mode: bool = False

    def get_current_page_index(self) -> int:
        """Return the current page's index, or -1 with no page current."""
        return self._current_page_index

    def reset_current_page_index(self) -> None:
        """Make no page current, as before a comic is opened or after it is closed."""
        self._current_page_index = -1

    def get_current_page_str(self) -> str:
        """Return the current page's name ("5", "3b"), or "" with no page current."""
        return self._index_to_page_map.get(self._current_page_index, "")

    def get_current_display_unit(self) -> DisplayUnit | None:
        """Return the display unit that contains the current page index."""
        if not self._display_units:
            return None

        unit_idx = self._page_index_to_unit_idx.get(self._current_page_index)
        if unit_idx is None:
            return None

        return self._display_units[unit_idx]

    def set_current_page_index_from_str(self, page_str: str) -> None:
        """Make the page named `page_str` current: in double-page mode, its pair's left page.

        Args:
            page_str: The page's name in the page map.

        """
        assert self.page_map is not None
        page_index = self.page_map[page_str].page_index

        if self.double_page_mode and self._display_units:
            unit_idx = self._page_index_to_unit_idx.get(page_index)
            if unit_idx is not None:
                self._current_page_index = self._display_units[unit_idx].left_page_index
                return

        self._current_page_index = page_index

    def set_to_first_page_to_read(self) -> None:
        """Make the page the comic opens at current (its pair's left page in double-page mode)."""
        if self.double_page_mode and self._display_units:
            unit_idx = self._page_index_to_unit_idx.get(self._first_page_to_read_index)
            if unit_idx is not None:
                self._current_page_index = self._display_units[unit_idx].left_page_index
                return

        self._current_page_index = self._first_page_to_read_index

    def goto_start_page(self) -> None:
        """Make the first page current, logging when it already is."""
        first_idx = (
            self._display_units[0].left_page_index
            if self.double_page_mode and self._display_units
            else self._first_page_index
        )
        if self._current_page_index == first_idx:
            logger.debug(log_markers.ALREADY_ON_FIRST_PAGE.format(index=self._current_page_index))
        else:
            logger.debug(log_markers.GOTO_START_PAGE.format(index=first_idx))
            self._current_page_index = first_idx

    def goto_last_page(self) -> None:
        """Make the last page (or page pair) current, logging when it already is."""
        last_idx = (
            self._display_units[-1].left_page_index
            if self.double_page_mode and self._display_units
            else self._last_page_index
        )
        if self._current_page_index == last_idx:
            logger.debug(log_markers.ALREADY_ON_LAST_PAGE.format(index=self._current_page_index))
        else:
            logger.debug(log_markers.GOTO_LAST_PAGE.format(index=last_idx))
            self._current_page_index = last_idx

    def next_page(self) -> None:
        """Make the next page (or page pair) current, logging when there is none."""
        if self.double_page_mode and self._display_units:
            unit_idx = self._page_index_to_unit_idx.get(self._current_page_index, -1)
            if unit_idx < 0 or unit_idx >= len(self._display_units) - 1:
                logger.debug(
                    log_markers.ALREADY_ON_LAST_PAGE.format(index=self._current_page_index)
                )
            else:
                next_unit = self._display_units[unit_idx + 1]
                logger.debug(f"Next unit: left_page_index = {next_unit.left_page_index}.")
                self._current_page_index = next_unit.left_page_index
        elif self._current_page_index >= self._last_page_index:
            logger.debug(log_markers.ALREADY_ON_LAST_PAGE.format(index=self._current_page_index))
        else:
            logger.debug(f"Next page: requested index = {self._current_page_index + 1}")
            self._current_page_index += 1

    def prev_page(self) -> None:
        """Make the previous page (or page pair) current, logging when there is none."""
        if self.double_page_mode and self._display_units:
            unit_idx = self._page_index_to_unit_idx.get(self._current_page_index, -1)
            if unit_idx <= 0:
                logger.debug(
                    log_markers.ALREADY_ON_FIRST_PAGE.format(index=self._current_page_index)
                )
            else:
                prev_unit = self._display_units[unit_idx - 1]
                logger.debug(f"Prev unit: left_page_index = {prev_unit.left_page_index}.")
                self._current_page_index = prev_unit.left_page_index
        elif self._current_page_index <= self._first_page_index:
            logger.debug(log_markers.ALREADY_ON_FIRST_PAGE.format(index=self._current_page_index))
        else:
            logger.debug(f"Prev page: requested index = {self._current_page_index - 1}")
            self._current_page_index -= 1

    def set_page_map(self, page_map: OrderedDict[str, PageInfo], page_to_first_goto: str) -> None:
        """Take a comic's pages, and the page to open it at.

        Args:
            page_map: The comic's pages by name, in reading order, indexed from 0.
            page_to_first_goto: The name of the page to open at, or the comic's beginning.

        """
        self.page_map = page_map
        assert self.page_map is not None
        self._index_to_page_map: dict[int, str] = {
            page_info.page_index: page_str for page_str, page_info in page_map.items()
        }

        self._first_page_to_read_index = (
            0
            if page_to_first_goto == COMIC_BEGIN_PAGE
            else self.page_map[page_to_first_goto].page_index
        )

        self._first_page_index = next(iter(self.page_map.values())).page_index
        self._last_page_index = next(reversed(self.page_map.values())).page_index

        assert self._first_page_index == 0
        assert (self._last_page_index + 1) == len(self.page_map)

        self._build_display_units(page_map)

    def _build_display_units(self, page_map: OrderedDict[str, PageInfo]) -> None:
        """Pre-compute display units for double-page mode from the page map."""
        pages = list(page_map.values())
        self._display_units = []
        self._page_index_to_unit_idx = {}

        i = 0
        while i < len(pages):
            if pages[i].is_solo or (i + 1 >= len(pages)) or pages[i + 1].is_solo:
                unit_idx = len(self._display_units)
                self._display_units.append(DisplayUnit(i, None))
                self._page_index_to_unit_idx[i] = unit_idx
                i += 1
            else:
                unit_idx = len(self._display_units)
                self._display_units.append(DisplayUnit(i, i + 1))
                self._page_index_to_unit_idx[i] = unit_idx
                self._page_index_to_unit_idx[i + 1] = unit_idx
                i += 2

    def get_image_load_order(self) -> list[str]:
        """Determine the optimal order to load images for a smooth user experience."""
        assert self.page_map is not None
        if self._first_page_to_read_index == 0:
            return list(self.page_map.keys())

        # Start with the current page
        image_load_order = [self._index_to_page_map[self._first_page_to_read_index]]

        # Then the previous page (for immediate back navigation): there is one, as a
        # start at index 0 returned above.
        image_load_order.append(self._index_to_page_map[self._first_page_to_read_index - 1])

        # Then all subsequent pages.
        image_load_order.extend(
            self._index_to_page_map[page_index]
            for page_index in range(self._first_page_to_read_index + 1, self._last_page_index + 1)
        )

        # Finally, the rest of the previous pages in reverse order.
        image_load_order.extend(
            self._index_to_page_map[page_index]
            for page_index in range(self._first_page_to_read_index - 2, -1, -1)
        )

        return image_load_order

    @property
    def _current_page_index(self) -> int:
        return self._current_page_index_value

    @_current_page_index.setter
    def _current_page_index(self, index: int) -> None:
        if index == self._current_page_index_value:
            return
        self._current_page_index_value = index
        self._on_page_change()
