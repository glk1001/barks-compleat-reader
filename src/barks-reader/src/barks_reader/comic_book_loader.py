# ruff: noqa: ERA001

from __future__ import annotations

import io
import os
import sys
import threading
import time
import traceback
import zipfile
from collections import OrderedDict
from concurrent.futures import FIRST_COMPLETED, CancelledError, ThreadPoolExecutor, wait
from pathlib import Path
import tracemalloc
from typing import TYPE_CHECKING
from zipfile import ZipFile

from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.comics_utils import get_abbrev_path, get_dest_comic_zip_file_stem
from barks_fantagraphics.fanta_comics_info import (
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
    FantaComicBookInfo,
)
from comic_utils.comic_consts import CBZ_FILE_EXT, ZIP_FILE_EXT
from comic_utils.pil_image_utils import (
    get_pil_image_as_png_bytes,
    load_pil_image_from_bytes,
    load_pil_image_from_zip,
)
from comic_utils.timing import Timing
from kivy.clock import Clock
from loguru import logger
from PIL import Image, ImageOps
from PIL import Image as PilImage

from barks_reader.fantagraphics_volumes import FantagraphicsArchive, FantagraphicsVolumeArchives

# noinspection PyUnresolvedReferences
from barks_reader.open_zip_archive import get_opened_zip_file  # ty: ignore[unresolved-import]
from barks_reader.reader_ui_classes import set_kivy_busy_cursor, set_kivy_normal_cursor
from barks_reader.reader_utils import PNG_EXT_FOR_KIVY, is_blank_page, is_title_page

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_build_comic_images.build_comic_images import ComicBookImageBuilder

    from barks_reader.comic_book_page_info import PageInfo
    from barks_reader.reader_settings import ReaderSettings

ALL_FANTA_VOLUMES = list(range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1))
# ALL_FANTA_VOLUMES = [i for i in range(5, 7 + 1)]

# How many pages may be in-flight (being decoded) at once.
# This is a *concurrency / memory* control, not a limit on total pages loaded.
# Dynamic window constraints
PREFETCH_MIN = 2                # never go below 2
PREFETCH_MAX_FACTOR = 1.0       # max window = worker_count * factor

# Memory thresholds (MiB)
MEMORY_LOW_WATER = 250          # below = safe to grow
MEMORY_HIGH_WATER = 450         # above = shrink aggressively


