import os

os.environ["KIVY_LOG_MODE"] = "MIXED"

import logging
import sys
from pathlib import Path
from random import randrange
from typing import Any, Union

from kivy import Config
from kivy.app import App
from kivy.config import ConfigParser
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.utils import platform
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
from comic_book_reader import get_barks_comic_reader
from filtered_title_lists import FilteredTitleLists
from font_manager import FontManager
from main_screen import MainScreen
from reader_consts_and_types import ACTION_BAR_SIZE_Y
from reader_settings import ReaderSettings
from reader_ui_classes import ReaderTreeBuilderEventDispatcher, SettingLongPath
from screen_metrics import get_screen_info, log_screen_metrics

APP_TITLE = "The Compleat Barks Disney Reader"
MAIN_READER_SCREEN = "main_screen"
COMIC_BOOK_READER = "comic_book_reader"

KV_FILE = Path(__file__).stem + ".kv"
APP_INI_FILENAME = Path(__file__).stem + ".ini"

# TODO: how to nicely handle main window
DEFAULT_ASPECT_RATIO = 3200.0 / 2120.0
DEFAULT_WINDOW_HEIGHT = round(0.97 * get_monitors()[0].height)
DEFAULT_WINDOW_WIDTH = round(DEFAULT_WINDOW_HEIGHT / DEFAULT_ASPECT_RATIO)
DEFAULT_LEFT_POS = 2400
DEFAULT_TOP_POS = 50

SCREEN_TRANSITIONS = [
    NoTransition(duration=0),
    FadeTransition(),
    FallOutTransition(),
    RiseInTransition(),
    SwapTransition(),
    WipeTransition(),
]


class BarksReaderApp(App):
    def __init__(self, comics_db: ComicsDatabase, **kwargs):
        super().__init__(**kwargs)

        self.title = APP_TITLE
        self._screen_manager = ScreenManager()
        self._comics_database = comics_db
        self._reader_settings = ReaderSettings()
        self.font_manager = FontManager()

        self._main_screen: Union[MainScreen, None] = None

        # Window.size = (DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        # Window.left = DEFAULT_LEFT_POS
        # Window.top = DEFAULT_TOP_POS

        self._main_screen_transitions = SCREEN_TRANSITIONS + [
            SlideTransition(direction="left"),
            CardTransition(direction="left", mode="push"),
        ]
        self._comic_book_reader_screen_transitions = SCREEN_TRANSITIONS + [
            SlideTransition(direction="right"),
            CardTransition(direction="right", mode="pop"),
        ]

        Window.bind(on_resize=self._on_window_resize)
        self.settings_cls = SettingsWithSpinner

    def _on_window_resize(self, _window, width, height):
        logging.debug(f"App window resize event: width = {width}, height = {height}.")
        logging.debug(
            f"App window resize event:"
            f" Window.width = {Window.width}, Window.height = {Window.height}."
        )

        self.font_manager.update_font_sizes(height)

    def close_app(self):
        self._main_screen.app_closing()
        App.get_running_app().stop()
        Window.close()

    def show_settings(self, _instance):
        self.open_settings()

    def get_application_config(self, default_path=""):
        logging.debug(f'self.user_data_dir = "{self.user_data_dir}".')

        if platform == "android":
            return os.path.join(self.user_data_dir, APP_INI_FILENAME)

        if platform == "ios":
            config_path = f"~/Documents/{APP_INI_FILENAME}"
        elif platform == "win":
            config_path = os.path.join(self.directory, APP_INI_FILENAME)
        else:
            config_path = os.path.join(self._reader_settings.reader_files_dir, APP_INI_FILENAME)

        config_path = os.path.expanduser(config_path)
        logging.info(f'Using app config file "{config_path}".')

        return config_path

    def build_config(self, config: ConfigParser):
        self._reader_settings.build_config(config)

    def build_settings(self, settings):
        # Register our custom widget type with the name 'longpath'
        settings.register_type("longpath", SettingLongPath)

        self._reader_settings.build_settings(settings)
        self.config.write()
        settings.interface.menu.height = ACTION_BAR_SIZE_Y

    def on_config_change(self, config: ConfigParser, section: str, key: str, value: Any):
        logging.info(f"Config change: section = '{section}', key = '{key}', value = '{value}'.")
        self._reader_settings.on_changed_setting(section, key, value)

    def build(self):
        logging.debug("Building app...")

        self._initialize_settings_and_db()

        logging.debug("Loading kv files...")
        # Pass the font manager to kv lang so it can be accessed
        Builder.load_string(f"#:set fm app.font_manager")
        Builder.load_file(KV_FILE)

        root = self._build_ui_components()

        logging.debug("Building the main tree view...")
        self._main_screen.start_tree_build()

        _set_main_window()

        return root

    def _initialize_settings_and_db(self):
        """Handles the initial setup of settings and the database."""
        self._reader_settings.set_config(self.config)
        self._reader_settings.validate_settings()
        self._reader_settings.set_barks_panels_dir()

        self._comics_database.set_inset_info(
            self._reader_settings.file_paths.get_comic_inset_files_dir(),
            self._reader_settings.file_paths.get_inset_file_ext(),
        )

        self._reader_settings.sys_file_paths.set_barks_reader_files_dir(
            self._reader_settings.reader_files_dir
        )

    def _build_ui_components(self) -> ScreenManager:
        """Constructs and wires up the main UI screens and components."""
        logging.debug("Instantiating main screen...")
        filtered_title_lists = FilteredTitleLists()
        reader_tree_events = ReaderTreeBuilderEventDispatcher()
        self._main_screen = MainScreen(
            self,
            self._comics_database,
            self._reader_settings,
            reader_tree_events,
            filtered_title_lists,
            name=MAIN_READER_SCREEN,
        )
        self._set_custom_title_bar()

        root = self._screen_manager
        root.add_widget(self._main_screen)
        root.current = MAIN_READER_SCREEN

        comic_reader = get_barks_comic_reader(
            COMIC_BOOK_READER,
            self._reader_settings,
            self._main_screen.app_icon_filepath,
            self._switch_to_comic_book_reader,
            self._close_comic_book_reader,
        )
        root.add_widget(comic_reader)
        self._main_screen.comic_book_reader = comic_reader.children[0]

        return root

    def _set_custom_title_bar(self):
        Window.custom_titlebar = True
        title_bar = self._main_screen.ids.action_bar
        if Window.set_custom_titlebar(title_bar):
            logging.info("Window: setting custom titlebar successful")
        else:
            logging.info("Window: setting custom titlebar " "Not allowed on this system ")

    def _get_next_main_screen_transition(self) -> TransitionBase:
        transition_index = randrange(0, len(self._main_screen_transitions))
        return self._main_screen_transitions[transition_index]

    def _get_next_reader_screen_transition(self) -> TransitionBase:
        transition_index = randrange(0, len(self._comic_book_reader_screen_transitions))
        return self._comic_book_reader_screen_transitions[transition_index]

    def _switch_to_comic_book_reader(self):
        self._screen_manager.transition = self._get_next_reader_screen_transition()
        self._screen_manager.current = COMIC_BOOK_READER

    def _close_comic_book_reader(self):
        self._main_screen.comic_closed()

        self._screen_manager.transition = self._get_next_main_screen_transition()
        self._screen_manager.current = MAIN_READER_SCREEN


