import logging
import os
from typing import Any, Dict, Callable

from kivy.config import ConfigParser
from kivy.uix.settings import Settings

from reader_file_paths import ReaderFilePaths, BarksPanelsExtType, DEFAULT_BARKS_READER_FILES_DIR
from system_file_paths import SystemFilePaths

HOME_DIR = os.environ.get("HOME")

BARKS_READER_SECTION = "Barks Reader"

FANTA_DIR = "fanta_dir"
READER_FILES_DIR = "reader_files_dir"
PREBUILT_COMICS_DIR = "prebuilt_dir"
PNG_BARKS_PANELS_DIR = "png_barks_panels_dir"
JPG_BARKS_PANELS_DIR = "jpg_barks_panels_dir"
USE_PNG_IMAGES = "use_png_images"
USE_PREBUILT_COMICS = "use_prebuilt_comics"
GOTO_SAVED_NODE_ON_START = "goto_saved_node_on_start"

_READER_SETTINGS_JSON = f"""
[
   {{  "type": "title", "title": "Folders" }},
   {{
      "title": "Fantagraphics Directory",
      "desc": "Directory containing the Fantagraphics comic zips",
      "type": "path",
      "section": "{BARKS_READER_SECTION}",
      "key": "{FANTA_DIR}"
   }},
   {{
      "title": "Reader Files Directory",
      "desc": "Directory containing all the required Barks Reader files",
      "type": "path",
      "section": "{BARKS_READER_SECTION}",
      "key": "{READER_FILES_DIR}"
   }},
   {{
      "title": "Prebuilt Comics Directory",
      "desc": "Directory containing specially prebuilt comics",
      "type": "path",
      "section": "{BARKS_READER_SECTION}",
      "key": "{PREBUILT_COMICS_DIR}"
   }},
   {{
      "title": "Png Barks Panels Directory",
      "desc": "Directory containing Barks panels png images",
      "type": "path",
      "section": "{BARKS_READER_SECTION}",
      "key": "{PNG_BARKS_PANELS_DIR}"
   }},
   {{
      "title": "Jpg Barks Panels Directory",
      "desc": "Directory containing Barks panels jpg images",
      "type": "path",
      "section": "{BARKS_READER_SECTION}",
      "key": "{JPG_BARKS_PANELS_DIR}"
   }},
   {{  "type": "title", "title": "Options" }},
   {{
      "title": "Use Png Images",
      "desc": "Use png images where possible (needs app RESTART if changed)",
      "type": "bool",
      "section": "{BARKS_READER_SECTION}",
      "key": "{USE_PNG_IMAGES}"
   }},
   {{
      "title": "Use Prebuilt Comics",
      "desc": "Read comics from the prebuilt comics folder",
      "type": "bool",
      "section": "{BARKS_READER_SECTION}",
      "key": "{USE_PREBUILT_COMICS}"
   }},
   {{
      "title": "Goto Last Selection on Start",
      "desc": "When the app starts, goto the last selection in the tree view",
      "type": "bool",
      "section": "{BARKS_READER_SECTION}",
      "key": "{GOTO_SAVED_NODE_ON_START}"
   }}
]
"""


