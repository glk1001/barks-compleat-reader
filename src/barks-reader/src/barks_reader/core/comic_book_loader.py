from __future__ import annotations

import queue
import sys
import threading
import traceback
import zipfile
from collections import OrderedDict
from concurrent.futures import FIRST_COMPLETED, CancelledError, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from barks_build_comic_images.build_comic_images import build_double_page_image
from barks_fantagraphics.comics_utils import get_dest_comic_zip_file_stem
from barks_fantagraphics.fanta_comics_info import (
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
    FantaComicBookInfo,
    get_fanta_volume_from_str,
)
from comic_utils.comic_consts import CBZ_FILE_EXT
from comic_utils.timing import Timing
from loguru import logger

from . import log_markers
from .comic_book_loader_platform_settings import (
    get_max_worker_count,
    get_prefetch_tuning,
    process_rss_mib,
    release_freed_memory,
)
from .fantagraphics_volumes import (
    FantagraphicsVolumeArchives,
    MissingArchiveFilesError,
    MissingVolumeError,
    PageSourceKind,
    VolumeScanError,
)
from .page_image import PageImage

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from .comic_book_page_info import PageInfo
    from .fantagraphics_volumes import FantagraphicsArchive
    from .page_image_source import PageImageSource
    from .ports import Cursor, Scheduler
    from .reader_settings import ReaderSettings

ALL_FANTA_VOLUMES = list(range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1))

_LOADER_JOIN_TIMEOUT_SECS = 2.0


@dataclass(frozen=True, slots=True)
class RetainedImageStats:
    """How much memory the loader's cached page images currently hold."""

    loaded: int
    total_mib: float
    avg_kib: float
    max_kib: float
    rss_now_mib: float
    rss_growth_mib: float


@dataclass(slots=True)
class _Load:
    """Everything one comic's load reads, and the flag that stops it.

    The loader thread reads only this, never the loader's current comic: a thread that
    outlives its stop (a decode slower than the join) has its own flag, which stays
    raised, and its own pages, so it cannot come back to life or touch the next comic.
    """

    generation: int = 0
    image_source: PageImageSource | None = None
    image_load_order: list[str] = field(default_factory=list)
    num_pages_awaited: int = 1
    page_map: OrderedDict[str, PageInfo] = field(default_factory=OrderedDict)
    images: list[PageImage | None] = field(default_factory=list)
    loaded_events: list[threading.Event] = field(default_factory=list)
    # Page keys the user has navigated to that should jump the prefetch queue.
    # Written from the UI thread (prioritize_page), drained on the loader thread.
    priority_keys: queue.SimpleQueue[str] = field(default_factory=queue.SimpleQueue)
    desc: str = ""
    stop: bool = False


