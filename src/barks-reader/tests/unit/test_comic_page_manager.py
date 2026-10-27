"""Which page is current and the moves between them (barks_reader.core.comic_page_manager)."""

# ruff: noqa: PLR2004, SLF001

from __future__ import annotations

from collections import OrderedDict
from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.comics_consts import PageType
from barks_reader.core.comic_book_page_info import ComicLayout, PageInfo
from barks_reader.core.comic_page_manager import ComicPageManager
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE


class TestComicPageManager:
    @pytest.fixture
    def page_manager(self) -> tuple[ComicPageManager, MagicMock]:
        callback = MagicMock()
        pm = ComicPageManager(callback)
        return pm, callback

    def test_set_layout(self, page_manager: tuple[ComicPageManager, MagicMock]) -> None:
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

        pm.set_layout(_layout(page_map), COMIC_BEGIN_PAGE)

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

        pm.set_layout(_layout(page_map), COMIC_BEGIN_PAGE)
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
        pm.set_layout(_layout(page_map), COMIC_BEGIN_PAGE)
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
        pm.set_layout(_layout(page_map), COMIC_BEGIN_PAGE)
        order = pm.get_image_load_order()
        assert order == ["0", "1", "2", "3", "4"]

        # Case 2: Start in middle (index 2)
        pm.set_layout(_layout(page_map), "2")
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
        pm.set_layout(_layout(page_map), COMIC_BEGIN_PAGE)
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
        pm.set_layout(_layout(page_map), COMIC_BEGIN_PAGE)
        on_change.assert_not_called()

        pm.set_to_first_page_to_read()
        assert on_change.call_count == 1

        pm.goto_start_page()  # already there
        pm.reset_current_page_index()
        pm.reset_current_page_index()  # already reset
        assert on_change.call_count == 2


def _page_map(*solo: bool) -> OrderedDict[str, PageInfo]:
    """Return pages "0", "1", ... with indexes 0, 1, ..., solo as `solo` says."""
    return OrderedDict(
        (
            str(i),
            PageInfo(
                page_index=i,
                page_type=PageType.BODY,
                display_page_num=str(i),
                srce_page=MagicMock(),
                dest_page=MagicMock(),
                is_solo=is_solo,
            ),
        )
        for i, is_solo in enumerate(solo)
    )


def _layout(page_map: OrderedDict[str, PageInfo]) -> ComicLayout:
    """Return `page_map` laid out, its last page the last body page."""
    return ComicLayout(page_map, last_body_page=next(reversed(page_map)))


# Units (0), (1, 2), (3), (4), (5, 6): a solo page stands alone, and so does the page
# before one; the last two pair.
_SEVEN_PAGES = (True, False, False, False, True, False, False)


class TestBeforeAComic:
    def test_no_page_is_current_and_the_moves_go_nowhere(self) -> None:
        on_change = MagicMock()
        pm = ComicPageManager(on_change)
        assert pm.page_map is None
        assert pm.double_page_mode is False
        assert pm.get_current_page_index() == -1
        assert pm.get_current_page_str() == ""

        pm.set_to_first_page_to_read()
        pm.goto_start_page()
        pm.goto_last_page()
        assert pm.get_current_page_index() == -1
        on_change.assert_not_called()

    def test_in_double_page_mode_too(self, loguru_sink: list[str]) -> None:
        pm = ComicPageManager(MagicMock())
        pm.double_page_mode = True

        pm.goto_start_page()
        pm.goto_last_page()
        assert pm.get_current_page_index() == -1
        assert loguru_sink == [
            "Already on the first page: current index = -1.",
            "Already on the last page: current index = -1.",
        ]

    def test_next_and_prev_with_pages_but_none_current_go_nowhere(
        self, loguru_sink: list[str]
    ) -> None:
        """In double-page mode a page no unit holds, as -1 is, has no neighbour."""
        pm = ComicPageManager(MagicMock())
        pm.set_layout(_layout(_page_map(*_SEVEN_PAGES)), COMIC_BEGIN_PAGE)
        pm.double_page_mode = True

        pm.next_page()
        assert pm.get_current_page_index() == -1
        assert loguru_sink == ["Already on the last page: current index = -1."]

        loguru_sink.clear()
        pm.prev_page()
        assert pm.get_current_page_index() == -1
        assert loguru_sink == ["Already on the first page: current index = -1."]

    def test_a_reset_leaves_no_page_current(self) -> None:
        pm = ComicPageManager(MagicMock())
        pm.set_layout(_layout(_page_map(*_SEVEN_PAGES)), COMIC_BEGIN_PAGE)
        pm.set_to_first_page_to_read()

        pm.reset_current_page_index()
        assert pm.get_current_page_index() == -1
        assert pm.get_current_page_str() == ""


