from __future__ import annotations

from typing import TYPE_CHECKING, cast, override

from barks_fantagraphics.barks_tags import (
    BARKS_TAG_GROUPS,
    BARKS_TAGGED_TITLES,
    TagGroups,
    Tags,
)
from barks_fantagraphics.barks_titles import Titles
from comic_utils.timing import Timing
from kivy.graphics import Canvas, Color, Rectangle
from kivy.metrics import dp
from kivy.properties import (  # ty: ignore[unresolved-import]
    ColorProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.image_selector import ImageSelector
from barks_reader.core.index_headings import (
    tag_heading_markup,
)
from barks_reader.core.index_items import IndexItem
from barks_reader.core.main_index import (
    TitleHierarchy,
    build_main_index,
    index_item_markup,
    index_letter,
    tag_group_sub_items,
    tag_sub_items,
    tagged_pages,
    titles_for_letter,
)
from barks_reader.core.reader_file_paths_resolver import ReaderFilePathsResolver

from .index_screen import IndexItemButton, IndexScreen
from .panel_texture_loader import PanelTextureLoader

if TYPE_CHECKING:
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo

    from barks_reader.core.reader_settings import ReaderSettings

    from .font_manager import FontManager
    from .user_error_handler import UserErrorHandler

INDEX_ITEM_ROW_HEIGHT = dp(25)
INDEX_IMAGE_CHANGE_SECONDS = 5


class _MainIndexTitleItemButton(Button):
    background_color_normal = ColorProperty((0, 0, 0, 0))
    background_color_down = ColorProperty((0, 0, 0, 0))

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.border = (0, 0, 0, 0)
        self.background_color = (0, 0, 0, 0)
        self.size_hint = (0.90, None)
        self.halign = "left"
        self.valign = "middle"
        # A title too long for the row ends in an ellipsis: wrapped, it ran onto the next.
        self.shorten = True
        self.shorten_from = "right"

        self.bind(size=self.setter("text_size"))
        self.bind(pos=self.update_canvas, size=self.update_canvas, state=self.update_canvas)

    def update_canvas(self, *_args) -> None:  # noqa: ANN002
        canvas = cast("Canvas", self.canvas)
        canvas.before.clear()
        with canvas.before:
            Color(
                *(
                    self.background_color_down
                    if self.state == "down"
                    else self.background_color_normal
                )
            )
            # Draw a rectangle that respects the button's left padding.
            # The KV rule used 0.8 * padding[0]
            pad = 0.8 * self.padding[0]
            Rectangle(pos=(self.x + pad, self.y), size=(self.width - pad, self.height))


class MainIndexScreen(IndexScreen):
    """A widget that displays an A-Z index of comic titles and tags."""

    index_image_change_seconds = INDEX_IMAGE_CHANGE_SECONDS

    def __init__(
        self,
        reader_settings: ReaderSettings,
        font_manager: FontManager,
        user_error_handler: UserErrorHandler,
        **kwargs,  # noqa: ANN003
    ) -> None:
        # Call the parent constructor FIRST to ensure self.ids is populated.
        super().__init__(**kwargs)

        self._font_manager = font_manager
        self._user_error_handler = user_error_handler
        resolver = ReaderFilePathsResolver(reader_settings.file_paths)
        self._random_title_images = ImageSelector(resolver, reader_settings)
        self._texture_loader = PanelTextureLoader()
        self._cached_all_titles_for_letter: list[FantaComicBookInfo] = []
        self._cached_hierarchies: dict[Titles, TitleHierarchy] = {}

        self._open_tag_item: IndexItem | None = None
        # The shown letter page's tag entries, for a cross-reference to go to.
        self._tag_entries: dict[Tags, tuple[Button, IndexItem]] = {}

        self._item_index: dict[str, list[IndexItem]] = self._build_index()
        self._populate_alphabet_menu()

    @override
    def _get_items_for_letter(self, first_letter: str) -> list[IndexItem]:
        return self._item_index.get(first_letter, [])

    def _populate_index_for_letter(self, first_letter: str) -> None:
        self._tag_entries.clear()
        self._populate_index_grid(first_letter)

    @staticmethod
    def _build_index() -> dict[str, list[IndexItem]]:
        """Build the index from Barks titles and tags, timed for the log."""
        timing = Timing()
        logger.info("Building index...")
        index = build_main_index()
        logger.debug(
            log_markers.INDEX_BUILD_COMPLETE.format(elapsed=timing.get_elapsed_time_with_unit())
        )
        return index

    @override
    def _reset_background_image_caches(self) -> None:
        self._cached_all_titles_for_letter = []
        self._cached_hierarchies = {}

    @override
    def _next_background_image(self) -> None:
        if not self._cached_all_titles_for_letter:
            letter = self._selected_letter_button.text
            self._cached_all_titles_for_letter, self._cached_hierarchies = titles_for_letter(
                self._item_index[letter]
            )

        image_info = self._random_title_images.get_random_image(self._cached_all_titles_for_letter)
        self._set_background_image(image_info)

    @override
    def _get_background_title_str(self, title: Titles) -> str:
        return self._cached_hierarchies[title].get_title_with_hierarchy()

    @override
    def _create_index_button(self, item: IndexItem) -> IndexItemButton:
        """Create a configured IndexItemButton."""
        button = IndexItemButton(
            text=index_item_markup(item),
            markup=True,
            font_name=self._font_manager.main_index_item_font_name,
            font_size=self._font_manager.main_index_item_font_size,
            bold=type(item.id) is not Titles,
            italic=type(item.id) is Titles,
            height=INDEX_ITEM_ROW_HEIGHT,
        )
        button.bind(
            on_release=lambda btn, bound_item=item: self._on_index_item_press(btn, bound_item)
        )
        if isinstance(item.id, Tags) and not item.see:
            self._tag_entries[item.id] = (button, item)
        return button

    def _get_no_items_button(self, letter: str) -> IndexItemButton:
        return IndexItemButton(
            text=f"*** No index items for '{letter}' ***",
            color=self.index_theme.MENU_TEXT,
            font_name=self._font_manager.main_index_item_font_name,
            font_size=self._font_manager.main_index_item_font_size,
        )

    def _add_sub_items(self, _dt: float) -> None:
        """Create and add the sub-item widgets to the layout."""
        assert self._open_tag_item is not None
        item_id: Tags | TagGroups = self._open_tag_item.id
        logger.debug(f"Adding sub-items for {item_id.name}")

        sub_items_layout = self._get_sub_item_layout(item_id)
        self._insert_tag_sub_items_layout(sub_items_layout)
        logger.debug(
            log_markers.INDEX_SUB_ITEMS_ADDED.format(
                name=item_id.name, count=len(sub_items_layout.children)
            )
        )

    def _get_sub_item_layout(self, item_id: Tags | TagGroups) -> BoxLayout:
        # The new padding is the parent button's padding plus an indent step.
        assert self._open_tag_button is not None
        parent_padding = self._open_tag_button.padding[0]
        sub_item_padding = parent_padding + self.index_theme.SUB_ITEM_INDENT_STEP

        # --- Determine what items to display in the new sub-list ---
        if type(self._open_tag_item.id) is Tags:
            assert isinstance(item_id, Tags)
            use_italic = True
            sub_items_to_display: list[tuple[Titles | Tags, str, str]] = list(
                tag_sub_items(item_id)
            )
        else:  # It's a TagGroup
            assert isinstance(item_id, TagGroups)
            use_italic = False
            sub_items_to_display = list(tag_group_sub_items(item_id))

        # Now create the layout.
        sub_items_layout = BoxLayout(orientation="vertical", size_hint_y=None)
        sub_items_layout.bind(minimum_height=sub_items_layout.setter("height"))
        for (
            sub_item_id,
            sub_item_page_to_goto,
            sub_item_text,
        ) in sub_items_to_display:
            logger.info(f'For "{sub_item_text}", page to goto = {sub_item_page_to_goto}.')
            is_tag = isinstance(sub_item_id, Tags)
            title_button = _MainIndexTitleItemButton(
                text=tag_heading_markup(sub_item_id) if is_tag else sub_item_text,
                markup=is_tag,
                italic=use_italic,
                bold=not use_italic,  # not a title so must be TagGroup
                font_name=str(self._font_manager.index_title_item_font_name),
                font_size=self._font_manager.index_title_item_font_size,
                color=self.index_theme.TITLE_TEXT,
                background_color_normal=self.index_theme.TITLE_BG,
                background_color_down=self.index_theme.TITLE_BG_SELECTED,
                height=self.index_theme.ROW_HEIGHT,
                padding=[sub_item_padding, 0, 0, 0],
            )
            sub_item = IndexItem(
                id=sub_item_id,
                display_text=sub_item_text,
                page_to_goto=sub_item_page_to_goto,
                tagged_pages=tagged_pages(item_id, sub_item_id),
            )
            title_button.bind(
                on_release=lambda btn, bound_item=sub_item: self._on_index_item_press(
                    btn, bound_item
                ),
            )
            sub_items_layout.add_widget(title_button)
            logger.debug(f'Added sub-item "{sub_item_text}".')

        return sub_items_layout

    def _insert_tag_sub_items_layout(self, sub_items_layout: BoxLayout) -> None:
        button = self._open_tag_button
        assert button is not None
        target_layout = button.parent
        insertion_index = target_layout.children.index(button)
        target_layout.add_widget(sub_items_layout, index=insertion_index)
        sub_items_layout.owner_button = self._open_tag_button  # Tag the layout with its owner
        self._open_tag_widgets.append(sub_items_layout)

    @override
    def _handle_terminal_item(self, button: Button, item: IndexItem) -> bool:
        # A title is a terminal action: handle it and leave the UI alone.
        if type(item.id) is Titles:
            self._handle_title(button, item)
            return True
        if item.see:
            self._follow_see_reference(item)
            return True
        return False

    def _follow_see_reference(self, item: IndexItem) -> None:
        """Go to a cross-reference's target entry, on its letter page, and open it.

        A target on the page already shown is opened in place: the page is not rebuilt
        (which would close every open tag and scroll to the top), and a target already
        open stays open.
        """
        assert isinstance(item.id, Tags)
        logger.info(log_markers.INDEX_SEE_FOLLOWED.format(name=item.display_text, see=item.see))
        letter = index_letter(item.see)
        if self._selected_letter_button is None or self._selected_letter_button.text != letter:
            self.on_letter_press(self._alphabet_buttons[letter])
        if item.id not in self._tag_entries:
            logger.warning(f'No entry "{item.see}" for the cross-reference "{item.display_text}".')
            return
        target_button, target_item = self._tag_entries[item.id]
        self._hand_focus_to(target_button)
        is_open, _ = self._get_level_of_click_for_collapse(target_button)
        if is_open:
            logger.debug(f'"{item.see}" is open already.')
            return
        self._on_index_item_press(target_button, target_item)

    @override
    def _handle_item_expansion(self, button: Button, item: IndexItem) -> None:
        if type(item.id) is Tags:
            self._handle_tag(button, item)
        elif type(item.id) is TagGroups:
            self._handle_tag_group(button, item)

    def _handle_tag(self, button: Button, item: IndexItem) -> None:
        assert type(item.id) is Tags
        tag: Tags = item.id
        logger.info(log_markers.INDEX_HANDLING_TAG.format(name=tag.name))

        if tag not in BARKS_TAGGED_TITLES:
            logger.warning(f"No titles found for tag: {tag.name}")
            self._open_tag_button = None
            return

        self._open_tag_button = button
        self._open_tag_item = item
        self._schedule_sub_items(self._add_sub_items)

    def _handle_tag_group(self, button: Button, item: IndexItem) -> None:
        assert type(item.id) is TagGroups
        tag_group: TagGroups = item.id
        logger.info(log_markers.INDEX_HANDLING_TAG_GROUP.format(name=tag_group.name))

        if tag_group not in BARKS_TAG_GROUPS:
            logger.warning(f"No tags found for tag group: {tag_group.name}")
            self._open_tag_button = None
            return

        self._open_tag_button = button
        self._open_tag_item = item
        self._schedule_sub_items(self._add_sub_items)
