import logging
import os
from typing import Any, Dict, Callable

from kivy.config import ConfigParser
from kivy.uix.settings import Settings

from reader_file_paths import ReaderFilePaths, BarksPanelsExtType, DEFAULT_BARKS_READER_FILES_DIR
from settings_fix import LONG_PATH
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
USE_HARPIES_INSTEAD_OF_LARKIES = "use_harpies"
USE_DERE_INSTEAD_OF_THEAH = "use_dere"
USE_BLANK_EYEBALLS_FOR_BOMBIE = "use_blank_eyeballs"
USE_GLK_FIREBUG_ENDING = "use_glk_firebug_ending"

_READER_SETTINGS_JSON = f"""
[
   {{  "type": "title", "title": "Folders" }},
   {{
      "title": "Fantagraphics Directory",
      "desc": "Directory containing the Fantagraphics comic zips",
      "type": "{LONG_PATH}",
      "section": "{BARKS_READER_SECTION}",
      "key": "{FANTA_DIR}"
   }},
   {{
      "title": "Reader Files Directory",
      "desc": "Directory containing all the required Barks Reader files",
      "type": "{LONG_PATH}",
      "section": "{BARKS_READER_SECTION}",
      "key": "{READER_FILES_DIR}"
   }},
   {{
      "title": "Prebuilt Comics Directory",
      "desc": "Directory containing specially prebuilt comics",
      "type": "{LONG_PATH}",
      "section": "{BARKS_READER_SECTION}",
      "key": "{PREBUILT_COMICS_DIR}"
   }},
   {{
      "title": "Png Barks Panels Directory",
      "desc": "Directory containing Barks panels png images",
      "type": "{LONG_PATH}",
      "section": "{BARKS_READER_SECTION}",
      "key": "{PNG_BARKS_PANELS_DIR}"
   }},
   {{
      "title": "Jpg Barks Panels Directory",
      "desc": "Directory containing Barks panels jpg images",
      "type": "{LONG_PATH}",
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
   }},
   {{
      "title": "Use 'Harpies' Instead of 'Larkies'",
      "desc": "When reading 'The Golden Fleecing', use 'Harpies' instead of 'Larkies'",
      "type": "bool",
      "section": "{BARKS_READER_SECTION}",
      "key": "{USE_HARPIES_INSTEAD_OF_LARKIES}"
   }},
   {{
      "title": "Use 'Dere' Instead of 'Theah'",
      "desc": "When reading 'Lost in the Andes!', use 'Dere' instead of 'Theah'",
      "type": "bool",
      "section": "{BARKS_READER_SECTION}",
      "key": "{USE_DERE_INSTEAD_OF_THEAH}"
   }},
   {{
      "title": "Use Blank Eyeballs for Bombie",
      "desc": "When reading 'Voodoo Hoodoo', use blank eyeballs for Bombie the Zombie",
      "type": "bool",
      "section": "{BARKS_READER_SECTION}",
      "key": "{USE_BLANK_EYEBALLS_FOR_BOMBIE}"
   }},
   {{
      "title": "Don't Use Fantagraphics Ending for 'The Firebug'",
      "desc": "When reading 'The Firebug', don't use the Fantagraphics ending",
      "type": "bool",
      "section": "{BARKS_READER_SECTION}",
      "key": "{USE_GLK_FIREBUG_ENDING}"
   }}
]
"""


