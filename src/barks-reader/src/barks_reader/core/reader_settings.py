from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from loguru import logger

from .reader_consts_and_types import ALT_ESCAPE_KEY_SETTING, LONG_PATH_SETTING
from .reader_file_paths import BarksPanelsExtType, ReaderFilePaths
from .system_file_paths import SystemFilePaths

READER_FILES_DIR = "Reader Files"  # relative to app data directory
JPG_BARKS_PANELS_ZIP = "Barks Panels.zip"

BARKS_READER_SECTION = "Barks Reader"

FANTA_DIR = "fanta_dir"
UNSET_FANTA_DIR_MARKER = "<Fantagraphics Volumes Not Set>"
PREBUILT_COMICS_DIR = "prebuilt_dir"
PNG_BARKS_PANELS_DIR = "png_barks_panels_dir"
USE_PNG_IMAGES = "use_png_images"
USE_PREBUILT_COMICS = "use_prebuilt_comics"
GOTO_SAVED_NODE_ON_START = "goto_saved_node_on_start"
GOTO_FULLSCREEN_ON_APP_START = "goto_fullscreen_on_app_start"
GOTO_FULLSCREEN_ON_COMIC_READ = "goto_fullscreen_on_comic_read"
USE_HARPIES_INSTEAD_OF_LARKIES = "use_harpies"
USE_DERE_INSTEAD_OF_THEAH = "use_dere"
USE_BLANK_EYEBALLS_FOR_BOMBIE = "use_blank_eyeballs"
USE_GLK_FIREBUG_ENDING = "use_glk_firebug_ending"
IS_FIRST_USE_OF_READER = "is_first_use_of_reader"
LOG_LEVEL = "log_level"
USE_VIRTUAL_KEYBOARD = "use_virtual_keyboard"
DOUBLE_PAGE_MODE = "double_page_mode"
SHOW_TOP_VIEW_TITLE_INFO = "show_tree_view_title_info"
SHOW_FUN_VIEW_TITLE_INFO = "show_fun_view_title_info"
MAIN_WINDOW_HEIGHT = "main_window_height"
MAIN_WINDOW_LEFT = "main_window_left"
MAIN_WINDOW_TOP = "main_window_top"
ALT_ESCAPE_KEY = "alt_escape_key"
ALT_ESCAPE_KEY_UNSET = 0

LOG_LEVEL_OPTIONS = ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class FieldKind(Enum):
    """Setting types accepted by Kivy's settings panel."""

    BOOL = "bool"
    INT = "numeric"
    OPTIONS = "options"
    LONG_PATH = LONG_PATH_SETTING
    ALT_ESCAPE = ALT_ESCAPE_KEY_SETTING


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """Declarative description of a single configurable setting.

    A single :class:`FieldSpec` is the source of truth for the Kivy settings
    schema entry, the ``ConfigParser`` default value, and the names of the
    bound :class:`ReaderSettings` methods used to read and validate the value.
    """

    key: str
    title: str
    desc: str
    kind: FieldKind
    section_header: str | None = None
    options: tuple[str, ...] | None = None
    config_default: Any = None
    getter_method_name: str = ""
    validator_method_name: str = ""


def _resolve_default(spec: FieldSpec) -> Any:  # noqa: ANN401
    """Return ``spec.config_default``, calling it first if it is a zero-arg callable."""
    return spec.config_default() if callable(spec.config_default) else spec.config_default


