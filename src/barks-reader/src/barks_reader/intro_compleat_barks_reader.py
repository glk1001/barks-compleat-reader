from collections.abc import Callable
from pathlib import Path

from kivy.lang import Builder
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen

from barks_reader.font_manager import FontManager
from barks_reader.reader_formatter import get_action_bar_title
from barks_reader.reader_settings import ReaderSettings
from barks_reader.reader_ui_classes import ACTION_BAR_SIZE_Y

INTRO_COMPLEAT_BARKS_READER_KV_FILE = Path(__file__).with_suffix(".kv")


class IntroCompleatBarksReaderScreen(BoxLayout, Screen):
    action_bar_title = StringProperty()
    ACTION_BAR_TITLE_COLOR = (0.0, 1.0, 0.0, 1.0)
    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
    app_icon_filepath = StringProperty()
    intro_source = StringProperty()

    def __init__(
        self,
        reader_settings: ReaderSettings,
        app_icon_file: str,
        font_manager: FontManager,
        on_close_screen: Callable[[], None],
        **kwargs: str,
    ) -> None:
        super().__init__(**kwargs)

        self.action_bar_title = get_action_bar_title(
            font_manager, "Introduction to the Compleat Barks Reader"
        )
        self.app_icon_filepath = app_icon_file
        self._on_close_screen = on_close_screen
        self.intro_source = str(reader_settings.sys_file_paths.get_intro_image_file())

    def close(self) -> None:
        self._on_close_screen()


def get_intro_compleat_barks_reader_screen(
    screen_name: str,
    reader_settings: ReaderSettings,
    app_icon_file: str,
    font_manager: FontManager,
    on_close_screen: Callable[[], None],
) -> Screen:
    Builder.load_file(str(INTRO_COMPLEAT_BARKS_READER_KV_FILE))

    return IntroCompleatBarksReaderScreen(
        reader_settings,
        app_icon_file,
        font_manager,
        on_close_screen,
        name=screen_name,
    )
