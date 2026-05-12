# ruff: noqa: SLF001

from __future__ import annotations

from collections import OrderedDict
from unittest.mock import MagicMock, patch

import barks_reader.core.reader_setup
import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
from barks_reader.core.comic_book_page_info import ComicLayout, PageInfo
from barks_reader.core.display_unit import DisplayUnit
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE
from barks_reader.ui.comic_reader_manager import ComicReaderManager
from barks_reader.ui.json_settings_manager import SavedPageInfo


@pytest.fixture
def mock_dependencies() -> dict[str, MagicMock]:
    return {
        "comics_database": MagicMock(),
        "reader_settings": MagicMock(),
        "json_settings_manager": MagicMock(),
        "layout_builder": MagicMock(),
        "tree_view_screen": MagicMock(),
        "user_error_handler": MagicMock(),
    }


@pytest.fixture
def manager(mock_dependencies: dict[str, MagicMock]) -> ComicReaderManager:
    return ComicReaderManager(**mock_dependencies)


def _make_layout(page_map: OrderedDict[str, PageInfo], last_body_page: str = "10") -> ComicLayout:
    return ComicLayout(page_map=page_map, last_body_page=last_body_page)


class TestComicReaderManager:
    def test_set_comic_book_reader_screen(self, manager: ComicReaderManager) -> None:
        mock_screen = MagicMock()
        mock_reader = MagicMock()
        mock_screen.comic_book_reader = mock_reader

        manager.set_comic_book_reader_screen(mock_screen)

        assert manager._comic_book_reader_screen == mock_screen
        assert manager._comic_book_reader == mock_reader

    def test_init_comic_book_data(self, manager: ComicReaderManager) -> None:
        mock_reader = MagicMock()
        manager._comic_book_reader = mock_reader

        manager.init_comic_book_data()
        mock_reader.init_data.assert_called_once()

    def test_read_article_as_comic_book(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_screen = MagicMock()
        mock_reader = MagicMock()
        mock_screen.comic_book_reader = mock_reader
        manager.set_comic_book_reader_screen(mock_screen)

        mock_comic = MagicMock()
        mock_dependencies["comics_database"].get_comic_book.return_value = mock_comic

        page_info_obj = PageInfo(
            page_index=0,
            display_page_num="1",
            page_type=PageType.BODY,
            srce_page=MagicMock(),
            dest_page=MagicMock(),
        )
        mock_layout = _make_layout(OrderedDict([("1", page_info_obj)]), last_body_page="1")
        mock_dependencies["layout_builder"].build.return_value = mock_layout

        with patch.object(
            barks_reader.core.reader_setup, "ComicBookImageBuilder"
        ) as mock_builder_cls:
            manager.read_article_as_comic_book(Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION, "1")

            assert mock_screen.can_benefit_from_fullscreen is True

            mock_reader.read_comic.assert_called_once()
            args, _ = mock_reader.read_comic.call_args
            assert args[3] == "1"
            assert args[4] == mock_layout.page_map

            mock_builder_cls.assert_called_once()

    def test_read_barks_comic_book(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_screen = MagicMock()
        mock_reader = MagicMock()
        mock_screen.comic_book_reader = mock_reader
        manager.set_comic_book_reader_screen(mock_screen)

        mock_fanta_info = MagicMock(spec=FantaComicBookInfo)
        mock_fanta_info.comic_book_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "Title"

        mock_comic = MagicMock()

        page_info_obj = PageInfo(
            page_index=0,
            display_page_num="1",
            page_type=PageType.BODY,
            srce_page=MagicMock(),
            dest_page=MagicMock(),
        )
        mock_layout = _make_layout(OrderedDict([("1", page_info_obj)]), last_body_page="1")
        mock_dependencies["layout_builder"].build.return_value = mock_layout

        with patch.object(barks_reader.core.reader_setup, "ComicBookImageBuilder"):
            manager.read_barks_comic_book(
                mock_fanta_info, mock_comic, "1", use_overrides_active=True
            )

            mock_reader.read_comic.assert_called_once()
            assert manager._save_last_page is True

    def test_comic_closed_no_save(self, manager: ComicReaderManager) -> None:
        manager._save_last_page = False
        assert manager.comic_closed() is None

    def test_comic_closed_save(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        # Single page mode — display unit's right page is irrelevant here.
        mock_reader = MagicMock()
        mock_reader.get_last_read_page.return_value = "5"
        mock_reader.double_page_mode = False
        mock_reader.get_current_display_unit.return_value = DisplayUnit(
            left_page_index=4, right_page_index=5
        )
        manager._comic_book_reader = mock_reader

        mock_fanta_info = MagicMock(spec=FantaComicBookInfo)
        mock_fanta_info.comic_book_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "My Title"
        manager._fanta_info = mock_fanta_info

        page_info_obj = PageInfo(
            page_index=4,
            display_page_num="5",
            page_type=PageType.BODY,
            srce_page=MagicMock(),
            dest_page=MagicMock(),
        )
        manager._layout = _make_layout(OrderedDict([("5", page_info_obj)]), last_body_page="10")

        result = manager.comic_closed()

        assert result is not None
        assert result.display_page_num == "5"
        mock_dependencies["json_settings_manager"].save_last_read_page.assert_called_with(
            "My Title", result
        )

    def test_get_last_read_page(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        # Case 1: No saved page
        mock_dependencies["json_settings_manager"].get_last_read_page.return_value = None
        assert manager.get_last_read_page("Title") is None

        # Case 2: Saved page inside body
        saved_info = SavedPageInfo(
            page_index=5, display_page_num="6", page_type=PageType.BODY, last_body_page="10"
        )
        mock_dependencies["json_settings_manager"].get_last_read_page.return_value = saved_info
        res = manager.get_last_read_page("Title")
        assert res == saved_info
        assert res is not None
        assert res.display_page_num == "6"

        # Case 3: Saved page is last page (finished) — should reset to beginning.
        saved_info_finished = SavedPageInfo(
            page_index=9, display_page_num="10", page_type=PageType.BODY, last_body_page="10"
        )
        mock_dependencies[
            "json_settings_manager"
        ].get_last_read_page.return_value = saved_info_finished
        res_finished = manager.get_last_read_page("Title")
        assert res_finished is not None
        assert res_finished.display_page_num == COMIC_BEGIN_PAGE

    def test_comic_closed_double_page_with_back_matter(self, manager: ComicReaderManager) -> None:
        """In double page mode, if right page is back matter, page should not be saved."""
        body_page = PageInfo(
            page_index=8,
            display_page_num="9",
            page_type=PageType.BODY,
            srce_page=MagicMock(),
            dest_page=MagicMock(),
        )
        back_matter_page = PageInfo(
            page_index=9,
            display_page_num="10",
            page_type=PageType.BACK_MATTER,
            srce_page=MagicMock(),
            dest_page=MagicMock(),
        )

        mock_reader = MagicMock()
        mock_reader.get_last_read_page.return_value = "9"
        mock_reader.double_page_mode = True
        mock_reader.get_current_display_unit.return_value = DisplayUnit(
            left_page_index=8, right_page_index=9
        )
        manager._comic_book_reader = mock_reader

        mock_fanta_info = MagicMock(spec=FantaComicBookInfo)
        mock_fanta_info.comic_book_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "My Title"
        manager._fanta_info = mock_fanta_info

        manager._layout = _make_layout(
            OrderedDict([("9", body_page), ("10", back_matter_page)]),
            last_body_page="9",
        )

        result = manager.comic_closed()

        assert result is not None
        # Right page is back matter, so save logic resets to the beginning.
        assert result.display_page_num == COMIC_BEGIN_PAGE

    def test_comic_closed_double_page_on_first_body_pair(self, manager: ComicReaderManager) -> None:
        """Double page mode on first body pair should reset to begin."""
        body_page_1 = PageInfo(
            page_index=0,
            display_page_num="1",
            page_type=PageType.BODY,
            srce_page=MagicMock(),
            dest_page=MagicMock(),
        )
        body_page_2 = PageInfo(
            page_index=1,
            display_page_num="2",
            page_type=PageType.BODY,
            srce_page=MagicMock(),
            dest_page=MagicMock(),
        )

        mock_reader = MagicMock()
        mock_reader.get_last_read_page.return_value = "1"
        mock_reader.double_page_mode = True
        mock_reader.get_current_display_unit.return_value = DisplayUnit(
            left_page_index=0, right_page_index=1
        )
        manager._comic_book_reader = mock_reader

        mock_fanta_info = MagicMock(spec=FantaComicBookInfo)
        mock_fanta_info.comic_book_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "My Title"
        manager._fanta_info = mock_fanta_info

        manager._layout = _make_layout(
            OrderedDict([("1", body_page_1), ("2", body_page_2)]),
            last_body_page="10",
        )

        result = manager.comic_closed()

        assert result is not None
        # Unit's left page is the first body page, so save resets to the beginning.
        assert result.display_page_num == COMIC_BEGIN_PAGE

    def test_comic_closed_single_page_on_first_body_page(self, manager: ComicReaderManager) -> None:
        """Single page mode on first body page should reset to begin."""
        body_page_1 = PageInfo(
            page_index=0,
            display_page_num="1",
            page_type=PageType.BODY,
            srce_page=MagicMock(),
            dest_page=MagicMock(),
        )

        mock_reader = MagicMock()
        mock_reader.get_last_read_page.return_value = "1"
        mock_reader.double_page_mode = False
        mock_reader.get_current_display_unit.return_value = DisplayUnit(
            left_page_index=0, right_page_index=None
        )
        manager._comic_book_reader = mock_reader

        mock_fanta_info = MagicMock(spec=FantaComicBookInfo)
        mock_fanta_info.comic_book_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "My Title"
        manager._fanta_info = mock_fanta_info

        manager._layout = _make_layout(OrderedDict([("1", body_page_1)]), last_body_page="10")

        result = manager.comic_closed()

        assert result is not None
        assert result.display_page_num == COMIC_BEGIN_PAGE
