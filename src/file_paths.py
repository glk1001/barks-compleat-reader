import logging
import os
from enum import Enum, auto
from pathlib import Path
from typing import List, Tuple

from barks_fantagraphics.barks_titles import (
    Titles,
    BARKS_TITLE_INFO,
    BARKS_TITLES,
    BARKS_TITLE_DICT,
)
from barks_fantagraphics.comics_consts import JPG_FILE_EXT, PNG_FILE_EXT

EDITED_SUBDIR = "edited"

HOME_DIR = os.environ.get("HOME")

BARKS_DIR = os.path.join(HOME_DIR, "Books/Carl Barks")
THE_COMICS_DIR = os.path.join(BARKS_DIR, "The Comics")
THE_COMIC_ZIPS_DIR = os.path.join(THE_COMICS_DIR, "Chronological")
THE_COMIC_FILES_DIR = os.path.join(THE_COMICS_DIR, "aaa-Chronological-dirs")
FANTA_VOLUME_ARCHIVES_ROOT_DIR = "/mnt/2tb_drive/Books/Carl Barks/Fantagraphics Volumes"

BARKS_READER_FILES_DIR = os.path.join(BARKS_DIR, "Compleat Barks Disney Reader")

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

JPG_BARKS_PANELS_DIR = os.path.join(BARKS_READER_FILES_DIR, "Barks Panels")
PNG_BARKS_PANELS_DIR = os.path.join(BARKS_DIR, "Barks Panels Pngs")
JPG_INSET_FILES_DIR = os.path.join(JPG_BARKS_PANELS_DIR, "Insets")
PNG_INSET_FILES_DIR = os.path.join(PNG_BARKS_PANELS_DIR, "Insets")


