from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, override

from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    ColorProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from loguru import logger
from screeninfo import get_monitors

from barks_reader.core.random_title_images import FIT_MODE_CONTAIN, ImageInfo
from barks_reader.core.reader_settings import (
    BARKS_READER_SECTION,
    SHOW_FUN_VIEW_TITLE_INFO,
)
from barks_reader.core.settings_notifier import settings_notifier
from barks_reader.reader_navigation import ReaderNavigation
from barks_reader.reader_ui_classes import ARROW_WIDTH

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.input import MotionEvent

    from barks_reader.core.reader_settings import ReaderSettings

FUN_IMAGE_VIEW_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

MAX_IMAGES_HISTORY = 20


class FunImageViewScreen(BoxLayout):
    """Screen for displaying a fun image.

    NOTE: This is a child layout that should be added over
          a parent FloatLayout.
    """

    # TODO: What happens if monitor changes??
    MAX_WINDOW_WIDTH = get_monitors()[0].width
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

        self._load_image: Callable[[ImageInfo], None] | None = None
        self._image_history: deque[ImageInfo] = deque(maxlen=MAX_IMAGES_HISTORY)
        self._current_history_index = -1
        self._navigation = ReaderNavigation(self.MAX_WINDOW_WIDTH, 0.54, 0.98)

        self.on_goto_title_func: Callable[[], None] | None = None
        self.fun_view_from_title = True
        self._reader_settings = reader_settings
        self.show_current_title = self._reader_settings.show_fun_view_title_info

        settings_notifier.register_callback(
            BARKS_READER_SECTION, SHOW_FUN_VIEW_TITLE_INFO, self.on_change_show_current_title
        )

    def set_load_image_func(self, load_image_func: Callable[[ImageInfo], None]) -> None:
        self._load_image = load_image_func

    def on_resized(self, size: tuple[int, int]) -> None:
        self._navigation.update_regions(size[0], size[1], self.x, self.y)

    @override
    def on_touch_down(self, touch: MotionEvent) -> bool:
        if not self.is_visible or self.fun_options_enabled:
            return super().on_touch_down(touch)

        x_rel = round(touch.x - self.x)
        y_rel = round(touch.y - self.y)

        logger.debug(
            f"Touch down event: self.x,self.y = {self.x},{self.y},"
            f" touch.x,touch.y = {round(touch.x)},{round(touch.y)},"
            f" x_rel,y_rel = {x_rel},{y_rel},"
            f" width = {round(self.width)}, height = {round(self.height)}."
            f" x_mid = {self._navigation.x_mid},"
            f" y_bottom_margin = {self._navigation.y_bottom_margin},"
            f" y_top_margin = {self._navigation.y_top_margin}."
        )

        if self._navigation.is_in_left_margin(x_rel, y_rel):
            logger.debug(f"Left margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            self._goto_previous_image()
            return True

        if self._navigation.is_in_right_margin(x_rel, y_rel):
            logger.debug(f"Right margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            self._goto_next_image()
            return True

        return super().on_touch_down(touch)

    def _goto_previous_image(self) -> None:
        if self._current_history_index <= 0:
            return

        self._current_history_index -= 1
        self._load_current_history_image()

    def _goto_next_image(self) -> None:
        if self._current_history_index >= (len(self._image_history) - 1):
            return

        self._current_history_index += 1
        self._load_current_history_image()

    def _load_current_history_image(self) -> None:
        image_info = self._image_history[self._current_history_index]
        assert self._load_image is not None
        self._load_image(image_info)
        self._set_title(image_info.from_title)

    def fun_options_button_pressed(self) -> None:
        self.fun_options_enabled = not self.fun_options_enabled
        logger.debug(f"Fun view options button pressed. New state is '{self.fun_options_enabled}'.")

    def view_options_clear_all_button_pressed(self) -> None:
        logger.debug("Fun view options clear all pressed. Setting all checkboxes to inactive.")

        for child in self.ids.custom_options_box.children:
            child.active = False

    def set_last_loaded_image_info(self, image_info: ImageInfo) -> None:
        self._set_title(image_info.from_title)

        self._image_history.append(image_info)
        self._current_history_index = len(self._image_history) - 1
        assert image_info.filename
        logger.debug(
            f'Set last loaded fun image file "{image_info.filename.name}'
            f' and title: "{self.current_title_str}".'
        )

    def _set_title(self, title: Titles | None) -> None:
        self.current_title_str = "" if title is None else BARKS_TITLES[title]
        self.fun_view_from_title = self.current_title_str != ""
        self.goto_title_button_active = self.fun_view_from_title
        logger.debug(f'Set fun view title to "{self.current_title_str}".')

    def on_goto_title(self) -> None:
        assert self.on_goto_title_func is not None
        self.on_goto_title_func()

    def on_change_show_current_title(self) -> None:
        self.show_current_title = self._reader_settings.show_fun_view_title_info
