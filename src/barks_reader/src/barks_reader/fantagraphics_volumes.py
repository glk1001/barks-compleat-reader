# ruff: noqa: ERA001

import zipfile
from dataclasses import dataclass
from pathlib import Path

from barks_fantagraphics.comic_book import get_page_str
from barks_fantagraphics.fanta_comics_info import (
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
    NUM_VOLUMES,
)
from comic_utils.comic_consts import JPG_FILE_EXT, PNG_FILE_EXT
from loguru import logger

VALID_IMAGE_EXTENSION = [PNG_FILE_EXT, JPG_FILE_EXT]


class NotEnoughArchiveFilesError(Exception):
    def __init__(self, num_archive_files: int, num_volumes: int, archive_root: Path) -> None:
        super().__init__(
            f'There are not enough archive files in "{archive_root}".'
            f"There are {num_archive_files} but there should be {num_volumes}."
        )


class TooManyArchiveFilesError(Exception):
    def __init__(self, num_archive_files: int, num_volumes: int, archive_root: Path) -> None:
        super().__init__(
            f'There are too many archive files in "{archive_root}".'
            f"There are {num_archive_files} but there should be {num_volumes}."
        )

        self.num_archive_files = num_archive_files
        self.num_volumes = num_volumes
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


class WrongFantagraphicsVolumeError(Exception):
    def __init__(self, file: Path, file_vol: int, expected_volume: int, archive_root: Path) -> None:
        self.file = file
        self.file_vol = file_vol
        self.expected_volume = expected_volume
        self.archive_root = archive_root


class PageNumError(Exception):
    pass


class PageExtError(Exception):
    pass


@dataclass
class FantagraphicsArchive:
    fanta_volume: int
    archive_filename: Path
    override_dir: Path
    archive_image_subdir: Path
    image_ext: str
    first_page: int
    last_page: int
    archive_images_page_map: dict[str, Path]
    override_images_page_map: dict[str, Path]
    extra_images_page_map: dict[str, Path]

    def get_num_pages(self) -> int:
        return self.last_page - self.first_page + 1


