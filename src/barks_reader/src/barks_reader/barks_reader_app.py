# ruff: noqa: E402, ERA001

from __future__ import annotations

# ------------------------------------------------------------------ #
# --- We need to change the KIVY_HOME directory to be under this --- #
# --- app's settings directory. The 'config_info' module handles --- #
# --- this, and for this to work, we need to import it before    --- #
# --- any kivy imports.                                          --- #
from barks_reader.config_info import ConfigInfo

config_info = ConfigInfo()
# ------------------------------------------------------------------ #

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import kivy
import loguru
from barks_fantagraphics.comics_cmd_args import CmdArgs, ExtraArg
from kivy import Config
from kivy.app import App
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.settings import Settings, SettingsWithSpinner
from loguru import logger
from screeninfo import get_monitors

from barks_reader.comic_book_reader import get_barks_comic_reader_screen
from barks_reader.filtered_title_lists import FilteredTitleLists
from barks_reader.font_manager import FontManager
from barks_reader.intro_compleat_barks_reader import get_intro_compleat_barks_reader_screen
from barks_reader.main_screen import MainScreen
from barks_reader.reader_consts_and_types import APP_TITLE, LONG_PATH_SETTING
from barks_reader.reader_screens import (
    COMIC_BOOK_READER_SCREEN,
    INTRO_COMPLEAT_BARKS_READER_SCREEN,
    MAIN_READER_SCREEN,
    ReaderScreenManager,
    ReaderScreens,
)
from barks_reader.reader_settings import BuildableReaderSettings
from barks_reader.reader_ui_classes import ACTION_BAR_SIZE_Y, ReaderTreeBuilderEventDispatcher
from barks_reader.screen_metrics import get_screen_info, log_screen_metrics
from barks_reader.settings_fix import SettingLongPath

if TYPE_CHECKING:
    from barks_fantagraphics.comics_database import ComicsDatabase
    from kivy.config import ConfigParser
    from kivy.uix.screenmanager import ScreenManager
    from kivy.uix.widget import Widget

READER_TREE_VIEW_KV_FILE = str(Path(__file__).parent / "reader-tree-view.kv")
BARKS_READER_APP_KV_FILE = str(Path(__file__).with_suffix(".kv"))


LOGGER_SYS_NAME_KEY = "sys_name"
APP_LOGGING_NAME = "app"
KIVY_LOGGING_NAME = "kivy"