def _set_main_window() -> None:
    # Window.size = (694, 900)
    # Window.left = 2400
    # Window.top = 50
    # Config.set("graphics", "width", DEFAULT_WINDOW_WIDTH)
    # Config.set("graphics", "height", DEFAULT_WINDOW_HEIGHT)
    # Config.set("graphics", "left", DEFAULT_LEFT_POS)
    # Config.set("graphics", "top", DEFAULT_TOP_POS)
    # Config.write()

    # Force resize event
    config_left = Config.getint("graphics", "left")
    Window.left = config_left + 10
    Window.left = config_left

    # All the behind the scenes sizing and moving is done.
    # Now make the main window visible.
    Window.show()

    _log_screen_settings()


def _log_screen_settings() -> None:
    logging.info(f"Default aspect ratio = {DEFAULT_ASPECT_RATIO}")
    logging.info(f"Default window size = {DEFAULT_WINDOW_WIDTH},{DEFAULT_WINDOW_HEIGHT}")
    logging.info(f"Default window pos = {DEFAULT_LEFT_POS},{DEFAULT_TOP_POS}")
    logging.info(f"Window size = {Window.size}, dpi = {Window.dpi}.")
    logging.info(f"Window pos = {Window.left},{Window.top}.")


if __name__ == "__main__":
    # TODO(glk): Some issue with type checking inspection?
    # noinspection PyTypeChecker
    cmd_args = CmdArgs("Fantagraphics source files")
    args_ok, error_msg = cmd_args.args_are_valid()
    if not args_ok:
        logging.error(error_msg)
        sys.exit(1)

    setup_logging(log_level=logging.DEBUG)
    #    setup_logging(cmd_args.get_log_level())

    screen_info = get_screen_info()
    assert screen_info
    log_screen_metrics(screen_info)

    Config.set("kivy", "exit_on_escape", "0")
    Config.write()

    comics_database = cmd_args.get_comics_database()

    logging.debug("Running kivy app...")
    kivy_app = BarksReaderApp(comics_database)
    kivy_app.run()

    logging.debug("Terminating...")
    logging.info(
        f"Final window size = {Window.size},"
        f" dpi = {Window.dpi}, pos = {Window.left},{Window.top}."
    )
