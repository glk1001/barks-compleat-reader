from __future__ import annotations

from collections import OrderedDict
from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.comics_consts import PageType
from barks_reader.core.comic_book_page_info import ComicLayout, PageInfo
from barks_reader.core.display_unit import DisplayUnit
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE
from barks_reader.core.saved_page_info import SavedPageInfo
from barks_reader.ui.last_read_page_tracker import LastReadPageTracker


@pytest.fixture
def mock_settings_manager() -> MagicMock:
    return MagicMock()


@pytest.fixture
def tracker(mock_settings_manager: MagicMock) -> LastReadPageTracker:
    return LastReadPageTracker(mock_settings_manager)


def _make_layout(page_map: OrderedDict[str, PageInfo], last_body_page: str = "10") -> ComicLayout:
    return ComicLayout(page_map=page_map, last_body_page=last_body_page)


def _body_page(page_index: int, display_page_num: str) -> PageInfo:
    return PageInfo(
        page_index=page_index,
        display_page_num=display_page_num,
        page_type=PageType.BODY,
        srce_page=MagicMock(),
        dest_page=MagicMock(),
    )


class TestEndWithoutBegin:
    def test_end_returns_none_when_save_disabled(self, tracker: LastReadPageTracker) -> None:
        # No begin() called — save_enabled defaults to False.
        assert tracker.end(MagicMock()) is None

    def test_end_returns_none_when_begin_called_with_save_disabled(
        self, tracker: LastReadPageTracker
    ) -> None:
        layout = _make_layout(OrderedDict([("1", _body_page(0, "1"))]), last_body_page="1")
        tracker.begin("Title", layout, save_enabled=False)
        assert tracker.end(MagicMock()) is None


class TestEnd:
    def test_saves_mid_body_position(
        self, tracker: LastReadPageTracker, mock_settings_manager: MagicMock
    ) -> None:
        reader = MagicMock()
        reader.get_last_read_page.return_value = "5"
        reader.double_page_mode = False
        reader.get_current_display_unit.return_value = DisplayUnit(
            left_page_index=4, right_page_index=5
        )

        layout = _make_layout(OrderedDict([("5", _body_page(4, "5"))]), last_body_page="10")
        tracker.begin("My Title", layout, save_enabled=True)

        result = tracker.end(reader)

        assert result is not None
        assert result.display_page_num == "5"
        mock_settings_manager.save_last_read_page.assert_called_with("My Title", result)

    def test_returns_none_when_reader_has_no_last_page(
        self, tracker: LastReadPageTracker, mock_settings_manager: MagicMock
    ) -> None:
        reader = MagicMock()
        reader.get_last_read_page.return_value = ""

        layout = _make_layout(OrderedDict([("1", _body_page(0, "1"))]), last_body_page="1")
        tracker.begin("Title", layout, save_enabled=True)

        assert tracker.end(reader) is None
        mock_settings_manager.save_last_read_page.assert_not_called()

    def test_double_page_with_back_matter_resets_to_begin(
        self, tracker: LastReadPageTracker
    ) -> None:
        body_page = _body_page(8, "9")
        back_matter_page = PageInfo(
            page_index=9,
            display_page_num="10",
            page_type=PageType.BACK_MATTER,
            srce_page=MagicMock(),
            dest_page=MagicMock(),
        )

        reader = MagicMock()
        reader.get_last_read_page.return_value = "9"
        reader.double_page_mode = True
        reader.get_current_display_unit.return_value = DisplayUnit(
            left_page_index=8, right_page_index=9
        )

        layout = _make_layout(
            OrderedDict([("9", body_page), ("10", back_matter_page)]),
            last_body_page="9",
        )
        tracker.begin("My Title", layout, save_enabled=True)

        result = tracker.end(reader)
        assert result is not None
        # Right page is back matter, so save logic resets to the beginning.
        assert result.display_page_num == COMIC_BEGIN_PAGE

    def test_double_page_on_first_body_pair_resets_to_begin(
        self, tracker: LastReadPageTracker
    ) -> None:
        reader = MagicMock()
        reader.get_last_read_page.return_value = "1"
        reader.double_page_mode = True
        reader.get_current_display_unit.return_value = DisplayUnit(
            left_page_index=0, right_page_index=1
        )

        layout = _make_layout(
            OrderedDict([("1", _body_page(0, "1")), ("2", _body_page(1, "2"))]),
            last_body_page="10",
        )
        tracker.begin("My Title", layout, save_enabled=True)

        result = tracker.end(reader)
        assert result is not None
        # Unit's left page is the first body page, so save resets to the beginning.
        assert result.display_page_num == COMIC_BEGIN_PAGE

    def test_single_page_on_first_body_page_resets_to_begin(
        self, tracker: LastReadPageTracker
    ) -> None:
        reader = MagicMock()
        reader.get_last_read_page.return_value = "1"
        reader.double_page_mode = False
        reader.get_current_display_unit.return_value = DisplayUnit(
            left_page_index=0, right_page_index=None
        )

        layout = _make_layout(OrderedDict([("1", _body_page(0, "1"))]), last_body_page="10")
        tracker.begin("My Title", layout, save_enabled=True)

        result = tracker.end(reader)
        assert result is not None
        assert result.display_page_num == COMIC_BEGIN_PAGE


class TestGetLastReadPage:
    def test_returns_none_when_no_saved_page(
        self, tracker: LastReadPageTracker, mock_settings_manager: MagicMock
    ) -> None:
        mock_settings_manager.get_last_read_page.return_value = None
        assert tracker.get_last_read_page("Title") is None

    def test_returns_saved_page_when_inside_body(
        self, tracker: LastReadPageTracker, mock_settings_manager: MagicMock
    ) -> None:
        saved = SavedPageInfo(
            page_index=5, display_page_num="6", page_type=PageType.BODY, last_body_page="10"
        )
        mock_settings_manager.get_last_read_page.return_value = saved

        result = tracker.get_last_read_page("Title")

        assert result is saved
        assert result.display_page_num == "6"

    def test_resets_finished_comic_to_begin(
        self, tracker: LastReadPageTracker, mock_settings_manager: MagicMock
    ) -> None:
        saved_finished = SavedPageInfo(
            page_index=9, display_page_num="10", page_type=PageType.BODY, last_body_page="10"
        )
        mock_settings_manager.get_last_read_page.return_value = saved_finished

        result = tracker.get_last_read_page("Title")

        assert result is not None
        assert result.display_page_num == COMIC_BEGIN_PAGE
