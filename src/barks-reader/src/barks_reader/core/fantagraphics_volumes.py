import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles
from barks_fantagraphics.comic_book import get_page_str
from barks_fantagraphics.fanta_comics_info import (
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
    NUM_VOLUMES,
)
from comic_utils.comic_consts import CBZ_FILE_EXT, JPG_FILE_EXT, PNG_FILE_EXT, ZIP_FILE_EXT
from loguru import logger

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
                f"The missing volumes are '{missing_vols_str}'."
            )

        self.missing_file_vols = missing_file_vols


class MissingVolumeError(Exception):
    def __init__(self, missing_vol: int, title: Titles) -> None:
        super().__init__(
            f'Cannot show the the title "{BARKS_TITLES[title]}".'
            f" The Fantagraphics volume {missing_vol} is missing."
        )

        self.missing_vol = missing_vol
        self.title = title


class TooManyArchiveFilesError(Exception):
    def __init__(self, num_archive_files: int, num_volumes: int, archive_root: Path) -> None:
        super().__init__(
            f'There are too many archive files in "{archive_root}".'
            f"There are {num_archive_files} but there should be {num_volumes}."
        )

        self.num_archive_files = num_archive_files
        self.num_volumes = num_volumes
        self.archive_root = archive_root


class DuplicateArchiveFilesError(Exception):
    def __init__(self, duplicates: list[int], archive_root: Path) -> None:
        super().__init__(
            f'There are duplicate volume files in "{archive_root}".'
            f"The duplicate volumes are {', '.join(map(str, duplicates))}."
        )

        self.duplicates = duplicates
        self.archive_root = archive_root


class NotEnoughOverrideDirsError(Exception):
    def __init__(self, num_override_dirs: int, num_volumes: int, override_dirs_root: Path) -> None:
        super().__init__(
            f'There are not enough override dirs in "{override_dirs_root}".'
            f"There are {num_override_dirs} but there should be {num_volumes}."
        )


class TooManyOverrideDirsError(Exception):
    def __init__(self, num_override_dirs: int, num_volumes: int, override_dirs_root: Path) -> None:
        super().__init__(
            f'There are too many override dirs in "{override_dirs_root}".'
            f"There are {num_override_dirs} but there should be {num_volumes}."
        )


class PageNumError(Exception):
    pass


class PageExtError(Exception):
    pass


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

    def check_archives_and_overrides(
        self, archive_filenames: list[Path], override_archive_filenames: dict[int, Path]
    ) -> None:
        self.check_correct_volume_numbers(archive_filenames)

        if len(override_archive_filenames) > NUM_VOLUMES:
            raise TooManyOverrideDirsError(
                len(override_archive_filenames), NUM_VOLUMES, self._archive_root
            )

    def check_correct_volume_numbers(self, archive_filenames: list[Path]) -> None:
        file_vols = sorted([self._get_fanta_volume(f) for f in archive_filenames])

        # Check valid volume numbers.
        if file_vols[-1] > LAST_VOLUME_NUMBER:
            raise TooManyArchiveFilesError(len(archive_filenames), NUM_VOLUMES, self._archive_root)

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
            self.check_archives_and_overrides(archive_filenames, override_archive_filenames)
        except MissingArchiveFilesError as e:
            missing_volumes = e.missing_file_vols
        else:
            missing_volumes = []

        self._fantagraphics_archive_dict: dict[int, FantagraphicsArchive] = {}

        for missing_volume in missing_volumes:
            archive_filename = Path(f"{missing_volume}-MISSING.cbz")
            override_archive_filename = override_archive_filenames.get(missing_volume, None)
            archive_page_map = FantagraphicsArchive(
                fanta_volume=missing_volume,
                archive_filename=archive_filename,
                archive_image_subdir=None,
                image_ext="",
                first_page=-1,
                last_page=-1,
                archive_images_page_map={},
                override_images_page_map={},
                extra_images_page_map={},
                override_archive_filename=override_archive_filename,
                is_missing=True,
            )
            self._fantagraphics_archive_dict[missing_volume] = archive_page_map

        for archive_filename in archive_filenames:
            logger.debug(f'Processing Fantagraphics archive "{archive_filename}"...')

            fanta_volume = self._get_fanta_volume(archive_filename)
            override_archive_filename = override_archive_filenames.get(fanta_volume, None)

            archive_image_subdir, image_filenames = self._get_archive_contents(archive_filename)
            image_ext = Path(image_filenames[0]).suffix
            if image_ext not in _VALID_IMAGE_EXTENSION:
                msg = (
                    f'For image "{image_filenames[0]}",'
                    f' expecting extension to be in "{_VALID_IMAGE_EXTENSION}".'
                )
                raise PageExtError(msg)

            first_page, last_page = self._get_first_and_last_page_nums(image_filenames)
            self._check_image_names(image_filenames, first_page, last_page, image_ext)

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
        for archive_file in self._archive_root.iterdir():
            if archive_file.suffix.lower() not in [CBZ_FILE_EXT, ZIP_FILE_EXT]:
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
        """Return a map of volume number to override archive path."""
        override_archives = {}
        for override_archive_file in self._override_root.iterdir():
            if not override_archive_file.is_file():
                msg = f'Unexpected override archive directory "{override_archive_file}".'
                raise FileExistsError(msg)

            try:
                vol = self._get_fanta_volume(override_archive_file)
                assert FIRST_VOLUME_NUMBER <= vol <= LAST_VOLUME_NUMBER
                if vol in self._volume_list:
                    override_archives[vol] = override_archive_file
            except ValueError:
                continue

        return override_archives

    @staticmethod
    def _get_archive_contents(archive_filename: Path) -> tuple[Path, list[str]]:
        """Get the subdirectory and list of image filenames from the archive."""
        with zipfile.ZipFile(archive_filename, "r") as archive:
            image_names = sorted(
                [
                    Path(f)
                    for f in archive.namelist()
                    if f.lower().endswith(tuple(_VALID_IMAGE_EXTENSION))
                ]
            )
            image_subdir = Path()
            image_filenames = []
            for image_name in image_names:
                subdir = image_name.parent
                if subdir != image_subdir:
                    image_subdir = subdir
                assert image_subdir == subdir
                image_filenames.append(image_name.name)

            return image_subdir, image_filenames

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
                assert ext in [JPG_FILE_EXT, PNG_FILE_EXT]
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
                            f' "{file}" and "{override_pages_map[page]}".'
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

    def _check_image_names(self, img_files: list[str], first: int, last: int, img_ext: str) -> None:
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
                msg = f"Expecting page {page} but got {page_num}"
                raise PageNumError(msg)
            if img_ext != page_ext:
                msg = f'For page "{page}", expecting extension "{img_ext}" but got "{page_ext}"'
                raise RuntimeError(msg)
