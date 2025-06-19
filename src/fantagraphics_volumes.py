import logging
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict

from barks_fantagraphics.comic_book import get_page_str
from barks_fantagraphics.comics_consts import JPG_FILE_EXT, PNG_FILE_EXT
from barks_fantagraphics.fanta_comics_info import FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER


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


class PageNumError(Exception):
    pass


class PageExtError(Exception):
    pass


def get_fantagraphics_archive_dict(
    archive_root: str, override_root: str, volume_list: List[int]
) -> Dict[int, FantagraphicsArchive]:
    archive_filenames = sorted(get_all_volume_filenames(archive_root, volume_list))
    overrides_dirs = get_all_volume_overrides(override_root, volume_list)

    archive_dict: Dict[int, FantagraphicsArchive] = {}
    for archive in archive_filenames:
        logging.info(f'Processing Fantagraphics archive "{archive}"...')

        check_archive(archive)

        image_dir, image_filenames = get_archive_contents(archive)
        image_ext = Path(image_filenames[0]).suffix
        assert image_ext in [".png", ".jpg"]

        first_page, last_page = get_first_and_last_page_nums(image_filenames)
        check_image_names(image_filenames, first_page, last_page, image_ext)

        fanta_volume = get_fanta_volume(archive)
        override_dir = overrides_dirs.get(fanta_volume, "")

        archive_image_page_map = get_archive_image_page_map(image_dir, image_filenames, first_page, last_page)
        override_image_page_map, extra_images_page_map = get_override_and_extra_images_page_maps(
            override_dir, archive_image_page_map
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

        archive_dict[fanta_volume] = archive_page_map

        logging.info(
            f'Finished processing archive "{archive}"' f" ({last_page - first_page + 1} pages)."
        )

    return archive_dict


def get_all_volume_filenames(archive_root: str, volume_list: List[int]) -> List[str]:
    archive_files = []
    for file in os.listdir(archive_root):
        archive_file = os.path.join(archive_root, file)
        if Path(archive_file).suffix.lower() != ".cbz":
            continue

        if os.path.isfile(archive_file):
            try:
                vol = get_fanta_volume(file)
                assert FIRST_VOLUME_NUMBER <= vol <= LAST_VOLUME_NUMBER
                if vol in volume_list:
                    archive_files.append(archive_file)
            except ValueError:
                continue

    return archive_files


def get_all_volume_overrides(override_root: str, volume_list: List[int]) -> Dict[int, str]:
    override_dirs = {}
    for file in os.listdir(override_root):
        override_dir = os.path.join(override_root, file)
        if not os.path.isdir(override_dir):
            continue

        try:
            vol = get_fanta_volume(file)
            assert FIRST_VOLUME_NUMBER <= vol <= LAST_VOLUME_NUMBER
            if vol in volume_list:
                override_dirs[vol] = override_dir
        except ValueError:
            continue

    return override_dirs


def check_archive(archive_filename: str) -> None:
    with zipfile.ZipFile(archive_filename, "r") as archive:
        archive.testzip()


def get_archive_contents(archive_filename: str) -> Tuple[str, List[str]]:
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


def get_fanta_volume(archive_filename: str) -> int:
    archive_basename = os.path.basename(archive_filename)
    vol_str = archive_basename[:2]
    try:
        return int(vol_str)
    except ValueError:
        raise ValueError(
            f"Could not find Fantagraphics volume number"
            f' in archive filename "{archive_filename}".'
        )


def get_first_and_last_page_nums(filenames: List[str]) -> Tuple[int, int]:
    first_image = Path(filenames[0]).stem
    last_image = Path(filenames[-1]).stem

    first_page_num = extract_int(first_image)
    last_page_num = extract_int(last_image)

    return first_page_num, last_page_num


def get_archive_image_page_map(
    image_subdir: str, img_filenames: List[str], first: int, last: int
) -> Dict[str, str]:
    page_inc = 0 if first == 1 else 1
    archive_page_map = {}
    for page in range(first, last + 1):
        index = page - first
        page_str = get_page_str(page + page_inc)
        archive_page_map[page_str] = os.path.join(image_subdir, img_filenames[index])

    return archive_page_map


def get_override_and_extra_images_page_maps(
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


def extract_int(image_name: str) -> int:
    image_page = image_name[-3:]

    try:
        return int(image_page)
    except ValueError:
        raise ValueError(f'Image name does not have an integer suffix: "{image_name}".')


def check_image_names(img_files: List[str], first: int, last: int, img_ext: str) -> None:
    if first < 0:
        raise ValueError(f"First page should be >= 0 not {first}")
    if first >= last:
        raise ValueError(f"First page {first} should be < {last}")

    for page in range(first, last + 1):
        index = page - first

        page_num = extract_int(Path(img_files[index]).stem)
        page_ext = Path(img_files[index]).suffix

        if page != page_num:
            raise PageNumError(f"Expecting page {page} but got {page_num}")
        if img_ext != page_ext:
            raise PageExtError(f'Expecting extension "{img_ext}" but got "{page_ext}"')
