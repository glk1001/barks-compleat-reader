import os

# This app will hook into kivy logging.
# So no kivy console logging required.
os.environ["KIVY_NO_CONSOLELOG"] = "1"
os.environ["KIVY_LOG_MODE"] = "MIXED"

# --- We need to set up config stuff here before any kivy imports.  ---
# --- This is because we change the KIVY_HOME directory to be under ---
# --- this app's settings directory.                                 ---
from pathlib import Path
from config_info import ConfigInfo

APP_NAME = Path(__file__).stem
config_info = ConfigInfo(APP_NAME)
config_info.setup_app_config_dir()
# ---------------------------------------------------------------------

import logging
import sys
import traceback
from random import randrange
from typing import Any, Union, List

import kivy
from kivy import Config
from kivy.app import App
from kivy.config import ConfigParser
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.screenmanager import (
    ScreenManager,
    RiseInTransition,
    FallOutTransition,
    FadeTransition,
    WipeTransition,
    SlideTransition,
    NoTransition,
    SwapTransition,
    CardTransition,
    TransitionBase,
)
from kivy.uix.settings import SettingsWithSpinner
from screeninfo import get_monitors

from barks_fantagraphics.comics_cmd_args import CmdArgs
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.comics_logging import setup_logging
from censorship_fixes import get_censorship_fixes_screen
from comic_book_reader import get_barks_comic_reader
from filtered_title_lists import FilteredTitleLists
from font_manager import FontManager
from main_screen import MainScreen
from reader_consts_and_types import ACTION_BAR_SIZE_Y, APP_TITLE
from reader_settings import ReaderSettings
from reader_ui_classes import ReaderTreeBuilderEventDispatcher, ScreenSwitchers
from screen_metrics import get_screen_info, log_screen_metrics
from settings_fix import SettingLongPath, LONG_PATH

# --- Constants ---
MAIN_READER_SCREEN = "main_screen"
COMIC_BOOK_READER_SCREEN = "comic_book_reader"
CENSORSHIP_FIXES_SCREEN = "censorship_fixes"
KV_FILE = Path(__file__).stem + ".kv"


