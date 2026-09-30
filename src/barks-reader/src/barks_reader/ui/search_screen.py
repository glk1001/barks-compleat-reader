from __future__ import annotations

import random
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Self

from barks_fantagraphics.barks_tags import TagGroups
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, STR_TITLE_TO_ENUM, Titles
from barks_fantagraphics.comic_search import ComicSearch, SearchMode
from barks_fantagraphics.search_query import has_query_syntax, replace_word
from barks_fantagraphics.speech_speakers import (
    CHARACTER_SPEAKER_OPTIONS,
    NARRATOR,
    speaker_display_name,
)
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
from kivy.uix.label import Label
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.image_selector import ImageInfo
from barks_reader.core.reader_formatter import get_fitted_title_with_page_nums
from barks_reader.core.reader_palette import theme
from barks_reader.core.reader_settings import BARKS_READER_SECTION, SHOW_FUN_VIEW_TITLE_INFO
from barks_reader.core.settings_notifier import settings_notifier

from .index_screen import (
    TitleShowSpeechButton,
    create_speech_bubble_popup,
    show_speech_bubbles_popup,
)
from .reader_keyboard_nav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    KEY_TAB,
    KEY_UP,
    clear_focus_in_list,
    is_escape_key,
    log_nav_focus,
    update_focus_in_list,
)
from .search_chip_row import (
    CHIP_BORDER_NONE,
    ChipRow,
    RowKey,
    chip_bg_active,
    chip_bg_normal,
    chip_border_focused,
)
from .touch_keyboard import TouchAwareTextInput  # noqa: F401  # used in .kv

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.search_evaluate import Suggestion, WordQueryResult
    from barks_fantagraphics.whoosh_search_engine import TitleInfo
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.widget import Widget

    from barks_reader.core.reader_colors import Color
    from barks_reader.core.reader_settings import ReaderSettings

    from .font_manager import FontManager

SEARCH_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

SEARCH_IMAGE_CHANGE_SECONDS = 10
MAX_WORD_SEARCH_TITLE_AND_PAGES_LEN = 50

_SEARCH_NAV_FOCUS_GROUP = "search_nav_focus"


class _SearchResultButton(Button):
    """A clickable result row in a search results list."""

    row_index = NumericProperty(0)
    # Persistently highlights the last result the user opened (mouse or keyboard), so it
    # stays marked when they navigate away and come back. Distinct from the keyboard
    # focus ring, which tracks the live nav cursor.
    selected = BooleanProperty(defaultvalue=False)


class _QueryRowButton(_SearchResultButton):
    """The word list's first row while the box holds a query: pressing it runs the query."""


