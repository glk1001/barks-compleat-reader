from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

from comic_utils.comic_consts import JPG_FILE_EXT, JSON_FILE_EXT, PNG_FILE_EXT, SVG_FILE_EXT
from loguru import logger

from .barks_titles import (
    BARKS_TITLE_DICT,
    GOOD_DEEDS,
    MILKMAN_THE,
    SILENT_NIGHT,
    Titles,
    get_safe_title,
)
from .comics_consts import (
    BOUNDED_SUBDIR,
    IMAGES_SUBDIR,
    RESTORABLE_PAGE_TYPES,
    STORY_PAGE_TYPES,
    STORY_PAGE_TYPES_STR_LIST,
    THE_CHRONOLOGICAL_DIR,
    THE_CHRONOLOGICAL_DIRS_DIR,
    THE_COMICS_DIR,
    THE_YEARS_COMICS_DIR,
    PageType,
)
from .comics_utils import (
    get_abbrev_path,
    get_dest_comic_dirname,
    get_dest_comic_zip_file_stem,
    get_formatted_first_published_str,
    get_formatted_submitted_date,
)
from .fanta_comics_info import (
    CENSORED_TITLES,
    HAND_RESTORED_TITLES,
    FantaBook,
    FantaComicBookInfo,
)
from .page_classes import OriginalPage

if TYPE_CHECKING:
    from collections.abc import Callable

INTRO_TITLE_DEFAULT_FONT_SIZE = 155
INTRO_AUTHOR_DEFAULT_FONT_SIZE = 90


@dataclass
class ComicBookDirs:
    srce_dir: str
    srce_upscayled_dir: str
    srce_restored_dir: str
    srce_restored_upscayled_dir: str
    srce_restored_svg_dir: str
    srce_restored_ocr_dir: str
    srce_fixes_dir: str
    srce_upscayled_fixes_dir: str
    panel_segments_dir: str


class FixesType(Enum):
    ORIGINAL = auto()
    UPSCAYLED = auto()


class ModifiedType(Enum):
    ORIGINAL = auto()
    MODIFIED = auto()
    ADDED = auto()


