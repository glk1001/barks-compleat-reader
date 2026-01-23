# ruff: noqa: SLF001  # noqa: INP001

from __future__ import annotations

import io
import re
import threading
import zipfile
from collections import OrderedDict
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import barks_reader.comic_book_reader
import pytest
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.comics_utils import get_dest_comic_zip_file_stem
from barks_reader.comic_book_reader import ComicBookReader
from barks_reader.core.comic_book_page_info import PageInfo
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE
from loguru import logger
from PIL import Image as PilImage

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from pytest_benchmark.fixture import BenchmarkFixture


REAL_COMIC_BOOK_FILE = Path("/tmp/099 Lost in the Andes! [FC 223].cbz")  # noqa: S108
TEST_COMIC_PAGE_FILE = Path(__file__).parent / "comic-book-load-test-image.jpg"


class TestComicReaderLoadTime:
    @pytest.fixture
    def comic_data(self, tmp_path: Path) -> tuple[Path, OrderedDict[str, PageInfo], MagicMock]:
        """Use a real CBZ file if it exists, otherwise generate a temporary one."""
        if REAL_COMIC_BOOK_FILE.is_file():
            return self.get_real_comic_data()

        return self.temp_comic_data(tmp_path)

    @staticmethod
    def temp_comic_data(tmp_path: Path) -> tuple[Path, OrderedDict[str, PageInfo], MagicMock]:
        assert True
        logger.info(f'Using temporary generated zip based off "{TEST_COMIC_PAGE_FILE}".')
        assert TEST_COMIC_PAGE_FILE.is_file()
        test_image = PilImage.open(TEST_COMIC_PAGE_FILE)
        img = test_image
        img_byte_arr = io.BytesIO()
        img.save(
            img_byte_arr,
            format="JPEG",
            quality=95,
            optimize=True,
            compress_level=9,
        )
        logger.info(f'Width, height = {img.width}, {img.height}".')

        comics_dir = tmp_path
        title = "Benchmark Title"
        chrono_num = 1
        issue_title = "FC 1"

        file_stem = get_dest_comic_zip_file_stem(title, chrono_num, issue_title)
        cbz_path = comics_dir / f"{file_stem}.cbz"
        logger.info(f'Using temporary generated zip "{cbz_path}".')

        num_pages = 41
        page_map = OrderedDict()

        # Create a zip file with real images
        with zipfile.ZipFile(cbz_path, "w") as zf:
            for i in range(num_pages):
                page_str = str(i + 1)
                filename = f"page_{i:03d}.jpg"

                zf.writestr(f"images/{filename}", img_byte_arr.getvalue())

                # Create PageInfo
                srce_page = MagicMock()
                srce_page.page_filename = filename
                srce_page.page_type = PageType.BODY

                dest_page = MagicMock()
                dest_page.page_filename = filename
                dest_page.page_type = PageType.BODY

                page_map[page_str] = PageInfo(
                    page_index=i,
                    page_type=PageType.BODY,
                    display_page_num=page_str,
                    srce_page=srce_page,
                    dest_page=dest_page,
                )

        fanta_info = MagicMock()
        fanta_info.comic_book_info.get_title_str.return_value = title
        fanta_info.fanta_chronological_number = chrono_num
        fanta_info.get_short_issue_title.return_value = issue_title

        return comics_dir, page_map, fanta_info

    @staticmethod
    def get_real_comic_data() -> tuple[Path, OrderedDict[str, PageInfo], MagicMock]:
        logger.info(f'Using real comic book file "{REAL_COMIC_BOOK_FILE}".')
        cbz_path = REAL_COMIC_BOOK_FILE
        comics_dir = REAL_COMIC_BOOK_FILE.parent

        # Parse info from the filename.
        match = re.match(r"(\d+)\s+(.*)\s+\[(.*)]", cbz_path.stem)
        if not match:
            msg = f"Could not parse real CBZ filename: {cbz_path.name}"
            raise ValueError(msg)
        chrono_num = int(match.group(1))
        title = match.group(2)
        issue_title = match.group(3)

        page_map = OrderedDict()
        with zipfile.ZipFile(cbz_path, "r") as zf:
            image_files = sorted(
                [
                    f
                    for f in zf.namelist()
                    if f.startswith("images/") and f.lower().endswith((".jpg", ".jpeg", ".png"))
                ]
            )
            for i, image_path in enumerate(image_files):
                page_str = str(i + 1)
                filename = Path(image_path).name

                srce_page = MagicMock(page_filename=filename, page_type=PageType.BODY)
                dest_page = MagicMock(page_filename=filename, page_type=PageType.BODY)

                page_map[page_str] = PageInfo(
                    page_index=i,
                    page_type=PageType.BODY,
                    display_page_num=page_str,
                    srce_page=srce_page,
                    dest_page=dest_page,
                )

        fanta_info = MagicMock()
        fanta_info.comic_book_info.get_title_str.return_value = title
        fanta_info.fanta_chronological_number = chrono_num
        fanta_info.get_short_issue_title.return_value = issue_title

        return comics_dir, page_map, fanta_info

    @pytest.fixture
    def reader_setup(
        self, comic_data: tuple[Path, OrderedDict, MagicMock]
    ) -> Generator[tuple[ComicBookReader, Event, Event], Event]:
        comics_dir, _, _ = comic_data

        settings = MagicMock()
        settings.use_prebuilt_archives = True
        settings.prebuilt_comics_dir = str(comics_dir)
        settings.sys_file_paths.get_empty_page_file.return_value = "empty.png"

        font_manager = MagicMock()

        first_image_loaded = threading.Event()
        all_images_loaded = threading.Event()

        def on_first_loaded() -> None:
            first_image_loaded.set()

        def on_all_loaded() -> None:
            all_images_loaded.set()

        on_toggle = MagicMock()

        def mock_schedule_once(callback: Callable[[int], None], _timeout: int = 0) -> None:
            callback(0)

        with (
            patch("barks_reader.comic_book_reader.Image"),
            patch("barks_reader.comic_book_reader.ReaderNavigation"),
            patch("barks_reader.comic_book_reader.get_image_stream"),
            patch("barks_reader.comic_book_reader.get_monitors") as mock_monitors,
            patch("kivy.uix.floatlayout.FloatLayout.add_widget"),
            patch.object(barks_reader.comic_book_reader, "Clock") as mock_reader_clock,
            patch("pathlib.Path.open", new_callable=MagicMock) as mock_open,
        ):
            mock_monitors.return_value = [MagicMock(width=1920, height=1080)]

            mock_reader_clock.schedule_once.side_effect = mock_schedule_once

            mock_file = MagicMock()
            mock_file.read.return_value = b"empty_bytes"
            mock_open.return_value.__enter__.return_value = mock_file

            reader = ComicBookReader(settings, font_manager, on_first_loaded, on_toggle)

            # noinspection PyProtectedMember
            reader._comic_book_loader._on_all_images_loaded = on_all_loaded

            with (
                patch.object(reader, "_show_page", MagicMock()),
                patch.object(reader, "_wait_for_image_to_load", MagicMock()),
                patch.object(reader, "_load_error", MagicMock()),
            ):
                yield reader, first_image_loaded, all_images_loaded

    def test_first_image_load_benchmark(
        self,
        benchmark: BenchmarkFixture,
        reader_setup: tuple[ComicBookReader, threading.Event, threading.Event],
        comic_data: tuple[Path, OrderedDict, MagicMock],
    ) -> None:
        reader, first_loaded_event, all_loaded_event = reader_setup
        _, page_map, fanta_info = comic_data
        builder = MagicMock()

        def setup() -> None:
            first_loaded_event.clear()
            all_loaded_event.clear()

        def teardown() -> None:
            reader.close_comic_book_reader()

        def run_load_and_wait() -> None:
            reader.read_comic(
                fanta_info,
                use_fantagraphics_overrides=False,
                comic_book_image_builder=builder,
                page_to_first_goto=COMIC_BEGIN_PAGE,
                page_map=page_map,
            )
            if not first_loaded_event.wait(timeout=30.0):
                msg = "Timed out waiting for first image to load"
                raise TimeoutError(msg)

        benchmark.pedantic(
            run_load_and_wait,
            setup=setup,
            teardown=teardown,
            rounds=10,
            iterations=1,
        )

    def test_all_images_load_benchmark(
        self,
        benchmark: BenchmarkFixture,
        reader_setup: tuple[ComicBookReader, threading.Event, threading.Event],
        comic_data: tuple[Path, OrderedDict, MagicMock],
    ) -> None:
        reader, first_loaded_event, all_loaded_event = reader_setup
        _, page_map, fanta_info = comic_data
        builder = MagicMock()

        def setup() -> None:
            first_loaded_event.clear()
            all_loaded_event.clear()

        def teardown() -> None:
            reader.close_comic_book_reader()

        def run_load_and_wait() -> None:
            reader.read_comic(
                fanta_info,
                use_fantagraphics_overrides=False,
                comic_book_image_builder=builder,
                page_to_first_goto=COMIC_BEGIN_PAGE,
                page_map=page_map,
            )
            if not all_loaded_event.wait(timeout=30.0):
                msg = "Timed out waiting for all images to load"
                raise TimeoutError(msg)

        benchmark.pedantic(
            run_load_and_wait,
            setup=setup,
            teardown=teardown,
            rounds=5,
            iterations=1,
        )