_FIELDS: tuple[FieldSpec, ...] = (
    # -- Folders --
    FieldSpec(
        key=FANTA_DIR,
        title="Fantagraphics Directory",
        desc="Fantagraphics comic zips directory.",
        kind=FieldKind.LONG_PATH,
        section_header="Folders",
        config_default=UNSET_FANTA_DIR_MARKER,
        getter_method_name="_get_fantagraphics_volumes_dir",
        validator_method_name="is_valid_fantagraphics_volumes_dir",
    ),
    FieldSpec(
        key=PNG_BARKS_PANELS_DIR,
        title="Png Barks Panels Directory",
        desc="Directory containing Barks panels png images.",
        kind=FieldKind.LONG_PATH,
        config_default=ReaderFilePaths.get_default_png_barks_panels_source,
        getter_method_name="_get_png_barks_panels_dir",
        validator_method_name="_is_valid_png_barks_panels_dir",
    ),
    FieldSpec(
        key=PREBUILT_COMICS_DIR,
        title="Prebuilt Comics Directory",
        desc="Directory containing specially prebuilt comics.",
        kind=FieldKind.LONG_PATH,
        config_default=ReaderFilePaths.get_default_prebuilt_comic_zips_dir,
        getter_method_name="_get_prebuilt_comics_dir",
        validator_method_name="_is_valid_prebuilt_comics_dir",
    ),
    # -- Options --
    FieldSpec(
        key=DOUBLE_PAGE_MODE,
        title="Double Page Mode",
        desc="Show two pages side-by-side when reading comics.",
        kind=FieldKind.BOOL,
        section_header="Options",
        config_default=0,
        getter_method_name="_get_double_page_mode",
        validator_method_name="_is_valid_double_page_mode",
    ),
    FieldSpec(
        key=GOTO_SAVED_NODE_ON_START,
        title="Goto Last Selection on App Start",
        desc="When the app starts, goto the last selection in the tree view.",
        kind=FieldKind.BOOL,
        config_default=1,
        getter_method_name="_get_goto_saved_node_on_start",
        validator_method_name="_is_valid_goto_saved_node_on_start",
    ),
    FieldSpec(
        key=GOTO_FULLSCREEN_ON_APP_START,
        title="Go Straight to Fullscreen on App Start",
        desc="When the app starts it will go straight to fullscreen mode.",
        kind=FieldKind.BOOL,
        config_default=0,
        getter_method_name="_get_goto_fullscreen_on_app_start",
        validator_method_name="_is_valid_goto_fullscreen_on_app_start",
    ),
    FieldSpec(
        key=GOTO_FULLSCREEN_ON_COMIC_READ,
        title="Go Straight to Fullscreen for Comic Reading",
        desc="When you press the comic read button, the app will go straight to"
        " fullscreen mode to read the comic.",
        kind=FieldKind.BOOL,
        config_default=0,
        getter_method_name="_get_goto_fullscreen_on_comic_read",
        validator_method_name="_is_valid_goto_fullscreen_on_comic_read",
    ),
    FieldSpec(
        key=SHOW_TOP_VIEW_TITLE_INFO,
        title="Show Title Info in Top View",
        desc="Set this to true if you want to see the title associated with the top image.",
        kind=FieldKind.BOOL,
        config_default=1,
        getter_method_name="_get_show_top_view_title_info",
        validator_method_name="_is_valid_show_top_view_title_info",
    ),
    FieldSpec(
        key=SHOW_FUN_VIEW_TITLE_INFO,
        title="Show Title Info in Bottom View",
        desc="Set this to true if you want to see the title associated with the bottom image.",
        kind=FieldKind.BOOL,
        config_default=1,
        getter_method_name="_get_show_fun_view_title_info",
        validator_method_name="_is_valid_show_fun_view_title_info",
    ),
    FieldSpec(
        key=IS_FIRST_USE_OF_READER,
        title="First Use of Reader",
        desc="Set this to true if this is the first use of the Barks reader. You need"
        " to restart the app after changing this.",
        kind=FieldKind.BOOL,
        config_default=1,
        getter_method_name="_get_is_first_use_of_reader",
        validator_method_name="_is_valid_is_first_use_of_reader",
    ),
    FieldSpec(
        key=LOG_LEVEL,
        title="Log Level",
        desc="Level of logging information. You need to restart the app before this takes effect.",
        kind=FieldKind.OPTIONS,
        options=tuple(LOG_LEVEL_OPTIONS),
        config_default="INFO",
        getter_method_name="_get_log_level",
        validator_method_name="_is_valid_log_level",
    ),
    FieldSpec(
        key=MAIN_WINDOW_HEIGHT,
        title="Main Window Height",
        desc="Set this to height you want for the main window. The width will be"
        " automatically calculated from this value. Set to 0 to give the best fit."
        " You need to restart the app after changing this.",
        kind=FieldKind.INT,
        config_default=0,
        getter_method_name="_get_main_window_height",
        validator_method_name="_is_valid_main_window_height",
    ),
    FieldSpec(
        key=MAIN_WINDOW_LEFT,
        title="Main Window Left",
        desc="Set this to the left position of the main window. Set to -1 to give"
        " a good default position. You need to restart the app after changing this.",
        kind=FieldKind.INT,
        config_default=-1,
        getter_method_name="_get_main_window_left",
        validator_method_name="_is_valid_main_window_left",
    ),
    FieldSpec(
        key=MAIN_WINDOW_TOP,
        title="Main Window Top",
        desc="Set this to the top position of the main window. Set to -1 to give"
        " a good default position. You need to restart the app after changing this.",
        kind=FieldKind.INT,
        config_default=-1,
        getter_method_name="_get_main_window_top",
        validator_method_name="_is_valid_main_window_top",
    ),
    FieldSpec(
        key=ALT_ESCAPE_KEY,
        title="Alternate Escape Key",
        desc="Optional extra key that behaves like Escape (for remote controls"
        " without an Escape key). Real Escape always still works.",
        kind=FieldKind.ALT_ESCAPE,
        config_default=ALT_ESCAPE_KEY_UNSET,
        getter_method_name="get_alt_escape_key",
        validator_method_name="_is_valid_alt_escape_key",
    ),
    FieldSpec(
        key=USE_VIRTUAL_KEYBOARD,
        title="Use Virtual Keyboard",
        desc="Always show an on-screen keyboard when tapping search fields, "
        "even if a physical keyboard is connected. Requires app restart.",
        kind=FieldKind.BOOL,
        config_default=0,
        getter_method_name="_get_use_virtual_keyboard",
        validator_method_name="_is_valid_use_virtual_keyboard",
    ),
    FieldSpec(
        key=USE_PNG_IMAGES,
        title="Use Png Images",
        desc="Use png images where possible (needs app RESTART if changed).",
        kind=FieldKind.BOOL,
        config_default=1,
        getter_method_name="_get_use_png_images",
        validator_method_name="_is_valid_use_png_images",
    ),
    FieldSpec(
        key=USE_PREBUILT_COMICS,
        title="Use Prebuilt Comics",
        desc="Read comics from the prebuilt comics folder.",
        kind=FieldKind.BOOL,
        config_default=0,
        getter_method_name="_get_use_prebuilt_archives",
        validator_method_name="_is_valid_use_prebuilt_archives",
    ),
    # -- Controversial Censorship Fixes --
    FieldSpec(
        key=USE_HARPIES_INSTEAD_OF_LARKIES,
        title="Use 'Harpies' Instead of 'Larkies'",
        desc="When reading 'The Golden Fleecing', use 'Harpies' instead of 'Larkies'.",
        kind=FieldKind.BOOL,
        section_header="Controversial Censorship Fixes",
        config_default=1,
        getter_method_name="get_use_harpies_instead_of_larkies",
        validator_method_name="_is_valid_use_harpies_instead_of_larkies",
    ),
    FieldSpec(
        key=USE_DERE_INSTEAD_OF_THEAH,
        title="Use 'Dere' Instead of 'Theah'",
        desc="When reading 'Lost in the Andes!', use 'Dere' instead of 'Theah'.",
        kind=FieldKind.BOOL,
        config_default=1,
        getter_method_name="get_use_dere_instead_of_theah",
        validator_method_name="_is_valid_use_dere_instead_of_theah",
    ),
    FieldSpec(
        key=USE_BLANK_EYEBALLS_FOR_BOMBIE,
        title="Use Blank Eyeballs for Bombie",
        desc="When reading 'Voodoo Hoodoo', use blank eyeballs for Bombie the Zombie.",
        kind=FieldKind.BOOL,
        config_default=1,
        getter_method_name="get_use_blank_eyeballs_for_bombie",
        validator_method_name="_is_valid_use_blank_eyeballs_for_bombie",
    ),
    FieldSpec(
        key=USE_GLK_FIREBUG_ENDING,
        title="Don't Use Fantagraphics Ending for 'The Firebug'",
        desc="When reading 'The Firebug', don't use the Fantagraphics ending.",
        kind=FieldKind.BOOL,
        config_default=1,
        getter_method_name="get_use_glk_firebug_ending",
        validator_method_name="_is_valid_use_glk_firebug_ending",
    ),
)

