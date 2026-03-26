from __future__ import annotations

import random
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Self

from barks_fantagraphics.barks_tags import TagGroups
from barks_fantagraphics.barks_titles import BARKS_TITLE_DICT, BARKS_TITLES, Titles
from barks_fantagraphics.comic_search import ComicSearch, SearchMode
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from loguru import logger

from barks_reader.core.image_selector import ImageInfo
from barks_reader.core.reader_formatter import get_fitted_title_with_page_nums
from barks_reader.core.reader_settings import BARKS_READER_SECTION, SHOW_FUN_VIEW_TITLE_INFO
from barks_reader.core.settings_notifier import settings_notifier
from barks_reader.ui.index_screen import (
    TitleShowSpeechButton,
    create_speech_bubble_popup,
    show_speech_bubbles_popup,
)
from barks_reader.ui.reader_keyboard_nav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    KEY_TAB,
    KEY_UP,
    clear_focus_in_list,
    update_focus_in_list,
)
from barks_reader.ui.touch_keyboard import TouchAwareTextInput  # noqa: F401  # used in .kv

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.whoosh_search_engine import TitleInfo
    from kivy.uix.scrollview import ScrollView

    from barks_reader.core.reader_settings import ReaderSettings
    from barks_reader.ui.font_manager import FontManager

SEARCH_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

SEARCH_IMAGE_CHANGE_SECONDS = 10
MAX_WORD_SEARCH_TITLE_AND_PAGES_LEN = 50

_SEARCH_NAV_FOCUS_GROUP = "search_nav_focus"


class _SearchResultButton(Button):
    """A clickable result row in a search results list."""

    row_index = NumericProperty(0)


_CHIP_BG_NORMAL = (0.2, 0.35, 0.2, 1)
_CHIP_BG_ACTIVE = (0.25, 0.45, 0.25, 1)
_CHIP_BG_MEMBER = (0.18, 0.30, 0.22, 1)


_CHIP_BORDER_NONE = (0, 0, 0, 0)
_CHIP_BORDER_FOCUSED = (0.5, 1, 0.5, 1)

_WORD_ITEM_SELECTED_BG = (0.15, 0.35, 0.55, 0.8)


class _TagChipButton(Button):
    """A pill-shaped tag chip button for tag search results."""

    chip_bg_color = ObjectProperty(_CHIP_BG_NORMAL)
    chip_border_color = ObjectProperty(_CHIP_BORDER_NONE)

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)