class _SuggestionButton(_SearchResultButton):
    """A close spelling for a word of the query that is in no story: pressing it swaps it in."""

    def __init__(self, suggestion: Suggestion, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self.suggestion = suggestion


class _NoticeLabel(Label):
    """A line of the word list the user reads but cannot pick: a notice, a heading."""


def _query_row_text(query: str) -> str:
    return f"Search for:  {query}"


# Theme colors must be read lazily (the active theme is set after UI modules
# import), so chip/selection colors are functions, not module constants.


def _chip_bg_member() -> Color:
    r, g, b, a = theme().tag_chip_bg
    return (r * 0.75, g * 0.75, b * 0.75, a)


def _word_item_selected_bg() -> Color:
    return theme().accent_selection


def _row_stripe(row_index: int) -> Color:
    active_theme = theme()
    return active_theme.row_stripe_even if row_index % 2 == 0 else active_theme.row_stripe_odd


class _TagChipButton(Button):
    """A pill-shaped tag chip button for tag search results.

    ``count_text`` is the number of stories the tag lists, shown small at the
    chip's right; empty for none (a speaker chip). ``text`` stays the tag's name
    alone: picking a chip looks the tag up by it, and the focus lines name it.
    """

    chip_bg_color = ObjectProperty(CHIP_BORDER_NONE)
    chip_border_color = ObjectProperty(CHIP_BORDER_NONE)
    count_text = StringProperty("")

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        if "chip_bg_color" not in kwargs:
            self.chip_bg_color = chip_bg_normal()


class _SpeakerChipButton(_TagChipButton):
    """A word-search speaker filter chip.

    ``value`` is the stored speaker the chip filters to (``"Scrooge"``,
    ``"narrator"``), or empty for the *All* chip that lifts the filter.
    """

    value = StringProperty("")


def _make_speaker_chip(value: str, label: str) -> _SpeakerChipButton:
    return _SpeakerChipButton(text=label, value=value)


# The *All* chip's speaker value: no filter.
_ALL_SPEAKERS = ""


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
        # Set by MainScreenNavigation; lets Enter in a search input pull the app's
        # keyboard focus to this screen when nav isn't active (mouse-click flow).
        self.on_request_nav_focus: Callable[[], None] | None = None
        # "input", "clear", "tags", "speakers" (Word mode only), "results"
        self._nav_focus_area: str = "input"
        self._nav_focused_result_idx: int = 0
        self._nav_focused_chip_idx: int = 0
        self._nav_word_sub_focus: str = "title"  # "title" or "speech"

        # Tag search state
        self._current_tag = None
        self._selected_tag: str = ""
        self._selected_member: str = ""
        self._tag_chip_strings: list[str] = []
        self._tag_chip_counts: dict[str, int] = {}
        self._tag_titles: list[str] = []

        # Word search state
        self._word_search_results: list[tuple[str, str, str, TitleInfo]] = []
        # Read the index's word list now, not on the first keystroke (an empty
        # query matches nothing, but builds the cached list it matches against).
        self._search.get_words_matching("")
        self._selected_word: str = ""
        # The typed query the word results are for, and what it found; "" and None
        # while the results are a picked word's (or there are none).
        self._word_query: str = ""
        self._word_query_result: WordQueryResult | None = None
        # The box's text while it is a query to run (Return runs it), else "".
        self._box_query: str = ""
        # The speaker the word results are narrowed to (its `selected`); `_ALL_SPEAKERS`
        # for everyone.
        self._speaker_row = ChipRow(
            self.ids.speaker_chips_layout,
            _make_speaker_chip,
            self._on_speaker_chip_selected,
            selected=_ALL_SPEAKERS,
        )
        self._speaker_chips_built: bool = False

        # Last activated result (for restoring focus after go-back)
        self._last_activated_result_idx: int | None = None
        self._last_activated_word_sub_focus: str = "title"

        # Persistent highlight of the last-opened result row (mouse or keyboard).
        self._selected_result_button: _SearchResultButton | None = None

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

        logger.debug(log_markers.SEARCH_MODE_SET.format(mode=mode))

    # --- Shared Helpers ---

    def _mark_result_selected(self, button: _SearchResultButton) -> None:
        """Mark `button` as the last-opened result, clearing any prior highlight.

        Bound into the row's on_release, so it fires for both mouse clicks and keyboard
        activation and the highlight survives navigating away and back.
        """
        if self._selected_result_button is not None and self._selected_result_button is not button:
            self._selected_result_button.selected = False
        button.selected = True
        self._selected_result_button = button
        # Also drive the keyboard restore target, so a later keyboard Go Back lands its
        # focus ring on the same row the mouse opened.
        self._last_activated_result_idx = button.row_index
        self._last_activated_word_sub_focus = "title"

    def _populate_title_results(
        self, layout: BoxLayout, title_strings: list[str], on_select: Callable[[str], None]
    ) -> None:
        layout.clear_widgets()
        self._selected_result_button = None
        for i, title_str in enumerate(title_strings):
            btn = _SearchResultButton(text=title_str, row_index=i)
            btn.bind(
                on_release=lambda b, t=title_str: self._on_result_row_released(b, t, on_select)
            )
            layout.add_widget(btn)

    def _on_result_row_released(
        self, button: _SearchResultButton, title_str: str, on_select: Callable[[str], None]
    ) -> None:
        self._mark_result_selected(button)
        on_select(title_str)

    def _on_result_goto_title(self, title_str: str) -> None:
        logger.info(log_markers.SEARCH_SELECTED_TITLE.format(title=title_str))
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
        logger.debug(log_markers.SEARCH_TITLE_RESULTS.format(count=len(title_strings), text=text))

    def _get_titles_matching(self, value: str) -> tuple[list[Titles], list[str]]:
        result = self._search.search(value, SearchMode.TITLE)
        return result.titles, result.title_strings

    def on_title_clear(self) -> None:
        logger.debug(log_markers.SEARCH_CLEARED.format(mode="title"))
        self._cancel_image_change_event()
        self.ids.title_search_input.text = ""
        self.ids.title_search_input.focus = True

    # --- Tag Search ---

    def on_tag_search_text(self, text: str) -> None:
        self.ids.tag_chips_layout.clear_widgets()
        self._tag_chip_strings = []
        self._tag_chip_counts = {}
        self._selected_member = ""
        self._clear_tag_title_results()

        if len(text) <= 1:
            return

        # An alias typed whole first, then aliases starting with the text, then (from
        # three letters) aliases with it inside; each with the stories it lists.
        matches = self._search.get_tags_matching(text)
        self._tag_chip_strings = [match.label for match in matches]
        self._tag_chip_counts = {match.label: match.title_count for match in matches}
        logger.debug(
            log_markers.SEARCH_TAG_RESULTS.format(count=len(self._tag_chip_strings), text=text)
        )

        self._rebuild_tag_chips()

        # Picked as typed when it is the only one, or the text is its name whole
        # ("africa" also finds Central and South Africa, but means Africa).
        if len(matches) == 1 or (matches and matches[0].exact):
            self._on_tag_result_selected(matches[0].label)

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
            count = self._tag_chip_counts.get(tag_str)
            btn = _TagChipButton(text=tag_str, count_text="" if count is None else str(count))
            btn.chip_bg_color = chip_bg_active() if tag_str == selected else chip_bg_normal()
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
            btn = _TagChipButton(
                text=label, count_text=str(self._search.get_tag_title_count(member))
            )
            btn.chip_bg_color = (
                chip_bg_active() if label == self._selected_member else _chip_bg_member()
            )
            btn.bind(on_release=lambda _b, m=label: self._on_member_tag_selected(m))
            stack.add_widget(btn)
        return stack

    def _show_tag_titles(self, tag_str: str) -> None:
        """Look up titles for a tag and populate the results list."""
        _, titles = self._search.resolve_tag(tag_str.lower())
        self._tag_titles = self._search.get_title_display_strings(titles) if titles else []
        logger.debug(log_markers.TAG_TITLES_LISTED.format(tag=tag_str, count=len(titles)))
        title_results_layout: BoxLayout = self.ids.tag_title_results_layout
        self._populate_title_results(
            title_results_layout, self._tag_titles, self._on_result_goto_title
        )
        self._update_background_from_results(titles or [])

    def _on_tag_result_selected(self, tag_str: str) -> None:
        logger.info(log_markers.TAG_SELECTED_TAG.format(tag=tag_str))
        self._selected_tag = tag_str
        self._selected_member = ""
        self._current_tag, _ = self._search.resolve_tag(tag_str.lower())
        self._rebuild_tag_chips()
        self._show_tag_titles(tag_str)

    def _on_member_tag_selected(self, member_label: str) -> None:
        # Strip subgroup indicator suffix
        member_str = member_label.rstrip(" \u25b8")
        logger.info(log_markers.TAG_SELECTED_MEMBER.format(member=member_str))
        self._selected_member = member_label
        self._show_tag_titles(member_str)

        # Highlight the selected member chip
        for chip in self._get_member_chip_buttons():
            chip.chip_bg_color = (
                chip_bg_active() if chip.text == member_label else _chip_bg_member()
            )

    def _clear_tag_title_results(self) -> None:
        self.ids.tag_title_results_layout.clear_widgets()
        self._tag_titles = []

    def on_tag_clear(self) -> None:
        logger.debug(log_markers.SEARCH_CLEARED.format(mode="tag"))
        self._cancel_image_change_event()
        self.ids.tag_search_input.text = ""
        self.ids.tag_chips_layout.clear_widgets()
        self._tag_chip_strings = []
        self._tag_chip_counts = {}
        self._selected_member = ""
        self._clear_tag_title_results()
        self.ids.tag_search_input.focus = True

    # --- Word Search ---

    def on_word_search_text(self, text: str) -> None:
        self.ids.word_chips_layout.clear_widgets()
        self.ids.word_results_layout.clear_widgets()
        self._word_search_results = []
        self._selected_word = ""
        self._word_query = ""
        self._word_query_result = None
        self._box_query = ""

        if not text.strip():
            return

        if not self._speaker_chips_built:
            self._build_speaker_chips()

        # The words that are the text, then those starting with it, then (from three
        # characters) those with it inside; at most MAX_MATCHES_SHOWN of them.
        matches = self._search.get_words_matching(text)
        # A query that matches nothing otherwise looks exactly like a query that
        # never ran: the only word-search log line fires on picking a chip, so a
        # search returning zero leaves no trace at all. The count is every match,
        # shown or not.
        logger.debug(log_markers.WORD_SEARCH_MATCHED.format(text=text, count=matches.total))

        # Query syntax, or text no word matches, is a query to run: offered as the
        # list's first row, which Return in the box also runs.
        is_query = has_query_syntax(text) or not matches.total
        first_row = 0
        if is_query:
            self._box_query = text
            self._add_query_row(text)
            first_row = 1

        for i, word in enumerate(matches.words, start=first_row):
            btn = _SearchResultButton(text=word, row_index=i, color=theme().text_secondary)
            btn.bind(on_release=lambda _b, w=word: self._on_word_chip_selected(w))
            self.ids.word_chips_layout.add_widget(btn)
        if matches.more:
            # Says what was left out; disabled, so the keyboard walk passes it by.
            self.ids.word_chips_layout.add_widget(
                _SearchResultButton(
                    text=f"... {matches.more} more - type more of the word",
                    row_index=first_row + len(matches.words),
                    disabled=True,
                )
            )

        if matches.total == 1 and not is_query:
            self._on_word_chip_selected(matches.words[0])

    def _add_query_row(self, query: str, *, selected: bool = False) -> None:
        row = _QueryRowButton(
            text=_query_row_text(query), row_index=0, shorten=True, selected=selected
        )
        row.bind(on_release=lambda _b, q=query: self._run_word_query(q))
        self.ids.word_chips_layout.add_widget(row)

    # --- Word Search: typed queries ---

    def _run_word_query(self, query: str) -> None:
        """Run a typed query and list what it found, its notices and its suggestions.

        The word list becomes the query's: its row (selected), then what the query
        tells the user, then close spellings for its words that are in no story.
        The results list its stories with how many bubbles matched in each.
        """
        result = self._search.run_word_query(query, speaker=self._speaker_row.selected or None)
        self._word_query = query
        self._word_query_result = result
        self._selected_word = ""

        if result.used_literal_fallback:
            logger.info(log_markers.WORD_QUERY_FALLBACK.format(text=query, error=result.error))
        notices = list(result.notices)
        if result.error and not result.used_literal_fallback:
            notices.insert(0, result.error)
        for notice in notices:
            logger.info(log_markers.WORD_QUERY_NOTICE.format(notice=notice))

        layout = self.ids.word_chips_layout
        layout.clear_widgets()
        self._add_query_row(query, selected=True)
        for notice in notices:
            layout.add_widget(_NoticeLabel(text=notice, disabled=True))
        self._add_suggestion_rows(result.suggestions)

        self._list_word_stories(result.title_dict, query, result.hit_counts)
        logger.info(log_markers.WORD_QUERY_RUN.format(text=query, count=len(result.title_dict)))

    def _add_suggestion_rows(self, suggestions: tuple[Suggestion, ...]) -> None:
        layout = self.ids.word_chips_layout
        by_word: dict[str, list[Suggestion]] = {}
        for suggestion in suggestions:
            by_word.setdefault(suggestion.word, []).append(suggestion)
        for word, offered in by_word.items():
            spellings = ", ".join(s.spelling for s in offered)
            logger.info(log_markers.WORD_SUGGESTIONS.format(word=word, spellings=spellings))
            layout.add_widget(_NoticeLabel(text=f'Did you mean, for "{word}":', disabled=True))
            for i, suggestion in enumerate(offered):
                row = _SuggestionButton(suggestion, text=f"   {suggestion.spelling}", row_index=i)
                row.bind(on_release=lambda _b, sg=suggestion: self._on_suggestion_picked(sg))
                layout.add_widget(row)

    def _on_suggestion_picked(self, suggestion: Suggestion) -> None:
        """Put the spelling in place of the word it is for, in the box, and run the query."""
        query = replace_word(self._word_query, suggestion.word, suggestion.spelling)
        self.ids.word_search_input.text = query  # relists the box's words, as typing does
        self._run_word_query(query)

    def _focus_after_query(self) -> None:
        """Hand the keyboard on from a query: its first story, else its first suggestion.

        With neither, back to the box to type another.
        """
        self._ensure_nav_active()
        self._blur_all_inputs()
        if self._word_search_results:
            self._nav_enter_results()
            Clock.schedule_once(
                lambda _dt: Clock.schedule_once(lambda _dt2: self._draw_result_focus())
            )
            return
        rows = self._get_word_chip_buttons()
        first = next((i for i, r in enumerate(rows) if isinstance(r, _SuggestionButton)), None)
        if first is None:
            self._nav_focus_area = "input"
            self._focus_active_input()
            return
        self._nav_focus_area = "tags"
        self._nav_focused_chip_idx = first
        Clock.schedule_once(lambda _dt: Clock.schedule_once(lambda _dt2: self._draw_chip_focus()))

    def _on_word_chip_selected(self, word: str) -> None:
        logger.info(log_markers.WORD_SELECTED_CHIP.format(word=word))
        self._selected_word = word

        for btn in reversed(self.ids.word_chips_layout.children):
            if btn.text == word:
                btn.background_color = _word_item_selected_bg()
            else:
                btn.background_color = _row_stripe(btn.row_index)

        self._show_word_results(word)

    def _show_word_results(self, word: str) -> None:
        """Run the word search under the current speaker filter and list its titles."""
        found = self._search.find_words(word, speaker=self._speaker_row.selected or None)
        self._list_word_stories(found, word)

    def _list_word_stories(
        self, found: dict[str, TitleInfo], searched: str, hit_counts: dict[str, int] | None = None
    ) -> None:
        """List the stories a search found, each with its pages (and hit count, if given)."""
        results_layout: BoxLayout = self.ids.word_results_layout
        results_layout.clear_widgets()

        self._word_search_results = self._build_word_results(found, hit_counts)
        self._populate_word_results_layout(results_layout)

        if not found:
            results_layout.add_widget(
                _SearchResultButton(text=f'No results for "{searched}"', disabled=True)
            )
            return

        word_result_titles = [STR_TITLE_TO_ENUM[ct] for ct in found if ct in STR_TITLE_TO_ENUM]
        self._update_background_from_results(word_result_titles)

    # --- Word Search: speaker filter ---

    def _build_speaker_chips(self) -> None:
        """Offer one chip per roster speaker the index knows, plus *All*.

        Built once, from the index's speaker sidecar.  An index without one
        (built before speakers existed) offers nothing, and the row stays
        empty and takes no space.  The roster's named characters and the
        narrator are offered; ``other:`` speakers are a long tail and are not.
        """
        self._speaker_chips_built = True
        indexed = self._search.get_speakers()
        offered = [s for s in (*CHARACTER_SPEAKER_OPTIONS, NARRATOR) if s in indexed]
        if not offered:
            self._speaker_row.set_options([])
            logger.debug("Word search: index has no speakers; no speaker filter.")
            return

        self._speaker_row.set_options(
            [
                (v, "All" if v == _ALL_SPEAKERS else speaker_display_name(v) or v)
                for v in (_ALL_SPEAKERS, *offered)
            ]
        )

    def _on_speaker_chip_selected(self, speaker: str) -> None:
        """Rerun the word search under the speaker the row just picked."""
        logger.info(log_markers.SPEAKER_FILTER_SET.format(speaker=speaker or "All"))
        if self._word_query:
            self._run_word_query(self._word_query)
        elif self._selected_word:
            self._show_word_results(self._selected_word)

    def _nav_enter_speakers(self) -> None:
        """Focus the speaker row, on the selected chip."""
        self._nav_focus_area = "speakers"
        self._speaker_row.enter_focus()

    def _has_speaker_row(self) -> bool:
        return self._active_mode == "Word" and bool(self._speaker_row.chips)

    @staticmethod
    def _build_word_results(
        found: dict[str, TitleInfo], hit_counts: dict[str, int] | None = None
    ) -> list[tuple[str, str, str, TitleInfo]]:
        """Return each story's row: title, first page, row text and its matches.

        With `hit_counts` (a typed query's), each row ends in its story's count of
        matching bubbles: "Lost in the Andes!, 3,5 (4)".
        """
        results: list[tuple[str, str, str, TitleInfo]] = []
        for comic_title, title_speech_info in found.items():
            page_num_list = [page.comic_page for page in title_speech_info.fanta_pages.values()]
            count = "" if hit_counts is None else f" ({hit_counts.get(comic_title, 0)})"
            first_page_num, title_with_pages = get_fitted_title_with_page_nums(
                comic_title, page_num_list, MAX_WORD_SEARCH_TITLE_AND_PAGES_LEN - len(count)
            )
            results.append(
                (comic_title, first_page_num, title_with_pages + count, title_speech_info)
            )
        results.sort(key=lambda t: t[2])
        return results

    def _populate_word_results_layout(self, results_layout: BoxLayout) -> None:
        logger.debug(log_markers.SEARCH_WORD_RESULTS.format(count=len(self._word_search_results)))
        self._selected_result_button = None
        for i, (
            comic_title,
            first_page_num,
            title_with_pages,
            title_speech_info,
        ) in enumerate(self._word_search_results):
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(28))

            # One line, shortened in the middle when the panel is too narrow for it:
            # wrapped, a long page list spilled out of its row, and the middle keeps
            # both the title's start and a query's hit count at the end.
            title_btn = _SearchResultButton(
                text=title_with_pages,
                row_index=i,
                size_hint=(0.94, 1),
                halign="left",
                valign="middle",
                shorten=True,
                shorten_from="center",
            )
            title_btn.bind(
                on_release=lambda b, ct=comic_title, fp=first_page_num: (
                    self._on_word_result_row_released(b, ct, fp)
                ),
            )
            row.add_widget(title_btn)

            speech_btn = TitleShowSpeechButton(size_hint=(0.06, 1), background_color=_row_stripe(i))
            speech_btn.bind(
                on_release=lambda _b, ct=comic_title, tsi=title_speech_info: (
                    self._show_word_speech_bubbles(ct, tsi)
                ),
            )
            row.add_widget(speech_btn)

            results_layout.add_widget(row)

    def _on_word_result_row_released(
        self, button: _SearchResultButton, title_str: str, page_to_goto: str
    ) -> None:
        self._mark_result_selected(button)
        self._on_word_title_selected(title_str, page_to_goto)

    def _on_word_title_selected(self, title_str: str, page_to_goto: str) -> None:
        logger.info(f'Word search: navigating to "{title_str}", page {page_to_goto}.')
        self._goto_title_with_page(title_str, page_to_goto)

    def _show_word_speech_bubbles(self, title_str: str, title_speech_info: TitleInfo) -> None:
        search_text = self._word_query or self._selected_word
        result = self._word_query_result if self._word_query else None
        # A query's words and their forms; a literal fallback, as a picked word, its text.
        highlight_terms = (
            result.highlight_terms if result and not result.used_literal_fallback else None
        )
        logger.info(log_markers.SHOW_BUBBLES_FOR_SEARCH.format(title=title_str, text=search_text))
        show_speech_bubbles_popup(
            self._speech_bubble_popup,
            title_str,
            search_text,
            title_speech_info,
            self._handle_bubble_title_press,
            self._font_manager.speech_bubble_popup_title_font_size,
            speaker=self._speaker_row.selected or None,
            text_font_size=self._font_manager.speech_bubble_text_font_size,
            highlight_terms=highlight_terms,
        )

    def _handle_bubble_title_press(self, title_str: str, page_to_goto: str) -> None:
        logger.info(log_markers.WORD_BUBBLE_PRESS.format(title=title_str, page=page_to_goto))
        self._speech_bubble_popup.dismiss()
        Clock.schedule_once(lambda _dt: self._goto_title_with_page(title_str, page_to_goto), 0.01)

    def _goto_title_with_page(self, title_str: str, page_to_goto: str) -> None:
        if title_str not in STR_TITLE_TO_ENUM:
            return
        title = STR_TITLE_TO_ENUM[title_str]
        image_info = ImageInfo(from_title=title, filename=None)
        if self.on_goto_title_with_page:
            self.on_goto_title_with_page(image_info, page_to_goto)

    def on_word_clear(self) -> None:
        logger.debug(log_markers.SEARCH_CLEARED.format(mode="word"))
        self._cancel_image_change_event()
        self.ids.word_search_input.text = ""
        self.ids.word_chips_layout.clear_widgets()
        self.ids.word_results_layout.clear_widgets()
        self._selected_word = ""
        self._word_query = ""
        self._word_query_result = None
        self._box_query = ""
        self._speaker_row.set_selected(_ALL_SPEAKERS)
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
            "" if image_info.from_title is None else ENUM_TO_STR_TITLE[image_info.from_title]
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
        logger.debug(log_markers.SEARCH_ENTERED_NAV)

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

    def adopt_nav_focus(self, on_exit_request: Callable) -> None:
        """Activate nav without resetting the focus area or grabbing the input.

        Unlike `enter_nav_focus`, this preserves whatever focus state the screen has
        already set up — used when the screen itself claims focus (Enter in an input).
        """
        self._nav_on_exit_request = on_exit_request
        self._nav_active = True
        logger.debug("SearchScreen: adopted nav focus.")

    def _ensure_nav_active(self) -> None:
        if not self._nav_active and self.on_request_nav_focus:
            self.on_request_nav_focus()

    def on_search_input_focus(self, _text_input: Widget, focused: bool) -> None:
        """Log a search box taking or losing the keyboard (kv callback).

        A box takes the keyboard a moment after focus is asked for, and the GUI
        path tests type into it only once this line says it has.
        """
        state = "focused" if focused else "unfocused"
        logger.debug(log_markers.SEARCH_BOX_FOCUS.format(mode=self._active_mode, state=state))

    def on_search_input_enter(self) -> None:
        """Handle Enter in a search input (kv callback).

        Title mode: focus the first result row. Tag/Word modes: select the first
        chip if none is selected yet and land focus on the chips, so Up/Down move
        through them; Enter on a chip then moves focus right to its title list.
        """
        if self._active_mode == "Word" and self._box_query:
            self._run_word_query(self._box_query)
            self._focus_after_query()
            return
        if self._active_mode in ("Tag", "Word") and self._get_active_chip_buttons():
            self._enter_chips_from_input()
            return
        if self._get_active_result_rows():
            self._focus_first_result_row()
        # else: nothing to show — the input keeps focus, keep typing.

    def _enter_chips_from_input(self) -> None:
        chips = self._get_active_chip_buttons()
        if not self._get_selected_chip_text():
            # Auto-pick the first chip so its titles show without another keypress.
            chips[0].trigger_action(duration=0)
        self._ensure_nav_active()
        self._blur_all_inputs()
        self._nav_focus_area = "tags"
        # Chips may have been rebuilt by the pick (e.g. a tag group inserting its
        # members) — resolve the focused index once the new widgets have settled.
        Clock.schedule_once(
            lambda _dt: Clock.schedule_once(lambda _dt2: self._focus_selected_or_first_chip())
        )

    def _get_selected_chip_text(self) -> str:
        if self._active_mode == "Word":
            return _query_row_text(self._word_query) if self._word_query else self._selected_word
        return self._selected_member or self._selected_tag

    def _focus_selected_or_first_chip(self) -> None:
        chips = self._get_active_chip_buttons()
        if not chips:
            return
        target = self._get_selected_chip_text()
        self._nav_focused_chip_idx = next((i for i, c in enumerate(chips) if c.text == target), 0)
        self._draw_chip_focus()

    def _focus_first_result_row(self) -> None:
        if not self._get_active_result_rows():
            return
        self._ensure_nav_active()
        self._blur_all_inputs()
        self._nav_enter_results()
        self._draw_result_focus()

    def exit_nav_focus(self) -> None:
        self._blur_all_inputs()
        self._clear_result_focus()
        self._clear_chip_focus()
        self._speaker_row.clear_focus()
        self._clear_clear_focus()
        self._nav_active = False
        self._nav_focus_area = "input"
        logger.debug(log_markers.SEARCH_EXITED_NAV)

    def handle_key(self, key: int) -> bool:
        # While the speech-bubble popup is open it owns the keyboard directly via
        # its own Window binding (see PopupKeyboardNav), so this handler is not
        # reached — the modal-popup guard in main_screen yields first.
        if not self._nav_active:
            return False

        handlers = {
            "input": self._handle_input_key,
            "clear": self._handle_clear_key,
            "tags": self._handle_tags_key,
            "speakers": self._handle_speakers_key,
            "results": self._handle_results_key,
        }
        handler = handlers.get(self._nav_focus_area)
        # noinspection PyArgumentList
        return handler(key) if handler else False

    def _handle_input_key(self, key: int) -> bool:
        if is_escape_key(key):
            self._blur_all_inputs()
            if self._nav_on_exit_request:
                self._nav_on_exit_request()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self.on_search_input_enter()
        elif key in (KEY_TAB, KEY_DOWN):
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
            self._handle_results_up()
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
        elif is_escape_key(key):
            self._nav_escape()
        else:
            return False
        return True

    def _handle_results_up(self) -> None:
        if self._nav_focused_result_idx > 0:
            self._nav_focused_result_idx -= 1
            self._nav_word_sub_focus = "title"
            self._draw_result_focus()
        elif self._has_speaker_row():
            # The speaker row sits directly above the word results.
            self._clear_result_focus()
            self._nav_enter_speakers()

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
            self._nav_back_to_word_chips()
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

    def _nav_back_to_word_chips(self) -> None:
        """Focus the word chip list, on the selected word."""
        self._nav_focus_area = "tags"
        word_buttons = self._get_word_chip_buttons()
        selected = self._get_selected_chip_text()
        self._nav_focused_chip_idx = next(
            (i for i, b in enumerate(word_buttons) if b.text == selected), 0
        )
        self._draw_chip_focus()

    def _handle_speakers_key(self, key: int) -> bool:
        """Keys on the word search's speaker row.

        The row walks its chips with Left and Right, and Enter applies the chip's
        filter and stays put, so the row can be tried out without losing one's
        place. Left off the first chip goes back to the word list, Down (or Tab)
        drops into the results, and Up returns to the search box.
        """
        match self._speaker_row.handle_key(key):
            case RowKey.UNHANDLED:
                return False
            case RowKey.EXIT_LEFT if self._get_word_chip_buttons():
                self._speaker_row.clear_focus()
                self._nav_back_to_word_chips()
            case RowKey.EXIT_DOWN if self._get_active_result_rows():
                self._speaker_row.clear_focus()
                self._nav_enter_results()
                self._draw_result_focus()
            case RowKey.EXIT_UP:
                self._speaker_row.clear_focus()
                self._nav_focus_area = "input"
                self._focus_active_input()
            case RowKey.EXIT_ESCAPE:
                self._nav_escape()
            case _:  # handled on the row, or a way out to nowhere: stay on the row
                pass
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
        self._speaker_row.clear_focus()
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
        elif is_escape_key(key):
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
            if self._has_speaker_row():
                # The speaker row is the first thing to the right of the words.
                self._nav_enter_speakers()
            else:
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
        elif is_escape_key(key):
            self._nav_escape()
        else:
            return False
        return True

    def _handle_tags_enter(self, chips: list[Button]) -> None:
        if not chips or self._nav_focused_chip_idx >= len(chips):
            return
        focused_chip = chips[self._nav_focused_chip_idx]
        if isinstance(focused_chip, (_QueryRowButton, _SuggestionButton)):
            focused_chip.trigger_action(duration=0)
            self._clear_chip_focus()
            self._focus_after_query()
            return
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
        # Not the disabled "... N more" row that ends a long list.
        return [b for b in reversed(self.ids.word_chips_layout.children) if not b.disabled]

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
                chip.chip_bg_color = chip_bg_active() if is_selected else chip_bg_normal()
            else:
                is_selected = chip.text == self._selected_member
                chip.chip_bg_color = chip_bg_active() if is_selected else _chip_bg_member()
            chip.chip_border_color = chip_border_focused() if i == focused_idx else CHIP_BORDER_NONE
        # Tag chips show focus by border colour, not a drawn ring, so log it here.
        if focused_idx is not None and 0 <= focused_idx < len(chips):
            log_nav_focus(chips[focused_idx])

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

    # Must match the SearchClearButton background_color in search_screen.kv.
    _CLEAR_BTN_NORMAL = (0.18, 0.18, 0.18, 0.9)

    def _active_widget(self, index: int):  # noqa: ANN202
        """Return the widget for the active mode at the given _MODE_WIDGETS index."""
        return self.ids[self._MODE_WIDGETS[self._active_mode][index]]

    def _get_active_clear_button(self) -> Button:
        return self._active_widget(1)

    def _draw_clear_focus(self) -> None:
        r, g, b, _a = theme().accent_selection
        clear_button = self._get_active_clear_button()
        clear_button.background_color = (r, g, b, 1.0)
        log_nav_focus(clear_button)  # shown by fill colour, not a drawn ring

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

    def _get_focused_result_widget(self, rows: list[Button]) -> Button | None:
        if not rows:
            return None
        idx = min(self._nav_focused_result_idx, len(rows) - 1)
        row = rows[idx]
        if self._active_mode == "Word" and hasattr(row, "children") and row.children:
            children = list(reversed(row.children))
            sub_idx = 1 if self._nav_word_sub_focus == "speech" else 0
            return children[min(sub_idx, len(children) - 1)]
        return row

    def _get_all_focusable_widgets(self, rows: list[Button]) -> list[Button]:
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