class FantagraphicsVolumeArchives:
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
        self, archive_filenames: list[Path], override_dirs: dict[int, Path]
    ) -> None:
        self.check_correct_volume_numbers(archive_filenames)

        if len(archive_filenames) < NUM_VOLUMES:
            raise NotEnoughArchiveFilesError(
                len(archive_filenames), NUM_VOLUMES, self._archive_root
            )
        if len(archive_filenames) > NUM_VOLUMES:
            raise TooManyArchiveFilesError(len(archive_filenames), NUM_VOLUMES, self._archive_root)
        if len(override_dirs) < NUM_VOLUMES:
            raise NotEnoughOverrideDirsError(len(override_dirs), NUM_VOLUMES, self._override_root)
        if len(override_dirs) > NUM_VOLUMES:
            raise TooManyOverrideDirsError(len(override_dirs), NUM_VOLUMES, self._archive_root)

    def check_correct_volume_numbers(self, archive_filenames: list[Path]) -> None:
        volume = FIRST_VOLUME_NUMBER

        for file in archive_filenames:
            file_vol = self._get_fanta_volume(file)

            if volume > LAST_VOLUME_NUMBER:
                raise TooManyArchiveFilesError(
                    len(archive_filenames), NUM_VOLUMES, self._archive_root
                )

            if file_vol != volume:
                raise WrongFantagraphicsVolumeError(file, file_vol, volume, self._archive_root)

            volume += 1

    def load(self) -> None:
        archive_filenames = sorted(self.get_all_volume_filenames())
        override_dirs = self.get_all_volume_overrides()
        self.check_archives_and_overrides(archive_filenames, override_dirs)

        self._fantagraphics_archive_dict: dict[int, FantagraphicsArchive] = {}
        for archive in archive_filenames:
            logger.debug(f'Processing Fantagraphics archive "{archive}"...')

            # self.__check_archive(archive)

            image_dir, image_filenames = self._get_archive_contents(archive)
            image_ext = Path(image_filenames[0]).suffix
            if image_ext not in VALID_IMAGE_EXTENSION:
                msg = (
                    f'For image "{image_filenames[0]}",'
                    f' expecting extension to be in "{VALID_IMAGE_EXTENSION}".'
                )
                raise PageExtError(msg)

            first_page, last_page = self._get_first_and_last_page_nums(image_filenames)
            self._check_image_names(image_filenames, first_page, last_page, image_ext)

            fanta_volume = self._get_fanta_volume(archive)
            override_dir = override_dirs.get(fanta_volume, "")

            archive_image_page_map = self._get_archive_image_page_map(
                image_dir, image_filenames, first_page, last_page
            )
            override_image_page_map, extra_images_page_map = (
                self._get_override_and_extra_images_page_maps(override_dir, archive_image_page_map)
            )

            archive_page_map = FantagraphicsArchive(
                fanta_volume,
                archive,
                override_dir,
                image_dir,
                image_ext,
                first_page,
                last_page,
                archive_image_page_map,
                override_image_page_map,
                extra_images_page_map,
            )

            self._fantagraphics_archive_dict[fanta_volume] = archive_page_map

            logger.debug(
                f'Finished processing archive "{archive}"'
                f" ({first_page}-{last_page}, {last_page - first_page + 1} pages)."
            )

    def get_all_volume_filenames(self) -> list[Path]:
        archive_files = []
        for file in self._archive_root.iterdir():
            archive_file = self._archive_root / file
            if archive_file.suffix.lower() != ".cbz":
                continue

            if archive_file.is_file():
                try:
                    vol = self._get_fanta_volume(file)
                    if vol in self._volume_list:
                        archive_files.append(archive_file)
                except ValueError:
                    continue

        return archive_files

    def get_all_volume_overrides(self) -> dict[int, Path]:
        override_dirs = {}
        for file in self._override_root.iterdir():
            override_dir = self._override_root / file
            if not override_dir.is_dir():
                continue

            try:
                vol = self._get_fanta_volume(file)
                assert FIRST_VOLUME_NUMBER <= vol <= LAST_VOLUME_NUMBER
                if vol in self._volume_list:
                    override_dirs[vol] = override_dir
            except ValueError:
                continue

        return override_dirs

    @staticmethod
    def _check_archive(archive_filename: str) -> None:
        with zipfile.ZipFile(archive_filename, "r") as archive:
            archive.testzip()

    @staticmethod
    def _get_archive_contents(archive_filename: Path) -> tuple[Path, list[str]]:
        with zipfile.ZipFile(archive_filename, "r") as archive:
            image_names = sorted(
                [Path(f) for f in archive.namelist() if f.lower().endswith((".png", ".jpg"))]
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
        archive_basename = archive_filename.name
        vol_str = archive_basename[:2]
        try:
            return int(vol_str)
        except ValueError as e:
            msg = (
                f"Could not find Fantagraphics volume number"
                f' in archive filename "{archive_filename}".'
            )
            raise ValueError(msg) from e

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
        override_dir: Path, archive_page_map: dict[str, Path]
    ) -> tuple[dict[str, Path], dict[str, Path]]:
        override_pages_map = {}
        extra_pages_map = {}
        if not override_dir:
            return override_pages_map, extra_pages_map

        for file in override_dir.iterdir():
            image_file = override_dir / file
            page = file.stem
            ext = file.suffix
            assert ext in [JPG_FILE_EXT, PNG_FILE_EXT]
            if ext not in VALID_IMAGE_EXTENSION:
                msg = (
                    f'For image "{image_file}",'
                    f' expecting extension to be in "{VALID_IMAGE_EXTENSION}".'
                )
                raise PageExtError(msg)

            if page in archive_page_map:
                if page in override_pages_map:
                    msg = (
                        f"Cannot have jpg and png override:"
                        f' "{image_file}" and "{override_pages_map[page]}".'
                    )
                    raise RuntimeError(msg)
                override_pages_map[page] = image_file
            else:
                if page in extra_pages_map:
                    msg = (
                        f"Cannot have jpg and png override:"
                        f' "{image_file}" and "{override_pages_map[page]}".'
                    )
                    raise RuntimeError(msg)
                extra_pages_map[page] = image_file

        return override_pages_map, extra_pages_map

    @staticmethod
    def _extract_image_int(image_name: str) -> int:
        image_page = image_name[-3:]

        try:
            return int(image_page)
        except ValueError as e:
            msg = f'Image name does not have an integer suffix: "{image_name}".'
            raise ValueError(msg) from e

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
