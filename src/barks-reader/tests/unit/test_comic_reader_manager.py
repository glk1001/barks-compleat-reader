# ruff: noqa: SLF001

from __future__ import annotations

from collections import OrderedDict
from unittest.mock import MagicMock, patch

import barks_reader.core.reader_setup
import pytest
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
from barks_reader.core import comic_reader_manager as comic_reader_manager_module
from barks_reader.core.comic_book_page_info import ComicLayout, PageInfo
from barks_reader.core.comic_reader_manager import ComicReaderManager
from barks_reader.core.fantagraphics_volumes import MissingVolumeError
from barks_reader.core.testing import FakeScheduler
from barks_reader.core.user_error_types import ErrorTypes


@pytest.fixture
def mock_dependencies() -> dict[str, MagicMock]:
    return {
        "comics_database": MagicMock(),
        "reader_settings": MagicMock(),
        "last_read_page_tracker": MagicMock(),
        "reading_history_tracker": MagicMock(),
        "layout_builder": MagicMock(),
        "user_error_handler": MagicMock(),
    }


@pytest.fixture
def manager(mock_dependencies: dict[str, MagicMock]) -> ComicReaderManager:
    return ComicReaderManager(**mock_dependencies, scheduler=FakeScheduler())


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


def _multi_body_page_layout(count: int) -> ComicLayout:
    """Return a layout with body pages "1".."count" (page_index 0..count-1)."""
    page_map: OrderedDict[str, PageInfo] = OrderedDict()
    for i in range(count):
        page_map[str(i + 1)] = PageInfo(
            page_index=i,
            display_page_num=str(i + 1),
            page_type=PageType.BODY,
            srce_page=MagicMock(),
            dest_page=MagicMock(),
            is_solo=True,
        )
    return _make_layout(page_map, last_body_page=str(count))


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

            mock_dependencies["reading_history_tracker"].begin.assert_not_called()

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

            mock_dependencies["reading_history_tracker"].begin.assert_called_once_with("Title")

    def test_collection_page_range_slices_the_layout(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        _mock_screen, mock_reader = _attach_reader_screen(manager)

        mock_fanta_info = MagicMock(spec=FantaComicBookInfo)
        mock_fanta_info.comic_book_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "All Covers"

        # Full collection layout has pages "1".."10"; open only the "4".."7" group.
        mock_dependencies["layout_builder"].build.return_value = _multi_body_page_layout(10)

        with patch.object(barks_reader.core.reader_setup, "ComicBookImageBuilder"):
            manager.read_barks_comic_book(
                mock_fanta_info,
                MagicMock(),
                "5",  # goto a member inside the group (still a global key)
                use_overrides_active=True,
                collection_page_range=(4, 7),
            )

        # read_comic receives the sliced map (global keys, page_index renumbered from 0).
        args, _ = mock_reader.read_comic.call_args
        sliced_page_map = args[4]
        assert list(sliced_page_map.keys()) == ["4", "5", "6", "7"]
        assert [p.page_index for p in sliced_page_map.values()] == [0, 1, 2, 3]
        # Goto key "5" is still present and resolvable in the slice.
        assert "5" in sliced_page_map

        # The last-read-page tracker gets the same sliced layout (consistent indices).
        tracker_args, _ = mock_dependencies["last_read_page_tracker"].begin.call_args
        assert list(tracker_args[1].page_map.keys()) == ["4", "5", "6", "7"]

    def test_no_collection_page_range_passes_full_layout(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        _mock_screen, mock_reader = _attach_reader_screen(manager)

        mock_fanta_info = MagicMock(spec=FantaComicBookInfo)
        mock_fanta_info.comic_book_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "Title"

        full_layout = _multi_body_page_layout(10)
        mock_dependencies["layout_builder"].build.return_value = full_layout

        with patch.object(barks_reader.core.reader_setup, "ComicBookImageBuilder"):
            manager.read_barks_comic_book(
                mock_fanta_info, MagicMock(), "1", use_overrides_active=True
            )

        args, _ = mock_reader.read_comic.call_args
        assert args[4] is full_layout.page_map

    def test_read_barks_records_history_with_override_title(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        _attach_reader_screen(manager)

        mock_fanta_info = MagicMock(spec=FantaComicBookInfo)
        mock_fanta_info.comic_book_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "All One-Pagers"

        mock_layout = _single_body_page_layout()
        mock_dependencies["layout_builder"].build.return_value = mock_layout

        with patch.object(barks_reader.core.reader_setup, "ComicBookImageBuilder"):
            manager.read_barks_comic_book(
                mock_fanta_info,
                MagicMock(),
                "1",
                use_overrides_active=True,
                history_title_str="Coffee for Two",
            )

        mock_dependencies["reading_history_tracker"].begin.assert_called_once_with("Coffee for Two")

    def test_missing_volume_reports_error_and_closes_reader(
        self, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        scheduler = FakeScheduler()
        manager = ComicReaderManager(**mock_dependencies, scheduler=scheduler)
        mock_screen, mock_reader = _attach_reader_screen(manager)

        mock_fanta_info = MagicMock(spec=FantaComicBookInfo)
        mock_fanta_info.comic_book_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "Title"

        mock_layout = _single_body_page_layout()
        mock_dependencies["layout_builder"].build.return_value = mock_layout

        mock_reader.read_comic.side_effect = MissingVolumeError(7, Titles.LOST_IN_THE_ANDES)

        with patch.object(barks_reader.core.reader_setup, "ComicBookImageBuilder"):
            manager.read_barks_comic_book(
                mock_fanta_info, MagicMock(), "1", use_overrides_active=True
            )

        handle_error = mock_dependencies["user_error_handler"].handle_error
        handle_error.assert_called_once()
        error_type, error_info = handle_error.call_args.args
        assert error_type is ErrorTypes.MissingVolumeCannotShowTitle
        assert error_info.missing_volumes == [7]
        assert error_info.title is Titles.LOST_IN_THE_ANDES

        # FakeScheduler runs one-shots inline, so the deferred close happens now.
        assert scheduler.scheduled_once_count == 1
        mock_screen.close_comic_book_reader.assert_called_once_with()

    def test_successful_read_schedules_no_close(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_screen, _mock_reader = _attach_reader_screen(manager)

        mock_fanta_info = MagicMock(spec=FantaComicBookInfo)
        mock_fanta_info.comic_book_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "Title"

        mock_layout = _single_body_page_layout()
        mock_dependencies["layout_builder"].build.return_value = mock_layout

        with patch.object(barks_reader.core.reader_setup, "ComicBookImageBuilder"):
            manager.read_barks_comic_book(
                mock_fanta_info, MagicMock(), "1", use_overrides_active=True
            )

        mock_dependencies["user_error_handler"].handle_error.assert_not_called()
        mock_screen.close_comic_book_reader.assert_not_called()

    def test_comic_closed_delegates_to_tracker(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_reader = MagicMock()
        manager._comic_book_reader = mock_reader

        sentinel = MagicMock()
        mock_dependencies["last_read_page_tracker"].end.return_value = sentinel

        result = manager.comic_closed()

        mock_dependencies["last_read_page_tracker"].end.assert_called_once_with(mock_reader)
        mock_dependencies["reading_history_tracker"].end.assert_called_once_with(sentinel)
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


class TestArticleReading:
    def test_the_article_is_looked_up_by_its_own_title(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        """The database is keyed by title string, so the wrong key opens the wrong book."""
        _attach_reader_screen(manager)
        mock_dependencies["layout_builder"].build.return_value = _single_body_page_layout()
        article = Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION

        with patch.object(barks_reader.core.reader_setup, "ComicBookImageBuilder"):
            manager.read_article_as_comic_book(article, "1")

        mock_dependencies["comics_database"].get_comic_book.assert_called_once_with(
            ENUM_TO_STR_TITLE[article]
        )

    def test_the_looked_up_comic_is_the_one_prepared(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        _attach_reader_screen(manager)
        comic = MagicMock()
        mock_dependencies["comics_database"].get_comic_book.return_value = comic
        mock_dependencies["layout_builder"].build.return_value = _single_body_page_layout()

        with (
            patch.object(barks_reader.core.reader_setup, "ComicBookImageBuilder"),
            patch.object(
                comic_reader_manager_module,
                "prepare_comic_for_reading",
                return_value=(_single_body_page_layout(), MagicMock()),
            ) as mock_prepare,
        ):
            manager.read_article_as_comic_book(Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION, "1")

        mock_prepare.assert_called_once_with(
            comic,
            mock_dependencies["reader_settings"],
            mock_dependencies["layout_builder"],
        )

    def test_fullscreen_is_suppressed_while_the_article_is_opening(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        """Articles are text, so the reader must not offer fullscreen for them.

        The flag is restored afterwards, so its value has to be captured mid-read.
        """
        mock_screen, mock_reader = _attach_reader_screen(manager)
        mock_dependencies["layout_builder"].build.return_value = _single_body_page_layout()
        seen: list[bool] = []
        mock_reader.read_comic.side_effect = lambda *_a, **_k: seen.append(
            mock_screen.can_benefit_from_fullscreen
        )

        with patch.object(barks_reader.core.reader_setup, "ComicBookImageBuilder"):
            manager.read_article_as_comic_book(Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION, "1")

        assert seen == [False]
        assert mock_screen.can_benefit_from_fullscreen is True

    def test_fullscreen_is_restored_even_when_the_read_fails(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_screen, mock_reader = _attach_reader_screen(manager)
        mock_dependencies["layout_builder"].build.return_value = _single_body_page_layout()
        mock_reader.read_comic.side_effect = RuntimeError("boom")

        with (
            patch.object(barks_reader.core.reader_setup, "ComicBookImageBuilder"),
            pytest.raises(RuntimeError),
        ):
            manager.read_article_as_comic_book(Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION, "1")

        assert mock_screen.can_benefit_from_fullscreen is True

    def test_articles_are_read_with_overrides_active(
        self, manager: ComicReaderManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        """Articles take `_read_comic_book`'s default, which applies overrides."""
        _attach_reader_screen(manager)
        _, mock_reader = _attach_reader_screen(manager)
        mock_dependencies["layout_builder"].build.return_value = _single_body_page_layout()

        with patch.object(barks_reader.core.reader_setup, "ComicBookImageBuilder"):
            manager.read_article_as_comic_book(Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION, "1")

        assert mock_reader.read_comic.call_args.args[1] is True


class TestBarksReadingPassesThrough:
    @pytest.mark.parametrize("use_overrides", [True, False], ids=["on", "off"])
    def test_the_override_setting_reaches_the_reader(
        self,
        manager: ComicReaderManager,
        mock_dependencies: dict[str, MagicMock],
        use_overrides: bool,
    ) -> None:
        _, mock_reader = _attach_reader_screen(manager)
        mock_dependencies["layout_builder"].build.return_value = _single_body_page_layout()
        fanta_info = MagicMock(spec=FantaComicBookInfo)
        fanta_info.comic_book_info = MagicMock()
        fanta_info.comic_book_info.get_title_str.return_value = "Title"

        with patch.object(barks_reader.core.reader_setup, "ComicBookImageBuilder"):
            manager.read_barks_comic_book(
                fanta_info, MagicMock(), "1", use_overrides_active=use_overrides
            )

        assert mock_reader.read_comic.call_args.args[1] is use_overrides


class TestErrorCloseDelay:
    def test_the_reader_closes_after_the_configured_delay(
        self, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        """The delay lets the user read the error popup before the reader vanishes."""
        scheduler = FakeScheduler()
        manager = ComicReaderManager(**mock_dependencies, scheduler=scheduler)
        mock_screen, mock_reader = _attach_reader_screen(manager)
        mock_dependencies["layout_builder"].build.return_value = _single_body_page_layout()

        fanta_info = MagicMock(spec=FantaComicBookInfo)
        fanta_info.comic_book_info = MagicMock()
        fanta_info.comic_book_info.get_title_str.return_value = "Title"
        mock_reader.read_comic.side_effect = MissingVolumeError(7, Titles.LOST_IN_THE_ANDES)

        with (
            patch.object(barks_reader.core.reader_setup, "ComicBookImageBuilder"),
            patch.object(scheduler, "schedule_once", wraps=scheduler.schedule_once) as spy,
        ):
            manager.read_barks_comic_book(fanta_info, MagicMock(), "1", use_overrides_active=True)

        spy.assert_called_once_with(
            mock_screen.close_comic_book_reader,
            comic_reader_manager_module._CLOSE_READER_ON_ERROR_DELAY_SECS,
        )
        assert comic_reader_manager_module._CLOSE_READER_ON_ERROR_DELAY_SECS > 0
