from __future__ import annotations

import random
from collections import defaultdict
from functools import cached_property
from itertools import islice
from typing import TYPE_CHECKING, override

from barks_fantagraphics.alpha_split import MAX_PREFIX_BUTTONS_PER_LETTER
from barks_fantagraphics.barks_titles import STR_TITLE_TO_ENUM, Titles
from barks_fantagraphics.comic_search import ComicSearch
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import (  # ty: ignore[import-not-found]
    ObjectProperty,
)
from kivy.uix.boxlayout import BoxLayout
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.image_selector import ImageInfo, ImageSelector
from barks_reader.core.index_items import (
    IndexItem,
    context_entities,
    title_row_item,
    word_index_items,
)
from barks_reader.core.index_text import (
    MAX_TITLE_AND_PAGES_LEN,
    stacked_prefix_label,
)
from barks_reader.core.keys import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    KEY_UP,
    is_escape_key,
)
from barks_reader.core.reader_file_paths_resolver import ReaderFilePathsResolver
from barks_reader.core.speech_hits import SpeechHitRow, comic_pages, speech_hit_rows

from .index_screen import (
    INDEX_NAV_FOCUS_GROUP,
    IndexItemButton,
    IndexPrefixButton,
    IndexScreen,
    IndexTitleItemButton,
    TitleShowSpeechButton,
    _IndexNavPanel,
    create_speech_bubble_popup,
    move_selection,
    show_speech_bubbles_popup,
)
from .panel_texture_loader import PanelTextureLoader
from .reader_keyboard_nav import clear_focus_in_list, draw_focus_highlight

if TYPE_CHECKING:
    from barks_fantagraphics.whoosh_search_engine import TitleDict, TitleInfo
    from kivy.uix.button import Button
    from kivy.uix.gridlayout import GridLayout

    from barks_reader.core.reader_settings import ReaderSettings

    from .font_manager import FontManager
    from .user_error_handler import UserErrorHandler

INDEX_ITEM_ROW_HEIGHT = dp(21)
INDEX_IMAGE_CHANGE_SECONDS = 15

SAVED_NODE_STATE_PREFIX_KEY = "prefix"

# Search results are cached so re-opening a word is instant, but each entry can hold
# every speech bubble of every matching title, so the caches are capped rather than
# left to grow for the lifetime of the app.
_SEARCH_CACHE_MAX_ENTRIES = 64


def _store_bounded[K, V](cache: dict[K, V], key: K, value: V) -> None:
    """Insert into a bounded cache, evicting the oldest entry when it is full."""
    if len(cache) >= _SEARCH_CACHE_MAX_ENTRIES:
        del cache[next(iter(cache))]
    cache[key] = value


