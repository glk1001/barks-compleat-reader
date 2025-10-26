# ruff: noqa: ERA001

from __future__ import annotations

import os
import zipfile
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import (
    BARKS_TITLE_DICT,
    BARKS_TITLE_INFO,
    Titles,
    get_filename_from_title,
    get_title_str_from_filename,
)
from comic_utils.comic_consts import JPG_FILE_EXT, PNG_FILE_EXT, ZIP_FILE_EXT
from loguru import logger

from barks_reader.reader_consts_and_types import NO_OVERRIDES_SUFFIX, PanelPath
from barks_reader.reader_utils import get_all_files_in_dir

if TYPE_CHECKING:
    from collections.abc import Callable

EMERGENCY_INSET_FILE = Titles.BICEPS_BLUES

_DEFAULT_THE_COMIC_ZIPS_DIR = "${HOME}/Books/Carl Barks/The Comics/Chronological"
_DEFAULT_JPG_BARKS_PANELS_SOURCE = "${HOME}/.local/share/barks-reader/Reader Files/Barks Panels.zip"
_DEFAULT_PNG_BARKS_PANELS_SOURCE = "${HOME}/Books/Carl Barks/Barks Panels Pngs"

EDITED_SUBDIR = "edited"


class PanelDirNames(Enum):
    AI = "AI"
    BW = "BW"
    CENSORSHIP = "Censorship"
    CLOSEUPS = "Closeups"
    COVERS = "Covers"
    FAVOURITES = "Favourites"
    INSETS = "Insets"
    NONTITLES = "Nontitles"
    ORIGINAL_ART = "Original Art"
    SEARCH = "Search"
    SILHOUETTES = "Silhouettes"
    SPLASH = "Splash"


class FileTypes(Enum):
    AI = auto()
    BLACK_AND_WHITE = auto()
    CENSORSHIP = auto()
    CLOSEUP = auto()
    COVER = auto()
    FAVOURITE = auto()
    INSET = auto()
    NONTITLE = auto()
    ORIGINAL_ART = auto()
    SILHOUETTE = auto()
    SPLASH = auto()


ALL_TYPES = set(FileTypes)


class BarksPanelsExtType(Enum):
    JPG = auto()
    MOSTLY_PNG = auto()


