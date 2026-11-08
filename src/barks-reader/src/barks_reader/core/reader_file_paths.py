from __future__ import annotations

import zipfile
from enum import Enum, auto
from pathlib import Path, PurePath
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import STR_TITLE_TO_ENUM, Titles
from barks_fantagraphics.comic_book_info import (
    BARKS_TITLE_INFO,
    get_filename_from_title,
    get_title_str_from_filename,
)
from comic_utils.comic_consts import JPG_FILE_EXT, PNG_FILE_EXT, ZIP_FILE_EXT, PanelPath
from loguru import logger

from .reader_consts_and_types import NO_OVERRIDES_SUFFIX
from .reader_utils import expand_path_vars, get_all_files_in_dir

if TYPE_CHECKING:
    from collections.abc import Callable

EMERGENCY_INSET_FILE = Titles.BICEPS_BLUES

_DEFAULT_BARKS_DIR = "${HOME}/Books/Carl Barks"
_DEFAULT_THE_COMIC_ZIPS_DIR = _DEFAULT_BARKS_DIR + "/The Comics/Chronological"
_DEFAULT_JPG_BARKS_PANELS_SOURCE = (
    _DEFAULT_BARKS_DIR + "/Compleat Barks Disney Reader/Reader Files/Barks Panels.zip"
)
_DEFAULT_PNG_BARKS_PANELS_SOURCE = _DEFAULT_BARKS_DIR + "/Barks Panels Pngs"

EDITED_SUBDIR = "edited"

# The files whose names are titles in a panel-type folder.
_TITLE_IMAGE_EXTS = (JPG_FILE_EXT, PNG_FILE_EXT)


def is_edited_file(image_file: PanelPath) -> bool:
    """Return whether ``image_file`` is an edited copy: one in an ``edited`` folder."""
    # PurePath: a zip member's parent is typed as a bare PathLike.
    return PurePath(str(image_file)).parent.name == EDITED_SUBDIR


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

# The panel folder each image type's files are in.
_FILE_TYPE_DIRS: dict[FileTypes, PanelDirNames] = {
    FileTypes.AI: PanelDirNames.AI,
    FileTypes.BLACK_AND_WHITE: PanelDirNames.BW,
    FileTypes.CENSORSHIP: PanelDirNames.CENSORSHIP,
    FileTypes.CLOSEUP: PanelDirNames.CLOSEUPS,
    FileTypes.COVER: PanelDirNames.COVERS,
    FileTypes.FAVOURITE: PanelDirNames.FAVOURITES,
    FileTypes.INSET: PanelDirNames.INSETS,
    FileTypes.NONTITLE: PanelDirNames.NONTITLES,
    FileTypes.ORIGINAL_ART: PanelDirNames.ORIGINAL_ART,
    FileTypes.SILHOUETTE: PanelDirNames.SILHOUETTES,
    FileTypes.SPLASH: PanelDirNames.SPLASH,
}
assert set(_FILE_TYPE_DIRS) == ALL_TYPES


class BarksPanelsExtType(Enum):
    JPG = auto()
    MOSTLY_PNG = auto()


