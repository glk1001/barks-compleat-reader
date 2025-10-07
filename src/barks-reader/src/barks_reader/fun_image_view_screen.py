from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from kivy.properties import (
    BooleanProperty,
    ColorProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from loguru import logger

from barks_reader.random_title_images import FIT_MODE_CONTAIN
from barks_reader.reader_ui_classes import ARROW_WIDTH

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_reader.reader_settings import ReaderSettings

FUN_IMAGE_VIEW_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")


class FunImageViewScreen(BoxLayout):
    """Screen for displaying a fun image.

    NOTE: This is a child layout that should be added over
          a parent FloatLayout.
    """

    UP_ARROW_WIDTH = ARROW_WIDTH

    goto_title_button_active = BooleanProperty(defaultvalue=True)

    fun_view_opacity = NumericProperty(0.0)
    fun_view_image_texture = ObjectProperty(allownone=True)
    fun_view_image_fit_mode = StringProperty(FIT_MODE_CONTAIN)
    fun_view_image_color = ColorProperty()
    fun_view_options_enabled = BooleanProperty(defaultvalue=False)

    def __init__(self, _reader_settings: ReaderSettings, **kwargs: str) -> None:
        super().__init__(**kwargs)

        self.on_goto_title_func: Callable[[], None] | None = None
        self.fun_view_from_title = True

    def view_options_button_pressed(self) -> None:
        self.fun_view_options_enabled = not self.fun_view_options_enabled
        logger.debug(
            f"Fun view options button pressed. New state is '{self.fun_view_options_enabled}'."
        )

    def view_options_clear_all_button_pressed(self) -> None:
        logger.debug("Fun view options clear all pressed. Setting all checkboxes to inactive.")

        for child in self.ids.custom_options_box.children:
            child.active = False

    def on_goto_title(self) -> None:
        assert self.on_goto_title_func is not None
        self.on_goto_title_func()