@dataclass
class ComicBook:
    ini_file: str
    title: str
    title_font_file: str
    title_font_size: int
    # NOTE: Need 'issue_title' to force a series title that has
    #       changed from another title. E.g., FC 495 == Uncle Scrooge #3
    issue_title: str
    author_font_size: int

    srce_dir_num_page_files: int
    dirs: ComicBookDirs

    intro_inset_file: str | zipfile.Path
    config_page_images: list[OriginalPage]
    page_images_in_order: list[OriginalPage]

    publication_date: str
    submitted_date: str
    publication_text: str

    fanta_book: FantaBook
    fanta_info: FantaComicBookInfo

    # TODO(glk): Eventually just use fanta_info.comic_book_info.chronological_number
    @property
    def chronological_number(self) -> int:
        return self.fanta_info.fanta_chronological_number

    @property
    def submitted_year(self) -> int:
        return self.fanta_info.comic_book_info.submitted_year

    @property
    def series_name(self) -> str:
        return self.fanta_info.series_name

    @property
    def number_in_series(self) -> int:
        return self.fanta_info.number_in_series

    def __post_init__(self) -> None:
        assert self.series_name != ""
        assert self.number_in_series > 0
        assert self.title or not self.is_barks_title()

    def is_barks_title(self) -> bool:
        return self.fanta_info.comic_book_info.is_barks_title

    def get_fanta_volume(self) -> int:
        return self.fanta_book.volume

    @staticmethod
    def _get_image_subdir(dirpath: str) -> str:
        return os.path.join(dirpath, IMAGES_SUBDIR)

    def get_srce_image_dir(self) -> str:
        return self._get_image_subdir(self.dirs.srce_dir)

    def get_srce_upscayled_image_dir(self) -> str:
        return self._get_image_subdir(self.dirs.srce_upscayled_dir)

    def get_srce_restored_image_dir(self) -> str:
        return self._get_image_subdir(self.dirs.srce_restored_dir)

    def get_srce_restored_upscayled_image_dir(self) -> str:
        return self._get_image_subdir(self.dirs.srce_restored_upscayled_dir)

    def get_srce_restored_svg_image_dir(self) -> str:
        return self._get_image_subdir(self.dirs.srce_restored_svg_dir)

    def get_srce_restored_ocr_image_dir(self) -> str:
        return self._get_image_subdir(self.dirs.srce_restored_ocr_dir)

    def get_srce_original_fixes_image_dir(self) -> str:
        return self._get_image_subdir(self.dirs.srce_fixes_dir)

    def get_srce_upscayled_fixes_image_dir(self) -> str:
        return self._get_image_subdir(self.dirs.srce_upscayled_fixes_dir)

    def get_srce_original_fixes_bounded_dir(self) -> str:
        return os.path.join(self.get_srce_original_fixes_image_dir(), BOUNDED_SUBDIR)

    def get_srce_original_story_files(self, page_types: list[PageType]) -> list[str]:
        return self._get_story_files(page_types, self._get_srce_original_story_file)

    def get_srce_upscayled_story_files(self, page_types: list[PageType]) -> list[str]:
        return self._get_story_files(page_types, self.get_srce_upscayled_story_file)

    def get_srce_restored_story_files(self, page_types: list[PageType]) -> list[str]:
        return self._get_story_files(page_types, self._get_srce_restored_story_file)

    def get_srce_restored_upscayled_story_files(self, page_types: list[PageType]) -> list[str]:
        return self._get_story_files(page_types, self.get_srce_restored_upscayled_story_file)

    def get_srce_restored_svg_story_files(self, page_types: list[PageType]) -> list[str]:
        return self._get_story_files(page_types, self.get_srce_restored_svg_story_file)

    def get_srce_restored_ocr_story_files(
        self,
        page_types: list[PageType],
    ) -> list[tuple[str, str]]:
        all_files = []
        for page in self.page_images_in_order:
            if page.page_type in page_types:
                all_files.append(self._get_srce_restored_ocr_story_file(page.page_filenames))

        return all_files

    def get_srce_panel_segments_files(self, page_types: list[PageType]) -> list[str]:
        return self._get_story_files(page_types, self.get_srce_panel_segments_file)

    def get_final_srce_original_story_files(
        self,
        page_types: list[PageType],
    ) -> list[tuple[str, ModifiedType]]:
        return self._get_story_files_with_mods(page_types, self.get_final_srce_original_story_file)

    def get_final_srce_upscayled_story_files(
        self,
        page_types: list[PageType],
    ) -> list[tuple[str, ModifiedType]]:
        return self._get_story_files_with_mods(page_types, self.get_final_srce_upscayled_story_file)

    def get_final_srce_story_files(
        self,
        page_types: None | list[PageType],
    ) -> list[tuple[str, ModifiedType]]:
        return self._get_story_files_with_mods(page_types, self.get_final_srce_story_file)

    def _get_story_files(
        self,
        page_types: list[PageType],
        get_story_file: Callable[[str], str],
    ) -> list[str]:
        all_files = []
        for page in self.page_images_in_order:
            if page.page_type in page_types:
                all_files.append(get_story_file(page.page_filenames))

        return all_files

    def _get_story_files_with_mods(
        self,
        page_types: list[PageType],
        get_story_file: Callable[[str, PageType], tuple[str, ModifiedType]],
    ) -> list[tuple[str, ModifiedType]]:
        all_files = []
        for page in self.page_images_in_order:
            if page.page_type in page_types:
                all_files.append(get_story_file(page.page_filenames, page.page_type))

        return all_files

    def _get_srce_original_story_file(self, page_num: str) -> str:
        return os.path.join(self.get_srce_image_dir(), page_num + JPG_FILE_EXT)

    def get_srce_upscayled_story_file(self, page_num: str) -> str:
        return os.path.join(self.get_srce_upscayled_image_dir(), page_num + PNG_FILE_EXT)

    def _get_srce_restored_story_file(self, page_num: str) -> str:
        return os.path.join(self.get_srce_restored_image_dir(), page_num + PNG_FILE_EXT)

    def get_srce_restored_upscayled_story_file(self, page_num: str) -> str:
        return os.path.join(self.get_srce_restored_upscayled_image_dir(), page_num + PNG_FILE_EXT)

    def get_srce_restored_svg_story_file(self, page_num: str) -> str:
        return os.path.join(self.get_srce_restored_svg_image_dir(), page_num + SVG_FILE_EXT)

    def _get_srce_restored_ocr_story_file(self, page_num: str) -> tuple[str, str]:
        return (
            os.path.join(
                self.dirs.srce_restored_ocr_dir,
                page_num + ".easyocr" + JSON_FILE_EXT,
            ),
            os.path.join(
                self.dirs.srce_restored_ocr_dir,
                page_num + ".paddleocr" + JSON_FILE_EXT,
            ),
        )

    def get_srce_panel_segments_file(self, page_num: str) -> str:
        return os.path.join(self.dirs.panel_segments_dir, page_num + JSON_FILE_EXT)

    def get_srce_original_fixes_story_file(self, page_num: str) -> str:
        jpg_fixes_file = os.path.join(
            self.get_srce_original_fixes_image_dir(),
            page_num + JPG_FILE_EXT,
        )
        png_fixes_file = os.path.join(
            self.get_srce_original_fixes_image_dir(),
            page_num + PNG_FILE_EXT,
        )
        if os.path.isfile(jpg_fixes_file) and os.path.isfile(png_fixes_file):
            msg = f'Cannot have both .jpg and .png fixes file "{jpg_fixes_file}"'
            raise RuntimeError(msg)

        if os.path.isfile(jpg_fixes_file):
            return jpg_fixes_file

        return png_fixes_file

    def get_srce_upscayled_fixes_story_file(self, page_num: str) -> str:
        return os.path.join(self.get_srce_upscayled_fixes_image_dir(), page_num + PNG_FILE_EXT)

    def get_final_srce_original_story_file(
        self,
        page_num: str,
        page_type: PageType,
    ) -> tuple[str, ModifiedType]:
        srce_file = self._get_srce_original_story_file(page_num)
        srce_fixes_file = self.get_srce_original_fixes_story_file(page_num)

        return self._get_final_story_file(
            FixesType.ORIGINAL,
            page_num,
            page_type,
            srce_file,
            srce_fixes_file,
        )

    def get_final_srce_upscayled_story_file(
        self,
        page_num: str,
        page_type: PageType,
    ) -> tuple[str, ModifiedType]:
        srce_file = self._get_srce_original_story_file(page_num)
        srce_upscayled_fixes_file = os.path.join(
            self.get_srce_upscayled_fixes_image_dir(),
            page_num + JPG_FILE_EXT,
        )
        if os.path.isfile(srce_upscayled_fixes_file):
            msg = f'Upscayled fixes file must be .png not .jpg: "{srce_upscayled_fixes_file}".'
            raise RuntimeError(msg)
        srce_upscayled_fixes_file = self.get_srce_upscayled_fixes_story_file(page_num)
        srce_upscayled_file = self.get_srce_upscayled_story_file(page_num)

        final_file, mod_type = self._get_final_story_file(
            FixesType.UPSCAYLED,
            page_num,
            page_type,
            srce_file,
            srce_upscayled_fixes_file,
        )

        if mod_type == ModifiedType.ORIGINAL:
            final_file = srce_upscayled_file
        elif os.path.isfile(srce_upscayled_file):
            msg = (
                f"Cannot have an upscayled file and a fixes file:"
                f' "{srce_upscayled_file}" and "{srce_upscayled_fixes_file}".'
            )
            raise RuntimeError(msg)

        return final_file, mod_type

    def get_final_srce_story_file(
        self,
        page_num: str,
        page_type: PageType,
    ) -> tuple[str, ModifiedType]:
        if page_type == PageType.TITLE:
            return "TITLE PAGE", ModifiedType.ORIGINAL
        if page_type == PageType.BLANK_PAGE:
            return "EMPTY PAGE", ModifiedType.ORIGINAL

        if self.get_ini_title() not in HAND_RESTORED_TITLES and page_type in RESTORABLE_PAGE_TYPES:
            srce_restored_file = os.path.join(
                self.get_srce_restored_image_dir(),
                page_num + JPG_FILE_EXT,
            )
            if os.path.isfile(srce_restored_file):
                msg = f'Restored files should be png not jpg: "{srce_restored_file}".'
                raise RuntimeError(msg)

            srce_restored_file = self._get_srce_restored_story_file(page_num)
            if os.path.isfile(srce_restored_file):
                return srce_restored_file, ModifiedType.ORIGINAL

            msg = (
                f'Could not find restored source file "{srce_restored_file}"'
                f' of type "{page_type.name}"'
            )
            raise FileNotFoundError(msg)

        srce_file, mod_type = self.get_final_srce_original_story_file(page_num, page_type)
        if os.path.isfile(srce_file):
            return srce_file, mod_type

        msg = f'Could not find source file "{srce_file}" of type "{page_type.name}"'
        raise FileNotFoundError(msg)

    def _get_final_story_file(
        self,
        file_type: FixesType,
        page_num: str,
        page_type: PageType,
        primary_file: str,
        fixes_file: str,
    ) -> tuple[str, ModifiedType]:
        if not os.path.isfile(fixes_file):
            return primary_file, ModifiedType.ORIGINAL

        # Fixes file exists - use it unless a special case.
        if os.path.isfile(primary_file):
            # Fixes file is an EDITED file.
            if self._is_edited_fixes_special_case(page_num):
                logger.info(
                    f"NOTE: Special case - using EDITED {page_type.name}"
                    f" {file_type.name} fixes file:"
                    f' "{get_abbrev_path(fixes_file)}".',
                )
            else:
                logger.info(
                    f"NOTE: Using EDITED {file_type.name}"
                    f' fixes file: "{get_abbrev_path(fixes_file)}".',
                )
                if page_type not in STORY_PAGE_TYPES:
                    msg = (
                        f"EDITED {file_type.name} fixes page '{page_num}',"
                        f' must be in "{", ".join(STORY_PAGE_TYPES_STR_LIST)}"'
                    )
                    raise RuntimeError(msg)
            mod_type = ModifiedType.MODIFIED
        elif self._is_added_fixes_special_case(page_num, page_type):
            # Fixes file is a special case ADDED file.
            logger.info(
                f"NOTE: Special case - using ADDED {file_type.name} fixes file"
                f' for {page_type.name} page: "{get_abbrev_path(fixes_file)}".',
            )
            mod_type = ModifiedType.ADDED
        else:
            # Fixes file is an ADDED file - must not be a COVER or BODY page.
            logger.info(
                f"NOTE: Using ADDED {file_type.name} fixes file of type {page_type.name}:"
                f' "{get_abbrev_path(fixes_file)}".',
            )
            if page_type in STORY_PAGE_TYPES:
                msg = (
                    f"ADDED {file_type.name} page '{page_num}',"
                    f' must NOT be in "{", ".join(STORY_PAGE_TYPES_STR_LIST)}"'
                )
                raise RuntimeError(msg)
            mod_type = ModifiedType.ADDED

        return fixes_file, mod_type

    @staticmethod
    def is_fixes_special_case(volume: int, page_num: str) -> bool:
        if volume == 16 and page_num == "209":
            return True
        if volume == 4 and page_num == "227":  # Bill collectors
            return True

        return False

    @staticmethod
    def is_fixes_special_case_added(volume: int, page_num: str) -> bool:
        if volume == 4 and page_num == "227":  # Restored Bill Collectors
            return True
        if volume == 7 and page_num == "240":  # Copied from volume 8, jpeg 31
            return True
        if volume == 7 and page_num == "241":  # Copied from volume 8, jpeg 32
            return True
        if volume == 16 and page_num == "235":  # Copied from volume 14, jpeg 145
            return True
        if volume == 2 and page_num in [
            "252",
            "253",
            "254",
            "255",
            "256",
            "257",
        ]:  # Non-comic title
            return True
        if volume == 7 and page_num in [
            "260",
            "261",
            "262",
            "263",
            "264",
            "265",
            "266",
        ]:  # Non-comic title
            return True

        return False

    def _is_edited_fixes_special_case(self, page_num: str) -> bool:
        return bool(self.fanta_book.volume == 16 and page_num == "209")

    def _is_added_fixes_special_case(self, page_num: str, page_type: PageType) -> bool:
        if self.is_fixes_special_case_added(self.fanta_book.volume, page_num):
            return True
        if self.get_ini_title() in CENSORED_TITLES:
            return page_type == PageType.BODY

        return False

    def get_story_file_sources(self, page_num: str) -> list[str]:
        srce_restored_file = self._get_srce_restored_story_file(page_num)
        srce_upscayled_file = self.get_srce_upscayled_story_file(page_num)
        srce_upscayled_fixes_file = self.get_srce_upscayled_fixes_story_file(page_num)
        srce_original_file = self._get_srce_original_story_file(page_num)
        srce_original_fixes_file = self.get_srce_original_fixes_story_file(page_num)

        sources = []

        if os.path.isfile(srce_restored_file):
            sources.append(srce_restored_file)

        if os.path.isfile(srce_upscayled_fixes_file):
            sources.append(srce_upscayled_fixes_file)
        elif os.path.isfile(srce_upscayled_file):
            sources.append(srce_upscayled_file)

        if os.path.isfile(srce_original_fixes_file):
            sources.append(srce_original_fixes_file)
        elif os.path.isfile(srce_original_file):
            sources.append(srce_original_file)

        return sources

    def get_final_fixes_panel_bounds_file(self, page_num: int) -> str:
        panels_bounds_file = os.path.join(
            self.get_srce_original_fixes_bounded_dir(),
            get_page_str(page_num) + JPG_FILE_EXT,
        )

        if os.path.isfile(panels_bounds_file):
            return panels_bounds_file

        return ""

    # TODO: Should dest stuff be elsewhere??
    @staticmethod
    def get_dest_root_dir() -> str:
        return THE_CHRONOLOGICAL_DIRS_DIR

    def get_dest_dir(self) -> str:
        return os.path.join(
            self.get_dest_root_dir(),
            self.get_dest_rel_dirname(),
        )

    def get_dest_rel_dirname(self) -> str:
        return get_dest_comic_dirname(
            _get_lookup_title(self.title, self.get_ini_title()),
            self.chronological_number,
        )

    def get_series_comic_title(self) -> str:
        return f"{self.series_name} {self.number_in_series}"

    def get_dest_image_dir(self) -> str:
        return os.path.join(self.get_dest_dir(), IMAGES_SUBDIR)

    @staticmethod
    def get_dest_zip_root_dir() -> str:
        return THE_CHRONOLOGICAL_DIR

    def get_dest_series_zip_symlink_dir(self) -> str:
        return os.path.join(
            THE_COMICS_DIR,
            self.series_name,
        )

    def get_dest_year_zip_symlink_dir(self) -> str:
        return os.path.join(
            THE_YEARS_COMICS_DIR,
            str(self.submitted_year),
        )

    def get_dest_comic_zip_filename(self) -> str:
        return f"{self.get_title_with_issue_num()}.cbz"

    def get_dest_comic_zip(self) -> str:
        return os.path.join(self.get_dest_zip_root_dir(), self.get_dest_comic_zip_filename())

    def get_dest_series_comic_zip_symlink_filename(self) -> str:
        file_title = _get_lookup_title(self.title, self.get_ini_title())
        full_title = f"{file_title} [{self.get_comic_issue_title()}]"
        return f"{self.number_in_series:03d} {full_title}.cbz"

    def get_dest_series_comic_zip_symlink(self) -> str:
        return os.path.join(
            f"{self.get_dest_series_zip_symlink_dir()}",
            f"{self.get_dest_series_comic_zip_symlink_filename()}",
        )

    def get_dest_year_comic_zip_symlink(self) -> str:
        return os.path.join(
            f"{self.get_dest_year_zip_symlink_dir()}",
            f"{self.get_dest_comic_zip_filename()}",
        )

    def get_ini_title(self) -> str:
        return Path(self.ini_file).stem

    def get_title_enum(self) -> Titles:
        return BARKS_TITLE_DICT[self.get_ini_title()]

    def get_comic_title(self) -> str:
        if self.title != "":
            return self.title
        if self.issue_title != "":
            return self.issue_title

        return self.fanta_info.comic_book_info.get_formatted_title_from_issue_name()

    def get_comic_issue_title(self) -> str:
        return self.fanta_info.get_short_issue_title()

    def get_title_with_issue_num(self) -> str:
        return get_dest_comic_zip_file_stem(
            _get_lookup_title(self.title, self.get_ini_title()),
            self.chronological_number,
            self.get_comic_issue_title(),
        )


