import os
from pathlib import Path
from typing import List, Tuple

from barks_fantagraphics.barks_titles import Titles, BARKS_TITLE_INFO, BARKS_TITLES
from barks_fantagraphics.comics_consts import JPG_FILE_EXT, PNG_FILE_EXT

EDITED_SUBDIR = "edited"

HOME_DIR = os.environ.get("HOME")

THE_COMICS_DIR = os.path.join(HOME_DIR, "Books/Carl Barks/The Comics")
THE_COMIC_ZIPS_DIR = os.path.join(THE_COMICS_DIR, "Chronological")
THE_COMIC_FILES_DIR = os.path.join(THE_COMICS_DIR, "aaa-Chronological-dirs")
FANTA_VOLUME_ARCHIVES_ROOT_DIR = "/mnt/2tb_drive/Books/Carl Barks/Fantagraphics Volumes"

BARKS_READER_FILES_DIR = os.path.join(THE_COMICS_DIR, "Reader Files")

BARKS_PANELS_DIR = os.path.join(BARKS_READER_FILES_DIR, "Barks Panels")
INSET_FILES_DIR = os.path.join(BARKS_PANELS_DIR, "Insets")
INSET_EDITED_FILES_DIR = os.path.join(INSET_FILES_DIR, EDITED_SUBDIR)
COVER_FILES_DIR = os.path.join(BARKS_PANELS_DIR, "Covers")
SILHOUETTE_FILES_DIR = os.path.join(BARKS_PANELS_DIR, "Silhouettes")
SPLASH_FILES_DIR = os.path.join(BARKS_PANELS_DIR, "Splash")
CENSORSHIP_FILES_DIR = os.path.join(BARKS_PANELS_DIR, "Censorship")
FAVOURITE_FILES_DIR = os.path.join(BARKS_PANELS_DIR, "Favourites")
ORIGINAL_ART_FILES_DIR = os.path.join(BARKS_PANELS_DIR, "Original Art")
SEARCH_FILES_DIR = os.path.join(BARKS_PANELS_DIR, "Search")

READER_ICON_FILES_DIR = os.path.join(BARKS_READER_FILES_DIR, "Reader Icons")
APP_ICON_PATH = os.path.join(READER_ICON_FILES_DIR, "Barks Reader Icon 1.png")

ACTION_BAR_ICONS_DIR = os.path.join(READER_ICON_FILES_DIR, "ActionBar Icons")
CLOSE_ICON_PATH = os.path.join(ACTION_BAR_ICONS_DIR, "icon-close.png")
FULLSCREEN_ICON_PATH = os.path.join(ACTION_BAR_ICONS_DIR, "icon-fullscreen.png")
FULLSCREEN_EXIT_ICON_PATH = os.path.join(ACTION_BAR_ICONS_DIR, "icon-fullscreen-exit.png")
NEXT_ICON_PATH = os.path.join(ACTION_BAR_ICONS_DIR, "icon-next.png")
PREV_ICON_PATH = os.path.join(ACTION_BAR_ICONS_DIR, "icon-previous.png")
GOTO_ICON_PATH = os.path.join(ACTION_BAR_ICONS_DIR, "icon-goto.png")
GOTO_START_ICON_PATH = os.path.join(ACTION_BAR_ICONS_DIR, "icon-goto-start.png")
GOTO_END_ICON_PATH = os.path.join(ACTION_BAR_ICONS_DIR, "icon-goto-end.png")
ACTION_BAR_BACKGROUND_PATH = os.path.join(ACTION_BAR_ICONS_DIR, "action-bar-background.png")
ACTION_BAR_GROUP_BACKGROUND_PATH = os.path.join(ACTION_BAR_ICONS_DIR, "action-group-background.png")

VARIOUS_FILES_DIR = os.path.join(BARKS_READER_FILES_DIR, "Various")
UP_ARROW_PATH = os.path.join(VARIOUS_FILES_DIR, "up-arrow.png")
TRANSPARENT_BLANK_PATH = os.path.join(VARIOUS_FILES_DIR, "transparent-blank.png")
EMPTY_PAGE_PATH = os.path.join(VARIOUS_FILES_DIR, "empty-page.jpg")
USER_DATA_PATH = os.path.join(VARIOUS_FILES_DIR, "barks-reader.json")

