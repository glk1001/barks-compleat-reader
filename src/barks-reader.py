import logging
import sys
from pathlib import Path
from random import randrange

from kivy import Config
from kivy.app import App
from kivy.clock import Clock
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
from screeninfo import get_monitors

from barks_fantagraphics.comics_cmd_args import CmdArgs
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.comics_utils import setup_logging
from comic_book_reader import get_barks_comic_reader
from filtered_title_lists import FilteredTitleLists
from main_screen import MainScreen
from reader_tree_builder import ReaderTreeBuilder
from reader_ui_classes import ReaderTreeBuilderEventDispatcher

APP_TITLE = "The Compleat Barks Reader"
MAIN_READER_SCREEN = "main_screen"
COMIC_BOOK_READER = "comic_book_reader"

KV_FILE = Path(__file__).stem + ".kv"

# TODO: how to nicely handle main window
DEFAULT_ASPECT_RATIO = 3200.0 / 2120.0
DEFAULT_WINDOW_HEIGHT = round(0.96 * get_monitors()[0].height)
DEFAULT_WINDOW_WIDTH = int(round(DEFAULT_WINDOW_HEIGHT / DEFAULT_ASPECT_RATIO))
DEFAULT_LEFT_POS = 400
DEFAULT_TOP_POS = 50

SCREEN_TRANSITIONS = [
    NoTransition(duration=0),
    FadeTransition(),
    FallOutTransition(),
    RiseInTransition(),
    SwapTransition(),
    WipeTransition(),
]


# def get_str_pixel_width(text: str, **kwargs) -> int:
#     return kivy.core.text.Label(**kwargs).get_extents(text)[0]


class BarksReaderApp(App):
    def __init__(self, comics_db: ComicsDatabase, **kwargs):
        super().__init__(**kwargs)

        self.screen_manager = ScreenManager()
        self.comics_database = comics_db

        logging.debug("Instantiating main screen...")
        filtered_title_lists = FilteredTitleLists()
        reader_tree_events = ReaderTreeBuilderEventDispatcher()
        self.main_screen = MainScreen(
            self.comics_database,
            reader_tree_events,
            filtered_title_lists,
            self.switch_to_comic_book_reader,
            name=MAIN_READER_SCREEN,
        )

        Window.size = (DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        Window.left = DEFAULT_LEFT_POS
        Window.top = DEFAULT_TOP_POS

        self.main_screen_transitions = SCREEN_TRANSITIONS + [
            SlideTransition(direction="left"),
            CardTransition(direction="left", mode="push"),
        ]
        self.comic_book_reader_screen_transitions = SCREEN_TRANSITIONS + [
            SlideTransition(direction="right"),
            CardTransition(direction="right", mode="pop"),
        ]

    def build(self):
        logging.debug("Building app...")

        self.set_custom_title_bar()
        self.title = APP_TITLE

        self.build_tree_view()

        root = self.screen_manager
        root.add_widget(self.main_screen)
        root.current = MAIN_READER_SCREEN

        comic_reader = get_barks_comic_reader(COMIC_BOOK_READER, self.close_comic_book_reader)
        root.add_widget(comic_reader)

        self.main_screen.comic_book_reader = comic_reader.children[0]

        return root

    @staticmethod
    def on_action_bar_quit():
        App.get_running_app().stop()
        Window.close()

    def get_next_main_screen_transition(self) -> TransitionBase:
        transition_index = randrange(0, len(self.main_screen_transitions))
        return self.main_screen_transitions[transition_index]

    def get_next_reader_screen_transition(self) -> TransitionBase:
        transition_index = randrange(0, len(self.comic_book_reader_screen_transitions))
        return self.comic_book_reader_screen_transitions[transition_index]

    def switch_to_comic_book_reader(self):
        self.screen_manager.transition = self.get_next_reader_screen_transition()
        self.screen_manager.current = COMIC_BOOK_READER

    def close_comic_book_reader(self):
        self.main_screen.comic_closed()

        self.screen_manager.transition = self.get_next_main_screen_transition()
        self.screen_manager.current = MAIN_READER_SCREEN

    def set_custom_title_bar(self):
        Window.custom_titlebar = True
        title_bar = self.main_screen.ids.action_bar
        if Window.set_custom_titlebar(title_bar):
            logging.info("Window: setting custom titlebar successful")
        else:
            logging.info("Window: setting custom titlebar " "Not allowed on this system ")

    def build_tree_view(self):
        Clock.schedule_once(self.main_screen.loading_data_popup.open, 0)

        logging.debug("Building the tree view...")
        tree_builder = ReaderTreeBuilder(self.main_screen)
        tree_builder.build_main_screen_tree()
        self.main_screen.year_range_nodes = tree_builder.chrono_year_range_nodes
        logging.debug("Finished building.")


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

    Config.set("kivy", "exit_on_escape", "0")
    Config.write()

    logging.debug("Loading kv files...")
    Builder.load_file(KV_FILE)

    logging.debug("Running kivy app...")
    BarksReaderApp(cmd_args.get_comics_database()).run()

    logging.debug("Terminating...")
