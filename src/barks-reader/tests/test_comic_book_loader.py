# ruff: noqa: SLF001, PLR2004

from __future__ import annotations

import io
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_titles import ComicBookInfo
from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
from barks_reader.comic_book_loader import ComicBookLoader
from barks_reader.comic_book_page_info import PageInfo

if TYPE_CHECKING:
    from collections.abc import Generator


class TestComicBookLoader:
    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None]:
        self.mock_settings = MagicMock()
        self.mock_settings.sys_file_paths.get_empty_page_file.return_value = "empty.png"

        self.mock_on_first = MagicMock()
        self.mock_on_all = MagicMock()
        self.mock_on_error = MagicMock()

        # Mock file reading in __init__ for empty page image
        self.open_patcher = patch("pathlib.Path.open", new_callable=MagicMock)
        self.mock_open = self.open_patcher.start()
        self.mock_file_handle = MagicMock()
        self.mock_open.return_value.__enter__.return_value = self.mock_file_handle
        self.mock_file_handle.read.return_value = b"empty_bytes"

        # Mock threading to prevent actual threads starting automatically
        self.thread_patcher = patch("threading.Thread")
        self.mock_thread_cls = self.thread_patcher.start()

        # Mock autotune to return 1 worker for simplicity
        self.autotune_patcher = patch(
            "barks_reader.comic_book_loader.autotune_worker_count", return_value=1
        )
        self.autotune_patcher.start()

        self.loader = ComicBookLoader(
            self.mock_settings,
            self.mock_on_first,
            self.mock_on_all,
            self.mock_on_error,
            1000,
            1000,
        )

        yield

        self.open_patcher.stop()
        self.thread_patcher.stop()
        self.autotune_patcher.stop()

    def test_init_data_prebuilt(self) -> None:
        self.mock_settings.use_prebuilt_archives = True
        self.loader.init_data()
        # noinspection PyProtectedMember
        assert self.loader._fanta_volume_archives is None

    @patch("barks_reader.comic_book_loader.FantagraphicsVolumeArchives")
    def test_init_data_fanta(self, mock_archives_cls: MagicMock) -> None:
        self.mock_settings.use_prebuilt_archives = False
        self.mock_settings.fantagraphics_volumes_dir = Path("/fanta")

        sys_file_paths = self.mock_settings.sys_file_paths
        sys_file_paths.get_barks_reader_fantagraphics_overrides_root_dir.return_value = Path(
            "/overrides"
        )

        self.loader.init_data()

        mock_archives_cls.assert_called_once()
        # noinspection PyProtectedMember
        mock_archives_cls.return_value.load.assert_called_once()

    def test_set_comic_prebuilt(self) -> None:
        self.mock_settings.use_prebuilt_archives = True
        self.mock_settings.prebuilt_comics_dir = "/prebuilt"

        mock_fanta_info = MagicMock(spec=FantaComicBookInfo)

        mock_comic_info = MagicMock(spec=ComicBookInfo)
        mock_comic_info.get_title_str.return_value = "Title"
        mock_fanta_info.comic_book_info = mock_comic_info

        mock_fanta_info.fanta_chronological_number = 1
        mock_fanta_info.get_short_issue_title.return_value = "FC 1"

        mock_builder = MagicMock()
        page_map = OrderedDict([("1", MagicMock())])
        load_order = ["1"]

        # Mock path existence checks
        with patch("pathlib.Path.is_file", return_value=True):
            self.loader.set_comic(
                mock_fanta_info,
                use_fantagraphics_overrides=False,
                comic_book_image_builder=mock_builder,
                image_load_order=load_order,
                page_map=page_map,
            )

        # Check path construction (windows/linux separators handled by Path)
        expected_path = Path("/prebuilt") / "001 Title [FC 1].cbz"
        # noinspection PyProtectedMember
        assert self.loader._current_comic_path == expected_path
        self.mock_thread_cls.return_value.start.assert_called_once()

    def test_close_comic(self) -> None:
        # noinspection PyProtectedMember
        self.loader._current_comic_path = "some/path"
        # noinspection PyProtectedMember
        mock_thread = MagicMock()
        self.loader._thread = mock_thread
        # noinspection PyProtectedMember
        mock_thread.is_alive.return_value = True

        self.loader.close_comic()

        # noinspection PyProtectedMember
        assert self.loader._stop is True
        # noinspection PyProtectedMember
        mock_thread.join.assert_called()
        # noinspection PyProtectedMember
        assert self.loader._current_comic_path == ""
        # noinspection PyProtectedMember
        assert len(self.loader._images) == 0

    def test_get_image_ready_for_reading(self) -> None:
        # Setup fake loaded images
        # noinspection PyProtectedMember
        self.loader._images = [(io.BytesIO(b"img1"), "png"), (io.BytesIO(b"img2"), "jpg")]

        stream, ext = self.loader.get_image_ready_for_reading(1)
        assert stream.read() == b"img2"
        assert ext == "jpg"

    @patch("barks_reader.comic_book_loader.zipfile.ZipFile")
    @patch("barks_reader.comic_book_loader.Clock")
    def test_load_comic_in_thread_success(
        self,
        mock_clock: MagicMock,
        _mock_zipfile: MagicMock,  # noqa: PT019
    ) -> None:
        # Setup
        # noinspection PyProtectedMember
        self.loader._current_comic_path = "test.cbz"
        page_info = MagicMock(spec=PageInfo)
        page_info.page_index = 0
        page_info.display_page_num = "1"
        # noinspection PyProtectedMember
        self.loader._page_map = OrderedDict([("1", page_info)])
        # noinspection PyProtectedMember
        self.loader._image_load_order = ["1"]
        # noinspection PyProtectedMember
        self.loader._init_load_events()  # Initialize events based on page map

        def mock_load_pages_side_effect(*_args, **_kwargs) -> int:  # noqa: ANN002, ANN003
            # Simulate the side effect of _load_pages, which is setting the event
            self.loader._image_loaded_events[0].set()
            return 1

        # Mock _load_pages to simulate loading
        with patch.object(
            self.loader, "_load_pages", side_effect=mock_load_pages_side_effect
        ) as mock_load_pages:
            # noinspection PyProtectedMember
            self.loader._load_comic_in_thread()

            mock_load_pages.assert_called_once()
            # Check callback scheduled
            # The lambda passed to schedule_once calls _on_all_images_loaded
            args, _ = mock_clock.schedule_once.call_args
            # Execute the lambda to verify it calls the right method
            args[0](0)
            self.mock_on_all.assert_called_once()

    @patch("barks_reader.comic_book_loader.zipfile.ZipFile")
    @patch("barks_reader.comic_book_loader.Clock")
    def test_load_comic_in_thread_file_not_found(
        self, mock_clock: MagicMock, mock_zipfile: MagicMock
    ) -> None:
        # noinspection PyProtectedMember
        self.loader._current_comic_path = "missing.cbz"
        mock_zipfile.side_effect = FileNotFoundError
        # noinspection PyProtectedMember
        self.loader._page_map = OrderedDict([("1", MagicMock())])
        # noinspection PyProtectedMember
        self.loader._images = [None]  # Initialize images list

        with (
            patch("barks_reader.comic_book_loader.set_kivy_busy_cursor"),
            patch("barks_reader.comic_book_loader.set_kivy_normal_cursor"),
        ):
            # noinspection PyProtectedMember
            self.loader._load_comic_in_thread()

        # noinspection PyProtectedMember
        assert self.loader._stop is True
        # Check that on_load_error was scheduled
        mock_clock.schedule_once.assert_called()

    def test_wait_load_event(self) -> None:
        # noinspection PyProtectedMember
        self.loader._images = [None]
        mock_event = MagicMock()
        # noinspection PyProtectedMember
        self.loader._image_loaded_events = [mock_event]

        self.loader.wait_load_event(0, 1.0)
        mock_event.wait.assert_called_with(1.0)

    def test_get_image_path_prebuilt(self) -> None:
        # noinspection PyProtectedMember
        self.loader._fanta_volume_archive = None
        page_info = MagicMock()
        page_info.dest_page.page_filename = "p1.png"

        # noinspection PyProtectedMember
        path, is_archive = self.loader._get_image_path(page_info)
        assert path == "images/p1.png"
        assert is_archive is True

    @patch("barks_reader.comic_book_loader.ThreadPoolExecutor")
    @patch("barks_reader.comic_book_loader.get_prefetch_tuning")
    def test_load_pages_logic(self, mock_get_tuning: MagicMock, mock_executor: MagicMock) -> None:
        # Setup for _load_pages
        # noinspection PyProtectedMember
        self.loader._image_load_order = ["1", "2"]
        p1 = MagicMock(page_index=0)
        p2 = MagicMock(page_index=1)
        # noinspection PyProtectedMember
        self.loader._page_map = OrderedDict([("1", p1), ("2", p2)])
        # noinspection PyProtectedMember
        self.loader._images = [None, None]
        # noinspection PyProtectedMember
        self.loader._image_loaded_events = [MagicMock(), MagicMock()]

        # Mock tuning
        mock_tuning = MagicMock()
        mock_tuning.get_initial_dynamic_window.return_value = 2
        mock_tuning.get_new_dynamic_window.return_value = (100, 2)
        mock_get_tuning.return_value = mock_tuning

        # Mock executor
        mock_future1 = MagicMock()
        mock_future1.result.return_value = (io.BytesIO(b"1"), "png")
        mock_future2 = MagicMock()
        mock_future2.result.return_value = (io.BytesIO(b"2"), "png")

        mock_executor_instance = mock_executor.return_value.__enter__.return_value
        mock_executor_instance.submit.side_effect = [mock_future1, mock_future2]

        # Mock wait to return futures as done
        with patch("barks_reader.comic_book_loader.wait") as mock_wait:
            # First call returns future1, second call returns future2
            mock_wait.side_effect = [({mock_future1}, set()), ({mock_future2}, set())]

            archive = MagicMock()
            # noinspection PyProtectedMember
            num_loaded = self.loader._load_pages(archive)

            assert num_loaded == 2
            # noinspection PyProtectedMember
            assert self.loader._images[0][0].getvalue() == b"1"  # type: ignore[index]
            # noinspection PyProtectedMember
            assert self.loader._images[1][0].getvalue() == b"2"  # type: ignore[index]