def _check_dirs_and_files() -> None:
    dirs_to_check = [
        THE_COMICS_DIR,
        THE_COMIC_ZIPS_DIR,
        THE_COMIC_FILES_DIR,
        FANTA_VOLUME_ARCHIVES_ROOT_DIR,
        READER_ICON_FILES_DIR,
        ACTION_BAR_ICONS_DIR,
        VARIOUS_FILES_DIR,
    ]
    files_to_check = [
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


_check_dirs_and_files()


class BarksPanelsExtType(Enum):
    JPG = auto()
    MOSTLY_PNG = auto()


_barks_panels_dir = ""
_cover_files_dir = ""
_silhouette_files_dir = ""
_splash_files_dir = ""
_censorship_files_dir = ""
_favourite_files_dir = ""
_original_art_files_dir = ""
_search_files_dir = ""
_nontitle_files_dir = ""
_inset_files_dir = ""
_inset_edited_files_dir = ""

_inset_files_ext = ""
_edited_files_ext = ""

_panels_ext_type: BarksPanelsExtType


def set_barks_panels_dir(panels_dir: str, ext_type: BarksPanelsExtType) -> None:
    global _barks_panels_dir
    global _cover_files_dir
    global _silhouette_files_dir
    global _splash_files_dir
    global _censorship_files_dir
    global _favourite_files_dir
    global _original_art_files_dir
    global _search_files_dir
    global _nontitle_files_dir
    global _inset_files_dir
    global _inset_edited_files_dir
    global _panels_ext_type

    _barks_panels_dir = panels_dir
    _panels_ext_type = ext_type

    _cover_files_dir = os.path.join(_barks_panels_dir, "Covers")
    _silhouette_files_dir = os.path.join(_barks_panels_dir, "Silhouettes")
    _splash_files_dir = os.path.join(_barks_panels_dir, "Splash")
    _censorship_files_dir = os.path.join(_barks_panels_dir, "Censorship")
    _favourite_files_dir = os.path.join(_barks_panels_dir, "Favourites")
    _original_art_files_dir = os.path.join(_barks_panels_dir, "Original Art")
    _search_files_dir = os.path.join(_barks_panels_dir, "Search")
    _nontitle_files_dir = os.path.join(_barks_panels_dir, "Nontitles")
    _inset_files_dir = os.path.join(_barks_panels_dir, "Insets")
    _inset_edited_files_dir = os.path.join(_inset_files_dir, EDITED_SUBDIR)

    assert os.path.isdir(_barks_panels_dir)
    assert os.path.isdir(_cover_files_dir)
    assert os.path.isdir(_silhouette_files_dir)
    assert os.path.isdir(_splash_files_dir)
    assert os.path.isdir(_censorship_files_dir)
    assert os.path.isdir(_favourite_files_dir)
    assert os.path.isdir(_original_art_files_dir)
    assert os.path.isdir(_search_files_dir)
    assert os.path.isdir(_nontitle_files_dir)
    assert os.path.isdir(_inset_files_dir)
    assert os.path.isdir(_inset_edited_files_dir)

    global _inset_files_ext
    _inset_files_ext = JPG_FILE_EXT if _panels_ext_type == BarksPanelsExtType.JPG else PNG_FILE_EXT

    global _edited_files_ext
    _edited_files_ext = JPG_FILE_EXT if _panels_ext_type == BarksPanelsExtType.JPG else PNG_FILE_EXT


def get_inset_file_ext() -> str:
    return _inset_files_ext


def get_emergency_inset_file() -> str:
    return os.path.join(
        _inset_files_dir,
        BARKS_TITLE_INFO[EMERGENCY_INSET_FILE].get_title_str() + _inset_files_ext,
    )


def get_the_comic_zips_dir() -> str:
    return THE_COMIC_ZIPS_DIR


def get_the_comic_files_dir() -> str:
    return THE_COMIC_FILES_DIR


def get_fanta_volume_archives_root_dir() -> str:
    return FANTA_VOLUME_ARCHIVES_ROOT_DIR


def get_comic_inset_files_dir() -> str:
    return _inset_files_dir


def get_barks_reader_user_data_file() -> str:
    return USER_DATA_PATH


def get_comic_cover_files_dir() -> str:
    return _cover_files_dir


def get_comic_silhouette_files_dir() -> str:
    return _silhouette_files_dir


def get_comic_splash_files_dir() -> str:
    return _splash_files_dir


def get_comic_censorship_files_dir() -> str:
    return _censorship_files_dir


def get_comic_favourite_files_dir() -> str:
    return _favourite_files_dir


def get_comic_original_art_files_dir() -> str:
    return _original_art_files_dir


def get_comic_search_files_dir() -> str:
    return _search_files_dir


def get_nontitle_files_dir() -> str:
    return _nontitle_files_dir


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
        edited_file = os.path.join(_inset_edited_files_dir, title_str + _inset_files_ext)
        if os.path.isfile(edited_file):
            return edited_file
        logging.debug(f'No edited inset file "{edited_file}".')

    main_file = os.path.join(_inset_files_dir, title_str + _inset_files_ext)
    # TODO: Fix this when all titles are configured.
    # assert os.path.isfile(edited_file)
    if os.path.isfile(main_file):
        return main_file

    return get_emergency_inset_file()


def get_comic_inset_files(title_str: str, use_edited_only: bool = False) -> List[str]:
    title = BARKS_TITLE_DICT[title_str]

    inset_list = [get_comic_inset_file(title, use_edited_only)]
    if use_edited_only:
        return inset_list

    main_inset_file = get_comic_inset_file(title, False)
    if main_inset_file not in inset_list:
        inset_list.append(main_inset_file)

    return inset_list


def get_comic_cover_file(title: str, use_edited_only: bool = False) -> str:
    if use_edited_only:
        edited_file = os.path.join(
            get_comic_cover_files_dir(), EDITED_SUBDIR, title + _edited_files_ext
        )
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


def get_nontitle_files() -> List[str]:
    return get_all_files(get_nontitle_files_dir())


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
    edited_image_file = os.path.join(
        dir_path, EDITED_SUBDIR, Path(image_file).stem + _edited_files_ext
    )
    if os.path.isfile(edited_image_file):
        return edited_image_file, True

    return image_file, False
