# ruff: noqa: SLF001

from __future__ import annotations

from collections import OrderedDict
from unittest.mock import MagicMock, patch

import barks_reader.ui.comic_reader_manager
import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
from barks_fantagraphics.page_classes import RequiredDimensions
from barks_reader.core.comic_book_page_info import ComicBookPageInfo, PageInfo
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE
from barks_reader.ui.comic_reader_manager import ComicReaderManager
from barks_reader.ui.json_settings_manager import SavedPageInfo


@pytest.fixture
def mock_dependencies() -> dict[str, MagicMock]:
    return {
        "comics_database": MagicMock(),
        "reader_settings": MagicMock(),
        "json_settings_manager": MagicMock(),
        "tree_view_screen": MagicMock(),
        "user_error_handler": MagicMock(),
    }


@pytest.fixture
def manager(mock_dependencies: dict[str, MagicMock]) -> ComicReaderManager:
    return ComicReaderManager(**mock_dependencies)


class TestComicReaderManager:
    def test_set_comic_book_reader_screen(self, manager: ComicReaderManager) -> None:
        mock_screen = MagicMock()
        mock_reader = MagicMock()
        mock_screen.comic_book_reader = mock_reader

        manager.set_comic_book_reader_screen(mock_screen)

        # noinspection PyProtectedMember
        assert manager._comic_book_reader_screen == mock_screen
        # noinspection PyProtectedMember
        assert manager._comic_book_reader == mock_reader

    def test_init_comic_book_data(self, manager: ComicReaderManager) -> None:
        mock_reader = MagicMock()
        # noinspection PyProtectedMember
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

        # Mock page info manager
        mock_page_info = ComicBookPageInfo(
            required_dim=RequiredDimensions(100, 100),
            page_map=OrderedDict([("1", MagicMock())]),
            last_body_page="1",
            last_page="1",
        )
        # noinspection PyProtectedMember,LongLine
        manager._comic_page_info_mgr.get_comic_page_info = MagicMock(return_value=mock_page_info)  # type: ignore[assignment]

        # Mock ImageBuilder
        with patch.object(
            barks_reader.ui.comic_reader_manager, "ComicBookImageBuilder"
        ) as mock_builder_cls:
            manager.read_article_as_comic_book(Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION, "1")

            # Check fullscreen toggle logic
            assert mock_screen.can_benefit_from_fullscreen is True  # Should be reset to True

            # Check read call
            mock_reader.read_comic.assert_called_once()
            args, _ = mock_reader.read_comic.call_args
            # fanta_info, use_overrides, builder, page_to_goto, page_map
            assert args[3] == "1"
            assert args[4] == mock_page_info.page_map

            # Check builder created
            mock_builder_cls.assert_called_once()

    def test_read_barks_comic_book(self, manager: ComicReaderManager) -> None:
        mock_screen = MagicMock()
        mock_reader = MagicMock()
        mock_screen.comic_book_reader = mock_reader
        manager.set_comic_book_reader_screen(mock_screen)

        mock_fanta_info = MagicMock(spec=FantaComicBookInfo)
        mock_fanta_info.comic_book_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "Title"

        mock_comic = MagicMock()

        mock_page_info = ComicBookPageInfo(
            required_dim=RequiredDimensions(100, 100),
            page_map=OrderedDict([("1", MagicMock())]),
            last_body_page="1",
            last_page="1",
        )
        # noinspection PyProtectedMember,LongLine
        manager._comic_page_info_mgr.get_comic_page_info = MagicMock(return_value=mock_page_info)  # type: ignore[assignment]

        with patch.object(barks_reader.ui.comic_reader_manager, "ComicBookImageBuilder"):
            manager.read_barks_comic_book(
                mock_fanta_info, mock_comic, "1", use_overrides_active=True
            )

            mock_reader.read_comic.assert_called_once()
            # noinspection PyProtectedMember
            assert manager._save_last_page is True

    def test_comic_closed_no_save(self, manager: ComicReaderManager) -> None:
        # noinspection PyProtectedMember
        manager._save_last_page = False
        assert manager.comic_closed() is None

    def test_comic_closed_save(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        # Setup state
        mock_reader = MagicMock()
        mock_reader.get_last_read_page.return_value = "5"
        # noinspection PyProtectedMember
        manager._comic_book_reader = mock_reader

        mock_fanta_info = MagicMock(spec=FantaComicBookInfo)
        mock_fanta_info.comic_book_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "My Title"
        # noinspection PyProtectedMember
        manager._fanta_info = mock_fanta_info

        # Setup page info to map "5" to a PageInfo object
        page_info_obj = PageInfo(
            page_index=4,
            display_page_num="5",
            page_type=PageType.BODY,
            srce_page=MagicMock(),
            dest_page=MagicMock(),
        )
        mock_comic_page_info = ComicBookPageInfo(
            required_dim=RequiredDimensions(100, 100),
            page_map=OrderedDict([("5", page_info_obj)]),
            last_body_page="10",
            last_page="10",
        )
        # noinspection PyProtectedMember
        manager._comic_page_info = mock_comic_page_info

        # Execute
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
        assert res.display_page_num == "6"  # ty:ignore[unresolved-attribute]

        # Case 3: Saved page is last page (finished)
        saved_info_finished = SavedPageInfo(
            page_index=9, display_page_num="10", page_type=PageType.BODY, last_body_page="10"
        )
        mock_dependencies[
            "json_settings_manager"
        ].get_last_read_page.return_value = saved_info_finished
        res_finished = manager.get_last_read_page("Title")
        assert res_finished is not None
        # Should reset to start
        assert res_finished.display_page_num == COMIC_BEGIN_PAGE
