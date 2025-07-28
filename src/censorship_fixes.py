from pathlib import Path
from typing import Callable

from kivy.lang import Builder
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen

from reader_settings import ReaderSettings

KV_FILE = Path(__file__).stem + ".kv"


class CensorshipFixes(BoxLayout):
    def __init__(
        self,
        reader_settings: ReaderSettings,
        on_close_screen: Callable[[], None],
        app_icon_file: str,
        **kwargs
    ):
        super().__init__(**kwargs)
        self._reader_settings = reader_settings
        self.censorship_fixes_widget = None


class CensorshipFixesScreen(BoxLayout, Screen):
    censorship_fixes_text = StringProperty("HELLO")

    def add_censorship_fixes_widget(self, censorship_fixes_widget: CensorshipFixes):
        self.censorship_fixes_widget = censorship_fixes_widget
        self.add_widget(self.censorship_fixes_widget)


def get_censorship_fixes_screen(
    screen_name: str,
    reader_settings: ReaderSettings,
    app_icon_file: str,
    on_close_screen: Callable[[], None],
):
    Builder.load_file(KV_FILE)

    root = CensorshipFixesScreen(name=screen_name)

    censorship_fixes_widget = CensorshipFixes(reader_settings, on_close_screen, app_icon_file)

    root.add_censorship_fixes_widget(censorship_fixes_widget)

    return root
