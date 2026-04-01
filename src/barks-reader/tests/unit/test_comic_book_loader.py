# ruff: noqa: SLF001

from __future__ import annotations

import io
import threading
import time
from collections import OrderedDict
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.comics_consts import PageType
from barks_reader.core import comic_book_loader as loader_module
from barks_reader.core.comic_book_loader import ComicBookLoader
from barks_reader.core.comic_book_loader_platform_settings import (
    autotune_worker_count,
    get_prefetch_tuning,
)
from barks_reader.core.fantagraphics_volumes import FantagraphicsVolumeArchives
from barks_reader.core.services import schedule_once, set_busy_cursor, set_normal_cursor

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from barks_reader.core.comic_book_page_info import PageInfo


class FakePageImageSource:
    """Test double that returns canned bytes with no I/O."""

    def __init__(self, *, delay: float = 0.0, fail: bool = False) -> None:
        self._delay = delay
        self._fail = fail
        self.load_count = 0
        self.opened = False
        self.closed = False

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.closed = True

    def load_page_image(self, _page_info: PageInfo) -> tuple[io.BytesIO, str]:
        """Return fake PNG bytes."""
        if self._delay:
            time.sleep(self._delay)
        if self._fail:
            msg = "Simulated load failure"
            raise FileNotFoundError(msg)
        self.load_count += 1
        return io.BytesIO(b"fake_png_data"), ".png"

    @staticmethod
    def get_image_info_str(page_info: PageInfo) -> str:
        """Return a fake description."""
        return f'"fake_image" (from test, page {page_info.page_index})'


@pytest.fixture
def mock_sys_file_paths(tmp_path: Path) -> MagicMock:
    """Mock the system file paths helper."""
    mock = MagicMock()
    empty_page = tmp_path / "empty_page.png"
    empty_page.write_bytes(b"fake_empty_page_data")

    mock.get_empty_page_file.return_value = str(empty_page)
    mock.get_barks_reader_fantagraphics_overrides_root_dir.return_value = str(
        tmp_path / "overrides"
    )
    return mock


@pytest.fixture
def mock_reader_settings(mock_sys_file_paths: MagicMock, tmp_path: Path) -> MagicMock:
    """Mock the reader settings."""
    mock = MagicMock()
    mock.sys_file_paths = mock_sys_file_paths
    mock.use_prebuilt_archives = True
    mock.prebuilt_comics_dir = str(tmp_path / "comics")
    mock.fantagraphics_volumes_dir = str(tmp_path / "fanta_volumes")
    return mock


@pytest.fixture
def mock_callbacks() -> dict[str, MagicMock]:
    """Mock the callbacks passed to the loader."""
    return {
        "on_first_image_loaded": MagicMock(),
        "on_all_images_loaded": MagicMock(),
        "on_load_error": MagicMock(),
    }


@pytest.fixture
def mock_services() -> Generator[tuple[MagicMock, MagicMock, MagicMock]]:
    """Patches global services like schedule_once and cursor changes."""
    with (
        patch.object(loader_module, schedule_once.__name__) as mock_schedule,
        patch.object(loader_module, set_busy_cursor.__name__) as mock_busy,
        patch.object(loader_module, set_normal_cursor.__name__) as mock_normal,
    ):
        mock_schedule.side_effect = lambda func, dt: func(dt)
        yield mock_schedule, mock_busy, mock_normal


@pytest.fixture
def mock_tuning() -> Generator[None]:
    """Patch the prefetch tuning to return simple values."""
    with patch.object(loader_module, get_prefetch_tuning.__name__) as mock_get:
        tuning = MagicMock()
        tuning.get_initial_dynamic_window.return_value = 2
        tuning.get_new_dynamic_window.return_value = (50.0, 2)
        mock_get.return_value = tuning
        yield


@pytest.fixture
def loader(
    mock_reader_settings: MagicMock,
    mock_callbacks: dict[str, MagicMock],
    mock_services: tuple[MagicMock, MagicMock, MagicMock],  # noqa: ARG001
    mock_tuning: None,  # noqa: ARG001
) -> Generator[ComicBookLoader]:
    """Create a ComicBookLoader instance with mocked dependencies."""
    # Patch autotune to use 1 worker for deterministic testing
    with patch.object(loader_module, autotune_worker_count.__name__, return_value=1):
        loader_instance = ComicBookLoader(
            reader_settings=mock_reader_settings,
            on_first_image_loaded=mock_callbacks["on_first_image_loaded"],
            on_all_images_loaded=mock_callbacks["on_all_images_loaded"],
            on_load_error=mock_callbacks["on_load_error"],
            max_window_width=800,
            max_window_height=600,
        )
        yield loader_instance
        loader_instance.stop_now()


