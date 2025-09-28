# ruff: noqa: ERA001

from __future__ import annotations

import sys
import threading
import traceback
import zipfile
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING
from zipfile import ZipFile

from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.comics_utils import get_abbrev_path, get_dest_comic_zip_file_stem
from barks_fantagraphics.fanta_comics_info import (
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
    FantaComicBookInfo,
)
from comic_utils.pil_image_utils import (
    get_pil_image_as_png_bytes,
    open_pil_image_from_bytes,
)
from kivy.clock import Clock
from loguru import logger
from PIL import Image as PilImage
from PIL import ImageOps

from barks_reader.fantagraphics_volumes import FantagraphicsArchive, FantagraphicsVolumeArchives
from barks_reader.reader_ui_classes import set_kivy_busy_cursor, set_kivy_normal_cursor
from barks_reader.reader_utils import PNG_EXT_FOR_KIVY, is_blank_page, is_title_page

if TYPE_CHECKING:
    import io
    from collections.abc import Callable

    from barks_build_comic_images.build_comic_images import ComicBookImageBuilder

    from barks_reader.comic_book_page_info import PageInfo
    from barks_reader.reader_settings import ReaderSettings

ALL_FANTA_VOLUMES = list(range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1))
# ALL_FANTA_VOLUMES = [i for i in range(5, 7 + 1)]


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

    def init_data(self) -> None:
        if self._reader_settings.use_prebuilt_archives:
            logger.info("Using prebuilt archives. No extra data to initialize.")
            self._fanta_volume_archives = None
        else:
            logger.info("Using Fantagraphics volume archives. Now loading volume info...")
            self._fanta_volume_archives = FantagraphicsVolumeArchives(
                self._reader_settings.fantagraphics_volumes_dir,
                self._sys_file_paths.get_barks_reader_fantagraphics_overrides_root_dir(),
                ALL_FANTA_VOLUMES,
            )
            self._fanta_volume_archives.load()

    def get_image_ready_for_reading(self, page_index: int) -> tuple[io.BytesIO, str]:
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

    def get_load_event(self, page_index: int) -> threading.Event:
        assert 0 <= page_index < len(self._images)
        return self._image_loaded_events[page_index]

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
            self._fanta_volume_archive = self._fanta_volume_archives.get_fantagraphics_archive(
                int(fanta_info.fantagraphics_volume[-2:])
            )
            if self._fanta_volume_archive.has_overrides():
                self._fanta_volume_archive.override_archive = zipfile.ZipFile(
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

        self._stop = True

        if self._thread and self._thread.is_alive():
            logger.debug("Waiting for image loading thread to terminate...")
            self._thread.join(timeout=2.0)  # Wait for 2 seconds
            if self._thread.is_alive():
                logger.error("Image loading thread did not terminate in time.")

        self._thread = None

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

        comic_path = Path(self._reader_settings.prebuilt_comics_dir) / (comic_file_stem + ".cbz")
        if comic_path.suffix not in [".cbz", ".zip"]:
            msg = "Expected '.cbz' or '.zip' file."
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
        num_loaded = 0
        first_loaded = False

        for i in range(len(self._image_load_order)):
            if self._stop:
                logger.warning(f"For i = {i}, image loading stopped.")
                return num_loaded

            load_index = self._image_load_order[i]
            logger.debug(f'For i = {i}, load_index = "{load_index}".')

            page_info = self._page_map[load_index]
            logger.debug(
                f"For i = {i}, page_info ="
                f" {page_info.display_page_num}, {page_info.srce_page.page_filename}."
            )

            # Double check stop flag before any more heavy processing.
            if self._stop:
                logger.warning(f"For i = {i}, image loading stopped before getting image.")
                return num_loaded

            page_index = page_info.page_index
            # noinspection PyTypeChecker
            self._images[page_index] = self._load_image_content(archive, page_info)
            num_loaded += 1

            self._image_loaded_events[page_index].set()

            if not first_loaded and not self._stop:
                first_loaded = True
                logger.info(
                    f"Loaded first image,"
                    f" page index = {page_index},"
                    f" page = {page_info.display_page_num}."
                )
                Clock.schedule_once(lambda _dt: self._on_first_image_loaded(), 0)

        return num_loaded

    def _close_and_report_load_error(self, load_warning_only: bool) -> None:
        self._stop = True
        self.close_comic()
        Clock.schedule_once(lambda _dt: self._on_load_error(load_warning_only), 0)

    def _get_image_path(self, page_info: PageInfo) -> tuple[Path, bool]:
        """Determine the path to an image file for a given page.

        This method acts as a dispatcher, deciding whether to get the path
        from a prebuilt archive or from a Fantagraphics source volume.

        Args:
            page_info: The PageInfo object for the desired page.

        Returns:
            A tuple containing:
                - Path: The path to the image file.
                - bool (is_from_archive): True if the path is relative to a zip archive,
                        False if it's a direct path to a file on disk (like an override file).

        """
        if not self._fanta_volume_archive:
            # Return path to prebuilt archive image.
            return Path("images") / page_info.dest_page.page_filename, True

        # Return path to Fantagraphics archive or override file.
        return self._get_fanta_volume_image_path(page_info)

    def _get_fanta_volume_image_path(self, page_info: PageInfo) -> tuple[Path, bool]:
        if is_title_page(page_info.srce_page) or is_blank_page(
            page_info.srce_page.page_filename, page_info.page_type
        ):
            return Path(self._sys_file_paths.get_empty_page_file()), False

        page_str = Path(page_info.srce_page.page_filename).stem

        if page_str in self._fanta_volume_archive.extra_images_page_map:
            return Path(self._fanta_volume_archive.extra_images_page_map[page_str]), False

        if self._use_fantagraphics_overrides and (
            page_str in self._fanta_volume_archive.override_images_page_map
        ):
            return Path(self._fanta_volume_archive.override_images_page_map[page_str]), False

        return Path(self._fanta_volume_archive.archive_images_page_map[page_str]), True

    def _load_image_content(self, archive: ZipFile, page_info: PageInfo) -> tuple[io.BytesIO, str]:
        image_path, is_from_archive = self._get_image_path(page_info)
        ext = image_path.suffix

        logger.debug(
            f'Getting image (page = "{page_info.display_page_num}"): '
            f'image_path = "{image_path}", is_from_archive = {is_from_archive}.'
        )

        if is_from_archive:
            zip_path = zipfile.Path(archive, at=str(image_path))
            file_data = zip_path.read_bytes()
        elif page_info.srce_page.page_type in [PageType.BLANK_PAGE, PageType.TITLE]:
            file_data = self._empty_page_image
        else:  # it's an override
            zip_path = zipfile.Path(self._fanta_volume_archive.override_archive, at=str(image_path))
            file_data = zip_path.read_bytes()

        return self._get_image_data(file_data, ext, page_info)

    def _get_image_data(
        self, file_data: bytes, ext: str, page_info: PageInfo
    ) -> tuple[io.BytesIO, str]:
        pil_image = open_pil_image_from_bytes(file_data, ext)

        if self._fanta_volume_archive:
            pil_image = self._comic_book_image_builder.get_dest_page_image(
                pil_image, page_info.srce_page, page_info.dest_page
            )

        pil_image_resized = ImageOps.contain(
            pil_image,
            (self._max_window_width, self._max_window_height),
            PilImage.Resampling.LANCZOS,
        )

        return get_pil_image_as_png_bytes(pil_image_resized), PNG_EXT_FOR_KIVY
