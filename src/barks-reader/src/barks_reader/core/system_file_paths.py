from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


class _Need(Enum):
    REQUIRED_DIR = auto()
    REQUIRED_FILE = auto()
    OPTIONAL = auto()


class _Asset(Enum):
    """A folder or file in Reader Files: its path there, and whether boot needs it.

    A member's name, lower-cased, is its label in the validator's report.
    """

    def __init__(self, relative_path: str, need: _Need) -> None:
        self.relative_path = relative_path
        self.need = need

    # Required folders.
    READER_ICON_FILES_DIR = ("Reader Icons", _Need.REQUIRED_DIR)
    ACTION_BAR_ICONS_DIR = ("Reader Icons/ActionBar Icons", _Need.REQUIRED_DIR)
    VARIOUS_FILES_DIR = ("Various", _Need.REQUIRED_DIR)
    INDEXES_DIR = ("Indexes", _Need.REQUIRED_DIR)
    FANTAGRAPHICS_OVERRIDES_ROOT_DIR = ("Fantagraphics Volumes Overrides", _Need.REQUIRED_DIR)
    INTRO_DOC_DIR = ("Various/documents/intro-to-barks-reader", _Need.REQUIRED_DIR)
    CENSORSHIP_FIXES_DOC_DIR = ("Various/documents/censorship-fixes", _Need.REQUIRED_DIR)
    HOW_TO_DOC_DIR = ("Various/documents/how-to", _Need.REQUIRED_DIR)
    # Required files.
    APP_WINDOW_ICON_PATH = ("Various/app-icon.png", _Need.REQUIRED_FILE)
    ERROR_BACKGROUND_PATH = ("Various/error-background.png", _Need.REQUIRED_FILE)
    SUCCESS_BACKGROUND_PATH = ("Various/success-background.png", _Need.REQUIRED_FILE)
    # The app's identity image: shown behind the quit-confirmation and about popups.
    APP_IDENTITY_IMAGE_PATH = ("Various/app-identity-image.png", _Need.REQUIRED_FILE)
    CLOSE_ICON_PATH = ("Reader Icons/ActionBar Icons/icon-close.png", _Need.REQUIRED_FILE)
    POWER_ICON_PATH = ("Reader Icons/ActionBar Icons/icon-power.png", _Need.REQUIRED_FILE)
    GO_BACK_ICON_PATH = ("Reader Icons/ActionBar Icons/icon-back-arrow.png", _Need.REQUIRED_FILE)
    COLLAPSE_ICON_PATH = ("Reader Icons/ActionBar Icons/icon-collapse.png", _Need.REQUIRED_FILE)
    REFRESH_ARROW_ICON_PATH = (
        "Reader Icons/ActionBar Icons/icon-refresh-arrow.png",
        _Need.REQUIRED_FILE,
    )
    SETTINGS_ICON_PATH = ("Reader Icons/ActionBar Icons/icon-settings.png", _Need.REQUIRED_FILE)
    MENU_DOTS_ICON_PATH = ("Reader Icons/ActionBar Icons/icon-menu-dots.png", _Need.REQUIRED_FILE)
    FULLSCREEN_ICON_PATH = ("Reader Icons/ActionBar Icons/icon-fullscreen.png", _Need.REQUIRED_FILE)
    FULLSCREEN_EXIT_ICON_PATH = (
        "Reader Icons/ActionBar Icons/icon-fullscreen-exit.png",
        _Need.REQUIRED_FILE,
    )
    SINGLE_PAGE_ICON_PATH = (
        "Reader Icons/ActionBar Icons/icon-single-page.png",
        _Need.REQUIRED_FILE,
    )
    DOUBLE_PAGE_ICON_PATH = (
        "Reader Icons/ActionBar Icons/icon-double-page.png",
        _Need.REQUIRED_FILE,
    )
    GOTO_ICON_PATH = ("Reader Icons/ActionBar Icons/icon-goto.png", _Need.REQUIRED_FILE)
    GOTO_START_ICON_PATH = ("Reader Icons/ActionBar Icons/icon-goto-start.png", _Need.REQUIRED_FILE)
    GOTO_END_ICON_PATH = ("Reader Icons/ActionBar Icons/icon-goto-end.png", _Need.REQUIRED_FILE)
    CONTRAST_ON_ICON_PATH = (
        "Reader Icons/ActionBar Icons/icon-contrast-on.png",
        _Need.REQUIRED_FILE,
    )
    CONTRAST_OFF_ICON_PATH = (
        "Reader Icons/ActionBar Icons/icon-contrast-off.png",
        _Need.REQUIRED_FILE,
    )
    GOTO_TITLE_ICON_PATH = ("Reader Icons/ActionBar Icons/icon-goto-title.png", _Need.REQUIRED_FILE)
    HAMBURGER_MENU_ICON_PATH = (
        "Reader Icons/ActionBar Icons/menu-hamburger-icon.png",
        _Need.REQUIRED_FILE,
    )
    SPEECH_BUBBLE_ICON_PATH = ("Various/speech-bubble-icon.png", _Need.REQUIRED_FILE)
    EYE_OPEN_ICON_PATH = ("Various/icon-eye-open.png", _Need.REQUIRED_FILE)
    EYE_OFF_ICON_PATH = ("Various/icon-eye-off.png", _Need.REQUIRED_FILE)
    GOTO_TITLE_BUTTON_PATH = ("Various/goto-title-button.png", _Need.REQUIRED_FILE)
    TRANSPARENT_BLANK_PATH = ("Various/transparent-blank.png", _Need.REQUIRED_FILE)
    EMPTY_PAGE_PATH = ("Various/empty-page.jpg", _Need.REQUIRED_FILE)
    FAVOURITE_TITLES_PATH = ("Various/favourite-titles.txt", _Need.REQUIRED_FILE)
    BY_THE_NUMBERS_BACKGROUND_PATH = ("Various/by-the-numbers-background.jpg", _Need.REQUIRED_FILE)
    # Optional: the app shows what needs them only when they are there.
    ILLUSTRATED_HISTORY_DOC_DIR = ("Various/documents/illustrated-history", _Need.OPTIONAL)
    FANTAGRAPHICS_PANEL_SEGMENTS_ROOT_DIR = ("Fantagraphics-panel-segments", _Need.OPTIONAL)
    STATISTICS_DIR = ("Statistics", _Need.OPTIONAL)


