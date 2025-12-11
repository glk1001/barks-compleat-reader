from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from barks_fantagraphics.barks_tags import (
    BARKS_TAG_GROUPS,
    BARKS_TAGGED_PAGES,
    BARKS_TAGGED_TITLES,
    TagGroups,
    Tags,
    get_all_tags_in_tag_group,
    get_tag_titles,
)
from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO, FantaComicBookInfo
from comic_utils.timing import Timing
from kivy.app import App
from kivy.clock import Clock
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from loguru import logger

from barks_reader.index_screen import (
    IndexItemButton,
    IndexScreen,
    Theme,
    TitleItemButton,
)
from barks_reader.panel_image_loader import PanelImageLoader
from barks_reader.random_title_images import ImageInfo, RandomTitleImages
from barks_reader.reader_utils import get_concat_page_nums_str

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.core.image import Texture
    from kivy.uix.button import Button

    from barks_reader.reader_settings import ReaderSettings


@dataclass()
class TitleHierarchy:
    tag_group: TagGroups | None
    tag: Tags | None
    title: Titles | None

    def get_title_with_hierarchy(self) -> str:
        assert self.title is not None
        title_str = BARKS_TITLES[self.title]

        if not self.tag_group and not self.tag:
            return title_str

        title_str += " ("
        if self.tag_group:
            title_str += self.tag_group.value + "/"
        if self.tag:
            title_str += self.tag.value
        title_str += ") "

        return title_str


@dataclass
class IndexItem:
    id: Titles | Tags | TagGroups
    display_text: str
    page_to_goto: str = ""


