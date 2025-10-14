from __future__ import annotations

import string
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_tags import (
    BARKS_TAG_GROUPS,
    BARKS_TAGGED_PAGES,
    BARKS_TAGGED_TITLES,
    TagGroups,
    Tags,
)
from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles
from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from loguru import logger

from barks_reader.random_title_images import ImageInfo
from barks_reader.reader_consts_and_types import CLOSE_TO_ZERO
from barks_reader.reader_utils import get_concat_page_nums_str

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.gridlayout import GridLayout
    from kivy.uix.widget import Widget


class IndexMenuButton(Button):
    """A custom button for the A-Z menu, styled in the .kv file."""

    is_selected = BooleanProperty(defaultvalue=False)


class IndexItemButton(Button):
    """A custom button for the index items, styled in the .kv file."""


class TitleItemButton(Button):
    """A custom button for title items, styled in the .kv file for press feedback."""


class Theme:
    """A central place for theme constants."""

    ROW_HEIGHT = dp(25)
    INDEX_ITEM_LEFT_PAD = dp(50)
    TAG_SUB_ITEM_LEFT_PAD = dp(50)
    TITLE_SUB_ITEM_LEFT_PAD = dp(80)

    MENU_TEXT = (0, 0, 0, 1)
    MENU_BG = (0, 0, 0, 0)
    MENU_BG_SELECTED = (0.0, 0.8, 0.0, 0.5)

    ITEM_TEXT = (0, 0, 0, 1)
    ITEM_BG = (0, 0, 0, 0)
    ITEM_BG_SELECTED = (0.8, 0.8, 0.0, 0.5)

    TITLE_TEXT = (0, 0, 0, 1)
    TITLE_BG = (0.95, 0.95, 0.95, 1)
    TITLE_BG_SELECTED = (0.85, 0.85, 0.85, 1)


class IndexItemType(Enum):
    TITLE = auto()
    TAG = auto()
    TAG_GROUP = auto()


@dataclass
class IndexItem:
    id: Titles | Tags | TagGroups
    item_type: IndexItemType
    display_text: str
    page_to_goto: str = ""


