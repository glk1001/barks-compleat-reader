# ruff: noqa: SLF001

from __future__ import annotations

import io
import threading
import time
import zipfile
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
from barks_reader.core.testing import FakeScheduler, RecordingCursor

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

    def load_page_image(self, page_info: PageInfo) -> tuple[io.BytesIO, str]:  # noqa: ARG002
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
def fake_scheduler() -> FakeScheduler:
    """Inline scheduler — `schedule_once` callbacks run on the calling thread."""
    return FakeScheduler()


@pytest.fixture
def recording_cursor() -> RecordingCursor:
    """Capture every busy/normal cursor transition for assertions."""
    return RecordingCursor()


@pytest.fixture
def mock_tuning() -> Generator[None]:
    """Patch the prefetch tuning to return simple values."""
    with patch.object(loader_module, get_prefetch_tuning.__name__) as mock_get:
        tuning = MagicMock()
        tuning.get_initial_dynamic_window.return_value = 2
        tuning.get_new_dynamic_window.return_value = (50.0, 2)
        tuning.get_traced_peak_mib.return_value = 12.5
        mock_get.return_value = tuning
        yield


@pytest.fixture
def loader(
    mock_reader_settings: MagicMock,
    mock_callbacks: dict[str, MagicMock],
    fake_scheduler: FakeScheduler,
    recording_cursor: RecordingCursor,
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
            scheduler=fake_scheduler,
            cursor=recording_cursor,
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


def test_init_data_retains_archives_when_volumes_missing(
    loader: ComicBookLoader, mock_reader_settings: MagicMock, tmp_path: Path
) -> None:
    """A missing-volumes load still keeps the (placeholder) archive set.

    load() builds every volume - present ones plus missing placeholders carrying
    their bundled override/extra pages - and then re-raises. The built set must be
    retained so a later resolve reads bundled stories instead of re-init/re-raising.
    """
    from barks_reader.core.fantagraphics_volumes import (  # noqa: PLC0415
        MissingArchiveFilesError,
    )

    mock_reader_settings.use_prebuilt_archives = False

    with patch.object(loader_module, FantagraphicsVolumeArchives.__name__) as mock_archives:
        built = mock_archives.return_value
        built.load.side_effect = MissingArchiveFilesError([1, 2, 3], tmp_path)

        with pytest.raises(MissingArchiveFilesError):
            loader.init_data()

        # The fully-built archive set is retained despite the raise.
        assert loader._fanta_volume_archives is built


def test_set_comic_and_load_success(
    loader: ComicBookLoader,
    page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
    mock_callbacks: dict[str, MagicMock],
) -> None:
    """Test loading via FakePageImageSource — no I/O patches needed."""
    page_map, load_order = page_map_and_order
    source = FakePageImageSource()

    loader.set_comic(source, load_order, page_map, archive_desc="test_comic.cbz")
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


def test_cursor_restored_at_first_page_ready(
    loader: ComicBookLoader,
    page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
    recording_cursor: RecordingCursor,
) -> None:
    """The busy cursor is released once the first page is readable, not at load end."""
    page_map, load_order = page_map_and_order
    release_last_page = threading.Event()

    class GatedPageImageSource(FakePageImageSource):
        """Blocks every page after the first until the test releases them."""

        def load_page_image(self, page_info: PageInfo) -> tuple[io.BytesIO, str]:
            if page_info.page_index > 0:
                release_last_page.wait(timeout=2.0)
            return super().load_page_image(page_info)

    loader.set_comic(GatedPageImageSource(), load_order, page_map, archive_desc="gated.cbz")

    deadline = time.monotonic() + 2.0
    while "normal" not in recording_cursor.states and time.monotonic() < deadline:
        time.sleep(0.01)

    # First page delivered, last page still gated: cursor must already be back to normal.
    assert recording_cursor.states == ["busy", "normal"]

    release_last_page.set()
    if loader._thread:
        loader._thread.join(timeout=2.0)

    assert recording_cursor.states == ["busy", "normal", "normal"]


class OrderRecordingSource:
    """Records the order pages are loaded, gating one page until released."""

    def __init__(
        self, block_index: int, started: threading.Event, release: threading.Event
    ) -> None:
        self.load_order: list[int] = []
        self._block_index = block_index
        self._started = started
        self._release = release
        self.opened = False

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        pass

    def load_page_image(self, page_info: PageInfo) -> tuple[io.BytesIO, str]:
        idx = page_info.page_index
        if idx == self._block_index:
            self._started.set()
            self._release.wait(timeout=2.0)
        self.load_order.append(idx)
        return io.BytesIO(b"fake_png_data"), ".png"

    @staticmethod
    def get_image_info_str(page_info: PageInfo) -> str:  # noqa: ARG004
        return "fake_image"


def _make_indexed_page_map(count: int) -> tuple[OrderedDict[str, Any], list[str]]:
    """Build a `count`-page map keyed "0".."N-1" with a natural forward load order."""
    page_map: OrderedDict[str, Any] = OrderedDict()
    for i in range(count):
        page = MagicMock()
        page.page_index = i
        page.srce_page.page_filename = f"page_{i}.png"
        page.page_type = PageType.BODY
        page_map[str(i)] = page
    return page_map, [str(i) for i in range(count)]


def test_prioritize_page_loads_navigated_page_before_later_pages(
    loader: ComicBookLoader,
) -> None:
    """A prioritized (navigated-to) page loads ahead of its normal load-order slot.

    With a single worker and a 2-page prefetch window, page 0 is gated while the
    test asks the loader to prioritize page 4. Once page 0 is released, page 4 must
    be fetched before pages 2 and 3, which would otherwise load first.
    """
    page_map, load_order = _make_indexed_page_map(5)
    started = threading.Event()
    release = threading.Event()
    source = OrderRecordingSource(block_index=0, started=started, release=release)

    loader.set_comic(source, load_order, page_map, archive_desc="prioritize.cbz")

    assert started.wait(2.0)  # page 0 is loading -> the initial window has been primed
    loader.prioritize_page(4)
    release.set()

    assert loader._thread is not None
    loader._thread.join(timeout=2.0)

    order = source.load_order
    assert set(order) == {0, 1, 2, 3, 4}  # every page still loaded exactly once
    assert order.index(4) < order.index(2)
    assert order.index(4) < order.index(3)


def test_prioritize_page_is_noop_when_page_already_loaded(
    loader: ComicBookLoader,
    page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
) -> None:
    """Prioritizing an already-loaded page enqueues nothing."""
    page_map, load_order = page_map_and_order
    source = FakePageImageSource()

    loader.set_comic(source, load_order, page_map, archive_desc="test.cbz")
    if loader._thread:
        loader._thread.join(timeout=2.0)

    assert loader._priority_keys.empty()
    loader.prioritize_page(0)  # already loaded
    assert loader._priority_keys.empty()


def test_load_error_file_not_found(
    loader: ComicBookLoader,
    page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
    mock_callbacks: dict[str, MagicMock],
) -> None:
    """Test handling of a source that raises FileNotFoundError."""
    page_map, load_order = page_map_and_order
    source = FakePageImageSource(fail=True)

    loader.set_comic(source, load_order, page_map, archive_desc="missing_comic.cbz")
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

    loader.set_comic(source, load_order, page_map, archive_desc="test.cbz")
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

    loader.set_comic(source, load_order, page_map, archive_desc="slow.cbz")
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

    loader.set_comic(source, load_order, page_map, archive_desc="test.cbz")
    if loader._thread:
        loader._thread.join(timeout=2.0)

    info_str = loader.get_image_info_str("p1")
    assert "fake_image" in info_str


# ---------------------------------------------------------------------------
# resolve_archive_for_comic + _get_prebuilt_comic_path + double-page composite
# ---------------------------------------------------------------------------


def _make_fanta_info(
    *,
    title: str = "Adventure Down Under",
    chrono: int = 42,
    issue: str = "WDC 100",
    volume: str = "FANTA_07",
) -> MagicMock:
    """Build a FantaComicBookInfo stub with the fields read by the loader."""
    info = MagicMock()
    info.comic_book_info.get_title_str.return_value = title
    info.comic_book_info.title = title
    info.fanta_chronological_number = chrono
    info.get_short_issue_title.return_value = issue
    info.fantagraphics_volume = volume
    return info


def _make_page_map(
    *, page_filename: str = "258.jpg", page_type: PageType = PageType.BODY
) -> OrderedDict[str, MagicMock]:
    """Build a one-page page_map with the fields the resolve gate reads."""
    page_info = MagicMock()
    page_info.srce_page.page_filename = page_filename
    page_info.page_type = page_type
    return OrderedDict({"1": page_info})


def test_resolve_archive_for_comic_returns_prebuilt_when_setting_enabled(
    loader: ComicBookLoader,
    mock_reader_settings: MagicMock,
    tmp_path: Path,
) -> None:
    """Prebuilt branch: returns the on-disk cbz path and None for the volume archive."""
    mock_reader_settings.use_prebuilt_archives = True
    comics_dir = tmp_path / "comics"
    comics_dir.mkdir()
    mock_reader_settings.prebuilt_comics_dir = str(comics_dir)

    fanta_info = _make_fanta_info(title="Lost in the Andes", chrono=77, issue="FC 223")
    expected_stem = "077 Lost in the Andes [FC 223]"
    expected_path = comics_dir / f"{expected_stem}.cbz"
    expected_path.write_bytes(b"PK\x03\x04")  # minimal cbz placeholder

    archive_path, archive = loader.resolve_archive_for_comic(fanta_info, _make_page_map())
    assert archive_path == expected_path
    assert archive is None


def test_resolve_archive_for_comic_returns_fanta_volume_when_not_prebuilt(
    loader: ComicBookLoader,
    mock_reader_settings: MagicMock,
) -> None:
    """Non-prebuilt branch: returns the fanta volume archive without overrides."""
    mock_reader_settings.use_prebuilt_archives = False
    fake_archive = MagicMock()
    fake_archive.is_missing = False
    fake_archive.has_overrides.return_value = False
    fake_archive.archive_filename = "/fake/path/07.cbz"

    fanta_volume_archives = MagicMock()
    fanta_volume_archives.get_fantagraphics_archive.return_value = fake_archive
    loader._fanta_volume_archives = fanta_volume_archives

    fanta_info = _make_fanta_info(volume="FANTA_07")

    archive_path, returned = loader.resolve_archive_for_comic(fanta_info, _make_page_map())
    fanta_volume_archives.get_fantagraphics_archive.assert_called_once_with(7)
    assert archive_path == "/fake/path/07.cbz"
    assert returned is fake_archive


def test_resolve_archive_for_comic_raises_when_missing_volume_page_needs_archive(
    loader: ComicBookLoader,
    mock_reader_settings: MagicMock,
) -> None:
    """A missing volume raises MissingVolumeError when a page needs the real archive."""
    from barks_fantagraphics.barks_titles import Titles  # noqa: PLC0415
    from barks_reader.core.fantagraphics_volumes import MissingVolumeError  # noqa: PLC0415

    mock_reader_settings.use_prebuilt_archives = False
    fake_archive = MagicMock()
    fake_archive.is_missing = True
    fake_archive.needs_real_archive_for.return_value = True  # page not bundled

    fanta_volume_archives = MagicMock()
    fanta_volume_archives.get_fantagraphics_archive.return_value = fake_archive
    loader._fanta_volume_archives = fanta_volume_archives

    fanta_info = _make_fanta_info(volume="FANTA_12")
    fanta_info.comic_book_info.title = Titles.LOST_IN_THE_ANDES

    with pytest.raises(MissingVolumeError):
        loader.resolve_archive_for_comic(fanta_info, _make_page_map())


def test_resolve_archive_for_comic_allows_missing_volume_when_all_pages_bundled(
    loader: ComicBookLoader,
    mock_reader_settings: MagicMock,
) -> None:
    """A missing volume is readable when every page is bundled (extra/override/title)."""
    mock_reader_settings.use_prebuilt_archives = False
    fake_archive = MagicMock()
    fake_archive.is_missing = True
    fake_archive.needs_real_archive_for.return_value = False  # every page bundled
    fake_archive.has_overrides.return_value = False
    fake_archive.archive_filename = "/fake/path/12-MISSING.cbz"

    fanta_volume_archives = MagicMock()
    fanta_volume_archives.get_fantagraphics_archive.return_value = fake_archive
    loader._fanta_volume_archives = fanta_volume_archives

    fanta_info = _make_fanta_info(volume="FANTA_12")

    archive_path, returned = loader.resolve_archive_for_comic(fanta_info, _make_page_map())
    assert archive_path == "/fake/path/12-MISSING.cbz"
    assert returned is fake_archive


def test_get_prebuilt_comic_path_raises_when_file_missing(
    loader: ComicBookLoader,
    mock_reader_settings: MagicMock,
    tmp_path: Path,
) -> None:
    """No file on disk → FileNotFoundError."""
    mock_reader_settings.prebuilt_comics_dir = str(tmp_path / "nonexistent")
    fanta_info = _make_fanta_info()

    with pytest.raises(FileNotFoundError, match="Could not find comic file"):
        loader._get_prebuilt_comic_path(fanta_info)


def test_get_double_page_image_ready_for_reading_composes_two_pages(
    loader: ComicBookLoader,
) -> None:
    """Compose two real PNG streams into a wider landscape PNG."""
    from PIL import Image  # noqa: PLC0415

    left_buf = io.BytesIO()
    Image.new("RGB", (50, 80), (255, 0, 0)).save(left_buf, format="PNG")
    right_buf = io.BytesIO()
    Image.new("RGB", (50, 80), (0, 255, 0)).save(right_buf, format="PNG")

    # Stub the loader's image cache directly.
    loader._images = [(left_buf, ".png"), (right_buf, ".png")]

    stream, ext = loader.get_double_page_image_ready_for_reading(0, 1)

    assert ext == "png"  # PNG_EXT_FOR_KIVY (no leading dot)
    data = stream.read()
    assert data.startswith(b"\x89PNG\r\n")

    # The composited image must be wider than either source.
    out_image = Image.open(io.BytesIO(data))
    assert out_image.width == 100  # noqa: PLR2004
    assert out_image.height == 80  # noqa: PLR2004


# ---------------------------------------------------------------------------
# _page_needs_real_archive - the missing-volume readability gate
# ---------------------------------------------------------------------------


def _page(filename: str, page_type: PageType = PageType.BODY) -> MagicMock:
    page_info = MagicMock()
    page_info.srce_page.page_filename = filename
    page_info.srce_page.page_type = page_type
    page_info.page_type = page_type
    return page_info


class TestPageNeedsRealArchive:
    """Decides whether a comic is still readable with its volume archive absent."""

    def test_a_title_page_is_bundled(self) -> None:
        archive = MagicMock()
        archive.needs_real_archive_for.return_value = True

        assert (
            loader_module._page_needs_real_archive(_page("empty_page.jpg", PageType.TITLE), archive)
            is False
        )
        archive.needs_real_archive_for.assert_not_called()

    def test_a_blank_page_is_bundled(self) -> None:
        """Same placeholder filename, any page type other than TITLE."""
        archive = MagicMock()
        archive.needs_real_archive_for.return_value = True

        assert (
            loader_module._page_needs_real_archive(_page("empty_page.jpg", PageType.BODY), archive)
            is False
        )
        archive.needs_real_archive_for.assert_not_called()

    def test_a_real_page_is_looked_up_by_its_page_number(self) -> None:
        """The archive's page maps are keyed by the filename stem, not the filename."""
        archive = MagicMock()
        archive.needs_real_archive_for.return_value = True

        result = loader_module._page_needs_real_archive(_page("258.jpg"), archive)

        archive.needs_real_archive_for.assert_called_once_with("258")
        assert result is True

    def test_a_bundled_override_page_does_not_need_the_archive(self) -> None:
        archive = MagicMock()
        archive.needs_real_archive_for.return_value = False

        assert loader_module._page_needs_real_archive(_page("258.jpg"), archive) is False


class TestOverrideArchiveOpening:
    def test_the_override_zip_is_opened_for_reading(
        self, loader: ComicBookLoader, mock_reader_settings: MagicMock, tmp_path: Path
    ) -> None:
        """A volume with overrides gets its bundled zip opened and attached."""
        mock_reader_settings.use_prebuilt_archives = False
        override_zip = tmp_path / "07-overrides.zip"
        with zipfile.ZipFile(override_zip, "w") as zf:
            zf.writestr("258.png", b"x")

        fake_archive = MagicMock()
        fake_archive.is_missing = False
        fake_archive.has_overrides.return_value = True
        fake_archive.override_archive_filename = override_zip
        fake_archive.archive_filename = tmp_path / "07.cbz"

        archives = MagicMock()
        archives.get_fantagraphics_archive.return_value = fake_archive
        loader._fanta_volume_archives = archives

        loader.resolve_archive_for_comic(_make_fanta_info(volume="FANTA_07"), _make_page_map())

        opened = fake_archive.override_archive
        assert isinstance(opened, zipfile.ZipFile)
        assert opened.filename == str(override_zip)
        assert opened.namelist() == ["258.png"]
        opened.close()

    def test_no_override_zip_is_opened_when_the_volume_has_none(
        self, loader: ComicBookLoader, mock_reader_settings: MagicMock, tmp_path: Path
    ) -> None:
        mock_reader_settings.use_prebuilt_archives = False
        fake_archive = MagicMock()
        fake_archive.is_missing = False
        fake_archive.has_overrides.return_value = False
        fake_archive.archive_filename = tmp_path / "07.cbz"
        fake_archive.override_archive = None

        archives = MagicMock()
        archives.get_fantagraphics_archive.return_value = fake_archive
        loader._fanta_volume_archives = archives

        loader.resolve_archive_for_comic(_make_fanta_info(volume="FANTA_07"), _make_page_map())

        assert fake_archive.override_archive is None


class TestLoaderInitialState:
    def test_a_fresh_loader_holds_no_comic(self, loader: ComicBookLoader) -> None:
        """Nothing is loaded until `set_comic`, and loading is *not* pre-stopped."""
        assert loader._stop is False
        assert loader._current_comic_desc == ""
        assert loader._image_source is None
        assert loader._images == []
        assert loader._image_load_order == []
        assert loader._index_to_key == {}
        assert loader._page_map == OrderedDict()
        assert loader._priority_keys.empty()
        assert loader._fanta_volume_archives is None

    def test_the_window_size_is_kept_for_page_resizing(self, loader: ComicBookLoader) -> None:
        assert loader._max_window_width == 800  # noqa: PLR2004
        assert loader._max_window_height == 600  # noqa: PLR2004

    def test_closing_without_a_comic_is_a_no_op(self, loader: ComicBookLoader) -> None:
        loader.close_comic()

        assert loader._current_comic_desc == ""
        assert loader._stop is False


class TestResidentMemoryReading:
    def test_rss_is_reported_in_mebibytes(self) -> None:
        process = MagicMock()
        process.memory_info.return_value.rss = 150 * 1024 * 1024

        with patch.object(loader_module.psutil, "Process", return_value=process):
            assert ComicBookLoader._process_rss_mib() == 150.0  # noqa: PLR2004


class TestCachedImageAccess:
    def test_the_stream_is_rewound_before_it_is_handed_out(self, loader: ComicBookLoader) -> None:
        """A page can be displayed twice; the second read must not start mid-stream."""
        stream = io.BytesIO(b"png-bytes")
        stream.seek(5)
        loader._images = [(stream, ".png")]

        returned, ext = loader.get_image_ready_for_reading(0)

        assert returned.tell() == 0
        assert returned.read() == b"png-bytes"
        assert ext == ".png"

    def test_an_out_of_range_page_index_is_rejected(self, loader: ComicBookLoader) -> None:
        """The bound is exclusive: index == len is one past the last page."""
        loader._images = [(io.BytesIO(b"x"), ".png")]

        with pytest.raises(AssertionError):
            loader.get_image_ready_for_reading(1)


# ---------------------------------------------------------------------------
# Retained-image memory arithmetic
# ---------------------------------------------------------------------------


class TestRetainedImageStats:
    """The unit conversions behind the `[mem]` log line.

    Split out of the logging so the numbers are assertable without pinning the
    wording. A wrong divisor here makes the memory report quietly lie.
    """

    @staticmethod
    def _with_page_sizes(loader: ComicBookLoader, *sizes: int) -> None:
        loader._images = [(io.BytesIO(b"\0" * size), ".png") for size in sizes]

    def test_totals_are_mebibytes_and_averages_are_kibibytes(self, loader: ComicBookLoader) -> None:
        # 1 MiB and 3 MiB: total 4 MiB, average 2 MiB (2048 KiB), max 3 MiB (3072 KiB).
        self._with_page_sizes(loader, 1024 * 1024, 3 * 1024 * 1024)

        with patch.object(ComicBookLoader, "_process_rss_mib", return_value=500.0):
            stats = loader._retained_image_stats(rss_before_mib=200.0)

        assert stats == loader_module.RetainedImageStats(
            loaded=2,
            total_mib=4.0,
            avg_kib=2048.0,
            max_kib=3072.0,
            rss_now_mib=500.0,
            rss_growth_mib=300.0,
        )

    def test_unloaded_pages_are_excluded_from_every_figure(self, loader: ComicBookLoader) -> None:
        """A stopped load leaves `None` holes; they are not zero-size pages."""
        self._with_page_sizes(loader, 2 * 1024 * 1024)
        loader._images.append(None)

        with patch.object(ComicBookLoader, "_process_rss_mib", return_value=10.0):
            stats = loader._retained_image_stats(rss_before_mib=10.0)

        assert stats.loaded == 1
        assert stats.total_mib == 2.0  # noqa: PLR2004
        assert stats.avg_kib == 2048.0  # noqa: PLR2004

    def test_an_empty_cache_reports_zeroes_rather_than_dividing_by_zero(
        self, loader: ComicBookLoader
    ) -> None:
        loader._images = []

        with patch.object(ComicBookLoader, "_process_rss_mib", return_value=64.0):
            stats = loader._retained_image_stats(rss_before_mib=64.0)

        assert stats.loaded == 0
        assert stats.total_mib == 0.0
        assert stats.avg_kib == 0.0
        assert stats.max_kib == 0.0
        assert stats.rss_growth_mib == 0.0

    def test_rss_growth_is_a_difference_not_a_sum(self, loader: ComicBookLoader) -> None:
        """Growth must go negative when the process shrank during the load."""
        loader._images = []

        with patch.object(ComicBookLoader, "_process_rss_mib", return_value=80.0):
            stats = loader._retained_image_stats(rss_before_mib=100.0)

        assert stats.rss_growth_mib == -20.0  # noqa: PLR2004

    def test_the_log_line_reports_the_measured_stats(self, loader: ComicBookLoader) -> None:
        """`_log_retained_image_memory` is now only formatting."""
        sentinel = loader_module.RetainedImageStats(
            loaded=3, total_mib=1.0, avg_kib=2.0, max_kib=3.0, rss_now_mib=4.0, rss_growth_mib=5.0
        )

        with patch.object(
            ComicBookLoader, "_retained_image_stats", return_value=sentinel
        ) as measure:
            loader._log_retained_image_memory(rss_before_mib=42.0)

        measure.assert_called_once_with(42.0)


# ---------------------------------------------------------------------------
# The load-error handler matrix
# ---------------------------------------------------------------------------


def _run_load(
    loader: ComicBookLoader,
    page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
    source: Any = None,  # noqa: ANN401
) -> None:
    """Drive one full `set_comic` load to completion."""
    page_map, load_order = page_map_and_order
    loader.set_comic(source or FakePageImageSource(), load_order, page_map, archive_desc="t.cbz")
    assert loader._thread is not None
    loader._thread.join(timeout=3.0)
    assert not loader._thread.is_alive()


# `on_load_error`'s only argument is a severity flag; name it at the call sites.
GENUINE_FAILURE = False
WARNING_ONLY = True


class ExplodingOpenSource(FakePageImageSource):
    """A source whose `open()` fails, as a missing or truncated archive would."""

    def __init__(self, error: Exception) -> None:
        super().__init__()
        self._error = error

    def open(self) -> None:
        raise self._error


class TestLoadErrorReporting:
    """Every failure path must reach `on_load_error` with the right severity.

    The second argument is *warning-only*: True means "expected during a stop",
    which the UI reports more quietly than a genuine failure.
    """

    @pytest.mark.parametrize(
        "error",
        [FileNotFoundError("no such archive"), zipfile.BadZipFile("truncated")],
        ids=["missing-archive", "corrupt-archive"],
    )
    def test_an_archive_that_cannot_be_opened_is_reported(
        self,
        loader: ComicBookLoader,
        page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
        mock_callbacks: dict[str, MagicMock],
        error: Exception,
    ) -> None:
        """Regression: opening happens inside the try, so the thread cannot die silently.

        `image_source.open()` is where the archive is first touched. It used to sit
        outside the guarded block, so a missing or truncated volume raised straight
        out of the loader thread: no callback, no dialog, just a comic stuck loading.
        """
        _run_load(loader, page_map_and_order, ExplodingOpenSource(error))

        mock_callbacks["on_load_error"].assert_called_once_with(GENUINE_FAILURE)
        mock_callbacks["on_all_images_loaded"].assert_not_called()

    @pytest.mark.parametrize(
        "error",
        [
            FileNotFoundError("gone"),
            zipfile.BadZipFile("bad"),
            KeyError("p1"),
            IndexError("out of range"),
        ],
        ids=["file-not-found", "bad-zip", "key-error", "index-error"],
    )
    def test_each_handled_error_reports_a_genuine_failure(
        self,
        loader: ComicBookLoader,
        page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
        mock_callbacks: dict[str, MagicMock],
        error: Exception,
    ) -> None:
        with patch.object(ComicBookLoader, "_load_pages", side_effect=error):
            _run_load(loader, page_map_and_order)

        mock_callbacks["on_load_error"].assert_called_once_with(GENUINE_FAILURE)
        mock_callbacks["on_all_images_loaded"].assert_not_called()

    def test_an_index_error_during_a_stop_is_only_a_warning(
        self,
        loader: ComicBookLoader,
        page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
        mock_callbacks: dict[str, MagicMock],
    ) -> None:
        """Tearing down mid-load races the indexing; that is expected, not a failure."""

        def raise_after_stop() -> int:
            loader._stop = True
            msg = "list index out of range"
            raise IndexError(msg)

        with patch.object(ComicBookLoader, "_load_pages", side_effect=raise_after_stop):
            _run_load(loader, page_map_and_order)

        mock_callbacks["on_load_error"].assert_called_once_with(WARNING_ONLY)

    def test_an_unexpected_error_is_reported_as_a_failure(
        self,
        loader: ComicBookLoader,
        page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
        mock_callbacks: dict[str, MagicMock],
    ) -> None:
        """The catch-all branch reads the traceback; it must not itself blow up."""
        with patch.object(ComicBookLoader, "_load_pages", side_effect=RuntimeError("boom")):
            _run_load(loader, page_map_and_order)

        mock_callbacks["on_load_error"].assert_called_once_with(GENUINE_FAILURE)

    def test_a_successful_load_reports_no_error(
        self,
        loader: ComicBookLoader,
        page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
        mock_callbacks: dict[str, MagicMock],
    ) -> None:
        _run_load(loader, page_map_and_order)

        mock_callbacks["on_load_error"].assert_not_called()
        mock_callbacks["on_all_images_loaded"].assert_called_once()

    def test_a_stopped_load_reports_neither_completion_nor_error(
        self,
        loader: ComicBookLoader,
        page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
        mock_callbacks: dict[str, MagicMock],
    ) -> None:
        """Stopping is not a failure — and the all-loaded callback must not fire."""

        def stop_then_report_partial() -> int:
            loader._stop = True
            return 1

        with patch.object(ComicBookLoader, "_load_pages", side_effect=stop_then_report_partial):
            _run_load(loader, page_map_and_order)

        mock_callbacks["on_all_images_loaded"].assert_not_called()
        mock_callbacks["on_load_error"].assert_not_called()

    def test_reporting_an_error_closes_the_comic(
        self,
        loader: ComicBookLoader,
        page_map_and_order: tuple[OrderedDict[str, Any], list[str]],
        mock_callbacks: dict[str, MagicMock],
    ) -> None:
        source = FakePageImageSource()

        with patch.object(ComicBookLoader, "_load_pages", side_effect=RuntimeError("boom")):
            _run_load(loader, page_map_and_order, source)

        assert source.closed
        assert loader._stop is True
        assert loader._current_comic_desc == ""
        mock_callbacks["on_load_error"].assert_called_once_with(GENUINE_FAILURE)


# ---------------------------------------------------------------------------
# The prefetch window and its submission bookkeeping
# ---------------------------------------------------------------------------


class TestPrefetchWindow:
    """`_load_pages` keeps a sliding window of in-flight page loads."""

    def test_the_tuning_is_asked_for_this_load_s_workers_and_page_count(
        self, loader: ComicBookLoader
    ) -> None:
        page_map, load_order = _make_indexed_page_map(4)

        with patch.object(loader_module, get_prefetch_tuning.__name__) as get_tuning:
            tuning = get_tuning.return_value
            tuning.get_initial_dynamic_window.return_value = 2
            tuning.get_new_dynamic_window.return_value = (50.0, 2)
            tuning.get_traced_peak_mib.return_value = 1.0

            loader.set_comic(FakePageImageSource(), load_order, page_map, archive_desc="t.cbz")
            assert loader._thread is not None
            loader._thread.join(timeout=3.0)

        # One worker (autotuned to 1 in the fixture), four pages.
        get_tuning.assert_called_once_with(1, 4)
        # The window is re-read each round, seeded with the window in force.
        assert tuning.get_new_dynamic_window.call_args_list[0].args == (2,)

    def test_the_worker_count_never_exceeds_the_page_count(self, loader: ComicBookLoader) -> None:
        """A two-page comic must not spin up the full autotuned pool."""
        loader._max_worker_count = 8

        assert loader.get_worker_count_for_pages(2) == 2  # noqa: PLR2004
        assert loader.get_worker_count_for_pages(20) == 8  # noqa: PLR2004

    def test_every_page_is_submitted_exactly_once(self, loader: ComicBookLoader) -> None:
        """The `submitted` set is what stops a refill re-fetching a queued page."""
        page_map, load_order = _make_indexed_page_map(6)
        source = FakePageImageSource()

        loader.set_comic(source, load_order, page_map, archive_desc="t.cbz")
        assert loader._thread is not None
        loader._thread.join(timeout=3.0)

        assert source.load_count == 6  # noqa: PLR2004
        assert all(entry is not None for entry in loader._images)

    def test_the_window_caps_how_many_loads_are_in_flight(self, loader: ComicBookLoader) -> None:
        """With a window of 2, a third page cannot start until one completes."""
        page_map, load_order = _make_indexed_page_map(5)
        inflight = 0
        peak = 0
        lock = threading.Lock()
        release = threading.Event()

        class CountingSource(FakePageImageSource):
            def load_page_image(self, page_info: PageInfo) -> tuple[io.BytesIO, str]:  # noqa: ARG002
                nonlocal inflight, peak
                with lock:
                    inflight += 1
                    peak = max(peak, inflight)
                release.wait(timeout=0.05)
                with lock:
                    inflight -= 1
                return io.BytesIO(b"png"), ".png"

        # Two workers so the window, not the pool, is the binding constraint.
        loader._max_worker_count = 2
        loader.set_comic(CountingSource(), load_order, page_map, archive_desc="t.cbz")
        assert loader._thread is not None
        loader._thread.join(timeout=5.0)

        assert peak <= 2  # noqa: PLR2004
        assert all(entry is not None for entry in loader._images)

    def test_the_first_page_callback_fires_once_for_the_first_page_only(
        self, loader: ComicBookLoader, mock_callbacks: dict[str, MagicMock]
    ) -> None:
        """Three pages: a mis-aimed comparison would fire it for the other two."""
        page_map, load_order = _make_indexed_page_map(3)

        loader.set_comic(FakePageImageSource(), load_order, page_map, archive_desc="t.cbz")
        assert loader._thread is not None
        loader._thread.join(timeout=3.0)

        mock_callbacks["on_first_image_loaded"].assert_called_once()

    def test_a_priority_request_for_a_loaded_page_is_dropped_not_refetched(
        self, loader: ComicBookLoader
    ) -> None:
        """A stale queue entry must be skipped without re-submitting the page."""
        page_map, load_order = _make_indexed_page_map(4)
        started = threading.Event()
        release = threading.Event()
        source = OrderRecordingSource(block_index=0, started=started, release=release)

        loader.set_comic(source, load_order, page_map, archive_desc="t.cbz")
        assert started.wait(2.0)
        # Queue the page that is *currently* being loaded, plus a later one.
        loader.prioritize_page(0)
        loader.prioritize_page(3)
        release.set()

        assert loader._thread is not None
        loader._thread.join(timeout=3.0)

        # Page 0 is not fetched twice, and every page still arrives exactly once.
        assert sorted(source.load_order) == [0, 1, 2, 3]

    def test_a_page_pulled_forward_is_skipped_when_the_normal_order_reaches_it(
        self, loader: ComicBookLoader
    ) -> None:
        """Skipping a already-submitted key must not abandon the rest of the order.

        Prioritizing a *middle* page is what exposes this: the normal load order
        later walks onto that page, has to step over it, and must keep going to the
        pages behind it. Stopping there instead would strand them unloaded.
        """
        page_map, load_order = _make_indexed_page_map(6)
        started = threading.Event()
        release = threading.Event()
        source = OrderRecordingSource(block_index=0, started=started, release=release)

        loader.set_comic(source, load_order, page_map, archive_desc="t.cbz")
        assert started.wait(2.0)
        loader.prioritize_page(2)
        release.set()

        assert loader._thread is not None
        loader._thread.join(timeout=3.0)

        assert sorted(source.load_order) == [0, 1, 2, 3, 4, 5]
        assert all(entry is not None for entry in loader._images)

    def test_a_stale_priority_entry_does_not_discard_the_ones_behind_it(
        self, loader: ComicBookLoader
    ) -> None:
        """The drain loop skips spent entries; it must not stop at the first one.

        The user can navigate back onto a page that is already being fetched. That
        request is dropped, but any genuinely new request queued behind it still has
        to be honoured.
        """
        page_map, load_order = _make_indexed_page_map(6)
        started = threading.Event()
        release = threading.Event()
        source = OrderRecordingSource(block_index=0, started=started, release=release)

        loader.set_comic(source, load_order, page_map, archive_desc="t.cbz")
        assert started.wait(2.0)
        loader.prioritize_page(0)  # already in flight - a spent entry
        loader.prioritize_page(5)  # queued behind it, and genuinely new
        release.set()

        assert loader._thread is not None
        loader._thread.join(timeout=3.0)

        order = source.load_order
        assert sorted(order) == [0, 1, 2, 3, 4, 5]
        # The live request behind the spent one still jumped the queue.
        assert order.index(5) < order.index(4)

    def test_stopping_mid_load_leaves_the_remaining_pages_unloaded(
        self, loader: ComicBookLoader, mock_callbacks: dict[str, MagicMock]
    ) -> None:
        """The stop check runs before each delivery, so later pages never land."""
        page_map, load_order = _make_indexed_page_map(6)
        first_done = threading.Event()

        class StopAfterFirstSource(FakePageImageSource):
            def load_page_image(self, page_info: PageInfo) -> tuple[io.BytesIO, str]:
                result = super().load_page_image(page_info)
                if page_info.page_index == 0:
                    first_done.set()
                else:
                    time.sleep(0.05)
                return result

        loader.set_comic(StopAfterFirstSource(), load_order, page_map, archive_desc="t.cbz")
        assert first_done.wait(2.0)
        loader.stop_now()

        assert any(entry is None for entry in loader._images)
        mock_callbacks["on_all_images_loaded"].assert_not_called()


# ---------------------------------------------------------------------------
# Lifecycle: thread creation, stop, close
# ---------------------------------------------------------------------------


class TestLoaderLifecycle:
    def test_the_loading_thread_is_a_daemon(
        self, loader: ComicBookLoader, page_map_and_order: tuple[OrderedDict[str, Any], list[str]]
    ) -> None:
        """A non-daemon loader thread would keep the app alive after the window closes."""
        page_map, load_order = page_map_and_order

        loader.set_comic(FakePageImageSource(), load_order, page_map, archive_desc="t.cbz")
        thread = loader._thread
        assert thread is not None

        assert thread.daemon is True
        thread.join(timeout=3.0)

    def test_a_second_load_does_not_start_a_rival_thread(self, loader: ComicBookLoader) -> None:
        """`_start_loading_thread` is a no-op while a load is already running."""
        page_map, load_order = _make_indexed_page_map(3)
        started = threading.Event()
        release = threading.Event()
        source = OrderRecordingSource(block_index=0, started=started, release=release)

        loader.set_comic(source, load_order, page_map, archive_desc="t.cbz")
        assert started.wait(2.0)
        running = loader._thread

        loader._start_loading_thread()

        assert loader._thread is running
        release.set()
        assert running is not None
        running.join(timeout=3.0)

    def test_stop_now_waits_a_bounded_time_for_the_thread(self, loader: ComicBookLoader) -> None:
        """An unbounded join would hang the UI thread on a wedged loader."""
        thread = MagicMock()
        # Alive for the guard, dead once joined - so no "did not terminate" error.
        thread.is_alive.side_effect = [True, False]
        loader._thread = thread

        loader.stop_now()

        thread.join.assert_called_once_with(timeout=2.0)

    def test_stop_now_clears_the_thread_and_restores_the_cursor(
        self, loader: ComicBookLoader, recording_cursor: RecordingCursor
    ) -> None:
        thread = MagicMock()
        thread.is_alive.return_value = False
        loader._thread = thread

        loader.stop_now()

        assert loader._thread is None
        assert recording_cursor.states[-1] == "normal"

    def test_stop_now_is_idempotent(self, loader: ComicBookLoader) -> None:
        """Already stopped means the join is not attempted a second time."""
        loader.stop_now()
        thread = MagicMock()
        thread.is_alive.return_value = True
        loader._thread = thread

        loader.stop_now()

        thread.join.assert_not_called()

    def test_set_comic_defaults_to_an_empty_archive_description(
        self, loader: ComicBookLoader, page_map_and_order: tuple[OrderedDict[str, Any], list[str]]
    ) -> None:
        """An empty description is what makes `close_comic` a no-op."""
        page_map, load_order = page_map_and_order

        loader.set_comic(FakePageImageSource(), load_order, page_map)
        assert loader._thread is not None
        loader._thread.join(timeout=3.0)

        assert loader._current_comic_desc == ""

    def test_set_comic_clears_a_previous_stop(
        self, loader: ComicBookLoader, page_map_and_order: tuple[OrderedDict[str, Any], list[str]]
    ) -> None:
        """Reusing the loader after a stop must actually re-enable loading."""
        page_map, load_order = page_map_and_order
        loader.stop_now()
        assert loader._stop is True

        loader.set_comic(FakePageImageSource(), load_order, page_map, archive_desc="second.cbz")
        assert loader._thread is not None
        loader._thread.join(timeout=3.0)

        assert loader._stop is False
        assert all(entry is not None for entry in loader._images)

    def test_close_comic_resets_the_description_to_empty(
        self, loader: ComicBookLoader, page_map_and_order: tuple[OrderedDict[str, Any], list[str]]
    ) -> None:
        """A second close must short-circuit rather than re-run the teardown."""
        page_map, load_order = page_map_and_order
        source = FakePageImageSource()
        loader.set_comic(source, load_order, page_map, archive_desc="t.cbz")
        assert loader._thread is not None
        loader._thread.join(timeout=3.0)

        loader.close_comic()

        assert loader._current_comic_desc == ""
        assert loader._image_source is None
        assert loader._images == []
        assert loader._image_loaded_events == []

    def test_close_comic_tolerates_a_source_with_no_close_method(
        self, loader: ComicBookLoader, page_map_and_order: tuple[OrderedDict[str, Any], list[str]]
    ) -> None:
        """The `hasattr` guard is the reason a minimal source is allowed."""
        page_map, load_order = page_map_and_order

        class NoCloseSource:
            def load_page_image(self, page_info: PageInfo) -> tuple[io.BytesIO, str]:  # noqa: ARG002
                return io.BytesIO(b"png"), ".png"

            @staticmethod
            def get_image_info_str(page_info: PageInfo) -> str:  # noqa: ARG004
                return "x"

        loader.set_comic(NoCloseSource(), load_order, page_map, archive_desc="t.cbz")
        assert loader._thread is not None
        loader._thread.join(timeout=3.0)

        loader.close_comic()  # must not raise

        assert loader._image_source is None


# ---------------------------------------------------------------------------
# init_data wiring
# ---------------------------------------------------------------------------


class TestInitDataWiring:
    def test_the_volume_archives_are_built_from_settings_and_bundled_overrides(
        self,
        loader: ComicBookLoader,
        mock_reader_settings: MagicMock,
        mock_sys_file_paths: MagicMock,
    ) -> None:
        """Three positional arguments that are easy to transpose and never asserted."""
        mock_reader_settings.use_prebuilt_archives = False

        with patch.object(loader_module, FantagraphicsVolumeArchives.__name__) as archives:
            loader.init_data()

        archives.assert_called_once_with(
            mock_reader_settings.fantagraphics_volumes_dir,
            mock_sys_file_paths.get_barks_reader_fantagraphics_overrides_root_dir.return_value,
            loader_module.ALL_FANTA_VOLUMES,
        )
        assert loader._fanta_volume_archives is archives.return_value

    def test_every_fantagraphics_volume_is_requested(self) -> None:
        """The reader loads the whole run; a short list would hide later volumes."""
        from barks_fantagraphics.fanta_comics_info import (  # noqa: PLC0415
            FIRST_VOLUME_NUMBER,
            LAST_VOLUME_NUMBER,
        )

        assert loader_module.ALL_FANTA_VOLUMES[0] == FIRST_VOLUME_NUMBER
        assert loader_module.ALL_FANTA_VOLUMES[-1] == LAST_VOLUME_NUMBER
        assert len(loader_module.ALL_FANTA_VOLUMES) == (
            LAST_VOLUME_NUMBER - FIRST_VOLUME_NUMBER + 1
        )


class TestMissingVolumeErrorContents:
    def test_the_error_names_the_volume_and_the_title(
        self, loader: ComicBookLoader, mock_reader_settings: MagicMock
    ) -> None:
        """The dialog is built from these two fields, so they must be the real ones."""
        from barks_fantagraphics.barks_titles import Titles  # noqa: PLC0415
        from barks_fantagraphics.fanta_comics_info import (  # noqa: PLC0415
            get_fanta_volume_from_str,
        )
        from barks_reader.core.fantagraphics_volumes import MissingVolumeError  # noqa: PLC0415

        mock_reader_settings.use_prebuilt_archives = False
        fake_archive = MagicMock()
        fake_archive.is_missing = True
        fake_archive.needs_real_archive_for.return_value = True

        archives = MagicMock()
        archives.get_fantagraphics_archive.return_value = fake_archive
        loader._fanta_volume_archives = archives

        fanta_info = _make_fanta_info(volume="FANTA_12")
        fanta_info.comic_book_info.title = Titles.LOST_IN_THE_ANDES

        with pytest.raises(MissingVolumeError) as excinfo:
            loader.resolve_archive_for_comic(fanta_info, _make_page_map())

        assert excinfo.value.missing_vol == get_fanta_volume_from_str("FANTA_12")
        assert excinfo.value.title == Titles.LOST_IN_THE_ANDES


class TestDoublePageCompositing:
    def test_the_composite_is_encoded_without_compression(self, loader: ComicBookLoader) -> None:
        """Double-page spreads are re-encoded per turn; compression would cost latency."""
        from PIL import Image  # noqa: PLC0415

        buffers = []
        for _ in range(2):
            buf = io.BytesIO()
            Image.new("RGB", (10, 10), (1, 2, 3)).save(buf, format="PNG")
            buffers.append(buf)
        loader._images = [(buffers[0], ".png"), (buffers[1], ".png")]

        with patch.object(
            loader_module,
            "get_pil_image_as_png_bytes",
            return_value=io.BytesIO(b"\x89PNG\r\n composited"),
        ) as encode:
            loader.get_double_page_image_ready_for_reading(0, 1)

        assert encode.call_args.kwargs == {"compress_level": 0}


class TestBlankPageDetectionUsesPageType:
    def test_the_page_type_decides_whether_an_empty_page_name_means_blank(self) -> None:
        """`is_blank_page` is *name* AND *not TITLE*; dropping the type flips the answer.

        A page carrying the blank-page filename but a TITLE page type is not a blank
        page, so it still has to be resolved against the archive. Without the type,
        the name alone would wrongly mark it bundled and skip the lookup entirely.
        """
        archive = MagicMock()
        archive.needs_real_archive_for.return_value = True

        # Title page *type*, but srce_page's own type is BODY, so `is_title_page` is
        # False and only the `is_blank_page` type check is left to decide.
        page = _page("empty_page.jpg", PageType.TITLE)
        page.srce_page.page_type = PageType.BODY

        assert loader_module._page_needs_real_archive(page, archive) is True
        archive.needs_real_archive_for.assert_called_once_with("empty_page")
