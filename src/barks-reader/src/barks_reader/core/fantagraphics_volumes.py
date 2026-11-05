from __future__ import annotations

import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.comic_book import get_page_str
from barks_fantagraphics.fanta_comics_info import (
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
)
from comic_utils.comic_consts import CBZ_FILE_EXT, JPG_FILE_EXT, PNG_FILE_EXT, ZIP_FILE_EXT
from loguru import logger

from .log_markers import EMPTY_PAGE_IMAGE
from .reader_utils import is_blank_page, is_title_page

if TYPE_CHECKING:
    from .comic_book_page_info import PageInfo

_VALID_IMAGE_EXTENSION = [PNG_FILE_EXT, JPG_FILE_EXT]


class MissingArchiveFilesError(Exception):
    def __init__(self, missing_file_vols: list[int], archive_root: Path) -> None:
        missing_vols_str = ", ".join(map(str, missing_file_vols))

        if len(missing_file_vols) == 1:
            super().__init__(
                f'There is a volume missing in "{archive_root}".'
                f" The missing volume is '{missing_vols_str}'."
            )
        else:
            super().__init__(
                f'There are volumes missing in "{archive_root}".'
                f" The missing volumes are '{missing_vols_str}'."
            )

        self.missing_file_vols = missing_file_vols


class MissingVolumeError(Exception):
    def __init__(self, missing_vol: int, title: Titles) -> None:
        super().__init__(
            f'Cannot show the title "{ENUM_TO_STR_TITLE[title]}".'
            f" The Fantagraphics volume {missing_vol} is missing."
        )

        self.missing_vol = missing_vol
        self.title = title


class VolumeScanError(Exception):
    """Scanning the volumes failed when a comic needed them, after boot's scan had not run."""


class DuplicateArchiveFilesError(Exception):
    def __init__(self, duplicates: list[int], archive_root: Path) -> None:
        super().__init__(
            f'There are duplicate volume files in "{archive_root}".'
            f" The duplicate volumes are {', '.join(map(str, duplicates))}."
        )

        self.duplicates = duplicates
        self.archive_root = archive_root


class PageNumError(Exception):
    pass


class PageExtError(Exception):
    pass


class EmptyArchiveError(Exception):
    """A volume archive that opened cleanly but holds no page images."""

    def __init__(self, archive_filename: Path) -> None:
        exts = ", ".join(_VALID_IMAGE_EXTENSION)
        super().__init__(
            f'Fantagraphics archive "{archive_filename}" contains no page images'
            f" (looked for {exts}). The file is most likely empty, truncated or a"
            f" partial copy - replace it from the library and retry."
        )


class MixedImageFoldersError(Exception):
    """A volume archive whose page images are not all in one folder."""

    def __init__(self, archive_filename: Path, image_subdirs: list[Path]) -> None:
        folders = ", ".join(f'"{subdir.as_posix()}"' for subdir in image_subdirs)
        super().__init__(
            f'Fantagraphics archive "{archive_filename}" has page images in more than one'
            f" folder ({folders}); they must all be in one. Replace it from the library"
            f" and retry."
        )
        self.image_subdirs = image_subdirs


def has_archive_extension(path: Path) -> bool:
    """Return whether a volume or override archive is named as one.

    Args:
        path: The archive.

    Returns:
        Whether its extension is ``.cbz`` or ``.zip``, in any case.

    """
    return path.suffix.lower() in (CBZ_FILE_EXT, ZIP_FILE_EXT)


_MACOS_JUNK_DIR = "__MACOSX"
_MACOS_JUNK_PREFIX = "._"


def _is_macos_junk(zip_entry_name: str) -> bool:
    """Return whether a zip entry is macOS metadata, not content (Finder's Compress adds it)."""
    entry = PurePosixPath(zip_entry_name)
    return entry.parts[0] == _MACOS_JUNK_DIR or entry.name.startswith(_MACOS_JUNK_PREFIX)


