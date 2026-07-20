from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from loguru import logger

from .reader_consts_and_types import ALT_ESCAPE_KEY_SETTING, LONG_PATH_SETTING
from .reader_file_paths import BarksPanelsExtType, ReaderFilePaths
from .reader_palette import DEFAULT_THEME_NAME, THEME_NAMES
from .system_file_paths import SystemFilePaths

if TYPE_CHECKING:
    from collections.abc import Callable

READER_FILES_DIR = "Reader Files"  # relative to app data directory
JPG_BARKS_PANELS_ZIP = "Barks Panels.zip"
WIKI_BUNDLE_SUBDIR = "Carl Barks Wiki"

BARKS_READER_SECTION = "Barks Reader"

FANTA_DIR = "fanta_dir"
UNSET_FANTA_DIR_MARKER = "<Fantagraphics Volumes Not Set>"
PREBUILT_COMICS_DIR = "prebuilt_dir"
WIKI_BUNDLE_DIR = "wiki_bundle_dir"
UNSET_WIKI_BUNDLE_DIR_MARKER = "<Carl Barks Wiki Not Set>"
USE_LIVE_WIKI_BUNDLE = "use_live_wiki_bundle"
PNG_BARKS_PANELS_DIR = "png_barks_panels_dir"
USE_PNG_IMAGES = "use_png_images"
USE_PREBUILT_COMICS = "use_prebuilt_comics"
GOTO_SAVED_NODE_ON_START = "goto_saved_node_on_start"
RECORD_READING_HISTORY = "record_reading_history"
CONFIRM_QUIT = "confirm_quit"
COLOR_THEME = "color_theme"
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
    schema entry, the ``ConfigParser`` default value, and (optionally) the
    unbound validator method on :class:`ReaderSettings`.
    """

    key: str
    title: str
    desc: str
    kind: FieldKind
    section_header: str | None = None
    options: tuple[str, ...] | None = None
    config_default: Any = None
    expand_vars: bool = False
    validator: Callable[..., bool] | None = None


def _resolve_default(spec: FieldSpec) -> Any:  # noqa: ANN401
    """Return ``spec.config_default``, calling it first if it is a zero-arg callable."""
    return spec.config_default() if callable(spec.config_default) else spec.config_default


class ConfigReader(Protocol):
    # `*args`/`**kwargs` so both Kivy's ConfigParser and stdlib's
    # ``configparser.ConfigParser`` (with extra optional ``raw``/``vars``/``fallback``
    # kwargs) satisfy the protocol structurally.
    def get(self, section: str, key: str, *args: Any, **kwargs: Any) -> str: ...  # noqa: ANN401
    def getboolean(self, section: str, key: str, *args: Any, **kwargs: Any) -> bool: ...  # noqa: ANN401
    def getint(self, section: str, key: str, *args: Any, **kwargs: Any) -> int: ...  # noqa: ANN401


class ConfigParser(ConfigReader, Protocol):
    def set(self, section: str, option: str, value: Any) -> None: ...  # noqa: ANN401
    def write(self) -> None: ...


def read_setting_from_config(config: ConfigReader, key: str) -> Any:  # noqa: ANN401
    """Return the typed value for setting ``key`` from a raw ``ConfigParser``.

    Used both by :meth:`ReaderSettings._read` and by pre-init callers
    (e.g. ``minimal_config_info``) that read settings before a full
    :class:`ReaderSettings` is constructed.
    """
    spec = _FIELDS_BY_KEY[key]
    match spec.kind:
        case FieldKind.BOOL:
            return config.getboolean(BARKS_READER_SECTION, key)
        case FieldKind.INT:
            return config.getint(BARKS_READER_SECTION, key)
        case FieldKind.ALT_ESCAPE:
            try:
                return config.getint(BARKS_READER_SECTION, key)
            except (ValueError, TypeError):
                return ALT_ESCAPE_KEY_UNSET
        case FieldKind.LONG_PATH:
            value = config.get(BARKS_READER_SECTION, key)
            return Path(os.path.expandvars(value)) if spec.expand_vars else Path(value)
        case _:
            return config.get(BARKS_READER_SECTION, key)


class ReaderSettings:
    def __init__(self) -> None:
        self._config: ConfigParser | None = None
        self._app_settings_path: Path | None = None
        self._app_data_dir: Path | None = None
        self._user_data_path: Path | None = None
        self._user_history_path: Path | None = None
        self._reader_file_paths: ReaderFilePaths = ReaderFilePaths()
        self._reader_sys_file_paths: SystemFilePaths = SystemFilePaths()

    def _save_settings(self) -> None:
        pass

    def set_config(self, config: ConfigParser, app_settings_path: Path, app_data_dir: Path) -> None:
        self._config = config
        self._app_settings_path = app_settings_path
        self._app_data_dir = app_data_dir
        self._user_data_path = app_settings_path.parent / "barks-reader.json"
        self._user_history_path = app_settings_path.parent / "barks-reader-history.json"

    def get_app_settings_path(self) -> Path:
        assert self._app_settings_path
        return self._app_settings_path

    def get_user_data_path(self) -> Path:
        assert self._user_data_path
        return self._user_data_path

    def get_user_history_path(self) -> Path:
        assert self._user_history_path
        return self._user_history_path

    @property
    def file_paths(self) -> ReaderFilePaths:
        return self._reader_file_paths

    @property
    def sys_file_paths(self) -> SystemFilePaths:
        return self._reader_sys_file_paths

    def _read(self, key: str) -> Any:  # noqa: ANN401
        """Return the typed value for setting ``key`` (dispatches via :class:`FieldSpec`)."""
        assert self._config
        return read_setting_from_config(self._config, key)

    # -- Panel image sources (derived; not direct config reads) --

    def set_barks_panels_dir(self) -> None:
        self.force_barks_panels_dir(self._read(USE_PNG_IMAGES))

    def force_barks_panels_dir(self, use_png_images: bool) -> None:
        if use_png_images:
            self._reader_file_paths.set_barks_panels_source(
                self._read(PNG_BARKS_PANELS_DIR), BarksPanelsExtType.MOSTLY_PNG
            )
        else:
            self._reader_file_paths.set_barks_panels_source(
                self._get_jpg_barks_panels_source(), BarksPanelsExtType.JPG
            )

    def _get_jpg_barks_panels_source(self) -> Path:
        return self.reader_files_dir / JPG_BARKS_PANELS_ZIP

    def _get_barks_panels_ext_type(self) -> BarksPanelsExtType:
        return self._get_barks_panels_ext_type_from_bool(self._read(USE_PNG_IMAGES))

    @staticmethod
    def _get_barks_panels_ext_type_from_bool(use_png_images: bool) -> BarksPanelsExtType:
        return BarksPanelsExtType.MOSTLY_PNG if use_png_images else BarksPanelsExtType.JPG

    # -- Typed config properties (all delegate to ``_read``) --

    @property
    def fantagraphics_volumes_dir(self) -> Path:
        return self._read(FANTA_DIR)

    @property
    def reader_files_dir(self) -> Path:
        assert self._app_data_dir
        return self.get_reader_files_dir(self._app_data_dir)

    @staticmethod
    def get_reader_files_dir(app_data_dir: Path) -> Path:
        return app_data_dir / READER_FILES_DIR

    @property
    def prebuilt_comics_dir(self) -> Path:
        return self._read(PREBUILT_COMICS_DIR)

    @property
    def use_prebuilt_archives(self) -> bool:
        return self._read(USE_PREBUILT_COMICS)

    @property
    def wiki_bundle_dir(self) -> Path | None:
        """The OKF wiki bundle root in use, or None when unset or not a bundle.

        When ``use_live_wiki_bundle`` is on, this is the ``wiki_bundle_dir``
        setting; otherwise it is the fixed ``reader_files_dir / "Carl Barks
        Wiki"`` copy. The wiki is an optional feature: consumers (the Indexes
        tree node, the wiki screen) simply hide it when this is None. A
        directory only counts as a bundle when its reserved root ``index.md``
        exists.
        """
        if self._read(USE_LIVE_WIKI_BUNDLE):
            value = self._read(WIKI_BUNDLE_DIR)
            if str(value) == UNSET_WIKI_BUNDLE_DIR_MARKER:
                return None
            candidate = Path(value)
        else:
            candidate = self._get_bundled_wiki_bundle_dir()
        if not (candidate / "index.md").is_file():
            return None
        return candidate

    def _get_bundled_wiki_bundle_dir(self) -> Path:
        return self.reader_files_dir / WIKI_BUNDLE_SUBDIR

    @property
    def goto_saved_node_on_start(self) -> bool:
        return self._read(GOTO_SAVED_NODE_ON_START)

    @property
    def record_reading_history(self) -> bool:
        return self._read(RECORD_READING_HISTORY)

    @property
    def confirm_quit(self) -> bool:
        return self._read(CONFIRM_QUIT)

    @property
    def color_theme(self) -> str:
        return self._read(COLOR_THEME)

    @property
    def goto_fullscreen_on_app_start(self) -> bool:
        return self._read(GOTO_FULLSCREEN_ON_APP_START)

    @property
    def goto_fullscreen_on_comic_read(self) -> bool:
        return self._read(GOTO_FULLSCREEN_ON_COMIC_READ)

    def get_use_harpies_instead_of_larkies(self) -> bool:
        return self._read(USE_HARPIES_INSTEAD_OF_LARKIES)

    def get_use_dere_instead_of_theah(self) -> bool:
        return self._read(USE_DERE_INSTEAD_OF_THEAH)

    def get_use_blank_eyeballs_for_bombie(self) -> bool:
        return self._read(USE_BLANK_EYEBALLS_FOR_BOMBIE)

    def get_use_glk_firebug_ending(self) -> bool:
        return self._read(USE_GLK_FIREBUG_ENDING)

    def get_alt_escape_key(self) -> int:
        return self._read(ALT_ESCAPE_KEY)

    def set_alt_escape_key(self, keycode: int) -> None:
        logger.info(f"Setting alt_escape_key = {keycode}.")
        assert self._config
        self._config.set(BARKS_READER_SECTION, ALT_ESCAPE_KEY, int(keycode))
        self._save_settings()

    @property
    def show_top_view_title_info(self) -> bool:
        return self._read(SHOW_TOP_VIEW_TITLE_INFO)

    @property
    def show_fun_view_title_info(self) -> bool:
        return self._read(SHOW_FUN_VIEW_TITLE_INFO)

    @property
    def is_first_use_of_reader(self) -> bool:
        return self._read(IS_FIRST_USE_OF_READER)

    @property
    def log_level(self) -> str:
        return self._read(LOG_LEVEL)

    @property
    def use_virtual_keyboard(self) -> bool:
        return self._read(USE_VIRTUAL_KEYBOARD)

    @property
    def double_page_mode(self) -> bool:
        return self._read(DOUBLE_PAGE_MODE)

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

    # -- Validators (only non-trivial ones; trivial ones are absent and treated as always-valid) --

    def is_valid_fantagraphics_volumes_dir(self, dir_path: Path) -> bool:
        if self.use_prebuilt_archives:
            return True
        return self._is_valid_dir(dir_path)

    def _is_valid_prebuilt_comics_dir(self, dir_path: Path) -> bool:
        return (not self.use_prebuilt_archives) or self._is_valid_dir(dir_path)

    def _is_valid_use_prebuilt_archives(self, use_prebuilt_archives: bool) -> bool:
        if not use_prebuilt_archives:
            return True
        return self._is_valid_prebuilt_comics_dir(self.prebuilt_comics_dir)

    def _is_valid_wiki_bundle_dir(self, dir_path: Path) -> bool:
        # The wiki is optional: unset is always valid; a set path must be an
        # actual bundle — the same root index.md gate as the wiki_bundle_dir
        # property — so a typo or a non-bundle directory gets flagged rather
        # than validating green while the wiki node silently never appears.
        if not self._read(USE_LIVE_WIKI_BUNDLE):
            return True
        if str(dir_path) == UNSET_WIKI_BUNDLE_DIR_MARKER:
            return True
        return self._is_valid_dir(dir_path) and (dir_path / "index.md").is_file()

    def _is_valid_use_live_wiki_bundle(self, use_live_wiki_bundle: bool) -> bool:
        # The bundled Reader Files copy is optional (the wiki just hides when
        # it is missing), so turning the live bundle off is always valid.
        if not use_live_wiki_bundle:
            return True
        return self._is_valid_wiki_bundle_dir(self._read(WIKI_BUNDLE_DIR))

    def _is_valid_png_barks_panels_dir(self, dir_path: Path) -> bool:
        return (not self._read(USE_PNG_IMAGES)) or self._is_valid_dir(dir_path)

    def _is_valid_jpg_barks_panels_source(self, source_path: Path) -> bool:
        return self._read(USE_PNG_IMAGES) or source_path.is_file()

    def _is_valid_use_png_images(self, use_png_images: bool) -> bool:
        if use_png_images:
            return self._is_valid_png_barks_panels_dir(self._read(PNG_BARKS_PANELS_DIR))
        return self._is_valid_jpg_barks_panels_source(self._get_jpg_barks_panels_source())

    @staticmethod
    def _is_valid_dir(dir_path: str | Path) -> bool:
        path = Path(dir_path)

        if path.is_dir():
            return True

        logger.error(f'Reader Settings: Required directory not found: "{path}".')
        return False


# ``_FIELDS`` lives below :class:`ReaderSettings` so each ``validator`` can be a real
# unbound-method reference (type-checked, rename-safe) rather than a string lookup.
_FIELDS: tuple[FieldSpec, ...] = (
    # -- Folders --
    FieldSpec(
        key=FANTA_DIR,
        title="Fantagraphics Directory",
        desc="Fantagraphics comic zips directory.",
        kind=FieldKind.LONG_PATH,
        section_header="Folders",
        config_default=UNSET_FANTA_DIR_MARKER,
        validator=ReaderSettings.is_valid_fantagraphics_volumes_dir,
    ),
    FieldSpec(
        key=PNG_BARKS_PANELS_DIR,
        title="PNG Barks Panels Directory",
        desc="Directory containing Barks panels PNG images.",
        kind=FieldKind.LONG_PATH,
        config_default=ReaderFilePaths.get_default_png_barks_panels_source,
        expand_vars=True,
        validator=ReaderSettings._is_valid_png_barks_panels_dir,  # noqa: SLF001
    ),
    FieldSpec(
        key=PREBUILT_COMICS_DIR,
        title="Prebuilt Comics Directory",
        desc="Directory containing specially prebuilt comics.",
        kind=FieldKind.LONG_PATH,
        config_default=ReaderFilePaths.get_default_prebuilt_comic_zips_dir,
        expand_vars=True,
        validator=ReaderSettings._is_valid_prebuilt_comics_dir,  # noqa: SLF001
    ),
    FieldSpec(
        key=WIKI_BUNDLE_DIR,
        title="Carl Barks Wiki Directory",
        desc="Directory of the Carl Barks Wiki knowledge bundle (its root holds"
        " an index.md). Only used when 'Use Live Wiki Bundle' is on; when not"
        " set, the wiki entry is hidden from the Indexes tree. (Restart required.)",
        kind=FieldKind.LONG_PATH,
        config_default=UNSET_WIKI_BUNDLE_DIR_MARKER,
        expand_vars=True,
        validator=ReaderSettings._is_valid_wiki_bundle_dir,  # noqa: SLF001
    ),
    # -- Reading --
    FieldSpec(
        key=DOUBLE_PAGE_MODE,
        title="Double Page Mode",
        desc="Show two pages side-by-side when reading comics.",
        kind=FieldKind.BOOL,
        section_header="Reading",
        config_default=0,
    ),
    FieldSpec(
        key=GOTO_FULLSCREEN_ON_COMIC_READ,
        title="Go Straight to Fullscreen for Comic Reading",
        desc="When you press the comic read button, go straight to fullscreen"
        " mode to read the comic.",
        kind=FieldKind.BOOL,
        config_default=0,
    ),
    FieldSpec(
        key=RECORD_READING_HISTORY,
        title="Record Reading History",
        desc="Record every comic you read in the Reading History view.",
        kind=FieldKind.BOOL,
        config_default=1,
    ),
    # -- Appearance --
    FieldSpec(
        key=COLOR_THEME,
        title="Color Theme",
        desc="Color theme for the app's accents, selection bar, and labels. (Restart required.)",
        kind=FieldKind.OPTIONS,
        options=THEME_NAMES,
        section_header="Appearance",
        config_default=DEFAULT_THEME_NAME,
    ),
    FieldSpec(
        key=SHOW_TOP_VIEW_TITLE_INFO,
        title="Show Title Info in Top View",
        desc="Show the title associated with the top image.",
        kind=FieldKind.BOOL,
        config_default=1,
    ),
    FieldSpec(
        key=SHOW_FUN_VIEW_TITLE_INFO,
        title="Show Title Info in Bottom View",
        desc="Show the title associated with the bottom image.",
        kind=FieldKind.BOOL,
        config_default=1,
    ),
    # -- Startup --
    FieldSpec(
        key=GOTO_SAVED_NODE_ON_START,
        title="Go to Last Selection on App Start",
        desc="When the app starts, go to the last selection in the tree view.",
        kind=FieldKind.BOOL,
        section_header="Startup",
        config_default=1,
    ),
    FieldSpec(
        key=GOTO_FULLSCREEN_ON_APP_START,
        title="Go Straight to Fullscreen on App Start",
        desc="When the app starts it will go straight to fullscreen mode.",
        kind=FieldKind.BOOL,
        config_default=0,
    ),
    # -- Window --
    FieldSpec(
        key=MAIN_WINDOW_HEIGHT,
        title="Main Window Height",
        desc="Height for the main window; the width is calculated automatically"
        " from this value. Set to 0 for the best fit. (Restart required.)",
        kind=FieldKind.INT,
        section_header="Window",
        config_default=0,
    ),
    FieldSpec(
        key=MAIN_WINDOW_LEFT,
        title="Main Window Left",
        desc="Left position of the main window. Set to -1 for a good default"
        " position. (Restart required.)",
        kind=FieldKind.INT,
        config_default=-1,
    ),
    FieldSpec(
        key=MAIN_WINDOW_TOP,
        title="Main Window Top",
        desc="Top position of the main window. Set to -1 for a good default"
        " position. (Restart required.)",
        kind=FieldKind.INT,
        config_default=-1,
    ),
    # -- Controls --
    FieldSpec(
        key=CONFIRM_QUIT,
        title="Confirm Before Quitting",
        desc="Ask for confirmation when the app close button is pressed.",
        kind=FieldKind.BOOL,
        section_header="Controls",
        config_default=1,
    ),
    FieldSpec(
        key=ALT_ESCAPE_KEY,
        title="Alternate Escape Key",
        desc="Optional extra key that behaves like Escape (for remote controls"
        " without an Escape key). Real Escape always still works.",
        kind=FieldKind.ALT_ESCAPE,
        config_default=ALT_ESCAPE_KEY_UNSET,
    ),
    FieldSpec(
        key=USE_VIRTUAL_KEYBOARD,
        title="Use Virtual Keyboard",
        desc="Always show an on-screen keyboard when tapping search fields, even"
        " if a physical keyboard is connected. (Restart required.)",
        kind=FieldKind.BOOL,
        config_default=0,
    ),
    # -- Advanced --
    FieldSpec(
        key=USE_PNG_IMAGES,
        title="Use PNG Images",
        desc="Use PNG images where possible. (Restart required.)",
        kind=FieldKind.BOOL,
        section_header="Advanced",
        config_default=1,
        validator=ReaderSettings._is_valid_use_png_images,  # noqa: SLF001
    ),
    FieldSpec(
        key=USE_PREBUILT_COMICS,
        title="Use Prebuilt Comics",
        desc="Read comics from the prebuilt comics folder.",
        kind=FieldKind.BOOL,
        config_default=0,
        validator=ReaderSettings._is_valid_use_prebuilt_archives,  # noqa: SLF001
    ),
    FieldSpec(
        key=USE_LIVE_WIKI_BUNDLE,
        title="Use Live Wiki Bundle",
        desc="Use the 'Carl Barks Wiki Directory' setting instead of the copy in"
        " the Reader Files folder. (Restart required.)",
        kind=FieldKind.BOOL,
        config_default=0,
        validator=ReaderSettings._is_valid_use_live_wiki_bundle,  # noqa: SLF001
    ),
    FieldSpec(
        key=LOG_LEVEL,
        title="Log Level",
        desc="Level of logging information. (Restart required.)",
        kind=FieldKind.OPTIONS,
        options=tuple(LOG_LEVEL_OPTIONS),
        config_default="INFO",
    ),
    FieldSpec(
        key=IS_FIRST_USE_OF_READER,
        title="First Use of Reader",
        desc="Treat the next launch as a first run, re-running first-use setup."
        " (Restart required.)",
        kind=FieldKind.BOOL,
        config_default=1,
    ),
    # -- Controversial Censorship Fixes --
    FieldSpec(
        key=USE_HARPIES_INSTEAD_OF_LARKIES,
        title="Use 'Harpies' Instead of 'Larkies'",
        desc="When reading 'The Golden Fleecing', use 'Harpies' instead of 'Larkies'.",
        kind=FieldKind.BOOL,
        section_header="Controversial Censorship Fixes",
        config_default=1,
    ),
    FieldSpec(
        key=USE_DERE_INSTEAD_OF_THEAH,
        title="Use 'Dere' Instead of 'Theah'",
        desc="When reading 'Lost in the Andes!', use 'Dere' instead of 'Theah'.",
        kind=FieldKind.BOOL,
        config_default=1,
    ),
    FieldSpec(
        key=USE_BLANK_EYEBALLS_FOR_BOMBIE,
        title="Use Blank Eyeballs for Bombie",
        desc="When reading 'Voodoo Hoodoo', use blank eyeballs for Bombie the Zombie.",
        kind=FieldKind.BOOL,
        config_default=1,
    ),
    FieldSpec(
        key=USE_GLK_FIREBUG_ENDING,
        title="Don't Use Fantagraphics Ending for 'The Firebug'",
        desc="When reading 'The Firebug', don't use the Fantagraphics ending.",
        kind=FieldKind.BOOL,
        config_default=1,
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


class BuildableConfigParser(ConfigParser):
    def setdefaults(self, section: str, defaults: dict[str, Any]) -> None: ...


class Settings(Protocol):
    def add_json_panel(self, section: str, config: ConfigParser, data: str) -> None: ...

    interface: Any
