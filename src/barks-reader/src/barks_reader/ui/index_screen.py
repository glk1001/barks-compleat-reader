from __future__ import annotations

import string
import textwrap
from abc import abstractmethod
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles
from comic_utils.timing import Timing
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    NumericProperty,
    ObjectProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from loguru import logger

from barks_reader.ui.reader_keyboard_nav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_PAGE_DOWN,
    KEY_PAGE_UP,
    KEY_RIGHT,
    KEY_UP,
    clear_focus_highlight,
    clear_focus_in_list,
    draw_focus_highlight,
)
from barks_reader.ui.reader_ui_classes import ARROW_WIDTH, MainTreeViewNode

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.gridlayout import GridLayout
    from kivy.uix.widget import Widget

    from barks_reader.core.random_title_images import ImageInfo

MAX_TITLE_AND_PAGES_LEN = 34 + 8  # len(", 11,...") == 8

INDEX_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

SAVED_NODE_STATE_FIRST_LETTER_KEY = "first_letter"

INDEX_NAV_FOCUS_GROUP = "index_nav_focus"

_LETTER_ORDER = list("0'" + string.ascii_uppercase)

_PAGE_SCROLL_STEP = 0.2


class _IndexNavPanel(Enum):
    ALPHABET = auto()
    PREFIX = auto()
    ITEMS = auto()


class IndexMenuButton(Button):
    """A custom button for the A-Z menu, styled in the .kv file."""

    is_selected = BooleanProperty(defaultvalue=False)


class IndexItemButton(Button):
    """A custom button for the index items, styled in the .kv file."""


class TitleShowSpeechButton(Button):
    """A custom button for showing speech bubbles for titles, styled in the .kv file."""


class SpeechBubblesPopup(Popup):
    """A custom popup for showing speech bubbles, styled in the .kv file."""


