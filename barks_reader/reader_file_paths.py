# ruff: noqa: ERA001

from __future__ import annotations

import logging
import os
from enum import Enum, auto
from pathlib import Path

from barks_fantagraphics.barks_titles import (
    BARKS_TITLE_DICT,
    BARKS_TITLE_INFO,
    BARKS_TITLES,
    Titles,
)
from barks_fantagraphics.comics_consts import JPG_FILE_EXT, PNG_FILE_EXT

from barks_reader.reader_utils import get_all_files_in_dir

HOME_DIR = Path(os.environ.get("HOME"))
BARKS_DIR = HOME_DIR / "Books" / "Carl Barks"
DEFAULT_BARKS_READER_FILES_DIR = BARKS_DIR / "Compleat Barks Disney Reader"
EMERGENCY_INSET_FILE = Titles.BICEPS_BLUES

_THE_COMICS_DIR = BARKS_DIR / "The Comics"

_DEFAULT_THE_COMIC_ZIPS_DIR = _THE_COMICS_DIR / "Chronological"
_DEFAULT_FANTA_VOLUME_ARCHIVES_ROOT_DIR = Path(
    "/mnt/2tb_drive/Books/Carl Barks/Fantagraphics Volumes"
)
_DEFAULT_JPG_BARKS_PANELS_DIR = DEFAULT_BARKS_READER_FILES_DIR / "Barks Panels"
_DEFAULT_PNG_BARKS_PANELS_DIR = BARKS_DIR / "Barks Panels Pngs"

_EDITED_SUBDIR = "edited"


class BarksPanelsExtType(Enum):
    JPG = auto()
    MOSTLY_PNG = auto()


