# ruff: noqa: I001, E402, ERA001

from __future__ import annotations

# ------------------------------------------------------------------ #
# --- We need to change the KIVY_HOME directory to be under this --- #
# --- app's settings directory. The 'config_info' module handles --- #
# --- this, and for this to work, we need to import it before    --- #
# --- any kivy imports.                                          --- #
import os
from pathlib import Path
from config_info import ConfigInfo

# This app will hook into kivy logging, so there is no kivy console
# logging required.
os.environ["KIVY_NO_CONSOLELOG"] = "1"
os.environ["KIVY_LOG_MODE"] = "MIXED"

APP_NAME = Path(__file__).stem
config_info = ConfigInfo(APP_NAME)
config_info.setup_app_config_dir()
# ------------------------------------------------------------------ #

import logging
import sys
import traceback
from typing import TYPE_CHECKING, Any

import kivy
from barks_fantagraphics.comics_cmd_args import CmdArgs
from barks_fantagraphics.comics_logging import setup_logging
from kivy import Config
from kivy.app import App
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.settings import Settings, SettingsWithSpinner
from screeninfo import get_monitors

from censorship_fixes import get_censorship_fixes_screen
from comic_book_reader import get_barks_comic_reader_screen
from filtered_title_lists import FilteredTitleLists
from font_manager import FontManager
from main_screen import MainScreen
from reader_consts_and_types import ACTION_BAR_SIZE_Y, APP_TITLE
from reader_screens import (
    CENSORSHIP_FIXES_SCREEN,
    COMIC_BOOK_READER_SCREEN,
    MAIN_READER_SCREEN,
    ReaderScreenManager,
    ReaderScreens,
)
from reader_settings import ReaderSettings
from reader_ui_classes import ReaderTreeBuilderEventDispatcher
from screen_metrics import get_screen_info, log_screen_metrics
from settings_fix import LONG_PATH, SettingLongPath

if TYPE_CHECKING:
    from barks_fantagraphics.comics_database import ComicsDatabase
    from kivy.config import ConfigParser
    from kivy.uix.screenmanager import ScreenManager
    from kivy.uix.widget import Widget

KV_FILE = Path(__file__).stem + ".kv"


class BarksReaderApp(App):
    """The main Kivy application class for the Barks Reader."""

    def __init__(self, comics_db: ComicsDatabase, **kwargs: str) -> None:
        super().__init__(**kwargs)

        self.title = APP_TITLE
        self.settings_cls = SettingsWithSpinner

        self._comics_database = comics_db
        self._reader_settings = ReaderSettings()
        self.font_manager = FontManager()

        self._reader_screen_manager = ReaderScreenManager(self.open_settings)
        self._screen_switchers = self._reader_screen_manager.screen_switchers

        self._main_screen: MainScreen | None = None

    def _on_window_resize(self, _window: Window, width: int, height: int) -> None:
        logging.debug(f"App window resize event: width = {width}, height = {height}.")
        self.update_fonts(height)

    def update_fonts(self, height: int) -> None:
        self.font_manager.update_font_sizes(height)
        self._main_screen.fonts_updated(self.font_manager)

    def close_app(self) -> None:
        if self._main_screen:
            self._main_screen.app_closing()
        App.get_running_app().stop()
        Window.close()

    def get_application_config(self, _default_path: str = "") -> str:
        return str(config_info.app_config_path)

    def build_config(self, config: ConfigParser) -> None:
        """Set default values for the application configuration."""
        # Set default window geometry if not already present in the config file
        primary_monitor = get_monitors()[0]
        default_height = round(0.97 * primary_monitor.height)
        default_width = round(default_height / (3200.0 / 2120.0))

        config.setdefaults(
            "graphics",
            {
                "width": default_width,
                "height": default_height,
                "left": 2400,
                "top": 50,
            },
        )

        # Delegate to the settings class to set its own defaults
        self._reader_settings.build_config(config)

    def build_settings(self, settings: Settings) -> None:
        # Register our custom widget type with the name 'longpath'
        settings.register_type(LONG_PATH, SettingLongPath)

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
        logging.info(f"Config change: section = '{section}', key = '{key}', value = '{value}'.")
        self._reader_settings.on_changed_setting(section, key, value)

    def build(self) -> Widget:
        logging.debug("Building app...")
        Window.bind(on_resize=self._on_window_resize)

        self._initialize_settings_and_db()

        logging.debug("Loading kv files...")
        # Pass the font manager to kv lang so it can be accessed
        Builder.load_string("#:set fm app.font_manager")
        Builder.load_file(KV_FILE)

        root = self._build_screens()

        logging.debug("Building the main tree view...")
        self._main_screen.start_tree_build()

        _finalize_window_setup()

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
        logging.debug("Instantiating main screen...")
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

        logging.debug("Instantiating comic reader screen...")
        comic_reader_screen = get_barks_comic_reader_screen(
            COMIC_BOOK_READER_SCREEN,
            self._reader_settings,
            self._main_screen.app_icon_filepath,
            self.font_manager,
            self._screen_switchers.switch_to_comic_book_reader,
            self._screen_switchers.close_comic_book_reader,
        )
        self._main_screen.comic_book_reader = comic_reader_screen.comic_book_reader

        logging.debug("Instantiating censorship fixes screen...")
        censorship_fixes_screen = get_censorship_fixes_screen(
            CENSORSHIP_FIXES_SCREEN,
            self._reader_settings,
            self._main_screen.app_icon_filepath,
            self.font_manager,
            self._screen_switchers.close_censorship_fixes,
        )

        reader_screens = ReaderScreens(
            self._main_screen, comic_reader_screen, censorship_fixes_screen
        )

        return self._reader_screen_manager.add_screens(reader_screens)

    def _set_custom_title_bar(self) -> None:
        Window.custom_titlebar = True
        title_bar = self._main_screen.ids.action_bar
        if Window.set_custom_titlebar(title_bar):
            logging.info("Window: setting custom titlebar successful")
        else:
            logging.warning("Window: setting custom titlebar not allowed on this system.")


