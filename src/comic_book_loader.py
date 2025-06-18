import io
import logging
import os
import sys
import threading
import traceback
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Union, Callable, OrderedDict, IO, Tuple

from PIL import Image as PilImage, ImageOps
from kivy.clock import Clock

from barks_fantagraphics.comics_consts import PageType, PNG_FILE_EXT, JPG_FILE_EXT
from barks_fantagraphics.comics_utils import get_dest_comic_zip_file_stem
from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
from file_paths import get_the_comic_zips_dir


@dataclass
class PageInfo:
    page_index: int
    page_type: PageType
    image_filename: str


class ComicBookLoader:
    def __init__(
        self,
        on_first_image_loaded: Callable[[], None],
        on_all_images_loaded: Callable[[], None],
        max_window_width: int,
        max_window_height: int,
    ):
        self.__image_loaded_events: List[threading.Event] = []
        self.__image_load_order: List[str] = []
        self.__page_map: OrderedDict[str, PageInfo] = OrderedDict()
        self.__images: List[Union[None, Tuple[io.BytesIO, str]]] = []
        self.__max_window_width = max_window_width
        self.__max_window_height = max_window_height

        self.__stop = False
        self.__current_comic_path = ""

        self.__on_first_image_loaded: Callable[[], None] = on_first_image_loaded
        self.__on_all_images_loaded: Callable[[], None] = on_all_images_loaded

    def get_image_ready_for_reading(self, page_index: int) -> Tuple[io.BytesIO, str]:
        assert 0 <= page_index < len(self.__images)

        image_stream, image_ext = self.__images[page_index]
        assert image_stream

        image_stream.seek(0)  # Ensure stream is at the beginning for reading

        return image_stream, image_ext

    def get_load_event(self, page_index: int) -> threading.Event:
        assert 0 <= page_index < len(self.__images)
        return self.__image_loaded_events[page_index]

    def set_comic(
        self,
        fanta_info: FantaComicBookInfo,
        image_load_order: List[str],
        page_map: OrderedDict[str, PageInfo],
    ) -> None:
        assert len(image_load_order) == len(page_map)

        self.__current_comic_path = self.__get_comic_path(fanta_info)
        self.__image_load_order = image_load_order
        self.__page_map = page_map
        self.__stop = False

        self.init_load_events()

    @staticmethod
    def __get_comic_path(fanta_info: FantaComicBookInfo) -> str:
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
        self.__images = [None for _i in range(0, len(self.__page_map))]

        try:
            num_loaded = 0
            with zipfile.ZipFile(self.__current_comic_path, "r") as archive:
                first_loaded = False

                for i in range(0, len(self.__image_load_order)):
                    if self.__stop:
                        logging.warning("Image loading stopped.")
                        return

                    page_info = self.__page_map[self.__image_load_order[i]]

                    page_index = page_info.page_index
                    image_path_in_archive = Path("images") / page_info.image_filename

                    with archive.open(str(image_path_in_archive)) as file:
                        ext = image_path_in_archive.suffix
                        # Double check stop flag before heavy processing
                        if self.__stop:
                            logging.warning("Image loading stopped before processing file.")
                            return
                        self.__images[page_index] = self.__get_image_data(file, ext)
                        num_loaded += 1

                    self.__image_loaded_events[page_index].set()

                    if not first_loaded and not self.__stop:
                        first_loaded = True
                        logging.info(
                            f"Loaded first image,"
                            f' index = {page_index}, image_filename = "{image_path_in_archive}".'
                        )
                        Clock.schedule_once(lambda dt: self.__on_first_image_loaded(), 0)

            if self.__stop:
                logging.warning("Image loading stopped before completion.")
                return

            assert num_loaded == len(self.__page_map)
            assert all(ev.is_set() for ev in self.__image_loaded_events)
            logging.info(f'Loaded {num_loaded} images from "{self.__current_comic_path}".')

            Clock.schedule_once(lambda dt: self.__on_all_images_loaded(), 0)

        except FileNotFoundError:
            logging.error(f'Comic file not found: "{self.__current_comic_path}".')
        except zipfile.BadZipFile:
            logging.error(f'Bad zip file: "{self.__current_comic_path}".')
        except KeyError as ke:
            logging.error(
                f"Error accessing page_map or image_load_order, possibly due to stop/reset: {ke}"
            )
        except IndexError:
            if not self.__stop:
                logging.error(f'Unexpected index error reading comic: stop = "{self.__stop}".')
            else:
                logging.warning(
                    f'Index error reading comic: probably because stop = "{self.__stop}".'
                )
        except Exception as _e:
            _, _, tb = sys.exc_info()
            tb_info = traceback.extract_tb(tb)
            filename, line, func, text = tb_info[-1]
            logging.error(
                f'Error loading comic: "{_e}" at "{filename}:{line}" in "{func}" ({text}).'
            )

    @staticmethod
    def __get_pil_format_from_ext(ext: str) -> str:
        ext_lower = ext.lower()
        if ext_lower == JPG_FILE_EXT:  # e.g., ".jpg"
            return "JPEG"
        elif ext_lower == PNG_FILE_EXT:  # e.g., ".png"
            return "PNG"
        raise ValueError(f"Unsupported image extension for PIL: {ext}")

    def __get_image_data(self, file: IO[bytes], ext: str) -> Tuple[io.BytesIO, str]:
        # Ensure extension is one of the supported ones before proceeding
        assert ext.lower() in [PNG_FILE_EXT.lower(), JPG_FILE_EXT.lower()]

        pil_image = PilImage.open(io.BytesIO(file.read()))

        # Corrected parameters for ImageOps.contain: (width, height)
        pil_image_resized = ImageOps.contain(
            pil_image,
            (self.__max_window_width, self.__max_window_height),
            PilImage.Resampling.LANCZOS,
        )

        data = io.BytesIO()
        pil_format = self.__get_pil_format_from_ext(ext)
        pil_image_resized.save(data, format=pil_format)

        return data, ext[1:]
