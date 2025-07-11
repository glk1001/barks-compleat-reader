import logging
import os
from enum import Enum, auto
from pathlib import Path
from typing import List, Tuple

from barks_fantagraphics.barks_titles import (
    Titles,
    BARKS_TITLE_INFO,
    BARKS_TITLES,
    BARKS_TITLE_DICT,
)
from barks_fantagraphics.comics_consts import JPG_FILE_EXT, PNG_FILE_EXT
from file_paths import BARKS_DIR

EDITED_SUBDIR = "edited"

THE_COMICS_DIR = os.path.join(BARKS_DIR, "The Comics")
DEFAULT_BARKS_READER_FILES_DIR = os.path.join(BARKS_DIR, "Compleat Barks Disney Reader")

DEFAULT_THE_COMIC_ZIPS_DIR = os.path.join(THE_COMICS_DIR, "Chronological")
DEFAULT_FANTA_VOLUME_ARCHIVES_ROOT_DIR = "/mnt/2tb_drive/Books/Carl Barks/Fantagraphics Volumes"
DEFAULT_JPG_BARKS_PANELS_DIR = os.path.join(DEFAULT_BARKS_READER_FILES_DIR, "Barks Panels")
DEFAULT_PNG_BARKS_PANELS_DIR = os.path.join(BARKS_DIR, "Barks Panels Pngs")

EMERGENCY_INSET_FILE = Titles.BICEPS_BLUES


class BarksPanelsExtType(Enum):
    JPG = auto()
    MOSTLY_PNG = auto()


