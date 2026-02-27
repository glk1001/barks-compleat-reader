from __future__ import annotations

import random
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from random import randrange
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import (
    BARKS_TITLES,
    PIXILATED_PARROT_THE,
    VACATION_TIME,
    Titles,
)
from loguru import logger

from barks_reader.core.image_file_getter import TitleImageFileGetter
from barks_reader.core.reader_file_paths import ALL_TYPES, EMERGENCY_INSET_FILE, FileTypes
from barks_reader.core.reader_utils import get_all_files_in_dir

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from comic_utils.comic_consts import PanelPath

    from barks_reader.core.reader_settings import ReaderSettings

NUM_RAND_ATTEMPTS = 10
MAX_IMAGE_FILENAMES_TO_KEEP = 100

SEARCH_TITLES = [
    Titles.BACK_TO_LONG_AGO,
    Titles.TRACKING_SANDY,
    Titles.SEARCH_FOR_THE_CUSPIDORIA,
]

FIT_MODE_CONTAIN = "contain"
FIT_MODE_COVER = "cover"

type PossibleFiles = list[tuple[PanelPath, FileTypes]]

NON_TITLE_BIAS = 0.1


@dataclass(frozen=True, slots=True)
class ImageInfo:
    filename: PanelPath | None = None
    from_title: Titles | None = None
    fit_mode: str = FIT_MODE_COVER


def get_title_str(title: Titles | None) -> str:
    return BARKS_TITLES[title] if title is not None else ""