class TextBoxWithTitleAndBorder(BoxLayout):
    """Text box with title and rectangle border."""

    def __init__(self, title: str, content: str, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self.title = title
        self.content = content


class Theme:
    """A central place for theme constants."""

    ROW_HEIGHT = dp(25)
    INDEX_ITEM_LEFT_PAD = dp(20)
    SUB_ITEM_INDENT_STEP = dp(20)

    MENU_TEXT = (0, 0, 0, 1)
    MENU_BG = (0, 0, 0, 0)
    MENU_BG_SELECTED = (0.0, 0.8, 0.0, 0.5)

    ITEM_TEXT = (0, 0, 0, 1)
    ITEM_BG = (0, 0, 0, 0)
    ITEM_BG_SELECTED = (0.8, 0.8, 0.0, 0.5)

    TITLE_TEXT = (0, 0, 0, 1)
    TITLE_BG = (0.0, 0.0, 0.95, 0.1)
    TITLE_BG_SELECTED = (0.85, 0.85, 0.85, 1)


# noinspection PyAbstractClass
class IndexScreen(FloatLayout):
    UP_ARROW_WIDTH = ARROW_WIDTH

    index_theme = ObjectProperty()
    _selected_letter_button = ObjectProperty(None, allownone=True)
    num_columns = NumericProperty(2)

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)

        self.index_theme = Theme()
        App.get_running_app().index_theme = self.index_theme  # Make theme accessible globally in kv

        self._current_image_info: ImageInfo | None = None
        self.on_goto_background_title_func: Callable[[ImageInfo], None] | None = None

        self.treeview_index_node: MainTreeViewNode | None = None

        self._alphabet_buttons: dict[str, Button] = {}
        self._open_tag_button: Button | None = None
        self._open_tag_widgets: list[Widget] = []

        # Keyboard navigation state
        self._nav_active: bool = False
        self._nav_panel: _IndexNavPanel = _IndexNavPanel.ALPHABET
        self._nav_focused_letter_idx: int = 0
        self._nav_focused_col: int = 0
        self._nav_focused_item_idx: int = 0
        self._nav_on_exit_request: Callable | None = None
        self._grid_version: int = 0  # Incremented on every items grid repopulation.
        self._nav_saved_grid_version: int = -1  # Version when ITEMS nav state was last saved.
        self._nav_focused_btn: Button | None = None  # Button ref for robust position restore.

    def on_goto_background_title(self) -> None:
        assert self.on_goto_background_title_func is not None
        if not self._current_image_info:
            return
        self.on_goto_background_title_func(self._current_image_info)

    # --- Keyboard navigation public API ---

    def enter_nav_focus(self, on_exit_request: Callable) -> None:
        """Enter keyboard navigation mode. on_exit_request is called when the user exits."""
        self._nav_on_exit_request = on_exit_request
        self._nav_active = True
        # Restore items position if the grid hasn't changed since we last left it.
        if (
            self._nav_panel == _IndexNavPanel.ITEMS
            and self._nav_saved_grid_version == self._grid_version
            and self._nav_focused_btn is not None
        ):
            # Search all columns for the saved button to guard against a stale _nav_focused_col.
            for col_idx in range(self.num_columns):
                col_buttons = self._get_col_buttons(col_idx)
                if self._nav_focused_btn in col_buttons:
                    self._nav_focused_col = col_idx
                    self._nav_focused_item_idx = col_buttons.index(self._nav_focused_btn)
                    self._draw_item_focus()
                    return
        self._nav_panel = _IndexNavPanel.ALPHABET
        # Start focus on the currently selected letter.
        if self._selected_letter_button:
            letter = self._selected_letter_button.text
            if letter in _LETTER_ORDER:
                self._nav_focused_letter_idx = _LETTER_ORDER.index(letter)
        self._draw_letter_focus()

    def exit_nav_focus(self) -> None:
        """Exit keyboard navigation mode and clear all highlights."""
        if not self._nav_active:
            return
        self._nav_active = False
        self._nav_on_exit_request = None
        self._clear_letter_focus()
        self._clear_all_item_focus()

    def handle_key(self, key: int) -> bool:
        """Handle a key press. Returns True if consumed, False to propagate."""
        if not self._nav_active:
            return False
        if self._nav_panel == _IndexNavPanel.ALPHABET:
            return self._handle_alphabet_key(key)
        return self._handle_items_key(key)

    # --- Alphabet panel navigation ---

    def _handle_alphabet_key(self, key: int) -> bool:
        if key == KEY_UP:
            self._move_letter_focus(-1)
        elif key == KEY_DOWN:
            self._move_letter_focus(1)
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._select_focused_letter()
        elif key == KEY_RIGHT:
            self._on_right_from_alphabet()
        elif key == KEY_ESCAPE:
            callback = self._nav_on_exit_request
            self.exit_nav_focus()
            if callback:
                callback()
        else:
            return False
        return True

    def _move_letter_focus(self, delta: int) -> None:
        self._clear_letter_focus()
        self._nav_focused_letter_idx = (self._nav_focused_letter_idx + delta) % len(_LETTER_ORDER)
        self._select_focused_letter()
        self._draw_letter_focus()

    def _select_focused_letter(self) -> None:
        letter = _LETTER_ORDER[self._nav_focused_letter_idx]
        self.on_letter_press(self._alphabet_buttons[letter])

    def _enter_items_panel(self) -> None:
        col_buttons = self._get_col_buttons(0)
        if not col_buttons:
            return
        self._clear_letter_focus()
        self._nav_panel = _IndexNavPanel.ITEMS
        self._nav_focused_col = 0
        self._nav_focused_item_idx = 0
        self._draw_item_focus()

    def _on_right_from_alphabet(self) -> None:
        self._enter_items_panel()

    def _on_back_from_items(self) -> None:
        self._enter_alphabet_panel()

    def _on_up_from_first_item(self) -> None:
        pass  # Default: stop at the top item.

    # --- Items panel navigation ---

    def _handle_items_key(self, key: int) -> bool:
        if key == KEY_UP:
            self._handle_items_up()
        elif key == KEY_DOWN:
            self._move_item_focus(1)
        elif key == KEY_RIGHT:
            self._move_col_focus(1)
        elif key == KEY_LEFT:
            if self._nav_focused_col == 0:
                self._on_back_from_items()
            else:
                self._move_col_focus(-1)
        elif key == KEY_ESCAPE:
            self._on_back_from_items()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._activate_focused_item()
        elif key == KEY_PAGE_UP:
            self._scroll_page(-1)
        elif key == KEY_PAGE_DOWN:
            self._scroll_page(1)
        else:
            return False
        return True

    def _handle_items_up(self) -> None:
        if self._nav_focused_item_idx == 0:
            self._on_up_from_first_item()
        else:
            self._move_item_focus(-1)

    def _move_item_focus(self, delta: int) -> None:
        col_buttons = self._get_col_buttons(self._nav_focused_col)
        if not col_buttons:
            return
        new_idx = max(0, min(len(col_buttons) - 1, self._nav_focused_item_idx + delta))
        if new_idx == self._nav_focused_item_idx:
            return
        self._clear_all_item_focus()
        self._nav_focused_item_idx = new_idx
        self._draw_item_focus()

    def _move_col_focus(self, delta: int) -> None:
        new_col = self._nav_focused_col + delta
        if new_col < 0 or new_col >= self.num_columns:
            return
        new_col_buttons = self._get_col_buttons(new_col)
        if not new_col_buttons:
            return
        self._clear_all_item_focus()
        self._nav_focused_col = new_col
        self._nav_focused_item_idx = min(self._nav_focused_item_idx, len(new_col_buttons) - 1)
        self._draw_item_focus()

    def _activate_focused_item(self) -> None:
        col_buttons = self._get_col_buttons(self._nav_focused_col)
        if not col_buttons or self._nav_focused_item_idx >= len(col_buttons):
            return
        btn = col_buttons[self._nav_focused_item_idx]
        old_count = len(col_buttons)
        btn.trigger_action(duration=0)
        # Re-sync focus after items may have been added/removed by the action.
        # duration=0 fires on_release synchronously, so sub-items are scheduled
        # (via Clock.schedule_once at delay 0) before our resync runs.
        Clock.schedule_once(lambda _dt: self._resync_item_focus(btn, old_count), 0.05)

    def _resync_item_focus(self, btn: Button, old_count: int) -> None:
        if not self._nav_active or self._nav_panel != _IndexNavPanel.ITEMS:
            return
        col_buttons = self._get_col_buttons(self._nav_focused_col)
        new_count = len(col_buttons)
        if new_count > old_count:
            # Sub-items were expanded — move focus to the first one.
            self._nav_focused_item_idx = min(self._nav_focused_item_idx + 1, new_count - 1)
        else:
            # Collapsed or unchanged — stay on (or near) the parent button.
            try:
                self._nav_focused_item_idx = col_buttons.index(btn)
            except ValueError:
                self._nav_focused_item_idx = min(self._nav_focused_item_idx, max(0, new_count - 1))
        self._clear_all_item_focus()
        self._draw_item_focus()

    def _scroll_page(self, direction: int) -> None:
        scroll_view = self.ids.index_scroll_view
        scroll_view.scroll_y = max(
            0.0, min(1.0, scroll_view.scroll_y - direction * _PAGE_SCROLL_STEP)
        )

    def _enter_alphabet_panel(self) -> None:
        self._clear_all_item_focus()
        self._nav_panel = _IndexNavPanel.ALPHABET
        self._draw_letter_focus()

    # --- Focus drawing helpers ---

    def _draw_letter_focus(self) -> None:
        letter = _LETTER_ORDER[self._nav_focused_letter_idx]
        btn = self._alphabet_buttons.get(letter)
        if btn:
            draw_focus_highlight(btn, INDEX_NAV_FOCUS_GROUP)

    def _clear_letter_focus(self) -> None:
        clear_focus_in_list(self._alphabet_buttons.values(), INDEX_NAV_FOCUS_GROUP)

    def _draw_item_focus(self) -> None:
        col_buttons = self._get_col_buttons(self._nav_focused_col)
        if not col_buttons:
            return
        self._nav_focused_item_idx = min(self._nav_focused_item_idx, len(col_buttons) - 1)
        btn = col_buttons[self._nav_focused_item_idx]
        self._nav_focused_btn = btn
        draw_focus_highlight(btn, INDEX_NAV_FOCUS_GROUP, color=(1, 0.55, 0, 1))
        self.ids.index_scroll_view.scroll_to(btn)
        self._nav_saved_grid_version = self._grid_version

    def _clear_all_item_focus(self) -> None:
        for col_idx in range(self.num_columns):
            layout = self._get_col_layout(col_idx)
            self._clear_layout_focus(layout)

    def _clear_layout_focus(self, widget: Widget) -> None:
        clear_focus_highlight(widget, INDEX_NAV_FOCUS_GROUP)
        for child in widget.children:
            self._clear_layout_focus(child)

    # --- Column button helpers ---

    def _get_col_buttons(self, col_idx: int) -> list[Button]:
        layout = self._get_col_layout(col_idx)
        result: list[Button] = []
        self._collect_buttons(layout, result)
        return result

    def _get_col_layout(self, col_idx: int) -> Widget:
        if self.num_columns == 2:  # noqa: PLR2004
            return [self.ids.left_column_layout, self.ids.right_column_layout][col_idx]
        return [
            self.ids.left_column_layout,
            self.ids.middle_column_layout,
            self.ids.right_column_layout,
        ][col_idx]

    def _collect_buttons(self, widget: Widget, result: list[Button]) -> None:
        for child in reversed(widget.children):
            if isinstance(child, Button):
                result.append(child)
            else:
                self._collect_buttons(child, result)

    def _populate_alphabet_menu(self) -> None:
        """Create the A-Z buttons and add them to the GridLayout."""
        timing = Timing()

        alphabet_side_layout: GridLayout = self.ids.alphabet_side_layout
        for letter in "0" + "'" + string.ascii_uppercase:
            button = IndexMenuButton(text=letter)
            button.bind(on_release=self.on_letter_press)
            self._alphabet_buttons[letter] = button
            alphabet_side_layout.add_widget(button)

        logger.debug(f"Created A-Z index buttons in {timing.get_elapsed_time_with_unit()}.")

    @abstractmethod
    def _new_index_image(self) -> None:
        pass

    @abstractmethod
    def _create_index_button(self, item: Any) -> IndexItemButton:  # noqa: ANN401
        pass

    @abstractmethod
    def _cancel_index_image_change_events(self) -> None:
        pass

    @abstractmethod
    def _get_items_for_letter(self, first_letter: str) -> list:
        pass

    @abstractmethod
    def _populate_index_for_letter(self, first_letter: str) -> None:
        pass

    def on_letter_press(self, button: Button) -> None:
        """Handle a letter button press and display the corresponding index items."""
        self._open_tag_widgets.clear()
        self._open_tag_button = None

        first_letter = button.text
        logger.debug(f"Letter '{first_letter}' pressed.")
        self.treeview_index_node.saved_state[SAVED_NODE_STATE_FIRST_LETTER_KEY] = first_letter

        # Let the .kv file handle the color changes by setting the property.
        if self._selected_letter_button and self._selected_letter_button != button:
            self._selected_letter_button.is_selected = False
        button.is_selected = True
        self._selected_letter_button = button

        self._populate_index_for_letter(first_letter)

    def _populate_index_grid(self, letter: str) -> None:
        """Handle a letter button press and display the corresponding index items."""
        self._grid_version += 1
        timing = Timing()

        self._new_index_image()

        left_index_column: BoxLayout = self.ids.left_column_layout
        middle_index_column: BoxLayout = self.ids.middle_column_layout
        right_index_column: BoxLayout = self.ids.right_column_layout
        left_index_column.clear_widgets()
        middle_index_column.clear_widgets()
        right_index_column.clear_widgets()

        items_for_letter = self._get_items_for_letter(letter)
        if not items_for_letter:
            left_index_column.add_widget(self._get_no_items_button(letter))
            return

        # Populate the columns
        num_items = len(items_for_letter)

        if self.num_columns == 3:  # noqa: PLR2004
            split1 = (num_items + 2) // 3
            split2 = split1 + (num_items - split1 + 1) // 2

            left_index_items = items_for_letter[:split1]
            middle_index_items = items_for_letter[split1:split2]
            right_index_items = items_for_letter[split2:]

            for item in left_index_items:
                left_index_column.add_widget(self._create_index_button(item))
            for item in middle_index_items:
                middle_index_column.add_widget(self._create_index_button(item))
            for item in right_index_items:
                right_index_column.add_widget(self._create_index_button(item))
        else:
            split_point = (num_items + 1) // 2
            left_index_items = items_for_letter[:split_point]
            right_index_items = items_for_letter[split_point:]

            for item in left_index_items:
                left_index_column.add_widget(self._create_index_button(item))

            for item in right_index_items:
                right_index_column.add_widget(self._create_index_button(item))

        self.ids.index_scroll_view.scroll_y = 1

        logger.debug(
            f"Populated index page for letter '{letter}' in {timing.get_elapsed_time_with_unit()}."
        )

    def on_is_visible(self, _instance: Self, value: bool) -> None:
        """When the widget becomes visible, automatically press the 'A' button."""
        if not value:
            self._cancel_index_image_change_events()
            return

        if self._selected_letter_button:
            # The index has already been shown, just change the index image.
            self._new_index_image()
        else:
            # Which 'first_letter' to show first.
            if SAVED_NODE_STATE_FIRST_LETTER_KEY not in self.treeview_index_node.saved_state:
                first_letter = "A"
            else:
                first_letter = self.treeview_index_node.saved_state[
                    SAVED_NODE_STATE_FIRST_LETTER_KEY
                ]

            self.on_letter_press(self._alphabet_buttons[first_letter])

    def _get_indexable_title(self, title: Titles) -> str:
        return self._get_indexable_title_from_str(BARKS_TITLES[title])

    def _get_indexable_title_from_str(self, title_str: str) -> str:
        title_str = textwrap.shorten(title_str, width=MAX_TITLE_AND_PAGES_LEN, placeholder="...")
        return self._get_sortable_string(title_str)

    @staticmethod
    def _get_sortable_string(text: str) -> str:
        text_upper = text.upper()
        if text_upper.startswith("THE "):
            return text[4:] + ", The"
        if text_upper.startswith("A "):
            return text[2:] + ", A"
        return text

    def _handle_collapse(self, level_of_click: int) -> None:
        # When collapsing a parent, close it and all its children.
        slice_index = level_of_click
        widgets_to_close = self._open_tag_widgets[slice_index:]
        for widget in widgets_to_close[:]:
            if widget.parent:
                widget.parent.remove_widget(widget)
            self._open_tag_widgets.remove(widget)

    def _handle_expand_or_switch(self, button: Button) -> None:
        level_of_click = self._get_level_of_click_for_expand_or_switch(button)

        # Determine slice index for cleanup based on click type
        slice_index = (
            0  # Top-level switch (e.g., Africa -> Asia). Close everything.
            if level_of_click == -1
            else (
                level_of_click + 1
            )  # Drill-down or lateral move. Close lists at the same or deeper level.
        )

        # Perform the cleanup.
        widgets_to_close = self._open_tag_widgets[slice_index:]
        if widgets_to_close:
            for widget in widgets_to_close[:]:  # Iterate over a copy
                if widget.parent:
                    widget.parent.remove_widget(widget)
                self._open_tag_widgets.remove(widget)

    def _get_level_of_click_for_collapse(self, button: Button) -> tuple[bool, int]:
        for i, container in enumerate(self._open_tag_widgets):
            if getattr(container, "owner_button", None) == button:
                return True, i
        return False, -1

    def _get_level_of_click_for_expand_or_switch(self, button: Button) -> int:
        if self._open_tag_widgets:
            for i, container in enumerate(self._open_tag_widgets):
                # Walk up a maximum of 20 parents as a safety measure against infinite loops.
                current = button
                for _ in range(20):
                    if not current:
                        break
                    if current == container:
                        return i
                    current = current.parent
        return -1