class ReaderFilePaths:
    def __init__(self):
        self.__barks_reader_files_dir = ""
        self.__reader_icon_files_dir = ""
        self.__app_icon_path = ""

        self.__barks_panels_dir = ""
        self.__cover_files_dir = ""
        self.__silhouette_files_dir = ""
        self.__splash_files_dir = ""
        self.__censorship_files_dir = ""
        self.__favourite_files_dir = ""
        self.__original_art_files_dir = ""
        self.__search_files_dir = ""
        self.__nontitle_files_dir = ""
        self.__inset_files_dir = ""
        self.__inset_edited_files_dir = ""

        self.__inset_files_ext = ""
        self.__edited_files_ext = ""

        self.__panels_ext_type = None

    def set_barks_panels_dir(self, panels_dir: str, ext_type: BarksPanelsExtType) -> None:
        self.__barks_panels_dir = panels_dir
        self.__panels_ext_type = ext_type

        self.__cover_files_dir = os.path.join(self.__barks_panels_dir, "Covers")
        self.__silhouette_files_dir = os.path.join(self.__barks_panels_dir, "Silhouettes")
        self.__splash_files_dir = os.path.join(self.__barks_panels_dir, "Splash")
        self.__censorship_files_dir = os.path.join(self.__barks_panels_dir, "Censorship")
        self.__favourite_files_dir = os.path.join(self.__barks_panels_dir, "Favourites")
        self.__original_art_files_dir = os.path.join(self.__barks_panels_dir, "Original Art")
        self.__search_files_dir = os.path.join(self.__barks_panels_dir, "Search")
        self.__nontitle_files_dir = os.path.join(self.__barks_panels_dir, "Nontitles")
        self.__inset_files_dir = os.path.join(self.__barks_panels_dir, "Insets")
        self.__inset_edited_files_dir = os.path.join(self.__inset_files_dir, EDITED_SUBDIR)

        self.__check_panels_dirs()

        self.__inset_files_ext = (
            JPG_FILE_EXT if self.__panels_ext_type == BarksPanelsExtType.JPG else PNG_FILE_EXT
        )
        self.__edited_files_ext = (
            JPG_FILE_EXT if self.__panels_ext_type == BarksPanelsExtType.JPG else PNG_FILE_EXT
        )

    def __check_panels_dirs(self) -> None:
        dirs_to_check = [
            self.__barks_panels_dir,
            self.__cover_files_dir,
            self.__silhouette_files_dir,
            self.__splash_files_dir,
            self.__censorship_files_dir,
            self.__favourite_files_dir,
            self.__original_art_files_dir,
            self.__search_files_dir,
            self.__nontitle_files_dir,
            self.__inset_files_dir,
            self.__inset_edited_files_dir,
        ]

        self.__check_dirs(dirs_to_check)

    @staticmethod
    def __check_dirs(dirs_to_check: List[str]) -> None:
        for dir_path in dirs_to_check:
            if not os.path.isdir(dir_path):
                raise FileNotFoundError(f'Required directory not found: "{dir_path}".')

    @staticmethod
    def __check_files(files_to_check: List[str]) -> None:
        for file_path in files_to_check:
            if not os.path.isfile(file_path):
                raise FileNotFoundError(f'Required file not found: "{file_path}".')

    def get_inset_file_ext(self) -> str:
        return self.__inset_files_ext

    def get_emergency_inset_file(self) -> str:
        return os.path.join(
            self.__inset_files_dir,
            BARKS_TITLE_INFO[EMERGENCY_INSET_FILE].get_title_str() + self.__inset_files_ext,
        )

    @staticmethod
    def get_default_png_barks_panels_dir() -> str:
        return DEFAULT_PNG_BARKS_PANELS_DIR

    @staticmethod
    def get_default_jpg_barks_panels_dir() -> str:
        return DEFAULT_JPG_BARKS_PANELS_DIR

    @staticmethod
    def get_default_prebuilt_comic_zips_dir() -> str:
        return DEFAULT_THE_COMIC_ZIPS_DIR

    @staticmethod
    def get_default_fanta_volume_archives_root_dir() -> str:
        return DEFAULT_FANTA_VOLUME_ARCHIVES_ROOT_DIR

    def get_comic_inset_files_dir(self) -> str:
        return self.__inset_files_dir

    def get_comic_cover_files_dir(self) -> str:
        return self.__cover_files_dir

    def get_comic_silhouette_files_dir(self) -> str:
        return self.__silhouette_files_dir

    def get_comic_splash_files_dir(self) -> str:
        return self.__splash_files_dir

    def get_comic_censorship_files_dir(self) -> str:
        return self.__censorship_files_dir

    def get_comic_favourite_files_dir(self) -> str:
        return self.__favourite_files_dir

    def get_comic_original_art_files_dir(self) -> str:
        return self.__original_art_files_dir

    def get_comic_search_files_dir(self) -> str:
        return self.__search_files_dir

    def get_nontitle_files_dir(self) -> str:
        return self.__nontitle_files_dir

    def get_barks_reader_app_icon_file(self) -> str:
        return self.__app_icon_path

    def get_comic_inset_file(self, title: Titles, use_edited_only: bool = False) -> str:
        title_str = BARKS_TITLES[title]

        if use_edited_only:
            edited_file = os.path.join(
                self.__inset_edited_files_dir, title_str + self.__inset_files_ext
            )
            if os.path.isfile(edited_file):
                return edited_file
            logging.debug(f'No edited inset file "{edited_file}".')

        main_file = os.path.join(self.__inset_files_dir, title_str + self.__inset_files_ext)
        # TODO: Fix this when all titles are configured.
        # assert os.path.isfile(edited_file)
        if os.path.isfile(main_file):
            return main_file

        return self.get_emergency_inset_file()

    def get_comic_inset_files(self, title_str: str, use_edited_only: bool = False) -> List[str]:
        title = BARKS_TITLE_DICT[title_str]

        inset_list = [self.get_comic_inset_file(title, use_edited_only)]
        if use_edited_only:
            return inset_list

        main_inset_file = self.get_comic_inset_file(title, False)
        if main_inset_file not in inset_list:
            inset_list.append(main_inset_file)

        return inset_list

    def get_comic_cover_file(self, title: str, use_edited_only: bool = False) -> str:
        if use_edited_only:
            edited_file = os.path.join(
                self.get_comic_cover_files_dir(), EDITED_SUBDIR, title + self.__edited_files_ext
            )
            if os.path.isfile(edited_file):
                return edited_file

        cover_file = os.path.join(self.get_comic_cover_files_dir(), title + JPG_FILE_EXT)
        if not os.path.isfile(cover_file):
            return ""

        return cover_file

    def get_comic_silhouette_files(self, title: str, use_edited_only: bool = False) -> List[str]:
        return self.__get_files(self.get_comic_silhouette_files_dir(), title, use_edited_only)

    def get_comic_splash_files(self, title: str, use_edited_only: bool = False) -> List[str]:
        return self.__get_files(self.get_comic_splash_files_dir(), title, use_edited_only)

    def get_comic_censorship_files(self, title: str, use_edited_only: bool = False) -> List[str]:
        return self.__get_files(self.get_comic_censorship_files_dir(), title, use_edited_only)

    def get_comic_favourite_files(self, title: str, use_edited_only: bool = False) -> List[str]:
        return self.__get_files(self.get_comic_favourite_files_dir(), title, use_edited_only)

    def get_comic_original_art_files(self, title: str, use_edited_only: bool = False) -> List[str]:
        return self.__get_files(self.get_comic_original_art_files_dir(), title, use_edited_only)

    def get_comic_search_files(self, title: str, use_edited_only: bool = False) -> List[str]:
        return self.__get_files(self.get_comic_search_files_dir(), title, use_edited_only)

    def get_nontitle_files(self) -> List[str]:
        return self.__get_all_files(self.get_nontitle_files_dir())

    def __get_files(self, parent_image_dir: str, title: str, use_edited_only: bool) -> List[str]:
        image_dir = os.path.join(parent_image_dir, title)
        if not os.path.isdir(image_dir):
            return list()

        image_files = []

        edited_image_dir = os.path.join(image_dir, EDITED_SUBDIR)
        if os.path.isdir(edited_image_dir):
            image_files = self.__get_all_files(edited_image_dir)
            if use_edited_only and image_files:
                # Don't want any unedited images.
                return image_files

        image_files.extend(self.__get_all_files(image_dir))

        return image_files

    @staticmethod
    def __get_all_files(image_dir: str) -> List[str]:
        image_files = []
        for file in os.listdir(image_dir):
            image_file = os.path.join(image_dir, file)
            if os.path.isfile(image_file):
                image_files.append(image_file)

        return image_files

    def get_edited_version_if_possible(self, image_file: str) -> Tuple[str, bool]:
        dir_path = os.path.dirname(image_file)
        edited_image_file = os.path.join(
            dir_path, EDITED_SUBDIR, Path(image_file).stem + self.__edited_files_ext
        )
        if os.path.isfile(edited_image_file):
            return edited_image_file, True

        return image_file, False