EMERGENCY_INSET_FILE = Titles.BICEPS_BLUES
EMERGENCY_INSET_FILE_PATH = os.path.join(
    INSET_FILES_DIR,
    BARKS_TITLE_INFO[EMERGENCY_INSET_FILE].get_title_str() + JPG_FILE_EXT,
)


def check_dirs_and_files() -> None:
    dirs_to_check = [
        THE_COMICS_DIR,
        THE_COMIC_ZIPS_DIR,
        THE_COMIC_FILES_DIR,
        FANTA_VOLUME_ARCHIVES_ROOT_DIR,
        BARKS_PANELS_DIR,
        INSET_FILES_DIR,
        INSET_EDITED_FILES_DIR,
        COVER_FILES_DIR,
        SILHOUETTE_FILES_DIR,
        SPLASH_FILES_DIR,
        CENSORSHIP_FILES_DIR,
        FAVOURITE_FILES_DIR,
        ORIGINAL_ART_FILES_DIR,
        SEARCH_FILES_DIR,
        READER_ICON_FILES_DIR,
        ACTION_BAR_ICONS_DIR,
        VARIOUS_FILES_DIR,
    ]
    files_to_check = [
        EMERGENCY_INSET_FILE_PATH,
        APP_ICON_PATH,
        UP_ARROW_PATH,
        CLOSE_ICON_PATH,
        FULLSCREEN_ICON_PATH,
        FULLSCREEN_EXIT_ICON_PATH,
        NEXT_ICON_PATH,
        PREV_ICON_PATH,
        GOTO_ICON_PATH,
        GOTO_START_ICON_PATH,
        GOTO_END_ICON_PATH,
        ACTION_BAR_BACKGROUND_PATH,
        ACTION_BAR_GROUP_BACKGROUND_PATH,
        TRANSPARENT_BLANK_PATH,
        EMPTY_PAGE_PATH,
    ]

    if HOME_DIR is None:
        raise EnvironmentError("HOME environment variable is not set. Cannot determine base paths.")
    if not os.path.isdir(HOME_DIR):
        raise FileNotFoundError(f'The HOME directory specified does not exist: "{HOME_DIR}".')

    for dir_path in dirs_to_check:
        if not os.path.isdir(dir_path):
            raise FileNotFoundError(f'Required directory not found: "{dir_path}".')

    for file_path in files_to_check:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f'Required file not found: "{file_path}".')


check_dirs_and_files()


def get_the_comic_zips_dir() -> str:
    return THE_COMIC_ZIPS_DIR


def get_the_comic_files_dir() -> str:
    return THE_COMIC_FILES_DIR


def get_fanta_volume_archives_root_dir() -> str:
    return FANTA_VOLUME_ARCHIVES_ROOT_DIR


def get_comic_inset_files_dir() -> str:
    return INSET_FILES_DIR


def get_barks_reader_user_data_file() -> str:
    return USER_DATA_PATH


def get_comic_cover_files_dir() -> str:
    return COVER_FILES_DIR


def get_comic_silhouette_files_dir() -> str:
    return SILHOUETTE_FILES_DIR


def get_comic_splash_files_dir() -> str:
    return SPLASH_FILES_DIR


def get_comic_censorship_files_dir() -> str:
    return CENSORSHIP_FILES_DIR


def get_comic_favourite_files_dir() -> str:
    return FAVOURITE_FILES_DIR


def get_comic_original_art_files_dir() -> str:
    return ORIGINAL_ART_FILES_DIR


def get_comic_search_files_dir() -> str:
    return SEARCH_FILES_DIR


def get_barks_reader_app_icon_file() -> str:
    return APP_ICON_PATH


def get_up_arrow_file() -> str:
    return UP_ARROW_PATH


def get_barks_reader_close_icon_file() -> str:
    return CLOSE_ICON_PATH


def get_barks_reader_fullscreen_icon_file() -> str:
    return FULLSCREEN_ICON_PATH


def get_barks_reader_fullscreen_exit_icon_file() -> str:
    return FULLSCREEN_EXIT_ICON_PATH


