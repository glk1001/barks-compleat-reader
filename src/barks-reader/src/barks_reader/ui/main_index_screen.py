from __future__ import annotations

from typing import TYPE_CHECKING, override

from barks_fantagraphics.barks_tags import (
    BARKS_TAG_GROUPS,
    BARKS_TAGGED_TITLES,
    TagGroups,
    Tags,
)
from barks_fantagraphics.barks_titles import Titles
from comic_utils.timing import Timing
from kivy.clock import Clock
from kivy.metrics import dp
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.image_selector import ImageSelector
from barks_reader.core.main_index import (
    MAIN_INDEX_LETTERS,
    TitleHierarchy,
    build_main_index,
    index_item_markup,
    index_letter,
    sub_index_rows,
    titles_for_letter,
)
from barks_reader.core.reader_file_paths_resolver import ReaderFilePathsResolver

from .index_screen import IndexItemButton, IndexScreen, IndexTitleItemButton
from .panel_texture_loader import PanelTextureLoader

if TYPE_CHECKING:
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button

    from barks_reader.core.index_items import IndexItem
    from barks_reader.core.reader_settings import ReaderSettings

    from .font_manager import FontManager
    from .user_error_handler import UserErrorHandler

INDEX_ITEM_ROW_HEIGHT = dp(25)
INDEX_IMAGE_CHANGE_SECONDS = 5
# How many frames a cross-reference's target waits for its page's layout before it opens.
_SEE_TARGET_LAYOUT_FRAMES = 30


