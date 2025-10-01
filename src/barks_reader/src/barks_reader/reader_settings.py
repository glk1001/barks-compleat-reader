from __future__ import annotations

from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, override

from loguru import logger

from barks_reader.reader_consts_and_types import LONG_PATH_SETTING
from barks_reader.reader_file_paths import (
    DEFAULT_BARKS_READER_FILES_DIR,
    BarksPanelsExtType,
    ReaderFilePaths,
)
from barks_reader.system_file_paths import SystemFilePaths

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.boxlayout import BoxLayout


class FantaVolumesState(Enum):
    VOLUMES_EXIST = auto()
    VOLUMES_MISSING = auto()
    VOLUMES_NOT_SET = auto()
    VOLUMES_NOT_NEEDED = auto()


BARKS_READER_SECTION = "Barks Reader"

FANTA_DIR = "fanta_dir"
UNSET_FANTA_DIR_MARKER = "<Fantagraphics Volumes Not Set>"
READER_FILES_DIR = "reader_files_dir"
PREBUILT_COMICS_DIR = "prebuilt_dir"
PNG_BARKS_PANELS_DIR = "png_barks_panels_dir"
JPG_BARKS_PANELS_SOURCE = "jpg_barks_panels_source"
USE_PNG_IMAGES = "use_png_images"
USE_PREBUILT_COMICS = "use_prebuilt_comics"
GOTO_SAVED_NODE_ON_START = "goto_saved_node_on_start"
USE_HARPIES_INSTEAD_OF_LARKIES = "use_harpies"
USE_DERE_INSTEAD_OF_THEAH = "use_dere"
USE_BLANK_EYEBALLS_FOR_BOMBIE = "use_blank_eyeballs"
USE_GLK_FIREBUG_ENDING = "use_glk_firebug_ending"
IS_FIRST_USE_OF_READER = "is_first_use_of_reader"
MAIN_WINDOW_HEIGHT = "main_window_height"
MAIN_WINDOW_LEFT = "main_window_left"
MAIN_WINDOW_TOP = "main_window_top"

# noinspection LongLine
_READER_SETTINGS_JSON = f"""
[
   {{  "type": "title", "title": "Folders" }},
   {{
      "title": "Fantagraphics Directory",
      "desc": "Directory containing the Fantagraphics comic zips.",
      "type": "{LONG_PATH_SETTING}",
      "section": "{BARKS_READER_SECTION}",
      "key": "{FANTA_DIR}"
   }},
   {{
      "title": "Reader Files Directory",
      "desc": "Directory containing all the required Barks Reader files.",
      "type": "{LONG_PATH_SETTING}",
      "section": "{BARKS_READER_SECTION}",
      "key": "{READER_FILES_DIR}"
   }},
   {{
      "title": "Prebuilt Comics Directory",
      "desc": "Directory containing specially prebuilt comics.",
      "type": "{LONG_PATH_SETTING}",
      "section": "{BARKS_READER_SECTION}",
      "key": "{PREBUILT_COMICS_DIR}"
   }},
   {{
      "title": "Png Barks Panels Directory",
      "desc": "Directory containing Barks panels png images.",
      "type": "{LONG_PATH_SETTING}",
      "section": "{BARKS_READER_SECTION}",
      "key": "{PNG_BARKS_PANELS_DIR}"
   }},
   {{
      "title": "Jpg Barks Panels Directory",
      "desc": "Directory containing Barks panels jpg images.",
      "type": "{LONG_PATH_SETTING}",
      "section": "{BARKS_READER_SECTION}",
      "key": "{JPG_BARKS_PANELS_SOURCE}"
   }},
   {{  "type": "title", "title": "Options" }},
   {{
      "title": "Use Png Images",
      "desc": "Use png images where possible (needs app RESTART if changed).",
      "type": "bool",
      "section": "{BARKS_READER_SECTION}",
      "key": "{USE_PNG_IMAGES}"
   }},
   {{
      "title": "Use Prebuilt Comics",
      "desc": "Read comics from the prebuilt comics folder.",
      "type": "bool",
      "section": "{BARKS_READER_SECTION}",
      "key": "{USE_PREBUILT_COMICS}"
   }},
   {{
      "title": "Goto Last Selection on Start",
      "desc": "When the app starts, goto the last selection in the tree view.",
      "type": "bool",
      "section": "{BARKS_READER_SECTION}",
      "key": "{GOTO_SAVED_NODE_ON_START}"
   }},
   {{
      "title": "Use 'Harpies' Instead of 'Larkies'",
      "desc": "When reading 'The Golden Fleecing', use 'Harpies' instead of 'Larkies'.",
      "type": "bool",
      "section": "{BARKS_READER_SECTION}",
      "key": "{USE_HARPIES_INSTEAD_OF_LARKIES}"
   }},
   {{
      "title": "Use 'Dere' Instead of 'Theah'",
      "desc": "When reading 'Lost in the Andes!', use 'Dere' instead of 'Theah'.",
      "type": "bool",
      "section": "{BARKS_READER_SECTION}",
      "key": "{USE_DERE_INSTEAD_OF_THEAH}"
   }},
   {{
      "title": "Use Blank Eyeballs for Bombie",
      "desc": "When reading 'Voodoo Hoodoo', use blank eyeballs for Bombie the Zombie.",
      "type": "bool",
      "section": "{BARKS_READER_SECTION}",
      "key": "{USE_BLANK_EYEBALLS_FOR_BOMBIE}"
   }},
   {{
      "title": "Don't Use Fantagraphics Ending for 'The Firebug'",
      "desc": "When reading 'The Firebug', don't use the Fantagraphics ending.",
      "type": "bool",
      "section": "{BARKS_READER_SECTION}",
      "key": "{USE_GLK_FIREBUG_ENDING}"
   }},
   {{
      "title": "First Use of Reader",
      "desc": "Set this to true if this is the first use of the Barks reader. You need to restart the app after changing this.",
      "type": "bool",
      "section": "{BARKS_READER_SECTION}",
      "key": "{IS_FIRST_USE_OF_READER}"
   }},
   {{
      "title": "Main Window Height",
      "desc": "Set this to height you want for the main window. The width will be automatically calculated from this value. Setting to 0 will give the best fit. You need to restart the app after changing this.",
      "type": "numeric",
      "section": "{BARKS_READER_SECTION}",
      "key": "{MAIN_WINDOW_HEIGHT}"
   }},
   {{
      "title": "Main Window Left",
      "desc": "Set this to the left position of the main window. Setting to -1 will give the best fit. You need to restart the app after changing this.",
      "type": "numeric",
      "section": "{BARKS_READER_SECTION}",
      "key": "{MAIN_WINDOW_LEFT}"
   }},
   {{
      "title": "Main Window Top",
      "desc": "Set this to the top position of the main window. Setting to -1 will give the best fit. You need to restart the app after changing this.",
      "type": "numeric",
      "section": "{BARKS_READER_SECTION}",
      "key": "{MAIN_WINDOW_TOP}"
   }}
]
"""  # noqa: E501