class ReaderFilePaths:
    def __init__(self) -> None:
        self._barks_reader_files_dir: Path | None = None
        self._reader_icon_files_dir: Path | None = None
        self._app_icon_path: Path | None = None

        self._barks_panels_source: Path | None = None
        self._barks_panels_zip: zipfile.ZipFile | None = None
        self._panels_ext_type: BarksPanelsExtType | None = None

        self._panel_dirs: dict[PanelDirNames, PanelPath] = {}
        self._inset_edited_files_dir: PanelPath | None = None

        self._inset_files_ext = ""
        self._edited_files_ext = ""

        self._titles_cache: dict[FileTypes, list[str]] = {}

        self.FILE_TYPE_FILE_GETTERS: dict[
            FileTypes, Callable[[str, bool], PanelPath | list[PanelPath] | None]
        ] = {
            # COVER special case: returns single string or None
            FileTypes.COVER: self.get_comic_cover_file,
            FileTypes.AI: self.get_comic_ai_files,
            FileTypes.BLACK_AND_WHITE: self.get_comic_bw_files,
            FileTypes.CENSORSHIP: self.get_comic_censorship_files,
            FileTypes.CLOSEUP: self.get_comic_closeup_files,
            FileTypes.FAVOURITE: self.get_comic_favourite_files,
            FileTypes.INSET: self.get_comic_inset_files,
            FileTypes.ORIGINAL_ART: self.get_comic_original_art_files,
            FileTypes.SILHOUETTE: self.get_comic_silhouette_files,
            FileTypes.SPLASH: self.get_comic_splash_files,
        }

        self._FILE_TYPE_DIR_GETTERS: dict[FileTypes, Callable[[], PanelPath]] = {
            FileTypes.COVER: self.get_comic_cover_files_dir,
            FileTypes.AI: self.get_comic_ai_files_dir,
            FileTypes.BLACK_AND_WHITE: self.get_comic_bw_files_dir,
            FileTypes.CENSORSHIP: self.get_comic_censorship_files_dir,
            FileTypes.CLOSEUP: self.get_comic_closeup_files_dir,
            FileTypes.FAVOURITE: self.get_comic_favourite_files_dir,
            FileTypes.INSET: self.get_comic_inset_files_dir,
            FileTypes.ORIGINAL_ART: self.get_comic_original_art_files_dir,
            FileTypes.SILHOUETTE: self.get_comic_silhouette_files_dir,
            FileTypes.SPLASH: self.get_comic_splash_files_dir,
        }

    def set_barks_panels_source(self, panels_source: Path, ext_type: BarksPanelsExtType) -> None:
        self._barks_panels_source = Path(os.path.expandvars(panels_source))
        self._panels_ext_type = ext_type

        is_zip = self._barks_panels_source.suffix == ZIP_FILE_EXT
        panels_root: Path | zipfile.Path

        if is_zip:
            self._barks_panels_zip = zipfile.ZipFile(self._barks_panels_source)
            panels_root = zipfile.Path(self._barks_panels_zip)
        else:
            panels_root = self._barks_panels_source

        for dir_enum in PanelDirNames:
            dir_name = dir_enum.value + ("/" if is_zip else "")
            self._panel_dirs[dir_enum] = panels_root / dir_name

        # Special handling for the nested 'edited' directory
        self._inset_edited_files_dir = self._panel_dirs[PanelDirNames.INSETS] / EDITED_SUBDIR

        self._check_panels_dirs()

        self._inset_files_ext = (
            JPG_FILE_EXT if self._panels_ext_type == BarksPanelsExtType.JPG else PNG_FILE_EXT
        )
        self._edited_files_ext = (
            JPG_FILE_EXT if self._panels_ext_type == BarksPanelsExtType.JPG else PNG_FILE_EXT
        )

    def _check_panels_dirs(self) -> None:
        dirs_to_check = list(self._panel_dirs.values())

        if self._barks_panels_zip:
            self._check_dirs_in_archive(dirs_to_check)
        else:
            dirs_to_check.insert(0, self._barks_panels_source)
            dirs_to_check.append(self._inset_edited_files_dir)
            self._check_dirs(dirs_to_check)

    def _check_dirs(self, dirs_to_check: list[PanelPath]) -> None:
        assert self._barks_panels_zip is None
        for dir_path in dirs_to_check:
            if not dir_path.is_dir():
                msg = f'Required directory not found: "{dir_path}".'
                raise FileNotFoundError(msg)

    def _check_dirs_in_archive(self, dirs_to_check: list[PanelPath]) -> None:
        assert self._barks_panels_zip is not None
        all_paths_in_zip = self._barks_panels_zip.namelist()
        for dir_path in dirs_to_check:
            # A "directory" exists if any path starts with its name followed by a slash.
            dir_prefix = f"{dir_path.name}/"
            if not any(p.startswith(dir_prefix) for p in all_paths_in_zip):
                msg = (
                    f'Required directory "{dir_path.name}"'
                    f' not found or is empty in zip "{self._barks_panels_source}".'
                )
                raise FileNotFoundError(msg)

    @staticmethod
    def _check_files(files_to_check: list[PanelPath]) -> None:
        for file_path in files_to_check:
            if not file_path.is_file():
                msg = f'Required file not found: "{file_path}".'
                raise FileNotFoundError(msg)

    def get_inset_file_ext(self) -> str:
        return self._inset_files_ext

    def get_file_ext(self) -> str:
        return self._inset_files_ext

    def get_emergency_inset_file(self) -> PanelPath:
        return self._panel_dirs[PanelDirNames.INSETS] / (
            BARKS_TITLE_INFO[EMERGENCY_INSET_FILE].get_title_str() + self._inset_files_ext
        )

    @staticmethod
    def get_default_png_barks_panels_source() -> Path:
        return Path(os.path.expandvars(_DEFAULT_PNG_BARKS_PANELS_SOURCE))

    @staticmethod
    def get_default_jpg_barks_panels_source() -> Path:
        return Path(os.path.expandvars(_DEFAULT_JPG_BARKS_PANELS_SOURCE))

    @staticmethod
    def get_default_prebuilt_comic_zips_dir() -> Path:
        return Path(os.path.expandvars(_DEFAULT_THE_COMIC_ZIPS_DIR))

    def get_comic_bw_files_dir(self) -> PanelPath:
        return self._panel_dirs[PanelDirNames.BW]

    def get_comic_ai_files_dir(self) -> PanelPath:
        return self._panel_dirs[PanelDirNames.AI]

    def get_comic_censorship_files_dir(self) -> PanelPath:
        return self._panel_dirs[PanelDirNames.CENSORSHIP]

    def get_comic_closeup_files_dir(self) -> PanelPath:
        return self._panel_dirs[PanelDirNames.CLOSEUPS]

    def get_comic_cover_files_dir(self) -> PanelPath:
        return self._panel_dirs[PanelDirNames.COVERS]

    def get_comic_favourite_files_dir(self) -> PanelPath:
        return self._panel_dirs[PanelDirNames.FAVOURITES]

    def get_comic_inset_files_dir(self) -> PanelPath:
        return self._panel_dirs[PanelDirNames.INSETS]

    def get_nontitle_files_dir(self) -> PanelPath:
        return self._panel_dirs[PanelDirNames.NONTITLES]

    def get_comic_original_art_files_dir(self) -> PanelPath:
        return self._panel_dirs[PanelDirNames.ORIGINAL_ART]

    def get_comic_search_files_dir(self) -> PanelPath:
        return self._panel_dirs[PanelDirNames.SEARCH]

    def get_comic_silhouette_files_dir(self) -> PanelPath:
        return self._panel_dirs[PanelDirNames.SILHOUETTES]

    def get_comic_splash_files_dir(self) -> PanelPath:
        return self._panel_dirs[PanelDirNames.SPLASH]

    def get_barks_reader_app_icon_file(self) -> PanelPath:
        return self._app_icon_path

    def get_comic_inset_file(
        self, title: Titles, use_only_edited_if_possible: bool = False
    ) -> PanelPath:
        if use_only_edited_if_possible:
            edited_file = self._inset_edited_files_dir / get_filename_from_title(
                title, self._inset_files_ext
            )
            if edited_file.is_file():
                return edited_file
            logger.debug(f'No edited inset file "{edited_file}".')

        main_file = self._panel_dirs[PanelDirNames.INSETS] / get_filename_from_title(
            title, self._inset_files_ext
        )
        # TODO: Fix this when all titles are configured.
        # assert os.path.isfile(edited_file)
        if main_file.is_file():
            return main_file

        return self.get_emergency_inset_file()

    def get_comic_inset_files(
        self, title_str: str, use_only_edited_if_possible: bool = False
    ) -> list[PanelPath]:
        title = BARKS_TITLE_DICT[title_str]

        inset_list = []

        edited_inset_file = self.get_comic_inset_file(title, use_only_edited_if_possible)
        if edited_inset_file != self.get_emergency_inset_file():
            inset_list.append(edited_inset_file)
        if use_only_edited_if_possible:
            return inset_list

        main_inset_file = self.get_comic_inset_file(title, use_only_edited_if_possible=False)
        if (main_inset_file != self.get_emergency_inset_file()) and (
            main_inset_file not in inset_list
        ):
            inset_list.append(main_inset_file)

        return inset_list

    def get_comic_cover_file(
        self, title: str, use_only_edited_if_possible: bool = False
    ) -> PanelPath | None:
        if use_only_edited_if_possible:
            edited_file = (
                self.get_comic_cover_files_dir() / EDITED_SUBDIR / (title + self._edited_files_ext)
            )
            if edited_file.is_file():
                return edited_file

        cover_file = self.get_comic_cover_files_dir() / (title + JPG_FILE_EXT)
        if not cover_file.is_file():
            return None

        return cover_file

    def get_comic_bw_files(
        self, title: str, use_only_edited_if_possible: bool = False
    ) -> list[PanelPath]:
        return self._get_files(self.get_comic_bw_files_dir(), title, use_only_edited_if_possible)

    def get_comic_ai_files(
        self, title: str, use_only_edited_if_possible: bool = False
    ) -> list[PanelPath]:
        return self._get_files(self.get_comic_ai_files_dir(), title, use_only_edited_if_possible)

    def get_comic_censorship_files(
        self, title: str, use_only_edited_if_possible: bool = False
    ) -> list[PanelPath]:
        return self._get_files(
            self.get_comic_censorship_files_dir(), title, use_only_edited_if_possible
        )

    def get_comic_closeup_files(
        self, title: str, use_only_edited_if_possible: bool = False
    ) -> list[PanelPath]:
        return self._get_files(
            self.get_comic_closeup_files_dir(), title, use_only_edited_if_possible
        )

    def get_comic_favourite_files(
        self, title: str, use_only_edited_if_possible: bool = False
    ) -> list[PanelPath]:
        return self._get_files(
            self.get_comic_favourite_files_dir(), title, use_only_edited_if_possible
        )

    def get_nontitle_files(self) -> list[PanelPath]:
        return self._get_all_files(self.get_nontitle_files_dir())

    def get_comic_original_art_files(
        self, title: str, use_only_edited_if_possible: bool = False
    ) -> list[PanelPath]:
        return self._get_files(
            self.get_comic_original_art_files_dir(), title, use_only_edited_if_possible
        )

    def get_comic_search_files(
        self, title: str, use_only_edited_if_possible: bool = False
    ) -> list[PanelPath]:
        return self._get_files(
            self.get_comic_search_files_dir(), title, use_only_edited_if_possible
        )

    def get_comic_silhouette_files(
        self, title: str, use_only_edited_if_possible: bool = False
    ) -> list[PanelPath]:
        return self._get_files(
            self.get_comic_silhouette_files_dir(), title, use_only_edited_if_possible
        )

    def get_comic_splash_files(
        self, title: str, use_only_edited_if_possible: bool = False
    ) -> list[PanelPath]:
        return self._get_files(
            self.get_comic_splash_files_dir(), title, use_only_edited_if_possible
        )

    def _get_files(
        self, parent_image_dir: PanelPath, title: str, use_only_edited_if_possible: bool
    ) -> list[PanelPath]:
        image_dir = parent_image_dir / title
        if not image_dir.is_dir():
            return []

        image_files = []

        edited_image_dir = image_dir / EDITED_SUBDIR
        if edited_image_dir.is_dir():
            image_files = self._get_all_files(edited_image_dir)
            if use_only_edited_if_possible:
                # Don't want any unedited images so return now.
                return image_files

        image_files.extend(self._get_all_files(image_dir))

        return image_files

    def get_file_type_titles(
        self, file_type: FileTypes, allowed_titles: set[str] | None = None
    ) -> list[str]:
        if allowed_titles is None:
            allowed_titles = set()

        if file_type in self._titles_cache:
            all_titles = self._titles_cache[file_type]
        else:
            parent_image_dir = self._FILE_TYPE_DIR_GETTERS[file_type]()

            all_titles = []
            for file in parent_image_dir.iterdir():
                title = get_title_str_from_filename(file)
                if file.is_dir():
                    if title != EDITED_SUBDIR:
                        all_titles.append(title)
                elif not title.endswith(NO_OVERRIDES_SUFFIX):
                    all_titles.append(title)

            self._titles_cache[file_type] = all_titles

        if len(allowed_titles) == 0:
            return all_titles

        return [title for title in all_titles if title in allowed_titles]

    @staticmethod
    def _get_all_files(image_dir: PanelPath) -> list[PanelPath]:
        return get_all_files_in_dir(image_dir)

    def get_edited_version_if_possible(self, image_file: PanelPath) -> tuple[PanelPath, bool]:
        dir_path = image_file.parent
        edited_image_file = dir_path / EDITED_SUBDIR / (image_file.stem + self._edited_files_ext)
        if edited_image_file.is_file():
            return edited_image_file, True

        return image_file, False


if __name__ == "__main__":
    barks_panels_source = _DEFAULT_JPG_BARKS_PANELS_SOURCE
    barks_panels_zip = zipfile.ZipFile(barks_panels_source)
    non_titles_dir = zipfile.Path(barks_panels_zip, "Nontitles")
    # assert non_titles_dir.is_dir()
    print(non_titles_dir.name)  # noqa: T201
    for f in non_titles_dir.iterdir():
        print(f)  # noqa: T201
