from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    ColorProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from loguru import logger

from barks_reader.random_title_images import FIT_MODE_CONTAIN
from barks_reader.reader_settings import (
    BARKS_READER_SECTION,
    SHOW_FUN_VIEW_TITLE_INFO,
)
from barks_reader.reader_ui_classes import ARROW_WIDTH
from barks_reader.settings_notifier import settings_notifier

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

    is_visible = BooleanProperty(defaultvalue=False)
    image_texture = ObjectProperty(allownone=True)
    image_fit_mode = StringProperty(FIT_MODE_CONTAIN)
    image_color = ColorProperty()
    fun_options_enabled = BooleanProperty(defaultvalue=False)
    current_title_str = StringProperty()
    show_current_title = BooleanProperty(defaultvalue=True)

    def __init__(self, reader_settings: ReaderSettings, **kwargs: str) -> None:
        super().__init__(**kwargs)

        self.on_goto_title_func: Callable[[], None] | None = None
        self.fun_view_from_title = True
        self._reader_settings = reader_settings
        self.show_current_title = self._reader_settings.show_fun_view_title_info

        settings_notifier.register_callback(
            BARKS_READER_SECTION, SHOW_FUN_VIEW_TITLE_INFO, self.on_change_show_current_title
        )

    def fun_options_button_pressed(self) -> None:
        self.fun_options_enabled = not self.fun_options_enabled
        logger.debug(f"Fun view options button pressed. New state is '{self.fun_options_enabled}'.")

    def view_options_clear_all_button_pressed(self) -> None:
        logger.debug("Fun view options clear all pressed. Setting all checkboxes to inactive.")

        for child in self.ids.custom_options_box.children:
            child.active = False

    def set_title(self, title: Titles | None) -> None:
        self.current_title_str = "" if title is None else BARKS_TITLES[title]
        self.fun_view_from_title = self.current_title_str != ""

    def on_goto_title(self) -> None:
        assert self.on_goto_title_func is not None
        self.on_goto_title_func()

    def on_change_show_current_title(self) -> None:
        self.show_current_title = self._reader_settings.show_fun_view_title_info