class ConfigParser(Protocol):
    def get(self, section: str, key: str) -> Any: ...  # noqa: ANN401


class ReaderSettings:
    def __init__(self) -> None:
        self._config = None
        self._app_settings_path: Path | None = None
        self._user_data_path: Path | None = None
        self._reader_file_paths: ReaderFilePaths = ReaderFilePaths()
        self._reader_sys_file_paths: SystemFilePaths = SystemFilePaths()

    def _save_settings(self) -> None:
        pass

    def set_config(self, config: ConfigParser, app_settings_path: Path) -> None:
        self._config: ConfigParser = config
        self._app_settings_path = app_settings_path
        self._user_data_path = self._app_settings_path.parent / "barks_reader.json"

    def get_app_settings_path(self) -> Path:
        return self._app_settings_path

    def get_user_data_path(self) -> Path:
        return self._user_data_path

    @property
    def file_paths(self) -> ReaderFilePaths:
        return self._reader_file_paths

    @property
    def sys_file_paths(self) -> SystemFilePaths:
        return self._reader_sys_file_paths

    def set_barks_panels_dir(self) -> None:
        self.force_barks_panels_dir(self._get_use_png_images())

    def force_barks_panels_dir(self, use_png_images: bool) -> None:
        if use_png_images:
            self._reader_file_paths.set_barks_panels_source(
                self._get_png_barks_panels_dir(), BarksPanelsExtType.MOSTLY_PNG
            )
        else:
            self._reader_file_paths.set_barks_panels_source(
                self._get_jpg_barks_panels_source(), BarksPanelsExtType.JPG
            )

    def _get_png_barks_panels_dir(self) -> Path:
        return Path(self._config.get(BARKS_READER_SECTION, PNG_BARKS_PANELS_DIR))

    def _get_jpg_barks_panels_source(self) -> Path:
        return Path(self._config.get(BARKS_READER_SECTION, JPG_BARKS_PANELS_SOURCE))

    def _get_barks_panels_ext_type(self) -> BarksPanelsExtType:
        return self._get_barks_panels_ext_type_from_bool(self._get_use_png_images())

    @staticmethod
    def _get_barks_panels_ext_type_from_bool(use_png_images: bool) -> BarksPanelsExtType:
        return BarksPanelsExtType.MOSTLY_PNG if use_png_images else BarksPanelsExtType.JPG

    def _get_use_png_images(self) -> bool:
        return self._config.getboolean(BARKS_READER_SECTION, USE_PNG_IMAGES)

    @property
    def fantagraphics_volumes_dir(self) -> Path:
        return self._get_fantagraphics_volumes_dir()

    def _get_fantagraphics_volumes_dir(self) -> Path:
        return Path(self._config.get(BARKS_READER_SECTION, FANTA_DIR))

    @property
    def reader_files_dir(self) -> Path:
        return self._get_reader_files_dir()

    def _get_reader_files_dir(self) -> Path:
        if not self._config:
            # TODO: Not viable?? - Bootstrap problem. Return default.
            return DEFAULT_BARKS_READER_FILES_DIR

        return Path(self._config.get(BARKS_READER_SECTION, READER_FILES_DIR))

    @property
    def prebuilt_comics_dir(self) -> Path:
        return self._get_prebuilt_comics_dir()

    def _get_prebuilt_comics_dir(self) -> Path:
        return Path(self._config.get(BARKS_READER_SECTION, PREBUILT_COMICS_DIR))

    @property
    def use_prebuilt_archives(self) -> bool:
        return self._get_use_prebuilt_archives()

    def _get_use_prebuilt_archives(self) -> bool:
        return self._config.getboolean(BARKS_READER_SECTION, USE_PREBUILT_COMICS)

    @property
    def goto_saved_node_on_start(self) -> bool:
        return self._get_goto_saved_node_on_start()

    def _get_goto_saved_node_on_start(self) -> bool:
        return self._config.getboolean(BARKS_READER_SECTION, GOTO_SAVED_NODE_ON_START)

    def _get_main_window_height(self) -> int:
        return self._config.get(BARKS_READER_SECTION, MAIN_WINDOW_HEIGHT)

    def _get_main_window_left(self) -> int:
        return self._config.get(BARKS_READER_SECTION, MAIN_WINDOW_LEFT)

    def _get_main_window_top(self) -> int:
        return self._config.get(BARKS_READER_SECTION, MAIN_WINDOW_TOP)

    def get_use_harpies_instead_of_larkies(self) -> bool:
        return self._config.getboolean(BARKS_READER_SECTION, USE_HARPIES_INSTEAD_OF_LARKIES)

    def get_use_dere_instead_of_theah(self) -> bool:
        return self._config.getboolean(BARKS_READER_SECTION, USE_DERE_INSTEAD_OF_THEAH)

    def get_use_blank_eyeballs_for_bombie(self) -> bool:
        return self._config.getboolean(BARKS_READER_SECTION, USE_BLANK_EYEBALLS_FOR_BOMBIE)

    def get_use_glk_firebug_ending(self) -> bool:
        return self._config.getboolean(BARKS_READER_SECTION, USE_GLK_FIREBUG_ENDING)

    @property
    def is_first_use_of_reader(self) -> bool:
        return self._get_is_first_use_of_reader()

    def _get_is_first_use_of_reader(self) -> bool:
        return self._config.getboolean(BARKS_READER_SECTION, IS_FIRST_USE_OF_READER)

    @is_first_use_of_reader.setter
    def is_first_use_of_reader(self, value: bool) -> None:
        logger.info(f"Setting is_first_use_of_reader = {value}.")
        self._config.set(BARKS_READER_SECTION, IS_FIRST_USE_OF_READER, 1 if value else 0)
        self._save_settings()

    def is_valid_fantagraphics_volumes_dir(self, dir_path: Path) -> bool:
        if self.use_prebuilt_archives:
            return True
        return self._is_valid_dir(dir_path)

    def get_fantagraphics_volumes_state(self) -> FantaVolumesState:
        if self.use_prebuilt_archives:
            return FantaVolumesState.VOLUMES_NOT_NEEDED
        if str(self.fantagraphics_volumes_dir) == UNSET_FANTA_DIR_MARKER:
            return FantaVolumesState.VOLUMES_NOT_SET
        if not self.fantagraphics_volumes_dir.is_dir():
            return FantaVolumesState.VOLUMES_MISSING
        return FantaVolumesState.VOLUMES_EXIST

    def _is_valid_reader_files_dir(self, dir_path: Path) -> bool:
        return self._is_valid_dir(dir_path)

    def _is_valid_prebuilt_comics_dir(self, dir_path: Path) -> bool:
        return (not self.use_prebuilt_archives) or self._is_valid_dir(dir_path)

    def _is_valid_use_prebuilt_archives(self, use_prebuilt_archives: bool) -> bool:
        if not use_prebuilt_archives:
            return True

        return self._is_valid_prebuilt_comics_dir(self.prebuilt_comics_dir)

    @staticmethod
    def _is_valid_goto_saved_node_on_start(_goto_saved_node_on_start: bool) -> bool:
        return True

    @staticmethod
    def _is_valid_use_harpies_instead_of_larkies(_use_harpies_instead_of_larkies: bool) -> bool:
        return True

    @staticmethod
    def _is_valid_use_dere_instead_of_theah(_use_dere_instead_of_theah: bool) -> bool:
        return True

    @staticmethod
    def _is_valid_use_blank_eyeballs_for_bombie(_use_blank_eyeballs_for_bombie: bool) -> bool:
        return True

    @staticmethod
    def _is_valid_use_glk_firebug_ending(_use_glk_firebug_ending: bool) -> bool:
        return True

    @staticmethod
    def _is_valid_is_first_use_of_reader(_is_first_use_of_reader: bool) -> bool:
        return True

    @staticmethod
    def _is_valid_main_window_height(_main_window_height: int) -> bool:
        return True

    @staticmethod
    def _is_valid_main_window_left(_main_window_left: int) -> bool:
        return True

    @staticmethod
    def _is_valid_main_window_top(_main_window_top: int) -> bool:
        return True

    def _is_valid_png_barks_panels_dir(self, dir_path: Path) -> bool:
        return self._is_valid_dir(dir_path)

    @staticmethod
    def _is_valid_jpg_barks_panels_source(source_path: Path) -> bool:
        return source_path.is_file()

    def _is_valid_use_png_images(self, use_png_images: bool) -> bool:
        if use_png_images:
            return self._is_valid_png_barks_panels_dir(self._get_png_barks_panels_dir())

        return self._is_valid_jpg_barks_panels_source(self._get_jpg_barks_panels_source())

    @staticmethod
    def _is_valid_dir(dir_path: str | Path) -> bool:
        if type(dir_path) is str:
            dir_path = Path(dir_path)

        if dir_path.is_dir():
            return True

        logger.error(f'Reader Settings: Required directory not found: "{dir_path}".')
        return False


