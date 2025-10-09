from __future__ import annotations

import random
from collections import defaultdict, deque
from dataclasses import dataclass
from random import randrange
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import BARKS_TITLES, VACATION_TIME, Titles
from barks_fantagraphics.comics_utils import get_abbrev_path
from loguru import logger

from barks_reader.image_file_getter import TitleImageFileGetter
from barks_reader.reader_file_paths import ALL_TYPES, EMERGENCY_INSET_FILE, FileTypes
from barks_reader.reader_utils import get_all_files_in_dir, prob_rand_less_equal

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo

    from barks_reader.reader_consts_and_types import PanelPath
    from barks_reader.reader_settings import ReaderSettings

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

type PossibleFiles = list[tuple[Path, FileTypes]]

NON_TITLE_BIAS = 0.1


@dataclass
class ImageInfo:
    filename: PanelPath | None = None
    from_title: Titles | None = None
    fit_mode: str = FIT_MODE_COVER


class RandomTitleImages:
    def __init__(self, reader_settings: ReaderSettings) -> None:
        self._reader_settings = reader_settings

        self._title_image_files: dict[str, dict[FileTypes, set[tuple[Path, bool]]]] = defaultdict(
            lambda: defaultdict(set)
        )
        self._title_image_file_getter = TitleImageFileGetter(self._reader_settings)

        self._most_recently_used_images: deque[Path] = deque(maxlen=MAX_IMAGE_FILENAMES_TO_KEEP)
        self._last_title_image: dict[str, Path] = {}
        self._nontitle_files = self._get_nontitle_files()

    def _add_last_image(self, image_filename: Path) -> None:
        self._most_recently_used_images.append(image_filename)

    def get_random_search_image(self) -> ImageInfo:
        title_index = randrange(0, len(SEARCH_TITLES))
        title = SEARCH_TITLES[title_index]

        return ImageInfo(
            self._get_random_comic_file(
                BARKS_TITLES[title],
                self._reader_settings.file_paths.get_comic_search_files,
                use_only_edited_if_possible=False,
            ),
            title,
            FIT_MODE_COVER,
        )

    def get_reader_app_icon_file(self) -> Path:
        icon_files = get_all_files_in_dir(
            self._reader_settings.sys_file_paths.get_reader_icon_files_dir(),
        )
        file_index = randrange(0, len(icon_files))
        return icon_files[file_index]

    def get_random_censorship_fix_image(self) -> ImageInfo:
        title = Titles.VACATION_TIME
        file1 = (
            self._reader_settings.file_paths.get_comic_favourite_files_dir()
            / VACATION_TIME
            / ("076-8-flipped" + self._reader_settings.file_paths.get_file_ext())
        )
        return ImageInfo(file1, title, FIT_MODE_COVER)

    def get_loading_screen_random_image(self, title_list: list[FantaComicBookInfo]) -> Path:
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
    ) -> Path:
        return self.get_random_image(title_list, file_types=file_types).filename

    def get_random_image_for_title(
        self, title_str: str, file_types: set[FileTypes], use_only_edited_if_possible: bool = False
    ) -> Path:
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
        use_only_edited_if_possible: bool = False,
    ) -> ImageInfo:
        if not title_list:
            # Handle empty title list gracefully
            return ImageInfo(
                self._reader_settings.file_paths.get_comic_inset_file(EMERGENCY_INSET_FILE),
                Titles.GOOD_NEIGHBORS,
                FIT_MODE_COVER,
            )

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
        return ImageInfo(
            self._reader_settings.file_paths.get_comic_inset_file(EMERGENCY_INSET_FILE),
            Titles.GOOD_NEIGHBORS,
            FIT_MODE_COVER,
        )

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

        title_info = title_list[randrange(0, len(title_list))]
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
    ) -> tuple[Path, FileTypes] | None:
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

        return candidates[randrange(0, len(candidates))]

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
        self, title_str: str, file_types: set[FileTypes], use_only_edited_if_possible: bool
    ) -> PossibleFiles:
        possible_files: list[tuple[Path, FileTypes]] = []

        for file_type in file_types:
            if file_type in self._title_image_files.get(title_str, {}):
                for filename, is_edited in self._title_image_files[title_str][file_type]:
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
        get_files_func: Callable[[str, bool], list[Path]],
        use_only_edited_if_possible: bool,
    ) -> Path:
        title_files = get_files_func(title_str, use_only_edited_if_possible)
        if title_files:
            index = randrange(0, len(title_files))
            return title_files[index]

        raise AssertionError


