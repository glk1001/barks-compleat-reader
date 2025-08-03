from collections.abc import Callable
from pathlib import Path

from kivy.lang import Builder
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen

from font_manager import FontManager
from reader_consts_and_types import ACTION_BAR_SIZE_Y
from reader_formatter import get_action_bar_title
from reader_settings import ReaderSettings
from reader_utils import read_text_paragraphs

KV_FILE = Path(__file__).stem + ".kv"


class CensorshipFixesScreen(BoxLayout, Screen):
    action_bar_title = StringProperty()
    ACTION_BAR_TITLE_COLOR = (0.0, 1.0, 0.0, 1.0)
    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
    app_icon_filepath = StringProperty()
    action_bar_close_icon_filepath = StringProperty()
    censorship_fixes_text = StringProperty()

    def __init__(
        self,
        reader_settings: ReaderSettings,
        app_icon_file: str,
        font_manager: FontManager,
        on_close_screen: Callable[[], None],
        **kwargs: str
    ) -> None:
        super().__init__(**kwargs)

        self.action_bar_title = get_action_bar_title(
            font_manager, "Censorship Fixes and Other Changes"
        )
        self.app_icon_filepath = app_icon_file
        self.action_bar_close_icon_filepath = str(
            reader_settings.sys_file_paths.get_barks_reader_close_icon_file()
        )
        self._on_close_screen = on_close_screen
        self.censorship_fixes_text = read_text_paragraphs(
            reader_settings.sys_file_paths.get_censorship_fixes_text_file()
        )

    def close(self) -> None:
        self._on_close_screen()


def get_censorship_fixes_screen(
    screen_name: str,
    reader_settings: ReaderSettings,
    app_icon_file: str,
    font_manager: FontManager,
    on_close_screen: Callable[[], None],
) -> Screen:
    Builder.load_file(KV_FILE)

    return CensorshipFixesScreen(
        reader_settings,
        app_icon_file,
        font_manager,
        on_close_screen,
        name=screen_name,
    )
