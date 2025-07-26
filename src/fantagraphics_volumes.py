import logging
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict

from barks_fantagraphics.comic_book import get_page_str
from barks_fantagraphics.comics_consts import JPG_FILE_EXT, PNG_FILE_EXT
from barks_fantagraphics.fanta_comics_info import (
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
    NUM_VOLUMES,
)

VALID_IMAGE_EXTENSION = [PNG_FILE_EXT, JPG_FILE_EXT]


class NotEnoughArchiveFilesError(Exception):
    def __init__(self, num_archive_files: int, num_volumes: int, archive_root: str):
        super().__init__(
            f'There are not enough archive files in "{archive_root}".'
            f"There are {num_archive_files} but there should be {num_volumes}."
        )


class TooManyArchiveFilesError(Exception):
    def __init__(self, num_archive_files: int, num_volumes: int, archive_root: str):
        super().__init__(
            f'There are too many archive files in "{archive_root}".'
            f"There are {num_archive_files} but there should be {num_volumes}."
        )

        self.num_archive_files = num_archive_files
        self.num_volumes = num_volumes
        self.archive_root = archive_root


class NotEnoughOverrideDirsError(Exception):
    def __init__(self, num_override_dirs: int, num_volumes: int, override_dirs_root: str):
        super().__init__(
            f'There are not enough override dirs in "{override_dirs_root}".'
            f"There are {num_override_dirs} but there should be {num_volumes}."
        )


class TooManyOverrideDirsError(Exception):
    def __init__(self, num_override_dirs: int, num_volumes: int, override_dirs_root: str):
        super().__init__(
            f'There are too many override dirs in "{override_dirs_root}".'
            f"There are {num_override_dirs} but there should be {num_volumes}."
        )


class WrongFantagraphicsVolumeError(Exception):
    def __init__(self, file: str, file_vol: int, expected_volume: int, archive_root: str):
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
    archive_filename: str
    override_dir: str
    archive_image_subdir: str
    image_ext: str
    first_page: int
    last_page: int
    archive_images_page_map: Dict[str, str]
    override_images_page_map: Dict[str, str]
    extra_images_page_map: Dict[str, str]

    def get_num_pages(self):
        return self.last_page - self.first_page + 1