class MainIndexScreen(IndexScreen):
    """A widget that displays an A-Z index of comic titles and tags."""

    index_image_change_seconds = INDEX_IMAGE_CHANGE_SECONDS

    def __init__(
        self,
        reader_settings: ReaderSettings,
        font_manager: FontManager,
        user_error_handler: UserErrorHandler,
        **kwargs: object,
    ) -> None:
        # Call the parent constructor FIRST to ensure self.ids is populated.
        super().__init__(**kwargs)

        self._font_manager = font_manager
        self._user_error_handler = user_error_handler
        resolver = ReaderFilePathsResolver(reader_settings.file_paths)
        # Its own selector, not the main screen's `image_selector`: the two remember
        # what they last showed apart, so a background here can repeat a view's image.
        # Sharing the one would change which backgrounds come up.
        self._random_title_images = ImageSelector(resolver, reader_settings)
        self._texture_loader = PanelTextureLoader()
        self._cached_all_titles_for_letter: list[FantaComicBookInfo] = []
        self._cached_hierarchies: dict[Titles, TitleHierarchy] = {}

        # The shown letter page's tag entries, for a cross-reference to go to.
        self._tag_entries: dict[Tags, tuple[Button, IndexItem]] = {}

        self._item_index: dict[str, list[IndexItem]] = self._build_index()
        self._populate_alphabet_menu()

    @override
    def _get_alphabet_letters(self) -> str:
        """Return the letter pages the index can have: no apostrophe, which none is filed under."""
        return MAIN_INDEX_LETTERS

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
                self._get_items_for_letter(letter)
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

    @override
    def _index_item_font(self) -> tuple[str, float]:
        return (
            self._font_manager.main_index_item_font_name,
            self._font_manager.main_index_item_font_size,
        )

    @override
    def _sub_items_added(self, item: IndexItem, sub_items_layout: BoxLayout) -> None:
        assert isinstance(item.id, Tags | TagGroups)
        logger.debug(
            log_markers.INDEX_SUB_ITEMS_ADDED.format(
                name=item.id.name, count=len(sub_items_layout.children)
            )
        )

    @override
    def _get_sub_items_layout(self, item: IndexItem) -> BoxLayout:
        item_id = item.id
        assert isinstance(item_id, Tags | TagGroups)
        logger.debug(f"Adding sub-items for {item_id.name}")
        # The new padding is the parent button's padding plus an indent step.
        assert self._open_tag_button is not None
        parent_padding = self._open_tag_button.padding[0]
        sub_item_padding = parent_padding + self.index_theme.SUB_ITEM_INDENT_STEP

        sub_items_layout = self._new_sub_items_layout()
        for row in sub_index_rows(item_id):
            title_button = IndexTitleItemButton(
                full_text=row.text,
                markup=row.markup,
                size_hint=(0.90, None),
                italic=row.italic,
                bold=not row.italic,  # not a title so must be a tag group's tag
                font_name=str(self._font_manager.index_title_item_font_name),
                font_size=self._font_manager.index_title_item_font_size,
                color=self.index_theme.TITLE_TEXT,
                background_color_normal=self.index_theme.TITLE_BG,
                background_color_down=self.index_theme.TITLE_BG_SELECTED,
                height=self.index_theme.ROW_HEIGHT,
                padding=[sub_item_padding, 0, 0, 0],
            )
            sub_item = row.item
            title_button.bind(
                on_release=lambda btn, bound_item=sub_item: self._on_index_item_press(
                    btn, bound_item
                ),
            )
            sub_items_layout.add_widget(title_button)
            # One line a row, at debug: an info line beside it doubled the log written
            # in the frame a tag of a few hundred titles opens in.
            logger.debug(
                f'Added sub-item "{sub_item.display_text}", page to goto = {sub_item.page_to_goto}.'
            )

        return sub_items_layout

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
        open stays open. One on another page is opened a frame on, once its page is
        laid out (see `_open_see_target`).
        """
        assert isinstance(item.id, Tags)
        logger.info(log_markers.INDEX_SEE_FOLLOWED.format(name=item.display_text, see=item.see))
        letter = index_letter(item.see)
        on_another_page = (
            self._selected_letter_button is None or self._selected_letter_button.text != letter
        )
        if on_another_page:
            self.on_letter_press(self._alphabet_buttons[letter])
        if item.id not in self._tag_entries:
            logger.warning(f'No entry "{item.see}" for the cross-reference "{item.display_text}".')
            return
        target_button, target_item = self._tag_entries[item.id]
        self._hand_focus_to(target_button)
        if on_another_page:
            grid_version = self._grid_version
            Clock.schedule_once(
                lambda _dt: self._open_see_target(target_button, target_item, grid_version), 0
            )
            return
        is_open, _ = self._get_level_of_click_for_collapse(target_button)
        if is_open:
            logger.debug(f'"{item.see}" is open already.')
            return
        self._on_index_item_press(target_button, target_item)

    def _open_see_target(
        self,
        button: Button,
        item: IndexItem,
        grid_version: int,
        frames_left: int = _SEE_TARGET_LAYOUT_FRAMES,
    ) -> None:
        """Open a cross-reference's target on the page just shown for it, in view.

        Opened in the frame its page was built, the target's row was not laid out yet:
        the pin that holds a row still as it opens measured it where it was not, and the
        heading and its first titles ended above the view. So this waits for the layout,
        then brings the target into view before it is pressed, a page being taller than
        the view and the target anywhere down it.

        The wait is `frames_left` frames at most: a layout that stays asked for (a
        screen hidden meanwhile) had this called again every frame, with no end.
        """
        if self._grid_version != grid_version or button.parent is None:
            return  # another page was shown in the frames between
        if self._is_open_owner(button):
            # Opened by hand in the frames between: pressed again, it closed.
            logger.debug(f'"{item.display_text}" is open already.')
            return
        scroll_view = self.ids.index_scroll_view
        content = scroll_view.children[0]
        if frames_left > 0 and any(
            layout._trigger_layout.is_triggered  # noqa: SLF001
            for layout in (content, *self._get_col_layouts())
        ):
            Clock.schedule_once(
                lambda _dt: self._open_see_target(button, item, grid_version, frames_left - 1), 0
            )
            return
        if content.height > scroll_view.height:
            scroll_view.scroll_to(button, animate=False)
            # Now, not on the next frame: the pin measures where the row is on screen.
            scroll_view.update_from_scroll()
        self._on_index_item_press(button, item)

    @override
    def _handle_item_expansion(self, button: Button, item: IndexItem) -> None:
        # A tag opens onto its titles, a tag group onto its tags: the one path, told
        # apart by the line logged and by where what the entry holds is looked up.
        if type(item.id) is Tags:
            marker, holds, has_any = (
                log_markers.INDEX_HANDLING_TAG,
                "titles",
                item.id in BARKS_TAGGED_TITLES,
            )
        elif type(item.id) is TagGroups:
            marker, holds, has_any = (
                log_markers.INDEX_HANDLING_TAG_GROUP,
                "tags",
                item.id in BARKS_TAG_GROUPS,
            )
        else:
            return  # a title: nothing under it to open
        logger.info(marker.format(name=item.id.name))

        if not has_any:
            kind = "tag" if holds == "titles" else "tag group"
            logger.warning(f"No {holds} found for {kind}: {item.id.name}")
            self._open_tag_button = None
            return

        self._open_sub_items(button, item)