class BarksReaderApp(App):
    """The main Kivy application class for the Barks Reader."""

    def __init__(
        self, comics_db: ComicsDatabase, window_left: int, window_height: int, **kwargs: str
    ) -> None:
        super().__init__(**kwargs)

        self.title = APP_TITLE
        self.settings_cls = SettingsWithSpinner

        self._comics_database = comics_db
        self.window_left = window_left
        self.window_height = window_height
        self._reader_settings = BuildableReaderSettings()
        self.font_manager = FontManager()

        self._reader_screen_manager = ReaderScreenManager(self.open_settings)
        self._screen_switchers = self._reader_screen_manager.screen_switchers

        self._main_screen: MainScreen | None = None

    # noinspection PyTypeHints
    def _on_window_resize(self, _window: Window, width: int, height: int) -> None:
        logger.debug(f"App window resize event: width = {width}, height = {height}.")
        self.update_fonts(height)

    def update_fonts(self, height: int) -> None:
        self.font_manager.update_font_sizes(height)
        self._main_screen.fonts_updated(self.font_manager)

    def close_app(self) -> None:
        self._main_screen.app_closing()
        App.get_running_app().stop()
        Window.close()

    def get_application_config(self, _default_path: str = "") -> str:
        return str(config_info.app_config_path)

    def build_config(self, config: ConfigParser) -> None:
        """Set default values for the application configuration."""
        # Set default window geometry if not already present in the config file
        comic_page_aspect_ratio = 3200.0 / 2120.0
        primary_monitor = get_monitors()[0]
        default_height = round(0.96 * primary_monitor.height)
        default_width = round(default_height / comic_page_aspect_ratio)
        default_height_incl_action_bar = default_height + ACTION_BAR_SIZE_Y

        config.setdefaults(
            "graphics",
            {
                "width": default_width,
                "height": default_height_incl_action_bar,
                "left": 2400,
                "top": 50,
            },
        )

        # Delegate to the settings class to set its own defaults
        self._reader_settings.build_config(config)

    def build_settings(self, settings: Settings) -> None:
        # Register our custom widget type with the name 'longpath'
        settings.register_type(LONG_PATH_SETTING, SettingLongPath)

        self._reader_settings.build_settings(settings)
        self.config.write()
        settings.interface.menu.height = ACTION_BAR_SIZE_Y

    def on_config_change(
        self,
        _config: ConfigParser,
        section: str,
        key: str,
        value: Any,  # noqa: ANN401
    ) -> None:
        logger.info(f"Config change: section = '{section}', key = '{key}', value = '{value}'.")
        self._reader_settings.on_changed_setting(section, key, value)

    def build(self) -> Widget:
        logger.debug("Building app...")
        Window.bind(on_resize=self._on_window_resize)

        self._initialize_settings_and_db()

        logger.debug("Loading kv files...")
        # Pass the font manager to kv lang so it can be accessed
        Builder.load_string("#:set fm app.font_manager")
        Builder.load_file(READER_TREE_VIEW_KV_FILE)
        Builder.load_file(BARKS_READER_APP_KV_FILE)

        root = self._build_screens()

        logger.debug("Building the main tree view...")
        self._main_screen.start_tree_build()

        self._finalize_window_setup()

        return root

    def _initialize_settings_and_db(self) -> None:
        """Handle the initial setup of settings and the database."""
        self._reader_settings.set_config(self.config, Path(self.get_application_config()))
        self._reader_settings.validate_settings()
        self._reader_settings.set_barks_panels_dir()

        self._comics_database.set_inset_info(
            str(self._reader_settings.file_paths.get_comic_inset_files_dir()),
            self._reader_settings.file_paths.get_inset_file_ext(),
        )

        self._reader_settings.sys_file_paths.set_barks_reader_files_dir(
            self._reader_settings.reader_files_dir
        )

    def _build_screens(self) -> ScreenManager:
        logger.debug("Instantiating main screen...")
        filtered_title_lists = FilteredTitleLists()
        reader_tree_events = ReaderTreeBuilderEventDispatcher()
        self._main_screen = MainScreen(
            self._comics_database,
            self._reader_settings,
            reader_tree_events,
            filtered_title_lists,
            self._reader_screen_manager.screen_switchers,
            name=MAIN_READER_SCREEN,
        )
        self._set_custom_title_bar()
        self.update_fonts(Config.getint("graphics", "height"))

        logger.debug("Instantiating comic reader screen...")
        comic_reader_screen = get_barks_comic_reader_screen(
            COMIC_BOOK_READER_SCREEN,
            self._reader_settings,
            self._main_screen.app_icon_filepath,
            self.font_manager,
            self._screen_switchers.switch_to_comic_book_reader,
            self._screen_switchers.close_comic_book_reader,
        )
        self._main_screen.comic_book_reader = comic_reader_screen.comic_book_reader

        logger.debug("Instantiating introduction screen...")
        intro_screen = get_intro_compleat_barks_reader_screen(
            INTRO_COMPLEAT_BARKS_READER_SCREEN,
            self._reader_settings,
            self._main_screen.app_icon_filepath,
            self.font_manager,
            self._screen_switchers.close_intro_compleat_barks_reader,
        )

        reader_screens = ReaderScreens(
            self._main_screen,
            comic_reader_screen,
            intro_screen,
        )

        return self._reader_screen_manager.add_screens(reader_screens)

    def _set_custom_title_bar(self) -> None:
        Window.custom_titlebar = True
        title_bar = self._main_screen.ids.action_bar
        if Window.set_custom_titlebar(title_bar):
            logger.info("Window: setting custom titlebar successful")
        else:
            logger.warning("Window: setting custom titlebar not allowed on this system.")

    def _finalize_window_setup(self) -> None:
        """Finalize window state after the main build process.

        This includes forcing an initial resize event to ensure all widgets
        are correctly sized based on the loaded configuration.
        """
        if self.window_height == 0:
            # This is a known Kivy workaround. By briefly changing the window position,
            # we force an `on_resize` event to fire, which ensures that all UI elements
            # that depend on window size are correctly initialized.
            config_left = Config.getint("graphics", "left")
            Window.left = config_left + 1
            Window.left = config_left
        else:
            Window.left = self.window_left
            comic_page_aspect_ratio = 3200.0 / 2120.0
            width = round(self.window_height / comic_page_aspect_ratio)
            Window.size = (width, self.window_height + ACTION_BAR_SIZE_Y)

        # All the behind the scenes sizing and moving is done.
        # Now make the main window visible.
        Window.show()

        _log_screen_settings()