def _get_lookup_title(title: str, file_title: str) -> str:
    if title != "":
        return get_safe_title(title)

    assert file_title != ""
    return file_title


def get_main_publication_info(
    file_title: str,
    fanta_info: FantaComicBookInfo,
    fanta_book: FantaBook,
) -> str:
    first_published = get_formatted_first_published_str(fanta_info.comic_book_info)
    submitted_date = get_formatted_submitted_date(fanta_info.comic_book_info)

    if file_title == SILENT_NIGHT:
        # Originally intended for WDCS 64
        return (
            f"(*) Rejected by Western editors in 1945, this story was originally\n"
            f" intended for publication in {first_published}\n"
            f"Submitted to Western Publishing{submitted_date}\n"
        )
    if file_title == MILKMAN_THE:
        # Originally intended for WDCS 215
        return (
            f"(*) Rejected by Western editors in 1957, this story was originally\n"
            f" intended for publication in {first_published}\n"
            f"Submitted to Western Publishing{submitted_date}\n"
            "\n"
            f"Color restoration by {fanta_info.colorist}"
        )

    if file_title == GOOD_DEEDS:
        fanta_pub_info = ""
    else:
        fanta_pub_info = (
            "\n"
            f"This edition published in {fanta_book.pub} CBDL,"
            f" Volume {fanta_book.volume}, {fanta_book.year}\n"
            f"Color restoration by {fanta_info.colorist}"
        )

    return (
        f"First published in {first_published}\n"
        f"Submitted to Western Publishing{submitted_date}\n"
        f"{fanta_pub_info}"
    )


