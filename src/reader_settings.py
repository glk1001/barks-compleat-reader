import os
from typing import Any

from kivy.config import ConfigParser
from kivy.uix.settings import Settings

from file_paths import (
    get_default_fanta_volume_archives_root_dir,
    get_default_prebuilt_comic_zips_dir,
)

HOME_DIR = os.environ.get("HOME")

BARKS_READER_SECTION = "Barks Reader"

FANTA_FOLDER = "fanta_folder"
PREBUILT_FOLDER = "prebuilt_folder"
USE_PREBUILT_COMICS = "use_prebuilt_comics"

_READER_SETTINGS_JSON = f"""
[
   {{  "type": "title", "title": "Folders" }},
   {{
      "title": "Fantagraphics Folder",
      "desc": "Folder containing the Fantagraphics comic zips",
      "type": "path",
      "section": "{BARKS_READER_SECTION}",
      "key": "{FANTA_FOLDER}"
   }},
   {{
      "title": "Prebuilt Comics",
      "desc": "Folder containing specially prebuilt comics",
      "type": "path",
      "section": "{BARKS_READER_SECTION}",
      "key": "{PREBUILT_FOLDER}"
   }},
   {{  "type": "title", "title": "Options" }},
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

    def get_config(self) -> ConfigParser:
        return self.__config

    def set_config(self, config: ConfigParser) -> None:
        self.__config = config

    @staticmethod
    def build_config(config: ConfigParser):
        config.setdefaults(
            BARKS_READER_SECTION,
            {
                FANTA_FOLDER: get_default_fanta_volume_archives_root_dir(),
                PREBUILT_FOLDER: get_default_prebuilt_comic_zips_dir(),
                USE_PREBUILT_COMICS: False,
            },
        )

    def build_settings(self, settings: Settings):
        settings.add_json_panel(BARKS_READER_SECTION, self.__config, data=_READER_SETTINGS_JSON)

    # TODO: Fill this out with separate validation method per setting
    def validate_settings(self) -> None:
        pass

    # TODO: Fill this out with validation method for setting
    def validate_changed_setting(self, section: str, key: str, value: Any) -> None:
        pass

    @property
    def fantagraphics_volumes_dir(self) -> str:
        return self.__config.get(BARKS_READER_SECTION, FANTA_FOLDER)

    @property
    def prebuilt_comics_dir(self) -> str:
        return self.__config.get(BARKS_READER_SECTION, PREBUILT_FOLDER)

    @property
    def use_prebuilt_archives(self) -> bool:
        return self.__config.getboolean(BARKS_READER_SECTION, USE_PREBUILT_COMICS)