class TestDoublePageMode:
    @pytest.fixture
    def pm(self) -> ComicPageManager:
        pm = ComicPageManager(MagicMock())
        pm.set_layout(_layout(_page_map(*_SEVEN_PAGES)), COMIC_BEGIN_PAGE)
        pm.double_page_mode = True
        return pm

    def test_solo_pages_and_their_neighbors_stand_alone_and_the_rest_pair(
        self, pm: ComicPageManager
    ) -> None:
        assert pm._layout is not None
        assert [(u.left_page_index, u.right_page_index) for u in pm._layout.display_units] == [
            (0, None),
            (1, 2),
            (3, None),
            (4, None),
            (5, 6),
        ]
        assert [pm._layout.unit_idx_for(i) for i in range(7)] == [0, 1, 1, 2, 3, 4, 4]

    def test_next_and_prev_step_a_unit_at_a_time_and_stop_at_the_ends(
        self, pm: ComicPageManager, loguru_sink: list[str]
    ) -> None:
        pm.set_to_first_page_to_read()
        forward = []
        for _ in range(5):
            pm.next_page()
            forward.append(pm.get_current_page_index())
        assert forward == [1, 3, 4, 5, 5]
        assert "Already on the last page: current index = 5." in loguru_sink

        back = []
        for _ in range(5):
            pm.prev_page()
            back.append(pm.get_current_page_index())
        assert back == [4, 3, 1, 0, 0]
        assert "Already on the first page: current index = 0." in loguru_sink

    def test_start_and_last_are_the_first_and_last_units_left_pages(
        self, pm: ComicPageManager, loguru_sink: list[str]
    ) -> None:
        pm.set_current_page_index_from_str("3")
        pm.goto_last_page()
        assert pm.get_current_page_index() == 5
        assert "Goto last page: requested index = 5." in loguru_sink

        pm.goto_start_page()
        assert pm.get_current_page_index() == 0
        assert "Goto start page: requested index = 0." in loguru_sink

    def test_a_comic_opened_at_a_right_page_opens_at_its_pair(self) -> None:
        pm = ComicPageManager(MagicMock())
        pm.set_layout(_layout(_page_map(*_SEVEN_PAGES)), "2")
        pm.double_page_mode = True

        pm.set_to_first_page_to_read()
        assert pm.get_current_page_index() == 1
        assert pm.get_current_page_str() == "1"

    def test_a_right_page_by_name_is_its_pairs_left(self, pm: ComicPageManager) -> None:
        pm.set_current_page_index_from_str("6")
        assert pm.get_current_page_index() == 5

        pm.set_current_page_index_from_str("4")
        assert pm.get_current_page_index() == 4


class TestSinglePageMode:
    @pytest.fixture
    def pm(self) -> ComicPageManager:
        pm = ComicPageManager(MagicMock())
        pm.set_layout(_layout(_page_map(*_SEVEN_PAGES)), COMIC_BEGIN_PAGE)
        return pm

    def test_next_and_prev_step_a_page_at_a_time_whatever_the_pairs(
        self, pm: ComicPageManager
    ) -> None:
        pm.set_to_first_page_to_read()
        pm.next_page()
        pm.next_page()
        assert pm.get_current_page_index() == 2

    def test_last_is_the_last_page_not_its_pairs_left(
        self, pm: ComicPageManager, loguru_sink: list[str]
    ) -> None:
        pm.set_to_first_page_to_read()
        pm.goto_last_page()
        assert pm.get_current_page_index() == 6
        assert "Goto last page: requested index = 6." in loguru_sink

        pm.goto_last_page()
        assert "Already on the last page: current index = 6." in loguru_sink

    def test_a_comic_opened_at_a_right_page_opens_at_that_page(self) -> None:
        pm = ComicPageManager(MagicMock())
        pm.set_layout(_layout(_page_map(*_SEVEN_PAGES)), "2")

        pm.set_to_first_page_to_read()
        assert pm.get_current_page_index() == 2

    def test_a_right_page_by_name_is_that_page(self, pm: ComicPageManager) -> None:
        pm.set_current_page_index_from_str("6")
        assert pm.get_current_page_index() == 6
        assert pm.get_current_page_str() == "6"

    def test_pages_before_the_one_opened_at_load_last_nearest_first(self) -> None:
        pm = ComicPageManager(MagicMock())
        pm.set_layout(_layout(_page_map(*_SEVEN_PAGES)), "4")

        assert pm.get_image_load_order() == ["4", "3", "5", "6", "2", "1", "0"]

    def test_start_on_the_first_page_says_so_and_stays(
        self, pm: ComicPageManager, loguru_sink: list[str]
    ) -> None:
        pm.set_to_first_page_to_read()
        pm.goto_start_page()
        assert pm.get_current_page_index() == 0
        assert loguru_sink == ["Already on the first page: current index = 0."]

    def test_next_on_the_last_page_and_prev_on_the_first_say_so(
        self, pm: ComicPageManager, loguru_sink: list[str]
    ) -> None:
        pm.set_current_page_index_from_str("6")
        loguru_sink.clear()
        pm.next_page()
        assert loguru_sink == ["Already on the last page: current index = 6."]

        pm.set_current_page_index_from_str("0")
        loguru_sink.clear()
        pm.prev_page()
        assert loguru_sink == ["Already on the first page: current index = 0."]
