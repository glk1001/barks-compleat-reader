import logging
import os
import sys
from pathlib import Path
from random import randrange
from typing import Any, Union

os.environ["KIVY_LOG_MODE"] = "MIXED"

from kivy import Config
from kivy.app import App
from kivy.clock import Clock
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
from comic_book_reader import get_barks_comic_reader
from filtered_title_lists import FilteredTitleLists
from font_manager import FontManager
from main_screen import MainScreen
from reader_consts_and_types import ACTION_BAR_SIZE_Y
from reader_settings import ReaderSettings
from reader_tree_builder import ReaderTreeBuilder
from reader_ui_classes import ReaderTreeBuilderEventDispatcher
from screen_metrics import get_screen_info, log_screen_metrics

APP_TITLE = "The Compleat Barks Disney Reader"
MAIN_READER_SCREEN = "main_screen"
COMIC_BOOK_READER = "comic_book_reader"

KV_FILE = Path(__file__).stem + ".kv"

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
        self.__screen_manager = ScreenManager()
        self.__comics_database = comics_db
        self.__reader_settings = ReaderSettings()
        self.font_manager = FontManager()

        self.__main_screen: Union[MainScreen, None] = None

        # Window.size = (DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        # Window.left = DEFAULT_LEFT_POS
        # Window.top = DEFAULT_TOP_POS

        self.__main_screen_transitions = SCREEN_TRANSITIONS + [
            SlideTransition(direction="left"),
            CardTransition(direction="left", mode="push"),
        ]
        self.__comic_book_reader_screen_transitions = SCREEN_TRANSITIONS + [
            SlideTransition(direction="right"),
            CardTransition(direction="right", mode="pop"),
        ]

        Window.bind(on_resize=self.on_window_resize)
        self.settings_cls = SettingsWithSpinner

    def on_window_resize(self, _window, width, height):
        logging.debug(f"App window resize event: width = {width}, height = {height}.")
        logging.debug(
            f"App window resize event:"
            f" Window.width = {Window.width}, Window.height = {Window.height}."
        )

        self.font_manager.update_font_sizes(height)

    def close_app(self):
        self.__main_screen.app_closing()
        App.get_running_app().stop()
        Window.close()

    def show_settings(self, _instance):
        self.open_settings()

    def build_config(self, config):
        self.__reader_settings.build_config(config)

    def build_settings(self, settings):
        self.__reader_settings.build_settings(settings)
        settings.interface.menu.height = ACTION_BAR_SIZE_Y

    def on_config_change(self, config: ConfigParser, section: str, key: str, value: Any):
        logging.info(f"Config change: section = '{section}', key = '{key}', value = '{value}'.")
        self.__reader_settings.on_changed_setting(section, key, value)

    def build(self):
        logging.debug("Building app...")

        self.__initialize_settings_and_db()

        logging.debug("Loading kv files...")
        # Pass the font manager to kv lang so it can be accessed
        Builder.load_string(f"#:set fm app.font_manager")
        Builder.load_file(KV_FILE)

        root = self.__build_ui_components()

        logging.debug("Building the main tree view...")
        self.__build_tree_view()

        _set_main_window()

        return root

    def __initialize_settings_and_db(self):
        """Handles the initial setup of settings and the database."""
        self.__reader_settings.set_config(self.config)
        self.__reader_settings.validate_settings()
        self.__reader_settings.set_barks_panels_dir()

        self.__comics_database.set_inset_info(
            self.__reader_settings.file_paths.get_comic_inset_files_dir(),
            self.__reader_settings.file_paths.get_inset_file_ext(),
        )

        self.__reader_settings.sys_file_paths.set_barks_reader_files_dir(
            self.__reader_settings.reader_files_dir
        )

    def __build_ui_components(self) -> ScreenManager:
        """Constructs and wires up the main UI screens and components."""
        logging.debug("Instantiating main screen...")
        filtered_title_lists = FilteredTitleLists()
        reader_tree_events = ReaderTreeBuilderEventDispatcher()
        self.__main_screen = MainScreen(
            self.__comics_database,
            self.__reader_settings,
            reader_tree_events,
            filtered_title_lists,
            name=MAIN_READER_SCREEN,
        )
        self.__set_custom_title_bar()

        root = self.__screen_manager
        root.add_widget(self.__main_screen)
        root.current = MAIN_READER_SCREEN

        comic_reader = get_barks_comic_reader(
            COMIC_BOOK_READER,
            self.__reader_settings,
            self.__switch_to_comic_book_reader,
            self.__close_comic_book_reader,
        )
        root.add_widget(comic_reader)
        self.__main_screen.comic_book_reader = comic_reader.children[0]

        return root

    def __set_custom_title_bar(self):
        Window.custom_titlebar = True
        title_bar = self.__main_screen.ids.action_bar
        if Window.set_custom_titlebar(title_bar):
            logging.info("Window: setting custom titlebar successful")
        else:
            logging.info("Window: setting custom titlebar " "Not allowed on this system ")

    def __build_tree_view(self):
        self.__main_screen.set_new_loading_data_popup_image()
        Clock.schedule_once(lambda dt: self.__main_screen.loading_data_popup.open(), 0)

        tree_builder = ReaderTreeBuilder(self.__main_screen)
        self.__main_screen.year_range_nodes = tree_builder.chrono_year_range_nodes
        Clock.schedule_once(lambda dt: tree_builder.build_main_screen_tree(), 0)

    def __get_next_main_screen_transition(self) -> TransitionBase:
        transition_index = randrange(0, len(self.__main_screen_transitions))
        return self.__main_screen_transitions[transition_index]

    def __get_next_reader_screen_transition(self) -> TransitionBase:
        transition_index = randrange(0, len(self.__comic_book_reader_screen_transitions))
        return self.__comic_book_reader_screen_transitions[transition_index]

    def __switch_to_comic_book_reader(self):
        self.__screen_manager.transition = self.__get_next_reader_screen_transition()
        self.__screen_manager.current = COMIC_BOOK_READER

    def __close_comic_book_reader(self):
        self.__main_screen.comic_closed()

        self.__screen_manager.transition = self.__get_next_main_screen_transition()
        self.__screen_manager.current = MAIN_READER_SCREEN


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