class BarksReaderApp(App):
    """The main Kivy application class for the Barks Reader."""

    # Encapsulate screen transitions as class attributes
    _MAIN_SCREEN_TRANSITIONS: List[TransitionBase] = [
        NoTransition(duration=0),
        FadeTransition(),
        FallOutTransition(),
        RiseInTransition(),
        SwapTransition(),
        WipeTransition(),
        SlideTransition(direction="left"),
        CardTransition(direction="left", mode="push"),
    ]
    _READER_SCREEN_TRANSITIONS: List[TransitionBase] = [
        NoTransition(duration=0),
        FadeTransition(),
        FallOutTransition(),
        RiseInTransition(),
        SwapTransition(),
        WipeTransition(),
        SlideTransition(direction="right"),
        CardTransition(direction="right", mode="pop"),
    ]

    def __init__(self, comics_db: ComicsDatabase, **kwargs):
        super().__init__(**kwargs)

        self.title = APP_TITLE
        self.settings_cls = SettingsWithSpinner

        self._screen_manager = ScreenManager()
        self._comics_database = comics_db
        self._reader_settings = ReaderSettings()
        self.font_manager = FontManager()

        self._screen_switchers: Union[ScreenSwitchers, None] = None
        self._main_screen: Union[MainScreen, None] = None

    def _on_window_resize(self, _window, width, height):
        logging.debug(f"App window resize event: width = {width}, height = {height}.")
        self.update_fonts(height)

    def update_fonts(self, height):
        self.font_manager.update_font_sizes(height)
        self._main_screen.fonts_updated(self.font_manager)

    def close_app(self):
        if self._main_screen:
            self._main_screen.app_closing()
        App.get_running_app().stop()
        Window.close()

    def get_application_config(self, _default_path=""):
        return config_info.app_config_path

    def build_config(self, config: ConfigParser):
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

    def build_settings(self, settings):
        # Register our custom widget type with the name 'longpath'
        settings.register_type(LONG_PATH, SettingLongPath)

        self._reader_settings.build_settings(settings)
        self.config.write()
        settings.interface.menu.height = ACTION_BAR_SIZE_Y

    def on_config_change(self, config: ConfigParser, section: str, key: str, value: Any):
        logging.info(f"Config change: section = '{section}', key = '{key}', value = '{value}'.")
        self._reader_settings.on_changed_setting(section, key, value)

    def build(self):
        logging.debug("Building app...")
        Window.bind(on_resize=self._on_window_resize)

        self._initialize_settings_and_db()

        logging.debug("Loading kv files...")
        # Pass the font manager to kv lang so it can be accessed
        Builder.load_string(f"#:set fm app.font_manager")
        Builder.load_file(KV_FILE)

        root = self._build_screens()

        logging.debug("Building the main tree view...")
        self._main_screen.start_tree_build()

        _finalize_window_setup()

        return root

    def _initialize_settings_and_db(self):
        """Handles the initial setup of settings and the database."""
        self._reader_settings.set_config(self.config, self.get_application_config())
        self._reader_settings.validate_settings()
        self._reader_settings.set_barks_panels_dir()

        self._comics_database.set_inset_info(
            self._reader_settings.file_paths.get_comic_inset_files_dir(),
            self._reader_settings.file_paths.get_inset_file_ext(),
        )

        self._reader_settings.sys_file_paths.set_barks_reader_files_dir(
            self._reader_settings.reader_files_dir
        )

        self._screen_switchers = ScreenSwitchers(
            self.open_settings, self._switch_to_comic_book_reader, self._switch_to_censorship_fixes
        )

    def _build_screens(self) -> ScreenManager:
        root = self._screen_manager

        logging.debug("Instantiating main screen...")
        filtered_title_lists = FilteredTitleLists()
        reader_tree_events = ReaderTreeBuilderEventDispatcher()
        self._main_screen = MainScreen(
            self._comics_database,
            self._reader_settings,
            reader_tree_events,
            filtered_title_lists,
            self._screen_switchers,
            name=MAIN_READER_SCREEN,
        )
        self._set_custom_title_bar()
        self.update_fonts(Config.getint("graphics", "height"))
        root.add_widget(self._main_screen)

        logging.debug("Instantiating comic reader screen...")
        comic_reader_screen = get_barks_comic_reader(
            COMIC_BOOK_READER_SCREEN,
            self._reader_settings,
            self._main_screen.app_icon_filepath,
            self.font_manager,
            self._switch_to_comic_book_reader,
            self._close_comic_book_reader,
        )
        root.add_widget(comic_reader_screen)
        self._main_screen.comic_book_reader = comic_reader_screen.comic_book_reader

        logging.debug("Instantiating censorship fixes screen...")
        censorship_fixes_screen = get_censorship_fixes_screen(
            CENSORSHIP_FIXES_SCREEN,
            self._reader_settings,
            self._main_screen.app_icon_filepath,
            self.font_manager,
            self._close_censorship_fixes,
        )
        root.add_widget(censorship_fixes_screen)

        root.current = MAIN_READER_SCREEN

        return root

    def _set_custom_title_bar(self):
        Window.custom_titlebar = True
        title_bar = self._main_screen.ids.action_bar
        if Window.set_custom_titlebar(title_bar):
            logging.info("Window: setting custom titlebar successful")
        else:
            logging.warning("Window: setting custom titlebar not allowed on this system.")

    def _get_next_main_screen_transition(self) -> TransitionBase:
        return self._MAIN_SCREEN_TRANSITIONS[randrange(0, len(self._MAIN_SCREEN_TRANSITIONS))]

    def _get_next_reader_screen_transition(self) -> TransitionBase:
        return self._READER_SCREEN_TRANSITIONS[randrange(0, len(self._READER_SCREEN_TRANSITIONS))]

    def _switch_to_comic_book_reader(self):
        self._screen_manager.transition = self._get_next_reader_screen_transition()
        self._screen_manager.current = COMIC_BOOK_READER_SCREEN

    def _close_comic_book_reader(self):
        self._main_screen.comic_closed()

        self._screen_manager.transition = self._get_next_main_screen_transition()
        self._screen_manager.current = MAIN_READER_SCREEN

    def _switch_to_censorship_fixes(self):
        self._screen_manager.current = CENSORSHIP_FIXES_SCREEN

    def _close_censorship_fixes(self):
        self._screen_manager.transition = self._get_next_main_screen_transition()
        self._screen_manager.current = MAIN_READER_SCREEN


def _finalize_window_setup() -> None:
    """
    Finalizes window state after the main build process.
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


def start_logging(args: CmdArgs) -> None:
    log_level = logging.DEBUG
    # log_level = cmd_args.get_log_level()
    setup_logging(log_level, "app", config_info.app_log_path)
    Config.set("kivy", "log_level", logging.getLevelName(log_level).lower())

    # Redirect Kivy's log messages to our main logging setup
    class KivyCustomHandler(logging.Handler):
        def emit(self, record):
            logging.root.handle(record)

    kivy.Logger.addHandler(KivyCustomHandler())

    logging.info(f"*** Starting barks reader ***")
    logging.info(f'app config path = "{config_info.app_config_path}".')
    logging.info(f'kivy config dir = "{config_info.kivy_config_dir}".')


if __name__ == "__main__":
    cmd_args = CmdArgs("Fantagraphics source files")
    args_ok, error_msg = cmd_args.args_are_valid()
    if not args_ok:
        # Logging may not be set up, so print to stderr as a fallback
        print(f"Argument Error: {error_msg}", file=sys.stderr)
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
    except Exception as e:
        _, _, tb = sys.exc_info()
        tb_info = traceback.extract_tb(tb)
        filename, line, func, text = tb_info[-1]
        logging.fatal(
            f"There's been a program error - the Barks reader app is terminating:"
            f' Exception "{e}" at "{filename}:{line}" in "{func}" ({text}).'
        )
        sys.exit(1)

    logging.debug("Terminating...")
    logging.info(
        f"Final window size = {Window.size},"
        f" dpi = {Window.dpi}, pos = {Window.left},{Window.top}."
    )