class SearchScreen(FloatLayout):
    """Bottom view screen for search. Mode is set externally via set_mode()."""

    is_visible = BooleanProperty(defaultvalue=False)
    image_texture = ObjectProperty(allownone=True)
    current_title_str = StringProperty()
    show_current_title = BooleanProperty(defaultvalue=True)
    on_goto_title: Callable[[str], bool] | None = ObjectProperty(None, allownone=True)
    on_goto_title_with_page: Callable[[ImageInfo, str], None] | None = ObjectProperty(
        None, allownone=True
    )

    # Per-mode widget ID mapping: mode -> (input, clear_button, scroll_view, results_layout)
    _MODE_WIDGETS: ClassVar[dict[str, tuple[str, str, str, str]]] = {
        "Title": (
            "title_search_input",
            "title_clear_button",
            "title_results_scroll",
            "title_results_layout",
        ),
        "Tag": (
            "tag_search_input",
            "tag_clear_button",
            "tag_results_scroll",
            "tag_title_results_layout",
        ),
        "Word": (
            "word_search_input",
            "word_clear_button",
            "word_results_scroll",
            "word_results_layout",
        ),
    }

    def __init__(
        self,
        reader_settings: ReaderSettings,
        font_manager: FontManager,
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)
        self._reader_settings = reader_settings
        self._font_manager = font_manager
        self._search = ComicSearch(reader_settings.sys_file_paths.get_barks_reader_indexes_dir())

        self._current_image_info: ImageInfo | None = None
        self.on_goto_background_title_func: Callable[[ImageInfo], None] | None = None
        self.on_search_results_title_changed: Callable[[Titles], None] | None = None
        self._search_result_titles: list[Titles] = []
        self._image_change_event = None
        self.show_current_title = self._reader_settings.show_fun_view_title_info

        settings_notifier.register_callback(
            BARKS_READER_SECTION, SHOW_FUN_VIEW_TITLE_INFO, self._on_change_show_current_title
        )

        self._active_mode: str = "Title"

        self._nav_active: bool = False
        self._nav_on_exit_request: Callable | None = None
        self._nav_focus_area: str = "input"  # "input", "clear", "tags", "results"
        self._nav_focused_result_idx: int = 0
        self._nav_focused_chip_idx: int = 0
        self._nav_word_sub_focus: str = "title"  # "title" or "speech"

        # Tag search state
        self._current_tag = None
        self._selected_tag: str = ""
        self._selected_member: str = ""
        self._tag_chip_strings: list[str] = []
        self._tag_titles: list[str] = []

        # Word search state
        self._word_search_results: list[tuple[str, str, str, TitleInfo]] = []
        self._word_terms = self._search.get_alpha_split_terms()
        self._selected_word: str = ""

        # Last activated result (for restoring focus after go-back)
        self._last_activated_result_idx: int | None = None
        self._last_activated_word_sub_focus: str = "title"

        self._speech_bubble_popup, self._popup_nav = create_speech_bubble_popup(
            self._font_manager.speech_bubble_popup_title_font_name,
        )

    def on_is_visible(self, _instance: Self, value: bool) -> None:
        if not value:
            self._cancel_image_change_event()

    def set_mode(self, mode: str) -> None:
        """Switch to the given search mode: 'Title', 'Tag', or 'Word'."""
        self._active_mode = mode

        for content_mode, content_id in [
            ("Title", "title_search_content"),
            ("Tag", "tag_search_content"),
            ("Word", "word_search_content"),
        ]:
            active = mode == content_mode
            widget = self.ids[content_id]
            widget.opacity = 1 if active else 0
            widget.size_hint = (0.86, 1) if active else (0, 0)

        logger.debug(f"SearchScreen mode set to '{mode}'.")

    # --- Shared Helpers ---

    @staticmethod
    def _populate_title_results(
        layout: BoxLayout, title_strings: list[str], on_select: Callable[[str], None]
    ) -> None:
        layout.clear_widgets()
        for i, title_str in enumerate(title_strings):
            btn = _SearchResultButton(text=title_str, row_index=i)
            btn.bind(on_release=lambda _b, t=title_str: on_select(t))
            layout.add_widget(btn)

    def _on_result_goto_title(self, title_str: str) -> None:
        logger.info(f'Search: selected "{title_str}".')
        if self.on_goto_title:
            self.on_goto_title(title_str)

    # --- Title Search ---

    def on_title_search_text(self, text: str) -> None:
        results_layout: BoxLayout = self.ids.title_results_layout
        results_layout.clear_widgets()

        if len(text) <= 1:
            return

        title_enums, title_strings = self._get_titles_matching(text)
        self._populate_title_results(results_layout, title_strings, self._on_result_goto_title)
        self._update_background_from_results(title_enums)

    def _get_titles_matching(self, value: str) -> tuple[list[Titles], list[str]]:
        result = self._search.search(value, SearchMode.TITLE)
        return result.titles, result.title_strings

    def on_title_clear(self) -> None:
        self._cancel_image_change_event()
        self.ids.title_search_input.text = ""
        self.ids.title_search_input.focus = True

    # --- Tag Search ---

    def on_tag_search_text(self, text: str) -> None:
        self.ids.tag_chips_layout.clear_widgets()
        self._tag_chip_strings = []
        self._selected_member = ""
        self._clear_tag_title_results()

        if len(text) <= 1:
            return

        found_tags = self._search.search(text, SearchMode.TAG).matched_tags
        self._tag_chip_strings = sorted([str(t.value) for t in found_tags]) if found_tags else []

        self._rebuild_tag_chips()

        if len(self._tag_chip_strings) == 1:
            self._on_tag_result_selected(self._tag_chip_strings[0])

    def _rebuild_tag_chips(self) -> None:
        """Rebuild the tag chips layout, inserting member chips after the selected group."""
        container: BoxLayout = self.ids.tag_chips_layout
        container.clear_widgets()

        selected = self._selected_tag
        selected_is_group = isinstance(self._current_tag, TagGroups) and selected

        # Find the split point (index after the selected group chip)
        split_idx: int | None = None
        if selected_is_group:
            for i, tag_str in enumerate(self._tag_chip_strings):
                if tag_str == selected:
                    split_idx = i + 1
                    break

        if split_idx is not None:
            before = self._tag_chip_strings[:split_idx]
            after = self._tag_chip_strings[split_idx:]
            container.add_widget(self._make_main_chip_stack(before, selected))
            member_stack = self._make_member_chip_stack()
            if member_stack:
                container.add_widget(member_stack)
            if after:
                container.add_widget(self._make_main_chip_stack(after, selected))
        else:
            container.add_widget(self._make_main_chip_stack(self._tag_chip_strings, selected))

    def _make_main_chip_stack(self, tag_strings: list[str], selected: str) -> BoxLayout:
        stack = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4), padding=dp(2))
        stack.bind(minimum_height=stack.setter("height"))
        for tag_str in tag_strings:
            btn = _TagChipButton(text=tag_str)
            btn.chip_bg_color = _CHIP_BG_ACTIVE if tag_str == selected else _CHIP_BG_NORMAL
            btn.bind(on_release=lambda _b, t=tag_str: self._on_tag_result_selected(t))
            stack.add_widget(btn)
        return stack

    def _make_member_chip_stack(self) -> BoxLayout | None:
        members = self._search.get_tag_group_members(self._current_tag)
        if not members:
            return None
        stack = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(4),
            padding=[dp(48), dp(2), dp(2), dp(2)],
        )
        stack.is_member_layout = True
        stack.bind(minimum_height=stack.setter("height"))
        for member in members:
            label = str(member.value)
            if isinstance(member, TagGroups):
                label += " \u25b8"
            btn = _TagChipButton(text=label)
            btn.chip_bg_color = (
                _CHIP_BG_ACTIVE if label == self._selected_member else _CHIP_BG_MEMBER
            )
            btn.bind(on_release=lambda _b, m=label: self._on_member_tag_selected(m))
            stack.add_widget(btn)
        return stack

    def _show_tag_titles(self, tag_str: str) -> None:
        """Look up titles for a tag and populate the results list."""
        _, titles = self._search.resolve_tag(tag_str.lower())
        self._tag_titles = self._search.get_title_display_strings(titles) if titles else []
        title_results_layout: BoxLayout = self.ids.tag_title_results_layout
        self._populate_title_results(
            title_results_layout, self._tag_titles, self._on_result_goto_title
        )
        self._update_background_from_results(titles or [])

    def _on_tag_result_selected(self, tag_str: str) -> None:
        logger.info(f'Tag search: selected tag "{tag_str}".')
        self._selected_tag = tag_str
        self._selected_member = ""
        self._current_tag, _ = self._search.resolve_tag(tag_str.lower())
        self._rebuild_tag_chips()
        self._show_tag_titles(tag_str)

    def _on_member_tag_selected(self, member_label: str) -> None:
        # Strip subgroup indicator suffix
        member_str = member_label.rstrip(" \u25b8")
        logger.info(f'Tag search: selected member "{member_str}".')
        self._selected_member = member_label
        self._show_tag_titles(member_str)

        # Highlight the selected member chip
        for chip in self._get_member_chip_buttons():
            chip.chip_bg_color = _CHIP_BG_ACTIVE if chip.text == member_label else _CHIP_BG_MEMBER

    def _clear_tag_title_results(self) -> None:
        self.ids.tag_title_results_layout.clear_widgets()
        self._tag_titles = []

    def on_tag_clear(self) -> None:
        self._cancel_image_change_event()
        self.ids.tag_search_input.text = ""
        self.ids.tag_chips_layout.clear_widgets()
        self._tag_chip_strings = []
        self._selected_member = ""
        self._clear_tag_title_results()
        self.ids.tag_search_input.focus = True

    # --- Word Search ---

    def on_word_search_text(self, text: str) -> None:
        self.ids.word_chips_layout.clear_widgets()
        self.ids.word_results_layout.clear_widgets()
        self._word_search_results = []

        if not text:
            return

        words = self._get_words_matching_prefix(text)

        for i, word in enumerate(words):
            btn = _SearchResultButton(text=word, row_index=i, color=(0.65, 0.8, 1, 1))
            btn.bind(on_release=lambda _b, w=word: self._on_word_chip_selected(w))
            self.ids.word_chips_layout.add_widget(btn)

        if len(words) == 1:
            self._on_word_chip_selected(words[0])

    def _get_words_matching_prefix(self, text: str) -> list[str]:
        query = text.lower()
        first_char = query[0]
        letter_group = self._word_terms.get(first_char, {})

        min_prefix_len = 2
        if len(query) >= min_prefix_len:
            candidates = letter_group.get(query[:min_prefix_len], [])
        else:
            candidates = [w for group in letter_group.values() for w in group]

        matching = [w for w in candidates if w.lower().startswith(query)]
        matching.sort()
        return matching

    def _on_word_chip_selected(self, word: str) -> None:
        logger.info(f'Word search: selected chip "{word}".')
        self._selected_word = word

        for btn in reversed(self.ids.word_chips_layout.children):
            if btn.text == word:
                btn.background_color = _WORD_ITEM_SELECTED_BG
            else:
                idx = btn.row_index
                btn.background_color = (
                    (0.15, 0.15, 0.15, 0.4) if idx % 2 == 0 else (0.22, 0.22, 0.22, 0.4)
                )

        found = self._search.find_words(word)

        results_layout: BoxLayout = self.ids.word_results_layout
        results_layout.clear_widgets()

        self._word_search_results = self._build_word_results(found)
        self._populate_word_results_layout(results_layout)

        if not found:
            results_layout.add_widget(
                _SearchResultButton(text=f'No results for "{word}"', disabled=True)
            )
            return

        word_result_titles = [BARKS_TITLE_DICT[ct] for ct in found if ct in BARKS_TITLE_DICT]
        self._update_background_from_results(word_result_titles)

    @staticmethod
    def _build_word_results(found: dict[str, TitleInfo]) -> list[tuple[str, str, str, TitleInfo]]:
        results: list[tuple[str, str, str, TitleInfo]] = []
        for comic_title, title_speech_info in found.items():
            page_num_list = [page.comic_page for page in title_speech_info.fanta_pages.values()]
            first_page_num, title_with_pages = get_fitted_title_with_page_nums(
                comic_title, page_num_list, MAX_WORD_SEARCH_TITLE_AND_PAGES_LEN
            )
            results.append((comic_title, first_page_num, title_with_pages, title_speech_info))
        results.sort(key=lambda t: t[2])
        return results

    def _populate_word_results_layout(self, results_layout: BoxLayout) -> None:
        for i, (
            comic_title,
            first_page_num,
            title_with_pages,
            title_speech_info,
        ) in enumerate(self._word_search_results):
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(28))

            title_btn = _SearchResultButton(
                text=title_with_pages,
                row_index=i,
                size_hint=(0.94, 1),
                halign="left",
                valign="middle",
            )
            title_btn.text_size = (title_btn.width, None)
            title_btn.bind(size=lambda inst, _val: setattr(inst, "text_size", (inst.width, None)))
            title_btn.bind(
                on_release=lambda _b, ct=comic_title, fp=first_page_num: (
                    self._on_word_title_selected(ct, fp)
                ),
            )
            row.add_widget(title_btn)

            row_bg = (0.15, 0.15, 0.15, 0.4) if i % 2 == 0 else (0.22, 0.22, 0.22, 0.4)
            speech_btn = TitleShowSpeechButton(size_hint=(0.06, 1), background_color=row_bg)
            speech_btn.bind(
                on_release=lambda _b, ct=comic_title, tsi=title_speech_info: (
                    self._show_word_speech_bubbles(ct, tsi)
                ),
            )
            row.add_widget(speech_btn)

            results_layout.add_widget(row)

    def _on_word_title_selected(self, title_str: str, page_to_goto: str) -> None:
        logger.info(f'Word search: navigating to "{title_str}", page {page_to_goto}.')
        self._goto_title_with_page(title_str, page_to_goto)

    def _show_word_speech_bubbles(self, title_str: str, title_speech_info: TitleInfo) -> None:
        search_text = self._selected_word
        logger.info(f'Show speech bubbles for: "{title_str}" and search "{search_text}".')
        show_speech_bubbles_popup(
            self._speech_bubble_popup,
            title_str,
            search_text,
            title_speech_info,
            self._handle_bubble_title_press,
            self._font_manager.speech_bubble_popup_title_font_size,
        )

    def _handle_bubble_title_press(self, title_str: str, page_to_goto: str) -> None:
        logger.info(f'Word search bubble press: "{title_str}" page {page_to_goto}.')
        self._speech_bubble_popup.dismiss()
        Clock.schedule_once(lambda _dt: self._goto_title_with_page(title_str, page_to_goto), 0.01)

    def _goto_title_with_page(self, title_str: str, page_to_goto: str) -> None:
        if title_str not in BARKS_TITLE_DICT:
            return
        title = BARKS_TITLE_DICT[title_str]
        image_info = ImageInfo(from_title=title, filename=None)
        if self.on_goto_title_with_page:
            self.on_goto_title_with_page(image_info, page_to_goto)

    def on_word_clear(self) -> None:
        self._cancel_image_change_event()
        self.ids.word_search_input.text = ""
        self.ids.word_chips_layout.clear_widgets()
        self.ids.word_results_layout.clear_widgets()
        self.ids.word_search_input.focus = True

    # --- Background Image Update from Results ---

    def _update_background_from_results(self, titles: list[Titles]) -> None:
        if not titles or not self.on_search_results_title_changed:
            return
        self._search_result_titles = titles
        self._cancel_image_change_event()
        self.on_search_results_title_changed(random.choice(titles))
        self._image_change_event = Clock.schedule_interval(
            lambda _dt: self._next_background_image(), SEARCH_IMAGE_CHANGE_SECONDS
        )

    def _next_background_image(self) -> None:
        if not self._search_result_titles or not self.on_search_results_title_changed:
            return
        self.on_search_results_title_changed(random.choice(self._search_result_titles))

    def _cancel_image_change_event(self) -> None:
        if self._image_change_event:
            self._image_change_event.cancel()
            self._image_change_event = None

    # --- Background Image ---

    def set_background_image(self, image_info: ImageInfo) -> None:
        self._current_image_info = image_info
        self.current_title_str = (
            "" if image_info.from_title is None else BARKS_TITLES[image_info.from_title]
        )

    def on_goto_background_title(self) -> None:
        if self.on_goto_background_title_func and self._current_image_info:
            self.on_goto_background_title_func(self._current_image_info)

    def _on_change_show_current_title(self) -> None:
        self.show_current_title = self._reader_settings.show_fun_view_title_info

    # --- Keyboard Navigation ---

    def enter_nav_focus(self, on_exit_request: Callable) -> None:
        self._nav_on_exit_request = on_exit_request
        self._nav_active = True
        self._nav_focus_area = "input"
        self._focus_active_input()
        logger.debug("SearchScreen: entered nav focus.")

    def enter_nav_focus_at_last_result(self, on_exit_request: Callable) -> None:
        """Enter nav focus, restoring focus to the last activated result if available."""
        self._nav_on_exit_request = on_exit_request
        self._nav_active = True
        rows = self._get_active_result_rows()
        if self._last_activated_result_idx is not None and rows:
            self._nav_focus_area = "results"
            self._nav_focused_result_idx = min(self._last_activated_result_idx, len(rows) - 1)
            self._nav_word_sub_focus = self._last_activated_word_sub_focus
            Clock.schedule_once(
                lambda _dt: Clock.schedule_once(lambda _dt2: self._draw_result_focus())
            )
        else:
            self._nav_focus_area = "input"
            self._focus_active_input()
        logger.debug("SearchScreen: entered nav focus at last result.")

    def exit_nav_focus(self) -> None:
        self._blur_all_inputs()
        self._clear_result_focus()
        self._clear_chip_focus()
        self._clear_clear_focus()
        self._nav_active = False
        self._nav_focus_area = "input"
        logger.debug("SearchScreen: exited nav focus.")

    def handle_key(self, key: int) -> bool:
        if self._popup_nav.is_open:
            return self._popup_nav.handle_key(key)

        if not self._nav_active:
            return False

        handlers = {
            "input": self._handle_input_key,
            "clear": self._handle_clear_key,
            "tags": self._handle_tags_key,
            "results": self._handle_results_key,
        }
        handler = handlers.get(self._nav_focus_area)
        # noinspection PyArgumentList
        return handler(key) if handler else False

    def _handle_input_key(self, key: int) -> bool:
        if key == KEY_ESCAPE:
            self._blur_all_inputs()
            if self._nav_on_exit_request:
                self._nav_on_exit_request()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER, KEY_TAB, KEY_DOWN):
            self._blur_all_inputs()
            self._nav_to_tags_or_results()
        elif key == KEY_RIGHT:
            text_input = self._active_widget(0)
            if text_input.cursor_index() >= len(text_input.text):
                self._blur_all_inputs()
                self._nav_enter_results()
                self._draw_result_focus()
            else:
                return False
        else:
            # Let the text input handle the key
            return False
        return True

    def _nav_to_tags_or_results(self) -> None:
        if self._active_mode in ("Tag", "Word") and self._get_active_chip_buttons():
            self._nav_focus_area = "tags"
            self._nav_focused_chip_idx = 0
            self._draw_chip_focus()
        else:
            self._nav_enter_results()
            self._draw_result_focus()

    def _handle_results_key(self, key: int) -> bool:
        rows = self._get_active_result_rows()
        if key == KEY_UP:
            if self._nav_focused_result_idx <= 0:
                return True
            self._nav_focused_result_idx -= 1
            self._nav_word_sub_focus = "title"
            self._draw_result_focus()
        elif key == KEY_DOWN:
            if rows and self._nav_focused_result_idx < len(rows) - 1:
                self._nav_focused_result_idx += 1
                self._nav_word_sub_focus = "title"
                self._draw_result_focus()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            focused = self._get_focused_result_widget(rows)
            if focused is not None:
                self._last_activated_result_idx = self._nav_focused_result_idx
                self._last_activated_word_sub_focus = self._nav_word_sub_focus
                focused.trigger_action(duration=0)
        elif key in (KEY_LEFT, KEY_RIGHT):
            return self._handle_results_left_right(key)
        elif key == KEY_TAB:
            self._clear_result_focus()
            self._nav_focus_area = "input"
            self._focus_active_input()
        elif key == KEY_ESCAPE:
            self._nav_escape()
        else:
            return False
        return True

    def _handle_results_left_right(self, key: int) -> bool:
        if key == KEY_RIGHT:
            if self._active_mode == "Word" and self._nav_word_sub_focus == "title":
                self._nav_word_sub_focus = "speech"
                self._draw_result_focus()
                return True
            return False
        # KEY_LEFT
        if self._active_mode == "Word" and self._nav_word_sub_focus == "speech":
            self._nav_word_sub_focus = "title"
            self._draw_result_focus()
        elif self._active_mode == "Word" and self._get_word_chip_buttons():
            self._clear_result_focus()
            self._nav_focus_area = "tags"
            word_buttons = self._get_word_chip_buttons()
            selected_idx = next(
                (i for i, b in enumerate(word_buttons) if b.text == self._selected_word), 0
            )
            self._nav_focused_chip_idx = selected_idx
            self._draw_chip_focus()
        elif self._active_mode == "Tag" and self._get_tag_chip_buttons():
            self._clear_result_focus()
            self._nav_focus_area = "tags"
            tag_chips = self._get_tag_chip_buttons()
            # Go back to the selected member chip if one is active, otherwise the group chip
            target = self._selected_member or self._selected_tag
            selected_idx = next((i for i, c in enumerate(tag_chips) if c.text == target), 0)
            self._nav_focused_chip_idx = selected_idx
            self._draw_chip_focus()
        else:
            self._clear_result_focus()
            self._nav_focus_area = "clear"
            self._draw_clear_focus()
        return True

    def _nav_enter_results(self) -> None:
        self._nav_focus_area = "results"
        self._nav_focused_result_idx = 0
        self._nav_word_sub_focus = "title"

    def _nav_up_from_results(self) -> None:
        if self._active_mode in ("Tag", "Word") and self._get_active_chip_buttons():
            self._nav_focus_area = "tags"
            chips = self._get_active_chip_buttons()
            self._nav_focused_chip_idx = len(chips) - 1
            self._draw_chip_focus()
        else:
            self._nav_focus_area = "input"
            self._focus_active_input()

    def _nav_escape(self) -> None:
        self._clear_result_focus()
        self._clear_chip_focus()
        self._clear_clear_focus()
        self._nav_focus_area = "input"
        self._blur_all_inputs()
        if self._nav_on_exit_request:
            self._nav_on_exit_request()

    def _handle_clear_key(self, key: int) -> bool:
        if key == KEY_LEFT:
            self._clear_clear_focus()
            self._nav_focus_area = "input"
            self._focus_active_input()
        elif key == KEY_RIGHT:
            self._clear_clear_focus()
            self._nav_enter_results()
            self._draw_result_focus()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._get_active_clear_button().trigger_action(duration=0)
            self._clear_clear_focus()
            self._nav_focus_area = "input"
        elif key == KEY_ESCAPE:
            self._nav_escape()
        else:
            return False
        return True

    def _handle_tags_key(self, key: int) -> bool:
        chips = self._get_active_chip_buttons()
        if key == KEY_DOWN:
            if chips and self._nav_focused_chip_idx < len(chips) - 1:
                self._nav_focused_chip_idx += 1
                self._draw_chip_focus()
        elif key == KEY_RIGHT:
            self._clear_chip_focus()
            self._nav_enter_results()
            self._draw_result_focus()
        elif key in (KEY_LEFT, KEY_UP):
            if self._nav_focused_chip_idx > 0:
                self._nav_focused_chip_idx -= 1
                self._draw_chip_focus()
            else:
                self._clear_chip_focus()
                self._nav_focus_area = "input"
                self._focus_active_input()
        elif key == KEY_TAB:
            self._clear_chip_focus()
            self._nav_enter_results()
            self._draw_result_focus()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._handle_tags_enter(chips)
        elif key == KEY_ESCAPE:
            self._nav_escape()
        else:
            return False
        return True

    def _handle_tags_enter(self, chips: list[Button]) -> None:
        if not chips or self._nav_focused_chip_idx >= len(chips):
            return
        focused_chip = chips[self._nav_focused_chip_idx]
        was_main = focused_chip in self._get_main_tag_chip_buttons()
        is_open_group = (
            was_main and focused_chip.text == self._selected_tag and self._get_member_chip_buttons()
        )
        if is_open_group:
            # Collapse the open group: show the group's own titles
            self._selected_member = ""
            self._current_tag = None
            self._rebuild_tag_chips()
            self._show_tag_titles(self._selected_tag)
            new_chips = self._get_tag_chip_buttons()
            self._nav_focused_chip_idx = next(
                (i for i, c in enumerate(new_chips) if c.text == self._selected_tag), 0
            )
            self._draw_chip_focus()
            return
        focused_chip.trigger_action(duration=0)
        self._clear_chip_focus()
        # If a main group chip was selected, focus and select the first member chip
        member_chips = self._get_member_chip_buttons()
        if was_main and self._active_mode == "Tag" and member_chips:
            all_chips = self._get_tag_chip_buttons()
            selected_idx = next(
                (i for i, c in enumerate(all_chips) if c.text == self._selected_tag), -1
            )
            self._nav_focused_chip_idx = selected_idx + 1
            member_chips[0].trigger_action(duration=0)
            Clock.schedule_once(
                lambda _dt: Clock.schedule_once(lambda _dt2: self._draw_chip_focus())
            )
        else:
            self._nav_enter_results()
            Clock.schedule_once(
                lambda _dt: Clock.schedule_once(lambda _dt2: self._draw_result_focus())
            )

    def _get_main_tag_chip_buttons(self) -> list[_TagChipButton]:
        if not hasattr(self.ids, "tag_chips_layout"):
            return []
        result: list[_TagChipButton] = []
        for stack in reversed(self.ids.tag_chips_layout.children):
            if not getattr(stack, "is_member_layout", False):
                result.extend(reversed(stack.children))
        return result

    def _get_member_chip_buttons(self) -> list[_TagChipButton]:
        if not hasattr(self.ids, "tag_chips_layout"):
            return []
        result: list[_TagChipButton] = []
        for stack in reversed(self.ids.tag_chips_layout.children):
            if getattr(stack, "is_member_layout", False):
                result.extend(reversed(stack.children))
        return result

    def _get_tag_chip_buttons(self) -> list[_TagChipButton]:
        """Return all tag chips (main + member) in visual order for keyboard nav."""
        if not hasattr(self.ids, "tag_chips_layout"):
            return []
        result: list[_TagChipButton] = []
        for stack in reversed(self.ids.tag_chips_layout.children):
            result.extend(reversed(stack.children))
        return result

    def _get_word_chip_buttons(self) -> list[Button]:
        if not hasattr(self.ids, "word_chips_layout"):
            return []
        return list(reversed(self.ids.word_chips_layout.children))

    def _get_active_chip_buttons(self) -> list[Button]:
        if self._active_mode == "Word":
            return self._get_word_chip_buttons()
        return self._get_tag_chip_buttons()

    def _update_tag_chip_colors(
        self, chips: list[_TagChipButton], focused_idx: int | None = None
    ) -> None:
        """Set bg and border colors on tag chips. If focused_idx is given, highlight that chip."""
        main_chips = {id(c) for c in self._get_main_tag_chip_buttons()}
        for i, chip in enumerate(chips):
            is_main = id(chip) in main_chips
            if is_main:
                is_selected = chip.text == self._selected_tag
                chip.chip_bg_color = _CHIP_BG_ACTIVE if is_selected else _CHIP_BG_NORMAL
            else:
                is_selected = chip.text == self._selected_member
                chip.chip_bg_color = _CHIP_BG_ACTIVE if is_selected else _CHIP_BG_MEMBER
            chip.chip_border_color = _CHIP_BORDER_FOCUSED if i == focused_idx else _CHIP_BORDER_NONE

    def _draw_chip_focus(self) -> None:
        chips = self._get_active_chip_buttons()
        if not chips:
            return
        self._nav_focused_chip_idx = min(self._nav_focused_chip_idx, len(chips) - 1)
        if self._active_mode == "Word":
            update_focus_in_list(chips, self._nav_focused_chip_idx, _SEARCH_NAV_FOCUS_GROUP)
            self.ids.word_chips_scroll.scroll_to(chips[self._nav_focused_chip_idx])
        else:
            self._update_tag_chip_colors(chips, self._nav_focused_chip_idx)

    def _clear_chip_focus(self) -> None:
        chips = self._get_active_chip_buttons()
        if self._active_mode == "Word":
            clear_focus_in_list(chips, _SEARCH_NAV_FOCUS_GROUP)
        else:
            self._update_tag_chip_colors(chips)

    _CLEAR_BTN_NORMAL = (0.35, 0.35, 0.35, 1.0)
    _CLEAR_BTN_FOCUSED = (0.0, 0.5, 0.0, 1.0)

    def _active_widget(self, index: int):  # noqa: ANN202
        """Return the widget for the active mode at the given _MODE_WIDGETS index."""
        return self.ids[self._MODE_WIDGETS[self._active_mode][index]]

    def _get_active_clear_button(self) -> Button:
        return self._active_widget(1)

    def _draw_clear_focus(self) -> None:
        self._get_active_clear_button().background_color = self._CLEAR_BTN_FOCUSED

    def _clear_clear_focus(self) -> None:
        self._get_active_clear_button().background_color = self._CLEAR_BTN_NORMAL

    def _focus_active_input(self) -> None:
        self._active_widget(0).focus = True

    def _blur_all_inputs(self) -> None:
        for _input_id, _, _, _ in self._MODE_WIDGETS.values():
            self.ids[_input_id].focus = False

    def _get_active_results_scroll_view(self) -> ScrollView:
        return self._active_widget(2)

    def _get_active_result_rows(self) -> list[Button]:
        return list(reversed(self._active_widget(3).children))

    def _get_focused_result_widget(self, rows: list) -> Button | None:
        if not rows:
            return None
        idx = min(self._nav_focused_result_idx, len(rows) - 1)
        row = rows[idx]
        if self._active_mode == "Word" and hasattr(row, "children") and row.children:
            children = list(reversed(row.children))
            sub_idx = 1 if self._nav_word_sub_focus == "speech" else 0
            return children[min(sub_idx, len(children) - 1)]
        return row

    def _get_all_focusable_widgets(self, rows: list) -> list:
        if self._active_mode != "Word":
            return rows
        widgets = []
        for row in rows:
            if hasattr(row, "children") and row.children:
                widgets.extend(reversed(row.children))
            else:
                widgets.append(row)
        return widgets

    def _draw_result_focus(self) -> None:
        rows = self._get_active_result_rows()
        if not rows:
            return
        self._nav_focused_result_idx = min(self._nav_focused_result_idx, len(rows) - 1)
        all_widgets = self._get_all_focusable_widgets(rows)
        focused = self._get_focused_result_widget(rows)
        if focused is None:
            return
        try:
            focus_idx = all_widgets.index(focused)
        except ValueError:
            return
        update_focus_in_list(all_widgets, focus_idx, _SEARCH_NAV_FOCUS_GROUP)
        scroll_view = self._get_active_results_scroll_view()
        scroll_target = rows[self._nav_focused_result_idx]
        scroll_view.scroll_to(scroll_target)

    def _clear_result_focus(self) -> None:
        rows = self._get_active_result_rows()
        all_widgets = self._get_all_focusable_widgets(rows)
        clear_focus_in_list(all_widgets, _SEARCH_NAV_FOCUS_GROUP)