class FantagraphicsVolumeArchives:
    def __init__(self, archive_root: str, override_root: str, volume_list: List[int]):
        self._archive_root = archive_root
        self._override_root = override_root
        self._volume_list = volume_list

        self._fantagraphics_archive_dict: Dict[int, FantagraphicsArchive] = {}

    def get_volume_list(self) -> List[int]:
        return self._volume_list

    def get_fantagraphics_archive(self, volume: int) -> FantagraphicsArchive:
        return self._fantagraphics_archive_dict[volume]

    def check_archives_and_overrides(
        self, archive_filenames: List[str], override_dirs: Dict[int, str]
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

    def check_correct_volume_numbers(self, archive_filenames: List[str]) -> None:
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

        self._fantagraphics_archive_dict: Dict[int, FantagraphicsArchive] = {}
        for archive in archive_filenames:
            logging.debug(f'Processing Fantagraphics archive "{archive}"...')

            # self.__check_archive(archive)

            image_dir, image_filenames = self._get_archive_contents(archive)
            image_ext = Path(image_filenames[0]).suffix
            if image_ext not in VALID_IMAGE_EXTENSION:
                raise PageExtError(
                    f'For image "{image_filenames[0]}",'
                    f' expecting extension to be in "{VALID_IMAGE_EXTENSION}".'
                )

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

            logging.debug(
                f'Finished processing archive "{archive}"' f" ({last_page - first_page + 1} pages)."
            )

    def get_all_volume_filenames(self) -> List[str]:
        archive_files = []
        for file in os.listdir(self._archive_root):
            archive_file = os.path.join(self._archive_root, file)
            if Path(archive_file).suffix.lower() != ".cbz":
                continue

            if os.path.isfile(archive_file):
                try:
                    vol = self._get_fanta_volume(file)
                    if vol in self._volume_list:
                        archive_files.append(archive_file)
                except ValueError:
                    continue

        return archive_files

    def get_all_volume_overrides(self) -> Dict[int, str]:
        override_dirs = {}
        for file in os.listdir(self._override_root):
            override_dir = os.path.join(self._override_root, file)
            if not os.path.isdir(override_dir):
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
    def _get_archive_contents(archive_filename: str) -> Tuple[str, List[str]]:
        with zipfile.ZipFile(archive_filename, "r") as archive:
            image_names = sorted(
                [f for f in archive.namelist() if f.lower().endswith((".png", ".jpg"))]
            )
            image_subdir = ""
            image_filenames = []
            for image_name in image_names:
                subdir = os.path.dirname(image_name)
                if subdir != image_subdir:
                    image_subdir = subdir
                assert image_subdir == subdir
                image_filenames.append(os.path.basename(image_name))

            return image_subdir, image_filenames

    @staticmethod
    def _get_fanta_volume(archive_filename: str) -> int:
        archive_basename = os.path.basename(archive_filename)
        vol_str = archive_basename[:2]
        try:
            return int(vol_str)
        except ValueError:
            raise ValueError(
                f"Could not find Fantagraphics volume number"
                f' in archive filename "{archive_filename}".'
            )

    def _get_first_and_last_page_nums(self, filenames: List[str]) -> Tuple[int, int]:
        first_image = Path(filenames[0]).stem
        last_image = Path(filenames[-1]).stem

        first_page_num = self._extract_image_int(first_image)
        last_page_num = self._extract_image_int(last_image)

        return first_page_num, last_page_num

    @staticmethod
    def _get_archive_image_page_map(
        image_subdir: str, img_filenames: List[str], first: int, last: int
    ) -> Dict[str, str]:
        page_inc = 0 if first == 1 else 1
        archive_page_map = {}
        for page in range(first, last + 1):
            index = page - first
            page_str = get_page_str(page + page_inc)
            archive_page_map[page_str] = os.path.join(image_subdir, img_filenames[index])

        return archive_page_map

    @staticmethod
    def _get_override_and_extra_images_page_maps(
        override_dir: str, archive_page_map: Dict[str, str]
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        override_pages_map = {}
        extra_pages_map = {}
        if not override_dir:
            return override_pages_map, extra_pages_map

        for file in os.listdir(override_dir):
            image_file = os.path.join(override_dir, file)
            page = Path(file).stem
            ext = Path(file).suffix
            assert ext in [JPG_FILE_EXT, PNG_FILE_EXT]
            if ext not in VALID_IMAGE_EXTENSION:
                raise PageExtError(
                    f'For image "{image_file}",'
                    f' expecting extension to be in "{VALID_IMAGE_EXTENSION}".'
                )

            if page in archive_page_map:
                if page in override_pages_map:
                    raise Exception(
                        f"Cannot have jpg and png override:"
                        f' "{image_file}" and "{override_pages_map[page]}".'
                    )
                override_pages_map[page] = image_file
            else:
                if page in extra_pages_map:
                    raise Exception(
                        f"Cannot have jpg and png override:"
                        f' "{image_file}" and "{override_pages_map[page]}".'
                    )
                extra_pages_map[page] = image_file

        return override_pages_map, extra_pages_map

    @staticmethod
    def _extract_image_int(image_name: str) -> int:
        image_page = image_name[-3:]

        try:
            return int(image_page)
        except ValueError:
            raise ValueError(f'Image name does not have an integer suffix: "{image_name}".')

    def _check_image_names(self, img_files: List[str], first: int, last: int, img_ext: str) -> None:
        if first < 0:
            raise ValueError(f"First page should be >= 0 not {first}")
        if first >= last:
            raise ValueError(f"First page {first} should be < {last}")

        for page in range(first, last + 1):
            index = page - first

            page_num = self._extract_image_int(Path(img_files[index]).stem)
            page_ext = Path(img_files[index]).suffix

            if page != page_num:
                raise PageNumError(f"Expecting page {page} but got {page_num}")
            if img_ext != page_ext:
                raise PageExtError(
                    f'For page "{page}", expecting extension "{img_ext}" but got "{page_ext}"'
                )
