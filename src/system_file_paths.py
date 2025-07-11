import logging
import os
from typing import List

from file_paths import BARKS_DIR

DEFAULT_BARKS_READER_FILES_DIR = os.path.join(BARKS_DIR, "Compleat Barks Disney Reader")


class SystemFilePaths:
    def __init__(self):
        self.__barks_reader_files_dir = ""

        self.__reader_icon_files_dir = ""
        self.__app_icon_path = ""

        self.__action_bar_icons_dir = ""
        self.__close_icon_path = ""
        self.__collapse_icon_path = ""
        self.__refresh_arrow_icon_path = ""
        self.__settings_icon_path = ""
        self.__fullscreen_icon_path = ""
        self.__fullscreen_exit_icon_path = ""
        self.__goto_icon_path = ""
        self.__goto_start_icon_path = ""
        self.__goto_end_icon_path = ""

        self.__various_files_dir = ""
        self.__up_arrow_path = ""
        self.__transparent_blank_path = ""
        self.__empty_page_path = ""
        self.__user_data_path = ""

    def set_barks_reader_files_dir(self, reader_files_dir: str) -> None:
        logging.info(f'SystemFilePaths: Setting reader_files_dir = "{reader_files_dir}".')

        self.__barks_reader_files_dir = reader_files_dir

        self.__reader_icon_files_dir = os.path.join(self.__barks_reader_files_dir, "Reader Icons")
        self.__app_icon_path = os.path.join(self.__reader_icon_files_dir, "Barks Reader Icon 1.png")

        self.__action_bar_icons_dir = os.path.join(self.__reader_icon_files_dir, "ActionBar Icons")
        self.__close_icon_path = os.path.join(self.__action_bar_icons_dir, "icon-close.png")
        self.__collapse_icon_path = os.path.join(self.__action_bar_icons_dir, "icon-collapse.png")
        self.__refresh_arrow_icon_path = os.path.join(
            self.__action_bar_icons_dir, "icon-refresh-arrow.png"
        )
        self.__settings_icon_path = os.path.join(self.__action_bar_icons_dir, "icon-settings.png")
        self.__fullscreen_icon_path = os.path.join(
            self.__action_bar_icons_dir, "icon-fullscreen.png"
        )
        self.__fullscreen_exit_icon_path = os.path.join(
            self.__action_bar_icons_dir, "icon-fullscreen-exit.png"
        )
        self.__goto_icon_path = os.path.join(self.__action_bar_icons_dir, "icon-goto.png")
        self.__goto_start_icon_path = os.path.join(
            self.__action_bar_icons_dir, "icon-goto-start.png"
        )
        self.__goto_end_icon_path = os.path.join(self.__action_bar_icons_dir, "icon-goto-end.png")

        self.__various_files_dir = os.path.join(self.__barks_reader_files_dir, "Various")
        self.__up_arrow_path = os.path.join(self.__various_files_dir, "up-arrow.png")
        self.__transparent_blank_path = os.path.join(
            self.__various_files_dir, "transparent-blank.png"
        )
        self.__empty_page_path = os.path.join(self.__various_files_dir, "empty-page.jpg")
        self.__user_data_path = os.path.join(self.__various_files_dir, "barks-reader.json")

        self.__check_reader_files_dirs()

    def __check_reader_files_dirs(self) -> None:
        dirs_to_check = [
            self.__barks_reader_files_dir,
            self.__reader_icon_files_dir,
            self.__action_bar_icons_dir,
            self.__various_files_dir,
        ]
        self.__check_dirs(dirs_to_check)

        files_to_check = [
            self.__app_icon_path,
            self.__close_icon_path,
            self.__collapse_icon_path,
            self.__refresh_arrow_icon_path,
            self.__settings_icon_path,
            self.__fullscreen_icon_path,
            self.__fullscreen_exit_icon_path,
            self.__goto_icon_path,
            self.__goto_start_icon_path,
            self.__goto_end_icon_path,
            self.__up_arrow_path,
            self.__transparent_blank_path,
            self.__empty_page_path,
            self.__user_data_path,
        ]
        self.__check_files(files_to_check)

    @staticmethod
    def __check_dirs(dirs_to_check: List[str]) -> None:
        for dir_path in dirs_to_check:
            if not os.path.isdir(dir_path):
                raise FileNotFoundError(f'Required directory not found: "{dir_path}".')

    @staticmethod
    def __check_files(files_to_check: List[str]) -> None:
        for file_path in files_to_check:
            if not os.path.isfile(file_path):
                raise FileNotFoundError(f'Required file not found: "{file_path}".')

    def get_barks_reader_user_data_file(self) -> str:
        return self.__user_data_path

    def get_barks_reader_app_icon_file(self) -> str:
        return self.__app_icon_path

    def get_up_arrow_file(self) -> str:
        return self.__up_arrow_path

    def get_barks_reader_close_icon_file(self) -> str:
        return self.__close_icon_path

    def get_barks_reader_collapse_icon_file(self) -> str:
        return self.__collapse_icon_path

    def get_barks_reader_refresh_arrow_icon_file(self) -> str:
        return self.__refresh_arrow_icon_path

    def get_barks_reader_settings_icon_file(self) -> str:
        return self.__settings_icon_path

    def get_barks_reader_fullscreen_icon_file(self) -> str:
        return self.__fullscreen_icon_path

    def get_barks_reader_fullscreen_exit_icon_file(self) -> str:
        return self.__fullscreen_exit_icon_path

    def get_barks_reader_goto_icon_file(self) -> str:
        return self.__goto_icon_path

    def get_barks_reader_goto_start_icon_file(self) -> str:
        return self.__goto_start_icon_path

    def get_barks_reader_goto_end_icon_file(self) -> str:
        return self.__goto_end_icon_path

    def get_transparent_blank_file(self) -> str:
        return self.__transparent_blank_path

    def get_empty_page_file(self) -> str:
        return self.__empty_page_path