class MainIndexScreen(IndexScreen):
    """A widget that displays an A-Z index of comic titles and tags."""

    is_visible = BooleanProperty(defaultvalue=False)
    index_theme = ObjectProperty()
    image_texture = ObjectProperty()
    current_title_str = StringProperty()

    def __init__(self, reader_settings: ReaderSettings, **kwargs) -> None:  # noqa: ANN003
        # Call the parent constructor FIRST to ensure self.ids is populated.
        super().__init__(**kwargs)

        self._random_title_images = RandomTitleImages(reader_settings)
        self._image_loader = PanelImageLoader(reader_settings.file_paths.barks_panels_are_encrypted)
        self._index_image_change_event = None
        self._cached_all_titles_for_letter: list[FantaComicBookInfo] = []
        self._cached_hierarchies: dict[Titles, TitleHierarchy] = {}

        self.index_theme = Theme()
        App.get_running_app().index_theme = self.index_theme  # Make theme accessible globally in kv

        self._open_tag_item: IndexItem | None = None
        self._item_index: dict[str, list[IndexItem]] = defaultdict(list)
        self.on_goto_title: Callable[[ImageInfo, str], None] | None = None

        self._build_index()
        self._populate_alphabet_menu()

    def _build_index(self) -> None:
        """Build the index from Barks titles and tags."""
        timing = Timing()
        logger.info("Building index...")

        # Add all comic titles
        for title in Titles:
            title_str = self._get_indexable_title(title)
            first_letter = title_str[0].upper()
            assert "A" <= first_letter <= "Z"
            self._item_index[first_letter].append(IndexItem(title, title_str))

        # Add all tags
        for tag in Tags:
            tag_name = self._get_sortable_string(tag.value)
            first_letter = tag_name[0].upper()
            assert "A" <= first_letter <= "Z"
            self._item_index[first_letter].append(IndexItem(tag, tag_name))

        # Add all tag groups
        for tag_group in TagGroups:
            tag_group_name = tag_group.value
            first_letter = tag_group_name[0].upper()
            assert "A" <= first_letter <= "Z"
            self._item_index[first_letter].append(IndexItem(tag_group, tag_group_name))

        # Sort items within each letter group
        for letter in self._item_index:
            self._item_index[letter].sort(key=lambda item: item.display_text.lower())

        logger.debug(f"Index build complete (in {timing.get_elapsed_time_with_unit()}).")

    @override
    def _new_index_image(self) -> None:
        self._cached_all_titles_for_letter = []
        self._cached_hierarchies = {}

        self._cancel_index_image_change_events()

        self._next_background_image()

        self._index_image_change_event = Clock.schedule_interval(
            lambda _dt: self._next_background_image(), self.index_theme.INDEX_IMAGE_CHANGE_SECONDS
        )

    def _cancel_index_image_change_events(self) -> None:
        if self._index_image_change_event:
            self._index_image_change_event.cancel()
            self._index_image_change_event = None

    # noinspection PyNoneFunctionAssignment
    def _next_background_image(self) -> None:
        if not self._cached_all_titles_for_letter:
            letter = self._selected_letter_button.text
            self._cached_all_titles_for_letter, self._cached_hierarchies = (
                self._get_all_titles_for_letter(letter)
            )

        image_info = self._random_title_images.get_random_image(self._cached_all_titles_for_letter)
        # TODO: Get rid of this hack!!
        if image_info.from_title is None or image_info.from_title == Titles.GOOD_NEIGHBORS:
            self.current_title_str = ""
        else:
            hierarchy = self._cached_hierarchies[image_info.from_title]
            self.current_title_str = hierarchy.get_title_with_hierarchy()

        timing = Timing()

        def on_ready(tex: Texture | None, err: Exception) -> None:
            if err:
                raise RuntimeError(err)

            self.image_texture = tex
            logger.debug(f"Time taken to set index image: {timing.get_elapsed_time_with_unit()}.")

        # noinspection LongLine
        self._image_loader.load_texture(image_info.filename, on_ready)  # ty: ignore[invalid-argument-type]

    def _get_all_titles_for_letter(
        self, letter: str
    ) -> tuple[list[FantaComicBookInfo], dict[Titles, TitleHierarchy]]:
        """Get all unique titles for a given letter, from direct titles and from tags."""
        hierarchies: dict[Titles, TitleHierarchy] = {}
        all_titles: set[Titles] = set()

        for index_item in self._item_index[letter]:
            self._update_all_titles_and_hierarchies(index_item.id, all_titles, hierarchies)

        return [
            ALL_FANTA_COMIC_BOOK_INFO[BARKS_TITLES[title_id]]
            for title_id in all_titles
            if BARKS_TITLES[title_id] in ALL_FANTA_COMIC_BOOK_INFO
        ], hierarchies

    def _update_all_titles_and_hierarchies(
        self,
        item_id: Titles | Tags | TagGroups,
        all_titles: set[Titles],
        hierarchies: dict[Titles, TitleHierarchy],
        parent_tag_group: TagGroups | None = None,
    ) -> None:
        if type(item_id) is Titles:
            all_titles.add(item_id)
            hierarchies[item_id] = TitleHierarchy(None, None, item_id)
        elif type(item_id) is Tags:
            tag_titles = get_tag_titles(item_id)
            for title in tag_titles:
                hierarchies[title] = TitleHierarchy(parent_tag_group, item_id, title)
            all_titles.update(tag_titles)
        elif type(item_id) is TagGroups:
            for tag in BARKS_TAG_GROUPS[item_id]:
                if type(tag) is TagGroups:
                    self._update_all_titles_and_hierarchies(tag, all_titles, hierarchies)
                else:
                    self._update_all_titles_and_hierarchies(tag, all_titles, hierarchies, item_id)

    @override
    def _create_index_button(self, item: IndexItem) -> IndexItemButton:
        """Create a configured IndexItemButton."""
        button = IndexItemButton(
            text=item.display_text,
            bold=type(item.id) is not Titles,
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
        item_id: Tags | TagGroups = self._open_tag_item.id
        logger.debug(f"Adding sub-items for {item_id.name}")

        sub_items_layout = self._get_sub_item_layout(item_id)
        self._insert_sub_items_layout(sub_items_layout)

    def _get_sub_item_layout(self, item_id: Tags | TagGroups) -> BoxLayout:
        # The new padding is the parent button's padding plus an indent step.
        parent_padding = self._open_tag_button.padding[0]
        sub_item_padding = parent_padding + self.index_theme.SUB_ITEM_INDENT_STEP

        # --- Determine what items to display in the new sub-list ---
        if type(self._open_tag_item.id) is Tags:
            assert isinstance(item_id, Tags)
            sub_items_to_display = [
                (
                    title,
                    *self._get_indexable_title_with_page_nums(title, item_id),
                )  # ty: ignore[invalid-assignment]
                for title in BARKS_TAGGED_TITLES[item_id]
            ]
        else:  # It's a TagGroup
            assert isinstance(item_id, TagGroups)
            sub_items_to_display = [
                (tag, "", tag.value) for tag in get_all_tags_in_tag_group(item_id)
            ]

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
                on_release=lambda btn, bound_item=sub_item: self._on_index_item_press(
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

    def _on_index_item_press(self, button: Button, item: IndexItem) -> None:
        """Handle a press on an individual index item."""
        logger.info(f"Index item pressed: {item}")

        # If a title is clicked, it's a terminal action. Handle it and do not change the UI.
        if type(item.id) is Titles:
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
        if type(item.id) is Tags:
            self._handle_tag(button, item)
        elif type(item.id) is TagGroups:
            self._handle_tag_group(button, item)

    def _handle_title(self, button: Button, item: IndexItem) -> None:
        logger.info(f'Handling title: "{item.id.name}".')

        assert type(item.id) is Titles
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