class SpeechSubItemsIndexScreen(IndexScreen):
    """An index whose items expand into the titles and speech bubbles they appear in.

    Holds everything the word index and the entity indexes share: the search engine,
    the three-column grid, the title sub-item rows with their speech buttons, and the
    speech-bubble popup. It has the base ALPHABET -> ITEMS navigation; the prefix bar
    is added by ``SpeechIndexScreen`` alone.
    """

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
        self.num_columns = 3

        self._font_manager = font_manager
        self._user_error_handler = user_error_handler
        self._search = ComicSearch(reader_settings.sys_file_paths.get_barks_reader_indexes_dir())
        resolver = ReaderFilePathsResolver(reader_settings.file_paths)
        self._random_title_images = ImageSelector(resolver, reader_settings)
        self._texture_loader = PanelTextureLoader()
        self._found_words_cache: dict[IndexItem, TitleDict] = {}
        # The background image only needs to know *which* titles match, so this cache
        # holds title strings rather than full TitleDicts. Keeping the latter would pin
        # every speech bubble of every match in memory for the app's lifetime.
        self._background_titles_cache: dict[IndexItem, list[str]] = {}

        self._item_index: dict[str, list[IndexItem]] = defaultdict(list)

        self._nav_on_speech_btn: bool = False

        self._populate_alphabet_menu()

        # The pages of the story whose bubbles the popup shows: a bubble pressed offers
        # them all, as the story's row does, not the one page pressed.
        self._bubble_title_pages: tuple[str, ...] = ()
        self._speech_bubble_browser_popup, self._popup_nav = create_speech_bubble_popup(
            self._font_manager.speech_bubble_popup_title_font_name,
        )

    def _find_words(self, index_terms: str) -> TitleDict:
        return self._search.find_words(index_terms)

    def _find_words_for_item(self, item: IndexItem) -> TitleDict:
        """Resolve one index item to the titles it appears in.

        Context-sensitive words (see ``CONTEXT_SENSITIVE_WORDS``) expand into typed
        entity entries, which must be looked up by entity rather than as plain words.
        Both the click path and the background image go through here so they can never
        disagree about what an item means.
        """
        if item.entity_type is not None:
            return self._search.find_entities(str(item.entity_type), str(item.id))
        return self._find_words(str(item.id))

    @override
    def _populate_index_for_letter(self, first_letter: str) -> None:
        self._populate_index_grid(first_letter)

    # --- Keyboard navigation overrides ---

    @override
    def handle_key(self, key: int) -> bool:
        # While the speech-bubble popup is open its frame has the keys, and asks
        # PopupKeyboardNav about each first (the frame's `key_handler`), so this
        # handler is normally not reached then: the modal-popup guard in main_screen
        # yields first.
        if self._popup_nav.is_open:
            return self._popup_nav.handle_key(key)
        return super().handle_key(key)

    @override
    def exit_nav_focus(self) -> None:
        self._nav_on_speech_btn = False
        super().exit_nav_focus()

    @override
    def _enter_items_panel(self) -> None:
        self._nav_on_speech_btn = False
        super()._enter_items_panel()

    @override
    def _place_focus_on(self, btn: Button) -> bool:
        # The focus follows a mouse press onto the title row itself, off a speech button.
        if not super()._place_focus_on(btn):
            return False
        self._nav_on_speech_btn = False
        return True

    @override
    def _get_col_buttons(self, col_idx: int) -> list[Button]:
        """Return navigable buttons (title/index only, no speech buttons) for Up/Down."""
        all_btns = super()._get_col_buttons(col_idx)
        return [b for b in all_btns if not isinstance(b, TitleShowSpeechButton)]

    @staticmethod
    def _get_paired_speech_button(title_btn: Button) -> TitleShowSpeechButton | None:
        """Return the TitleShowSpeechButton paired with an IndexTitleItemButton."""
        if not isinstance(title_btn, IndexTitleItemButton):
            return None
        parent = title_btn.parent
        if parent is None:
            return None
        children = parent.children
        try:
            title_idx = children.index(title_btn)
        except ValueError:
            return None
        speech_idx = title_idx - 1
        if 0 <= speech_idx < len(children) and isinstance(
            children[speech_idx], TitleShowSpeechButton
        ):
            return children[speech_idx]
        return None

    def _focused_item_button(self) -> Button | None:
        """Return the row the focus is on in its column, or None when it is on none."""
        col_buttons = self._get_col_buttons(self._nav_focused_col)
        if self._nav_focused_item_idx >= len(col_buttons):
            return None
        return col_buttons[self._nav_focused_item_idx]

    def _focused_speech_button(self) -> TitleShowSpeechButton | None:
        """Return the speech button of the focused row, when it is a title row with one."""
        title_btn = self._focused_item_button()
        return self._get_paired_speech_button(title_btn) if title_btn else None

    @override
    def _draw_item_focus(self, *, scroll: bool = True) -> None:
        if not self._nav_on_speech_btn:
            super()._draw_item_focus(scroll=scroll)
            return
        title_btn = self._focused_item_button()
        speech_btn = self._get_paired_speech_button(title_btn) if title_btn else None
        if speech_btn:
            self._nav_focused_btn = title_btn
            draw_focus_highlight(speech_btn, INDEX_NAV_FOCUS_GROUP)
            self._set_item_fill(speech_btn)
            if scroll:
                self.ids.index_scroll_view.scroll_into_view(speech_btn)
            self._nav_saved_grid_version = self._grid_version

    def _handle_speech_btn_key(self, key: int) -> bool:
        """Handle key events when focus is on a speech button. Returns True if consumed."""
        if key in (KEY_UP, KEY_DOWN, KEY_LEFT):
            # Return focus to the paired title button.
            self._nav_on_speech_btn = False
            self._clear_all_item_focus()
            self._draw_item_focus()
            return True
        if key == KEY_RIGHT:
            # Move to the next column as a title button (not a speech button).
            next_col = self._nav_focused_col + 1
            if next_col < self.num_columns and self._get_col_buttons(next_col):
                self._nav_on_speech_btn = False
                self._move_col_focus(1)
            return True
        if key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            speech_btn = self._focused_speech_button()
            if speech_btn:
                speech_btn.trigger_action(duration=0)
            return True
        if is_escape_key(key):
            self._nav_on_speech_btn = False
            self._on_back_from_items()
            return True
        # PAGE_UP / PAGE_DOWN and others: delegate to base (just scrolls).
        return super()._handle_items_key(key)

    @override
    def _handle_items_key(self, key: int) -> bool:
        if self._nav_on_speech_btn:
            return self._handle_speech_btn_key(key)
        # Not on speech button — check if Right from a title sub-item should enter speech button.
        if key == KEY_RIGHT and self._focused_speech_button():
            self._clear_all_item_focus()
            self._nav_on_speech_btn = True
            self._draw_item_focus()
            return True
        return super()._handle_items_key(key)

    @override
    def _get_items_for_letter(self, first_letter: str) -> list[IndexItem]:
        return self._item_index.get(first_letter, [])

    @override
    def _next_background_image(self) -> None:
        first_letter = self._selected_letter_button.text
        index_terms = self._item_index[first_letter]
        if not index_terms:
            return
        rand_item = random.choice(index_terms)

        title_strs = self._background_titles_cache.get(rand_item)
        if title_strs is None:
            # Searched here, on the UI thread: 36 to 61 ms measured (2026-11-13), once
            # per word and then cached. That is each time a letter or prefix is shown,
            # so with every key along the letters or the prefix bar, and then every
            # 15 seconds while the index shows; each of those keys fills the grid
            # anew as well. A worker thread would need the search made safe to share
            # and its result handed back and checked against a letter changed since:
            # more machinery than a hitch nobody sees is worth.
            title_strs = list(self._find_words_for_item(rand_item))
            _store_bounded(self._background_titles_cache, rand_item, title_strs)

        # A word may be spoken only in titles that are in no Fantagraphics volume.
        found_titles = [
            ALL_FANTA_COMIC_BOOK_INFO[title]
            for title_str in title_strs
            if (title := STR_TITLE_TO_ENUM.get(title_str)) in ALL_FANTA_COMIC_BOOK_INFO
        ]
        image_info = self._random_title_images.get_random_image(found_titles)
        self._set_background_image(image_info)

    @override
    def _create_index_button(self, item: IndexItem) -> IndexItemButton:
        """Create a configured IndexItemButton."""
        button = IndexItemButton(
            text=item.display_text,
            font_name=self._font_manager.speech_index_item_font_name,
            font_size=self._font_manager.speech_index_item_font_size,
            bold=False,
            height=INDEX_ITEM_ROW_HEIGHT,
        )
        button.bind(
            on_release=lambda btn, bound_item=item: self._on_index_item_press(btn, bound_item)
        )
        return button

    @override
    def _index_item_font(self) -> tuple[str, float]:
        return (
            self._font_manager.speech_index_item_font_name,
            self._font_manager.speech_index_item_font_size,
        )

    @override
    def _get_sub_items_layout(self, item: IndexItem) -> BoxLayout:
        assert type(item.id) is str
        index_term: str = item.id
        logger.info(f'Laying out title sub-items for for index term "{index_term}".')

        sub_items_to_display = self._get_sub_items_data(item)

        assert self._open_tag_button is not None
        parent_padding = self._open_tag_button.padding[0]
        # Half the main index's step: the columns here are a third of the width.
        sub_item_padding = parent_padding + self.index_theme.SUB_ITEM_INDENT_STEP / 2

        # A row to a title, each the column's width: the title, cut short with an
        # ellipsis where the column is too narrow for it, and its speech button at
        # the column's right edge.
        sub_items_layout = self._new_sub_items_layout()

        for (
            title_str,
            first_page_to_goto,
            title_str_with_pages,
            title_speech_info,
        ) in sub_items_to_display:
            if title_str not in STR_TITLE_TO_ENUM:
                # A search index older than a title's renaming: the rest still open.
                logger.warning(f'No title "{title_str}" for the index term "{index_term}".')
                continue
            show_speech_bubbles_button = TitleShowSpeechButton()
            # As tall as its row: at the kv rule's taller size it ran over into the row
            # above, where a tap went to the row below's bubbles. Set once built, as the
            # kv rule's size beats one handed to the constructor.
            show_speech_bubbles_button.size = (INDEX_ITEM_ROW_HEIGHT, INDEX_ITEM_ROW_HEIGHT)
            title_button = IndexTitleItemButton(
                full_text=title_str_with_pages,
                italic=True,
                height=INDEX_ITEM_ROW_HEIGHT,
                padding=[sub_item_padding, 0, 0, 0],
                color=self.index_theme.TITLE_TEXT,
                background_color_normal=self.index_theme.TITLE_BG,
                background_color_down=self.index_theme.TITLE_BG_SELECTED,
                font_name=self._font_manager.index_title_item_font_name,
                font_size=self._font_manager.index_title_item_font_size,
                fill_past_right=INDEX_ITEM_ROW_HEIGHT,
            )
            sub_item = title_row_item(
                title_str, first_page_to_goto, title_str_with_pages, title_speech_info
            )
            # Through the one press path, as a term's is: the focus follows a mouse press.
            title_button.bind(
                on_release=lambda btn, bound_item=sub_item: self._on_index_item_press(
                    btn, bound_item
                ),
            )

            def _on_speech_btn(
                _btn: object,
                ts: str = title_str,
                it: str = index_term,
                tsi: TitleInfo = title_speech_info,
            ) -> None:
                self._show_title_speech_bubbles(ts, it, tsi)

            show_speech_bubbles_button.bind(on_release=_on_speech_btn)

            row = BoxLayout(
                orientation="horizontal", size_hint_y=None, height=INDEX_ITEM_ROW_HEIGHT
            )
            row.add_widget(title_button)
            row.add_widget(show_speech_bubbles_button)
            sub_items_layout.add_widget(row)

        return sub_items_layout

    def _get_sub_items_data(self, item: IndexItem) -> list[SpeechHitRow]:
        """Return the term's title rows, found once and cached, listed as an index lists."""
        found_words = self._found_words_cache.get(item)
        if found_words is None:
            found_words = self._find_words_for_item(item)
            _store_bounded(self._found_words_cache, item, found_words)

        return speech_hit_rows(found_words, max_len=MAX_TITLE_AND_PAGES_LEN, sortable=True)

    @override
    def _insert_sub_items_layout(self, sub_items_layout: BoxLayout) -> None:
        super()._insert_sub_items_layout(sub_items_layout)
        # The open word reads as the heading of the titles under it.
        assert self._open_tag_button is not None
        self._open_tag_button.bold = True

    @override
    def _close_open_widgets_from(self, level: int) -> None:
        for widget in self._open_tag_widgets[level:]:
            widget.owner_button.bold = False
        super()._close_open_widgets_from(level)

    @override
    def _handle_terminal_item(self, button: Button, item: IndexItem) -> bool:
        # A title, a term's sub-item, is a terminal action: handle it and leave the UI alone.
        if type(item.id) is Titles:
            self._handle_title(button, item)
            return True
        return False

    @override
    def _handle_item_expansion(self, button: Button, item: IndexItem) -> None:
        logger.info(log_markers.INDEX_TERM_HANDLED.format(term=item.id))

        self._open_sub_items(button, item)

    def _show_title_speech_bubbles(
        self, title_str: str, index_terms: str, title_speech_info: TitleInfo
    ) -> None:
        logger.info(
            log_markers.SHOW_BUBBLES_FOR_INDEX_TERMS.format(title=title_str, terms=index_terms)
        )
        self._bubble_title_pages = comic_pages(title_speech_info)
        show_speech_bubbles_popup(
            self._speech_bubble_browser_popup,
            title_str,
            index_terms,
            title_speech_info,
            self._handle_title_from_bubble_press,
            text_font_size=self._font_manager.speech_bubble_text_font_size,
        )

    def _handle_title_from_bubble_press(self, title_str: str, page_to_goto: str) -> None:
        logger.info(
            log_markers.TITLE_FROM_BUBBLE_BROWSER.format(title=title_str, page=page_to_goto)
        )
        self._speech_bubble_browser_popup.dismiss()

        title = STR_TITLE_TO_ENUM.get(title_str)
        if title is None:
            logger.warning(f'No title "{title_str}" to go to from the speech bubble browser.')
            return
        image_info = ImageInfo(from_title=title, filename=None)
        pages = self._bubble_title_pages

        def goto_title() -> None:
            if not self._goto_title_or_notice(image_info, page_to_goto, pages):
                return
            # The popup owned the keyboard, so this goto skipped the main screen's normal
            # key hand-off; land focus on the title portal (the read action) explicitly.
            if self.on_after_popup_goto_title is not None:
                self.on_after_popup_goto_title()

        Clock.schedule_once(lambda _dt: goto_title(), 0.01)


