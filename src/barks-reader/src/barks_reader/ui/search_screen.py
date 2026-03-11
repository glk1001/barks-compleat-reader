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
from kivy.uix.togglebutton import ToggleButton
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


class SearchTabButton(ToggleButton):
    """A tab button for the Search screen tab bar."""

    def _do_press(self) -> None:
        if self.state == "normal":
            super()._do_press()


class _SearchResultButton(Button):
    """A clickable result row in a search results list."""


class SearchScreen(FloatLayout):
    """Bottom view screen with three tabbed search modes: Title, Tag, Word."""

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

        self._tab_buttons: list[SearchTabButton] = []
        self._active_tab: str = "Title"

        self._nav_active: bool = False
        self._nav_on_exit_request: Callable | None = None
        self._nav_focused_tab_idx: int = 0
        self._nav_focus_area: str = "tabs"  # "tabs", "input", "results"
        self._nav_focused_result_idx: int = 0

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

        self._build_tabs()

    def _build_tabs(self) -> None:
        menu_layout = self.ids.search_tab_layout
        for label in ("Title", "Tag", "Word"):
            btn = SearchTabButton(text=label, group="search_tabs")
            btn.bind(on_press=lambda _b, tab=label: self._switch_tab(tab))
            menu_layout.add_widget(btn)
            self._tab_buttons.append(btn)

    def on_is_visible(self, _instance: object, value: bool) -> None:
        if value:
            self._activate_tab("Title")

    def _switch_tab(self, tab_name: str) -> None:
        self._activate_tab(tab_name)

    def _activate_tab(self, tab_name: str) -> None:
        self._active_tab = tab_name
        for btn in self._tab_buttons:
            btn.state = "down" if btn.text == tab_name else "normal"

        self.ids.title_search_content.opacity = 1 if tab_name == "Title" else 0
        self.ids.title_search_content.disabled = tab_name != "Title"
        self.ids.title_search_content.size_hint = (1, 1) if tab_name == "Title" else (0, 0)

        self.ids.tag_search_content.opacity = 1 if tab_name == "Tag" else 0
        self.ids.tag_search_content.disabled = tab_name != "Tag"
        self.ids.tag_search_content.size_hint = (1, 1) if tab_name == "Tag" else (0, 0)

        self.ids.word_search_content.opacity = 1 if tab_name == "Word" else 0
        self.ids.word_search_content.disabled = tab_name != "Word"
        self.ids.word_search_content.size_hint = (1, 1) if tab_name == "Word" else (0, 0)

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
        Clock.schedule_once(lambda _dt: setattr(self.ids.title_search_input, "focus", True))

    # --- Tag Search ---

    def on_tag_search_text(self, text: str) -> None:
        tag_results_layout: BoxLayout = self.ids.tag_results_layout
        tag_results_layout.clear_widgets()
        self._clear_tag_title_results()

        if len(text) <= 1:
            return

        found_tags = self._title_search.get_tags_matching_prefix(text)
        tags = sorted([str(t.value) for t in found_tags]) if found_tags else []

        for tag_str in tags:
            btn = _SearchResultButton(text=tag_str)
            btn.bind(on_release=lambda _b, t=tag_str: self._on_tag_result_selected(t))
            tag_results_layout.add_widget(btn)

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
        self._clear_tag_title_results()
        Clock.schedule_once(lambda _dt: setattr(self.ids.tag_search_input, "focus", True))

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
        Clock.schedule_once(lambda _dt: setattr(self.ids.word_search_input, "focus", True))

    # --- Keyboard Navigation ---

    def enter_nav_focus(self, on_exit_request: Callable) -> None:
        self._nav_on_exit_request = on_exit_request
        self._nav_active = True
        self._nav_focus_area = "tabs"
        self._nav_focused_tab_idx = 0
        update_focus_in_list(self._tab_buttons, self._nav_focused_tab_idx, _SEARCH_NAV_FOCUS_GROUP)
        logger.debug("SearchScreen: entered nav focus.")

    def exit_nav_focus(self) -> None:
        clear_focus_in_list(self._tab_buttons, _SEARCH_NAV_FOCUS_GROUP)
        self._nav_active = False
        self._nav_focus_area = "tabs"
        logger.debug("SearchScreen: exited nav focus.")

    def handle_key(self, key: int) -> bool:
        if not self._nav_active:
            return False

        if self._nav_focus_area == "tabs":
            return self._handle_tab_key(key)
        if self._nav_focus_area == "input":
            return self._handle_input_key(key)
        if self._nav_focus_area == "results":
            return self._handle_results_key(key)
        return False

    def _handle_tab_key(self, key: int) -> bool:
        if key == KEY_RIGHT:
            self._nav_focused_tab_idx = (self._nav_focused_tab_idx + 1) % len(self._tab_buttons)
            update_focus_in_list(
                self._tab_buttons, self._nav_focused_tab_idx, _SEARCH_NAV_FOCUS_GROUP
            )
        elif key == KEY_LEFT:
            self._nav_focused_tab_idx = (self._nav_focused_tab_idx - 1) % len(self._tab_buttons)
            update_focus_in_list(
                self._tab_buttons, self._nav_focused_tab_idx, _SEARCH_NAV_FOCUS_GROUP
            )
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._tab_buttons[self._nav_focused_tab_idx].trigger_action()
        elif key in (KEY_TAB, KEY_DOWN):
            clear_focus_in_list(self._tab_buttons, _SEARCH_NAV_FOCUS_GROUP)
            self._nav_focus_area = "input"
            self._focus_active_input()
        elif key == KEY_ESCAPE:
            if self._nav_on_exit_request:
                self._nav_on_exit_request()
        else:
            return False
        return True

    def _handle_input_key(self, key: int) -> bool:
        if key == KEY_ESCAPE:
            self._blur_all_inputs()
            self._nav_focus_area = "tabs"
            self._nav_focused_tab_idx = self._tab_buttons.index(
                next(b for b in self._tab_buttons if b.state == "down")
            )
            update_focus_in_list(
                self._tab_buttons, self._nav_focused_tab_idx, _SEARCH_NAV_FOCUS_GROUP
            )
        elif key in (KEY_TAB, KEY_DOWN):
            self._blur_all_inputs()
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
                self._nav_focus_area = "input"
                self._focus_active_input()
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
        elif key == KEY_TAB:
            self._clear_result_focus()
            self._nav_focus_area = "tabs"
            self._nav_focused_tab_idx = 0
            update_focus_in_list(
                self._tab_buttons, self._nav_focused_tab_idx, _SEARCH_NAV_FOCUS_GROUP
            )
        elif key == KEY_ESCAPE:
            self._clear_result_focus()
            self._nav_focus_area = "tabs"
            self._nav_focused_tab_idx = self._tab_buttons.index(
                next(b for b in self._tab_buttons if b.state == "down")
            )
            update_focus_in_list(
                self._tab_buttons, self._nav_focused_tab_idx, _SEARCH_NAV_FOCUS_GROUP
            )
        else:
            return False
        return True

    def _focus_active_input(self) -> None:
        if self._active_tab == "Title":
            Clock.schedule_once(lambda _dt: setattr(self.ids.title_search_input, "focus", True))
        elif self._active_tab == "Tag":
            Clock.schedule_once(lambda _dt: setattr(self.ids.tag_search_input, "focus", True))
        elif self._active_tab == "Word":
            Clock.schedule_once(lambda _dt: setattr(self.ids.word_search_input, "focus", True))

    def _blur_all_inputs(self) -> None:
        self.ids.title_search_input.focus = False
        self.ids.tag_search_input.focus = False
        self.ids.word_search_input.focus = False

    def _get_active_result_buttons(self) -> list[Button]:
        if self._active_tab == "Title":
            layout = self.ids.title_results_layout
        elif self._active_tab == "Tag":
            layout = self.ids.tag_title_results_layout
        elif self._active_tab == "Word":
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
