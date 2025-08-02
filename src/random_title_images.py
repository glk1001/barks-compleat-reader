from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum, auto
from random import randrange
from typing import TYPE_CHECKING, Callable

from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles

from reader_file_paths import EMERGENCY_INSET_FILE
from reader_utils import prob_rand_less_equal

if TYPE_CHECKING:
    from pathlib import Path

    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo

    from reader_settings import ReaderSettings

NUM_RAND_ATTEMPTS = 10
MAX_IMAGE_FILENAMES_TO_KEEP = 100

SEARCH_TITLES = [
    Titles.BACK_TO_LONG_AGO,
    Titles.TRACKING_SANDY,
    Titles.SEARCH_FOR_THE_CUSPIDORIA,
]
APP_SPLASH_IMAGES = [
    "006.png",
]

FIT_MODE_CONTAIN = "contain"
FIT_MODE_COVER = "cover"


class FileTypes(Enum):
    BLACK_AND_WHITE = auto()
    CENSORSHIP = auto()
    COVER = auto()
    FAVOURITE = auto()
    INSET = auto()
    NONTITLE = auto()
    ORIGINAL_ART = auto()
    SILHOUETTE = auto()
    SPLASH = auto()


ALL_TYPES = set(FileTypes)

NON_TITLE_BIAS = 0.1


@dataclass
class ImageInfo:
    filename: Path | None = None
    from_title: Titles | None = None
    fit_mode: str = FIT_MODE_COVER


