from __future__ import annotations

from collections import deque
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, override

from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    ColorProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from loguru import logger
from screeninfo import get_monitors

from barks_reader.core.image_selector import FIT_MODE_CONTAIN, ImageInfo
from barks_reader.core.reader_settings import (
    BARKS_READER_SECTION,
    SHOW_FUN_VIEW_TITLE_INFO,
)
from barks_reader.core.settings_notifier import settings_notifier

from .reader_keyboard_nav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    KEY_SPACE,
    KEY_UP,
    clear_focus_highlight,
    clear_focus_in_list,
    draw_focus_highlight,
    is_escape_key,
    update_focus_in_list,
)
from .reader_navigation import ReaderNavigation

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.input import MotionEvent
    from kivy.uix.widget import Widget

    from barks_reader.core.reader_settings import ReaderSettings

FUN_IMAGE_VIEW_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

_MAX_IMAGES_HISTORY = 20
_DEBUG = False

_GOTO_FOCUS_GROUP = "fun_view_goto_focus"
_FILTER_FOCUS_GROUP = "fun_view_filter_focus"
_MENU_FOCUS_GROUP = "fun_view_menu_focus"

# Menu focus order is [close(x), All, Custom, Clear-All, theme rows...]; opening the
# menu lands on the "All" radio (index 1), so Up reaches the close button.
_MENU_START_IDX = 1


class _FunFocus(Enum):
    """Which fun-view control currently holds keyboard focus."""

    ARROW = auto()  # the "Goto Title" overlay arrow (top-right)
    FILTER = auto()  # the image-filter toggle button (top-left)
    MENU = auto()  # inside the open image-type options menu