# ruff: noqa: T201
if __name__ == "__main__":
    """A simple main function to test the RandomTitleImages class."""
    import sys
    from configparser import ConfigParser

    from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO

    from barks_reader.config_info import ConfigInfo
    from barks_reader.reader_settings import BuildableReaderSettings

    def get_results(
        num_results: int,
        title_list: list[FantaComicBookInfo],
        use_random_fit_mode: bool = False,
        file_types: set[FileTypes] | None = None,
        use_only_edited_if_possible: bool = False,
    ) -> tuple[list[tuple[str, str, str]], int]:
        rand_results: list[tuple[str, str, str]] = []
        max_ttl_len = 0
        for _i in range(num_results):
            random_image_info = random_image_selector.get_random_image(
                title_list,
                use_random_fit_mode=use_random_fit_mode,
                file_types=file_types,
                use_only_edited_if_possible=use_only_edited_if_possible,
            )
            ttl = BARKS_TITLES[random_image_info.from_title] if random_image_info.from_title else ""
            img_file = get_abbrev_path(random_image_info.filename)
            fit = random_image_info.fit_mode
            rand_results.append((ttl, img_file, fit))
            max_ttl_len = max(max_ttl_len, len(ttl))

        return rand_results, max_ttl_len

    def show_results(rand_results: list[tuple[str, str, str]], max_ttl_len: int) -> None:
        for i, result in enumerate(rand_results):
            title = result[0]
            image_file = result[1]
            fit_mode = result[2]
            print(f'  {i + 1}: "{title:<{max_ttl_len}}", "{fit_mode:<7}", "{image_file}"')

    # --- Basic Setup ---
    # Configure logging to see the output
    logger.remove()
    logger.add(sys.stdout, level="INFO")

    # Create a minimal but functional ReaderSettings instance
    config_info = ConfigInfo()
    barks_config = ConfigParser()
    barks_config.read(config_info.app_config_path)
    settings = BuildableReaderSettings()
    settings.set_config(barks_config, config_info.app_config_path)
    settings.set_barks_panels_dir()

    # --- Test the Class ---
    print("\n--- Testing RandomTitleImages ---")
    random.seed(1)
    random_image_selector = RandomTitleImages(settings)

    # Get a list of all comic book info objects to choose from
    all_titles = list(ALL_FANTA_COMIC_BOOK_INFO.values())

    num_images = 5

    test_title_list = all_titles
    test_file_types = None
    test_use_random_fit_mode = True
    test_edited_only = False
    print(
        f"\nGenerating {num_images} random images:"
        f" num titles={len(test_title_list)},"
        f" file_types={test_file_types},"
        f" random_fit_mode={test_use_random_fit_mode},"
        f" edited_only={test_edited_only}"
    )
    print()
    results, max_title_len = get_results(
        num_images,
        test_title_list,
        use_random_fit_mode=test_use_random_fit_mode,
        file_types=test_file_types,
        use_only_edited_if_possible=test_edited_only,
    )
    show_results(results, max_title_len)

    test_title_list = all_titles
    test_file_types = {FileTypes.AI}
    test_use_random_fit_mode = False
    test_edited_only = True
    print(
        f"\nGenerating {num_images} random images:"
        f" num titles={len(test_title_list)},"
        f" file_types={test_file_types},"
        f" random_fit_mode={test_use_random_fit_mode},"
        f" edited_only={test_edited_only}"
    )
    print()
    results, max_title_len = get_results(
        num_images,
        test_title_list,
        use_random_fit_mode=test_use_random_fit_mode,
        file_types=test_file_types,
        use_only_edited_if_possible=test_edited_only,
    )
    show_results(results, max_title_len)

    test_title_list = all_titles
    test_file_types = {FileTypes.INSET}
    test_use_random_fit_mode = True
    test_edited_only = True
    print(
        f"\nGenerating {num_images} random images:"
        f" num titles={len(test_title_list)},"
        f" file_types={test_file_types},"
        f" random_fit_mode={test_use_random_fit_mode},"
        f" edited_only={test_edited_only}"
    )
    print()
    results, max_title_len = get_results(
        num_images,
        test_title_list,
        use_random_fit_mode=test_use_random_fit_mode,
        file_types=test_file_types,
        use_only_edited_if_possible=test_edited_only,
    )
    show_results(results, max_title_len)

    test_titles = [Titles.MAHARAJAH_DONALD, Titles.DONALD_DUCK_AND_THE_MUMMYS_RING]
    test_title_list = [ALL_FANTA_COMIC_BOOK_INFO[BARKS_TITLES[title]] for title in test_titles]
    test_file_types = {FileTypes.AI}
    test_use_random_fit_mode = False
    test_edited_only = True
    print(
        f"\nGenerating {num_images} random images:"
        f" num titles={len(test_title_list)},"
        f" file_types={test_file_types},"
        f" random_fit_mode={test_use_random_fit_mode},"
        f" edited_only={test_edited_only}"
    )
    print()
    results, max_title_len = get_results(
        num_images,
        test_title_list,
        use_random_fit_mode=test_use_random_fit_mode,
        file_types=test_file_types,
        use_only_edited_if_possible=test_edited_only,
    )
    show_results(results, max_title_len)