class ReaderFilePaths:
    def __init__(self) -> None:
        self._barks_reader_files_dir: Path | None = None
        self._reader_icon_files_dir: Path | None = None
        self._app_icon_path: Path | None = None

        self._barks_panels_dir: Path | None = None
        self._bw_files_dir: Path | None = None
        self._censorship_files_dir: Path | None = None
        self._cover_files_dir: Path | None = None
        self._favourite_files_dir: Path | None = None
        self._inset_files_dir: Path | None = None
        self._inset_edited_files_dir: Path | None = None
        self._nontitle_files_dir: Path | None = None
        self._original_art_files_dir: Path | None = None
        self._search_files_dir: Path | None = None
        self._silhouette_files_dir: Path | None = None
        self._splash_files_dir: Path | None = None

        self._inset_files_ext = ""
        self._edited_files_ext = ""

        self._panels_ext_type = None

    def set_barks_panels_dir(self, panels_dir: Path, ext_type: BarksPanelsExtType) -> None:
        self._barks_panels_dir = panels_dir
        self._panels_ext_type = ext_type

        self._bw_files_dir = self._barks_panels_dir / "BW"
        self._censorship_files_dir = self._barks_panels_dir / "Censorship"
        self._cover_files_dir = self._barks_panels_dir / "Covers"
        self._favourite_files_dir = self._barks_panels_dir / "Favourites"
        self._inset_files_dir = self._barks_panels_dir / "Insets"
        self._inset_edited_files_dir = self._inset_files_dir / _EDITED_SUBDIR
        self._nontitle_files_dir = self._barks_panels_dir / "Nontitles"
        self._original_art_files_dir = self._barks_panels_dir / "Original Art"
        self._search_files_dir = self._barks_panels_dir / "Search"
        self._silhouette_files_dir = self._barks_panels_dir / "Silhouettes"
        self._splash_files_dir = self._barks_panels_dir / "Splash"

        self._check_panels_dirs()

        self._inset_files_ext = (
            JPG_FILE_EXT if self._panels_ext_type == BarksPanelsExtType.JPG else PNG_FILE_EXT
        )
        self._edited_files_ext = (
            JPG_FILE_EXT if self._panels_ext_type == BarksPanelsExtType.JPG else PNG_FILE_EXT
        )

    def _check_panels_dirs(self) -> None:
        dirs_to_check = [
            self._barks_panels_dir,
            self._bw_files_dir,
            self._cover_files_dir,
            self._censorship_files_dir,
            self._favourite_files_dir,
            self._inset_files_dir,
            self._inset_edited_files_dir,
            self._nontitle_files_dir,
            self._original_art_files_dir,
            self._search_files_dir,
            self._silhouette_files_dir,
            self._splash_files_dir,
        ]

        self._check_dirs(dirs_to_check)

    @staticmethod
    def _check_dirs(dirs_to_check: list[Path]) -> None:
        for dir_path in dirs_to_check:
            if not dir_path.is_dir():
                msg = f'Required directory not found: "{dir_path}".'
                raise FileNotFoundError(msg)

    @staticmethod
    def _check_files(files_to_check: list[Path]) -> None:
        for file_path in files_to_check:
            if not file_path.is_file():
                msg = f'Required file not found: "{file_path}".'
                raise FileNotFoundError(msg)

    def get_inset_file_ext(self) -> str:
        return self._inset_files_ext

    def get_emergency_inset_file(self) -> Path:
        return self._inset_files_dir / (
            BARKS_TITLE_INFO[EMERGENCY_INSET_FILE].get_title_str() + self._inset_files_ext
        )

    @staticmethod
    def get_default_png_barks_panels_dir() -> Path:
        return _DEFAULT_PNG_BARKS_PANELS_DIR

    @staticmethod
    def get_default_jpg_barks_panels_dir() -> Path:
        return _DEFAULT_JPG_BARKS_PANELS_DIR

    @staticmethod
    def get_default_prebuilt_comic_zips_dir() -> Path:
        return _DEFAULT_THE_COMIC_ZIPS_DIR

    @staticmethod
    def get_default_fanta_volume_archives_root_dir() -> Path:
        return _DEFAULT_FANTA_VOLUME_ARCHIVES_ROOT_DIR

    def get_comic_bw_files_dir(self) -> Path:
        return self._bw_files_dir

    def get_comic_cover_files_dir(self) -> Path:
        return self._cover_files_dir

    def get_comic_censorship_files_dir(self) -> Path:
        return self._censorship_files_dir

    def get_comic_favourite_files_dir(self) -> Path:
        return self._favourite_files_dir

    def get_comic_inset_files_dir(self) -> Path:
        return self._inset_files_dir

    def get_nontitle_files_dir(self) -> Path:
        return self._nontitle_files_dir

    def get_comic_original_art_files_dir(self) -> Path:
        return self._original_art_files_dir

    def get_comic_search_files_dir(self) -> Path:
        return self._search_files_dir

    def get_comic_silhouette_files_dir(self) -> Path:
        return self._silhouette_files_dir

    def get_comic_splash_files_dir(self) -> Path:
        return self._splash_files_dir

    def get_barks_reader_app_icon_file(self) -> Path:
        return self._app_icon_path

    def get_comic_inset_file(self, title: Titles, use_edited_only: bool = False) -> Path:
        title_str = BARKS_TITLES[title]

        if use_edited_only:
            edited_file = self._inset_edited_files_dir / (title_str + self._inset_files_ext)
            if edited_file.is_file():
                return edited_file
            logging.debug(f'No edited inset file "{edited_file}".')

        main_file = self._inset_files_dir / (title_str + self._inset_files_ext)
        # TODO: Fix this when all titles are configured.
        # assert os.path.isfile(edited_file)
        if main_file.is_file():
            return main_file

        return self.get_emergency_inset_file()

    def get_comic_inset_files(self, title_str: str, use_edited_only: bool = False) -> list[Path]:
        title = BARKS_TITLE_DICT[title_str]

        inset_list = [self.get_comic_inset_file(title, use_edited_only)]
        if use_edited_only:
            return inset_list

        main_inset_file = self.get_comic_inset_file(title, use_edited_only=False)
        if main_inset_file not in inset_list:
            inset_list.append(main_inset_file)

        return inset_list

    def get_comic_cover_file(self, title: str, use_edited_only: bool = False) -> Path | None:
        if use_edited_only:
            edited_file = (
                self.get_comic_cover_files_dir() / _EDITED_SUBDIR / (title + self._edited_files_ext)
            )
            if edited_file.is_file():
                return edited_file

        cover_file = self.get_comic_cover_files_dir() / (title + JPG_FILE_EXT)
        if not cover_file.is_file():
            return None

        return cover_file

    def get_comic_bw_files(self, title: str, use_edited_only: bool = False) -> list[Path]:
        return self._get_files(self.get_comic_bw_files_dir(), title, use_edited_only)

    def get_comic_censorship_files(self, title: str, use_edited_only: bool = False) -> list[Path]:
        return self._get_files(self.get_comic_censorship_files_dir(), title, use_edited_only)

    def get_comic_favourite_files(self, title: str, use_edited_only: bool = False) -> list[Path]:
        return self._get_files(self.get_comic_favourite_files_dir(), title, use_edited_only)

    def get_nontitle_files(self) -> list[Path]:
        return self._get_all_files(self.get_nontitle_files_dir())

    def get_comic_original_art_files(self, title: str, use_edited_only: bool = False) -> list[Path]:
        return self._get_files(self.get_comic_original_art_files_dir(), title, use_edited_only)

    def get_comic_search_files(self, title: str, use_edited_only: bool = False) -> list[Path]:
        return self._get_files(self.get_comic_search_files_dir(), title, use_edited_only)

    def get_comic_silhouette_files(self, title: str, use_edited_only: bool = False) -> list[Path]:
        return self._get_files(self.get_comic_silhouette_files_dir(), title, use_edited_only)

    def get_comic_splash_files(self, title: str, use_edited_only: bool = False) -> list[Path]:
        return self._get_files(self.get_comic_splash_files_dir(), title, use_edited_only)

    def _get_files(self, parent_image_dir: Path, title: str, use_edited_only: bool) -> list[Path]:
        image_dir = parent_image_dir / title
        if not image_dir.is_dir():
            return []

        image_files = []

        edited_image_dir = image_dir / _EDITED_SUBDIR
        if edited_image_dir.is_dir():
            image_files = self._get_all_files(edited_image_dir)
            if use_edited_only and image_files:
                # Don't want any unedited images.
                return image_files

        image_files.extend(self._get_all_files(image_dir))

        return image_files

    @staticmethod
    def _get_all_files(image_dir: Path) -> list[Path]:
        return get_all_files_in_dir(image_dir)

    def get_edited_version_if_possible(self, image_file: Path) -> tuple[Path, bool]:
        dir_path = image_file.parent
        edited_image_file = dir_path / _EDITED_SUBDIR / (image_file.stem + self._edited_files_ext)
        if edited_image_file.is_file():
            return edited_image_file, True

        return image_file, False