class BuildableConfigParser(ConfigParser):
    def setdefaults(self, data: str, defaults: dict[str, Any]) -> None: ...


class Settings(Protocol):
    def add_json_panel(self, section: str, config: ConfigParser, data: str) -> None: ...

    interface: BoxLayout


class BuildableReaderSettings(ReaderSettings):
    def __init__(self) -> None:
        super().__init__()

        self._settings: Settings | None = None

        self._GETTER_METHODS = {
            FANTA_DIR: self._get_fantagraphics_volumes_dir,
            READER_FILES_DIR: self._get_reader_files_dir,
            PNG_BARKS_PANELS_DIR: self._get_png_barks_panels_dir,
            JPG_BARKS_PANELS_SOURCE: self._get_jpg_barks_panels_source,
            USE_PNG_IMAGES: self._get_use_png_images,
            PREBUILT_COMICS_DIR: self._get_prebuilt_comics_dir,
            USE_PREBUILT_COMICS: self._get_use_prebuilt_archives,
            IS_FIRST_USE_OF_READER: self._get_is_first_use_of_reader,
            MAIN_WINDOW_HEIGHT: self._get_main_window_height,
            MAIN_WINDOW_LEFT: self._get_main_window_left,
            MAIN_WINDOW_TOP: self._get_main_window_top,
            GOTO_SAVED_NODE_ON_START: self._get_goto_saved_node_on_start,
            USE_HARPIES_INSTEAD_OF_LARKIES: self.get_use_harpies_instead_of_larkies,
            USE_DERE_INSTEAD_OF_THEAH: self.get_use_dere_instead_of_theah,
            USE_BLANK_EYEBALLS_FOR_BOMBIE: self.get_use_blank_eyeballs_for_bombie,
            USE_GLK_FIREBUG_ENDING: self.get_use_glk_firebug_ending,
        }

        self._VALIDATION_METHODS: dict[str, Callable[[Path], bool]] = {
            FANTA_DIR: self.is_valid_fantagraphics_volumes_dir,
            READER_FILES_DIR: self._is_valid_reader_files_dir,
            PNG_BARKS_PANELS_DIR: self._is_valid_png_barks_panels_dir,
            JPG_BARKS_PANELS_SOURCE: self._is_valid_jpg_barks_panels_source,
            USE_PNG_IMAGES: self._is_valid_use_png_images,
            PREBUILT_COMICS_DIR: self._is_valid_prebuilt_comics_dir,
            USE_PREBUILT_COMICS: self._is_valid_use_prebuilt_archives,
            GOTO_SAVED_NODE_ON_START: self._is_valid_goto_saved_node_on_start,
            IS_FIRST_USE_OF_READER: self._is_valid_is_first_use_of_reader,
            MAIN_WINDOW_HEIGHT: self._is_valid_main_window_height,
            MAIN_WINDOW_LEFT: self._is_valid_main_window_left,
            MAIN_WINDOW_TOP: self._is_valid_main_window_top,
            USE_HARPIES_INSTEAD_OF_LARKIES: self._is_valid_use_harpies_instead_of_larkies,
            USE_DERE_INSTEAD_OF_THEAH: self._is_valid_use_dere_instead_of_theah,
            USE_BLANK_EYEBALLS_FOR_BOMBIE: self._is_valid_use_blank_eyeballs_for_bombie,
            USE_GLK_FIREBUG_ENDING: self._is_valid_use_glk_firebug_ending,
        }

    @staticmethod
    def build_config(config: BuildableConfigParser) -> None:
        # NOTE: For some reason we need to use 0/1 instead of False/True.
        #       Not sure why.
        config.setdefaults(
            BARKS_READER_SECTION,
            {
                FANTA_DIR: UNSET_FANTA_DIR_MARKER,
                READER_FILES_DIR: DEFAULT_BARKS_READER_FILES_DIR,
                PNG_BARKS_PANELS_DIR: ReaderFilePaths.get_default_png_barks_panels_source(),
                JPG_BARKS_PANELS_SOURCE: ReaderFilePaths.get_default_jpg_barks_panels_source(),
                USE_PNG_IMAGES: 1,
                PREBUILT_COMICS_DIR: ReaderFilePaths.get_default_prebuilt_comic_zips_dir(),
                USE_PREBUILT_COMICS: 0,
                GOTO_SAVED_NODE_ON_START: 1,
                USE_HARPIES_INSTEAD_OF_LARKIES: 1,
                USE_DERE_INSTEAD_OF_THEAH: 1,
                USE_BLANK_EYEBALLS_FOR_BOMBIE: 1,
                USE_GLK_FIREBUG_ENDING: 1,
                IS_FIRST_USE_OF_READER: 1,
                MAIN_WINDOW_HEIGHT: 0,
                MAIN_WINDOW_LEFT: -1,
                MAIN_WINDOW_TOP: -1,
            },
        )

    def build_settings(self, settings: Settings) -> None:
        settings.add_json_panel(BARKS_READER_SECTION, self._config, data=_READER_SETTINGS_JSON)
        self._settings = settings

    def validate_settings(self) -> None:
        for key in self._VALIDATION_METHODS:
            self._VALIDATION_METHODS[key](self._GETTER_METHODS[key]())

    def on_changed_setting(self, section: str, key: str, value: Any) -> bool:  # noqa: ANN401
        if section != BARKS_READER_SECTION:
            return True

        assert key in self._VALIDATION_METHODS
        if not self._VALIDATION_METHODS[key](value):
            return False

        if key in [PNG_BARKS_PANELS_DIR, JPG_BARKS_PANELS_SOURCE]:
            self._reader_file_paths.set_barks_panels_source(
                value, self._get_barks_panels_ext_type()
            )
        elif key == USE_PNG_IMAGES:
            if value:
                self._reader_file_paths.set_barks_panels_source(
                    self._get_png_barks_panels_dir(), BarksPanelsExtType.MOSTLY_PNG
                )
            else:
                self._reader_file_paths.set_barks_panels_source(
                    self._get_jpg_barks_panels_source(), BarksPanelsExtType.JPG
                )

        return True

    @override
    def _save_settings(self) -> None:
        self._config.write()
        self._update_settings_panel()

    def _update_settings_panel(self) -> None:
        if not self._settings:
            logger.debug("Panel settings not set. Skipping update.")
            return

        logger.info("Updating panel reader settings.")

        panels = self._settings.interface.content.panels

        # This module is used by non-GUI scripts but this import pops up a window.
        from kivy.uix.settings import SettingItem  # noqa: PLC0415

        for panel in panels.values():
            children = panel.children

            for child in children:
                if isinstance(child, SettingItem):
                    child.value = panel.get_value(child.section, child.key)
