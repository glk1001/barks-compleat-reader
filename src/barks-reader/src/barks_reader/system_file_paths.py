from pathlib import Path

from loguru import logger


class SystemFilePaths:
    def __init__(self) -> None:
        self._barks_reader_files_dir: Path | None = None

        self._reader_icon_files_dir: Path | None = None

        self._action_bar_icons_dir: Path | None = None
        self._close_icon_path: Path | None = None
        self._collapse_icon_path: Path | None = None
        self._refresh_arrow_icon_path: Path | None = None
        self._settings_icon_path: Path | None = None
        self._fullscreen_icon_path: Path | None = None
        self._fullscreen_exit_icon_path: Path | None = None
        self._goto_icon_path: Path | None = None
        self._goto_start_icon_path: Path | None = None
        self._goto_end_icon_path: Path | None = None
        self._hamburger_menu_icon_path: Path | None = None

        self._various_files_dir: Path | None = None
        self._up_arrow_path: Path | None = None
        self._down_arrow_path: Path | None = None
        self._transparent_blank_path: Path | None = None
        self._empty_page_path: Path | None = None
        self._intro_image_path: Path | None = None
        self._favourite_titles_path: Path | None = None

        self._fantagraphics_overrides_root_dir: Path | None = None
        self._fantagraphics_panel_segments_root_dir: Path | None = None

    def set_barks_reader_files_dir(self, reader_files_dir: Path) -> None:
        logger.info(f'SystemFilePaths: Setting reader_files_dir = "{reader_files_dir}".')

        self._barks_reader_files_dir = reader_files_dir

        self._reader_icon_files_dir = self._barks_reader_files_dir / "Reader Icons"
        self._app_window_icon_path = self._reader_icon_files_dir / "app-icon.png"

        self._action_bar_icons_dir = self._reader_icon_files_dir / "ActionBar Icons"
        self._close_icon_path = self._action_bar_icons_dir / "icon-close.png"
        self._collapse_icon_path = self._action_bar_icons_dir / "icon-collapse.png"
        self._refresh_arrow_icon_path = self._action_bar_icons_dir / "icon-refresh-arrow.png"
        self._settings_icon_path = self._action_bar_icons_dir / "icon-settings.png"
        self._fullscreen_icon_path = self._action_bar_icons_dir / "icon-fullscreen.png"
        self._fullscreen_exit_icon_path = self._action_bar_icons_dir / "icon-fullscreen-exit.png"
        self._goto_icon_path = self._action_bar_icons_dir / "icon-goto.png"
        self._goto_start_icon_path = self._action_bar_icons_dir / "icon-goto-start.png"
        self._goto_end_icon_path = self._action_bar_icons_dir / "icon-goto-end.png"
        self._hamburger_menu_icon_path = self._action_bar_icons_dir / "menu-hamburger-icon.png"

        self._various_files_dir = self._barks_reader_files_dir / "Various"
        self._up_arrow_path = self._various_files_dir / "up-arrow.png"
        self._down_arrow_path = self._various_files_dir / "down-arrow.png"
        self._transparent_blank_path = self._various_files_dir / "transparent-blank.png"
        self._empty_page_path = self._various_files_dir / "empty-page.jpg"
        self._intro_image_path = self._various_files_dir / "intro-to-barks-reader.jpg"
        self._favourite_titles_path = self._various_files_dir / "favourite-titles.txt"

        self._fantagraphics_overrides_root_dir = (
            self._barks_reader_files_dir / "Fantagraphics Volumes Overrides"
        )
        self._fantagraphics_panel_segments_root_dir = (
            self._barks_reader_files_dir / "Fantagraphics-panel-segments"
        )

        self._check_reader_files_dirs()

    def _check_reader_files_dirs(self) -> None:
        dirs_to_check = [
            self._barks_reader_files_dir,
            self._reader_icon_files_dir,
            self._action_bar_icons_dir,
            self._various_files_dir,
            self._fantagraphics_overrides_root_dir,
        ]
        self._check_dirs(dirs_to_check)

        files_to_check = [
            self._app_window_icon_path,
            self._close_icon_path,
            self._collapse_icon_path,
            self._refresh_arrow_icon_path,
            self._settings_icon_path,
            self._fullscreen_icon_path,
            self._fullscreen_exit_icon_path,
            self._goto_icon_path,
            self._goto_start_icon_path,
            self._goto_end_icon_path,
            self._hamburger_menu_icon_path,
            self._up_arrow_path,
            self._down_arrow_path,
            self._transparent_blank_path,
            self._empty_page_path,
            self._intro_image_path,
            self._favourite_titles_path,
        ]
        self._check_files(files_to_check)

    @staticmethod
    def _check_dirs(dirs_to_check: list[Path]) -> None:
        for dir_path in dirs_to_check:
            if not dir_path.is_dir():
                msg = f'Required directory not found: "{dir_path}".'
                raise FileNotFoundError(msg)

    @staticmethod
    def _check_files(files_to_check: list[Path]) -> None:
        for file_path in files_to_check:
            if not file_path.is_file():
                msg = f'Required file not found: "{file_path}".'
                raise FileNotFoundError(msg)

    def get_barks_reader_fantagraphics_overrides_root_dir(self) -> Path:
        return self._fantagraphics_overrides_root_dir

    def get_barks_reader_fantagraphics_panel_segments_root_dir(self) -> Path:
        return self._fantagraphics_panel_segments_root_dir

    def get_reader_icon_files_dir(self) -> Path:
        return self._reader_icon_files_dir

    def get_up_arrow_file(self) -> Path:
        return self._up_arrow_path

    def get_down_arrow_file(self) -> Path:
        return self._down_arrow_path

    def get_barks_reader_app_window_icon_path(self) -> Path:
        return self._app_window_icon_path

    def get_barks_reader_close_icon_file(self) -> Path:
        return self._close_icon_path

    def get_barks_reader_collapse_icon_file(self) -> Path:
        return self._collapse_icon_path

    def get_barks_reader_refresh_arrow_icon_file(self) -> Path:
        return self._refresh_arrow_icon_path

    def get_barks_reader_settings_icon_file(self) -> Path:
        return self._settings_icon_path

    def get_barks_reader_fullscreen_icon_file(self) -> Path:
        return self._fullscreen_icon_path

    def get_barks_reader_fullscreen_exit_icon_file(self) -> Path:
        return self._fullscreen_exit_icon_path

    def get_barks_reader_goto_icon_file(self) -> Path:
        return self._goto_icon_path

    def get_barks_reader_goto_start_icon_file(self) -> Path:
        return self._goto_start_icon_path

    def get_barks_reader_goto_end_icon_file(self) -> Path:
        return self._goto_end_icon_path

    def get_hamburger_menu_icon_path(self) -> Path:
        return self._hamburger_menu_icon_path

    def get_transparent_blank_file(self) -> Path:
        return self._transparent_blank_path

    def get_empty_page_file(self) -> Path:
        return self._empty_page_path

    def get_intro_image_file(self) -> Path:
        return self._intro_image_path

    def get_favourite_titles_path(self) -> Path:
        return self._favourite_titles_path
