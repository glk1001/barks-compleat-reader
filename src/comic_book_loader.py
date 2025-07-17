import io
import logging
import os
import sys
import threading
import traceback
import zipfile
from pathlib import Path
from typing import List, Union, Callable, OrderedDict, Tuple
from zipfile import ZipFile

from PIL import Image as PilImage, ImageOps
from kivy.clock import Clock

from barks_fantagraphics.comics_consts import PageType, PNG_FILE_EXT, JPG_FILE_EXT
from barks_fantagraphics.comics_utils import get_dest_comic_zip_file_stem, get_abbrev_path
from barks_fantagraphics.fanta_comics_info import (
    FantaComicBookInfo,
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
)
from barks_fantagraphics.pil_image_utils import open_pil_image_for_reading
from build_comic_images import ComicBookImageBuilder
from comic_book_page_info import PageInfo
from fantagraphics_volumes import FantagraphicsVolumeArchives, FantagraphicsArchive
from reader_settings import ReaderSettings
from reader_utils import is_blank_page, is_title_page, set_kivy_busy_cursor, set_kivy_normal_cursor

ALL_FANTA_VOLUMES = [i for i in range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)]
# ALL_FANTA_VOLUMES = [i for i in range(5, 7 + 1)]

_JPEG_PIL_FORMAT = "JPEG"
_PNG_PIL_FORMAT = "PNG"
_PNG_EXT_FOR_KIVY = _PNG_PIL_FORMAT.lower()
_EXTENSION_TO_PIL_FORMAT = {
    JPG_FILE_EXT: _JPEG_PIL_FORMAT,
    PNG_FILE_EXT: _PNG_PIL_FORMAT,
}


def _get_pil_format_from_ext(ext: str) -> str:
    try:
        return _EXTENSION_TO_PIL_FORMAT[ext.lower()]
    except KeyError:
        raise ValueError(f"Unsupported image extension for PIL: '{ext}'.")