class ComicBookLoader:
    def __init__(
        self,
        reader_settings: ReaderSettings,
        on_first_image_loaded: Callable[[], None],
        on_all_images_loaded: Callable[[], None],
        on_load_error: Callable[[bool], None],
        max_window_width: int,
        max_window_height: int,
    ) -> None:
        self._reader_settings = reader_settings
        self._use_fantagraphics_overrides = True
        self._sys_file_paths = self._reader_settings.sys_file_paths
        self._fanta_volume_archives: FantagraphicsVolumeArchives | None = None
        self._fanta_volume_archive: FantagraphicsArchive | None = None

        self._image_loaded_events: list[threading.Event] = []
        self._image_load_order: list[str] = []
        self._page_map: OrderedDict[str, PageInfo] = OrderedDict()
        self._images: list[None | tuple[io.BytesIO, str]] = []
        self._max_window_width = max_window_width
        self._max_window_height = max_window_height

        self._stop = False
        self._current_comic_path = ""
        self._comic_book_image_builder: ComicBookImageBuilder | None = None

        self._on_first_image_loaded: Callable[[], None] = on_first_image_loaded
        self._on_all_images_loaded: Callable[[], None] = on_all_images_loaded
        self._on_load_error = on_load_error

        with Path(self._sys_file_paths.get_empty_page_file()).open("rb") as file:
            self._empty_page_image = file.read()

        self._thread: threading.Thread | None = None
        self._max_worker_count = autotune_worker_count()
        logger.debug(f"Using {self._max_worker_count} as max worker threads (auto-tuned).")

    def init_data(self) -> None:
        if self._reader_settings.use_prebuilt_archives:
            logger.info("Using prebuilt archives. No extra data to initialize.")
            self._fanta_volume_archives = None
        else:
            timing = Timing()

            logger.info("Using Fantagraphics volume archives. Now loading volume info...")
            self._fanta_volume_archives = FantagraphicsVolumeArchives(
                self._reader_settings.fantagraphics_volumes_dir,
                self._sys_file_paths.get_barks_reader_fantagraphics_overrides_root_dir(),
                ALL_FANTA_VOLUMES,
            )
            self._fanta_volume_archives.load()

            logger.info(f"Finished loading all volumes in {timing.get_elapsed_time_with_unit()}.")

    def get_image_ready_for_reading(self, page_index: int) -> tuple[io.BytesIO, str]:
        assert self._images
        assert 0 <= page_index < len(self._images)

        image_stream, image_ext = self._images[page_index]
        assert image_stream

        image_stream.seek(0)  # Ensure stream is at the beginning for reading

        return image_stream, image_ext

    def get_image_info_str(self, page_str: str) -> str:
        page_info = self._page_map[page_str]
        image_path, is_from_archive = self._get_image_path(page_info)
        file_source = "from archive" if is_from_archive else "from override"

        return f'"{image_path!s}" ({file_source})'

    def wait_load_event(self, page_index: int, timeout: float) -> bool:
        if not self._images:
            return True
        assert 0 <= page_index < len(self._images)
        return self._image_loaded_events[page_index].wait(timeout)

    def set_comic(
        self,
        fanta_info: FantaComicBookInfo,
        use_fantagraphics_overrides: bool,
        comic_book_image_builder: ComicBookImageBuilder,
        image_load_order: list[str],
        page_map: OrderedDict[str, PageInfo],
    ) -> None:
        assert len(image_load_order) == len(page_map)

        # Stop any previous loading process before starting a new one.
        if self._thread and self._thread.is_alive():
            self.stop_now()

        if self._reader_settings.use_prebuilt_archives:
            self._fanta_volume_archive = None
        else:
            if not self._fanta_volume_archives:
                self.init_data()

            assert self._fanta_volume_archives
            self._fanta_volume_archive = self._fanta_volume_archives.get_fantagraphics_archive(
                int(fanta_info.fantagraphics_volume[-2:])
            )
            if self._fanta_volume_archive.has_overrides():
                assert self._fanta_volume_archive.override_archive_filename
                self._fanta_volume_archive.override_archive = get_opened_zip_file(
                    self._fanta_volume_archive.override_archive_filename
                )

        self._use_fantagraphics_overrides = use_fantagraphics_overrides
        self._current_comic_path = self._get_comic_path(fanta_info)
        self._comic_book_image_builder = comic_book_image_builder
        self._image_load_order = image_load_order
        self._page_map = page_map
        self._stop = False

        logger.info(f"Archive source: {self._get_archive_source()}.")

        self._init_load_events()
        self._start_loading_thread()  # Start the thread automatically

    def close_comic(self) -> None:
        if not self._current_comic_path:
            return

        logger.debug(f'Close the comic: "{self._current_comic_path}".')

        # Signal the thread to stop and wait for it to finish before clearing resources
        self.stop_now()

        if self._fanta_volume_archive:
            self._fanta_volume_archive.override_archive = None
        self._images.clear()
        self._image_loaded_events.clear()
        self._current_comic_path = ""

    def stop_now(self) -> None:
        """Signals the background thread to stop and waits for it to terminate."""
        if self._stop:  # Already stopping
            return

        if self._thread and self._thread.is_alive():
            logger.debug("Waiting for image loading thread to terminate...")
            self._thread.join(timeout=2.0)  # Wait for 2 seconds
            if self._thread.is_alive():
                logger.error("Image loading thread did not terminate in time.")

        self._thread = None
        self._stop = True

        set_kivy_normal_cursor()

    def _start_loading_thread(self) -> None:
        """Create and start the background thread for loading comic images."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Load is already in progress.")
            return

        logger.debug(f'Starting comic load in background thread for: "{self._current_comic_path}"')
        self._thread = threading.Thread(target=self._load_comic_in_thread, daemon=True)
        self._thread.start()

    def _get_archive_source(self) -> str:
        archive_type = "Prebuilt" if not self._fanta_volume_archive else "Fantagraphics volumes"
        return f'{archive_type} - "{get_abbrev_path(self._current_comic_path)}"'

    def _get_comic_path(self, fanta_info: FantaComicBookInfo) -> Path:
        if self._fanta_volume_archive:
            return self._fanta_volume_archive.archive_filename

        return self._get_prebuilt_comic_path(fanta_info)

    def _get_prebuilt_comic_path(self, fanta_info: FantaComicBookInfo) -> Path:
        comic_file_stem = get_dest_comic_zip_file_stem(
            fanta_info.comic_book_info.get_title_str(),
            fanta_info.fanta_chronological_number,
            fanta_info.get_short_issue_title(),
        )

        comic_path = Path(self._reader_settings.prebuilt_comics_dir) / (
            comic_file_stem + CBZ_FILE_EXT
        )
        if comic_path.suffix not in [CBZ_FILE_EXT, ZIP_FILE_EXT]:
            msg = f"Expected '{CBZ_FILE_EXT}' or '{ZIP_FILE_EXT}' file."
            raise ValueError(msg)
        if not comic_path.is_file():
            msg = f'Could not find comic file "{comic_path}".'
            raise FileNotFoundError(msg)

        return comic_path

    def _init_load_events(self) -> None:
        self._image_loaded_events.clear()
        for _ in range(len(self._page_map)):
            self._image_loaded_events.append(threading.Event())

    def _load_comic_in_thread(self) -> None:
        logger.debug(f'Load comic: comic_path = "{self._current_comic_path}"')

        load_error = False
        load_warning_only = False
        set_kivy_busy_cursor()

        try:
            self._images = [None for _i in range(len(self._page_map))]

            # noinspection PyBroadException
            try:
                with zipfile.ZipFile(self._current_comic_path, "r") as archive:
                    num_loaded = self._load_pages(archive)

                if self._stop:
                    logger.warning(
                        "Image loading stopped before all images loaded."
                        f" Loaded {num_loaded} out of {len(self._page_map)} images."
                    )
                    return

                assert num_loaded == len(self._page_map)
                assert all(ev.is_set() for ev in self._image_loaded_events)
                logger.info(f'Loaded {num_loaded} images from "{self._current_comic_path}".')

                Clock.schedule_once(lambda _dt: self._on_all_images_loaded(), 0)

            except FileNotFoundError:
                logger.exception(f'Comic file not found: "{self._current_comic_path}".')
                load_error = True
            except zipfile.BadZipFile:
                logger.exception(f'Bad zip file: "{self._current_comic_path}".')
                load_error = True
            except KeyError:
                logger.exception(
                    "Key error accessing page_map or image_load_order, possibly due to stop/reset:"
                )
                load_error = True
            except IndexError:
                if not self._stop:
                    logger.exception(
                        f'Unexpected index error reading comic: stop = "{self._stop}".'
                    )
                else:
                    logger.warning(
                        f'Index error reading comic: probably because stop = "{self._stop}".'
                    )
                    load_warning_only = True
                    load_error = True
            except Exception:  # noqa: BLE001
                _, _, tb = sys.exc_info()
                tb_info = traceback.extract_tb(tb)
                filename, line, func, text = tb_info[-1]
                logger.exception(
                    f'Error loading comic at "{filename}:{line}" in "{func}" ({text}): '
                )
                load_error = True

        finally:
            set_kivy_normal_cursor()
            if load_error:
                self._close_and_report_load_error(load_warning_only)

    def _load_pages(self, archive: ZipFile) -> int:
        """
        Dynamic prefetch window implementation.

        - Worker threads perform ZIP read + PIL decode + Fantagraphics processing + resize + PNG encode.
        - Keeps a sliding window of in-flight tasks, dynamically adjusted based on memory pressure.
        - In-flight window grows when memory is low, shrinks when memory rises.
        - Ensures ordered delivery and early-first-image callback.
        """

        # Wrap load to support cooperative cancellation.
        def load_wrapper(pg_info: PageInfo) -> tuple[io.BytesIO, str]:
            if self._stop:
                msg = "Load cancelled before starting work."
                raise CancelledError(msg)

            result = self._load_image_content(archive, pg_info)

            if self._stop:
                msg = "Load cancelled during work."
                raise CancelledError(msg)

            return result

        timing = Timing()
        num_pages = len(self._image_load_order)

        logger.debug(f"Dynamic window load: {num_pages} pages total.")

        first_page_index_to_display = self._page_map[self._image_load_order[0]].page_index
        logger.debug(f"First page index to display: {first_page_index_to_display}.")

        worker_count = self.get_worker_count_for_pages(num_pages)
        base_max_window = max(PREFETCH_MIN, int(worker_count * PREFETCH_MAX_FACTOR))
        dynamic_window = base_max_window

        logger.debug(
            f"Workers={worker_count}, dynamic window starts at {dynamic_window} "
            f"(min={PREFETCH_MIN}, max={base_max_window})"
        )

        tracemalloc.start()

        num_loaded = 0
        load_iter = iter(self._image_load_order)
        futures: dict = {}

        # We'll keep a sliding window of futures up to prefetch_window in size.
        with ThreadPoolExecutor(max_workers=worker_count) as executor:

            def submit_next():
                """Attempt to schedule next page if window not full."""
                nonlocal dynamic_window
                if len(futures) >= dynamic_window:
                    return False
                try:
                    load_key = next(load_iter)
                except StopIteration:
                    return False

                page_info = self._page_map[load_key]
                fut = executor.submit(load_wrapper, page_info)
                futures[fut] = page_info.page_index
                return True

            # Prime initial window.
            for _ in range(dynamic_window):
                if not submit_next():
                    break

            try:
                # Process futures as they complete, maintaining the prefetch window.
                while futures:
                    if self._stop:
                        logger.warning("Stop flag set. Cancelling remaining page loads.")
                        for f in futures:
                            f.cancel()
                        break

                    done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)

                    # Read memory usage.
                    current_mem, peak_mem = tracemalloc.get_traced_memory()
                    current_mib = current_mem / (1024 * 1024)

                    # Adjust dynamic window based on memory.
                    if current_mib > MEMORY_HIGH_WATER:
                        dynamic_window = max(
                            PREFETCH_MIN, dynamic_window - 1
                        )
                    elif current_mib < MEMORY_LOW_WATER:
                        dynamic_window = min(
                            base_max_window, dynamic_window + 1
                        )

                    logger.debug(
                        f"[dyn] mem={current_mib:.1f} MiB, window={dynamic_window}, "
                        f"inflight={len(futures)}"
                    )

                    for fut in done:
                        page_index = futures.pop(fut)

                        if self._stop:
                            logger.warning(f"Stop flag set while handling page index {page_index}.")
                            break

                        try:
                            image_stream, image_ext = fut.result()
                        except CancelledError:
                            logger.warning(f"Page {page_index} cancelled.")
                            break
                        except Exception as e:
                            logger.exception(f"Error loading page {page_index}")
                            raise CancelledError(e) from e

                        # Normal delivery.
                        self._images[page_index] = (image_stream, image_ext)
                        self._image_loaded_events[page_index].set()
                        num_loaded += 1

                        logger.debug(
                            f"Delivered page {page_index} "
                            f"({num_loaded}/{num_pages}, elapsed={timing.get_elapsed_time_with_unit()})"
                        )

                        # First page event
                        if page_index == first_page_index_to_display and not self._stop:
                            logger.info(
                                f"First page index to display, {page_index}, was loaded "
                                f"after {timing.get_elapsed_time_with_unit()}."
                            )
                            Clock.schedule_once(lambda _dt: self._on_first_image_loaded(), 0)

                        # Try to keep the number of in-flight tasks up to prefetch_window.
                        if not self._stop:
                            submit_next()

                    if self._stop:
                        # We've already requested cancellation above; break out of the loop.
                        break

            finally:
                executor.shutdown(cancel_futures=True)
                tracemalloc.stop()
                logger.debug("Dynamic loader executor shutdown.")

        logger.debug(
            f"Dynamic load finished: {num_loaded}/{num_pages} pages "
            f"processed in {timing.get_elapsed_time_with_unit()} (stop={self._stop})."
        )

        return num_loaded

    def get_worker_count_for_pages(self, num_pages: int) -> int:
        return min(self._max_worker_count, num_pages)

    def _close_and_report_load_error(self, load_warning_only: bool) -> None:
        self._stop = True
        self.close_comic()
        Clock.schedule_once(lambda _dt: self._on_load_error(load_warning_only), 0)

    def _get_image_path(self, page_info: PageInfo) -> tuple[str, bool]:
        """Determine the path to an image file for a given page.

        This method acts as a dispatcher, deciding whether to get the path
        from a prebuilt archive or from a Fantagraphics source volume.

        Args:
            page_info: The PageInfo object for the desired page.

        Returns:
            A tuple containing:
                - str (image_path): The path to the image file inside the zip archive.
                - bool (is_from_archive):
                          True if the path is relative to a zip archive,
                          False if it's a direct path to a file or from an override zip.

        """
        if not self._fanta_volume_archive:
            # Get path to prebuilt archive image.
            image_path = Path("images") / page_info.dest_page.page_filename, True
        else:
            # Get path to Fantagraphics archive or override file.
            image_path = self._get_fanta_volume_image_path(page_info)

        # Zip files always use '/' as a separator (even on Windows).
        return str(image_path[0]).replace("\\", "/"), image_path[1]

    def _get_fanta_volume_image_path(self, page_info: PageInfo) -> tuple[Path, bool]:
        if is_title_page(page_info.srce_page) or is_blank_page(
            page_info.srce_page.page_filename, page_info.page_type
        ):
            return Path(self._sys_file_paths.get_empty_page_file()), False

        page_str = Path(page_info.srce_page.page_filename).stem

        assert self._fanta_volume_archive
        if page_str in self._fanta_volume_archive.extra_images_page_map:
            return Path(self._fanta_volume_archive.extra_images_page_map[page_str]), False

        assert self._use_fantagraphics_overrides
        if self._use_fantagraphics_overrides and (
            page_str in self._fanta_volume_archive.override_images_page_map
        ):
            return Path(self._fanta_volume_archive.override_images_page_map[page_str]), False

        return Path(self._fanta_volume_archive.archive_images_page_map[page_str]), True

    def _load_image_content(self, archive: ZipFile, page_info: PageInfo) -> tuple[io.BytesIO, str]:
        image_path, is_from_archive = self._get_image_path(page_info)

        logger.debug(
            f'Loading page index {page_info.page_index} (page "{page_info.display_page_num}"):'
            f' image_path = "{image_path}", is_from_archive = {is_from_archive}.'
        )

        if is_from_archive:
            zip_path = zipfile.Path(archive, at=str(image_path))
            pil_image = load_pil_image_from_zip(zip_path)
        elif page_info.srce_page.page_type in [PageType.BLANK_PAGE, PageType.TITLE]:
            ext = Path(image_path).suffix
            file_data = self._empty_page_image
            pil_image = load_pil_image_from_bytes(file_data, ext)
        else:
            assert self._fanta_volume_archive is not None
            zip_path = zipfile.Path(self._fanta_volume_archive.override_archive, at=str(image_path))
            pil_image = load_pil_image_from_zip(zip_path)

        return self._get_image_data(pil_image, page_info)

    def _get_image_data(
        self, pil_image: Image.Image, page_info: PageInfo
    ) -> tuple[io.BytesIO, str]:
        if self._fanta_volume_archive:
            assert self._comic_book_image_builder
            pil_image = self._comic_book_image_builder.get_dest_page_image(
                pil_image, page_info.srce_page, page_info.dest_page
            )

        pil_image_resized = ImageOps.contain(
            pil_image,
            (self._max_window_width, self._max_window_height),
            PilImage.Resampling.LANCZOS,
        )

        return get_pil_image_as_png_bytes(pil_image_resized), PNG_EXT_FOR_KIVY


# We store the result so the autotuner only runs once per process.
_AUTO_TUNED_THREAD_COUNT = None
_AUTOTUNE_LOCK = threading.Lock()


def autotune_worker_count(sample_images: list[str] | None = None) -> int:
    """Automatically determine the optimal number of worker threads for ZIP + JPEG decode workloads.

    sample_images: optional list of paths (inside ZIP or filesystem)
                   to use as test samples.
                   If None, it generates synthetic JPEG bytes.

    Returns: integer worker count.
    """
    global _AUTO_TUNED_THREAD_COUNT  # noqa: PLW0603

    with _AUTOTUNE_LOCK:
        if _AUTO_TUNED_THREAD_COUNT is not None:
            return _AUTO_TUNED_THREAD_COUNT

        cpu_count = os.cpu_count() or 1

        # If 1-2 CPUs → don't bother benchmarking.
        if cpu_count <= 2:  # noqa: PLR2004
            _AUTO_TUNED_THREAD_COUNT = 1
            return 1

        logger.debug("[autotune] Starting thread count autotune...")

        # ----------------------------------------------------------
        # Step 1: obtain samples to decode
        # ----------------------------------------------------------

        if sample_images:
            samples = []
            for path in sample_images:
                p = Path(path)
                samples.append(p.read_bytes())
        else:
            # Create synthetic JPEGs in memory (fast + reliable)
            samples = []

            for _ in range(4):
                image = Image.new("RGB", (1800, 2600), (128, 64, 32))
                buf = io.BytesIO()
                image.save(buf, format="JPEG", quality=90)
                samples.append(buf.getvalue())

        # ----------------------------------------------------------
        # Step 2: test performance for various worker counts
        # ----------------------------------------------------------

        # Try these worker counts (cap at CPU count).
        test_counts = [wc for wc in [1, 2, 3, 4, 6, 8, 10, 12, 16] if wc <= cpu_count]

        times = {}

        for wc in test_counts:
            t0 = time.perf_counter()

            def task(data) -> None:  # noqa: ANN001
                img = Image.open(io.BytesIO(data))
                img.load()
                # noinspection PyUnusedLocal
                img = img.resize((900, 1300), Image.Resampling.LANCZOS)

            with ThreadPoolExecutor(max_workers=wc) as tp:
                futures = [tp.submit(task, s) for s in samples]
                for f in futures:
                    f.result()  # ensure completion

            dt = time.perf_counter() - t0
            times[wc] = dt
            logger.debug(f"[autotune] {wc} threads took {dt:.4f} sec.")

        # ----------------------------------------------------------
        # Step 3: pick the best-performing worker count.
        # ----------------------------------------------------------

        best_wc = min(times, key=lambda wc: times[wc])
        best_time = times[best_wc]

        # Some safety: don't return something silly like 1,
        # if the difference is tiny. Allow slight smoothing.
        for wc in sorted(times):
            if times[wc] <= best_time * 1.08:  # within 8 percent of fastest
                best_wc = wc

        logger.debug(f"[autotune] Best worker count selected: {best_wc}.")

        _AUTO_TUNED_THREAD_COUNT = best_wc
        return best_wc
