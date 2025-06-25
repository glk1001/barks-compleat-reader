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
from barks_fantagraphics.comics_utils import get_dest_comic_zip_file_stem
from barks_fantagraphics.fanta_comics_info import (
    FantaComicBookInfo,
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
)
from barks_fantagraphics.pil_image_utils import open_pil_image_for_reading
from build_comic_images import ComicBookImageBuilder
from comic_book_page_info import PageInfo
from fantagraphics_volumes import FantagraphicsVolumeArchives, FantagraphicsArchive
from file_paths import (
    get_the_comic_zips_dir,
    get_fanta_volume_archives_root_dir,
    get_empty_page_file,
)
from reader_utils import is_blank_page, is_title_page

FANTA_VOLUME_OVERRIDES_ROOT = "/mnt/2tb_drive/Books/Carl Barks/Fantagraphics Volumes Overrides"
ALL_FANTA_VOLUMES = [i for i in range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)]
# ALL_FANTA_VOLUMES = [i for i in range(5, 7 + 1)]


class ComicBookLoader:
    def __init__(
        self,
        on_first_image_loaded: Callable[[], None],
        on_all_images_loaded: Callable[[], None],
        on_load_error: Callable[[bool], None],
        max_window_width: int,
        max_window_height: int,
    ):
        self.__use_prebuilt_archives = False

        if self.__use_prebuilt_archives:
            self.__fanta_volume_archives = None
        else:
            self.__fanta_volume_archives = FantagraphicsVolumeArchives(
                get_fanta_volume_archives_root_dir(), FANTA_VOLUME_OVERRIDES_ROOT, ALL_FANTA_VOLUMES
            )

        self.__image_loaded_events: List[threading.Event] = []
        self.__image_load_order: List[str] = []
        self.__page_map: OrderedDict[str, PageInfo] = OrderedDict()
        self.__images: List[Union[None, Tuple[io.BytesIO, str]]] = []
        self.__max_window_width = max_window_width
        self.__max_window_height = max_window_height

        self.__stop = False
        self.__current_comic_path = ""
        self.__comic_book_image_builder: Union[ComicBookImageBuilder, None] = None
        self.__fanta_volume_archive: Union[FantagraphicsArchive, None] = None

        self.__on_first_image_loaded: Callable[[], None] = on_first_image_loaded
        self.__on_all_images_loaded: Callable[[], None] = on_all_images_loaded
        self.__on_load_error = on_load_error

        with open(get_empty_page_file(), "rb") as file:
            self.__empty_page_image = file.read()

    def load_data(self) -> None:
        if self.__use_prebuilt_archives:
            logging.debug("Using prebuilt archives. No extra data to load.")
            return

        logging.debug("Using Fantagraphics volume archives.")
        self.__fanta_volume_archives.load()

    def get_image_ready_for_reading(self, page_index: int) -> Tuple[io.BytesIO, str]:
        assert 0 <= page_index < len(self.__images)

        image_stream, image_ext = self.__images[page_index]
        assert image_stream

        image_stream.seek(0)  # Ensure stream is at the beginning for reading

        return image_stream, image_ext

    def get_image_info_str(self, page_str: str) -> str:
        page_info = self.__page_map[page_str]
        image_path, is_from_archive = self.__get_image_path(page_info)
        file_source = "from archive" if is_from_archive else "from override"

        return f'"{str(image_path)}" ({file_source})'

    def get_load_event(self, page_index: int) -> threading.Event:
        assert 0 <= page_index < len(self.__images)
        return self.__image_loaded_events[page_index]

    def set_comic(
        self,
        fanta_info: FantaComicBookInfo,
        comic_book_image_builder: ComicBookImageBuilder,
        image_load_order: List[str],
        page_map: OrderedDict[str, PageInfo],
    ) -> None:
        assert len(image_load_order) == len(page_map)

        if not self.__use_prebuilt_archives:
            self.__fanta_volume_archive = self.__fanta_volume_archives.get_fantagraphics_archive(
                int(fanta_info.fantagraphics_volume[-2:])
            )

        self.__current_comic_path = self.__get_comic_path(fanta_info)
        self.__comic_book_image_builder = comic_book_image_builder
        self.__image_load_order = image_load_order
        self.__page_map = page_map
        self.__stop = False

        self.init_load_events()

    def __get_comic_path(self, fanta_info: FantaComicBookInfo) -> str:
        if not self.__use_prebuilt_archives:
            return self.__fanta_volume_archive.archive_filename

        comic_file_stem = get_dest_comic_zip_file_stem(
            fanta_info.comic_book_info.get_title_str(),
            fanta_info.fanta_chronological_number,
            fanta_info.get_short_issue_title(),
        )

        comic_path = os.path.join(get_the_comic_zips_dir(), comic_file_stem + ".cbz")
        if not comic_path.endswith((".cbz", ".zip")):
            raise Exception("Expected '.cbz' or '.zip' file.")
        if not os.path.isfile(comic_path):
            raise Exception(f'Could not find comic file "{comic_path}".')

        return comic_path

    def close_comic(self) -> None:
        if not self.__current_comic_path:
            return

        logging.debug(f'Close the comic: "{self.__current_comic_path}".')

        self.__images.clear()
        self.__image_loaded_events.clear()
        self.__image_load_order.clear()
        self.__page_map.clear()
        self.__current_comic_path = ""

    def stop_now(self):
        self.__stop = True

    def init_load_events(self):
        self.__image_loaded_events.clear()
        for _ in range(len(self.__page_map)):
            self.__image_loaded_events.append(threading.Event())

    def load_comic(self):
        logging.debug(f'Load comic: comic_path = "{self.__current_comic_path}"')

        self.__images = [None for _i in range(0, len(self.__page_map))]

        load_error = False
        load_warning_only = False
        try:
            num_loaded = 0
            with zipfile.ZipFile(self.__current_comic_path, "r") as archive:
                first_loaded = False

                for i in range(0, len(self.__image_load_order)):
                    if self.__stop:
                        logging.warning(f"For i = {i}, image loading stopped.")
                        return

                    load_index = self.__image_load_order[i]
                    logging.debug(f'For i = {i}, load_index = "{load_index}".')

                    page_info = self.__page_map[load_index]
                    logging.debug(f"For i = {i}, page_info = {str(page_info)}.")

                    # Double check stop flag before any more heavy processing.
                    if self.__stop:
                        logging.warning(f"For i = {i}, image loading stopped before getting image.")
                        return

                    page_index = page_info.page_index
                    # noinspection PyTypeChecker
                    self.__images[page_index] = self.__load_image_content(archive, page_info)
                    num_loaded += 1

                    self.__image_loaded_events[page_index].set()

                    if not first_loaded and not self.__stop:
                        first_loaded = True
                        logging.info(
                            f"Loaded first image,"
                            f" page index = {page_index},"
                            f" page = {page_info.display_page_num}."
                        )
                        Clock.schedule_once(lambda dt: self.__on_first_image_loaded(), 0)

            if self.__stop:
                logging.warning(
                    "Image loading stopped before all images loaded."
                    f" Loaded {num_loaded} out of {len(self.__page_map)} images."
                )
                return

            assert num_loaded == len(self.__page_map)
            assert all(ev.is_set() for ev in self.__image_loaded_events)
            logging.info(f'Loaded {num_loaded} images from "{self.__current_comic_path}".')

            Clock.schedule_once(lambda dt: self.__on_all_images_loaded(), 0)

        except FileNotFoundError:
            logging.error(f'Comic file not found: "{self.__current_comic_path}".')
            load_error = True
        except zipfile.BadZipFile:
            logging.error(f'Bad zip file: "{self.__current_comic_path}".')
        except KeyError as ke:
            logging.error(
                "Key error accessing page_map or image_load_order,"
                f' possibly due to stop/reset: "{ke}"'
            )
            load_error = True
        except IndexError:
            if not self.__stop:
                logging.error(f'Unexpected index error reading comic: stop = "{self.__stop}".')
            else:
                logging.warning(
                    f'Index error reading comic: probably because stop = "{self.__stop}".'
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

        if load_error:
            self.__close_and_report_load_error(load_warning_only)

    def __close_and_report_load_error(self, load_warning_only: bool) -> None:
        self.__stop = True
        self.close_comic()
        Clock.schedule_once(lambda dt: self.__on_load_error(load_warning_only), 0)

    def __get_image_path(self, page_info: PageInfo) -> Tuple[Path, bool]:
        if self.__use_prebuilt_archives:
            return Path("images") / page_info.dest_page.page_filename, True

        if is_title_page(page_info.srce_page) or is_blank_page(
            page_info.srce_page.page_filename, page_info.page_type
        ):
            return Path(get_empty_page_file()), False

        page_str = Path(page_info.srce_page.page_filename).stem

        if page_str in self.__fanta_volume_archive.extra_images_page_map:
            return Path(self.__fanta_volume_archive.extra_images_page_map[page_str]), False

        if page_str in self.__fanta_volume_archive.override_images_page_map:
            return Path(self.__fanta_volume_archive.override_images_page_map[page_str]), False

        return Path(self.__fanta_volume_archive.archive_images_page_map[page_str]), True

    def __load_image_content(self, archive: ZipFile, page_info: PageInfo) -> Tuple[io.BytesIO, str]:
        image_path, is_from_archive = self.__get_image_path(page_info)
        ext = image_path.suffix

        if is_from_archive:
            with archive.open(str(image_path), "r") as file:
                file_data = file.read()
        elif page_info.srce_page.page_type in [PageType.BLANK_PAGE, PageType.TITLE]:
            file_data = self.__empty_page_image
        else:
            with open(image_path, "rb") as file:
                file_data = file.read()

        image_data = self.__get_image_data(file_data, ext, page_info)

        logging.debug(
            f'Getting image (page = "{page_info.display_page_num}"): '
            f'image_path = "{image_path}", is_from_archive = {is_from_archive}.'
        )

        return image_data

    def __get_image_data(
        self, file_data: bytes, ext: str, page_info: PageInfo
    ) -> Tuple[io.BytesIO, str]:
        pil_image = open_pil_image_for_reading(io.BytesIO(file_data))

        if not self.__use_prebuilt_archives:
            pil_image = self.__comic_book_image_builder.get_dest_page_image(
                pil_image, page_info.srce_page, page_info.dest_page
            )

        pil_image_resized = ImageOps.contain(
            pil_image,
            (self.__max_window_width, self.__max_window_height),
            PilImage.Resampling.LANCZOS,
        )

        data = io.BytesIO()
        pil_format = self.__get_pil_format_from_ext(ext)
        pil_image_resized.save(data, format=pil_format)

        return data, ext[1:]

    @staticmethod
    def __get_pil_format_from_ext(ext: str) -> str:
        ext_lower = ext.lower()
        if ext_lower == JPG_FILE_EXT:  # e.g., ".jpg"
            return "JPEG"
        elif ext_lower == PNG_FILE_EXT:  # e.g., ".png"
            return "PNG"
        raise ValueError(f"Unsupported image extension for PIL: {ext}")