def get_barks_reader_next_icon_file() -> str:
    return NEXT_ICON_PATH


def get_barks_reader_previous_icon_file() -> str:
    return PREV_ICON_PATH


def get_barks_reader_goto_icon_file() -> str:
    return GOTO_ICON_PATH


def get_barks_reader_goto_start_icon_file() -> str:
    return GOTO_START_ICON_PATH


def get_barks_reader_goto_end_icon_file() -> str:
    return GOTO_END_ICON_PATH


def get_barks_reader_action_bar_background_file() -> str:
    return ACTION_BAR_BACKGROUND_PATH


def get_barks_reader_action_bar_group_background_file() -> str:
    return ACTION_BAR_GROUP_BACKGROUND_PATH


def get_transparent_blank_file() -> str:
    return TRANSPARENT_BLANK_PATH


def get_empty_page_file() -> str:
    return EMPTY_PAGE_PATH


def get_comic_inset_file(title: Titles, use_edited_only: bool = False) -> str:
    title_str = BARKS_TITLES[title]

    if use_edited_only:
        edited_file = os.path.join(INSET_EDITED_FILES_DIR, title_str + PNG_FILE_EXT)
        if os.path.isfile(edited_file):
            return edited_file

    main_file = os.path.join(get_comic_inset_files_dir(), title_str + JPG_FILE_EXT)
    # TODO: Fix this when all titles are configured.
    # assert os.path.isfile(edited_file)
    if os.path.isfile(main_file):
        return main_file

    return EMERGENCY_INSET_FILE_PATH


def get_comic_cover_file(title: str, use_edited_only: bool = False) -> str:
    if use_edited_only:
        edited_file = os.path.join(get_comic_cover_files_dir(), EDITED_SUBDIR, title + PNG_FILE_EXT)
        if os.path.isfile(edited_file):
            return edited_file

    cover_file = os.path.join(get_comic_cover_files_dir(), title + JPG_FILE_EXT)
    if not os.path.isfile(cover_file):
        return ""

    return cover_file


def get_comic_silhouette_files(title: str, use_edited_only: bool = False) -> List[str]:
    return get_files(get_comic_silhouette_files_dir(), title, use_edited_only)


def get_comic_splash_files(title: str, use_edited_only: bool = False) -> List[str]:
    return get_files(get_comic_splash_files_dir(), title, use_edited_only)


def get_comic_censorship_files(title: str, use_edited_only: bool = False) -> List[str]:
    return get_files(get_comic_censorship_files_dir(), title, use_edited_only)


def get_comic_favourite_files(title: str, use_edited_only: bool = False) -> List[str]:
    return get_files(get_comic_favourite_files_dir(), title, use_edited_only)


def get_comic_original_art_files(title: str, use_edited_only: bool = False) -> List[str]:
    return get_files(get_comic_original_art_files_dir(), title, use_edited_only)


def get_comic_search_files(title: str, use_edited_only: bool = False) -> List[str]:
    return get_files(get_comic_search_files_dir(), title, use_edited_only)


def get_files(parent_image_dir: str, title: str, use_edited_only: bool) -> List[str]:
    image_dir = os.path.join(parent_image_dir, title)
    if not os.path.isdir(image_dir):
        return list()

    image_files = []

    edited_image_dir = os.path.join(image_dir, EDITED_SUBDIR)
    if os.path.isdir(edited_image_dir):
        image_files = get_all_files(edited_image_dir)
        if use_edited_only and image_files:
            # Don't want any unedited images.
            return image_files

    image_files.extend(get_all_files(image_dir))

    return image_files


def get_all_files(image_dir: str) -> List[str]:
    image_files = []
    for file in os.listdir(image_dir):
        image_file = os.path.join(image_dir, file)
        if os.path.isfile(image_file):
            image_files.append(image_file)

    return image_files


def get_edited_version_if_possible(image_file: str) -> Tuple[str, bool]:
    dir_path = os.path.dirname(image_file)
    edited_image_file = os.path.join(dir_path, EDITED_SUBDIR, Path(image_file).stem + PNG_FILE_EXT)
    if os.path.isfile(edited_image_file):
        return edited_image_file, True

    return image_file, False