def _finalize_window_setup() -> None:
    """Finalize window state after the main build process.

    This includes forcing an initial resize event to ensure all widgets
    are correctly sized based on the loaded configuration.
    """
    # This is a known Kivy workaround. By briefly changing the window position,
    # we force an `on_resize` event to fire, which ensures that all UI elements
    # that depend on window size are correctly initialized.
    config_left = Config.getint("graphics", "left")
    Window.left = config_left + 1
    Window.left = config_left

    # All the behind the scenes sizing and moving is done.
    # Now make the main window visible.
    Window.show()

    _log_screen_settings()


def _log_screen_settings() -> None:
    logging.info(f"Window size = {Window.size}, dpi = {Window.dpi}.")
    logging.info(f"Window pos = {Window.left},{Window.top}.")


def start_logging(_args: CmdArgs) -> None:
    log_level = logging.DEBUG
    # log_level = cmd_args.get_log_level()
    setup_logging(log_level, "app", str(config_info.app_log_path))
    Config.set("kivy", "log_level", logging.getLevelName(log_level).lower())

    # Redirect Kivy's log messages to our main logging setup
    class KivyCustomHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            logging.root.handle(record)

    kivy.Logger.addHandler(KivyCustomHandler())

    logging.info("*** Starting barks reader ***")
    logging.info(f'app config path = "{config_info.app_config_path}".')
    logging.info(f'kivy config dir = "{config_info.kivy_config_dir}".')


if __name__ == "__main__":
    cmd_args = CmdArgs("Fantagraphics source files")
    args_ok, error_msg = cmd_args.args_are_valid()
    if not args_ok:
        # Logging may not be set up, so print to stderr as a fallback
        sys.exit(1)

    start_logging(cmd_args)

    try:
        screen_info = get_screen_info()
        assert screen_info
        log_screen_metrics(screen_info)

        comics_database = cmd_args.get_comics_database(for_building_comics=False)

        logging.debug("Running kivy app...")
        assert Config.getint("kivy", "exit_on_escape") == 0
        kivy_app = BarksReaderApp(comics_database)
        kivy_app.run()
    except Exception as e:  # noqa: BLE001
        _, _, tb = sys.exc_info()
        tb_info = traceback.extract_tb(tb)
        filename, line, func, text = tb_info[-1]
        logging.fatal(
            f"There's been a program error - the Barks reader app is terminating:"
            f' Exception "{e}" at "{filename}:{line}" in "{func}" ({text}).'
        )
        traceback.print_exc()
        sys.exit(1)

    logging.debug("Terminating...")
    logging.info(
        f"Final window size = {Window.size}, dpi = {Window.dpi}, pos = {Window.left},{Window.top}."
    )
