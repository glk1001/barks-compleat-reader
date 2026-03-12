from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import BARKS_TITLE_DICT
from barks_fantagraphics.title_search import BarksTitleSearch
from barks_fantagraphics.whoosh_search_engine import SearchEngine, TitleInfo
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    ObjectProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from loguru import logger

from barks_reader.core.random_title_images import ImageInfo
from barks_reader.core.reader_formatter import get_fitted_title_with_page_nums, mark_phrase_in_text
from barks_reader.core.reader_utils import unique_extend
from barks_reader.ui.index_screen import (
    SpeechBubblesPopup,
    TextBoxWithTitleAndBorder,
    TitleShowSpeechButton,
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

    from barks_reader.core.reader_settings import ReaderSettings
    from barks_reader.ui.font_manager import FontManager

SEARCH_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

MAX_WORD_SEARCH_TITLE_AND_PAGES_LEN = 50

INDEX_TERMS_HIGHLIGHT_COLOR = "#1A6ABB"
INDEX_TERMS_HIGHLIGHT_START_TAG = f"[b][color={INDEX_TERMS_HIGHLIGHT_COLOR}]"
INDEX_TERMS_HIGHLIGHT_END_TAG = "[/color][/b]"

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
        self._font_manager = font_manager
        self._title_search = BarksTitleSearch()
        self._whoosh_indexer = SearchEngine(
            reader_settings.sys_file_paths.get_barks_reader_indexes_dir()
        )

        self._active_mode: str = "Title"

        self._nav_active: bool = False
        self._nav_on_exit_request: Callable | None = None
        self._nav_focus_area: str = "input"  # "input", "clear", "tags", "results"
        self._nav_focused_result_idx: int = 0
        self._nav_focused_chip_idx: int = 0

        # Tag search state
        self._current_tag = None
        self._tag_titles: list[str] = []

        # Word search state
        self._word_search_results: list[tuple[str, str, str, TitleInfo]] = []

        self._speech_bubble_popup = SpeechBubblesPopup(
            title_font=self._font_manager.speech_bubble_popup_title_font_name,
            title_align="left",
            title_color=[0, 1, 1, 1],
            size_hint=(0.7, 0.4),
            pos_hint={"x": 0.06, "y": 0.06},
        )
        self._speech_bubble_popup.children[0].children[-1].markup = True

    def set_mode(self, mode: str) -> None:
        """Switch to the given search mode: 'Title', 'Tag', or 'Word'."""
        self._active_mode = mode

        self.ids.title_search_content.opacity = 1 if mode == "Title" else 0
        self.ids.title_search_content.size_hint = (1, 1) if mode == "Title" else (0, 0)

        self.ids.tag_search_content.opacity = 1 if mode == "Tag" else 0
        self.ids.tag_search_content.size_hint = (1, 1) if mode == "Tag" else (0, 0)

        self.ids.word_search_content.opacity = 1 if mode == "Word" else 0
        self.ids.word_search_content.size_hint = (1, 1) if mode == "Word" else (0, 0)

        logger.debug(f"SearchScreen mode set to '{mode}'.")

    # --- Title Search ---

    def on_title_search_text(self, text: str) -> None:
        results_layout: BoxLayout = self.ids.title_results_layout
        results_layout.clear_widgets()

        if len(text) <= 1:
            return

        titles = self._get_titles_matching(text)
        for title_str in titles:
            btn = _SearchResultButton(text=title_str)
            btn.bind(on_release=lambda _b, t=title_str: self._on_title_result_selected(t))
            results_layout.add_widget(btn)

    def _get_titles_matching(self, value: str) -> list[str]:
        title_list = self._title_search.get_titles_matching_prefix(value)
        min_title_chars_len = 2
        if len(value) > min_title_chars_len:
            if not title_list:
                title_list = self._title_search.get_titles_from_issue_num(value)
            if not title_list:
                unique_extend(title_list, self._title_search.get_titles_containing(value))
        return self._title_search.get_titles_as_strings(title_list)

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

    def _on_word_title_selected(self, title_str: str, page_to_goto: str) -> None:
        logger.info(f'Word search: navigating to "{title_str}", page {page_to_goto}.')
        if title_str not in BARKS_TITLE_DICT:
            return
        title = BARKS_TITLE_DICT[title_str]
        image_info = ImageInfo(from_title=title, filename=None)
        if self.on_goto_title_with_page:
            self.on_goto_title_with_page(image_info, page_to_goto)

    def _show_word_speech_bubbles(self, title_str: str, title_speech_info: TitleInfo) -> None:
        search_text = self.ids.word_search_input.text.strip()
        logger.info(f'Show speech bubbles for: "{title_str}" and search "{search_text}".')

        text_boxes = GridLayout(cols=1, size_hint_y=None, spacing=dp(30), padding=dp(30))
        text_boxes.bind(minimum_height=text_boxes.setter("height"))

        for page_info in title_speech_info.fanta_pages.values():
            page_text = f"Page {page_info.comic_page}"
            text = "\n\n".join([s.speech_text for s in page_info.speech_info_list])
            text = mark_phrase_in_text(
                search_text,
                text,
                INDEX_TERMS_HIGHLIGHT_START_TAG,
                INDEX_TERMS_HIGHLIGHT_END_TAG,
            )
            text = text.replace("\u00ad", "-")
            text_box = TextBoxWithTitleAndBorder(title=page_text, content=text.strip())
            text_box.ids.the_text_id.bind(
                on_release=lambda _btn, bt=title_str, bp=page_info.comic_page: (
                    self._handle_bubble_title_press(bt, bp)
                ),
            )
            text_boxes.add_widget(text_box)

        scroll_view = ScrollView(
            always_overscroll=False,
            effect_cls="ScrollEffect",
            scroll_type=["bars", "content"],
            bar_color=(0.8, 0.8, 0.8, 1),
            bar_inactive_color=(0.8, 0.8, 0.8, 0.8),
            bar_width=dp(8),
        )
        scroll_view.add_widget(text_boxes)

        self._speech_bubble_popup.title = f"[b][i]{title_str}  \u2014  [/i]'{search_text}'[/b]"
        self._speech_bubble_popup.title_size = (
            self._font_manager.speech_bubble_popup_title_font_size
        )
        self._speech_bubble_popup.content = scroll_view
        self._speech_bubble_popup.open()

    def _handle_bubble_title_press(self, title_str: str, page_to_goto: str) -> None:
        logger.info(f'Word search bubble press: "{title_str}" page {page_to_goto}.')
        self._speech_bubble_popup.dismiss()

        if title_str not in BARKS_TITLE_DICT:
            return
        title = BARKS_TITLE_DICT[title_str]
        image_info = ImageInfo(from_title=title, filename=None)

        def goto_title() -> None:
            if self.on_goto_title_with_page:
                self.on_goto_title_with_page(image_info, page_to_goto)

        Clock.schedule_once(lambda _dt: goto_title(), 0.01)

    def on_word_clear(self) -> None:
        self.ids.word_search_input.text = ""
        self.ids.word_results_layout.clear_widgets()
        self.ids.word_search_input.focus = True

    # --- Keyboard Navigation ---

    def enter_nav_focus(self, on_exit_request: Callable) -> None:
        self._nav_on_exit_request = on_exit_request
        self._nav_active = True
        self._nav_focus_area = "input"
        self._focus_active_input()
        logger.debug("SearchScreen: entered nav focus.")

    def exit_nav_focus(self) -> None:
        self._blur_all_inputs()
        self._clear_result_focus()
        self._clear_chip_focus()
        self._clear_clear_focus()
        self._nav_active = False
        self._nav_focus_area = "input"
        logger.debug("SearchScreen: exited nav focus.")

    def handle_key(self, key: int) -> bool:
        if not self._nav_active:
            return False

        if self._nav_focus_area == "input":
            return self._handle_input_key(key)
        if self._nav_focus_area == "clear":
            return self._handle_clear_key(key)
        if self._nav_focus_area == "tags":
            return self._handle_tags_key(key)
        if self._nav_focus_area == "results":
            return self._handle_results_key(key)
        return False

    def _handle_input_key(self, key: int) -> bool:
        if key == KEY_ESCAPE:
            self._blur_all_inputs()
            if self._nav_on_exit_request:
                self._nav_on_exit_request()
        elif key in (KEY_TAB, KEY_DOWN, KEY_ENTER, KEY_NUMPAD_ENTER):
            self._blur_all_inputs()
            if self._active_mode == "Tag" and self._get_tag_chip_buttons():
                self._nav_focus_area = "tags"
                self._nav_focused_chip_idx = 0
                self._draw_chip_focus()
            else:
                self._nav_focus_area = "results"
                self._nav_focused_result_idx = 0
                self._draw_result_focus()
        else:
            # Let the text input handle the key
            return False
        return True

    def _handle_results_key(self, key: int) -> bool:
        results = self._get_active_result_buttons()
        if key == KEY_UP:
            if self._nav_focused_result_idx <= 0:
                self._clear_result_focus()
                self._nav_up_from_results()
            else:
                self._nav_focused_result_idx -= 1
                self._draw_result_focus()
        elif key == KEY_DOWN:
            if results and self._nav_focused_result_idx < len(results) - 1:
                self._nav_focused_result_idx += 1
                self._draw_result_focus()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            if results and self._nav_focused_result_idx < len(results):
                results[self._nav_focused_result_idx].trigger_action(duration=0)
        elif key == KEY_LEFT:
            self._clear_result_focus()
            self._nav_focus_area = "clear"
            self._draw_clear_focus()
        elif key == KEY_TAB:
            self._clear_result_focus()
            self._nav_focus_area = "input"
            self._focus_active_input()
        elif key == KEY_ESCAPE:
            self._nav_escape()
        else:
            return False
        return True

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
            self._nav_focus_area = "results"
            self._nav_focused_result_idx = 0
            self._draw_result_focus()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._get_active_clear_button().trigger_action(duration=0)
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
            self._nav_focus_area = "results"
            self._nav_focused_result_idx = 0
            self._draw_result_focus()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            if chips and self._nav_focused_chip_idx < len(chips):
                chips[self._nav_focused_chip_idx].trigger_action(duration=0)
                self._clear_chip_focus()
                self._nav_focus_area = "results"
                self._nav_focused_result_idx = 0
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

    def _get_active_result_buttons(self) -> list[Button]:
        if self._active_mode == "Title":
            layout = self.ids.title_results_layout
        elif self._active_mode == "Tag":
            layout = self.ids.tag_title_results_layout
        elif self._active_mode == "Word":
            layout = self.ids.word_results_layout
        else:
            return []
        return list(reversed(layout.children))

    def _draw_result_focus(self) -> None:
        results = self._get_active_result_buttons()
        if not results:
            return
        self._nav_focused_result_idx = min(self._nav_focused_result_idx, len(results) - 1)
        update_focus_in_list(results, self._nav_focused_result_idx, _SEARCH_NAV_FOCUS_GROUP)

    def _clear_result_focus(self) -> None:
        results = self._get_active_result_buttons()
        clear_focus_in_list(results, _SEARCH_NAV_FOCUS_GROUP)