_FIELDS_BY_KEY: dict[str, FieldSpec] = {f.key: f for f in _FIELDS}


def _get_reader_settings_json() -> str:
    items: list[dict[str, Any]] = []
    for spec in _FIELDS:
        if spec.section_header:
            items.append({"type": "title", "title": spec.section_header})
        entry: dict[str, Any] = {
            "title": spec.title,
            "desc": spec.desc,
            "type": spec.kind.value,
            "section": BARKS_READER_SECTION,
            "key": spec.key,
        }
        if spec.options is not None:
            entry["options"] = list(spec.options)
        if spec.kind is FieldKind.OPTIONS:
            entry["value"] = spec.config_default
        items.append(entry)
    return json.dumps(items)


class ConfigParser(Protocol):
    def get(self, section: str, key: str) -> str: ...
    def getboolean(self, section: str, key: str) -> bool: ...
    def getint(self, section: str, key: str) -> int: ...
    def set(self, section: str, key: str, value: Any) -> None: ...  # noqa: ANN401
    def write(self) -> None: ...


class ReaderSettings:
    def __init__(self) -> None:
        self._config: ConfigParser | None = None
        self._app_settings_path: Path | None = None
        self._app_data_dir: Path | None = None
        self._user_data_path: Path | None = None
        self._reader_file_paths: ReaderFilePaths = ReaderFilePaths()
        self._reader_sys_file_paths: SystemFilePaths = SystemFilePaths()

    def _save_settings(self) -> None:
        pass

    def set_config(self, config: ConfigParser, app_settings_path: Path, app_data_dir: Path) -> None:
        self._config: ConfigParser = config
        self._app_settings_path = app_settings_path
        self._app_data_dir = app_data_dir
        self._user_data_path = app_settings_path.parent / "barks-reader.json"

    def get_app_settings_path(self) -> Path:
        assert self._app_settings_path
        return self._app_settings_path

    def get_user_data_path(self) -> Path:
        assert self._user_data_path
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
        assert self._config
        return Path(
            os.path.expandvars(self._config.get(BARKS_READER_SECTION, PNG_BARKS_PANELS_DIR))
        )

    def _get_jpg_barks_panels_source(self) -> Path:
        return self.reader_files_dir / JPG_BARKS_PANELS_ZIP

    def _get_barks_panels_ext_type(self) -> BarksPanelsExtType:
        return self._get_barks_panels_ext_type_from_bool(self._get_use_png_images())

    @staticmethod
    def _get_barks_panels_ext_type_from_bool(use_png_images: bool) -> BarksPanelsExtType:
        return BarksPanelsExtType.MOSTLY_PNG if use_png_images else BarksPanelsExtType.JPG

    def _get_use_png_images(self) -> bool:
        assert self._config
        return self._config.getboolean(BARKS_READER_SECTION, USE_PNG_IMAGES)

    @property
    def fantagraphics_volumes_dir(self) -> Path:
        return self._get_fantagraphics_volumes_dir()

    def _get_fantagraphics_volumes_dir(self) -> Path:
        assert self._config
        return Path(self._config.get(BARKS_READER_SECTION, FANTA_DIR))

    @property
    def reader_files_dir(self) -> Path:
        return self._get_reader_files_dir()

    def _get_reader_files_dir(self) -> Path:
        assert self._app_data_dir
        return self.get_reader_files_dir(self._app_data_dir)

    @staticmethod
    def get_reader_files_dir(app_data_dir: Path) -> Path:
        return app_data_dir / READER_FILES_DIR

    @property
    def prebuilt_comics_dir(self) -> Path:
        return self._get_prebuilt_comics_dir()

    def _get_prebuilt_comics_dir(self) -> Path:
        assert self._config
        return Path(os.path.expandvars(self._config.get(BARKS_READER_SECTION, PREBUILT_COMICS_DIR)))

    @property
    def use_prebuilt_archives(self) -> bool:
        return self._get_use_prebuilt_archives()

    def _get_use_prebuilt_archives(self) -> bool:
        assert self._config
        return self._config.getboolean(BARKS_READER_SECTION, USE_PREBUILT_COMICS)

    @property
    def goto_saved_node_on_start(self) -> bool:
        return self._get_goto_saved_node_on_start()

    def _get_goto_saved_node_on_start(self) -> bool:
        assert self._config
        return self._config.getboolean(BARKS_READER_SECTION, GOTO_SAVED_NODE_ON_START)

    @property
    def goto_fullscreen_on_app_start(self) -> bool:
        return self._get_goto_fullscreen_on_app_start()

    def _get_goto_fullscreen_on_app_start(self) -> bool:
        assert self._config
        return self._config.getboolean(BARKS_READER_SECTION, GOTO_FULLSCREEN_ON_APP_START)

    @property
    def goto_fullscreen_on_comic_read(self) -> bool:
        return self._get_goto_fullscreen_on_comic_read()

    def _get_goto_fullscreen_on_comic_read(self) -> bool:
        assert self._config
        return self._config.getboolean(BARKS_READER_SECTION, GOTO_FULLSCREEN_ON_COMIC_READ)

    def _get_main_window_height(self) -> int:
        assert self._config
        return self._config.getint(BARKS_READER_SECTION, MAIN_WINDOW_HEIGHT)

    def _get_main_window_left(self) -> int:
        assert self._config
        return self._config.getint(BARKS_READER_SECTION, MAIN_WINDOW_LEFT)

    def _get_main_window_top(self) -> int:
        assert self._config
        return self._config.getint(BARKS_READER_SECTION, MAIN_WINDOW_TOP)

    def get_use_harpies_instead_of_larkies(self) -> bool:
        assert self._config
        return self._config.getboolean(BARKS_READER_SECTION, USE_HARPIES_INSTEAD_OF_LARKIES)

    def get_use_dere_instead_of_theah(self) -> bool:
        assert self._config
        return self._config.getboolean(BARKS_READER_SECTION, USE_DERE_INSTEAD_OF_THEAH)

    def get_use_blank_eyeballs_for_bombie(self) -> bool:
        assert self._config
        return self._config.getboolean(BARKS_READER_SECTION, USE_BLANK_EYEBALLS_FOR_BOMBIE)

    def get_use_glk_firebug_ending(self) -> bool:
        assert self._config
        return self._config.getboolean(BARKS_READER_SECTION, USE_GLK_FIREBUG_ENDING)

    def get_alt_escape_key(self) -> int:
        assert self._config
        try:
            return self._config.getint(BARKS_READER_SECTION, ALT_ESCAPE_KEY)
        except (ValueError, TypeError):
            return ALT_ESCAPE_KEY_UNSET

    def set_alt_escape_key(self, keycode: int) -> None:
        logger.info(f"Setting alt_escape_key = {keycode}.")
        assert self._config
        self._config.set(BARKS_READER_SECTION, ALT_ESCAPE_KEY, int(keycode))
        self._save_settings()

    @property
    def show_top_view_title_info(self) -> bool:
        return self._get_show_top_view_title_info()

    def _get_show_top_view_title_info(self) -> bool:
        assert self._config
        return self._config.getboolean(BARKS_READER_SECTION, SHOW_TOP_VIEW_TITLE_INFO)

    @property
    def show_fun_view_title_info(self) -> bool:
        return self._get_show_fun_view_title_info()

    def _get_show_fun_view_title_info(self) -> bool:
        assert self._config
        return self._config.getboolean(BARKS_READER_SECTION, SHOW_FUN_VIEW_TITLE_INFO)

    @property
    def is_first_use_of_reader(self) -> bool:
        return self._get_is_first_use_of_reader()

    def _get_is_first_use_of_reader(self) -> bool:
        assert self._config
        return self._config.getboolean(BARKS_READER_SECTION, IS_FIRST_USE_OF_READER)

    @property
    def log_level(self) -> str:
        return self._get_log_level()

    def _get_log_level(self) -> str:
        assert self._config
        return self._config.get(BARKS_READER_SECTION, LOG_LEVEL)

    @property
    def use_virtual_keyboard(self) -> bool:
        return self._get_use_virtual_keyboard()

    def _get_use_virtual_keyboard(self) -> bool:
        assert self._config
        return self._config.getboolean(BARKS_READER_SECTION, USE_VIRTUAL_KEYBOARD)

    @property
    def double_page_mode(self) -> bool:
        return self._get_double_page_mode()

    def _get_double_page_mode(self) -> bool:
        assert self._config
        return self._config.getboolean(BARKS_READER_SECTION, DOUBLE_PAGE_MODE)

    @double_page_mode.setter
    def double_page_mode(self, value: bool) -> None:
        logger.info(f"Setting double_page_mode = {value}.")
        assert self._config
        self._config.set(BARKS_READER_SECTION, DOUBLE_PAGE_MODE, 1 if value else 0)
        self._save_settings()

    @is_first_use_of_reader.setter
    def is_first_use_of_reader(self, value: bool) -> None:
        logger.info(f"Setting is_first_use_of_reader = {value}.")
        assert self._config
        self._config.set(BARKS_READER_SECTION, IS_FIRST_USE_OF_READER, 1 if value else 0)
        self._save_settings()

    def is_valid_fantagraphics_volumes_dir(self, dir_path: Path) -> bool:
        if self.use_prebuilt_archives:
            return True
        return self._is_valid_dir(dir_path)

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
    def _is_valid_goto_fullscreen_on_app_start(_goto_fullscreen_on_app_start: bool) -> bool:
        return True

    @staticmethod
    def _is_valid_goto_fullscreen_on_comic_read(_goto_fullscreen_on_comic_read: bool) -> bool:
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
    def _is_valid_show_top_view_title_info(_show_top_view_title_info: bool) -> bool:
        return True

    @staticmethod
    def _is_valid_show_fun_view_title_info(_show_fun_view_title_info: bool) -> bool:
        return True

    @staticmethod
    def _is_valid_is_first_use_of_reader(_is_first_use_of_reader: bool) -> bool:
        return True

    @staticmethod
    def _is_valid_use_virtual_keyboard(_use_virtual_keyboard: bool) -> bool:
        return True

    @staticmethod
    def _is_valid_double_page_mode(_double_page_mode: bool) -> bool:
        return True

    @staticmethod
    def _is_valid_log_level(_log_level: str) -> bool:
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

    @staticmethod
    def _is_valid_alt_escape_key(_alt_escape_key: int) -> bool:
        return True

    def _is_valid_png_barks_panels_dir(self, dir_path: Path) -> bool:
        return (not self._get_use_png_images()) or self._is_valid_dir(dir_path)

    def _is_valid_jpg_barks_panels_source(self, source_path: Path) -> bool:
        return self._get_use_png_images() or source_path.is_file()

    def _is_valid_use_png_images(self, use_png_images: bool) -> bool:
        if use_png_images:
            return self._is_valid_png_barks_panels_dir(self._get_png_barks_panels_dir())

        return self._is_valid_jpg_barks_panels_source(self._get_jpg_barks_panels_source())

    @staticmethod
    def _is_valid_dir(dir_path: str | Path) -> bool:
        path = Path(dir_path)

        if path.is_dir():
            return True

        logger.error(f'Reader Settings: Required directory not found: "{path}".')
        return False


class BuildableConfigParser(ConfigParser):
    def setdefaults(self, section: str, defaults: dict[str, Any]) -> None: ...


class Settings(Protocol):
    def add_json_panel(self, section: str, config: ConfigParser, data: str) -> None: ...

    interface: Any