class ReaderSettings:
    def __init__(self):
        self._config = None
        self._app_settings_path = ""
        self._user_data_path = ""
        self._reader_file_paths: ReaderFilePaths = ReaderFilePaths()
        self._reader_sys_file_paths: SystemFilePaths = SystemFilePaths()

        self._VALIDATION_METHODS: Dict[str, Callable[[str], bool]] = {
            FANTA_DIR: self.is_valid_fantagraphics_volumes_dir,
            READER_FILES_DIR: self._is_valid_reader_files_dir,
            PNG_BARKS_PANELS_DIR: self._is_valid_png_barks_panels_dir,
            JPG_BARKS_PANELS_DIR: self._is_valid_jpg_barks_panels_dir,
            USE_PNG_IMAGES: self._is_valid_use_png_images,
            PREBUILT_COMICS_DIR: self._is_valid_prebuilt_comics_dir,
            USE_PREBUILT_COMICS: self._is_valid_use_prebuilt_archives,
            GOTO_SAVED_NODE_ON_START: self._is_valid_goto_saved_node_on_start,
            USE_HARPIES_INSTEAD_OF_LARKIES: self._is_valid_use_harpies_instead_of_larkies,
            USE_DERE_INSTEAD_OF_THEAH: self._is_valid_use_dere_instead_of_theah,
            USE_BLANK_EYEBALLS_FOR_BOMBIE: self._is_valid_use_blank_eyeballs_for_bombie,
            USE_GLK_FIREBUG_ENDING: self._is_valid_use_glk_firebug_ending,
        }
        self._GETTER_METHODS = {
            FANTA_DIR: self._get_fantagraphics_volumes_dir,
            READER_FILES_DIR: self._get_reader_files_dir,
            PNG_BARKS_PANELS_DIR: self._get_png_barks_panels_dir,
            JPG_BARKS_PANELS_DIR: self._get_jpg_barks_panels_dir,
            USE_PNG_IMAGES: self._get_use_png_images,
            PREBUILT_COMICS_DIR: self._get_prebuilt_comics_dir,
            USE_PREBUILT_COMICS: self._get_use_prebuilt_archives,
            GOTO_SAVED_NODE_ON_START: self._get_goto_saved_node_on_start,
            USE_HARPIES_INSTEAD_OF_LARKIES: self.get_use_harpies_instead_of_larkies,
            USE_DERE_INSTEAD_OF_THEAH: self.get_use_dere_instead_of_theah,
            USE_BLANK_EYEBALLS_FOR_BOMBIE: self.get_use_blank_eyeballs_for_bombie,
            USE_GLK_FIREBUG_ENDING: self.get_use_glk_firebug_ending,
        }

    def set_config(self, config: ConfigParser, app_settings_path: str) -> None:
        self._config = config
        self._app_settings_path = app_settings_path
        self._user_data_path = os.path.join(
            os.path.dirname(self._app_settings_path), "barks-reader.json"
        )

    def get_app_settings_path(self) -> str:
        return self._app_settings_path

    def get_user_data_path(self) -> str:
        return self._user_data_path

    @staticmethod
    def build_config(config: ConfigParser):
        # NOTE: For some reason we need to use 0/1 instead of False/True.
        #       Not sure why.
        config.setdefaults(
            BARKS_READER_SECTION,
            {
                FANTA_DIR: ReaderFilePaths.get_default_fanta_volume_archives_root_dir(),
                READER_FILES_DIR: DEFAULT_BARKS_READER_FILES_DIR,
                PNG_BARKS_PANELS_DIR: ReaderFilePaths.get_default_png_barks_panels_dir(),
                JPG_BARKS_PANELS_DIR: ReaderFilePaths.get_default_jpg_barks_panels_dir(),
                USE_PNG_IMAGES: 1,
                PREBUILT_COMICS_DIR: ReaderFilePaths.get_default_prebuilt_comic_zips_dir(),
                USE_PREBUILT_COMICS: 0,
                GOTO_SAVED_NODE_ON_START: 1,
                USE_HARPIES_INSTEAD_OF_LARKIES: 1,
                USE_DERE_INSTEAD_OF_THEAH: 1,
                USE_BLANK_EYEBALLS_FOR_BOMBIE: 1,
                USE_GLK_FIREBUG_ENDING: 1,
            },
        )

    def build_settings(self, settings: Settings):
        settings.add_json_panel(BARKS_READER_SECTION, self._config, data=_READER_SETTINGS_JSON)

    def validate_settings(self) -> None:
        for key in self._VALIDATION_METHODS:
            self._VALIDATION_METHODS[key](self._GETTER_METHODS[key]())

    def on_changed_setting(self, section: str, key: str, value: Any) -> bool:
        if section != BARKS_READER_SECTION:
            return True

        assert key in self._VALIDATION_METHODS
        if not self._VALIDATION_METHODS[key](value):
            return False

        if key in [PNG_BARKS_PANELS_DIR, JPG_BARKS_PANELS_DIR]:
            self._reader_file_paths.set_barks_panels_dir(value, self._get_barks_panels_ext_type())
        elif key == USE_PNG_IMAGES:
            if value:
                self._reader_file_paths.set_barks_panels_dir(
                    self._get_png_barks_panels_dir(), BarksPanelsExtType.MOSTLY_PNG
                )
            else:
                self._reader_file_paths.set_barks_panels_dir(
                    self._get_jpg_barks_panels_dir(), BarksPanelsExtType.JPG
                )

        return True

    @property
    def file_paths(self) -> ReaderFilePaths:
        return self._reader_file_paths

    @property
    def sys_file_paths(self) -> SystemFilePaths:
        return self._reader_sys_file_paths

    def set_barks_reader_files_dir(self, reader_files_dir: str) -> None:
        self._reader_sys_file_paths.set_barks_reader_files_dir(reader_files_dir)

    def set_barks_panels_dir(self) -> None:
        if self._get_use_png_images():
            self._reader_file_paths.set_barks_panels_dir(
                self._get_png_barks_panels_dir(), BarksPanelsExtType.MOSTLY_PNG
            )
        else:
            self._reader_file_paths.set_barks_panels_dir(
                self._get_jpg_barks_panels_dir(), BarksPanelsExtType.JPG
            )

    def _get_png_barks_panels_dir(self) -> str:
        return self._config.get(BARKS_READER_SECTION, PNG_BARKS_PANELS_DIR)

    def _get_jpg_barks_panels_dir(self) -> str:
        return self._config.get(BARKS_READER_SECTION, JPG_BARKS_PANELS_DIR)

    def _get_barks_panels_ext_type(self) -> BarksPanelsExtType:
        return self._get_barks_panels_ext_type_from_bool(self._get_use_png_images())

    @staticmethod
    def _get_barks_panels_ext_type_from_bool(use_png_images: bool) -> BarksPanelsExtType:
        return BarksPanelsExtType.MOSTLY_PNG if use_png_images else BarksPanelsExtType.JPG

    def _get_use_png_images(self) -> bool:
        return self._config.getboolean(BARKS_READER_SECTION, USE_PNG_IMAGES)

    @property
    def fantagraphics_volumes_dir(self) -> str:
        return self._get_fantagraphics_volumes_dir()

    def _get_fantagraphics_volumes_dir(self) -> str:
        return self._config.get(BARKS_READER_SECTION, FANTA_DIR)

    @property
    def reader_files_dir(self) -> str:
        return self._get_reader_files_dir()

    def _get_reader_files_dir(self) -> str:
        if not self._config:
            # TODO: Not viable?? - Bootstrap problem. Return default.
            return DEFAULT_BARKS_READER_FILES_DIR

        return self._config.get(BARKS_READER_SECTION, READER_FILES_DIR)

    @property
    def prebuilt_comics_dir(self) -> str:
        return self._get_prebuilt_comics_dir()

    def _get_prebuilt_comics_dir(self) -> str:
        return self._config.get(BARKS_READER_SECTION, PREBUILT_COMICS_DIR)

    @property
    def use_prebuilt_archives(self) -> bool:
        return self._get_use_prebuilt_archives()

    def _get_use_prebuilt_archives(self) -> bool:
        return self._config.getboolean(BARKS_READER_SECTION, USE_PREBUILT_COMICS)

    @property
    def goto_saved_node_on_start(self) -> bool:
        return self._get_goto_saved_node_on_start()

    def _get_goto_saved_node_on_start(self):
        return self._config.getboolean(BARKS_READER_SECTION, GOTO_SAVED_NODE_ON_START)

    def get_use_harpies_instead_of_larkies(self):
        return self._config.getboolean(BARKS_READER_SECTION, USE_HARPIES_INSTEAD_OF_LARKIES)

    def get_use_dere_instead_of_theah(self):
        return self._config.getboolean(BARKS_READER_SECTION, USE_DERE_INSTEAD_OF_THEAH)

    def get_use_blank_eyeballs_for_bombie(self):
        return self._config.getboolean(BARKS_READER_SECTION, USE_BLANK_EYEBALLS_FOR_BOMBIE)

    def get_use_glk_firebug_ending(self):
        return self._config.getboolean(BARKS_READER_SECTION, USE_GLK_FIREBUG_ENDING)

    def is_valid_fantagraphics_volumes_dir(self, dir_path: str) -> bool:
        if self.use_prebuilt_archives:
            return True
        return self._is_valid_dir(dir_path)

    def _is_valid_reader_files_dir(self, dir_path: str) -> bool:
        return self._is_valid_dir(dir_path)

    def _is_valid_prebuilt_comics_dir(self, dir_path: str) -> bool:
        return self._is_valid_dir(dir_path)

    def _is_valid_use_prebuilt_archives(self, use_prebuilt_archives: bool) -> bool:
        if not use_prebuilt_archives:
            return True

        return self._is_valid_prebuilt_comics_dir(self.prebuilt_comics_dir)

    @staticmethod
    def _is_valid_goto_saved_node_on_start(_goto_saved_node_on_start: bool):
        return True

    @staticmethod
    def _is_valid_use_harpies_instead_of_larkies(_use_harpies_instead_of_larkies: bool):
        return True

    @staticmethod
    def _is_valid_use_dere_instead_of_theah(_use_dere_instead_of_theah: bool):
        return True

    @staticmethod
    def _is_valid_use_blank_eyeballs_for_bombie(_use_blank_eyeballs_for_bombie: bool):
        return True

    @staticmethod
    def _is_valid_use_glk_firebug_ending(_use_glk_firebug_ending: bool):
        return True

    def _is_valid_png_barks_panels_dir(self, dir_path: str) -> bool:
        return self._is_valid_dir(dir_path)

    def _is_valid_jpg_barks_panels_dir(self, dir_path: str) -> bool:
        return self._is_valid_dir(dir_path)

    def _is_valid_use_png_images(self, use_png_images: bool) -> bool:
        if use_png_images:
            return self._is_valid_png_barks_panels_dir(self._get_png_barks_panels_dir())

        return self._is_valid_jpg_barks_panels_dir(self._get_jpg_barks_panels_dir())

    @staticmethod
    def _is_valid_dir(dir_path: str) -> bool:
        if os.path.isdir(dir_path):
            return True

        logging.error(f'Reader Settings: Required directory not found: "{dir_path}".')
        return False