def _log_screen_settings() -> None:
    logger.info(f"Window size = {Window.size}, dpi = {Window.dpi}.")
    logger.info(f"Window pos = {Window.left},{Window.top}.")


def start_logging(_args: CmdArgs) -> None:
    log_level = logging.DEBUG
    # log_level = cmd_args.get_log_level()

    def color_formatter(_record: loguru.Record) -> str:
        sys_name_fmt = f"<yellow>{{extra[{LOGGER_SYS_NAME_KEY}]: <4}}</yellow>"

        return (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            f"{sys_name_fmt}: "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
            " - <level>{message}</level>"
            "\n"
            "{exception}"
        )

    config = {
        "handlers": [
            {
                "sink": sys.stdout,
                "format": color_formatter,
                "backtrace": True,
                "diagnose": True,
            },
            {
                "sink": str(config_info.app_log_path),
                "format": color_formatter,
                "rotation": "5 MB",
                "enqueue": True,
                "backtrace": True,
                "diagnose": True,
            },
        ],
        "extra": {"sys_name": APP_LOGGING_NAME},
    }
    logger.configure(**config)

    Config.set("kivy", "log_level", logging.getLevelName(log_level).lower())

    # Redirect Kivy's log messages to our main loguru setup.
    class LoguruKivyHandler(logging.Handler):
        def __init__(self, logr: loguru.Logger) -> None:
            self.logr = logr
            super().__init__()

        def emit(self, log_record: logging.LogRecord) -> None:
            def patch_loguru_rec(record: loguru.Record) -> None:
                record.update(exception=log_record.exc_info)
                record.update(file=log_record.filename)
                record.update(function=log_record.funcName)
                record.update(line=log_record.lineno)
                record.update(module=log_record.module)
                record.update(name=log_record.name)
                record.update(process=log_record.process)
                record.update(thread=log_record.thread)

            patched_logger = self.logr.patch(patch_loguru_rec)
            level = logging.getLevelName(log_record.levelno).lower()
            message = log_record.getMessage()

            # Now log the kivy information using Loguru.
            # Use getattr to call the appropriate logging method based on level.
            log_method = getattr(patched_logger, level, patched_logger.info)  # Fallback to 'info'
            log_method(message, sys_name = KIVY_LOGGING_NAME)

    kivy.Logger.addHandler(LoguruKivyHandler(logger))

    logger.info("*** Starting barks reader ***")
    logger.info(f'app config path = "{config_info.app_config_path}".')
    logger.info(f'kivy config dir = "{config_info.kivy_config_dir}".')


EXTRA_ARGS: list[ExtraArg] = [
    ExtraArg("--win-left", action="store", type=int, default=0),
    ExtraArg("--win-height", action="store", type=int, default=0),
]


def main() -> None:
    cmd_args = CmdArgs("Fantagraphics source files", extra_args=EXTRA_ARGS)
    args_ok, error_msg = cmd_args.args_are_valid()
    if not args_ok:
        # Logging may not be set up, so print to stderr as a fallback
        sys.exit(1)

    start_logging(cmd_args)

    # noinspection PyBroadException
    try:
        screen_info = get_screen_info()
        assert screen_info
        log_screen_metrics(screen_info)

        comics_database = cmd_args.get_comics_database(for_building_comics=False)
        win_left = cmd_args.get_extra_arg("--win_left")
        win_height = cmd_args.get_extra_arg("--win_height")

        logger.debug("Running kivy app...")
        assert Config.getint("kivy", "exit_on_escape") == 0
        kivy_app = BarksReaderApp(comics_database, win_left, win_height)
        kivy_app.run()
    except Exception:  # noqa: BLE001
        logger.exception("There's been a program error - the Barks reader app is terminating: ")
        sys.exit(1)

    logger.debug("Terminating...")
    logger.info(
        f"Final window size = {Window.size}, dpi = {Window.dpi}, pos = {Window.left},{Window.top}."
    )
