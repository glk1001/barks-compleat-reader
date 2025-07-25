import logging
import os
from typing import List


class SystemFilePaths:
    def __init__(self):
        self._barks_reader_files_dir = ""

        self._reader_icon_files_dir = ""

        self._action_bar_icons_dir = ""
        self._close_icon_path = ""
        self._collapse_icon_path = ""
        self._refresh_arrow_icon_path = ""
        self._settings_icon_path = ""
        self._fullscreen_icon_path = ""
        self._fullscreen_exit_icon_path = ""
        self._goto_icon_path = ""
        self._goto_start_icon_path = ""
        self._goto_end_icon_path = ""

        self._various_files_dir = ""
        self._up_arrow_path = ""
        self._transparent_blank_path = ""
        self._empty_page_path = ""

        self._fantagraphics_overrides_root_dir = ""

    def set_barks_reader_files_dir(self, reader_files_dir: str) -> None:
        logging.info(f'SystemFilePaths: Setting reader_files_dir = "{reader_files_dir}".')

        self._barks_reader_files_dir = reader_files_dir

        self._reader_icon_files_dir = os.path.join(self._barks_reader_files_dir, "Reader Icons")

        self._action_bar_icons_dir = os.path.join(self._reader_icon_files_dir, "ActionBar Icons")
        self._close_icon_path = os.path.join(self._action_bar_icons_dir, "icon-close.png")
        self._collapse_icon_path = os.path.join(self._action_bar_icons_dir, "icon-collapse.png")
        self._refresh_arrow_icon_path = os.path.join(
            self._action_bar_icons_dir, "icon-refresh-arrow.png"
        )
        self._settings_icon_path = os.path.join(self._action_bar_icons_dir, "icon-settings.png")
        self._fullscreen_icon_path = os.path.join(self._action_bar_icons_dir, "icon-fullscreen.png")
        self._fullscreen_exit_icon_path = os.path.join(
            self._action_bar_icons_dir, "icon-fullscreen-exit.png"
        )
        self._goto_icon_path = os.path.join(self._action_bar_icons_dir, "icon-goto.png")
        self._goto_start_icon_path = os.path.join(self._action_bar_icons_dir, "icon-goto-start.png")
        self._goto_end_icon_path = os.path.join(self._action_bar_icons_dir, "icon-goto-end.png")

        self._various_files_dir = os.path.join(self._barks_reader_files_dir, "Various")
        self._up_arrow_path = os.path.join(self._various_files_dir, "up-arrow.png")
        self._transparent_blank_path = os.path.join(
            self._various_files_dir, "transparent-blank.png"
        )
        self._empty_page_path = os.path.join(self._various_files_dir, "empty-page.jpg")

        self._fantagraphics_overrides_root_dir = os.path.join(
            self._barks_reader_files_dir, "Fantagraphics Volumes Overrides"
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
            self._close_icon_path,
            self._collapse_icon_path,
            self._refresh_arrow_icon_path,
            self._settings_icon_path,
            self._fullscreen_icon_path,
            self._fullscreen_exit_icon_path,
            self._goto_icon_path,
            self._goto_start_icon_path,
            self._goto_end_icon_path,
            self._up_arrow_path,
            self._transparent_blank_path,
            self._empty_page_path,
        ]
        self._check_files(files_to_check)

    @staticmethod
    def _check_dirs(dirs_to_check: List[str]) -> None:
        for dir_path in dirs_to_check:
            if not os.path.isdir(dir_path):
                raise FileNotFoundError(f'Required directory not found: "{dir_path}".')

    @staticmethod
    def _check_files(files_to_check: List[str]) -> None:
        for file_path in files_to_check:
            if not os.path.isfile(file_path):
                raise FileNotFoundError(f'Required file not found: "{file_path}".')

    def get_barks_reader_fantagraphics_overrides_root_dir(self) -> str:
        return self._fantagraphics_overrides_root_dir

    def get_reader_icon_files_dir(self) -> str:
        return self._reader_icon_files_dir

    def get_up_arrow_file(self) -> str:
        return self._up_arrow_path

    def get_barks_reader_close_icon_file(self) -> str:
        return self._close_icon_path

    def get_barks_reader_collapse_icon_file(self) -> str:
        return self._collapse_icon_path

    def get_barks_reader_refresh_arrow_icon_file(self) -> str:
        return self._refresh_arrow_icon_path

    def get_barks_reader_settings_icon_file(self) -> str:
        return self._settings_icon_path

    def get_barks_reader_fullscreen_icon_file(self) -> str:
        return self._fullscreen_icon_path

    def get_barks_reader_fullscreen_exit_icon_file(self) -> str:
        return self._fullscreen_exit_icon_path

    def get_barks_reader_goto_icon_file(self) -> str:
        return self._goto_icon_path

    def get_barks_reader_goto_start_icon_file(self) -> str:
        return self._goto_start_icon_path

    def get_barks_reader_goto_end_icon_file(self) -> str:
        return self._goto_end_icon_path

    def get_transparent_blank_file(self) -> str:
        return self._transparent_blank_path

    def get_empty_page_file(self) -> str:
        return self._empty_page_path