class FunImageViewScreen(BoxLayout):
    """Screen for displaying a fun image.

    NOTE: This is a child layout that should be added over
          a parent FloatLayout.
    """

    # TODO: What happens if monitor changes??
    MAX_WINDOW_WIDTH = get_monitors()[0].width

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
        self._image_history: deque[ImageInfo] = deque(maxlen=_MAX_IMAGES_HISTORY)
        self._current_history_index = -1
        self._navigation = ReaderNavigation(self.MAX_WINDOW_WIDTH, 0.54, 0.98)

        self.on_goto_title_func: Callable[[], None] | None = None
        self.fun_view_from_title = True
        self._reader_settings = reader_settings
        self.show_current_title = self._reader_settings.show_fun_view_title_info

        # Keyboard navigation state.
        self._nav_active = False
        self._nav_on_exit_request: Callable[[], None] | None = None
        self._nav_focus = _FunFocus.ARROW
        self._menu_idx = 0

        settings_notifier.register_callback(
            BARKS_READER_SECTION, SHOW_FUN_VIEW_TITLE_INFO, self.on_change_show_current_title
        )

        goto_button = self.ids.goto_title_overlay.goto_button
        logger.debug(
            f"Go to title button touch region:"
            f" {goto_button.x},"
            f" {goto_button.y},"
            f" {goto_button.width},"
            f" {goto_button.height}."
        )

    def set_load_image_func(self, load_image_func: Callable[[ImageInfo], None]) -> None:
        self._load_image = load_image_func

    def on_resized(self, size: tuple[int, int]) -> None:
        self._navigation.update_regions(size[0], size[1], self.x, self.y)

    @override
    def on_touch_down(self, touch: MotionEvent) -> bool:
        if not self.is_visible or self.fun_options_enabled:
            return bool(super().on_touch_down(touch))

        x_rel = round(touch.x - self.x)
        y_rel = round(touch.y - self.y)

        if _DEBUG:
            logger.debug(
                f"Touch down event: self.x,self.y = {self.x},{self.y},"
                f" touch.x,touch.y = {round(touch.x)},{round(touch.y)},"
                f" window_width = {round(self.width)},"
                f" window_height = {round(self.height)}."
                f" x_rel,y_rel = {x_rel},{y_rel},"
                f" x_mid = {self._navigation.x_mid},"
                f" y_bottom_margin = {self._navigation.y_bottom_margin},"
                f" y_top_margin = {self._navigation.y_top_margin}."
            )

        # Give the up-arrow button priority before margin navigation.
        if self.ids.goto_title_overlay.goto_button.collide_point(touch.x, touch.y):
            return bool(super().on_touch_down(touch))

        if self._navigation.is_in_left_margin(x_rel, y_rel):
            logger.debug(f"Left margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            self._goto_previous_image()
            return True

        if self._navigation.is_in_right_margin(x_rel, y_rel):
            logger.debug(f"Right margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            self._goto_next_image()
            return True

        return bool(super().on_touch_down(touch))

    def prev_image(self) -> None:
        self._goto_previous_image()

    def next_image(self) -> None:
        self._goto_next_image()

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
        self.current_title_str = "" if title is None else ENUM_TO_STR_TITLE[title]
        self.fun_view_from_title = self.current_title_str != ""
        self.goto_title_button_active = self.fun_view_from_title
        logger.debug(f'Set fun view title to "{self.current_title_str}".')

    def on_goto_title(self) -> None:
        assert self.on_goto_title_func is not None
        self.on_goto_title_func()

    # --- Keyboard navigation -------------------------------------------------
    # Focus moves between the goto arrow (top-right) and the filter button
    # (top-left) with Up/Down; Enter fires the focused one. Pressing the filter
    # button opens the image-type options menu and moves focus into it, where
    # Up/Down move, Enter/Space toggle, and Escape closes the menu. Left/Right
    # keep cycling images while focus is on a button.

    @property
    def is_nav_active(self) -> bool:
        """Whether keyboard focus currently owns this screen."""
        return self._nav_active

    def enter_nav_focus(self, on_exit_request: Callable[[], None]) -> None:
        """Enter keyboard focus, landing on the menu, the arrow, or the filter button.

        ``on_exit_request`` is called when the user backs out of the top level
        (Escape) so the caller can hand focus back to the tree.
        """
        self._nav_active = True
        self._nav_on_exit_request = on_exit_request
        if self.fun_options_enabled:
            self._nav_focus = _FunFocus.MENU
            self._menu_idx = _MENU_START_IDX
        elif self.goto_title_button_active:
            self._nav_focus = _FunFocus.ARROW
        else:
            self._nav_focus = _FunFocus.FILTER
        self._draw_nav_focus()

    def exit_nav_focus(self) -> None:
        """Exit keyboard focus and clear every fun-view focus ring."""
        if not self._nav_active:
            return
        self._nav_active = False
        self._nav_on_exit_request = None
        self._clear_nav_focus()

    def handle_key(self, key: int) -> bool:
        """Handle a key press while in bottom focus. Returns True if consumed."""
        if not self._nav_active:
            return False
        if self._nav_focus == _FunFocus.MENU:
            return self._handle_menu_key(key)
        return self._handle_button_key(key)

    def _handle_button_key(self, key: int) -> bool:
        if key == KEY_LEFT:
            self.prev_image()
            self._reconcile_button_focus()
        elif key == KEY_RIGHT:
            self.next_image()
            self._reconcile_button_focus()
        elif key == KEY_UP:
            self._nav_focus = _FunFocus.FILTER
            self._draw_nav_focus()
        elif key == KEY_DOWN:
            if self.goto_title_button_active:
                self._nav_focus = _FunFocus.ARROW
                self._draw_nav_focus()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER, KEY_SPACE):
            self._activate_button_focus()
        elif is_escape_key(key):
            self._request_nav_exit()
        else:
            return False
        return True

    def _activate_button_focus(self) -> None:
        if self._nav_focus == _FunFocus.ARROW:
            if self.goto_title_button_active:
                self.on_goto_title()
        else:  # FILTER: open the options menu and move focus into it.
            self.fun_options_button_pressed()
            self._nav_focus = _FunFocus.MENU
            self._menu_idx = _MENU_START_IDX
            self._draw_nav_focus()

    def _reconcile_button_focus(self) -> None:
        """Keep focus valid after prev/next changed whether the arrow is actionable."""
        if self._nav_focus == _FunFocus.ARROW and not self.goto_title_button_active:
            self._nav_focus = _FunFocus.FILTER
        self._draw_nav_focus()

    def _handle_menu_key(self, key: int) -> bool:
        widgets = self._menu_focus_widgets()
        if not widgets:
            return False  # No focusable menu widgets: leave the key unhandled.
        self._menu_idx = min(self._menu_idx, len(widgets) - 1)
        if key == KEY_UP:
            self._menu_idx = max(0, self._menu_idx - 1)
            self._draw_nav_focus()
        elif key == KEY_DOWN:
            self._menu_idx = min(len(widgets) - 1, self._menu_idx + 1)
            self._draw_nav_focus()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER, KEY_SPACE):
            self._activate_menu_widget(widgets[self._menu_idx])
            self._draw_nav_focus()  # the focusable list may have grown/shrunk.
        elif is_escape_key(key):
            self._close_menu()
        elif key in (KEY_LEFT, KEY_RIGHT):
            pass  # Image cycling is disabled while the menu is open.
        else:
            return False
        return True

    def _close_menu(self) -> None:
        if self.fun_options_enabled:
            self.fun_options_button_pressed()  # toggles the menu off
        self._nav_focus = _FunFocus.FILTER
        self._draw_nav_focus()

    def _activate_menu_widget(self, widget: Widget) -> None:
        ids = self.ids
        if widget is ids.fun_options_button:
            self._close_menu()  # the close (x) button
        elif widget is ids.checkbox_all_image_types:
            ids.checkbox_all_image_types.active = True
        elif widget is ids.checkbox_custom_image_types:
            ids.checkbox_custom_image_types.active = True
        elif widget is ids.clear_all_button:
            self.view_options_clear_all_button_pressed()
        else:  # a CheckBoxRow theme toggle
            widget.active = not widget.active

    def _menu_focus_widgets(self) -> list[Widget]:
        """Return the currently keyboard-focusable menu widgets, top to bottom.

        The close (x) button leads, then the All/Custom radios. Selecting Custom
        reveals the Clear-All button (which sits at the top of the custom area) and
        the theme rows below it.
        """
        ids = self.ids
        widgets: list[Widget] = [
            ids.fun_options_button,
            ids.checkbox_all_image_types,
            ids.checkbox_custom_image_types,
        ]
        if ids.checkbox_custom_image_types.active:
            widgets.append(ids.clear_all_button)
            # custom_options_box children are held in reverse visual order.
            widgets.extend(reversed(ids.custom_options_box.children))
        return widgets

    def _all_menu_widgets(self) -> list[Widget]:
        """Every menu widget that may carry a ring (for blanket clearing)."""
        ids = self.ids
        return [
            ids.fun_options_button,
            ids.checkbox_all_image_types,
            ids.checkbox_custom_image_types,
            ids.clear_all_button,
            *reversed(ids.custom_options_box.children),
        ]

    def _request_nav_exit(self) -> None:
        callback = self._nav_on_exit_request
        self.exit_nav_focus()
        if callback is not None:
            callback()

    def _draw_nav_focus(self) -> None:
        self._clear_nav_focus()
        if self._nav_focus == _FunFocus.ARROW:
            if self.goto_title_button_active:
                draw_focus_highlight(self.ids.goto_title_overlay.goto_button, _GOTO_FOCUS_GROUP)
        elif self._nav_focus == _FunFocus.FILTER:
            draw_focus_highlight(self.ids.fun_options_button, _FILTER_FOCUS_GROUP)
        else:  # MENU
            widgets = self._menu_focus_widgets()
            if widgets:
                self._menu_idx = max(0, min(self._menu_idx, len(widgets) - 1))
                update_focus_in_list(widgets, self._menu_idx, _MENU_FOCUS_GROUP)

    def _clear_nav_focus(self) -> None:
        clear_focus_highlight(self.ids.goto_title_overlay.goto_button, _GOTO_FOCUS_GROUP)
        clear_focus_highlight(self.ids.fun_options_button, _FILTER_FOCUS_GROUP)
        clear_focus_in_list(self._all_menu_widgets(), _MENU_FOCUS_GROUP)

    def on_change_show_current_title(self) -> None:
        self.show_current_title = self._reader_settings.show_fun_view_title_info
