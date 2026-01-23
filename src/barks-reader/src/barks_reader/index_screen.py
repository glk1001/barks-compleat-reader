import string
import textwrap
from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles
from comic_utils.timing import Timing
from kivy.app import App
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ObjectProperty  # ty: ignore[unresolved-import]
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from loguru import logger

from barks_reader.reader_ui_classes import ARROW_WIDTH, MainTreeViewNode

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.gridlayout import GridLayout
    from kivy.uix.widget import Widget

    from barks_reader.core.random_title_images import ImageInfo

MAX_TITLE_AND_PAGES_LEN = 34 + 8  # len(", 11,...") == 8

INDEX_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

SAVED_NODE_STATE_FIRST_LETTER_KEY = "first_letter"


class IndexMenuButton(Button):
    """A custom button for the A-Z menu, styled in the .kv file."""

    is_selected = BooleanProperty(defaultvalue=False)


class IndexItemButton(Button):
    """A custom button for the index items, styled in the .kv file."""


class TitleItemButton(Button):
    """A custom button for title items, styled in the .kv file."""


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

    def on_goto_background_title(self) -> None:
        assert self.on_goto_background_title_func is not None
        if not self._current_image_info:
            return
        self.on_goto_background_title_func(self._current_image_info)

    def _populate_alphabet_menu(self) -> None:
        """Create the A-Z buttons and add them to the GridLayout."""
        timing = Timing()

        alphabet_layout: GridLayout = self.ids.alphabet_layout
        for letter in "0" + "'" + string.ascii_uppercase:
            button = IndexMenuButton(text=letter)
            button.bind(on_release=self.on_letter_press)
            self._alphabet_buttons[letter] = button
            alphabet_layout.add_widget(button)

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
        timing = Timing()

        self._new_index_image()

        left_index_column: BoxLayout = self.ids.left_column_layout
        right_index_column: BoxLayout = self.ids.right_column_layout
        left_index_column.clear_widgets()
        right_index_column.clear_widgets()

        items_for_letter = self._get_items_for_letter(letter)
        if not items_for_letter:
            left_index_column.add_widget(self._get_no_items_button(letter))
            return

        # Populate the two columns
        num_items = len(items_for_letter)
        split_point = (num_items + 1) // 2
        left_index_items = items_for_letter[:split_point]
        right_index_items = items_for_letter[split_point:]

        for item in left_index_items:
            item_button = self._create_index_button(item)
            left_index_column.add_widget(item_button)

        for item in right_index_items:
            item_button = self._create_index_button(item)
            right_index_column.add_widget(item_button)

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