class RandomTitleImages:
    def __init__(self, reader_settings: ReaderSettings) -> None:
        self._reader_settings = reader_settings

        self._title_image_files: dict[str, dict[FileTypes, set[tuple[PanelPath, bool]]]] = (
            defaultdict(lambda: defaultdict(set))
        )
        self._title_image_file_getter = TitleImageFileGetter(self._reader_settings)

        self._most_recently_used_images: deque[PanelPath] = deque(
            maxlen=MAX_IMAGE_FILENAMES_TO_KEEP
        )
        self._last_title_image: dict[str, PanelPath] = {}
        self._nontitle_files = self._get_nontitle_files()

        self._all_reader_icon_files = get_all_files_in_dir(
            self._reader_settings.sys_file_paths.get_reader_icon_files_dir()
        )
        random.shuffle(self._all_reader_icon_files)
        self._next_reader_icon_file = 0

        self._CENSORED_IMAGES = self._get_censored_images()

    def _add_last_image(self, image_filename: PanelPath) -> None:
        self._most_recently_used_images.append(image_filename)

    def _get_fallback_image_info(self) -> ImageInfo:
        return ImageInfo(
            self._reader_settings.file_paths.get_comic_inset_file(EMERGENCY_INSET_FILE),
            Titles.GOOD_NEIGHBORS,
            FIT_MODE_COVER,
        )

    def _get_censored_images(self) -> list[tuple[Titles, str]]:
        file_ext = self._reader_settings.file_paths.get_file_ext()

        return [
            (
                Titles.VACATION_TIME,
                self._get_posix_join(VACATION_TIME, f"076-8-flipped{file_ext}"),
            ),
            (
                Titles.VACATION_TIME,
                self._get_posix_join(VACATION_TIME, f"083-7-flipped{file_ext}"),
            ),
            (
                Titles.PIXILATED_PARROT_THE,
                self._get_posix_join(PIXILATED_PARROT_THE, f"017-4{file_ext}"),
            ),
        ]

    @staticmethod
    def _get_posix_join(filepart1: str, filepart2: str) -> str:
        return str((Path(filepart1) / filepart2).as_posix())

    def get_random_search_image(self) -> ImageInfo:
        title = random.choice(SEARCH_TITLES)

        return ImageInfo(
            self._get_random_comic_file(
                BARKS_TITLES[title],
                self._reader_settings.file_paths.get_comic_search_files,
                use_only_edited_if_possible=False,
            ),
            title,
            FIT_MODE_COVER,
        )

    def get_random_reader_app_icon_file(self) -> Path:
        icon_path = self._all_reader_icon_files[self._next_reader_icon_file]

        self._next_reader_icon_file = (self._next_reader_icon_file + 1) % len(
            self._all_reader_icon_files
        )

        assert isinstance(icon_path, Path)
        return icon_path

    def get_random_censorship_fix_image(self) -> ImageInfo:
        title, file = random.choice(self._CENSORED_IMAGES)

        return ImageInfo(
            self._reader_settings.file_paths.get_comic_favourite_files_dir() / file,
            title,
            FIT_MODE_COVER,
        )

    def get_loading_screen_random_image(self, title_list: list[FantaComicBookInfo]) -> PanelPath:
        return self._get_random_image_file(
            title_list,
            {
                FileTypes.BLACK_AND_WHITE,
                FileTypes.AI,
                FileTypes.CENSORSHIP,
                FileTypes.CLOSEUP,
                FileTypes.FAVOURITE,
                FileTypes.INSET,
                FileTypes.NONTITLE,
                FileTypes.ORIGINAL_ART,
                FileTypes.SILHOUETTE,
                FileTypes.SPLASH,
            },
        )

    def get_index_screen_random_image(self, title_list: list[FantaComicBookInfo]) -> PanelPath:
        return self._get_random_image_file(
            title_list,
            {
                FileTypes.BLACK_AND_WHITE,
                FileTypes.AI,
                FileTypes.CENSORSHIP,
                FileTypes.CLOSEUP,
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
    ) -> PanelPath:
        file = self.get_random_image(title_list, file_types=file_types).filename
        assert file
        return file

    def get_random_image_for_title(
        self, title_str: str, file_types: set[FileTypes], use_only_edited_if_possible: bool = False
    ) -> PanelPath:
        # Ensure files are loaded for this title.
        self._update_comic_files(title_str)

        possible_images = self._get_possible_files_for_title(
            title_str, file_types, use_only_edited_if_possible
        )
        if not possible_images:
            logger.warning(f'No possible images for title "{title_str}". Using emergency image.')
            return self._reader_settings.file_paths.get_comic_inset_file(EMERGENCY_INSET_FILE)

        # Try to find an image not recently used for this title.
        preferred_images = [
            image_info
            for image_info in possible_images
            if image_info[0] != self._last_title_image.get(title_str, "")
        ]

        if preferred_images:
            selected_image_info = random.choice(preferred_images)
        else:
            # Fallback to any image if all have been recently used for this title.
            selected_image_info = random.choice(possible_images)

        assert selected_image_info
        image_filename = selected_image_info[0]
        self._last_title_image[title_str] = image_filename

        return image_filename

    def get_random_image(
        self,
        title_list: list[FantaComicBookInfo],
        use_random_fit_mode: bool = False,
        file_types: set[FileTypes] | None = None,
        use_only_edited_if_possible: bool = False,
    ) -> ImageInfo:
        if not title_list:
            # Handle empty title list gracefully
            return self._get_fallback_image_info()

        current_file_types = ALL_TYPES if file_types is None else file_types
        logger.debug(f"File types to choose random image from: {current_file_types}.")

        for _ in range(NUM_RAND_ATTEMPTS):
            title_str, title_enum, possible_files = self._select_random_title_or_nontitle(
                title_list, current_file_types, use_only_edited_if_possible
            )

            selected_image = self._select_best_candidate_image(possible_files, title_str)
            if selected_image is None:
                continue

            image_filename, file_type_enum = selected_image
            fit_mode = self._get_fit_mode(use_random_fit_mode)

            image_filename, fit_mode = self._get_better_fitting_image_if_possible(
                image_filename, fit_mode, file_type_enum
            )

            self._add_last_image(image_filename)
            if title_str:
                self._last_title_image[title_str] = image_filename

            return ImageInfo(image_filename, title_enum, fit_mode)

        # Fallback if all attempts fail,
        logger.warning("Failed to find a suitable random image after multiple attempts.")
        return self._get_fallback_image_info()

    def _select_random_title_or_nontitle(
        self,
        title_list: list[FantaComicBookInfo],
        file_types: set[FileTypes],
        use_only_edited_if_possible: bool,
    ) -> tuple[str | None, Titles | None, PossibleFiles]:
        """Randomly select either a title from the list or a "nontitle" image."""
        if FileTypes.NONTITLE in file_types:
            # With a certain probability (defined by NON_TITLE_BIAS), choose a "nontitle" image.
            num_titles = len(title_list)
            biased_upper_bound = int((1 + NON_TITLE_BIAS) * num_titles)
            if randrange(0, biased_upper_bound) >= num_titles:
                logger.debug("Chose a nontitle image based on bias.")
                return None, None, self._nontitle_files

        title_info = random.choice(title_list)
        comic_book_info = title_info.comic_book_info
        title_enum = comic_book_info.title
        title_str = comic_book_info.get_title_str()
        logger.debug(f"Chose title '{title_str}'.")

        # Ensure files are loaded for title.
        self._update_comic_files(title_str)
        possible_files = self._get_possible_files_for_title(
            title_str, file_types, use_only_edited_if_possible
        )
        return title_str, title_enum, possible_files

    def _select_best_candidate_image(
        self, possible_files: PossibleFiles, title_str: str | None
    ) -> tuple[PanelPath, FileTypes] | None:
        """Select the best candidate image, preferring ones not recently used."""
        if not possible_files:
            return None

        # First, try to find candidates that are not in the global MRU list and
        # not the last image used for this specific title.
        candidates = [
            (filename, file_type)
            for filename, file_type in possible_files
            if filename not in self._most_recently_used_images
            and (title_str is None or filename != self._last_title_image.get(title_str, ""))
        ]

        # If the preferred filter yields no results, fall back to using all possible files.
        if not candidates:
            candidates = possible_files

        return random.choice(candidates)

    def _get_fit_mode(self, use_random_fit_mode: bool) -> str:
        if use_random_fit_mode:
            return self._get_random_fit_mode()

        return FIT_MODE_COVER

    @staticmethod
    def _get_random_fit_mode() -> str:
        return random.choice((FIT_MODE_COVER, FIT_MODE_CONTAIN))

    def _get_better_fitting_image_if_possible(
        self, image_filename: PanelPath, fit_mode: str, file_type_enum: FileTypes
    ) -> tuple[PanelPath, str]:
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
        self, title_str: str, file_types: set[FileTypes], use_only_edited_if_possible: bool
    ) -> PossibleFiles:
        possible_files: list[tuple[PanelPath, FileTypes]] = []

        title_files = self._title_image_files.get(title_str, {})
        for file_type in file_types:
            if file_type in title_files:
                for filename, is_edited in title_files[file_type]:
                    if use_only_edited_if_possible and not is_edited:
                        continue
                    possible_files.append((filename, file_type))

        return possible_files

    def _get_nontitle_files(self) -> PossibleFiles:
        return [
            (file, FileTypes.NONTITLE)
            for file in self._reader_settings.file_paths.get_nontitle_files()
        ]

    def _update_comic_files(self, title_str: str) -> None:
        # Check if already processed.
        if title_str in self._title_image_files:
            return

        logger.debug(f'Updating comic image files for title "{title_str}".')
        self._title_image_files[title_str].update(
            self._title_image_file_getter.get_all_title_image_files(title_str)
        )

    @staticmethod
    def _get_random_comic_file(
        title_str: str,
        get_files_func: Callable[[str, bool], list[PanelPath]],
        use_only_edited_if_possible: bool,
    ) -> Path:
        title_files = get_files_func(title_str, use_only_edited_if_possible)
        if title_files:
            return random.choice(title_files)

        raise AssertionError
