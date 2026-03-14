from __future__ import annotations

import random
from pathlib import Path
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import BARKS_TITLE_DICT, BARKS_TITLES, Titles
from barks_fantagraphics.title_search import BarksTitleSearch
from barks_fantagraphics.whoosh_search_engine import SearchEngine, TitleInfo
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from loguru import logger

from barks_reader.core.random_title_images import ImageInfo
from barks_reader.core.reader_formatter import get_fitted_title_with_page_nums
from barks_reader.core.reader_settings import BARKS_READER_SECTION, SHOW_FUN_VIEW_TITLE_INFO
from barks_reader.core.reader_utils import unique_extend
from barks_reader.core.settings_notifier import settings_notifier
from barks_reader.ui.index_screen import (
    PopupKeyboardNav,
    SpeechBubblesPopup,
    TitleShowSpeechButton,
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

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.scrollview import ScrollView

    from barks_reader.core.reader_settings import ReaderSettings
    from barks_reader.ui.font_manager import FontManager

SEARCH_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

MAX_WORD_SEARCH_TITLE_AND_PAGES_LEN = 50

_SEARCH_NAV_FOCUS_GROUP = "search_nav_focus"


class _SearchResultButton(Button):
    """A clickable result row in a search results list."""


_CHIP_BG_NORMAL = (0.2, 0.35, 0.2, 1)
_CHIP_BG_SELECTED = (0.3, 0.55, 0.3, 1)


class _TagChipButton(Button):
    """A pill-shaped tag chip button for tag search results."""

    chip_bg_color = ObjectProperty(_CHIP_BG_NORMAL)

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self.texture_update()
        self.width = self.texture_size[0] + dp(24)


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

    def __init__(
        self,
        reader_settings: ReaderSettings,
        font_manager: FontManager,
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)
        self._reader_settings = reader_settings
        self._font_manager = font_manager
        self._title_search = BarksTitleSearch()
        self._whoosh_indexer = SearchEngine(
            reader_settings.sys_file_paths.get_barks_reader_indexes_dir()
        )

        self._current_image_info: ImageInfo | None = None
        self.on_goto_background_title_func: Callable[[ImageInfo], None] | None = None
        self.on_search_results_title_changed: Callable[[Titles], None] | None = None
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
        self._tag_titles: list[str] = []

        # Word search state
        self._word_search_results: list[tuple[str, str, str, TitleInfo]] = []

        # Last activated result (for restoring focus after go-back)
        self._last_activated_result_idx: int | None = None
        self._last_activated_word_sub_focus: str = "title"

        self._speech_bubble_popup = SpeechBubblesPopup(
            title_font=self._font_manager.speech_bubble_popup_title_font_name,
            title_align="left",
            title_color=[0, 1, 1, 1],
            size_hint=(0.7, 0.4),
            pos_hint={"x": 0.06, "y": 0.06},
        )
        self._speech_bubble_popup.children[0].children[-1].markup = True
        self._popup_nav = PopupKeyboardNav(self._speech_bubble_popup)

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
            widget.size_hint = (1, 1) if active else (0, 0)

        logger.debug(f"SearchScreen mode set to '{mode}'.")

    # --- Title Search ---

    def on_title_search_text(self, text: str) -> None:
        results_layout: BoxLayout = self.ids.title_results_layout
        results_layout.clear_widgets()

        if len(text) <= 1:
            return

        title_enums, title_strings = self._get_titles_matching(text)
        for title_str in title_strings:
            btn = _SearchResultButton(text=title_str)
            btn.bind(on_release=lambda _b, t=title_str: self._on_title_result_selected(t))
            results_layout.add_widget(btn)

        self._update_background_from_results(title_enums)

    def _get_titles_matching(self, value: str) -> tuple[list[Titles], list[str]]:
        title_list = self._title_search.get_titles_matching_prefix(value)
        min_title_chars_len = 2
        if len(value) > min_title_chars_len:
            if not title_list:
                title_list = self._title_search.get_titles_from_issue_num(value)
            if not title_list:
                unique_extend(title_list, self._title_search.get_titles_containing(value))
        return title_list, self._title_search.get_titles_as_strings(title_list)

    def _on_title_result_selected(self, title_str: str) -> None:
        logger.info(f'Title search: selected "{title_str}".')
        if self.on_goto_title:
            self.on_goto_title(title_str)

    def on_title_clear(self) -> None:
        self.ids.title_search_input.text = ""
        self.ids.title_search_input.focus = True

    # --- Tag Search ---

    def on_tag_search_text(self, text: str) -> None:
        chips_layout = self.ids.tag_chips_layout
        chips_layout.clear_widgets()
        self._clear_tag_title_results()

        if len(text) <= 1:
            return

        found_tags = self._title_search.get_tags_matching_prefix(text)
        tags = sorted([str(t.value) for t in found_tags]) if found_tags else []

        for tag_str in tags:
            btn = _TagChipButton(text=tag_str)
            btn.bind(on_release=lambda _b, t=tag_str: self._on_tag_result_selected(t))
            chips_layout.add_widget(btn)

        if len(tags) == 1:
            self._on_tag_result_selected(tags[0])

    def _on_tag_result_selected(self, tag_str: str) -> None:
        logger.info(f'Tag search: selected tag "{tag_str}".')
        self._current_tag, titles = self._title_search.get_titles_from_alias_tag(tag_str.lower())
        self._tag_titles = self._title_search.get_titles_as_strings(titles) if titles else []

        title_results_layout: BoxLayout = self.ids.tag_title_results_layout
        title_results_layout.clear_widgets()
        for title_str in self._tag_titles:
            btn = _SearchResultButton(text=title_str)
            btn.bind(on_release=lambda _b, t=title_str: self._on_tag_title_result_selected(t))
            title_results_layout.add_widget(btn)

        self._update_background_from_results(titles or [])

    def _on_tag_title_result_selected(self, title_str: str) -> None:
        logger.info(f'Tag search: selected title "{title_str}".')
        if self.on_goto_title:
            self.on_goto_title(title_str)

    def _clear_tag_title_results(self) -> None:
        self.ids.tag_title_results_layout.clear_widgets()
        self._tag_titles = []

    def on_tag_clear(self) -> None:
        self.ids.tag_search_input.text = ""
        self.ids.tag_chips_layout.clear_widgets()
        self._clear_tag_title_results()
        self.ids.tag_search_input.focus = True

    # --- Word Search ---

    def on_word_search_submit(self) -> None:
        search_text = self.ids.word_search_input.text.strip()
        if not search_text:
            return

        logger.info(f'Word search: "{search_text}".')
        found = self._whoosh_indexer.find_all_words(search_text)

        results_layout: BoxLayout = self.ids.word_results_layout
        results_layout.clear_widgets()
        self._word_search_results = []

        for comic_title, title_speech_info in found.items():
            page_num_list = [page.comic_page for page in title_speech_info.fanta_pages.values()]
            first_page_num, title_with_pages = get_fitted_title_with_page_nums(
                comic_title, page_num_list, MAX_WORD_SEARCH_TITLE_AND_PAGES_LEN
            )
            self._word_search_results.append(
                (comic_title, first_page_num, title_with_pages, title_speech_info)
            )

        self._word_search_results.sort(key=lambda t: t[2])

        for (
            comic_title,
            first_page_num,
            title_with_pages,
            title_speech_info,
        ) in self._word_search_results:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(28))

            title_btn = _SearchResultButton(
                text=title_with_pages,
                size_hint=(0.9, 1),
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

            speech_btn = TitleShowSpeechButton(size_hint=(0.1, 1))
            speech_btn.bind(
                on_release=lambda _b, ct=comic_title, tsi=title_speech_info: (
                    self._show_word_speech_bubbles(ct, tsi)
                ),
            )
            row.add_widget(speech_btn)

            results_layout.add_widget(row)

        if not found:
            no_results = _SearchResultButton(
                text=f'No results for "{search_text}"',
                disabled=True,
            )
            results_layout.add_widget(no_results)
            self._nav_focus_area = "input"
            Clock.schedule_once(lambda _dt: self._focus_active_input())
            return

        word_result_titles = [BARKS_TITLE_DICT[ct] for ct in found if ct in BARKS_TITLE_DICT]
        self._update_background_from_results(word_result_titles)

        if found:
            self._nav_active = True
            self._blur_all_inputs()
            self._nav_enter_results()
            # Two frames: first for layout, second for drawing the highlight.
            Clock.schedule_once(
                lambda _dt: Clock.schedule_once(lambda _dt2: self._draw_result_focus())
            )

    def _on_word_title_selected(self, title_str: str, page_to_goto: str) -> None:
        logger.info(f'Word search: navigating to "{title_str}", page {page_to_goto}.')
        self._goto_title_with_page(title_str, page_to_goto)

    def _show_word_speech_bubbles(self, title_str: str, title_speech_info: TitleInfo) -> None:
        search_text = self.ids.word_search_input.text.strip()
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
        self.ids.word_search_input.text = ""
        self.ids.word_results_layout.clear_widgets()
        self.ids.word_search_input.focus = True

    # --- Background Image Update from Results ---

    def _update_background_from_results(self, titles: list[Titles]) -> None:
        if not titles or not self.on_search_results_title_changed:
            return
        self.on_search_results_title_changed(random.choice(titles))

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
        return handler(key) if handler else False

    def _handle_input_key(self, key: int) -> bool:
        if key == KEY_ESCAPE:
            self._blur_all_inputs()
            if self._nav_on_exit_request:
                self._nav_on_exit_request()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            if self._active_mode == "Word":
                # Let the TextInput's on_text_validate handle the search
                return False
            self._blur_all_inputs()
            self._nav_to_tags_or_results()
        elif key in (KEY_TAB, KEY_DOWN):
            self._blur_all_inputs()
            self._nav_to_tags_or_results()
        else:
            # Let the text input handle the key
            return False
        return True

    def _nav_to_tags_or_results(self) -> None:
        if self._active_mode == "Tag" and self._get_tag_chip_buttons():
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
                self._clear_result_focus()
                self._nav_up_from_results()
            else:
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
        if self._active_mode == "Tag" and self._get_tag_chip_buttons():
            self._nav_focus_area = "tags"
            chips = self._get_tag_chip_buttons()
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
        chips = self._get_tag_chip_buttons()
        if key in (KEY_RIGHT, KEY_DOWN):
            if chips and self._nav_focused_chip_idx < len(chips) - 1:
                self._nav_focused_chip_idx += 1
                self._draw_chip_focus()
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
            if chips and self._nav_focused_chip_idx < len(chips):
                chips[self._nav_focused_chip_idx].trigger_action(duration=0)
                self._clear_chip_focus()
                self._nav_enter_results()
                Clock.schedule_once(lambda _dt: self._draw_result_focus())
        elif key == KEY_ESCAPE:
            self._nav_escape()
        else:
            return False
        return True

    def _get_tag_chip_buttons(self) -> list[_TagChipButton]:
        if not hasattr(self.ids, "tag_chips_layout"):
            return []
        return list(reversed(self.ids.tag_chips_layout.children))

    def _draw_chip_focus(self) -> None:
        chips = self._get_tag_chip_buttons()
        if not chips:
            return
        self._nav_focused_chip_idx = min(self._nav_focused_chip_idx, len(chips) - 1)
        for i, chip in enumerate(chips):
            is_focused = i == self._nav_focused_chip_idx
            chip.chip_bg_color = _CHIP_BG_SELECTED if is_focused else _CHIP_BG_NORMAL

    def _clear_chip_focus(self) -> None:
        chips = self._get_tag_chip_buttons()
        for chip in chips:
            chip.chip_bg_color = _CHIP_BG_NORMAL

    _CLEAR_BTN_NORMAL = (0.35, 0.35, 0.35, 1.0)
    _CLEAR_BTN_FOCUSED = (0.0, 0.5, 0.0, 1.0)

    def _get_active_clear_button(self) -> Button:
        if self._active_mode == "Title":
            return self.ids.title_clear_button
        if self._active_mode == "Tag":
            return self.ids.tag_clear_button
        return self.ids.word_clear_button

    def _draw_clear_focus(self) -> None:
        self._get_active_clear_button().background_color = self._CLEAR_BTN_FOCUSED

    def _clear_clear_focus(self) -> None:
        self._get_active_clear_button().background_color = self._CLEAR_BTN_NORMAL

    def _focus_active_input(self) -> None:
        if self._active_mode == "Title":
            self.ids.title_search_input.focus = True
        elif self._active_mode == "Tag":
            self.ids.tag_search_input.focus = True
        elif self._active_mode == "Word":
            self.ids.word_search_input.focus = True

    def _blur_all_inputs(self) -> None:
        self.ids.title_search_input.focus = False
        self.ids.tag_search_input.focus = False
        self.ids.word_search_input.focus = False

    def _get_active_results_scroll_view(self) -> ScrollView:
        if self._active_mode == "Title":
            return self.ids.title_results_scroll
        if self._active_mode == "Tag":
            return self.ids.tag_results_scroll
        return self.ids.word_results_scroll

    def _get_active_result_rows(self) -> list[Button]:
        if self._active_mode == "Title":
            layout = self.ids.title_results_layout
        elif self._active_mode == "Tag":
            layout = self.ids.tag_title_results_layout
        elif self._active_mode == "Word":
            layout = self.ids.word_results_layout
        else:
            return []
        return list(reversed(layout.children))

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
