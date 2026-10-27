"""Which page of a comic is current, and the moves between them. Kivy-free."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from . import log_markers
from .reader_consts_and_types import COMIC_BEGIN_PAGE

if TYPE_CHECKING:
    from collections import OrderedDict
    from collections.abc import Callable

    from .comic_book_page_info import ComicLayout, PageInfo
    from .display_unit import DisplayUnit


class ComicPageManager:
    """The state and navigation logic of a comic book's pages.

    Which page is current, the first and last, the one to open at, and the page
    pairs of double-page mode. The pages, their indexes and their pairs are the
    comic's :class:`ComicLayout`'s; this adds only the position in them.
    `on_page_change` is called whenever the current page index changes (not when it
    is set to what it already is), as a Kivy property would tell its bound callback.
    """

    def __init__(self, on_page_change: Callable[[], None]) -> None:
        """Start with no comic: no layout, and no page current.

        Args:
            on_page_change: Called after every change of the current page index.

        """
        self._on_page_change = on_page_change
        self._current_page_index_value = -1

        self._layout: ComicLayout | None = None
        self._first_page_to_read_index = -1

        self._first_page_index = -1
        self._last_page_index = -1

        self.double_page_mode: bool = False

    @property
    def page_map(self) -> OrderedDict[str, PageInfo] | None:
        """The comic's pages by name, in reading order, or None with no comic set."""
        return None if self._layout is None else self._layout.page_map

    @property
    def _display_units(self) -> list[DisplayUnit]:
        return [] if self._layout is None else self._layout.display_units

    def _unit_idx_for(self, page_index: int) -> int | None:
        return None if self._layout is None else self._layout.unit_idx_for(page_index)

    def get_current_page_index(self) -> int:
        """Return the current page's index, or -1 with no page current."""
        return self._current_page_index

    def reset_current_page_index(self) -> None:
        """Make no page current, as before a comic is opened or after it is closed."""
        self._current_page_index = -1

    def get_current_page_str(self) -> str:
        """Return the current page's name ("5", "3b"), or "" with no page current."""
        return self.get_page_str(self._current_page_index)

    def get_page_str(self, page_index: int) -> str:
        """Return the name of the page at `page_index`, or "" for an index off the comic."""
        if self._layout is None:
            return ""
        page = self._layout.page_by_index(page_index)
        return "" if page is None else page.display_page_num

    def get_current_display_unit(self) -> DisplayUnit | None:
        """Return the display unit that contains the current page index."""
        unit_idx = self._unit_idx_for(self._current_page_index)
        if unit_idx is None:
            return None

        return self._display_units[unit_idx]

    def set_current_page_index_from_str(self, page_str: str) -> None:
        """Make the page named `page_str` current: in double-page mode, its pair's left page.

        Args:
            page_str: The page's name in the page map.

        """
        assert self._layout is not None
        page_index = self._layout.page_by_display(page_str).page_index

        if self.double_page_mode:
            unit_idx = self._unit_idx_for(page_index)
            if unit_idx is not None:
                self._current_page_index = self._display_units[unit_idx].left_page_index
                return

        self._current_page_index = page_index

    def set_to_first_page_to_read(self) -> None:
        """Make the page the comic opens at current (its pair's left page in double-page mode)."""
        if self.double_page_mode:
            unit_idx = self._unit_idx_for(self._first_page_to_read_index)
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
            unit_idx = self._unit_idx_for(self._current_page_index)
            if unit_idx is None or unit_idx >= len(self._display_units) - 1:
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
            unit_idx = self._unit_idx_for(self._current_page_index)
            if unit_idx is None or unit_idx <= 0:
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

    def set_layout(self, layout: ComicLayout, page_to_first_goto: str) -> None:
        """Take a comic's layout, and the page to open it at.

        Args:
            layout: The comic's pages, indexed from 0 in reading order, with their
                display units: the one source of both, for this and the reader.
            page_to_first_goto: The name of the page to open at, or the comic's beginning.

        """
        self._layout = layout
        page_map = layout.page_map

        self._first_page_to_read_index = (
            0
            if page_to_first_goto == COMIC_BEGIN_PAGE
            else layout.page_by_display(page_to_first_goto).page_index
        )

        self._first_page_index = next(iter(page_map.values())).page_index
        self._last_page_index = next(reversed(page_map.values())).page_index

        assert self._first_page_index == 0
        assert (self._last_page_index + 1) == len(page_map)

    def get_first_pages_to_read(self) -> list[int]:
        """Return the indices of the pages the comic opens on, in reading order.

        One page, or in double-page mode both pages of the pair the opening page is
        in: the reader shows nothing until every one of them has loaded.
        """
        assert self._layout is not None
        if self.double_page_mode:
            unit_idx = self._unit_idx_for(self._first_page_to_read_index)
            if unit_idx is not None:
                unit = self._display_units[unit_idx]
                if unit.right_page_index is not None:
                    return [unit.left_page_index, unit.right_page_index]
                return [unit.left_page_index]

        return [self._first_page_to_read_index]

    def get_image_load_order(self) -> list[str]:
        """Determine the optimal order to load images for a smooth user experience.

        The pages the comic opens on come first (see :meth:`get_first_pages_to_read`),
        then the page before them for an immediate turn back, then every page after
        them, then the rest of the pages before them, nearest first.
        """
        assert self._layout is not None
        first_pages = self.get_first_pages_to_read()
        first, last = first_pages[0], first_pages[-1]

        image_load_order = [self.get_page_str(page_index) for page_index in first_pages]

        if first > 0:
            image_load_order.append(self.get_page_str(first - 1))

        image_load_order.extend(
            self.get_page_str(page_index)
            for page_index in range(last + 1, self._last_page_index + 1)
        )

        image_load_order.extend(
            self.get_page_str(page_index) for page_index in range(first - 2, -1, -1)
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