class PageSourceKind(Enum):
    """Where a page's image comes from. The value names it in the logs."""

    PLACEHOLDER = "placeholder"
    EXTRA = "extra"
    OVERRIDE = "override"
    ARCHIVE = "archive"


@dataclass(frozen=True, slots=True)
class PageSource:
    """A page's image: the kind of source, and its path in that source.

    The path is ``None`` for a page no source holds: the volume's archive would have
    to, and it does not.
    """

    kind: PageSourceKind
    path: Path | None


@dataclass(slots=True)
class FantagraphicsArchive:
    """Represents a single Fantagraphics volume archive and its metadata."""

    fanta_volume: int
    archive_filename: Path
    archive_image_subdir: Path | None
    image_ext: str
    first_page: int
    last_page: int
    archive_images_page_map: dict[str, Path]
    override_images_page_map: dict[str, Path]
    extra_images_page_map: dict[str, Path]
    override_archive_filename: Path | None
    override_archive: zipfile.ZipFile | None = None
    is_missing: bool = False

    def get_num_pages(self) -> int:
        return self.last_page - self.first_page + 1

    def has_overrides(self) -> bool:
        return (len(self.extra_images_page_map) > 0) or (len(self.override_images_page_map) > 0)

    def page_source(self, page_str: str, *, use_overrides: bool) -> PageSource:
        """Return where the volume page numbered *page_str* comes from.

        A bundled extra image first, whatever the setting; then a bundled override
        image while *use_overrides* is on; otherwise the library archive, which with
        overrides off means an overridden page needs the archive too.

        Args:
            page_str: The page's number, as the page maps are keyed.
            use_overrides: Whether the pages are being read with their overrides.

        Returns:
            The page's source. ``ARCHIVE`` is what cannot be shown without the library.

        """
        if page_str in self.extra_images_page_map:
            return PageSource(PageSourceKind.EXTRA, self.extra_images_page_map[page_str])
        if use_overrides and page_str in self.override_images_page_map:
            return PageSource(PageSourceKind.OVERRIDE, self.override_images_page_map[page_str])
        return PageSource(PageSourceKind.ARCHIVE, self.archive_images_page_map.get(page_str))

    def page_source_for(self, page_info: PageInfo, *, use_overrides: bool) -> PageSource:
        """Return where a comic's page comes from: title and blank pages have no scan.

        Args:
            page_info: The comic's page.
            use_overrides: Whether the pages are being read with their overrides.

        Returns:
            The page's source, for the reader and for the missing-volume check alike.

        """
        if is_title_page(page_info.srce_page) or is_blank_page(
            page_info.srce_page.page_filename, page_info.page_type
        ):
            return PageSource(PageSourceKind.PLACEHOLDER, Path(EMPTY_PAGE_IMAGE))
        page_str = Path(page_info.srce_page.page_filename).stem
        return self.page_source(page_str, use_overrides=use_overrides)


