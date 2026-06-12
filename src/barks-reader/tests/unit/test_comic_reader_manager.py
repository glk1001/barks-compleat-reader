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
from barks_reader.ui.comic_reader_manager import ComicReaderManager


@pytest.fixture
def mock_dependencies() -> dict[str, MagicMock]:
    return {
        "comics_database": MagicMock(),
        "reader_settings": MagicMock(),
        "last_read_page_tracker": MagicMock(),
        "layout_builder": MagicMock(),
        "tree_view_screen": MagicMock(),
        "user_error_handler": MagicMock(),
    }


@pytest.fixture
def manager(mock_dependencies: dict[str, MagicMock]) -> ComicReaderManager:
    return ComicReaderManager(**mock_dependencies)


def _make_layout(page_map: OrderedDict[str, PageInfo], last_body_page: str = "10") -> ComicLayout:
    return ComicLayout(page_map=page_map, last_body_page=last_body_page)


def _attach_reader_screen(manager: ComicReaderManager) -> tuple[MagicMock, MagicMock]:
    """Attach a mock reader screen to *manager* and return (screen, reader)."""
    mock_screen = MagicMock()
    mock_reader = MagicMock()
    mock_screen.comic_book_reader = mock_reader
    manager.set_comic_book_reader_screen(mock_screen)
    return mock_screen, mock_reader


def _single_body_page_layout() -> ComicLayout:
    """Return a layout with a single body page "1"."""
    page_info_obj = PageInfo(
        page_index=0,
        display_page_num="1",
        page_type=PageType.BODY,
        srce_page=MagicMock(),
        dest_page=MagicMock(),
    )
    return _make_layout(OrderedDict([("1", page_info_obj)]), last_body_page="1")


class TestComicReaderManager:
    def test_set_comic_book_reader_screen(self, manager: ComicReaderManager) -> None:
        mock_screen, mock_reader = _attach_reader_screen(manager)

        assert manager._comic_book_reader_screen == mock_screen
        assert manager._comic_book_reader == mock_reader

    def test_init_comic_book_data(self, manager: ComicReaderManager) -> None:
        mock_reader = MagicMock()
        manager._comic_book_reader = mock_reader

        manager.init_comic_book_data()
        mock_reader.init_data.assert_called_once()

    def test_read_article_begins_tracker_with_save_disabled(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_screen, mock_reader = _attach_reader_screen(manager)

        mock_comic = MagicMock()
        mock_dependencies["comics_database"].get_comic_book.return_value = mock_comic

        mock_layout = _single_body_page_layout()
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

            tracker_begin = mock_dependencies["last_read_page_tracker"].begin
            tracker_begin.assert_called_once()
            _, kwargs = tracker_begin.call_args
            assert kwargs["save_enabled"] is False

    def test_read_barks_begins_tracker_with_save_enabled(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        _mock_screen, mock_reader = _attach_reader_screen(manager)

        mock_fanta_info = MagicMock(spec=FantaComicBookInfo)
        mock_fanta_info.comic_book_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "Title"

        mock_comic = MagicMock()

        mock_layout = _single_body_page_layout()
        mock_dependencies["layout_builder"].build.return_value = mock_layout

        with patch.object(barks_reader.core.reader_setup, "ComicBookImageBuilder"):
            manager.read_barks_comic_book(
                mock_fanta_info, mock_comic, "1", use_overrides_active=True
            )

            mock_reader.read_comic.assert_called_once()

            tracker_begin = mock_dependencies["last_read_page_tracker"].begin
            tracker_begin.assert_called_once()
            args, kwargs = tracker_begin.call_args
            assert args[0] == "Title"
            assert args[1] is mock_layout
            assert kwargs["save_enabled"] is True

    def test_comic_closed_delegates_to_tracker(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_reader = MagicMock()
        manager._comic_book_reader = mock_reader

        sentinel = MagicMock()
        mock_dependencies["last_read_page_tracker"].end.return_value = sentinel

        result = manager.comic_closed()

        mock_dependencies["last_read_page_tracker"].end.assert_called_once_with(mock_reader)
        assert result is sentinel

    def test_get_last_read_page_delegates_to_tracker(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        sentinel = MagicMock()
        mock_dependencies["last_read_page_tracker"].get_last_read_page.return_value = sentinel

        result = manager.get_last_read_page("My Title")

        mock_dependencies["last_read_page_tracker"].get_last_read_page.assert_called_once_with(
            "My Title"
        )
        assert result is sentinel