class SpeechIndexScreen(SpeechSubItemsIndexScreen):
    """The Words index: an A-Z index of every word spoken in the comics.

    Adds the prefix bar to ``SpeechSubItemsIndexScreen``, because a single letter
    holds far too many words for one grid. Navigation therefore runs
    ALPHABET -> PREFIX -> ITEMS rather than the base ALPHABET -> ITEMS.
    """

    _selected_prefix_button = ObjectProperty(None, allownone=True)

    def __init__(
        self,
        reader_settings: ReaderSettings,
        font_manager: FontManager,
        user_error_handler: UserErrorHandler,
        **kwargs: object,
    ) -> None:
        super().__init__(reader_settings, font_manager, user_error_handler, **kwargs)

        self.has_prefix_bar = True

        # What each ambiguous word may name, so it is listed as typed index entries.
        self._context_entity_map = context_entities()

        self._prefix_buttons: dict[str, IndexPrefixButton] = {}
        # The letter whose bar the saved prefix was pressed on, or None while the saved
        # prefix is still the one read from the settings file.
        self._saved_prefix_letter: str | None = None
        self._nav_focused_prefix_idx: int = 0

    @cached_property
    def _cleaned_alpha_split_terms(self) -> dict[str, dict[str, list[str]]]:
        """Every term, by letter and prefix: read when the index is first shown.

        Read as the screen was built, the 24,000 terms cost every start of the app
        a fifth of a second, shown or not.
        """
        return self._search.get_alpha_split_terms()

    @override
    def _populate_index_for_letter(self, first_letter: str) -> None:
        # Selecting a prefix populates the grid, so there is no second grid call here.
        self._populate_top_alphabet_split_menu(first_letter)

    def _populate_top_alphabet_split_menu(self, first_letter: str) -> None:
        """Create the top sub alphabet split buttons across the top."""
        first_letter_split_terms = self._cleaned_alpha_split_terms.get(first_letter.lower(), {})

        if len(first_letter_split_terms) > MAX_PREFIX_BUTTONS_PER_LETTER:
            # The bar is a fixed single row, so anything past the last slot is
            # unreachable. The split is meant to prevent this.
            logger.warning(
                f"Letter '{first_letter}' needs {len(first_letter_split_terms)} prefix"
                f" buttons but the bar holds {MAX_PREFIX_BUTTONS_PER_LETTER}."
            )
            # The first that fit: one more, and the bar's grid raises on being given it.
            first_letter_split_terms = dict(
                islice(first_letter_split_terms.items(), MAX_PREFIX_BUTTONS_PER_LETTER)
            )

        alphabet_top_split_layout: GridLayout = self.ids.alphabet_top_split_layout
        alphabet_top_split_layout.clear_widgets()
        self._prefix_buttons.clear()

        if not first_letter_split_terms:
            # The alphabet is fixed and the index is built: a letter may have no words.
            # The grid then shows its "no index items" row under an empty bar.
            self._selected_prefix_button = None
            self._item_index[first_letter] = []
            self._populate_index_grid(first_letter)
            return

        for prefix, terms in first_letter_split_terms.items():
            button = IndexPrefixButton(
                prefix=prefix, letter=first_letter, text=stacked_prefix_label(prefix, terms)
            )
            button.bind(on_release=self._on_prefix_button_released)
            self._prefix_buttons[prefix] = button
            alphabet_top_split_layout.add_widget(button)

        first_prefix = self._prefix_to_show_first(first_letter, first_letter_split_terms)
        self.on_letter_prefix_press(self._prefix_buttons[first_prefix])

    def _prefix_to_show_first(self, first_letter: str, split_terms: dict[str, list[str]]) -> str:
        """Return the saved prefix if it is one of this letter's, else the letter's first."""
        assert self.treeview_index_node is not None
        saved_prefix = self.treeview_index_node.saved_state.get(SAVED_NODE_STATE_PREFIX_KEY)
        if saved_prefix in split_terms:
            return saved_prefix
        # A prefix saved on another letter's bar is only the letter having changed. One
        # this letter should have had is a stale or hand-edited settings file.
        if saved_prefix is not None and self._saved_prefix_letter in (None, first_letter):
            logger.warning(f'Invalid restored prefix: "{saved_prefix}".')
        return next(iter(split_terms))

    def _on_prefix_button_released(self, button: IndexPrefixButton) -> None:
        """Show a prefix pressed by mouse or touch; the keys select one without a press."""
        self.on_letter_prefix_press(button)
        if self._nav_active:
            # The focus follows the press, as it does a letter's: left on a row of the
            # grid just replaced, the next key went on from that row's old place.
            self._enter_prefix_panel()

    def on_letter_prefix_press(self, button: IndexPrefixButton) -> None:
        """Show the words under a prefix button, and save the prefix as the one to restore.

        Args:
            button: The pressed prefix button, which carries its prefix and its letter.

        """
        prefix = button.prefix
        first_letter = button.letter
        logger.debug(log_markers.INDEX_PREFIX_PRESSED.format(prefix=prefix))
        assert self.treeview_index_node is not None
        self.treeview_index_node.saved_state[SAVED_NODE_STATE_PREFIX_KEY] = prefix
        self._saved_prefix_letter = first_letter

        move_selection(self._selected_prefix_button, button)
        self._selected_prefix_button = button

        terms = self._cleaned_alpha_split_terms[first_letter.lower()][prefix]
        self._item_index[first_letter] = word_index_items(terms, self._context_entity_map)

        self._populate_index_grid(first_letter)

    # --- Prefix panel navigation ---

    @override
    def _handle_panel_key(self, panel: _IndexNavPanel, key: int) -> bool:
        if panel is _IndexNavPanel.PREFIX:
            return self._handle_prefix_key(key)
        return super()._handle_panel_key(panel, key)

    @override
    def exit_nav_focus(self) -> None:
        self._clear_prefix_focus()
        super().exit_nav_focus()

    @override
    def _place_focus_on(self, btn: Button) -> bool:
        # A mouse press on a term takes the ring off the prefix bar, as Down from it does.
        if not super()._place_focus_on(btn):
            return False
        self._clear_prefix_focus()
        return True

    @override
    def _on_right_from_alphabet(self) -> None:
        self._enter_prefix_panel()

    @override
    def _on_back_from_items(self) -> None:
        self._enter_prefix_panel()

    @override
    def _on_up_from_first_item(self) -> None:
        self._clear_all_item_focus()
        self._enter_prefix_panel()

    def _enter_prefix_panel(self) -> None:
        visible = self._get_visible_prefix_buttons()
        if not visible:
            # A letter with no words has no prefix to ring (and no item either): the
            # letters keep the keys, where on an empty bar no key did anything again.
            self._enter_alphabet_panel()
            return
        self._clear_all_item_focus()
        self._clear_letter_focus()
        self._nav_panel = _IndexNavPanel.PREFIX
        # Focus the currently selected prefix.
        if self._selected_prefix_button and self._selected_prefix_button in visible:
            self._nav_focused_prefix_idx = visible.index(self._selected_prefix_button)
        else:
            self._nav_focused_prefix_idx = 0
        self._draw_prefix_focus()

    def _handle_prefix_key(self, key: int) -> bool:
        visible = self._get_visible_prefix_buttons()
        if not visible:
            # No bar to be on (`_enter_prefix_panel` keeps off an empty one): back to
            # the letters, not a screen that takes no key.
            self._enter_alphabet_panel()
            return True
        idx = self._nav_focused_prefix_idx
        if key in (KEY_LEFT, KEY_RIGHT):
            self._clear_prefix_focus()
            new_idx = idx + (1 if key == KEY_RIGHT else -1)
            if new_idx < 0:
                self._enter_alphabet_panel()
            elif new_idx >= len(visible):
                self._enter_items_panel()
            else:
                self._nav_focused_prefix_idx = new_idx
                self._select_focused_prefix(visible)
                self._draw_prefix_focus()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._select_focused_prefix(visible)
            self._clear_prefix_focus()
            # The new grid's rows have no place until the next frame lays them out.
            grid_version = self._grid_version
            Clock.schedule_once(lambda _dt: self._enter_items_of_grid(grid_version), 0)
        elif key == KEY_DOWN:
            self._clear_prefix_focus()
            self._enter_items_panel()
        elif is_escape_key(key):
            self._clear_prefix_focus()
            self._enter_alphabet_panel()
        else:
            return False
        return True

    def _enter_items_of_grid(self, grid_version: int) -> None:
        """Move the focus from the prefix bar into the grid Enter built, if it still can.

        In the frame between, the keys may have left the screen, moved to the alphabet
        or shown another prefix: the ring then stays where that put it.
        """
        if (
            self._nav_active
            and self._nav_panel is _IndexNavPanel.PREFIX
            and self._grid_version == grid_version
        ):
            self._enter_items_panel()

    def _select_focused_prefix(self, visible: list[IndexPrefixButton]) -> None:
        btn = visible[self._nav_focused_prefix_idx]
        self.on_letter_prefix_press(btn)

    def _get_visible_prefix_buttons(self) -> list[IndexPrefixButton]:
        """Return the currently displayed prefix buttons in left-to-right order."""
        layout = self.ids.alphabet_top_split_layout
        return list(reversed(layout.children))

    def _draw_prefix_focus(self) -> None:
        visible = self._get_visible_prefix_buttons()
        if not visible:
            return
        self._nav_focused_prefix_idx = min(self._nav_focused_prefix_idx, len(visible) - 1)
        draw_focus_highlight(visible[self._nav_focused_prefix_idx], INDEX_NAV_FOCUS_GROUP)

    def _clear_prefix_focus(self) -> None:
        clear_focus_in_list(self._get_visible_prefix_buttons(), INDEX_NAV_FOCUS_GROUP)