class FantagraphicsVolumeArchives:
    """Manages the loading and validation of Fantagraphics volume archives."""

    def __init__(self, archive_root: Path, override_root: Path, volume_list: list[int]) -> None:
        self._archive_root = archive_root
        self._override_root = override_root
        self._volume_list = volume_list

        self._fantagraphics_archive_dict: dict[int, FantagraphicsArchive] = {}

    def get_volume_list(self) -> list[int]:
        return self._volume_list

    def get_fantagraphics_archive(self, volume: int) -> FantagraphicsArchive:
        return self._fantagraphics_archive_dict[volume]

    def check_correct_volume_numbers(self, archive_filenames: list[Path]) -> None:
        """Raise if the library's volume files have duplicates or gaps.

        A file numbered outside the volume range never gets here:
        `get_all_volume_filenames` keeps only the volumes in the volume list.
        """
        file_vols = sorted([self._get_fanta_volume(f) for f in archive_filenames])

        # An empty archive dir (or one with no valid volume files) means every volume
        # is missing. Route it through the normal all-missing path rather than indexing
        # into an empty list below.
        if not file_vols:
            raise MissingArchiveFilesError(
                list(range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)), self._archive_root
            )

        # Check there are no duplicates.
        counts = Counter(file_vols)
        duplicates = [item for item, count in counts.items() if count > 1]
        if duplicates:
            raise DuplicateArchiveFilesError(duplicates, self._archive_root)

        # Check for missing volumes.
        full_vol_set = set(range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1))
        file_vols_set = set(file_vols)
        # The difference between the full set and the actual set are the gaps.
        file_vol_gaps = sorted(full_vol_set - file_vols_set)
        if file_vol_gaps:
            raise MissingArchiveFilesError(file_vol_gaps, self._archive_root)

    def load(self) -> None:
        """Load all archives and overrides from the configured directories."""
        archive_filenames = sorted(self.get_all_volume_filenames(), key=self._get_fanta_volume)
        override_archive_filenames = self.get_all_volume_override_archives()

        try:
            self.check_correct_volume_numbers(archive_filenames)
        except MissingArchiveFilesError as e:
            missing_volumes = e.missing_file_vols
        else:
            missing_volumes = []

        self._fantagraphics_archive_dict: dict[int, FantagraphicsArchive] = {}

        for missing_volume in missing_volumes:
            archive_filename = Path(f"{missing_volume}-MISSING.cbz")
            override_archive_filename = override_archive_filenames.get(missing_volume, None)
            # Even without the library archive, the bundled override zip still holds this
            # volume's extra pages (e.g. the fully hand-restored censored stories). With no
            # archive to compare against, every override-zip page classifies as "extra", so
            # a story whose pages are all extra/override can still be read.
            _override_map, extra_images_page_map = self._get_override_and_extra_images_page_maps(
                override_archive_filename, {}
            )
            archive_page_map = FantagraphicsArchive(
                fanta_volume=missing_volume,
                archive_filename=archive_filename,
                archive_image_subdir=None,
                image_ext="",
                first_page=-1,
                last_page=-1,
                archive_images_page_map={},
                override_images_page_map={},
                extra_images_page_map=extra_images_page_map,
                override_archive_filename=override_archive_filename,
                is_missing=True,
            )
            self._fantagraphics_archive_dict[missing_volume] = archive_page_map

        for archive_filename in archive_filenames:
            logger.debug(f'Processing Fantagraphics archive "{archive_filename}"...')

            fanta_volume = self._get_fanta_volume(archive_filename)
            override_archive_filename = override_archive_filenames.get(fanta_volume, None)

            archive_image_subdir, image_filenames = self._get_archive_contents(archive_filename)
            # Every check below indexes [0] or [-1]. An archive with no images is a
            # real field failure (a truncated copy), so name the file rather than
            # letting it surface as a bare IndexError from the next line.
            if not image_filenames:
                raise EmptyArchiveError(archive_filename)
            image_ext = Path(image_filenames[0]).suffix
            if image_ext not in _VALID_IMAGE_EXTENSION:
                msg = (
                    f'For image "{image_filenames[0]}",'
                    f' expecting extension to be in "{_VALID_IMAGE_EXTENSION}".'
                )
                raise PageExtError(msg)

            first_page, last_page = self._get_first_and_last_page_nums(image_filenames)
            self._check_image_names(
                archive_filename, image_filenames, first_page, last_page, image_ext
            )

            archive_images_page_map = self._get_archive_image_page_map(
                archive_image_subdir, image_filenames, first_page, last_page
            )
            override_images_page_map, extra_images_page_map = (
                self._get_override_and_extra_images_page_maps(
                    override_archive_filename, archive_images_page_map
                )
            )

            archive_page_map = FantagraphicsArchive(
                fanta_volume,
                archive_filename,
                archive_image_subdir,
                image_ext,
                first_page,
                last_page,
                archive_images_page_map,
                override_images_page_map,
                extra_images_page_map,
                override_archive_filename,
                is_missing=False,
            )
            self._fantagraphics_archive_dict[fanta_volume] = archive_page_map

            logger.debug(
                f'Finished processing archive "{archive_filename}"'
                f" ({first_page}-{last_page}, {last_page - first_page + 1} pages)."
            )

        if missing_volumes:
            raise MissingArchiveFilesError(missing_volumes, self._archive_root)

    def get_all_volume_filenames(self) -> list[Path]:
        """Return a list of all valid volume archive filenames in the archive root."""
        archive_files = []
        try:
            archive_root_contents = list(self._archive_root.iterdir())
        except (FileNotFoundError, NotADirectoryError):
            # The library dir is unset/missing, or vanished after the startup is_dir()
            # check. Treat it as empty; callers route this to the all-missing path.
            return []
        for archive_file in archive_root_contents:
            if not has_archive_extension(archive_file):
                continue

            if archive_file.is_file():
                try:
                    vol = self._get_fanta_volume(archive_file)
                    if vol in self._volume_list:
                        archive_files.append(archive_file)
                except ValueError:
                    continue

        return archive_files

    def get_all_volume_override_archives(self) -> dict[int, Path]:
        """Return a map of volume number to override archive path.

        A stray entry is logged and skipped rather than stopping the app, and an archive
        without a ``.cbz`` or ``.zip`` extension is logged and used: the overrides folder
        comes from the data pack, so either is a bad pack, which the nightly validator
        reports through `scan_override_root` and `has_archive_extension`.
        """
        override_archives, strays = self.scan_override_root()
        for stray in strays:
            logger.warning(f'Skipping the unexpected entry "{stray}" in the overrides folder.')
        for archive in override_archives.values():
            if not has_archive_extension(archive):
                logger.warning(
                    f'The override archive "{archive}" has no "{CBZ_FILE_EXT}" or'
                    f' "{ZIP_FILE_EXT}" extension; using it anyway.'
                )
        return override_archives

    def scan_override_root(self) -> tuple[dict[int, Path], list[Path]]:
        """Return the override archives by volume, and the overrides folder's stray entries.

        An override archive is a file named for its volume. It should end in ``.cbz`` or
        ``.zip`` (`has_archive_extension`), but one that does not is still the volume's
        archive, not a stray, so a misnamed file in a published pack keeps working. A stray
        is a folder, a file with no volume number or one outside the volume range, or a
        second file for a volume (the first by name is kept). A missing folder holds
        nothing and is itself reported as the one stray.

        Returns:
            The map of volume number to override archive path for the volumes in the
            volume list, and the stray entries in name order.

        """
        override_archives: dict[int, Path] = {}
        strays: list[Path] = []
        try:
            entries = sorted(self._override_root.iterdir())
        except (FileNotFoundError, NotADirectoryError):
            return {}, [self._override_root]

        seen_vols: set[int] = set()
        for entry in entries:
            vol = self._get_override_volume(entry)
            if vol is None or vol in seen_vols:
                strays.append(entry)
                continue
            seen_vols.add(vol)
            if vol in self._volume_list:
                override_archives[vol] = entry

        return override_archives, strays

    def _get_override_volume(self, entry: Path) -> int | None:
        """Return the volume an overrides-folder entry is for, or None for a stray."""
        if not entry.is_file():
            return None
        try:
            vol = self._get_fanta_volume(entry)
        except ValueError:
            return None
        return vol if FIRST_VOLUME_NUMBER <= vol <= LAST_VOLUME_NUMBER else None

    @staticmethod
    def _get_archive_contents(archive_filename: Path) -> tuple[Path, list[str]]:
        """Get the folder and the sorted file names of the archive's page images.

        macOS junk - the ``__MACOSX/`` folder and ``._`` files that Finder's Compress
        adds - is skipped.

        Raises:
            MixedImageFoldersError: The page images are in more than one folder.

        """
        with zipfile.ZipFile(archive_filename, "r") as archive:
            image_names = sorted(
                Path(name)
                for name in archive.namelist()
                if name.lower().endswith(tuple(_VALID_IMAGE_EXTENSION)) and not _is_macos_junk(name)
            )

        image_subdirs = sorted({image_name.parent for image_name in image_names})
        if len(image_subdirs) > 1:
            raise MixedImageFoldersError(archive_filename, image_subdirs)
        image_subdir = image_subdirs[0] if image_subdirs else Path()

        return image_subdir, [image_name.name for image_name in image_names]

    @staticmethod
    def _get_fanta_volume(archive_filename: Path) -> int:
        if match := re.match(r"^(\d+)", archive_filename.name):
            return int(match.group(1))

        msg = (
            f'Could not find Fantagraphics volume number in archive filename "{archive_filename}".'
        )
        raise ValueError(msg)

    def _get_first_and_last_page_nums(self, filenames: list[str]) -> tuple[int, int]:
        first_image = Path(filenames[0]).stem
        last_image = Path(filenames[-1]).stem

        first_page_num = self._extract_image_int(first_image)
        last_page_num = self._extract_image_int(last_image)

        return first_page_num, last_page_num

    @staticmethod
    def _get_archive_image_page_map(
        image_subdir: Path, img_filenames: list[str], first: int, last: int
    ) -> dict[str, Path]:
        page_inc = 0 if first == 1 else 1
        archive_page_map = {}
        for page in range(first, last + 1):
            index = page - first
            page_str = get_page_str(page + page_inc)
            archive_page_map[page_str] = image_subdir / img_filenames[index]

        return archive_page_map

    @staticmethod
    def _get_override_and_extra_images_page_maps(
        override_archive_filename: Path | None, archive_page_map: dict[str, Path]
    ) -> tuple[dict[str, Path], dict[str, Path]]:
        override_pages_map: dict[str, Path] = {}
        extra_pages_map: dict[str, Path] = {}
        if not override_archive_filename:
            return override_pages_map, extra_pages_map

        with zipfile.ZipFile(override_archive_filename, "r") as archive:
            for filename in archive.namelist():
                file = Path(filename)
                page = file.stem
                ext = file.suffix
                if ext not in _VALID_IMAGE_EXTENSION:
                    msg = (
                        f'For image "{file}" in "{override_archive_filename}",'
                        f' expecting extension to be in "{_VALID_IMAGE_EXTENSION}".'
                    )
                    raise PageExtError(msg)

                if page in archive_page_map:
                    if page in override_pages_map:
                        msg = (
                            f'Cannot have jpg and png override in "{override_archive_filename}":'
                            f' "{file}" and "{override_pages_map[page]}".'
                        )
                        raise RuntimeError(msg)
                    override_pages_map[page] = file
                else:
                    if page in extra_pages_map:
                        msg = (
                            f'Cannot have jpg and png override in "{override_archive_filename}":'
                            f' "{file}" and "{extra_pages_map[page]}".'
                        )
                        raise RuntimeError(msg)
                    extra_pages_map[page] = file

        return override_pages_map, extra_pages_map

    @staticmethod
    def _extract_image_int(image_name: str) -> int:
        if match := re.search(r"(\d+)$", image_name):
            return int(match.group(1))

        msg = f'Image name does not have an integer suffix: "{image_name}".'
        raise ValueError(msg)

    def _check_image_names(
        self, archive_filename: Path, img_files: list[str], first: int, last: int, img_ext: str
    ) -> None:
        if first < 0:
            msg = f"First page should be >= 0 not {first}"
            raise ValueError(msg)
        if first >= last:
            msg = f"First page {first} should be < {last}"
            raise ValueError(msg)

        for page in range(first, last + 1):
            index = page - first

            page_num = self._extract_image_int(Path(img_files[index]).stem)
            page_ext = Path(img_files[index]).suffix

            if page != page_num:
                msg = (
                    f'Fantagraphics archive "{archive_filename}": expecting page {page} but'
                    f' image "{img_files[index]}" is numbered {page_num}. Replace it from the'
                    f" library and retry."
                )
                raise PageNumError(msg)
            if img_ext != page_ext:
                msg = f'For page "{page}", expecting extension "{img_ext}" but got "{page_ext}"'
                raise RuntimeError(msg)