class RandomTitleImages:
    def __init__(self, reader_settings: ReaderSettings) -> None:
        self._reader_settings = reader_settings
        self._title_image_files: dict[str, dict[FileTypes, set[tuple[Path, bool]]]] = defaultdict(
            lambda: defaultdict(set)
        )

        self._most_recently_used_images: deque[Path] = deque(maxlen=MAX_IMAGE_FILENAMES_TO_KEEP)
        self._last_title_image: dict[str, Path] = {}
        self._nontitle_files = self._get_nontitle_files()

        self._FILE_TYPE_GETTERS: dict[
            FileTypes, Callable[[str, bool], None | Path | list[Path]]
        ] = {
            # COVER special case: returns single string or None
            FileTypes.COVER: self._reader_settings.file_paths.get_comic_cover_file,
            FileTypes.BLACK_AND_WHITE: self._reader_settings.file_paths.get_comic_bw_files,
            FileTypes.CENSORSHIP: self._reader_settings.file_paths.get_comic_censorship_files,
            FileTypes.FAVOURITE: self._reader_settings.file_paths.get_comic_favourite_files,
            FileTypes.INSET: self._reader_settings.file_paths.get_comic_inset_files,
            FileTypes.ORIGINAL_ART: self._reader_settings.file_paths.get_comic_original_art_files,
            FileTypes.SILHOUETTE: self._reader_settings.file_paths.get_comic_silhouette_files,
            FileTypes.SPLASH: self._reader_settings.file_paths.get_comic_splash_files,
        }

    def _add_last_image(self, image_filename: Path) -> None:
        self._most_recently_used_images.append(image_filename)

    def get_random_search_image(self) -> ImageInfo:
        title_index = randrange(0, len(SEARCH_TITLES))
        title = SEARCH_TITLES[title_index]

        return ImageInfo(
            self._get_random_comic_file(
                BARKS_TITLES[title],
                self._reader_settings.file_paths.get_comic_search_files,
                use_edited_only=False,
            ),
            title,
            FIT_MODE_COVER,
        )

    def get_loading_screen_random_image(self, title_list: list[FantaComicBookInfo]) -> Path:
        return self._get_random_image_file(
            title_list,
            {
                FileTypes.BLACK_AND_WHITE,
                FileTypes.CENSORSHIP,
                FileTypes.FAVOURITE,
                FileTypes.INSET,
                FileTypes.NONTITLE,
                FileTypes.ORIGINAL_ART,
                FileTypes.SILHOUETTE,
                FileTypes.SPLASH,
            },
        )

    def _get_random_image_file(
        self, title_list: list[FantaComicBookInfo], file_types: set[FileTypes] | None = None
    ) -> Path:
        return self.get_random_image(title_list, file_types=file_types).filename

    def get_random_image_for_title(
        self, title_str: str, file_types: set[FileTypes], use_edited_only: bool = False
    ) -> Path:
        # Ensure files are loaded for this title.
        self._update_comic_files(title_str)

        possible_images = self._get_possible_files_for_title(title_str, file_types, use_edited_only)
        if not possible_images:
            return self._reader_settings.file_paths.get_comic_inset_file(EMERGENCY_INSET_FILE)

        # Try to find an image not recently used for this title.
        preferred_images = [
            image_info
            for image_info in possible_images
            if image_info[0] != self._last_title_image.get(title_str, "")
        ]

        if preferred_images:
            selected_image_info = preferred_images[randrange(0, len(preferred_images))]
        else:
            # Fallback to any image if all have been recently used for this title.
            selected_image_info = possible_images[randrange(0, len(possible_images))]

        assert selected_image_info
        image_filename = selected_image_info[0]
        self._last_title_image[title_str] = image_filename

        return image_filename

    def get_random_image(
        self,
        title_list: list[FantaComicBookInfo],
        use_random_fit_mode: bool = False,
        file_types: set[FileTypes] | None = None,
        use_edited_only: bool = False,
    ) -> ImageInfo:
        if not title_list:
            # Handle empty title list gracefully
            return ImageInfo(
                self._reader_settings.file_paths.get_comic_inset_file(EMERGENCY_INSET_FILE),
                Titles.GOOD_NEIGHBORS,
                FIT_MODE_COVER,
            )

        actual_file_types = ALL_TYPES if file_types is None else file_types

        num_titles = len(title_list)
        if FileTypes.NONTITLE in actual_file_types:
            num_titles = int((1 + NON_TITLE_BIAS) * num_titles)  # include bias for nontitles

        for _ in range(NUM_RAND_ATTEMPTS):
            title_index = randrange(0, num_titles)
            # if title_index >= 0:
            if title_index >= len(title_list):  # handle nontitle bias
                title_str = ""
                title_enum = None
                actual_file_types = {FileTypes.NONTITLE}
                possible_files_for_title = self._nontitle_files
            else:
                title_info = title_list[randrange(0, len(title_list))]
                comic_book_info = title_info.comic_book_info
                title_enum = comic_book_info.title
                title_str = comic_book_info.get_title_str()

                # Ensure files are loaded for title.
                self._update_comic_files(title_str)

                possible_files_for_title = self._get_possible_files_for_title(
                    title_str, actual_file_types, use_edited_only
                )

            if not possible_files_for_title:
                continue

            # Candidate selection preference:
            # 1. Not in global MRU AND not last image for this specific title.
            candidates = [
                (filename, file_type)
                for filename, file_type in possible_files_for_title
                if filename not in self._most_recently_used_images
                and filename != self._last_title_image.get(title_str, "")
            ]

            if not candidates:
                # 2. Fallback: Not in global MRU.
                candidates = [
                    (filename, file_type)
                    for filename, file_type in possible_files_for_title
                    if filename not in self._most_recently_used_images
                ]

            if not candidates:
                # 3. Fallback: Any image for this title (already filtered
                #              by __get_possible_files_for_title).
                candidates = possible_files_for_title

            assert candidates
            image_filename, file_type_enum = candidates[randrange(0, len(candidates))]

            fit_mode = self._get_fit_mode(use_random_fit_mode)
            image_filename, fit_mode = self._get_better_fitting_image_if_possible(
                image_filename, fit_mode, file_type_enum
            )

            self._add_last_image(image_filename)
            self._last_title_image[title_str] = image_filename
            return ImageInfo(image_filename, title_enum, fit_mode)

        # Fallback if all attempts fail,
        logging.warning("Failed to find a suitable random image after multiple attempts.")
        return ImageInfo(
            self._reader_settings.file_paths.get_comic_inset_file(EMERGENCY_INSET_FILE),
            Titles.GOOD_NEIGHBORS,
            FIT_MODE_COVER,
        )

    def _get_fit_mode(self, use_random_fit_mode: bool) -> str:
        if use_random_fit_mode:
            return self._get_random_fit_mode()

        return FIT_MODE_COVER

    @staticmethod
    def _get_random_fit_mode() -> str:
        return FIT_MODE_COVER if prob_rand_less_equal(50) else FIT_MODE_CONTAIN

    def _get_better_fitting_image_if_possible(
        self, image_filename: Path, fit_mode: str, file_type_enum: FileTypes
    ) -> tuple[Path, str]:
        # If it's a cover image, and kivy fit_mode is 'cover', then try to use an edited image.
        if (file_type_enum == FileTypes.COVER) and (fit_mode == FIT_MODE_COVER):
            image_filename, is_edited = (
                self._reader_settings.file_paths.get_edited_version_if_possible(image_filename)
            )
            if is_edited:
                return image_filename, fit_mode
            return image_filename, FIT_MODE_CONTAIN

        return image_filename, fit_mode

    def _get_possible_files_for_title(
        self, title_str: str, file_types: set[FileTypes], use_edited_only: bool
    ) -> list[tuple[Path, FileTypes]]:
        possible_files: list[tuple[Path, FileTypes]] = []
        for file_type in file_types:
            if file_type in self._title_image_files.get(title_str, {}):
                for filename, is_edited in self._title_image_files[title_str][file_type]:
                    if is_edited == use_edited_only:
                        possible_files.append((filename, file_type))

        return possible_files

    def _get_nontitle_files(self) -> list[tuple[Path, FileTypes]]:
        return [
            (file, FileTypes.NONTITLE)
            for file in self._reader_settings.file_paths.get_nontitle_files()
        ]

    def _update_comic_files(self, title_str: str) -> None:
        # Check if already processed.
        if title_str in self._title_image_files:
            return

        for file_type, getter_func in self._FILE_TYPE_GETTERS.items():
            for use_edited in [False, True]:
                if file_type == FileTypes.COVER:
                    # getter for COMIC returns a single string or None
                    image_file = getter_func(title_str, use_edited)
                    if image_file:
                        self._add_image_files({image_file}, title_str, file_type, use_edited)
                else:
                    # Other getters return a List[str]
                    image_files = getter_func(title_str, use_edited)
                    if image_files:
                        self._add_image_files(set(image_files), title_str, file_type, use_edited)

    def _add_image_files(
        self, image_files: set[Path], title_str: str, file_type: FileTypes, use_edited_only: bool
    ) -> None:
        new_files = {(f, use_edited_only) for f in image_files}
        self._title_image_files[title_str][file_type].update(new_files)

    @staticmethod
    def _get_random_comic_file(
        title_str: str, get_files_func: Callable[[str, bool], list[Path]], use_edited_only: bool
    ) -> Path:
        title_files = get_files_func(title_str, use_edited_only)
        if title_files:
            index = randrange(0, len(title_files))
            return title_files[index]

        raise AssertionError
