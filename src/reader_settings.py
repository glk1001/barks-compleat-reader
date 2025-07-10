import logging
import os
from typing import Any, Dict, Callable

from kivy.config import ConfigParser
from kivy.uix.settings import Settings

import file_paths
from file_paths import (
    BarksPanelsExtType,
    get_default_fanta_volume_archives_root_dir,
    get_default_prebuilt_comic_zips_dir,
    get_default_png_barks_panels_dir,
    get_default_jpg_barks_panels_dir,
)

HOME_DIR = os.environ.get("HOME")

BARKS_READER_SECTION = "Barks Reader"

FANTA_DIR = "fanta_dir"
PREBUILT_COMICS_DIR = "prebuilt_dir"
PNG_BARKS_PANELS_DIR = "png_barks_panels_dir"
JPG_BARKS_PANELS_DIR = "jpg_barks_panels_dir"
USE_PNG_IMAGES = "use_png_images"
USE_PREBUILT_COMICS = "use_prebuilt_comics"

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
   }}
]
"""


class ReaderSettings:
    def __init__(self):
        self.__config = None

        self.VALIDATION_METHODS: Dict[str, Callable[[str], bool]] = {
            FANTA_DIR: self.is_valid_fantagraphics_volumes_dir,
            PNG_BARKS_PANELS_DIR: self.is_valid_png_barks_panels_dir,
            JPG_BARKS_PANELS_DIR: self.is_valid_jpg_barks_panels_dir,
            USE_PNG_IMAGES: self.is_valid_use_png_images,
            PREBUILT_COMICS_DIR: self.is_valid_prebuilt_comics_dir,
            USE_PREBUILT_COMICS: self.is_valid_use_prebuilt_archives,
        }
        self.GETTER_METHODS = {
            FANTA_DIR: self.__get_fantagraphics_volumes_dir,
            PNG_BARKS_PANELS_DIR: self.__get_png_barks_panels_dir,
            JPG_BARKS_PANELS_DIR: self.__get_jpg_barks_panels_dir,
            USE_PNG_IMAGES: self.__get_use_png_images,
            PREBUILT_COMICS_DIR: self.__get_prebuilt_comics_dir,
            USE_PREBUILT_COMICS: self.__get_use_prebuilt_archives,
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
                FANTA_DIR: get_default_fanta_volume_archives_root_dir(),
                PNG_BARKS_PANELS_DIR: get_default_png_barks_panels_dir(),
                JPG_BARKS_PANELS_DIR: get_default_jpg_barks_panels_dir(),
                USE_PNG_IMAGES: True,
                PREBUILT_COMICS_DIR: get_default_prebuilt_comic_zips_dir(),
                USE_PREBUILT_COMICS: False,
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
            file_paths.set_barks_panels_dir(
                value,
                self.barks_panels_ext_type,
            )
        elif key == USE_PNG_IMAGES:
            if value:
                file_paths.set_barks_panels_dir(
                    self.png_barks_panels_dir, BarksPanelsExtType.MOSTLY_PNG
                )
            else:
                file_paths.set_barks_panels_dir(self.jpg_barks_panels_dir, BarksPanelsExtType.JPG)

        return True

    @property
    def fantagraphics_volumes_dir(self) -> str:
        return self.__get_fantagraphics_volumes_dir()

    def __get_fantagraphics_volumes_dir(self) -> str:
        return self.__config.get(BARKS_READER_SECTION, FANTA_DIR)

    def set_barks_panels_dir(self) -> None:
        if self.__get_use_png_images():
            file_paths.set_barks_panels_dir(
                self.png_barks_panels_dir, BarksPanelsExtType.MOSTLY_PNG
            )
        else:
            file_paths.set_barks_panels_dir(self.jpg_barks_panels_dir, BarksPanelsExtType.JPG)

    @property
    def png_barks_panels_dir(self) -> str:
        return self.__get_png_barks_panels_dir()

    def __get_png_barks_panels_dir(self) -> str:
        return self.__config.get(BARKS_READER_SECTION, PNG_BARKS_PANELS_DIR)

    @property
    def jpg_barks_panels_dir(self) -> str:
        return self.__get_jpg_barks_panels_dir()

    def __get_jpg_barks_panels_dir(self) -> str:
        return self.__config.get(BARKS_READER_SECTION, JPG_BARKS_PANELS_DIR)

    @property
    def barks_panels_ext_type(self) -> BarksPanelsExtType:
        return self.__get_barks_panels_ext_type()

    def __get_barks_panels_ext_type(self) -> BarksPanelsExtType:
        return self.__get_barks_panels_ext_type_from_bool(self.__get_use_png_images())

    @staticmethod
    def __get_barks_panels_ext_type_from_bool(use_png_images: bool) -> BarksPanelsExtType:
        return BarksPanelsExtType.MOSTLY_PNG if use_png_images else BarksPanelsExtType.JPG

    def __get_use_png_images(self) -> bool:
        return self.__config.getboolean(BARKS_READER_SECTION, USE_PNG_IMAGES)

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

    def is_valid_fantagraphics_volumes_dir(self, dir_path: str) -> bool:
        return self.__is_valid_dir(dir_path)

    def is_valid_png_barks_panels_dir(self, dir_path: str) -> bool:
        return self.__is_valid_dir(dir_path)

    def is_valid_jpg_barks_panels_dir(self, dir_path: str) -> bool:
        return self.__is_valid_dir(dir_path)

    def is_valid_png_story_insets_dir(self, dir_path: str) -> bool:
        return self.__is_valid_dir(dir_path)

    def is_valid_jpg_story_insets_dir(self, dir_path: str) -> bool:
        return self.__is_valid_dir(dir_path)

    def is_valid_use_png_images(self, use_png_images: bool) -> bool:
        if use_png_images:
            return self.is_valid_png_barks_panels_dir(self.png_barks_panels_dir)

        return self.is_valid_jpg_barks_panels_dir(self.jpg_barks_panels_dir)

    def is_valid_prebuilt_comics_dir(self, dir_path: str) -> bool:
        return self.__is_valid_dir(dir_path)

    def is_valid_use_prebuilt_archives(self, use_prebuilt_archives: bool) -> bool:
        if not use_prebuilt_archives:
            return True

        return self.is_valid_prebuilt_comics_dir(self.prebuilt_comics_dir)

    @staticmethod
    def __is_valid_dir(dir_path: str) -> bool:
        if os.path.isdir(dir_path):
            return True

        logging.error(f'Required directory not found: "{dir_path}".')
        return False