class IndexScreen(BoxLayout):
    """A widget that displays an A-Z index of comic titles and tags."""

    is_visible = BooleanProperty(defaultvalue=False)
    index_theme = ObjectProperty()
    _selected_letter_button = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        # Call the parent constructor FIRST to ensure self.ids is populated.
        super().__init__(**kwargs)

        self.index_theme = Theme()
        App.get_running_app().index_theme = self.index_theme  # Make theme accessible globally in kv

        self._alphabet_buttons: dict[str, Button] = {}
        self._open_tag_button: Button | None = None
        self._open_tag_item: IndexItem | None = None
        self._open_tag_widgets: list[Widget] = []
        self._item_index: dict[str, list[IndexItem]] = defaultdict(list)
        self.on_goto_title: Callable[[ImageInfo, str], None] | None = None

        self._build_index()
        self._populate_alphabet_menu()

    def on_opacity(self, _instance: IndexScreen, value: float) -> None:
        """When the widget becomes visible, automatically press the 'A' button."""
        if (value < CLOSE_TO_ZERO) or self._selected_letter_button:
            return

        # The index is being shown for the first time so default to 'A'.
        self.on_letter_press(self._alphabet_buttons["A"])

    def _build_index(self) -> None:
        """Build the index from Barks titles and tags."""
        logger.info("Building index...")

        # Add all comic titles
        for title in Titles:
            title_str = self._get_indexable_title(title)
            first_letter = title_str[0].upper()
            if "A" <= first_letter <= "Z":
                self._item_index[first_letter].append(
                    IndexItem(title, IndexItemType.TITLE, title_str)
                )

        # Add all tags
        for tag in Tags:
            tag_name = self._get_sortable_string(tag.value)
            first_letter = tag_name[0].upper()
            if "A" <= first_letter <= "Z":
                self._item_index[first_letter].append(IndexItem(tag, IndexItemType.TAG, tag_name))

        # Add all tag groups
        for tag_group in TagGroups:
            tag_group_name = tag_group.value
            first_letter = tag_group_name[0].upper()
            if "A" <= first_letter <= "Z":
                self._item_index[first_letter].append(
                    IndexItem(tag_group, IndexItemType.TAG_GROUP, tag_group_name)
                )

        # Sort items within each letter group
        for letter in self._item_index:
            self._item_index[letter].sort(key=lambda item: item.display_text)

        logger.success("Index build complete.")

    def _populate_alphabet_menu(self) -> None:
        """Create the A-Z buttons and add them to the GridLayout."""
        alphabet_layout: GridLayout = self.ids.alphabet_layout
        for letter in string.ascii_uppercase:
            button = IndexMenuButton(text=letter)
            button.bind(on_release=self.on_letter_press)
            self._alphabet_buttons[letter] = button
            alphabet_layout.add_widget(button)

    def on_letter_press(self, button: Button) -> None:
        """Handle a letter button press and display the corresponding index items."""
        letter = button.text
        logger.debug(f"Letter '{letter}' pressed.")

        # Let the .kv file handle the color changes by setting the property.
        if self._selected_letter_button and self._selected_letter_button != button:
            self._selected_letter_button.is_selected = False
        button.is_selected = True
        self._selected_letter_button = button

        left_index_column: BoxLayout = self.ids.left_column_layout
        right_index_column: BoxLayout = self.ids.right_column_layout
        left_index_column.clear_widgets()
        right_index_column.clear_widgets()

        self._open_tag_widgets.clear()
        self._open_tag_button = None

        items_for_letter = self._item_index.get(letter, [])
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

    @staticmethod
    def _get_no_items_button(letter: str) -> IndexItemButton:
        return IndexItemButton(
            text=f"*** No index items for '{letter}' ***",
            color=(1, 0, 0, 1),
        )

    def _create_index_button(self, item: IndexItem) -> IndexItemButton:
        """Create a configured IndexItemButton."""
        button = IndexItemButton(
            text=item.display_text,
            bold=item.item_type != IndexItemType.TITLE,
        )
        button.bind(
            on_release=lambda btn, bound_item=item: self.on_index_item_press(btn, bound_item)
        )
        return button

    def _add_sub_items(self, _dt: float) -> None:
        """Create and add the sub-item widgets to the layout."""
        item_id: Tags | TagGroups = self._open_tag_item.id
        logger.debug(f"Adding sub-items for {item_id.name}")

        sub_items_layout = self._get_sub_item_layout(item_id)
        self._insert_sub_items_layout(sub_items_layout)

    def _get_sub_item_layout(self, item_id: Tags | TagGroups) -> BoxLayout:
        # --- Determine what items to display in the new sub-list ---
        if self._open_tag_item.item_type == IndexItemType.TAG:
            assert isinstance(item_id, Tags)
            sub_items_to_display = [
                (title, *self._get_indexable_title_with_page_nums(title, item_id))
                for title in BARKS_TAGGED_TITLES[item_id]
            ]
            sub_items_to_display.sort(key=lambda t: t[2])
            sub_item_padding = self.index_theme.TITLE_SUB_ITEM_LEFT_PAD
            sub_item_type = IndexItemType.TITLE
        else:  # It's a TagGroup
            assert isinstance(item_id, TagGroups)
            sub_items_to_display = [(tag, "", tag.value) for tag in BARKS_TAG_GROUPS[item_id]]
            sub_item_padding = self.index_theme.TAG_SUB_ITEM_LEFT_PAD
            sub_item_type = IndexItemType.TAG

        # Now create the layout.
        sub_items_layout = BoxLayout(orientation="vertical", size_hint_y=None)
        sub_items_layout.bind(minimum_height=sub_items_layout.setter("height"))
        for sub_item_id, sub_item_page_to_goto, sub_item_text in sub_items_to_display:
            logger.info(f'For "{sub_item_text}", page to goto = {sub_item_page_to_goto}.')
            title_button = TitleItemButton(
                text=sub_item_text,
                padding=[sub_item_padding, 0, 0, 0],
            )
            sub_item = IndexItem(
                id=sub_item_id,
                item_type=sub_item_type,
                display_text=sub_item_text,
                page_to_goto=sub_item_page_to_goto,
            )
            title_button.bind(
                on_release=lambda btn, bound_item=sub_item: self.on_index_item_press(
                    btn, bound_item
                ),
            )
            sub_items_layout.add_widget(title_button)
            logger.debug(f'Added sub-item "{sub_item_text}".')

        return sub_items_layout

    def _insert_sub_items_layout(self, sub_items_layout: BoxLayout) -> None:
        button = self._open_tag_button
        target_layout = button.parent
        insertion_index = target_layout.children.index(button)
        target_layout.add_widget(sub_items_layout, index=insertion_index)
        sub_items_layout.owner_button = self._open_tag_button  # Tag the layout with its owner
        self._open_tag_widgets.append(sub_items_layout)

    def on_index_item_press(self, button: Button, item: IndexItem) -> None:
        """Handle a press on an individual index item."""
        logger.info(f"Index item pressed: {item}")

        # If a title is clicked, it's a terminal action. Handle it and do not change the UI.
        if item.item_type == IndexItemType.TITLE:
            self._handle_title(button, item)
            return

        # --- State Machine for Cleanup and Expansion ---
        is_collapse, level_of_click = self._get_level_of_click_for_collapse(button)
        if is_collapse:
            logger.debug("Action: Collapse")
            self._handle_collapse(level_of_click)
            return

        # --- This is an Expand action (top-level, drill-down, or lateral) ---
        logger.debug("Action: Expand/Switch")
        self._handle_expand_or_switch(button)

        # --- Handle the actual press ---
        self._handle_press(button, item)

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
        logger.debug(
            f"slice_index = {slice_index}, len(widgets_to_close) = {len(widgets_to_close)}."
        )
        if widgets_to_close:
            logger.debug(
                f"Closing {len(widgets_to_close)} widget(s) from level {slice_index} onwards."
            )
            for widget in widgets_to_close[:]:  # Iterate over a copy
                if widget.parent:
                    widget.parent.remove_widget(widget)
                self._open_tag_widgets.remove(widget)

    def _get_level_of_click_for_collapse(self, button: Button) -> tuple[bool, int]:
        is_collapse = False
        level_of_click = -1

        for i, container in enumerate(self._open_tag_widgets):
            if getattr(container, "owner_button", None) == button:
                is_collapse = True
                level_of_click = i
                break

        return is_collapse, level_of_click

    def _get_level_of_click_for_expand_or_switch(self, button: Button) -> int:
        level_of_click = -1

        if self._open_tag_widgets:
            for i, container in enumerate(self._open_tag_widgets):
                # The `walk()` method can be unreliable in dynamic layouts.
                current = button
                # Walk up a maximum of 20 parents as a safety measure against infinite loops.
                for _ in range(20):
                    if not current:
                        break
                    if current == container:
                        level_of_click = i
                        logger.debug(
                            f'Button "{button.text}" is a descendant of a container at level {i}.'
                        )
                        break
                    current = current.parent
                if level_of_click != -1:
                    break

        return level_of_click

    def _handle_press(self, button: Button, item: IndexItem) -> None:
        if item.item_type == IndexItemType.TAG:
            self._handle_tag(button, item)
        elif item.item_type == IndexItemType.TAG_GROUP:
            self._handle_tag_group(button, item)

    def _handle_title(self, button: Button, item: IndexItem) -> None:
        logger.info(f'Handling title: "{item.id.name}".')

        time_delay_to_title = 0.1  # seconds
        anim = Animation(
            background_color=self.index_theme.ITEM_BG_SELECTED, duration=time_delay_to_title
        )
        anim.start(button)

        assert type(item.id) is Titles
        image_info = ImageInfo(from_title=item.id, filename=None)

        def goto_title() -> None:
            anim.cancel(button)
            button.background_color = self.index_theme.ITEM_BG
            assert self.on_goto_title is not None
            self.on_goto_title(image_info, item.page_to_goto)

        Clock.schedule_once(lambda _dt: goto_title(), time_delay_to_title)

    def _handle_tag(self, button: Button, item: IndexItem) -> None:
        assert type(item.id) is Tags
        tag: Tags = item.id
        logger.info(f'Handling tag: "{tag.name}".')

        if tag not in BARKS_TAGGED_TITLES:
            logger.warning(f"No titles found for tag: {tag.name}")
            self._open_tag_button = None
            return

        self._open_tag_button = button
        self._open_tag_item = item
        Clock.schedule_once(self._add_sub_items, 0)

    def _handle_tag_group(self, button: Button, item: IndexItem) -> None:
        assert type(item.id) is TagGroups
        tag_group: TagGroups = item.id
        logger.info(f'Handling tag group: "{tag_group.name}".')

        if tag_group not in BARKS_TAG_GROUPS:
            logger.warning(f"No tags found for tag group: {tag_group.name}")
            self._open_tag_button = None
            return

        self._open_tag_button = button
        self._open_tag_item = item
        Clock.schedule_once(self._add_sub_items, 0)

    def _get_indexable_title_with_page_nums(self, title: Titles, tag: Tags) -> tuple[str, str]:
        """Return the first page to goto, and the sortable title with page numbers."""
        if (tag, title) not in BARKS_TAGGED_PAGES:
            return "", self._get_indexable_title(title)

        page_nums = BARKS_TAGGED_PAGES[(tag, title)]

        title_str = self._get_indexable_title(title)
        page_nums_str = get_concat_page_nums_str(page_nums)

        return page_nums[0], title_str + ", " + page_nums_str

    def _get_indexable_title(self, title: Titles) -> str:
        return self._get_sortable_string(BARKS_TITLES[title])

    @staticmethod
    def _get_sortable_string(text: str) -> str:
        text_upper = text.upper()
        if text_upper.startswith("THE "):
            return text[4:] + ", The"
        if text_upper.startswith("A "):
            return text[2:] + ", A"
        return text


# Load the associated .kv file when the module is imported.
Builder.load_file(str(Path(__file__).with_suffix(".kv")))
