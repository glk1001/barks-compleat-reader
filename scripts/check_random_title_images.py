# ruff: noqa: T201

import random
import sys
from configparser import ConfigParser

from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles
from barks_fantagraphics.comics_utils import get_abbrev_path
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO, FantaComicBookInfo
from barks_reader.core.config_info import ConfigInfo
from barks_reader.core.random_title_images import RandomTitleImages
from barks_reader.core.reader_file_paths import FileTypes
from barks_reader.reader_settings_buildable import BuildableReaderSettings
from loguru import logger

if __name__ == "__main__":
    """A simple main function to test the RandomTitleImages class."""

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
            ttl = (
                BARKS_TITLES[random_image_info.from_title]
                if random_image_info.from_title is not None
                else ""
            )
            assert random_image_info.filename
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

    # ConfigParser is Protocol - ty should be OK with this.
    # noinspection PyTypeChecker,LongLine
    settings.set_config(barks_config, config_info.app_config_path, config_info.app_data_dir)  # ty: ignore[invalid-argument-type]
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