@pytest.fixture
def page_map_and_order() -> tuple[OrderedDict[str, Any], list[str]]:
    """Create a sample page map and load order."""
    p1 = MagicMock()
    p1.page_index = 0
    p1.dest_page.page_filename = "page_1.png"
    p1.srce_page.page_filename = "page_1.png"
    p1.display_page_num = "1"
    p1.page_type = PageType.BODY

    p2 = MagicMock()
    p2.page_index = 1
    p2.dest_page.page_filename = "page_2.png"
    p2.srce_page.page_filename = "page_2.png"
    p2.display_page_num = "2"
    p2.page_type = PageType.BODY

    page_map = OrderedDict([("p1", p1), ("p2", p2)])
    load_order = ["p1", "p2"]
    return page_map, load_order


def test_init(loader: ComicBookLoader, mock_reader_settings: MagicMock) -> None:
    """Test initialization of the loader."""
    assert loader._reader_settings == mock_reader_settings
    assert loader._max_worker_count == 1
    assert loader._empty_page_image == b"fake_empty_page_data"


def test_init_data_prebuilt(loader: ComicBookLoader, mock_reader_settings: MagicMock) -> None:
    """Test init_data when using prebuilt archives."""
    mock_reader_settings.use_prebuilt_archives = True
    loader.init_data()
    assert loader._fanta_volume_archives is None


def test_init_data_fanta_volumes(loader: ComicBookLoader, mock_reader_settings: MagicMock) -> None:
    """Test init_data when using Fantagraphics volumes."""
    mock_reader_settings.use_prebuilt_archives = False

    with patch.object(loader_module, FantagraphicsVolumeArchives.__name__) as mock_archives:
        loader.init_data()
        mock_archives.assert_called_once()
        mock_archives.return_value.load.assert_called_once()


def test_set_comic_and_load_success(
    loader: ComicBookLoader,
    page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
    mock_callbacks: dict[str, MagicMock],
) -> None:
    """Test loading via FakePageImageSource — no I/O patches needed."""
    page_map, load_order = page_map_and_order
    source = FakePageImageSource()

    loader.set_comic(source, load_order, page_map, archive_desc="test_comic.cbz")  # ty: ignore[invalid-argument-type]

    if loader._thread:
        loader._thread.join(timeout=2.0)

    mock_callbacks["on_first_image_loaded"].assert_called_once()
    mock_callbacks["on_all_images_loaded"].assert_called_once()
    mock_callbacks["on_load_error"].assert_not_called()

    assert source.load_count == 2  # noqa: PLR2004
    assert source.opened
    assert len(loader._images) == 2  # noqa: PLR2004
    assert loader._images[0] is not None
    assert loader._images[1] is not None


def test_load_error_file_not_found(
    loader: ComicBookLoader,
    page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
    mock_callbacks: dict[str, MagicMock],
) -> None:
    """Test handling of a source that raises FileNotFoundError."""
    page_map, load_order = page_map_and_order
    source = FakePageImageSource(fail=True)

    loader.set_comic(source, load_order, page_map, archive_desc="missing_comic.cbz")  # ty: ignore[invalid-argument-type]

    if loader._thread:
        loader._thread.join(timeout=2.0)

    mock_callbacks["on_load_error"].assert_called_once()


def test_stop_now(loader: ComicBookLoader) -> None:
    """Test stopping the loader thread."""
    stop_event = threading.Event()

    def dummy_worker() -> None:
        while not loader._stop and not stop_event.is_set():
            pass

    t = threading.Thread(target=dummy_worker)
    loader._thread = t
    t.start()

    loader.stop_now()

    assert loader._stop is True
    assert not t.is_alive()

    stop_event.set()
    t.join()


def test_close_comic_calls_source_close(
    loader: ComicBookLoader,
    page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
) -> None:
    """Test that close_comic calls close() on the image source."""
    page_map, load_order = page_map_and_order
    source = FakePageImageSource()

    loader.set_comic(source, load_order, page_map, archive_desc="test.cbz")  # ty: ignore[invalid-argument-type]

    if loader._thread:
        loader._thread.join(timeout=2.0)

    loader.close_comic()

    assert source.closed


def test_stop_cancels_inflight_loads(
    loader: ComicBookLoader,
    page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
) -> None:
    """Test that stop_now prevents loading all pages."""
    page_map, load_order = page_map_and_order
    source = FakePageImageSource(delay=0.5)

    loader.set_comic(source, load_order, page_map, archive_desc="slow.cbz")  # ty: ignore[invalid-argument-type]
    time.sleep(0.1)
    loader.stop_now()

    assert source.load_count < len(page_map)


def test_get_image_info_str_delegates_to_source(
    loader: ComicBookLoader,
    page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
) -> None:
    """Test that get_image_info_str delegates to the image source."""
    page_map, load_order = page_map_and_order
    source = FakePageImageSource()

    loader.set_comic(source, load_order, page_map, archive_desc="test.cbz")  # ty: ignore[invalid-argument-type]

    if loader._thread:
        loader._thread.join(timeout=2.0)

    info_str = loader.get_image_info_str("p1")
    assert "fake_image" in info_str
