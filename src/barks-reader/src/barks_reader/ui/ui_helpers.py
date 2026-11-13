from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

# ReaderScrollView/ReaderDropDown must be imported (Factory-registered) before
# kivy_helpers.kv's rule and the screen kv files that instantiate them are loaded.
from barks_kivy_ui.scrolling import ReaderDropDown, ReaderScrollView  # noqa: F401
from kivy.clock import Clock
from kivy.core.window import Keyboard, Window
from kivy.properties import (  # ty: ignore[import-not-found]
    BooleanProperty,
    NumericProperty,
    StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.button import Button
from kivy.uix.image import Image

if TYPE_CHECKING:
    from kivy.input import MotionEvent

KIVY_HELPERS_KV_FILE = Path(__file__).parent / "kivy_helpers.kv"

# What to call a keycode. Two names can share one ("/" and "?" are both 47): the first
# Kivy lists is the one used.
KEY_NAMES: dict[int, str] = {code: name for name, code in reversed(Keyboard.keycodes.items())}


def is_tap(touch: MotionEvent) -> bool:
    """Return whether a touch is a tap, rather than a wheel tick or another mouse button.

    Args:
        touch: The touch, whose ``button`` is None on a touchscreen.

    Returns:
        True for a left click or a touchscreen touch.

    """
    return touch.button in (None, "left")


def set_kivy_busy_cursor() -> None:
    """Show the wait cursor, from the next frame."""
    Clock.schedule_once(lambda _dt: Window.set_system_cursor("wait"), 0)


def set_kivy_normal_cursor() -> None:
    """Show the arrow cursor again, from the next frame."""
    Clock.schedule_once(lambda _dt: Window.set_system_cursor("arrow"), 0)


class TouchExpandedButton(Button):
    """A button with an image and an expanded touch region around the image."""

    # Defining these properties here prevents a "NoneType" error on initialization.
    visual_size = NumericProperty(40)
    touch_padding = NumericProperty(10)
    source = StringProperty("")
    is_active = BooleanProperty(defaultvalue=True)


class TitlePageImage(ButtonBehavior, Image):
    """A story's title page image, pressed to read the story."""

    TITLE_IMAGE_X_FRAC_OF_PARENT = 0.95
    TITLE_IMAGE_Y_FRAC_OF_PARENT = 0.95
