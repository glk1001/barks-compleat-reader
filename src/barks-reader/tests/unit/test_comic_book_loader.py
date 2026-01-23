# ruff: noqa: SLF001

from __future__ import annotations

import io
import threading
import zipfile
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
from barks_reader.core import comic_book_loader as loader_module
from barks_reader.core.comic_book_loader import ComicBookLoader
from barks_reader.core.comic_book_loader_platform_settings import (
    autotune_worker_count,
    get_prefetch_tuning,
)
from barks_reader.core.fantagraphics_volumes import FantagraphicsVolumeArchives
from barks_reader.core.services import schedule_once, set_busy_cursor, set_normal_cursor
from comic_utils.pil_image_utils import (
    get_pil_image_as_png_bytes,
    load_pil_image_from_bytes,
    load_pil_image_from_zip,
)
from PIL import Image, ImageOps

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_sys_file_paths(tmp_path: Path) -> MagicMock:
    """Mock the system file paths helper."""
    mock = MagicMock()
    # Create a dummy empty page file
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
        # Execute scheduled callbacks immediately
        mock_schedule.side_effect = lambda func, dt: func(dt)

        yield mock_schedule, mock_busy, mock_normal


@pytest.fixture
def mock_pil_utils() -> Generator[tuple[MagicMock, MagicMock, MagicMock, MagicMock]]:
    """Patch PIL image utilities to avoid real image processing."""
    with (
        patch.object(loader_module, load_pil_image_from_zip.__name__) as mock_load_zip,
        patch.object(loader_module, load_pil_image_from_bytes.__name__) as mock_load_bytes,
        patch.object(loader_module, get_pil_image_as_png_bytes.__name__) as mock_get_bytes,
        patch.object(loader_module.ImageOps, ImageOps.contain.__name__) as mock_contain,
    ):
        mock_image = MagicMock(spec=Image.Image)
        mock_load_zip.return_value = mock_image
        mock_load_bytes.return_value = mock_image
        mock_contain.return_value = mock_image

        # Return a BytesIO object for the png bytes
        mock_get_bytes.return_value = io.BytesIO(b"processed_png_data")

        yield mock_load_zip, mock_load_bytes, mock_get_bytes, mock_contain


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
    mock_pil_utils: tuple[MagicMock, MagicMock, MagicMock, MagicMock],  # noqa: ARG001
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


# noinspection LongLine
@pytest.fixture
def dummy_cbz(tmp_path: Path, page_map_and_order: tuple[OrderedDict[str, Any], list[str]]) -> Path:  # noqa: ARG001
    """Create a valid temporary CBZ file matching the page map."""
    cbz_path = tmp_path / "test_comic.cbz"
    with zipfile.ZipFile(cbz_path, "w") as zf:
        # The loader looks for "images/" + filename for prebuilt archives
        zf.writestr("images/page_1.png", b"fake_image_1")
        zf.writestr("images/page_2.png", b"fake_image_2")
    return cbz_path


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
    dummy_cbz: Path,
    page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
    mock_callbacks: dict[str, MagicMock],
) -> None:
    """Test setting a comic and successfully loading it in the background thread."""
    page_map, load_order = page_map_and_order
    fanta_info = MagicMock(spec=FantaComicBookInfo)
    builder = MagicMock()

    # Patch _get_prebuilt_comic_path to return our dummy CBZ
    with patch.object(
        loader, ComicBookLoader._get_prebuilt_comic_path.__name__, return_value=dummy_cbz
    ):
        loader.set_comic(
            fanta_info=fanta_info,
            use_fantagraphics_overrides=False,
            comic_book_image_builder=builder,
            image_load_order=load_order,
            page_map=page_map,
        )

        # Wait for the background thread to finish
        if loader._thread:
            loader._thread.join(timeout=2.0)

    # Verify callbacks
    mock_callbacks["on_first_image_loaded"].assert_called_once()
    mock_callbacks["on_all_images_loaded"].assert_called_once()
    mock_callbacks["on_load_error"].assert_not_called()

    # Verify images loaded
    assert len(loader._images) == 2  # noqa: PLR2004
    assert loader._images[0] is not None
    assert loader._images[1] is not None


def test_load_error_file_not_found(
    loader: ComicBookLoader,
    page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
    mock_callbacks: dict[str, MagicMock],
) -> None:
    """Test handling of a missing comic file."""
    page_map, load_order = page_map_and_order
    fanta_info = MagicMock(spec=FantaComicBookInfo)

    # Point to a non-existent file
    with patch.object(
        loader,
        ComicBookLoader._get_prebuilt_comic_path.__name__,
        return_value=Path("non_existent.cbz"),
    ):
        loader.set_comic(
            fanta_info,
            use_fantagraphics_overrides=False,
            comic_book_image_builder=MagicMock(),
            image_load_order=load_order,
            page_map=page_map,
        )
        if loader._thread:
            loader._thread.join(timeout=2.0)

    mock_callbacks["on_load_error"].assert_called_once_with(False)  # noqa: FBT003


def test_stop_now(loader: ComicBookLoader) -> None:
    """Test stopping the loader thread."""
    # Manually simulate a running thread to avoid complex race conditions with real loading
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

    # Cleanup
    stop_event.set()
    t.join()
