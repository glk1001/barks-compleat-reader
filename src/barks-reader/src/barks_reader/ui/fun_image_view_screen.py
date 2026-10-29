from __future__ import annotations

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

from barks_reader.core import log_markers
from barks_reader.core.image_history import ImageHistory
from barks_reader.core.image_selector import FIT_MODE_CONTAIN, ImageInfo
from barks_reader.core.keys import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    KEY_SPACE,
    KEY_UP,
    is_escape_key,
)
from barks_reader.core.main_layout import MainLayoutMode
from barks_reader.core.reader_navigation import ReaderNavigation
from barks_reader.core.reader_settings import (
    BARKS_READER_SECTION,
    SHOW_FUN_VIEW_TITLE_INFO,
)
from barks_reader.core.settings_notifier import settings_notifier

from .platform_window_utils import WindowManager
from .reader_keyboard_nav import (
    clear_focus_highlight,
    clear_focus_in_list,
    draw_focus_highlight,
    update_focus_in_list,
)
from .tap_targets import Rect, window_rect

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.core.image import Texture
    from kivy.input import MotionEvent
    from kivy.uix.widget import Widget

    from barks_reader.core.reader_settings import ReaderSettings

FUN_IMAGE_VIEW_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

_MAX_IMAGES_HISTORY = 20
_DEBUG = False

# The margins a press steps the images from: all of the view but a band at the top,
# which holds the options and goto buttons, and a sliver at the bottom.
_TOP_MARGIN_FRAC_OF_HEIGHT = 0.04
_BOTTOM_MARGIN_FRAC_OF_HEIGHT = 0.98

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


