"""Which page is current and the moves between them (barks_reader.core.comic_page_manager)."""

# ruff: noqa: PLR2004, SLF001

from __future__ import annotations

from collections import OrderedDict
from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.comics_consts import PageType
from barks_reader.core.comic_book_page_info import PageInfo
from barks_reader.core.comic_page_manager import ComicPageManager
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE


class TestComicPageManager:
    @pytest.fixture
    def page_manager(self) -> tuple[ComicPageManager, MagicMock]:
        callback = MagicMock()
        pm = ComicPageManager(callback)
        return pm, callback

    def test_set_page_map(self, page_manager: tuple[ComicPageManager, MagicMock]) -> None:
        pm, _ = page_manager

        # Create a dummy page map
        page_map = OrderedDict()
        page_map["1"] = PageInfo(
            page_index=0,
            page_type=PageType.BODY,
            display_page_num="1",
            srce_page=MagicMock(),
            dest_page=MagicMock(),
        )
        page_map["2"] = PageInfo(
            page_index=1,
            page_type=PageType.BODY,
            display_page_num="2",
            srce_page=MagicMock(),
            dest_page=MagicMock(),
        )
        page_map["3"] = PageInfo(
            page_index=2,
            page_type=PageType.BODY,
            display_page_num="3",
            srce_page=MagicMock(),
            dest_page=MagicMock(),
        )

        pm.set_page_map(page_map, COMIC_BEGIN_PAGE)

        assert pm._first_page_index == 0
        assert pm._last_page_index == 2
        assert (
            pm._current_page_index == -1
        )  # It doesn't set current page index, just first_page_to_read_index
        assert pm._first_page_to_read_index == 0

        pm.set_to_first_page_to_read()
        assert pm._current_page_index == 0

    def test_navigation(self, page_manager: tuple[ComicPageManager, MagicMock]) -> None:
        pm, _ = page_manager
        page_map = OrderedDict()
        for i in range(5):
            page_map[str(i)] = PageInfo(
                page_index=i,
                page_type=PageType.BODY,
                display_page_num=str(i),
                srce_page=MagicMock(),
                dest_page=MagicMock(),
            )

        pm.set_page_map(page_map, COMIC_BEGIN_PAGE)
        pm.set_to_first_page_to_read()  # index 0

        pm.next_page()
        assert pm._current_page_index == 1

        pm.prev_page()
        assert pm._current_page_index == 0

        pm.prev_page()  # Should stay at 0
        assert pm._current_page_index == 0

        pm.goto_last_page()
        assert pm._current_page_index == 4

        pm.next_page()  # Should stay at 4
        assert pm._current_page_index == 4

        pm.goto_start_page()
        assert pm._current_page_index == 0

    def test_the_page_edges_log_the_same_markers_in_double_page_mode(
        self, page_manager: tuple[ComicPageManager, MagicMock], loguru_sink: list[str]
    ) -> None:
        """A GUI test waits on the edge lines whichever mode the reader booted in."""
        pm, _ = page_manager
        page_map = OrderedDict()
        for i in range(5):  # units (0, 1), (2, 3), (4)
            page_map[str(i)] = PageInfo(
                page_index=i,
                page_type=PageType.BODY,
                display_page_num=str(i),
                srce_page=MagicMock(),
                dest_page=MagicMock(),
            )
        pm.set_page_map(page_map, COMIC_BEGIN_PAGE)
        pm.double_page_mode = True
        pm.set_to_first_page_to_read()

        pm.prev_page()
        assert pm._current_page_index == 0
        assert "Already on the first page: current index = 0." in loguru_sink

        pm.goto_last_page()
        assert pm._current_page_index == 4
        pm.next_page()
        assert pm._current_page_index == 4
        assert "Already on the last page: current index = 4." in loguru_sink

    def test_get_image_load_order(self, page_manager: tuple[ComicPageManager, MagicMock]) -> None:
        pm, _ = page_manager
        page_map = OrderedDict()
        for i in range(5):
            page_map[str(i)] = PageInfo(
                page_index=i,
                page_type=PageType.BODY,
                display_page_num=str(i),
                srce_page=MagicMock(),
                dest_page=MagicMock(),
            )

        # Case 1: Start at beginning
        pm.set_page_map(page_map, COMIC_BEGIN_PAGE)
        order = pm.get_image_load_order()
        assert order == ["0", "1", "2", "3", "4"]

        # Case 2: Start in middle (index 2)
        pm.set_page_map(page_map, "2")
        order = pm.get_image_load_order()
        # Expected: Current(2), Prev(1), Next...(3,4), Prev...(0)
        # 2, 1, 3, 4, 0
        assert order == ["2", "1", "3", "4", "0"]

    def test_no_display_unit_before_the_page_map_or_off_it(
        self, page_manager: tuple[ComicPageManager, MagicMock]
    ) -> None:
        """Before a comic has pages, and on a page no unit holds, there is no unit."""
        pm, _ = page_manager
        assert pm.get_current_display_unit() is None

        page_map = OrderedDict(
            (
                str(i),
                PageInfo(
                    page_index=i,
                    page_type=PageType.BODY,
                    display_page_num=str(i),
                    srce_page=MagicMock(),
                    dest_page=MagicMock(),
                ),
            )
            for i in range(4)
        )
        pm.set_page_map(page_map, COMIC_BEGIN_PAGE)
        assert pm.get_current_page_index() == -1  # no page chosen yet
        assert pm.get_current_display_unit() is None

        pm.set_to_first_page_to_read()
        unit = pm.get_current_display_unit()
        assert unit is not None
        assert unit.left_page_index == 0

    def test_a_change_of_page_is_told_once_and_a_repeat_not_at_all(
        self, page_manager: tuple[ComicPageManager, MagicMock]
    ) -> None:
        """As the Kivy property it replaced: the reader redraws on a change only."""
        pm, on_change = page_manager
        page_map = OrderedDict()
        for i in range(3):
            page_map[str(i)] = PageInfo(
                page_index=i,
                page_type=PageType.BODY,
                display_page_num=str(i),
                srce_page=MagicMock(),
                dest_page=MagicMock(),
            )
        pm.set_page_map(page_map, COMIC_BEGIN_PAGE)
        on_change.assert_not_called()

        pm.set_to_first_page_to_read()
        assert on_change.call_count == 1

        pm.goto_start_page()  # already there
        pm.reset_current_page_index()
        pm.reset_current_page_index()  # already reset
        assert on_change.call_count == 2
