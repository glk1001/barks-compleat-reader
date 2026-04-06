from __future__ import annotations

from pathlib import Path

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    NumericProperty,
    StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.image import Image

KIVY_HELPERS_KV_FILE = Path(__file__).parent / "kivy_helpers.kv"


def set_kivy_busy_cursor() -> None:
    Clock.schedule_once(lambda _dt: Window.set_system_cursor("wait"), 0)


def set_kivy_normal_cursor() -> None:
    Clock.schedule_once(lambda _dt: Window.set_system_cursor("arrow"), 0)


class ScrollableDropDown(DropDown):
    """DropDown that doesn't consume touches when dismissing.

    Kivy's default DropDown returns True (consuming the touch) when the user
    clicks outside it, which prevents the clicked widget from receiving the
    event. Returning False after dismiss lets the touch fall through so that,
    for example, pressing the clear button while a dropdown is open both closes the dropdown
    and clears the search box in a single tap.
    """

    def on_touch_down(self, touch: object) -> bool:
        if not self.collide_point(*touch.pos) and self.auto_dismiss:  # ty: ignore[unresolved-attribute]
            self.dismiss()
            return False
        return super().on_touch_down(touch)


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