def _title_str(title: Titles | None) -> str:
    return "" if title is None else ENUM_TO_STR_TITLE[title]


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
    # The book's layout (core.main_layout). On the two-page spread the view is a page:
    # the image on show above the one before it in the history, the lower tier, when
    # the image on show is landscape; a tall one stands alone, whole.
    layout_mode = StringProperty(MainLayoutMode.SINGLE.value)
    previous_image_texture = ObjectProperty(allownone=True)
    previous_image_fit_mode = StringProperty(FIT_MODE_CONTAIN)
    previous_title_str = StringProperty()
    stacked = BooleanProperty(defaultvalue=False)
    fun_options_enabled = BooleanProperty(defaultvalue=False)
    current_title_str = StringProperty()
    show_current_title = BooleanProperty(defaultvalue=True)

    def __init__(self, reader_settings: ReaderSettings, **kwargs: str) -> None:
        super().__init__(**kwargs)

        self._load_image: Callable[[ImageInfo], None] | None = None
        self._load_texture: Callable[[ImageInfo, Callable[[Texture], None]], None] | None = None
        self._history = ImageHistory(_MAX_IMAGES_HISTORY)
        # The lower tier's image, so a texture that arrives after another step is dropped.
        self._wanted_previous: ImageInfo | None = None
        self._navigation = ReaderNavigation(
            self.MAX_WINDOW_WIDTH,
            _TOP_MARGIN_FRAC_OF_HEIGHT,
            _BOTTOM_MARGIN_FRAC_OF_HEIGHT,
            is_fullscreen=WindowManager.is_fullscreen_now,
        )

        # Takes a ``from_keyboard`` keyword so the handler can tell an Enter on the
        # focused arrow from a mouse click on it. See on_goto_title.
        self.on_goto_title_func: Callable[..., None] | None = None
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

    def set_load_texture_func(
        self, load_texture_func: Callable[[ImageInfo, Callable[[Texture], None]], None]
    ) -> None:
        """Take the loader the lower tier's image is decoded with."""
        self._load_texture = load_texture_func

    def on_size(self, _instance: Widget, size: tuple[float, float]) -> None:
        """Work the tap margins out again for the view's new size.

        The margins are the view's own: a press lands relative to the view, so its
        place in the window plays no part (on the spread the view is the right page).
        """
        self._navigation.update_regions(round(size[0]), round(size[1]), 0, 0)

    def on_layout_mode(self, _instance: Widget, _mode: str) -> None:
        self._refresh_lower_tier()

    def on_image_texture(self, _instance: Widget, _texture: Texture | None) -> None:
        self._update_stacked()

    def on_previous_image_texture(self, _instance: Widget, _texture: Texture | None) -> None:
        self._update_stacked()

    def _update_stacked(self) -> None:
        """Stack the two tiers when the view is a page and the image on show is landscape."""
        texture = self.image_texture
        self.stacked = (
            self.layout_mode == MainLayoutMode.SPREAD.value
            and self.previous_image_texture is not None
            and texture is not None
            and texture.width >= texture.height
        )

    def _lower_tier_height(self) -> int:
        return round(self.height / 2)

    def tap_target_regions(self) -> dict[str, Rect]:
        """Return the margins that step through the images, for a GUI test to tap.

        Stacked, the margins are the upper tier's halves and the lower tier is its own
        target: a press on it promotes its image.
        """
        if not self.is_visible or self.fun_options_enabled:
            return {}
        width, height = round(self.width), round(self.height)
        regions = self._navigation.tap_regions(width, height)
        targets: dict[str, tuple[int, int, int, int]] = {}
        lower_tier_top = self._lower_tier_height() if self.stacked else 0
        for name in ("left margin", "right margin"):
            if name not in regions:
                continue
            x, y, w, h = regions[name]
            top = y + h
            bottom = max(y, lower_tier_top)
            if top > bottom:
                targets[name] = (x, bottom, w, top - bottom)
        if self.stacked:
            targets["lower tier"] = (0, 0, width, lower_tier_top)
        return {
            name: window_rect(self, self.x + x, self.y + y, w, h)
            for name, (x, y, w, h) in targets.items()
        }

    @override
    def on_touch_down(self, touch: MotionEvent) -> bool:
        # Hidden, the screen keeps its full size under the showing one, faded to nothing:
        # its options button took the title view's top-left presses. It takes no touch.
        if not self.is_visible:
            return False
        # A press off the view is no press on it: the margin checks bound a press by
        # its height only, and on the two-page spread the tree stands beside the view,
        # where its rows' taps (but the top one's, in the band above the margins) were
        # "left margin" presses with a negative x.
        if not self.collide_point(touch.x, touch.y):
            return False
        if self.fun_options_enabled:
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

        if self._step_for_press(x_rel, y_rel):
            return True

        return bool(super().on_touch_down(touch))

    def _step_for_press(self, x_rel: int, y_rel: int) -> bool:
        """Step the images for a press at (x_rel, y_rel); False when it is on no margin.

        Stacked, a press on the lower tier promotes its image, a step back; the
        upper tier's halves step back and forward as the whole view's do.
        """
        if self.stacked and y_rel < self._lower_tier_height():
            logger.debug(log_markers.LOWER_TIER_PRESSED.format(x=x_rel, y=y_rel))
            self._goto_previous_image()
            return True

        if self._navigation.is_in_left_margin(x_rel, y_rel):
            logger.debug(log_markers.LEFT_MARGIN_PRESSED.format(x=x_rel, y=y_rel))
            self._goto_previous_image()
            return True

        if self._navigation.is_in_right_margin(x_rel, y_rel):
            logger.debug(log_markers.RIGHT_MARGIN_PRESSED.format(x=x_rel, y=y_rel))
            self._goto_next_image()
            return True

        return False

    def prev_image(self) -> None:
        self._goto_previous_image()

    def next_image(self) -> None:
        self._goto_next_image()

    def _goto_previous_image(self) -> None:
        image_info = self._history.back()
        if image_info is not None:
            self._load_history_image(image_info)

    def _goto_next_image(self) -> None:
        image_info = self._history.forward()
        if image_info is not None:
            self._load_history_image(image_info)

    def _load_history_image(self, image_info: ImageInfo) -> None:
        assert self._load_image is not None
        self._load_image(image_info)
        self._set_title(image_info.from_title)
        self._refresh_lower_tier()

    def needs_a_second_image(self) -> bool:
        """Whether the spread's lower tier has nothing to show: one image in the history."""
        return self.layout_mode == MainLayoutMode.SPREAD.value and len(self._history.images) == 1

    def seed_previous_image(self, image_info: ImageInfo) -> None:
        """Put `image_info` before the images shown, as the lower tier's at boot."""
        if not self._history.add_oldest(image_info):
            return
        assert image_info.filename
        logger.debug(
            log_markers.FUN_VIEW_SEEDED.format(
                filename=image_info.filename.name, title=_title_str(image_info.from_title)
            )
        )
        self._refresh_lower_tier()

    def _refresh_lower_tier(self) -> None:
        """Show the image before the one on show in the lower tier, on the spread."""
        on_the_spread = self.layout_mode == MainLayoutMode.SPREAD.value
        previous = self._history.previous() if on_the_spread else None
        self._wanted_previous = previous
        if previous is None:
            self.previous_image_texture = None
            self.previous_title_str = ""
            if on_the_spread:
                logger.debug(log_markers.FUN_VIEW_LOWER_TIER_EMPTY)
            return

        assert previous.filename
        assert self._load_texture is not None

        def apply_texture(texture: Texture) -> None:
            if self._wanted_previous is not previous:
                return  # Another step overtook this load.
            self.previous_image_fit_mode = previous.fit_mode
            self.previous_title_str = _title_str(previous.from_title)
            self.previous_image_texture = texture
            assert previous.filename
            logger.debug(
                log_markers.FUN_VIEW_LOWER_TIER.format(
                    filename=previous.filename.name, title=self.previous_title_str
                )
            )

        self._load_texture(previous, apply_texture)

    def fun_options_button_pressed(self) -> None:
        self.fun_options_enabled = not self.fun_options_enabled
        logger.debug(log_markers.FUN_OPTIONS_PRESSED.format(state=self.fun_options_enabled))

    def view_options_clear_all_button_pressed(self) -> None:
        logger.debug("Fun view options clear all pressed. Setting all checkboxes to inactive.")

        for child in self.ids.custom_options_box.children:
            child.active = False

    def set_last_loaded_image_info(self, image_info: ImageInfo) -> None:
        self._set_title(image_info.from_title)

        self._history.add(image_info)
        assert image_info.filename
        logger.debug(
            log_markers.FUN_IMAGE_LOADED.format(
                filename=image_info.filename.name, title=self.current_title_str
            )
        )
        self._refresh_lower_tier()

    def _set_title(self, title: Titles | None) -> None:
        self.current_title_str = _title_str(title)
        self.fun_view_from_title = self.current_title_str != ""
        self.goto_title_button_active = self.fun_view_from_title
        logger.debug(log_markers.FUN_VIEW_TITLE_SET.format(title=self.current_title_str))

    def on_goto_title(self, *, from_keyboard: bool = False) -> None:
        """Fire the goto-title arrow.

        The kv-wired ``on_arrow_press`` is the pointer path and leaves ``from_keyboard``
        at its default, so the handler can keep a mouse click in mouse mode rather than
        landing the app in keyboard nav.
        """
        assert self.on_goto_title_func is not None
        self.on_goto_title_func(from_keyboard=from_keyboard)

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
                self.on_goto_title(from_keyboard=True)
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

        Never empty: the close (x) button leads, then the All/Custom radios. Selecting Custom
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
            self._menu_idx = max(0, min(self._menu_idx, len(widgets) - 1))
            update_focus_in_list(widgets, self._menu_idx, _MENU_FOCUS_GROUP)

    def _clear_nav_focus(self) -> None:
        clear_focus_highlight(self.ids.goto_title_overlay.goto_button, _GOTO_FOCUS_GROUP)
        clear_focus_highlight(self.ids.fun_options_button, _FILTER_FOCUS_GROUP)
        clear_focus_in_list(self._all_menu_widgets(), _MENU_FOCUS_GROUP)

    def on_change_show_current_title(self) -> None:
        self.show_current_title = self._reader_settings.show_fun_view_title_info
