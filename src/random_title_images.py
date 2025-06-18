import logging
from collections import deque, defaultdict
from dataclasses import dataclass
from enum import Enum, auto
from random import randrange
from typing import List, Callable, Union, Set, Tuple, Dict

from barks_fantagraphics.barks_titles import Titles, BARKS_TITLES
from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
from file_paths import (
    EMERGENCY_INSET_FILE,
    get_comic_inset_file,
    get_comic_cover_file,
    get_comic_splash_files,
    get_comic_silhouette_files,
    get_comic_censorship_files,
    get_comic_favourite_files,
    get_comic_original_art_files,
    get_comic_search_files,
)
from reader_utils import prob_rand_less_equal

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
    COVER = auto()
    SILHOUETTE = auto()
    SPLASH = auto()
    CENSORSHIP = auto()
    FAVOURITE = auto()
    ORIGINAL_ART = auto()


ALL_TYPES = {t for t in FileTypes}
ALL_BUT_ORIGINAL_ART = {t for t in FileTypes if t != FileTypes.ORIGINAL_ART}


@dataclass
class ImageInfo:
    filename: str = ""
    from_title: Titles = Titles.GOOD_NEIGHBORS
    fit_mode: str = FIT_MODE_COVER


class RandomTitleImages:
    __FILE_TYPE_GETTERS = {
        FileTypes.COVER: get_comic_cover_file,  # Special case: returns single string or None
        FileTypes.SILHOUETTE: get_comic_silhouette_files,
        FileTypes.SPLASH: get_comic_splash_files,
        FileTypes.CENSORSHIP: get_comic_censorship_files,
        FileTypes.FAVOURITE: get_comic_favourite_files,
        FileTypes.ORIGINAL_ART: get_comic_original_art_files,
    }

    def __init__(self):
        self.title_image_files: Dict[str, Dict[FileTypes, Set[Tuple[str, bool]]]] = defaultdict(
            lambda: defaultdict(set)
        )

        self.most_recently_used_images: deque[str] = deque(maxlen=MAX_IMAGE_FILENAMES_TO_KEEP)
        self.last_title_image: Dict[str, str] = {}

    def add_last_image(self, image_filename: str) -> None:
        self.most_recently_used_images.append(image_filename)

    def get_random_search_image(self) -> ImageInfo:
        title_index = randrange(0, len(SEARCH_TITLES))
        title = SEARCH_TITLES[title_index]

        return ImageInfo(
            self.__get_random_comic_file(BARKS_TITLES[title], get_comic_search_files, False),
            title,
            FIT_MODE_COVER,
        )

    def get_loading_screen_random_image(self, title_list: List[FantaComicBookInfo]) -> str:
        return self.get_random_image_file(
            title_list,
            {FileTypes.CENSORSHIP, FileTypes.FAVOURITE, FileTypes.SILHOUETTE, FileTypes.SPLASH},
        )

    def get_random_image_file(
        self, title_list: List[FantaComicBookInfo], file_types: Union[Set[FileTypes], None] = None
    ) -> str:
        return self.get_random_image(title_list, file_types=file_types).filename

    def get_random_image_for_title(
        self, title_str: str, file_types: Set[FileTypes], use_edited_only: bool = False
    ) -> str:
        # Ensure files are loaded for this title.
        self.__update_comic_files(title_str)

        possible_images = self.__get_possible_files_for_title(
            title_str, file_types, use_edited_only
        )
        if not possible_images:
            return get_comic_inset_file(EMERGENCY_INSET_FILE)

        # Try to find an image not recently used for this title.
        preferred_images = [
            image_info
            for image_info in possible_images
            if image_info[0] != self.last_title_image.get(title_str, "")
        ]

        if preferred_images:
            selected_image_info = preferred_images[randrange(0, len(preferred_images))]
        else:
            # Fallback to any image if all have been recently used for this title.
            selected_image_info = possible_images[randrange(0, len(possible_images))]

        assert selected_image_info
        image_filename = selected_image_info[0]
        self.last_title_image[title_str] = image_filename

        return image_filename

    def get_random_image(
        self,
        title_list: List[FantaComicBookInfo],
        use_random_fit_mode=False,
        file_types: Union[Set[FileTypes], None] = None,
        use_edited_only: bool = False,
    ) -> ImageInfo:
        if not title_list:
            # Handle empty title list gracefully
            return ImageInfo(
                get_comic_inset_file(EMERGENCY_INSET_FILE), Titles.GOOD_NEIGHBORS, FIT_MODE_COVER
            )

        actual_file_types = ALL_TYPES if file_types is None else file_types

        for _ in range(NUM_RAND_ATTEMPTS):
            title_info = title_list[randrange(0, len(title_list))]
            comic_book_info = title_info.comic_book_info
            title_enum = comic_book_info.title
            title_str = comic_book_info.get_title_str()

            # Ensure files are loaded for title.
            self.__update_comic_files(title_str)

            possible_files_for_title = self.__get_possible_files_for_title(
                title_str, actual_file_types, use_edited_only
            )

            if not possible_files_for_title:
                continue

            # Candidate selection preference:
            # 1. Not in global MRU AND not last image for this specific title.
            candidates = [
                (filename, file_type)
                for filename, file_type in possible_files_for_title
                if filename not in self.most_recently_used_images
                and filename != self.last_title_image.get(title_str, "")
            ]

            if not candidates:
                # 2. Fallback: Not in global MRU.
                candidates = [
                    (filename, file_type)
                    for filename, file_type in possible_files_for_title
                    if filename not in self.most_recently_used_images
                ]

            if not candidates:
                # 3. Fallback: Any image for this title (already filtered
                #              by __get_possible_files_for_title).
                candidates = possible_files_for_title

            assert candidates
            image_filename, file_type_enum = candidates[randrange(0, len(candidates))]

            fit_mode = FIT_MODE_COVER
            if use_random_fit_mode:
                fit_mode = self.__get_random_fit_mode()
            elif file_type_enum == FileTypes.COVER:
                fit_mode = FIT_MODE_CONTAIN

            self.add_last_image(image_filename)
            self.last_title_image[title_str] = image_filename
            return ImageInfo(image_filename, title_enum, fit_mode)

        # Fallback if all attempts fail,
        logging.warning("Failed to find a suitable random image after multiple attempts.")
        return ImageInfo(
            get_comic_inset_file(EMERGENCY_INSET_FILE), Titles.GOOD_NEIGHBORS, FIT_MODE_COVER
        )

    def __get_possible_files_for_title(
        self, title_str: str, file_types: Set[FileTypes], use_edited_only: bool
    ):
        possible_files: List[Tuple[str, FileTypes]] = []
        for file_type in file_types:
            if file_type in self.title_image_files.get(title_str, {}):
                for filename, is_edited in self.title_image_files[title_str][file_type]:
                    if is_edited == use_edited_only:
                        possible_files.append((filename, file_type))

        return possible_files

    @staticmethod
    def __get_random_fit_mode() -> str:
        if prob_rand_less_equal(50):
            return FIT_MODE_COVER

        return FIT_MODE_CONTAIN

    # Inside RandomTitleImages class
    def __update_comic_files(self, title_str: str) -> None:
        # Check if already processed.
        if title_str in self.title_image_files:
            return

        for file_type, getter_func in self.__FILE_TYPE_GETTERS.items():
            for use_edited in [False, True]:
                if file_type == FileTypes.COVER:
                    # get_comic_cover_file returns a single string or None
                    image_file = getter_func(title_str, use_edited)
                    if image_file:
                        self.__add_image_files({image_file}, title_str, file_type, use_edited)
                else:
                    # Other getters return a List[str]
                    image_files = getter_func(title_str, use_edited)
                    if image_files:
                        self.__add_image_files(set(image_files), title_str, file_type, use_edited)

    def __add_image_files(
        self, image_files: Set[str], title_str: str, file_type: FileTypes, use_edited_only: bool
    ) -> None:
        new_files = {(f, use_edited_only) for f in image_files}
        self.title_image_files[title_str][file_type].update(new_files)

    @staticmethod
    def __get_random_comic_file(
        title_str: str, get_files_func: Callable[[str, bool], List[str]], use_edited_only: bool
    ) -> str:
        title_files = get_files_func(title_str, use_edited_only)
        if title_files:
            index = randrange(0, len(title_files))
            return title_files[index]

        return ""
