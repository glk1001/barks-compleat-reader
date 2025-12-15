from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from barks_fantagraphics.barks_titles import BARKS_TITLE_DICT, BARKS_TITLES, Titles
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from barks_fantagraphics.whoosh_search_engine import SearchEngine
from comic_utils.timing import Timing
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from loguru import logger

from barks_reader.index_screen import (
    IndexItemButton,
    IndexMenuButton,
    IndexScreen,
    TitleItemButton,
)
from barks_reader.panel_image_loader import PanelImageLoader
from barks_reader.random_title_images import ImageInfo, RandomTitleImages
from barks_reader.reader_utils import get_concat_page_nums_str

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.whoosh_search_engine import TitleDict

    # noinspection PyProtectedMember
    from kivy.core.image import Texture
    from kivy.uix.button import Button
    from kivy.uix.gridlayout import GridLayout

    from barks_reader.reader_settings import ReaderSettings

INDEX_ITEM_ROW_HEIGHT = dp(21)
INDEX_IMAGE_CHANGE_SECONDS = 15


@dataclass
class IndexItem:
    id: str | Titles
    display_text: str
    page_to_goto: str = ""


class SpeechIndexScreen(IndexScreen):
    """A widget that displays an A-Z index of speech bubble texts."""

    _selected_prefix_button = ObjectProperty(None, allownone=True)
    is_visible = BooleanProperty(defaultvalue=False)
    image_texture = ObjectProperty()
    current_title_str = StringProperty()

    def __init__(self, reader_settings: ReaderSettings, **kwargs) -> None:  # noqa: ANN003
        # Call the parent constructor FIRST to ensure self.ids is populated.
        super().__init__(**kwargs)

        self._whoosh_indexer = SearchEngine(
            reader_settings.sys_file_paths.get_barks_reader_indexes_dir()
        )
        self._random_title_images = RandomTitleImages(reader_settings)
        self._image_loader = PanelImageLoader(reader_settings.file_paths.barks_panels_are_encrypted)
        self._index_image_change_event = None
        self._found_words_cache: dict[str, TitleDict] = {}

        self._open_tag_item: IndexItem | None = None
        self._item_index: dict[str, list[IndexItem]] = defaultdict(list)
        self.on_goto_title: Callable[[ImageInfo, str], None] | None = None

        self._cleaned_alpha_split_unstemmed_terms = (
            self._whoosh_indexer.get_cleaned_alpha_split_unstemmed_terms()
        )
        self._prefix_buttons: dict[str, Button] = {}

        self._populate_alphabet_menu()

    def _populate_index_for_letter(self, first_letter: str) -> None:
        self._populate_top_alphabet_split_menu(first_letter)
        self._populate_index_grid(first_letter)

    def _populate_top_alphabet_split_menu(self, first_letter: str) -> None:
        """Create the top sub alphabet split buttons across the top."""
        first_letter_split_terms = self._cleaned_alpha_split_unstemmed_terms[first_letter.lower()]

        alphabet_top_split_layout: GridLayout = self.ids.alphabet_top_split_layout
        alphabet_top_split_layout.clear_widgets()

        for prefix in first_letter_split_terms:
            button = IndexMenuButton(text=prefix)
            button.bind(on_release=self.on_letter_prefix_press)
            self._prefix_buttons[prefix] = button
            alphabet_top_split_layout.add_widget(button)

        first_prefix = next(iter(first_letter_split_terms))
        self.on_letter_prefix_press(self._prefix_buttons[first_prefix])

    def on_letter_prefix_press(self, button: Button) -> None:
        prefix = button.text
        logger.debug(f"Pressed prefix button: '{prefix}.")

        if self._selected_prefix_button and self._selected_prefix_button != button:
            self._selected_prefix_button.is_selected = False
        button.is_selected = True
        self._selected_prefix_button = button

        first_letter = "0" if "0" <= prefix <= "9" else prefix[0].upper()
        terms = self._cleaned_alpha_split_unstemmed_terms[first_letter.lower()][prefix]
        self._item_index[first_letter] = [IndexItem(t, t) for t in terms]

        self._populate_index_grid(first_letter)

    @override
    def _get_items_for_letter(self, first_letter: str) -> list:
        return self._item_index.get(first_letter, [])

    @override
    def _new_index_image(self) -> None:
        self._cancel_index_image_change_events()

        self._next_background_image()

        self._index_image_change_event = Clock.schedule_interval(
            lambda _dt: self._next_background_image(), INDEX_IMAGE_CHANGE_SECONDS
        )

    def _cancel_index_image_change_events(self) -> None:
        if self._index_image_change_event:
            self._index_image_change_event.cancel()
            self._index_image_change_event = None

    # noinspection PyNoneFunctionAssignment
    def _next_background_image(self) -> None:
        first_letter = self._selected_letter_button.text
        index_terms = self._item_index[first_letter]
        if not index_terms:
            return
        rand_term = random.choice(index_terms).id

        if rand_term in self._found_words_cache:
            found = self._found_words_cache[rand_term]
        else:
            found = self._whoosh_indexer.find_unstemmed_words(rand_term)
            self._found_words_cache[rand_term] = found

        found_titles = [ALL_FANTA_COMIC_BOOK_INFO[title_str] for title_str in found]
        image_info = self._random_title_images.get_random_image(found_titles)

        # TODO: Get rid of this hack!!
        if image_info.from_title is None or image_info.from_title == Titles.GOOD_NEIGHBORS:
            self.current_title_str = ""
        else:
            self.current_title_str = BARKS_TITLES[image_info.from_title]

        timing = Timing()

        def on_ready(tex: Texture | None, err: Exception) -> None:
            if err:
                raise RuntimeError(err)

            self.image_texture = tex
            logger.debug(f"Time taken to set index image: {timing.get_elapsed_time_with_unit()}.")

        # noinspection LongLine
        self._image_loader.load_texture(image_info.filename, on_ready)  # ty: ignore[invalid-argument-type]

    @override
    def _create_index_button(self, item: IndexItem) -> IndexItemButton:
        """Create a configured IndexItemButton."""
        button = IndexItemButton(
            text=item.display_text,
            bold=type(item.id) is not Titles,
            height=INDEX_ITEM_ROW_HEIGHT,
        )
        button.bind(
            on_release=lambda btn, bound_item=item: self._on_index_item_press(btn, bound_item)
        )
        return button

    def _get_no_items_button(self, letter: str) -> IndexItemButton:
        return IndexItemButton(
            text=f"*** No index items for '{letter}' ***", color=self.index_theme.MENU_TEXT
        )

    def _add_sub_items(self, _dt: float) -> None:
        """Create and add the sub-item widgets to the layout."""
        assert type(self._open_tag_item.id) is str
        item_id: str = self._open_tag_item.id
        logger.debug(f"Adding sub-items for {item_id}")

        sub_items_layout = self._get_sub_item_layout(item_id)
        self._insert_sub_items_layout(sub_items_layout)

    def _get_sub_item_layout(self, item_id: str) -> BoxLayout:
        # The new padding is the parent button's padding plus an indent step.
        parent_padding = self._open_tag_button.padding[0]
        sub_item_padding = parent_padding + self.index_theme.SUB_ITEM_INDENT_STEP

        # --- Determine what items to display in the new sub-list ---
        found = (
            self._found_words_cache[item_id]
            if item_id in self._found_words_cache
            else self._whoosh_indexer.find_unstemmed_words(item_id)
        )
        sub_items_to_display = []
        for comic_title, title_info in found.items():
            title = BARKS_TITLE_DICT[comic_title]
            page_nums = [page[1] for page in title_info.pages]
            sub_items_to_display.append(
                (title, *self._get_indexable_title_with_page_nums(title, page_nums))
            )

        sub_items_to_display.sort(key=lambda t: t[2])

        # Now create the layout.
        sub_items_layout = BoxLayout(orientation="vertical", size_hint_y=None)
        sub_items_layout.bind(minimum_height=sub_items_layout.setter("height"))
        for (
            sub_item_id,
            sub_item_page_to_goto,
            sub_item_text,
        ) in sub_items_to_display:  # ty: ignore[invalid-assignment]
            logger.info(f'For "{sub_item_text}", page to goto = {sub_item_page_to_goto}.')
            title_button = TitleItemButton(
                text=sub_item_text,
                padding=[sub_item_padding, 0, 0, 0],
            )
            sub_item = IndexItem(
                id=sub_item_id,
                display_text=sub_item_text,
                page_to_goto=sub_item_page_to_goto,
            )
            title_button.bind(
                on_release=lambda btn, bound_item=sub_item: self._handle_title(btn, bound_item),
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

    def _on_index_item_press(self, button: Button, item: IndexItem) -> None:
        """Handle a press on an individual index item."""
        logger.info(f"Index item pressed: '{item}'.")

        assert type(item.id) is not Titles

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
        logger.info(f'Handling term: "{item.id}".')

        self._open_tag_button = button
        self._open_tag_item = item
        Clock.schedule_once(self._add_sub_items, 0)

    def _handle_title(self, button: Button, item: IndexItem) -> None:
        assert type(item.id) is Titles
        logger.info(f'Handling title: "{item.id.name}".')
        image_info = ImageInfo(from_title=item.id, filename=None)

        def set_background_color_to_selected() -> None:
            button.background_color = self.index_theme.ITEM_BG_SELECTED

        def goto_title() -> None:
            assert self.on_goto_title is not None
            self.on_goto_title(image_info, item.page_to_goto)

        def reset_background_color() -> None:
            button.background_color = self.index_theme.ITEM_BG

        Clock.schedule_once(lambda _dt: set_background_color_to_selected(), 0)
        Clock.schedule_once(lambda _dt: goto_title(), 0.01)
        Clock.schedule_once(lambda _dt: reset_background_color(), 0.1)

    def _get_indexable_title_with_page_nums(
        self, title: Titles, page_nums: list[str]
    ) -> tuple[str, str]:
        title_str = self._get_indexable_title(title)
        page_nums_str = get_concat_page_nums_str(page_nums)

        return page_nums[0], title_str + ", " + page_nums_str