class ReaderFilePaths:
    def __init__(self) -> None:
        self._barks_panels_source: Path | None = None
        self._barks_panels_zip: zipfile.ZipFile | None = None
        self.barks_panels_are_encrypted: bool = False
        self._panels_ext_type: BarksPanelsExtType | None = None

        self._panel_dirs: dict[PanelDirNames, PanelPath] = {}
        self._inset_edited_files_dir: PanelPath | None = None

        # The panels' image extension: an edited copy, or an inset, has it. (A plain
        # cover is always a JPG.)
        self._panel_file_ext = ""

        self._titles_cache: dict[FileTypes, list[str]] = {}
        self._panels_source_listeners: list[Callable[[], None]] = []

    def add_panels_source_listener(self, listener: Callable[[], None]) -> None:
        """Call ``listener`` after every later ``set_barks_panels_source``.

        For state kept outside this class that follows the panels source, such as the
        comics database's inset folder and extension.

        Args:
            listener: Called with no arguments once the new source is fully set.

        """
        self._panels_source_listeners.append(listener)

    def set_barks_panels_source(self, panels_source: Path, ext_type: BarksPanelsExtType) -> None:
        """Point every panel lookup at ``panels_source``, a folder or a zip.

        The settings panel calls this again when the source changes, so nothing from
        the previous source is kept: its zip is dropped and the titles cache is cleared.

        Args:
            panels_source: The panels folder or zip; ``$VAR``s in it are expanded.
            ext_type: Whether the source holds JPGs or (mostly) PNGs.

        Raises:
            FileNotFoundError: If a required panel folder is missing from the source.

        """
        self._drop_panels_zip()
        self._titles_cache.clear()

        source = Path(expand_path_vars(panels_source))
        self._barks_panels_source = source
        self._panels_ext_type = ext_type

        is_zip = source.suffix == ZIP_FILE_EXT
        panels_root: Path | zipfile.Path

        if is_zip:
            self.barks_panels_are_encrypted = True
            self._barks_panels_zip = zipfile.ZipFile(self._barks_panels_source, "r")
            panels_root = zipfile.Path(self._barks_panels_zip)
        else:
            self.barks_panels_are_encrypted = False
            panels_root = self._barks_panels_source

        for dir_enum in PanelDirNames:
            dir_name = dir_enum.value + ("/" if is_zip else "")
            self._panel_dirs[dir_enum] = panels_root / dir_name

        # Special handling for the nested 'edited' directory
        self._inset_edited_files_dir = self._panel_dirs[PanelDirNames.INSETS] / EDITED_SUBDIR

        self._check_panels_dirs()

        self._panel_file_ext = (
            JPG_FILE_EXT if self._panels_ext_type == BarksPanelsExtType.JPG else PNG_FILE_EXT
        )

        for listener in self._panels_source_listeners:
            listener()

    def _drop_panels_zip(self) -> None:
        # Dropped, not closed: an image already on screen may hold a zip path from the
        # old source, and reading it from a closed zip raises. The zip closes itself
        # once nothing refers to it any more.
        self._barks_panels_zip = None

    def _check_panels_dirs(self) -> None:
        dirs_to_check = list(self._panel_dirs.values())

        if self._barks_panels_zip:
            self._check_dirs_in_archive(dirs_to_check)
        else:
            assert self._barks_panels_source is not None
            dirs_to_check.insert(0, self._barks_panels_source)
            assert self._inset_edited_files_dir
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

    def get_file_ext(self) -> str:
        """Return the panels' image extension, ".jpg" or ".png", as insets and edits have."""
        return self._panel_file_ext

    def get_emergency_inset_file(self) -> PanelPath:
        return self._panel_dirs[PanelDirNames.INSETS] / (
            BARKS_TITLE_INFO[EMERGENCY_INSET_FILE].get_title_str() + self._panel_file_ext
        )

    @staticmethod
    def get_default_png_barks_panels_source() -> Path:
        return Path(expand_path_vars(_DEFAULT_PNG_BARKS_PANELS_SOURCE))

    @staticmethod
    def get_default_jpg_barks_panels_source() -> Path:
        return Path(expand_path_vars(_DEFAULT_JPG_BARKS_PANELS_SOURCE))

    @staticmethod
    def get_default_prebuilt_comic_zips_dir() -> Path:
        return Path(expand_path_vars(_DEFAULT_THE_COMIC_ZIPS_DIR))

    def get_panel_dir(self, panel_dir: PanelDirNames) -> PanelPath:
        """Return a panel folder of the current source (a folder, or one in the zip)."""
        return self._panel_dirs[panel_dir]

    def get_title_files(
        self, file_type: FileTypes, title_str: str, use_only_edited_if_possible: bool = False
    ) -> list[PanelPath]:
        """Return a title's images of one type, its edited ones first.

        Args:
            file_type: The image type. NONTITLE images belong to no title: none.
            title_str: The title whose images to list.
            use_only_edited_if_possible: Only the edited images, when the title has any.

        Returns:
            The images found; a cover or inset lookup gives at most its own one or two.

        """
        match file_type:
            case FileTypes.COVER:
                cover = self.get_comic_cover_file(title_str, use_only_edited_if_possible)
                return [] if cover is None else [cover]
            case FileTypes.INSET:
                return self.get_comic_inset_files(title_str, use_only_edited_if_possible)
            case FileTypes.NONTITLE:
                return []
            case _:
                return self._get_files(
                    self._panel_dirs[_FILE_TYPE_DIRS[file_type]],
                    title_str,
                    use_only_edited_if_possible,
                )

    def get_comic_inset_file(
        self, title: Titles, use_only_edited_if_possible: bool = False
    ) -> PanelPath:
        """Return the title's inset, or the emergency inset when it has none.

        Args:
            title: The title whose inset to find.
            use_only_edited_if_possible: Prefer the edited inset when there is one.

        Returns:
            The edited inset (if asked for and there is one), else the plain one, else
            the emergency title's.

        """
        if use_only_edited_if_possible and (edited := self._find_edited_inset_file(title)):
            return edited
        return self._find_plain_inset_file(title) or self.get_emergency_inset_file()

    def get_comic_inset_files(
        self, title_str: str, use_only_edited_if_possible: bool = False
    ) -> list[PanelPath]:
        """Return the title's own insets: the edited one first, then the plain one.

        Never the emergency inset: a title with no inset of its own lists none.

        Args:
            title_str: The title whose insets to list.
            use_only_edited_if_possible: List only the edited inset when there is one;
                with none, the plain one.

        Returns:
            The insets found, the edited one first, as every other file getter lists them.

        """
        title = STR_TITLE_TO_ENUM[title_str]

        edited = self._find_edited_inset_file(title)
        if edited and use_only_edited_if_possible:
            return [edited]

        plain = self._find_plain_inset_file(title)
        return [inset for inset in (edited, plain) if inset is not None]

    def _find_edited_inset_file(self, title: Titles) -> PanelPath | None:
        assert self._inset_edited_files_dir
        edited_file = self._inset_edited_files_dir / get_filename_from_title(
            title, self._panel_file_ext
        )
        if edited_file.is_file():
            return edited_file
        logger.debug(f'No edited inset file "{edited_file}".')
        return None

    def _find_plain_inset_file(self, title: Titles) -> PanelPath | None:
        main_file = self._panel_dirs[PanelDirNames.INSETS] / get_filename_from_title(
            title, self._panel_file_ext
        )
        return main_file if main_file.is_file() else None

    def get_comic_cover_file(
        self, title: str, use_only_edited_if_possible: bool = False
    ) -> PanelPath | None:
        if use_only_edited_if_possible:
            edited_file = (
                self._panel_dirs[PanelDirNames.COVERS]
                / EDITED_SUBDIR
                / (title + self._panel_file_ext)
            )
            if edited_file.is_file():
                return edited_file

        cover_file = self._panel_dirs[PanelDirNames.COVERS] / (title + JPG_FILE_EXT)
        if not cover_file.is_file():
            return None

        return cover_file

    def get_nontitle_files(self) -> list[PanelPath]:
        """Return every image that belongs to no title."""
        return self._get_all_files(self._panel_dirs[PanelDirNames.NONTITLES])

    def get_comic_search_files(
        self, title: str, use_only_edited_if_possible: bool = False
    ) -> list[PanelPath]:
        """Return a title's search-screen images, its edited ones first."""
        return self._get_files(
            self._panel_dirs[PanelDirNames.SEARCH], title, use_only_edited_if_possible
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
        """Return the titles that have an image of ``file_type``.

        Args:
            file_type: The panel type whose folder is listed (cached after the first scan).
            allowed_titles: Keep only these titles. ``None`` keeps every title; an empty
                set keeps none.

        Returns:
            The titles, in the folder's listing order.

        """
        if file_type in self._titles_cache:
            all_titles = self._titles_cache[file_type]
        else:
            parent_image_dir = self._panel_dirs[_FILE_TYPE_DIRS[file_type]]

            all_titles = []
            for file in parent_image_dir.iterdir():
                # Hidden OS files (.DS_Store, ._ resource forks) are not titles.
                if file.name.startswith("."):
                    continue
                title = get_title_str_from_filename(file)
                if file.is_dir():
                    if title != EDITED_SUBDIR:
                        all_titles.append(title)
                elif file.suffix.lower() in _TITLE_IMAGE_EXTS and not title.endswith(
                    NO_OVERRIDES_SUFFIX
                ):
                    # Only an image names a title: not Thumbs.db or a stray text file.
                    all_titles.append(title)

            self._titles_cache[file_type] = all_titles

        if allowed_titles is None:
            return all_titles

        return [title for title in all_titles if title in allowed_titles]

    @staticmethod
    def _get_all_files(image_dir: PanelPath) -> list[PanelPath]:
        return get_all_files_in_dir(image_dir)

    def get_edited_version_if_possible(self, image_file: PanelPath) -> tuple[PanelPath, bool]:
        # Already the edited one: there is no "edited/edited/" copy to look for, and an
        # edited cover was once letterboxed for not finding one.
        # PurePath: a zip member's parent is typed as a bare PathLike.
        if is_edited_file(image_file):
            return image_file, True

        edited_image_file = (
            image_file.parent / Path(EDITED_SUBDIR) / (image_file.stem + self._panel_file_ext)
        )
        if edited_image_file.is_file():
            return edited_image_file, True

        return image_file, False