class ReaderSettings:
    def __init__(self):
        self.__config = None
        self.__reader_file_paths: ReaderFilePaths = ReaderFilePaths()
        self.__reader_sys_file_paths: SystemFilePaths = SystemFilePaths()

        self.VALIDATION_METHODS: Dict[str, Callable[[str], bool]] = {
            FANTA_DIR: self.is_valid_fantagraphics_volumes_dir,
            READER_FILES_DIR: self.is_valid_reader_files_dir,
            PNG_BARKS_PANELS_DIR: self.is_valid_png_barks_panels_dir,
            JPG_BARKS_PANELS_DIR: self.is_valid_jpg_barks_panels_dir,
            USE_PNG_IMAGES: self.is_valid_use_png_images,
            PREBUILT_COMICS_DIR: self.is_valid_prebuilt_comics_dir,
            USE_PREBUILT_COMICS: self.is_valid_use_prebuilt_archives,
            GOTO_SAVED_NODE_ON_START: self.is_valid_goto_saved_node_on_start,
        }
        self.GETTER_METHODS = {
            FANTA_DIR: self.__get_fantagraphics_volumes_dir,
            READER_FILES_DIR: self.__get_reader_files_dir,
            PNG_BARKS_PANELS_DIR: self.__get_png_barks_panels_dir,
            JPG_BARKS_PANELS_DIR: self.__get_jpg_barks_panels_dir,
            USE_PNG_IMAGES: self.__get_use_png_images,
            PREBUILT_COMICS_DIR: self.__get_prebuilt_comics_dir,
            USE_PREBUILT_COMICS: self.__get_use_prebuilt_archives,
            GOTO_SAVED_NODE_ON_START: self.__get_goto_saved_node_on_start,
        }

    def get_config(self) -> ConfigParser:
        return self.__config

    def set_config(self, config: ConfigParser) -> None:
        self.__config = config

    @staticmethod
    def build_config(config: ConfigParser):
        config.setdefaults(
            BARKS_READER_SECTION,
            {
                FANTA_DIR: ReaderFilePaths.get_default_fanta_volume_archives_root_dir(),
                READER_FILES_DIR: DEFAULT_BARKS_READER_FILES_DIR,
                PNG_BARKS_PANELS_DIR: ReaderFilePaths.get_default_png_barks_panels_dir(),
                JPG_BARKS_PANELS_DIR: ReaderFilePaths.get_default_jpg_barks_panels_dir(),
                USE_PNG_IMAGES: True,
                PREBUILT_COMICS_DIR: ReaderFilePaths.get_default_prebuilt_comic_zips_dir(),
                USE_PREBUILT_COMICS: False,
                GOTO_SAVED_NODE_ON_START: True,
            },
        )

    def build_settings(self, settings: Settings):
        settings.add_json_panel(BARKS_READER_SECTION, self.__config, data=_READER_SETTINGS_JSON)

    def validate_settings(self) -> None:
        for key in self.VALIDATION_METHODS:
            self.VALIDATION_METHODS[key](self.GETTER_METHODS[key]())

    def on_changed_setting(self, section: str, key: str, value: Any) -> bool:
        if section != BARKS_READER_SECTION:
            return True

        assert key in self.VALIDATION_METHODS
        if not self.VALIDATION_METHODS[key](value):
            return False

        if key in [PNG_BARKS_PANELS_DIR, JPG_BARKS_PANELS_DIR]:
            self.__reader_file_paths.set_barks_panels_dir(value, self.__get_barks_panels_ext_type())
        elif key == USE_PNG_IMAGES:
            if value:
                self.__reader_file_paths.set_barks_panels_dir(
                    self.__get_png_barks_panels_dir(), BarksPanelsExtType.MOSTLY_PNG
                )
            else:
                self.__reader_file_paths.set_barks_panels_dir(
                    self.__get_jpg_barks_panels_dir(), BarksPanelsExtType.JPG
                )

        return True

    @property
    def file_paths(self) -> ReaderFilePaths:
        return self.__reader_file_paths

    @property
    def sys_file_paths(self) -> SystemFilePaths:
        return self.__reader_sys_file_paths

    def set_barks_reader_files_dir(self, reader_files_dir: str) -> None:
        self.__reader_sys_file_paths.set_barks_reader_files_dir(reader_files_dir)

    def set_barks_panels_dir(self) -> None:
        if self.__get_use_png_images():
            self.__reader_file_paths.set_barks_panels_dir(
                self.__get_png_barks_panels_dir(), BarksPanelsExtType.MOSTLY_PNG
            )
        else:
            self.__reader_file_paths.set_barks_panels_dir(
                self.__get_jpg_barks_panels_dir(), BarksPanelsExtType.JPG
            )

    def __get_png_barks_panels_dir(self) -> str:
        return self.__config.get(BARKS_READER_SECTION, PNG_BARKS_PANELS_DIR)

    def __get_jpg_barks_panels_dir(self) -> str:
        return self.__config.get(BARKS_READER_SECTION, JPG_BARKS_PANELS_DIR)

    def __get_barks_panels_ext_type(self) -> BarksPanelsExtType:
        return self.__get_barks_panels_ext_type_from_bool(self.__get_use_png_images())

    @staticmethod
    def __get_barks_panels_ext_type_from_bool(use_png_images: bool) -> BarksPanelsExtType:
        return BarksPanelsExtType.MOSTLY_PNG if use_png_images else BarksPanelsExtType.JPG

    def __get_use_png_images(self) -> bool:
        return self.__config.getboolean(BARKS_READER_SECTION, USE_PNG_IMAGES)

    @property
    def fantagraphics_volumes_dir(self) -> str:
        return self.__get_fantagraphics_volumes_dir()

    def __get_fantagraphics_volumes_dir(self) -> str:
        return self.__config.get(BARKS_READER_SECTION, FANTA_DIR)

    @property
    def reader_files_dir(self) -> str:
        return self.__get_reader_files_dir()

    def __get_reader_files_dir(self) -> str:
        return self.__config.get(BARKS_READER_SECTION, READER_FILES_DIR)

    @property
    def prebuilt_comics_dir(self) -> str:
        return self.__get_prebuilt_comics_dir()

    def __get_prebuilt_comics_dir(self) -> str:
        return self.__config.get(BARKS_READER_SECTION, PREBUILT_COMICS_DIR)

    @property
    def use_prebuilt_archives(self) -> bool:
        return self.__get_use_prebuilt_archives()

    def __get_use_prebuilt_archives(self) -> bool:
        return self.__config.getboolean(BARKS_READER_SECTION, USE_PREBUILT_COMICS)

    @property
    def goto_saved_node_on_start(self) -> bool:
        return self.__get_goto_saved_node_on_start()

    def __get_goto_saved_node_on_start(self):
        return self.__config.getboolean(BARKS_READER_SECTION, GOTO_SAVED_NODE_ON_START)

    def is_valid_fantagraphics_volumes_dir(self, dir_path: str) -> bool:
        return self.__is_valid_dir(dir_path)

    def is_valid_reader_files_dir(self, dir_path: str) -> bool:
        return self.__is_valid_dir(dir_path)

    def is_valid_prebuilt_comics_dir(self, dir_path: str) -> bool:
        return self.__is_valid_dir(dir_path)

    def is_valid_use_prebuilt_archives(self, use_prebuilt_archives: bool) -> bool:
        if not use_prebuilt_archives:
            return True

        return self.is_valid_prebuilt_comics_dir(self.prebuilt_comics_dir)

    @staticmethod
    def is_valid_goto_saved_node_on_start(_goto_saved_node_on_start: bool):
        return True

    def is_valid_png_barks_panels_dir(self, dir_path: str) -> bool:
        return self.__is_valid_dir(dir_path)

    def is_valid_jpg_barks_panels_dir(self, dir_path: str) -> bool:
        return self.__is_valid_dir(dir_path)

    def is_valid_use_png_images(self, use_png_images: bool) -> bool:
        if use_png_images:
            return self.is_valid_png_barks_panels_dir(self.__get_png_barks_panels_dir())

        return self.is_valid_jpg_barks_panels_dir(self.__get_jpg_barks_panels_dir())

    @staticmethod
    def __is_valid_dir(dir_path: str) -> bool:
        if os.path.isdir(dir_path):
            return True

        logging.error(f'Required directory not found: "{dir_path}".')
        return False
