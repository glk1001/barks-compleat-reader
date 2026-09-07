from __future__ import annotations

from pathlib import Path

# ReaderScrollView/ReaderDropDown must be imported (Factory-registered) before
# kivy_helpers.kv's rule and the screen kv files that instantiate them are loaded.
from barks_kivy_ui.scrolling import ReaderDropDown, ReaderScrollView  # noqa: F401
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    NumericProperty,
    StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.button import Button
from kivy.uix.image import Image

KIVY_HELPERS_KV_FILE = Path(__file__).parent / "kivy_helpers.kv"


def set_kivy_busy_cursor() -> None:
    Clock.schedule_once(lambda _dt: Window.set_system_cursor("wait"), 0)


def set_kivy_normal_cursor() -> None:
    Clock.schedule_once(lambda _dt: Window.set_system_cursor("arrow"), 0)


# A button with an image and an expanded touch region around the image.
class TouchExpandedButton(Button):
    # Defining these properties here prevents a "NoneType" error on initialization.
    visual_size = NumericProperty(40)
    touch_padding = NumericProperty(10)
    source = StringProperty("")
    is_active = BooleanProperty(defaultvalue=True)


class TitlePageImage(ButtonBehavior, Image):
    TITLE_IMAGE_X_FRAC_OF_PARENT = 0.95
    TITLE_IMAGE_Y_FRAC_OF_PARENT = 0.95