def _get_pages_in_order(config_pages: list[OriginalPage]) -> list[OriginalPage]:
    page_images = []
    for config_page in config_pages:
        if "-" not in config_page.page_filenames:
            page_images.append(config_page)
        else:
            start, end = config_page.page_filenames.split("-")
            start_num = int(start)
            end_num = int(end)
            for file_num in range(start_num, end_num + 1):
                filename = get_page_str(file_num)
                page_images.append(OriginalPage(filename, config_page.page_type))

    return page_images


def get_page_str(page_num: int) -> str:
    return f"{page_num:03d}"


def get_page_num_str(filename: str) -> str:
    return Path(filename).stem


def get_story_files(image_dir: str, comic: ComicBook, file_ext: str) -> list[str]:
    return get_story_files_of_page_type(image_dir, comic, file_ext, STORY_PAGE_TYPES)


def get_story_files_of_page_type(
    image_dir: str,
    comic: ComicBook,
    file_ext: str,
    page_types: list[PageType],
) -> list[str]:
    srce_pages = comic.page_images_in_order
    all_files = []
    for page in srce_pages:
        if page.page_type in page_types:
            all_files.append(os.path.join(image_dir, page.page_filenames + file_ext))

    return all_files


def get_abbrev_jpg_page_list(comic: ComicBook) -> list[str]:
    return get_abbrev_jpg_page_of_type_list(comic, STORY_PAGE_TYPES)


def get_abbrev_jpg_page_of_type_list(comic: ComicBook, page_types: list[PageType]) -> list[str]:
    all_pages = []
    for page in comic.config_page_images:
        if page.page_type in page_types:
            all_pages.append(page.page_filenames)

    return all_pages


def get_jpg_page_list(comic: ComicBook) -> list[str]:
    return get_jpg_page_of_type_list(comic, STORY_PAGE_TYPES)


def get_jpg_page_of_type_list(comic: ComicBook, page_types: list[PageType]) -> list[str]:
    all_pages = []
    for page in comic.page_images_in_order:
        if page.page_type in page_types:
            all_pages.append(page.page_filenames)

    return all_pages


def get_has_front(comic: ComicBook) -> bool:
    return comic.page_images_in_order[0].page_type == PageType.FRONT


def get_num_splashes(comic: ComicBook) -> int:
    return len(get_jpg_page_of_type_list(comic, [PageType.SPLASH]))


def get_total_num_pages(comic: ComicBook) -> int:
    return len(comic.page_images_in_order)