class SystemFilePaths:
    """Where the app's own folders and files are in Reader Files."""

    def __init__(self) -> None:
        self._barks_reader_files_dir: Path | None = None

    def set_barks_reader_files_dir(self, reader_files_dir: Path, check_files: bool = True) -> None:
        """Point every lookup at ``reader_files_dir``, checking it first by default.

        Args:
            reader_files_dir: The Reader Files folder.
            check_files: Check that every required folder and file is there.

        Raises:
            FileNotFoundError: A required folder or file is missing.

        """
        logger.info(f'SystemFilePaths: Setting reader_files_dir = "{reader_files_dir}".')

        self._barks_reader_files_dir = reader_files_dir

        if check_files:
            self._check_dirs(path for _label, path in self.required_dirs())
            self.check_files(path for _label, path in self.required_files())

    def required_dirs(self) -> list[tuple[str, Path]]:
        """Return the folders boot needs, Reader Files itself first, each with its label."""
        assert self._barks_reader_files_dir
        return [
            ("barks_reader_files_dir", self._barks_reader_files_dir),
            *self._labelled(_Need.REQUIRED_DIR),
        ]

    def required_files(self) -> list[tuple[str, Path]]:
        """Return the files boot needs, each with its label."""
        return self._labelled(_Need.REQUIRED_FILE)

    def _labelled(self, need: _Need) -> list[tuple[str, Path]]:
        return [(asset.name.lower(), self._path(asset)) for asset in _Asset if asset.need is need]

    def _path(self, asset: _Asset) -> Path:
        assert self._barks_reader_files_dir, "set_barks_reader_files_dir has not been called."
        return self._barks_reader_files_dir / asset.relative_path

    @staticmethod
    def _check_dirs(dirs_to_check: Iterable[Path]) -> None:
        for dir_path in dirs_to_check:
            if not dir_path.is_dir():
                msg = f'Required directory not found: "{dir_path}".'
                raise FileNotFoundError(msg)

    @staticmethod
    def check_files(files_to_check: Iterable[Path]) -> None:
        """Raise ``FileNotFoundError`` for the first of ``files_to_check`` that is not a file."""
        for file_path in files_to_check:
            if not file_path.is_file():
                msg = f'Required file not found: "{file_path}".'
                raise FileNotFoundError(msg)

    def get_statistics_dir(self) -> Path:
        """Return the directory containing pre-generated statistics PNG images."""
        return self._path(_Asset.STATISTICS_DIR)

    def get_barks_reader_fantagraphics_overrides_root_dir(self) -> Path:
        return self._path(_Asset.FANTAGRAPHICS_OVERRIDES_ROOT_DIR)

    def get_barks_reader_fantagraphics_panel_segments_root_dir(self) -> Path:
        return self._path(_Asset.FANTAGRAPHICS_PANEL_SEGMENTS_ROOT_DIR)

    def get_barks_reader_indexes_dir(self) -> Path:
        return self._path(_Asset.INDEXES_DIR)

    def get_reader_icon_files_dir(self) -> Path:
        return self._path(_Asset.READER_ICON_FILES_DIR)

    def get_barks_reader_app_window_icon_path(self) -> Path:
        return self._path(_Asset.APP_WINDOW_ICON_PATH)

    def get_error_background_path(self) -> Path:
        return self._path(_Asset.ERROR_BACKGROUND_PATH)

    def get_success_background_path(self) -> Path:
        return self._path(_Asset.SUCCESS_BACKGROUND_PATH)

    def get_speech_bubble_icon_file(self) -> Path:
        return self._path(_Asset.SPEECH_BUBBLE_ICON_PATH)

    def get_eye_open_icon_file(self) -> Path:
        return self._path(_Asset.EYE_OPEN_ICON_PATH)

    def get_eye_off_icon_file(self) -> Path:
        return self._path(_Asset.EYE_OFF_ICON_PATH)

    def get_goto_title_button_file(self) -> Path:
        """Return the goto-title button, an open book on a disc, that the image overlays show."""
        return self._path(_Asset.GOTO_TITLE_BUTTON_PATH)

    def get_app_identity_image_file(self) -> Path:
        """Return the app's identity image: shown behind the quit-confirmation and about popups."""
        return self._path(_Asset.APP_IDENTITY_IMAGE_PATH)

    def get_barks_reader_close_icon_file(self) -> Path:
        return self._path(_Asset.CLOSE_ICON_PATH)

    def get_barks_reader_power_icon_file(self) -> Path:
        """Return the Quit button's power glyph: leaving the app, not closing a screen."""
        return self._path(_Asset.POWER_ICON_PATH)

    def get_barks_reader_go_back_icon_file(self) -> Path:
        return self._path(_Asset.GO_BACK_ICON_PATH)

    def get_barks_reader_collapse_icon_file(self) -> Path:
        return self._path(_Asset.COLLAPSE_ICON_PATH)

    def get_barks_reader_refresh_arrow_icon_file(self) -> Path:
        return self._path(_Asset.REFRESH_ARROW_ICON_PATH)

    def get_barks_reader_settings_icon_file(self) -> Path:
        return self._path(_Asset.SETTINGS_ICON_PATH)

    def get_barks_reader_menu_dots_icon_file(self) -> Path:
        return self._path(_Asset.MENU_DOTS_ICON_PATH)

    def get_barks_reader_fullscreen_icon_file(self) -> Path:
        return self._path(_Asset.FULLSCREEN_ICON_PATH)

    def get_barks_reader_fullscreen_exit_icon_file(self) -> Path:
        return self._path(_Asset.FULLSCREEN_EXIT_ICON_PATH)

    def get_barks_reader_single_page_icon_file(self) -> Path:
        return self._path(_Asset.SINGLE_PAGE_ICON_PATH)

    def get_barks_reader_double_page_icon_file(self) -> Path:
        return self._path(_Asset.DOUBLE_PAGE_ICON_PATH)

    def get_barks_reader_goto_icon_file(self) -> Path:
        return self._path(_Asset.GOTO_ICON_PATH)

    def get_barks_reader_contrast_on_icon_file(self) -> Path:
        return self._path(_Asset.CONTRAST_ON_ICON_PATH)

    def get_barks_reader_contrast_off_icon_file(self) -> Path:
        return self._path(_Asset.CONTRAST_OFF_ICON_PATH)

    def get_barks_reader_goto_title_icon_file(self) -> Path:
        return self._path(_Asset.GOTO_TITLE_ICON_PATH)

    def get_barks_reader_goto_start_icon_file(self) -> Path:
        return self._path(_Asset.GOTO_START_ICON_PATH)

    def get_barks_reader_goto_end_icon_file(self) -> Path:
        return self._path(_Asset.GOTO_END_ICON_PATH)

    def get_hamburger_menu_icon_path(self) -> Path:
        return self._path(_Asset.HAMBURGER_MENU_ICON_PATH)

    def get_transparent_blank_file(self) -> Path:
        return self._path(_Asset.TRANSPARENT_BLANK_PATH)

    def get_empty_page_file(self) -> Path:
        return self._path(_Asset.EMPTY_PAGE_PATH)

    def get_intro_doc_dir(self) -> Path:
        return self._path(_Asset.INTRO_DOC_DIR)

    def get_censorship_fixes_doc_dir(self) -> Path:
        return self._path(_Asset.CENSORSHIP_FIXES_DOC_DIR)

    def get_how_to_doc_dir(self) -> Path:
        return self._path(_Asset.HOW_TO_DOC_DIR)

    def get_illustrated_history_doc_dir(self) -> Path:
        """Return the illustrated history's folder of chapters, which may not exist.

        Unlike the other document folders it is optional: the Introduction shows its
        node only when the folder holds chapters.
        """
        return self._path(_Asset.ILLUSTRATED_HISTORY_DOC_DIR)

    def get_favourite_titles_path(self) -> Path:
        return self._path(_Asset.FAVOURITE_TITLES_PATH)

    def get_by_the_numbers_background_path(self) -> Path:
        """Return the art shown behind the Introduction's "By the Numbers" page."""
        return self._path(_Asset.BY_THE_NUMBERS_BACKGROUND_PATH)