class ComicBookLoader:
    """Orchestrates background loading of comic book page images.

    Manages prefetch threading, page caching, and callback delivery.
    Delegates actual image I/O to a :class:`PageImageSource`.
    """

    def __init__(
        self,
        reader_settings: ReaderSettings,
        on_first_image_loaded: Callable[[], None],
        on_all_images_loaded: Callable[[], None],
        on_load_error: Callable[[], None],
        *,
        scheduler: Scheduler,
        cursor: Cursor,
    ) -> None:
        self._reader_settings = reader_settings
        self._sys_file_paths = self._reader_settings.sys_file_paths
        self._fanta_volume_archives: FantagraphicsVolumeArchives | None = None
        # The folder those archives were scanned from: the setting can change after boot.
        self._volumes_dir_scanned: Path | None = None
        self._scheduler = scheduler
        self._cursor = cursor

        self._image_loaded_events: list[threading.Event] = []
        self._page_map: OrderedDict[str, PageInfo] = OrderedDict()
        self._images: list[PageImage | None] = []
        # Counts the comics set and closed, so a load error reported after its comic
        # was superseded or closed can be told from one for the comic now open.
        self._load_generation = 0

        self._load = _Load()
        self._current_comic_desc = ""
        self._image_source: PageImageSource | None = None

        self._on_first_image_loaded: Callable[[], None] = on_first_image_loaded
        self._on_all_images_loaded: Callable[[], None] = on_all_images_loaded
        self._on_load_error = on_load_error

        with Path(self._sys_file_paths.get_empty_page_file()).open("rb") as file:
            self._empty_page_image = file.read()

        self._thread: threading.Thread | None = None
        self._max_worker_count = get_max_worker_count()
        logger.debug(f"Using {self._max_worker_count} as max worker threads.")

    @property
    def cursor(self) -> Cursor:
        """The cursor port used to signal busy/normal state to the UI."""
        return self._cursor

    @property
    def empty_page_image(self) -> bytes:
        """Raw bytes for the blank/title page placeholder image."""
        return self._empty_page_image

    def init_data(self) -> None:
        """Preload Fantagraphics volume metadata (if not using prebuilt archives)."""
        if self._reader_settings.use_prebuilt_archives:
            logger.info(log_markers.USING_PREBUILT_ARCHIVES)
            self._fanta_volume_archives = None
        else:
            timing = Timing()

            logger.info(log_markers.USING_VOLUME_ARCHIVES)
            volumes_dir = self._reader_settings.fantagraphics_volumes_dir
            fanta_volume_archives = FantagraphicsVolumeArchives(
                volumes_dir,
                self._sys_file_paths.get_barks_reader_fantagraphics_overrides_root_dir(),
                ALL_FANTA_VOLUMES,
            )
            try:
                fanta_volume_archives.load()
            except MissingArchiveFilesError:
                # Missing volumes are built as placeholders carrying their bundled
                # override/extra pages, so keep the fully-built archive set (for reading
                # the restored censored stories) before the caller records the state.
                # Without this, a later resolve would re-init and re-raise uncaught.
                self._fanta_volume_archives = fanta_volume_archives
                self._volumes_dir_scanned = volumes_dir
                raise
            self._fanta_volume_archives = fanta_volume_archives
            self._volumes_dir_scanned = volumes_dir

            logger.info(
                log_markers.VOLUMES_LOADED.format(elapsed=timing.get_elapsed_time_with_unit())
            )

    # ------------------------------------------------------------------
    # Source creation helpers (used by callers before set_comic)
    # ------------------------------------------------------------------

    def resolve_archive_for_comic(
        self,
        fanta_info: FantaComicBookInfo,
        page_map: Mapping[str, PageInfo],
        *,
        use_fantagraphics_overrides: bool,
    ) -> tuple[Path, FantagraphicsArchive | None]:
        """Look up the archive path and volume metadata for a comic.

        Args:
            fanta_info: The comic to resolve.
            page_map: The comic's pages, used to decide whether a missing volume can
                still be read purely from bundled override/extra pages.
            use_fantagraphics_overrides: Whether the pages will be read with the
                bundled override images, as the image source will be told. Off, an
                overridden page comes from the library archive, so it needs it.

        Returns:
            A tuple of (*archive_path*, *fanta_volume_archive*).
            *fanta_volume_archive* is ``None`` when using prebuilt archives.

        Raises:
            MissingVolumeError: If the volume is absent and at least one page of the
                comic can only come from the (missing) library archive.
            FileNotFoundError: If prebuilt archives are in use and the comic's own
                archive file is absent.
            VolumeScanError: If the volumes had to be scanned here, and that failed.

        """
        if self._reader_settings.use_prebuilt_archives:
            return self._get_prebuilt_comic_path(fanta_info), None

        self._scan_volumes_if_needed()

        assert self._fanta_volume_archives
        fanta_volume_archive = self._fanta_volume_archives.get_fantagraphics_archive(
            get_fanta_volume_from_str(fanta_info.fantagraphics_volume)
        )
        # A missing volume can still be read if every page is bundled (a title/blank
        # page, or an override/extra image) - e.g. the fully hand-restored censored
        # stories. Only block when a page genuinely needs the absent library archive.
        if fanta_volume_archive.is_missing and any(
            fanta_volume_archive.page_source_for(
                page_info, use_overrides=use_fantagraphics_overrides
            ).kind
            is PageSourceKind.ARCHIVE
            for page_info in page_map.values()
        ):
            raise MissingVolumeError(
                get_fanta_volume_from_str(fanta_info.fantagraphics_volume),
                fanta_info.comic_book_info.title,
            )

        return fanta_volume_archive.archive_filename, fanta_volume_archive

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_comic(
        self,
        image_source: PageImageSource,
        image_load_order: list[str],
        page_map: OrderedDict[str, PageInfo],
        archive_desc: str = "",
        num_pages_awaited: int = 1,
    ) -> None:
        """Start loading a comic using the given image source.

        Args:
            image_source: Provides page images on demand.
            image_load_order: Page keys in the order they should be loaded.
            page_map: Ordered mapping of page keys to ``PageInfo`` objects.
            archive_desc: Human-readable description for logging.
            num_pages_awaited: How many of the leading keys in *image_load_order* the
                reader waits on before it shows anything: one page, or both of a
                double-page pair. They load together, and alone.

        """
        assert len(image_load_order) == len(page_map)
        assert 1 <= num_pages_awaited <= len(image_load_order)

        # Stop any previous loading process before starting a new one.
        if self._thread and self._thread.is_alive():
            self.stop_now()

        self._close_image_source()
        self._image_source = image_source
        self._page_map = page_map
        self._current_comic_desc = archive_desc
        self._load_generation += 1

        logger.info(f"Archive source: {self._current_comic_desc}.")

        # The page slots are laid out here, on the UI thread, before the loader thread
        # exists: laid out by the thread, a page turn arriving first found an empty or
        # the previous comic's list and read the wrong comic's readiness from it.
        self._images = [None] * len(page_map)
        self._image_loaded_events = [threading.Event() for _ in page_map]
        # A new load, not the old one reset: an old thread that outlived the stop above
        # keeps its own raised flag, its own pages and its own priority queue.
        self._load = _Load(
            generation=self._load_generation,
            image_source=image_source,
            image_load_order=image_load_order,
            num_pages_awaited=num_pages_awaited,
            page_map=page_map,
            images=self._images,
            loaded_events=self._image_loaded_events,
            desc=archive_desc,
        )
        self._start_loading_thread()

    def get_image_ready_for_reading(self, page_index: int) -> PageImage:
        """Return the loaded page at *page_index*."""
        assert self._images
        assert 0 <= page_index < len(self._images)

        page = self._images[page_index]
        assert page is not None

        return page

    def get_double_page_image_ready_for_reading(self, left_idx: int, right_idx: int) -> PageImage:
        """Composite two loaded pages side by side for double-page display.

        Args:
            left_idx: Page index of the left page.
            right_idx: Page index of the right page.

        Returns:
            The two pages as one landscape page.

        """
        left_page = self.get_image_ready_for_reading(left_idx)
        right_page = self.get_image_ready_for_reading(right_idx)

        composited = build_double_page_image(left_page.to_pil(), right_page.to_pil())

        return PageImage.from_pil(composited)

    def get_image_info_str(self, page_str: str) -> str:
        """Return a human-readable description of the image source for a page."""
        assert self._image_source is not None
        page_info = self._page_map[page_str]
        return self._image_source.get_image_info_str(page_info)

    def wait_load_event(self, page_index: int, timeout: float) -> bool:
        """Block until the image at *page_index* is loaded, or *timeout* expires.

        With no comic open nothing is loaded, so this is ``False`` at once.
        """
        if not self._images:
            return False
        assert 0 <= page_index < len(self._images)
        return self._image_loaded_events[page_index].wait(timeout)

    def prioritize_page(self, page_str: str) -> None:
        """Ask the background loader to fetch the page keyed *page_str* next.

        Used when the user navigates to a page that has not been prefetched yet
        (e.g. paging backward, where pages load last). The page jumps to the front
        of the prefetch queue so it loads as soon as a worker slot frees up, rather
        than in its normal load-order position. A no-op if the page is already
        loaded or the comic is not currently loading.
        """
        if not self._images:
            return
        page_info = self._page_map.get(page_str)
        if page_info is None or self._image_loaded_events[page_info.page_index].is_set():
            return
        self._load.priority_keys.put(page_str)

    def close_comic(self) -> None:
        """Stop loading and release all cached images.

        UI thread only: the page lists it clears are the ones the UI thread's page
        poll reads, so the loader thread hands its own close here through the
        scheduler (:meth:`_close_and_report_load_error`).
        """
        if self._image_source is None:
            return

        logger.debug(f'Close the comic: "{self._current_comic_desc}".')

        self.stop_now()

        self._close_image_source()
        self._images.clear()
        self._image_loaded_events.clear()
        self._current_comic_desc = ""
        self._load_generation += 1
        # The pages just dropped, and whatever the load's workers freed, go back to
        # the system now rather than sitting in the allocator's arenas.
        release_freed_memory()

    def _close_image_source(self) -> None:
        if self._image_source is not None:
            self._image_source.close()
            self._image_source = None

    def stop_now(self) -> None:
        """Signal the background thread to stop and wait for it to terminate.

        UI thread only, like the close it is part of. A no-op once stopped with no
        thread left to wait for. A thread still alive after an earlier stop (a load
        error raises the flag on the loader thread, then hands its close to the UI
        thread) is joined all the same: left running, the next comic's load would be
        refused as already in progress.
        """
        if self._load.stop and self._thread is None:
            return

        logger.debug("Tell the comic book loader to stop...")
        self._load.stop = True

        thread = self._thread
        if thread is not None and thread.is_alive():
            logger.debug("Waiting for image loading thread to terminate...")
            thread.join(timeout=_LOADER_JOIN_TIMEOUT_SECS)
            if thread.is_alive():
                logger.error("Image loading thread did not terminate in time.")

        self._thread = None
        self._cursor.set_normal()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _scan_volumes_if_needed(self) -> None:
        """Scan the volumes if boot did not, or the setting's folder has changed since.

        Boot reports a bad library itself. Here a comic is being opened, so a volume
        missing is left to that comic's own check, and any other failure is one error
        for the caller to report.
        """
        volumes_dir = self._reader_settings.fantagraphics_volumes_dir
        if self._fanta_volume_archives and self._volumes_dir_scanned in (None, volumes_dir):
            return
        try:
            self.init_data()
        except MissingArchiveFilesError as e:
            logger.warning(e)
        except Exception as e:
            raise VolumeScanError(str(e)) from e

    def _get_prebuilt_comic_path(self, fanta_info: FantaComicBookInfo) -> Path:
        comic_file_stem = get_dest_comic_zip_file_stem(
            fanta_info.comic_book_info.get_title_str(),
            fanta_info.fanta_chronological_number,
            fanta_info.get_short_issue_title(),
        )

        comic_path = Path(self._reader_settings.prebuilt_comics_dir) / (
            comic_file_stem + CBZ_FILE_EXT
        )
        if not comic_path.is_file():
            msg = f'Could not find comic file "{comic_path}".'
            raise FileNotFoundError(msg)

        return comic_path

    def _start_loading_thread(self) -> None:
        """Create and start the background thread for loading comic images."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Load is already in progress.")
            return

        logger.debug(f'Starting comic load in background thread for: "{self._current_comic_desc}"')
        thread = threading.Thread(
            target=self._load_comic_in_thread, args=(self._load,), daemon=True
        )
        thread.start()
        self._thread = thread

    def _retained_image_stats(self, rss_before_mib: float) -> RetainedImageStats:
        """Measure how much RAM the currently-cached page images occupy.

        Every loaded page is kept in ``self._images`` as window-resized pixels
        until ``close_comic``, so this is the aggregate cost of holding a
        whole comic open. Split out from the logging so the unit arithmetic is
        assertable without pinning the log wording.

        Args:
            rss_before_mib: Process RSS sampled before the load started.

        Returns:
            The page count, totals and the RSS growth since *rss_before_mib*.

        """
        sizes = [page.nbytes for page in self._images if page is not None]
        loaded = len(sizes)
        rss_now = process_rss_mib()
        return RetainedImageStats(
            loaded=loaded,
            total_mib=sum(sizes) / (1024 * 1024),
            avg_kib=(sum(sizes) / loaded / 1024) if loaded else 0.0,
            max_kib=(max(sizes) / 1024) if sizes else 0.0,
            rss_now_mib=rss_now,
            rss_growth_mib=rss_now - rss_before_mib,
        )

    def _log_retained_image_memory(self, rss_before_mib: float) -> None:
        """Log how much RAM the fully-loaded comic's retained pages occupy.

        Makes the cost of large collections (e.g. "All Covers")
        visible in the logs.
        """
        stats = self._retained_image_stats(rss_before_mib)
        logger.info(
            f"[mem] Retained pages: {stats.loaded} pages hold {stats.total_mib:.1f} MiB "
            f"(avg {stats.avg_kib:.0f} KiB/page, max {stats.max_kib:.0f} KiB). "
            f"Process RSS {stats.rss_now_mib:.0f} MiB "
            f"(+{stats.rss_growth_mib:.0f} MiB since load start)."
        )

    def _load_comic_in_thread(self, load: _Load) -> None:
        logger.debug(f'Load comic: "{load.desc}"')

        load_error = False

        try:
            assert load.image_source is not None

            # noinspection PyBroadException
            try:
                rss_before_mib = process_rss_mib()
                self._cursor.set_busy()

                # Opening is inside the try: it is where the archive is actually
                # touched, so a missing or truncated volume raises FileNotFoundError
                # or BadZipFile here. Outside, those escaped the loader thread
                # entirely - no error callback, no dialog, just a comic that never
                # loaded.
                load.image_source.open()

                if load.stop:
                    # An open slower than the join finishes after the close, which found
                    # nothing to close: nothing else will close what it has just opened.
                    logger.warning(f'Stopped while opening "{load.desc}": closing it again.')
                    load.image_source.close()
                    return

                num_loaded = self._load_pages(load)

                if load.stop:
                    logger.warning(
                        "Image loading stopped before all images loaded."
                        f" Loaded {num_loaded} out of {len(load.page_map)} images."
                    )
                    return

                assert num_loaded == len(load.page_map)
                assert all(ev.is_set() for ev in load.loaded_events)
                logger.info(
                    log_markers.COMIC_IMAGES_LOADED.format(count=num_loaded, comic=load.desc)
                )
                # The workers' decode buffers are all freed now: return them, so the
                # resident set holds the comic's pages and not the work of making them.
                release_freed_memory()
                self._log_retained_image_memory(rss_before_mib)

                self._schedule_for_load(load, self._on_all_images_loaded)

            except FileNotFoundError:
                logger.exception(f'Comic file not found: "{load.desc}".')
                load_error = True
            except zipfile.BadZipFile:
                logger.exception(f'Bad zip file: "{load.desc}".')
                load_error = True
            except KeyError:
                logger.exception(
                    f'A page is missing from its archive or page map in "{load.desc}".'
                )
                load_error = True
            except IndexError:
                # A close empties the page slots under a stopping load: expected then.
                if load.stop:
                    logger.warning("Index error reading comic: it was being stopped.")
                else:
                    logger.exception("Unexpected index error reading comic.")
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
            self._finish_load(load, load_error=load_error)

    def _finish_load(self, load: _Load, *, load_error: bool) -> None:
        # A thread outliving its stop must not call off the next comic's busy cursor.
        if load is self._load:
            self._cursor.set_normal()
        if load_error:
            self._close_and_report_load_error(load)

    def _load_pages(self, load: _Load) -> int:  # noqa: C901, PLR0912, PLR0915
        """Platform-aware dynamic prefetch window implementation.

        Uses system profile (CPU, RAM) to pick prefetch and memory thresholds.
        Worker threads call ``load.image_source.load_page_image()``.
        Maintains a sliding window of in-flight tasks, adjusting size based
        on memory. Pages are delivered as they land, in whatever order that is.
        """
        assert load.image_source is not None
        image_source = load.image_source

        def load_wrapper(pg_info: PageInfo) -> PageImage:
            if load.stop:
                msg = "Load cancelled before starting work."
                raise CancelledError(msg)

            result = image_source.load_page_image(pg_info)

            if load.stop:
                msg = "Load cancelled during work."
                raise CancelledError(msg)

            return result

        timing = Timing()
        num_pages = len(load.image_load_order)

        logger.debug(f"Platform-aware load: {num_pages} pages total.")

        first_page_index_to_display = load.page_map[load.image_load_order[0]].page_index
        logger.debug(f"First page index to display: {first_page_index_to_display}.")
        pages_awaited = {
            load.page_map[key].page_index for key in load.image_load_order[: load.num_pages_awaited]
        }

        worker_count = self.get_worker_count_for_pages(num_pages)
        tuning = get_prefetch_tuning(worker_count, num_pages)
        tuning.start_memory_watch()
        dynamic_window = tuning.get_initial_dynamic_window()

        logger.debug(
            f"Loader config: workers={worker_count}, window_start={dynamic_window},"
            f" window_min={tuning.prefetch_min}, window_max={tuning.base_max_window},"
            f" shrink below {tuning.shrink_below_mib} MiB available,"
            f" grow above {tuning.grow_above_mib} MiB."
        )

        num_loaded = 0
        load_iter = iter(load.image_load_order)
        submitted: set[str] = set()
        futures: dict[Future, int] = {}

        def next_load_key() -> str | None:
            """Return the next page key to load, honoring user navigation requests.

            Priority requests (pages the user navigated to) jump ahead of the
            normal prefetch order. Keys already submitted are skipped (a loaded page
            was submitted first), so every page is still submitted exactly once.
            """
            while True:
                try:
                    key = load.priority_keys.get_nowait()
                except queue.Empty:
                    break
                if key in submitted:
                    continue
                return key

            for key in load_iter:
                if key in submitted:
                    continue
                return key
            return None

        # The pages the reader is waiting for go alone: primed all at once, the
        # window set a worker's worth of other pages competing with them for the
        # cores. Until they have all landed the window holds only the ones still in
        # flight, so a landed left page does not let a stranger in beside the right.
        window_open = False

        # We'll keep a sliding window of futures up to prefetch_window in size.
        with ThreadPoolExecutor(max_workers=worker_count) as executor:

            def submit_next() -> bool:
                """Submit the next page if window not full."""
                window = dynamic_window if window_open else len(pages_awaited)
                if len(futures) >= window:
                    return False
                load_key = next_load_key()
                if load_key is None:
                    return False

                submitted.add(load_key)
                page_info = load.page_map[load_key]
                fut = executor.submit(load_wrapper, page_info)
                futures[fut] = page_info.page_index

                return True

            # Prime the window with the awaited pages alone.
            while submit_next():
                pass

            try:
                # Process futures as they complete, maintaining the prefetch window.
                while futures:
                    if load.stop:
                        logger.warning("Stop flag set. Cancelling remaining page loads.")
                        for f in futures:
                            f.cancel()
                        break

                    done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)

                    available_mib, dynamic_window = tuning.get_new_dynamic_window(dynamic_window)
                    logger.debug(
                        f"[prefetch] available={available_mib:.0f} MiB, window={dynamic_window},"
                        f" inflight={len(futures)}"
                    )

                    for future in done:
                        page_index = futures.pop(future)

                        if load.stop:
                            logger.warning(f"Stop flag set while handling page index {page_index}.")
                            break

                        try:
                            page_image = future.result()
                        except CancelledError:
                            logger.warning(f"Page {page_index} cancelled.")
                            break
                        except Exception:
                            # Only here knows the page. The handlers in _load_comic_in_thread
                            # log the traceback, so the error goes on to them as it is.
                            logger.error(f"Error loading page {page_index}.")
                            raise

                        # Normal page delivery.
                        load.images[page_index] = page_image
                        load.loaded_events[page_index].set()
                        num_loaded += 1

                        logger.debug(
                            f"Loaded page index {page_index} ({num_loaded}/{num_pages},"
                            f" elapsed={timing.get_elapsed_time_with_unit()})"
                        )

                        # First page event
                        if page_index == first_page_index_to_display and not load.stop:
                            logger.info(
                                f"First page index to display, {page_index}, was loaded "
                                f"after {timing.get_elapsed_time_with_unit()}."
                            )
                            self._schedule_for_load(load, self._on_first_image_loaded)
                            # The comic is now readable; don't keep the busy cursor
                            # for the rest of the background prefetch. (Scheduled
                            # after the first-page display callback above.)
                            self._cursor.set_normal()

                        pages_awaited.discard(page_index)
                        if not pages_awaited:
                            # Now the rest of the comic, a window at a time.
                            window_open = True

                        # Fill the window, not just this page's place in it: it may have
                        # grown since, and one for one would hold in-flight at its lowest.
                        while not load.stop and submit_next():
                            pass

                    if load.stop:
                        # We've already requested cancellation above; break out of the loop.
                        break

            finally:
                executor.shutdown(cancel_futures=True)
                logger.info(
                    f"[mem] Peak RSS growth during load: "
                    f"{tuning.get_peak_memory_growth_mib():.1f} MiB."
                )
                logger.debug("Platform-aware comic loading executor shut down.")

        logger.debug(
            f"Load finished: {num_loaded}/{num_pages} pages "
            f"processed in {timing.get_elapsed_time_with_unit()} (stop={load.stop})."
        )

        return num_loaded

    def get_worker_count_for_pages(self, num_pages: int) -> int:
        """Return the worker thread count to use for *num_pages* pages."""
        return min(self._max_worker_count, num_pages)

    def _schedule_for_load(self, load: _Load, callback: Callable[[], None]) -> None:
        """Run *callback* on the UI thread, unless *load*'s comic has gone by then.

        A close or the next comic can land between the post and the callback, which
        would then speak for a comic it knows nothing of.
        """

        def if_still_current() -> None:
            if load.generation == self._load_generation:
                callback()
            else:
                logger.debug("Dropped a callback of a comic since superseded or closed.")

        self._scheduler.schedule_once(if_still_current)

    def _close_and_report_load_error(self, load: _Load) -> None:
        """Hand the failed load's close and its report to the UI thread.

        This runs on the loader thread. The close clears the page lists the UI
        thread's page poll reads, so it goes through the scheduler with the report,
        and the thread never joins itself. A comic set or closed since this one
        failed owns the loader now, so a stale error is dropped rather than closing
        the new comic or raising for one already gone.
        """
        load.stop = True

        def close_and_report() -> None:
            if load.generation != self._load_generation:
                logger.warning("Dropped the load error of a comic since superseded or closed.")
                return
            self.close_comic()
            self._on_load_error()

        self._scheduler.schedule_once(close_and_report)