class ComicBookLoader:
    def __init__(
        self,
        reader_settings: ReaderSettings,
        on_first_image_loaded: Callable[[], None],
        on_all_images_loaded: Callable[[], None],
        on_load_error: Callable[[bool], None],
        max_window_width: int,
        max_window_height: int,
    ):
        self._reader_settings = reader_settings
        self._use_fantagraphics_overrides = True
        self._sys_file_paths = self._reader_settings.sys_file_paths
        self._fanta_volume_archives: Union[FantagraphicsVolumeArchives, None] = None
        self._fanta_volume_archive: Union[FantagraphicsArchive, None] = None

        self._image_loaded_events: List[threading.Event] = []
        self._image_load_order: List[str] = []
        self._page_map: OrderedDict[str, PageInfo] = OrderedDict()
        self._images: List[Union[None, Tuple[io.BytesIO, str]]] = []
        self._max_window_width = max_window_width
        self._max_window_height = max_window_height

        self._stop = False
        self._current_comic_path = ""
        self._comic_book_image_builder: Union[ComicBookImageBuilder, None] = None

        self._on_first_image_loaded: Callable[[], None] = on_first_image_loaded
        self._on_all_images_loaded: Callable[[], None] = on_all_images_loaded
        self._on_load_error = on_load_error

        with open(self._sys_file_paths.get_empty_page_file(), "rb") as file:
            self.__empty_page_image = file.read()

        self._thread: Union[threading.Thread, None] = None

    def init_data(self) -> None:
        if self._reader_settings.use_prebuilt_archives:
            logging.info("Using prebuilt archives. No extra data to initialize.")
            self._fanta_volume_archives = None
        else:
            logging.info("Using Fantagraphics volume archives. Now loading volume info...")
            self._fanta_volume_archives = FantagraphicsVolumeArchives(
                self._reader_settings.fantagraphics_volumes_dir,
                self._sys_file_paths.get_barks_reader_fantagraphics_overrides_root_dir(),
                ALL_FANTA_VOLUMES,
            )
            self._fanta_volume_archives.load()

    def get_image_ready_for_reading(self, page_index: int) -> Tuple[io.BytesIO, str]:
        assert 0 <= page_index < len(self._images)

        image_stream, image_ext = self._images[page_index]
        assert image_stream

        image_stream.seek(0)  # Ensure stream is at the beginning for reading

        return image_stream, image_ext

    def get_image_info_str(self, page_str: str) -> str:
        page_info = self._page_map[page_str]
        image_path, is_from_archive = self._get_image_path(page_info)
        file_source = "from archive" if is_from_archive else "from override"

        return f'"{str(image_path)}" ({file_source})'

    def get_load_event(self, page_index: int) -> threading.Event:
        assert 0 <= page_index < len(self._images)
        return self._image_loaded_events[page_index]

    def set_comic(
        self,
        fanta_info: FantaComicBookInfo,
        use_fantagraphics_overrides: bool,
        comic_book_image_builder: ComicBookImageBuilder,
        image_load_order: List[str],
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

        self._use_fantagraphics_overrides = use_fantagraphics_overrides
        self._current_comic_path = self._get_comic_path(fanta_info)
        self._comic_book_image_builder = comic_book_image_builder
        self._image_load_order = image_load_order
        self._page_map = page_map
        self._stop = False

        logging.info(f"Archive source: {self._get_archive_source()}.")

        self._init_load_events()
        self._start_loading_thread()  # Start the thread automatically

    def close_comic(self) -> None:
        if not self._current_comic_path:
            return

        logging.debug(f'Close the comic: "{self._current_comic_path}".')

        # Signal the thread to stop and wait for it to finish before clearing resources
        self.stop_now()

        self._images.clear()
        self._image_loaded_events.clear()
        self._current_comic_path = ""

    def stop_now(self):
        """Signals the background thread to stop and waits for it to terminate."""
        if self._stop:  # Already stopping
            return

        self._stop = True

        if self._thread and self._thread.is_alive():
            logging.debug("Waiting for image loading thread to terminate...")
            self._thread.join(timeout=2.0)  # Wait for 2 seconds
            if self._thread.is_alive():
                logging.error("Image loading thread did not terminate in time.")

        self._thread = None

        set_kivy_normal_cursor()

    def _start_loading_thread(self):
        """Creates and starts the background thread for loading comic images."""
        if self._thread is not None and self._thread.is_alive():
            logging.warning("Load is already in progress.")
            return

        logging.debug(f'Starting comic load in background thread for: "{self._current_comic_path}"')
        self._thread = threading.Thread(target=self._load_comic_in_thread, daemon=True)
        self._thread.start()

    def _get_archive_source(self) -> str:
        archive_type = "Prebuilt" if not self._fanta_volume_archive else "Fantagraphics volumes"
        return f'{archive_type} - "{get_abbrev_path(self._current_comic_path)}"'

    def _get_comic_path(self, fanta_info: FantaComicBookInfo) -> str:
        if self._fanta_volume_archive:
            return self._fanta_volume_archive.archive_filename

        return self._get_prebuilt_comic_path(fanta_info)

    def _get_prebuilt_comic_path(self, fanta_info: FantaComicBookInfo) -> str:
        comic_file_stem = get_dest_comic_zip_file_stem(
            fanta_info.comic_book_info.get_title_str(),
            fanta_info.fanta_chronological_number,
            fanta_info.get_short_issue_title(),
        )

        comic_path = os.path.join(
            self._reader_settings.prebuilt_comics_dir, comic_file_stem + ".cbz"
        )
        if not comic_path.endswith((".cbz", ".zip")):
            raise Exception("Expected '.cbz' or '.zip' file.")
        if not os.path.isfile(comic_path):
            raise Exception(f'Could not find comic file "{comic_path}".')

        return comic_path

    def _init_load_events(self):
        self._image_loaded_events.clear()
        for _ in range(len(self._page_map)):
            self._image_loaded_events.append(threading.Event())

    def _load_comic_in_thread(self):
        logging.debug(f'Load comic: comic_path = "{self._current_comic_path}"')

        load_error = False
        load_warning_only = False
        set_kivy_busy_cursor()

        try:
            self._images = [None for _i in range(0, len(self._page_map))]

            try:
                num_loaded = 0
                with zipfile.ZipFile(self._current_comic_path, "r") as archive:
                    first_loaded = False

                    for i in range(0, len(self._image_load_order)):
                        if self._stop:
                            logging.warning(f"For i = {i}, image loading stopped.")
                            return

                        load_index = self._image_load_order[i]
                        logging.debug(f'For i = {i}, load_index = "{load_index}".')

                        page_info = self._page_map[load_index]
                        logging.debug(f"For i = {i}, page_info = {str(page_info)}.")

                        # Double check stop flag before any more heavy processing.
                        if self._stop:
                            logging.warning(
                                f"For i = {i}, image loading stopped before getting image."
                            )
                            return

                        page_index = page_info.page_index
                        # noinspection PyTypeChecker
                        self._images[page_index] = self._load_image_content(archive, page_info)
                        num_loaded += 1

                        self._image_loaded_events[page_index].set()

                        if not first_loaded and not self._stop:
                            first_loaded = True
                            logging.info(
                                f"Loaded first image,"
                                f" page index = {page_index},"
                                f" page = {page_info.display_page_num}."
                            )
                            Clock.schedule_once(lambda dt: self._on_first_image_loaded(), 0)

                if self._stop:
                    logging.warning(
                        "Image loading stopped before all images loaded."
                        f" Loaded {num_loaded} out of {len(self._page_map)} images."
                    )
                    return

                assert num_loaded == len(self._page_map)
                assert all(ev.is_set() for ev in self._image_loaded_events)
                logging.info(f'Loaded {num_loaded} images from "{self._current_comic_path}".')

                Clock.schedule_once(lambda dt: self._on_all_images_loaded(), 0)

            except FileNotFoundError:
                logging.error(f'Comic file not found: "{self._current_comic_path}".')
                load_error = True
            except zipfile.BadZipFile:
                logging.error(f'Bad zip file: "{self._current_comic_path}".')
                load_error = True
            except KeyError as ke:
                logging.error(
                    "Key error accessing page_map or image_load_order,"
                    f' possibly due to stop/reset: "{ke}"'
                )
                load_error = True
            except IndexError:
                if not self._stop:
                    logging.error(f'Unexpected index error reading comic: stop = "{self._stop}".')
                else:
                    logging.warning(
                        f'Index error reading comic: probably because stop = "{self._stop}".'
                    )
                    load_warning_only = True
                    load_error = True
            except Exception as _e:
                _, _, tb = sys.exc_info()
                tb_info = traceback.extract_tb(tb)
                filename, line, func, text = tb_info[-1]
                logging.error(
                    f'Error loading comic: "{_e}" at "{filename}:{line}" in "{func}" ({text}).'
                )
                load_error = True

        finally:
            set_kivy_normal_cursor()
            if load_error:
                self._close_and_report_load_error(load_warning_only)

    def _close_and_report_load_error(self, load_warning_only: bool) -> None:
        self._stop = True
        self.close_comic()
        Clock.schedule_once(lambda dt: self._on_load_error(load_warning_only), 0)

    def _get_image_path(self, page_info: PageInfo) -> Tuple[Path, bool]:
        """
        Determines the path to an image file for a given page.

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

    def _get_fanta_volume_image_path(self, page_info: PageInfo) -> Tuple[Path, bool]:
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

    def _load_image_content(self, archive: ZipFile, page_info: PageInfo) -> Tuple[io.BytesIO, str]:
        image_path, is_from_archive = self._get_image_path(page_info)
        ext = image_path.suffix

        if is_from_archive:
            with archive.open(str(image_path), "r") as file:
                file_data = file.read()
        elif page_info.srce_page.page_type in [PageType.BLANK_PAGE, PageType.TITLE]:
            file_data = self.__empty_page_image
        else:  # it's a file
            with open(image_path, "rb") as file:
                file_data = file.read()

        image_data = self._get_image_data(file_data, ext, page_info)

        logging.debug(
            f'Getting image (page = "{page_info.display_page_num}"): '
            f'image_path = "{image_path}", is_from_archive = {is_from_archive}.'
        )

        return image_data

    def _get_image_data(
        self, file_data: bytes, ext: str, page_info: PageInfo
    ) -> Tuple[io.BytesIO, str]:
        pil_image = open_pil_image_for_reading(
            io.BytesIO(file_data), [_get_pil_format_from_ext(ext)]
        )

        if self._fanta_volume_archive:
            pil_image = self._comic_book_image_builder.get_dest_page_image(
                pil_image, page_info.srce_page, page_info.dest_page
            )

        pil_image_resized = ImageOps.contain(
            pil_image,
            (self._max_window_width, self._max_window_height),
            PilImage.Resampling.LANCZOS,
        )

        data = io.BytesIO()
        pil_image_resized.save(data, format=_PNG_PIL_FORMAT)

        return data, _PNG_EXT_FOR_KIVY
