from __future__ import annotations

import random
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Self, cast

from barks_fantagraphics.barks_tags import TagGroups, Tags
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, STR_TITLE_TO_ENUM, Titles
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO
from barks_fantagraphics.comic_search import ComicSearch, SearchMode
from barks_fantagraphics.search_filters import SearchFilter, apply_filter
from barks_fantagraphics.search_query import has_query_syntax, replace_word
from barks_fantagraphics.speech_speakers import (
    CHARACTER_SPEAKER_OPTIONS,
    NARRATOR,
    speaker_display_name,
)
from barks_fantagraphics.tag_query import has_tag_syntax, range_text
from barks_kivy_ui.scrolling import ReaderDropDown
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
from barks_reader.core.reader_consts_and_types import CHRONO_YEAR_RANGES
from barks_reader.core.reader_formatter import get_fitted_title_with_page_nums
from barks_reader.core.reader_palette import theme
from barks_reader.core.reader_settings import BARKS_READER_SECTION, SHOW_FUN_VIEW_TITLE_INFO
from barks_reader.core.search_state import (
    ALL_YEARS,
    VOLUMES_KEY,
    YEARS_KEY,
    EraChoice,
    TagBasket,
    TagState,
    WordBasket,
)
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
    DropdownNavMixin,
    clear_focus_in_list,
    is_escape_key,
    log_nav_focus,
    open_dropdown,
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
    from collections.abc import Callable, Sequence

    from barks_fantagraphics.search_evaluate import Suggestion, WordQueryResult
    from barks_fantagraphics.whoosh_search_engine import TitleInfo
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.widget import Widget

    from barks_reader.core.reader_colors import Color
    from barks_reader.core.reader_settings import ReaderSettings
    from barks_reader.core.search_help import HelpExamples

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


class _SyntaxExample(Label):
    """Something to type, in a search box's syntax help."""


class _SyntaxMeaning(Label):
    """What an example in a search box's syntax help does."""


class SearchSyntaxHelp(BoxLayout):
    """A search box's syntax help: a heading, then each example beside what it does.

    Read, not picked: nothing in it takes focus or a tap.
    """

    heading = StringProperty()
    examples: HelpExamples = ObjectProperty(())

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self._show_examples()

    def on_examples(self, _instance: Self, _examples: HelpExamples) -> None:
        self._show_examples()

    def _show_examples(self) -> None:
        grid = self.ids.get("examples_grid")
        if grid is None:  # examples given before the kv rule built the grid
            return
        grid.clear_widgets()
        for example, meaning in self.examples:
            grid.add_widget(_SyntaxExample(text=example))
            grid.add_widget(_SyntaxMeaning(text=meaning))


class _PlusButton(_SearchResultButton):
    """A list row's + (a dash once its item is picked): puts the item in the basket or back."""


class _WordRow(BoxLayout):
    """A word of the word list: its text, which searches it alone, and its + button."""

    def __init__(self, word_button: _SearchResultButton, plus_button: _PlusButton) -> None:
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(28))
        self.word_button = word_button
        self.item: Button = word_button
        self.plus_button = plus_button
        self.add_widget(word_button)
        self.add_widget(plus_button)


class _TagRow(BoxLayout):
    """A tag of the tag list: its chip, which lists its stories alone, and its + button."""

    def __init__(self, chip: _TagChipButton, plus_button: _PlusButton) -> None:
        super().__init__(orientation="horizontal", size_hint_y=None, spacing=dp(2))
        self.chip = chip
        self.item: Button = chip
        self.plus_button = plus_button
        # As tall as the chip, which wraps a long name onto more lines.
        self.height = chip.height
        chip.bind(height=self.setter("height"))
        plus_button.height = self.height
        self.bind(height=plus_button.setter("height"))
        self.add_widget(chip)
        self.add_widget(plus_button)


def _tag_name(chip_text: str) -> str:
    """Return a tag chip's tag: its text without the arrow that marks a subgroup."""
    return chip_text.removesuffix(" \u25b8")


def _plus_text(picked: bool) -> str:
    return "\u2013" if picked else "+"  # an en dash: a minus the width of the +


def _chips_of(stack: Widget) -> list[_TagChipButton]:
    """Return a tag list stack's chips, in order: each row's chip, the combine chip; no notice."""
    return [
        child.chip if isinstance(child, _TagRow) else child
        for child in reversed(stack.children)
        if isinstance(child, (_TagRow, _TagChipButton))
    ]


def _query_row_text(query: str) -> str:
    return f"Search for:  {query}"


# Theme colors must be read lazily (the active theme is set after UI modules
# import), so chip/selection colors are functions, not module constants.


def _chip_bg_member() -> Color:
    r, g, b, a = theme().tag_chip_bg
    return (r * 0.75, g * 0.75, b * 0.75, a)


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


class _SaidByChipButton(_SpeakerChipButton):
    """The word search's speaker filter: one chip, which opens the list of who says it."""


def _make_said_by_chip(value: str, label: str) -> _SaidByChipButton:
    return _SaidByChipButton(text=label, value=value)


class _SaidByItem(_SearchResultButton):
    """A speaker in the speaker filter's list, with the stories they say it in.

    ``value`` is the stored speaker, or empty for anyone (no filter).
    """

    value = StringProperty("")
    count_text = StringProperty("")


class _EraChipButton(_SpeakerChipButton):
    """A chip of the era row: a range of submitted years, or all of them."""


def _make_era_chip(value: str, label: str) -> _EraChipButton:
    return _EraChipButton(text=label, value=value)


class _ScopeChipButton(_SpeakerChipButton):
    """A chip of the word search's tag scope row: everywhere, or only the tags' stories."""


def _make_scope_chip(value: str, label: str) -> _ScopeChipButton:
    return _ScopeChipButton(text=label, value=value)


# The tag scope row's chips: the word search everywhere, or only in the tags' stories.
_EVERYWHERE, _ONLY_IN_TAGS = "", "tags"
_MAX_SCOPE_LABEL = 40


class _TagQueryChip(_TagChipButton):
    """The tag list's first chip while the box holds typed tags: pressing it combines them."""


class _BasketChipButton(_SpeakerChipButton):
    """A chip of the picked-words row: ALL/ANY, which flips, or a word, which comes out."""


def _make_basket_chip(value: str, label: str) -> _BasketChipButton:
    return _BasketChipButton(text=label, value=value)


# The ALL/ANY chip's value in the picked-words row: never a word.
_BASKET_MODE_VALUE = ""


# The speaker value for anyone: no filter.
_ALL_SPEAKERS = ""
# The speaker filter's one chip, by its value in its row: picked (filled) while a
# speaker is.
_SAID_BY = "said by"


def _speaker_label(speaker: str) -> str:
    """Return how the speaker filter names a stored speaker; anyone, for none."""
    return "anyone" if speaker == _ALL_SPEAKERS else speaker_display_name(speaker) or speaker


class SearchScreen(DropdownNavMixin, FloatLayout):
    """Bottom view screen for search. Mode is set externally via set_mode()."""

    is_visible = BooleanProperty(defaultvalue=False)
    image_texture = ObjectProperty(allownone=True)
    current_title_str = StringProperty()
    show_current_title = BooleanProperty(defaultvalue=True)
    on_goto_title: Callable[[str, Sequence[Tags]], bool] | None = ObjectProperty(
        None, allownone=True
    )
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
        # The speaker the word results are narrowed to; `_ALL_SPEAKERS` for anyone. Shown
        # as one chip, filled while a speaker is picked, which opens the list of the
        # speakers who say what was searched.
        self._speaker: str = _ALL_SPEAKERS
        self._speaker_row = ChipRow(
            self.ids.speaker_chips_layout, _make_said_by_chip, self._on_said_by_chip_pressed
        )
        # The speakers the filter offers (the index's roster ones); None until read.
        self._offered_speakers: list[str] | None = None
        self._said_by_dropdown = ReaderDropDown(auto_width=False, width=dp(220))
        self._said_by_dropdown.bind(
            on_select=self._on_said_by_item_selected, on_dismiss=self._on_said_by_dismissed
        )
        self._setup_dropdown_nav()
        self._init_picks_and_filters()

        # Last activated result (for restoring focus after go-back)
        self._last_activated_result_idx: int | None = None
        self._last_activated_word_sub_focus: str = "title"

        # Persistent highlight of the last-opened result row (mouse or keyboard).
        self._selected_result_button: _SearchResultButton | None = None

        self._speech_bubble_popup, self._popup_nav = create_speech_bubble_popup(
            self._font_manager.speech_bubble_popup_title_font_name,
        )

    def _init_picks_and_filters(self) -> None:
        """Set up what the searches hold between keystrokes, and the chip rows that show it."""
        # The words picked with their + to search together, and the row showing them.
        self._word_basket = WordBasket()
        self._basket_row = ChipRow(
            self.ids.word_basket_layout,
            _make_basket_chip,
            self._on_basket_chip_picked,
            selected=_BASKET_MODE_VALUE,
        )
        # Whether the results are the basket's, which typing in the box leaves in place.
        self._basket_results: bool = False
        # On a word or tag row, which part the keyboard is on: "word" (the item) or its "plus".
        self._nav_list_sub: str = "word"
        # The tags picked with their + (or typed), and the row showing them, under the box.
        self._tag_basket = TagBasket()
        self._tag_basket_row = ChipRow(
            self.ids.tag_basket_layout,
            _make_basket_chip,
            self._on_tag_basket_chip_picked,
            selected=_BASKET_MODE_VALUE,
        )
        self._tag_basket_results: bool = False
        # The tag box's text while it combines tags (Return combines them), else "".
        self._tag_box_query: str = ""
        # The tag whose stories are listed alone, if any: what a new era lists again.
        self._listed_tag: str = ""
        # The era both searches list stories from, and its row in each results panel.
        self._era = EraChoice(tuple(CHRONO_YEAR_RANGES))
        self._era_rows = {
            mode: ChipRow(self.ids[layout_id], _make_era_chip, self._on_era_selected)
            for mode, layout_id in (("Tag", "tag_era_layout"), ("Word", "word_era_layout"))
        }
        for row in self._era_rows.values():
            row.set_options(self._era.options())
        # The word search's tag scope: everywhere, or only the stories of the tags the tag
        # search has selected. Offered only while it has some; refreshed on entering Word.
        self._scope_row = ChipRow(
            self.ids.word_scope_layout, _make_scope_chip, self._on_scope_selected
        )
        self._scope_tags = ""
        self._scope_titles: frozenset[str] = frozenset()

    def on_is_visible(self, _instance: Self, value: bool) -> None:
        if not value:
            self._cancel_image_change_event()
            self._said_by_dropdown.dismiss()  # the speaker list does not outlive the screen

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
        if mode == "Word":
            self._refresh_tag_scope()

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

    def _on_result_goto_title(self, title_str: str, tags: Sequence[Tags] = ()) -> None:
        logger.info(log_markers.SEARCH_SELECTED_TITLE.format(title=title_str))
        if self.on_goto_title:
            self.on_goto_title(title_str, tags)

    def _on_tag_result_goto_title(self, title_str: str) -> None:
        self._on_result_goto_title(title_str, self._listed_tags())

    def _listed_tags(self) -> list[Tags]:
        """Return the tags the listed stories were found by: the one listed, or those picked.

        Only tags, not groups, and of the picked ones only those included: a tagged
        page is a tag's.
        """
        if self._tag_basket_results:
            names = self._tag_basket.selection().included
        else:
            names = (self._listed_tag,) if self._listed_tag else ()
        items = [self._search.resolve_tag(name.lower())[0] for name in names]
        return [item for item in items if isinstance(item, Tags)]

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
        self._tag_box_query = ""
        if not self._tag_basket_results:  # the picked tags' stories stay while typing
            self._clear_tag_title_results()

        if len(text) <= 1:
            return

        if has_tag_syntax(text):
            # Tags to combine ("scrooge + gyro -christmas"): offered as one chip, which
            # Return in the box also presses. Logged as no matches, so every keystroke
            # still leaves its line.
            self._tag_box_query = text
            logger.debug(log_markers.SEARCH_TAG_RESULTS.format(count=0, text=text))
            self._show_tag_query_chip(text)
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
            stack.add_widget(self._make_tag_row(btn))
        return stack

    def _make_tag_row(self, chip: _TagChipButton) -> _TagRow:
        name = _tag_name(chip.text)
        # Narrow and fixed, so the chip keeps nearly the whole row for a tag's name.
        plus = _PlusButton(
            text=_plus_text(name in self._tag_basket),
            size_hint=(None, None),
            width=dp(24),
            halign="center",
            padding=[0, 0],
        )
        plus.bind(on_release=lambda _b, t=name: self._toggle_tag_basket(t))
        return _TagRow(chip, plus)

    def _tag_rows(self) -> list[_TagRow]:
        if not hasattr(self.ids, "tag_chips_layout"):
            return []
        return [
            row
            for stack in reversed(self.ids.tag_chips_layout.children)
            for row in reversed(stack.children)
            if isinstance(row, _TagRow)
        ]

    def _show_tag_query_chip(self, text: str, notices: tuple[str, ...] = ()) -> None:
        """Show the typed tags as one chip to combine them, and any notice under it."""
        stack = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4), padding=dp(2))
        stack.bind(minimum_height=stack.setter("height"))
        chip = _TagQueryChip(text=f"Combine:  {text}")
        chip.bind(on_release=lambda _b, t=text: self._run_tag_query(t))
        stack.add_widget(chip)
        for notice in notices:
            stack.add_widget(_NoticeLabel(text=notice, disabled=True))
        self.ids.tag_chips_layout.clear_widgets()
        self.ids.tag_chips_layout.add_widget(stack)

    def _make_member_chip_stack(self) -> BoxLayout | None:
        members = self._search.get_tag_group_members(self._current_tag)
        if not members:
            return None
        stack = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(4),
            # Indented to show they belong to the group above; no more, since each
            # member row also holds its +.
            padding=[dp(24), dp(2), dp(2), dp(2)],
        )
        stack.is_member_layout = True
        stack.bind(minimum_height=stack.setter("height"))
        for member in members:
            label = str(member.value)
            if isinstance(member, TagGroups):
                label += " \u25b8"
            btn = _TagChipButton(
                text=label,
                count_text=str(self._search.get_tag_title_count(member)),
            )
            btn.chip_bg_color = (
                chip_bg_active() if label == self._selected_member else _chip_bg_member()
            )
            btn.bind(on_release=lambda _b, m=label: self._on_member_tag_selected(m))
            stack.add_widget(self._make_tag_row(btn))
        return stack

    def _show_tag_titles(self, tag_str: str) -> None:
        """Look up a tag's stories in the era and populate the results list."""
        _, titles = self._search.resolve_tag(tag_str.lower())
        titles = self._in_era(titles or [])
        self._listed_tag = tag_str
        self._tag_titles = self._search.get_title_display_strings(titles) if titles else []
        logger.debug(log_markers.TAG_TITLES_LISTED.format(tag=tag_str, count=len(titles)))
        title_results_layout: BoxLayout = self.ids.tag_title_results_layout
        self._populate_title_results(
            title_results_layout, self._tag_titles, self._on_tag_result_goto_title
        )
        self._add_none_in_era_row(title_results_layout, titles)
        self._update_background_from_results(titles)

    def _in_era(self, titles: list[Titles]) -> list[Titles]:
        """Return the stories of `titles` submitted in the era, in the same order."""
        return [t for t in titles if self._era.allows(BARKS_TITLE_INFO[t].submitted_year)]

    def _add_none_in_era_row(self, layout: BoxLayout, titles: list[Titles]) -> None:
        """Say so when the era leaves nothing of a list, so an empty list is not a mystery."""
        if not titles and self._era.years is not None:
            layout.add_widget(_SearchResultButton(text=f"None in {self._era.label}", disabled=True))

    def _on_tag_result_selected(self, tag_str: str) -> None:
        logger.info(log_markers.TAG_SELECTED_TAG.format(tag=tag_str))
        self._tag_basket_results = False
        self._selected_tag = tag_str
        self._selected_member = ""
        self._current_tag, _ = self._search.resolve_tag(tag_str.lower())
        self._rebuild_tag_chips()
        self._show_tag_titles(tag_str)

    def _on_member_tag_selected(self, member_label: str) -> None:
        # Strip subgroup indicator suffix
        member_str = member_label.rstrip(" \u25b8")
        logger.info(log_markers.TAG_SELECTED_MEMBER.format(member=member_str))
        self._tag_basket_results = False
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
        self._listed_tag = ""

    def on_tag_clear(self) -> None:
        logger.debug(log_markers.SEARCH_CLEARED.format(mode="tag"))
        self._cancel_image_change_event()
        self.ids.tag_search_input.text = ""
        self.ids.tag_chips_layout.clear_widgets()
        self._tag_chip_strings = []
        self._tag_chip_counts = {}
        self._selected_member = ""
        self._tag_box_query = ""
        self._tag_basket.clear()
        self._show_tag_basket()
        self._tag_basket_results = False
        self._selected_tag = ""
        self._current_tag = None
        self._clear_tag_title_results()
        self._set_era(ALL_YEARS)
        self.ids.tag_search_input.focus = True

    # --- Tag Search: the picked tags ---

    def _run_tag_query(self, text: str) -> bool:
        """Combine typed tags: they replace the picked ones. False, with a notice, if they cannot.

        Returns:
            Whether the text named tags to combine.

        """
        parsed = self._search.parse_tag_query(text)
        if parsed.selection is None:
            notice = parsed.error or "No tag is named."
            logger.info(log_markers.TAG_QUERY_NOTICE.format(notice=notice))
            self._show_tag_query_chip(text, (notice,))
            return False
        names = (*parsed.selection.included, *parsed.selection.excluded)
        self._tag_basket.fill(parsed.selection, {n: self._tag_label(n) for n in names})
        self._on_tag_basket_changed()
        return True

    def _tag_label(self, name: str) -> str:
        """Return the display name of the tag an alias names (its chip's text)."""
        item, _ = self._search.resolve_tag(name.lower())
        return name if item is None else str(item.value)

    def _toggle_tag_basket(self, tag: str) -> None:
        """Pick a tag to combine with the others, or put it back; then list their stories."""
        self._tag_basket.toggle(tag)
        self._on_tag_basket_changed()

    def _on_tag_basket_chip_picked(self, value: str) -> None:
        """Flip ALL/ANY, or step a tag on (included, left out, put back): its chip was pressed."""
        focused = self._tag_basket_row.focused
        if value == _BASKET_MODE_VALUE:
            mode = self._tag_basket.flip()
            logger.info(log_markers.TAG_BASKET_MODE.format(mode=mode.upper()))
            self._show_tag_basket()
            self._run_tag_basket()
        elif value in (YEARS_KEY, VOLUMES_KEY):  # a typed range: taken out, not stepped on
            self._tag_basket.drop_range(value)
            self._on_tag_basket_changed()
        else:
            self._tag_basket.cycle(value)
            self._on_tag_basket_changed()
        if self._nav_focus_area == "basket":
            self._refocus_basket(focused)

    def _on_tag_basket_changed(self) -> None:
        basket = self._tag_basket
        logger.info(
            log_markers.TAG_BASKET_CHANGED.format(
                count=len(basket), mode=basket.combine.upper(), tags=basket.selection().describe()
            )
        )
        self._show_tag_basket()
        self._mark_tag_rows()
        self._run_tag_basket()

    def _show_tag_basket(self) -> None:
        """Rebuild the picked-tags row: ALL/ANY, then each tag ("not" one left out)."""
        basket = self._tag_basket
        options = [
            (tag, tag if state is TagState.INCLUDED else f"not {tag}")
            for tag, state in basket.tags.items()
        ]
        if basket.years is not None:
            options.append((YEARS_KEY, f"years {range_text(basket.years, years=True)}"))
        if basket.volumes is not None:
            vols = range_text(basket.volumes, years=False)
            options.append((VOLUMES_KEY, f"vol {vols}" if "-" not in vols else f"vols {vols}"))
        if options:
            options.insert(0, (_BASKET_MODE_VALUE, basket.combine.upper()))
        self._tag_basket_row.set_options(options)
        self._tag_basket_row.set_selected(_BASKET_MODE_VALUE)

    def _mark_tag_rows(self) -> None:
        for row in self._tag_rows():
            row.plus_button.text = _plus_text(_tag_name(row.chip.text) in self._tag_basket)

    def _run_tag_basket(self) -> None:
        """List the stories the picked tags list together; none picked, the results empty."""
        if not self._tag_basket:
            self._tag_basket_results = False
            self._clear_tag_title_results()
            return
        self._tag_basket_results = True
        selection = self._tag_basket.selection()
        titles = self._in_era(self._search.titles_for_tag_selection(selection))
        self._listed_tag = ""
        self._tag_titles = self._search.get_title_display_strings(titles) if titles else []
        logger.info(
            log_markers.TAG_COMBINED_RESULTS.format(tags=selection.describe(), count=len(titles))
        )
        layout: BoxLayout = self.ids.tag_title_results_layout
        self._populate_title_results(layout, self._tag_titles, self._on_tag_result_goto_title)
        if not selection.included:
            layout.add_widget(
                _SearchResultButton(text="Include a tag to list stories", disabled=True)
            )
        elif not titles and self._era.years is not None:
            self._add_none_in_era_row(layout, titles)
        elif not titles:
            layout.add_widget(_SearchResultButton(text="No story has these tags", disabled=True))
        self._update_background_from_results(titles)

    # --- Word Search ---

    def on_word_search_text(self, text: str) -> None:
        self.ids.word_chips_layout.clear_widgets()
        self._selected_word = ""
        self._box_query = ""
        if not self._basket_results:  # the basket's results stay while more words are found
            self.ids.word_results_layout.clear_widgets()
            self._word_search_results = []
            self._word_query = ""
            self._word_query_result = None
        self._show_said_by_chip()

        if not text.strip():
            return

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
            self.ids.word_chips_layout.add_widget(self._make_word_row(word, i))
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

    def _make_word_row(self, word: str, row_index: int) -> _WordRow:
        btn = _SearchResultButton(
            text=word, row_index=row_index, color=theme().text_secondary, size_hint=(0.86, 1)
        )
        btn.bind(on_release=lambda _b, w=word: self._on_word_chip_selected(w))
        plus = _PlusButton(
            text=_plus_text(word in self._word_basket),
            row_index=row_index,
            size_hint=(0.14, 1),
            halign="center",
        )
        plus.bind(on_release=lambda _b, w=word: self._toggle_basket_word(w))
        return _WordRow(btn, plus)

    def _word_rows(self) -> list[_WordRow]:
        if not hasattr(self.ids, "word_chips_layout"):
            return []
        return [r for r in reversed(self.ids.word_chips_layout.children) if isinstance(r, _WordRow)]

    def _add_query_row(self, query: str, *, selected: bool = False) -> None:
        row = _QueryRowButton(
            text=_query_row_text(query), row_index=0, shorten=True, selected=selected
        )
        row.bind(on_release=lambda _b, q=query: self._run_word_query(q))
        self.ids.word_chips_layout.add_widget(row)

    # --- Word Search: typed queries ---

    def _run_word_query(
        self, query: str, *, list_words: bool = True, new_search: bool = True
    ) -> None:
        """Run a typed query and list what it found, its notices and its suggestions.

        The word list becomes the query's: its row (selected), then what the query
        tells the user, then close spellings for its words that are in no story.
        The results list its stories with how many bubbles matched in each.

        Args:
            query: The query text.
            list_words: Whether the word list becomes the query's; not for the
                basket's query, run beside the word list it is picked from.
            new_search: Whether the query is new, not the last one again under
                another filter: then a speaker who says none of it is lifted.

        """
        result = self._search.run_word_query(
            query,
            speaker=self._speaker or None,
            search_filter=self._word_search_filter(),
        )
        if new_search and self._speaker and not result.title_dict:
            everyone = self._search.run_word_query(
                query, speaker=None, search_filter=self._word_search_filter()
            )
            if everyone.title_dict:
                self._lift_speaker(query)
                result = everyone
        self._word_query = query
        self._word_query_result = result
        self._selected_word = ""
        self._basket_results = not list_words

        if result.used_literal_fallback:
            logger.info(log_markers.WORD_QUERY_FALLBACK.format(text=query, error=result.error))
        notices = list(result.notices)
        if result.error and not result.used_literal_fallback:
            notices.insert(0, result.error)
        for notice in notices:
            logger.info(log_markers.WORD_QUERY_NOTICE.format(notice=notice))

        if list_words:
            self._list_query_words(query, notices, result.suggestions)
        self._list_word_stories(result.title_dict, query, result.hit_counts)
        logger.info(log_markers.WORD_QUERY_RUN.format(text=query, count=len(result.title_dict)))

    def _list_query_words(
        self, query: str, notices: list[str], suggestions: tuple[Suggestion, ...]
    ) -> None:
        layout = self.ids.word_chips_layout
        layout.clear_widgets()
        self._add_query_row(query, selected=True)
        for notice in notices:
            layout.add_widget(_NoticeLabel(text=notice, disabled=True))
        self._add_suggestion_rows(suggestions)

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
        if self._active_mode == "Tag":
            self._focus_after_tag_query()
            return
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
        self._nav_list_sub = "word"
        Clock.schedule_once(lambda _dt: Clock.schedule_once(lambda _dt2: self._draw_chip_focus()))

    def _on_word_chip_selected(self, word: str) -> None:
        logger.info(log_markers.WORD_SELECTED_CHIP.format(word=word))
        self._word_query = ""
        self._word_query_result = None
        self._basket_results = False
        self._selected_word = word
        self._mark_word_rows()
        self._show_word_results(word)

    def _mark_word_rows(self) -> None:
        """Fill the word searched alone; show each word's + or dash by whether it is picked."""
        for row in self._word_rows():
            # The kv rule paints a selected row. A colour set here was painted over when
            # a mouse click's press state lapsed, so a clicked word lost its fill.
            row.word_button.selected = row.word_button.text == self._selected_word
            row.plus_button.text = _plus_text(row.word_button.text in self._word_basket)

    # --- Word Search: the picked words ---

    def _toggle_basket_word(self, word: str) -> None:
        """Pick a word to search with the others, or put it back; then run the basket."""
        self._word_basket.toggle(word)
        self._on_basket_changed()

    def _on_basket_chip_picked(self, value: str) -> None:
        """Flip ALL/ANY, or take a word out: its chip in the picked-words row was pressed."""
        focused = self._basket_row.focused
        if value == _BASKET_MODE_VALUE:
            mode = self._word_basket.flip()
            logger.info(log_markers.WORD_BASKET_MODE.format(mode=mode.upper()))
            self._show_basket()
            self._run_basket()
        else:
            self._word_basket.remove(value)
            self._on_basket_changed()
        if self._nav_focus_area == "basket":
            self._refocus_basket(focused)

    def _on_basket_changed(self) -> None:
        basket = self._word_basket
        logger.info(
            log_markers.WORD_BASKET_CHANGED.format(
                count=len(basket), mode=basket.combine.upper(), words=", ".join(basket.words)
            )
        )
        self._show_basket()
        self._mark_word_rows()
        self._run_basket()

    def _show_basket(self) -> None:
        """Rebuild the picked-words row: ALL/ANY, then each word with its x; none if empty."""
        basket = self._word_basket
        options = [(w, f"{w}  \u00d7") for w in basket.words]
        if options:
            options.insert(0, (_BASKET_MODE_VALUE, basket.combine.upper()))
        self._basket_row.set_options(options)
        self._basket_row.set_selected(_BASKET_MODE_VALUE)

    def _run_basket(self) -> None:
        """Search for the picked words together; with none picked, the results empty."""
        if self._word_basket:
            self._run_word_query(self._word_basket.query_text(), list_words=False)
            return
        self._basket_results = False
        self._word_query = ""
        self._word_query_result = None
        self._word_search_results = []
        self.ids.word_results_layout.clear_widgets()
        self._show_said_by_chip()

    def _active_basket_row(self) -> ChipRow:
        return self._tag_basket_row if self._active_mode == "Tag" else self._basket_row

    def _active_basket_has_items(self) -> bool:
        if self._active_mode == "Tag":
            return bool(self._tag_basket)
        return self._active_mode == "Word" and bool(self._word_basket)

    def _refocus_basket(self, focused: int | None) -> None:
        """Keep the keyboard on the row, where it was; off an emptied row, to the list."""
        if self._active_basket_has_items():
            self._active_basket_row().enter_focus(focused)
            return
        self._nav_to_word_list_or_input()

    def _nav_to_word_list_or_input(self) -> None:
        """Focus the list's first row (the word or tag list), or the box if it is empty."""
        if self._get_active_chip_buttons():
            self._nav_focus_area = "tags"
            self._nav_focused_chip_idx = 0
            self._nav_list_sub = "word"
            self._draw_chip_focus()
        else:
            self._nav_focus_area = "input"
            self._focus_active_input()

    def _nav_enter_basket(self) -> None:
        self._nav_focus_area = "basket"
        self._active_basket_row().enter_focus(0)

    def _handle_basket_key(self, key: int) -> bool:
        """Keys on the picked-words (or picked-tags) row, under the search box.

        Left and Right walk it, and Enter flips ALL/ANY, takes a word out, or steps
        a tag on. Down goes to the list (or the results, with no list), Up to the box.
        """
        row = self._active_basket_row()
        match row.handle_key(key):
            case RowKey.UNHANDLED:
                return False
            case RowKey.EXIT_DOWN if (
                self._get_active_chip_buttons() or self._get_active_result_rows()
            ):
                row.clear_focus()
                if self._get_active_chip_buttons():
                    self._nav_to_word_list_or_input()
                else:
                    self._nav_enter_results()
                    self._draw_result_focus()
            case RowKey.EXIT_UP:
                row.clear_focus()
                self._nav_focus_area = "input"
                self._focus_active_input()
            case RowKey.EXIT_ESCAPE:
                self._nav_escape()
            case _:
                pass
        return True

    def _show_word_results(self, word: str, *, new_search: bool = True) -> None:
        """Run the word search under the current speaker filter and list its titles.

        A new word (not the last one again under another filter) that the speaker
        never says, but others do, lifts the filter rather than list nothing.
        """
        found = self._find_word_stories(self._speaker or None)
        if new_search and self._speaker and not found:
            everyone = self._find_word_stories(None)
            if everyone:
                self._lift_speaker(word)
                found = everyone
        self._list_word_stories(found, word)

    def _lift_speaker(self, searched: str) -> None:
        """Go back to anyone: the picked speaker says none of a new search, which others say."""
        logger.info(log_markers.SPEAKER_FILTER_LIFTED.format(speaker=self._speaker, text=searched))
        self._speaker = _ALL_SPEAKERS

    def _find_word_stories(self, speaker: str | None) -> dict[str, TitleInfo]:
        """Return the stories the listed word search finds, said by `speaker` (None: anyone).

        The typed query (or the picked words') when there is one, else the picked
        word; in the era and the tag scope either way.
        """
        word_filter = self._word_search_filter()
        if self._word_query:
            result = self._search.run_word_query(
                self._word_query, speaker=speaker, search_filter=word_filter
            )
            return result.title_dict
        found = self._search.find_words(self._selected_word, speaker=speaker)
        return found if word_filter is None else apply_filter(word_filter, found)

    def _list_word_stories(
        self, found: dict[str, TitleInfo], searched: str, hit_counts: dict[str, int] | None = None
    ) -> None:
        """List the stories a search found, each with its pages (and hit count, if given)."""
        results_layout: BoxLayout = self.ids.word_results_layout
        results_layout.clear_widgets()
        self._show_said_by_chip()

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

    def _get_offered_speakers(self) -> list[str]:
        """Return the speakers the filter offers: the index's roster ones, in its order.

        Read once, from the index's speaker sidecar. An index without one (built
        before speakers existed) offers none, and no chip shows. The roster's named
        characters and the narrator are offered; ``other:`` speakers are a long tail
        and are not.
        """
        if self._offered_speakers is None:
            indexed = self._search.get_speakers()
            self._offered_speakers = [
                s for s in (*CHARACTER_SPEAKER_OPTIONS, NARRATOR) if s in indexed
            ]
            if not self._offered_speakers:
                logger.debug("Word search: index has no speakers; no speaker filter.")
        return self._offered_speakers

    def _show_said_by_chip(self) -> None:
        """Show the speaker chip, naming the speaker, while a word search's stories are listed.

        None while nothing is searched, or the index has no speakers. Filled while a
        speaker is picked. The keyboard stays on it as its text changes.
        """
        if not (self._word_query or self._selected_word) or not self._get_offered_speakers():
            self._speaker_row.set_options([])
            return
        focused = self._speaker_row.focused
        self._speaker_row.set_options([(_SAID_BY, f"Said by: {_speaker_label(self._speaker)}")])
        self._speaker_row.set_selected(_SAID_BY if self._speaker else "")
        if focused is not None:
            self._speaker_row.enter_focus(0)

    def _on_said_by_chip_pressed(self, _value: str) -> None:
        """Open the list of who says what was searched, each with their stories."""
        self._speaker_row.set_selected(_SAID_BY if self._speaker else "")  # opening picks none
        counts = self._speaker_story_counts()
        dropdown = self._said_by_dropdown
        dropdown.clear_widgets()
        for i, (speaker, count) in enumerate(counts):
            item = _SaidByItem(
                text=_speaker_label(speaker),
                value=speaker,
                count_text=str(count),
                row_index=i,
                selected=speaker == self._speaker,
            )
            item.bind(on_release=lambda _b, v=speaker: dropdown.select(v))
            dropdown.add_widget(item)
        chip = cast("Widget", self._speaker_row.chips[0])
        if not open_dropdown(dropdown, chip):
            return
        logger.info(log_markers.SPEAKER_LIST_OPENED.format(count=len(counts) - 1))
        if self._nav_focus_area == "speakers" and self._speaker_row.focused is not None:
            # By the remote: it walks the list, from the speaker picked now.
            self._nav_focus_area = "said_by_list"
            self._speaker_row.clear_focus()
            here = next(i for i, (speaker, _) in enumerate(counts) if speaker == self._speaker)
            self._enter_dropdown_nav(here)

    def _speaker_story_counts(self) -> list[tuple[str, int]]:
        """Return anyone's stories, then each speaker's who says what was searched, most first.

        Each count is the search run again under that speaker: the filter wants
        every bubble a typed query finds to be the speaker's, so counting everyone's
        bubbles could give too many. The picked speaker stays listed at none, so
        the filter can be lifted from the list.
        """
        total = len(self._find_word_stories(None))
        counts = [(s, len(self._find_word_stories(s))) for s in self._get_offered_speakers()]
        listed = [(s, n) for s, n in counts if n or s == self._speaker]
        listed.sort(key=lambda speaker_count: -speaker_count[1])  # stable: roster order on ties
        return [(_ALL_SPEAKERS, total), *listed]

    def _on_said_by_item_selected(self, _dropdown: Widget, speaker: str) -> None:
        """Narrow the word results to the speaker picked from the list, or lift the filter."""
        self._speaker = speaker
        logger.info(log_markers.SPEAKER_FILTER_SET.format(speaker=speaker or "All"))
        self._rerun_word_results()
        self._show_said_by_chip()

    def _on_said_by_dismissed(self, _dropdown: Widget) -> None:
        """Give the keyboard back to the speaker chip when the list closes under it."""
        if not self._dropdown_nav_mode:
            return
        self._exit_dropdown_nav()
        self._nav_focus_area = "speakers"
        self._speaker_row.enter_focus(0)

    def _handle_said_by_list_key(self, key: int) -> bool:
        """Keys while the speaker list is open: Up, Down, Enter, Escape; the rest wait."""
        self._handle_dropdown_key(key)
        return True

    # --- DropdownNavMixin hooks ---

    def _get_dropdown_buttons(self) -> list[Button]:
        """Return the speaker list's rows, top to bottom."""
        return list(reversed(self._said_by_dropdown.container.children))

    def _dismiss_dropdown(self) -> None:
        self._said_by_dropdown.dismiss()

    def _activate_dropdown_item(self) -> None:
        # At once, as Enter presses everything on this screen: the list closes on it.
        self._dropdown_buttons_cache[self._dropdown_focused_idx].trigger_action(duration=0)

    # --- The era, for both searches ---

    def _on_era_selected(self, value: str) -> None:
        """List both searches' stories again from the era a row just picked."""
        self._set_era(value)

    def _set_era(self, value: str) -> None:
        if value == self._era.value:
            for row in self._era_rows.values():
                row.set_selected(value)
            return
        self._era.select(value)
        logger.info(log_markers.ERA_FILTER_SET.format(era=self._era.label))
        for row in self._era_rows.values():
            row.set_selected(self._era.value)
        self._rerun_tag_results()
        self._rerun_word_results()

    def _rerun_tag_results(self) -> None:
        if self._tag_basket_results:
            self._run_tag_basket()
        elif self._listed_tag:
            self._show_tag_titles(self._listed_tag)

    def _panel_rows(self) -> list[tuple[str, ChipRow]]:
        """Return the active results panel's chip rows, top to bottom, by nav area.

        Word search: the speakers (when the index has them), the era, and the tag
        scope (while tags are selected). Tag search: the era.
        """
        if self._active_mode == "Tag":
            return [("era", self._era_rows["Tag"])]
        if self._active_mode != "Word":
            return []
        rows = [("speakers", self._speaker_row)] if self._speaker_row.chips else []
        rows.append(("era", self._era_rows["Word"]))
        if self._scope_row.chips:
            rows.append(("scope", self._scope_row))
        return rows

    def _nav_enter_panel_row(self, area: str) -> None:
        self._nav_focus_area = area
        dict(self._panel_rows())[area].enter_focus()

    def _nav_enter_era(self) -> None:
        self._nav_enter_panel_row("era")

    def _handle_panel_row_key(self, key: int) -> bool:
        """Keys on a chip row of the results panel: the speakers, the era, the tag scope.

        The row walks its chips with Left and Right, and Enter picks one and stays
        put, so a filter can be tried out without losing one's place. Left off the
        first chip goes back to the list; Down goes to the row below, then the
        stories; Up to the row above, then the search box.
        """
        rows = self._panel_rows()
        areas = [area for area, _ in rows]
        here = areas.index(self._nav_focus_area)
        row = rows[here][1]
        match row.handle_key(key):
            case RowKey.UNHANDLED:
                return False
            case RowKey.EXIT_LEFT if self._get_active_chip_buttons():
                row.clear_focus()
                if self._active_mode == "Word":
                    self._nav_back_to_word_chips()
                else:
                    self._nav_back_to_tag_chips()
            case RowKey.EXIT_DOWN if here + 1 < len(rows):
                row.clear_focus()
                self._nav_enter_panel_row(areas[here + 1])
            case RowKey.EXIT_DOWN if self._get_active_result_rows():
                row.clear_focus()
                self._nav_enter_results()
                self._draw_result_focus()
            case RowKey.EXIT_UP if here > 0:
                row.clear_focus()
                self._nav_enter_panel_row(areas[here - 1])
            case RowKey.EXIT_UP:
                row.clear_focus()
                self._nav_focus_area = "input"
                self._focus_active_input()
            case RowKey.EXIT_ESCAPE:
                self._nav_escape()
            case _:  # handled on the row, or a way out to nowhere: stay on the row
                pass
        return True

    def _rerun_word_results(self) -> None:
        if self._word_query:
            self._run_word_query(
                self._word_query, list_words=not self._basket_results, new_search=False
            )
        elif self._selected_word:
            self._show_word_results(self._selected_word, new_search=False)

    # --- The word search's tag scope ---

    def _selected_tags(self) -> tuple[str, frozenset[str]] | None:
        """Return the tags the tag search has selected, as typed, and their stories' titles.

        The tags picked with +, or, with none picked, the one tag whose stories are
        listed; None when there are neither.
        """
        if self._tag_basket.selection().included:
            selection = self._tag_basket.selection()
            titles = self._search.titles_for_tag_selection(selection)
            return selection.describe(), frozenset(ENUM_TO_STR_TITLE[t] for t in titles)
        if self._listed_tag:
            _, titles = self._search.resolve_tag(self._listed_tag.lower())
            return self._listed_tag, frozenset(ENUM_TO_STR_TITLE[t] for t in titles or [])
        return None

    def _refresh_tag_scope(self) -> None:
        """Offer 'Only in: <tags>' for the tags selected now; lift the scope if there are none.

        A scope in force follows a changed selection, and the word results are
        listed again under it.
        """
        selected = self._selected_tags()
        was_on = self._scope_row.selected == _ONLY_IN_TAGS
        old_titles = self._scope_titles
        if selected is None:
            self._scope_tags, self._scope_titles = "", frozenset()
            self._scope_row.set_options([])
            self._scope_row.set_selected(_EVERYWHERE)
            if was_on:
                logger.info(log_markers.WORD_TAG_FILTER_SET.format(tags="Everywhere"))
                self._rerun_word_results()
            return
        self._scope_tags, self._scope_titles = selected
        label = textwrap.shorten(f"Only in: {self._scope_tags}", _MAX_SCOPE_LABEL, placeholder="…")
        self._scope_row.set_options([(_EVERYWHERE, "Everywhere"), (_ONLY_IN_TAGS, label)])
        if was_on and self._scope_titles != old_titles:
            logger.info(log_markers.WORD_TAG_FILTER_SET.format(tags=self._scope_tags))
            self._rerun_word_results()

    def _on_scope_selected(self, value: str) -> None:
        """List the word search's stories again, everywhere or only in the tags' stories."""
        tags = self._scope_tags if value == _ONLY_IN_TAGS else "Everywhere"
        logger.info(log_markers.WORD_TAG_FILTER_SET.format(tags=tags))
        self._rerun_word_results()

    def _word_search_filter(self) -> SearchFilter | None:
        """Return the word search's story filter: the era's years and the tag scope's stories."""
        tag_titles = self._scope_titles if self._scope_row.selected == _ONLY_IN_TAGS else None
        if self._era.years is None and tag_titles is None:
            return None
        return SearchFilter(years=self._era.years, tag_titles=tag_titles)

    def _nav_enter_speakers(self) -> None:
        """Focus the speaker row, on the selected chip."""
        self._nav_enter_panel_row("speakers")

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
            speaker=self._speaker or None,
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
        self._word_basket.clear()
        self._show_basket()
        self._basket_results = False
        self._speaker = _ALL_SPEAKERS
        self._show_said_by_chip()
        self._set_era(ALL_YEARS)
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
        if self._active_mode == "Tag" and self._tag_box_query:
            self._run_tag_query(self._tag_box_query)
            self._focus_after_query()
            return
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
        self._nav_list_sub = "word"
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

    def _focus_after_tag_query(self) -> None:
        """From combined tags: their first story, else the picked-tags row, else the box."""
        if self._tag_titles:
            self._nav_enter_results()
            Clock.schedule_once(
                lambda _dt: Clock.schedule_once(lambda _dt2: self._draw_result_focus())
            )
        elif self._tag_basket:
            self._nav_enter_basket()
        elif self._tag_box_query:  # it could not be combined: the notice is under its chip
            self._nav_focus_area = "tags"
            self._nav_focused_chip_idx = 0
            self._draw_chip_focus()
        else:
            self._nav_focus_area = "input"
            self._focus_active_input()

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
        self._basket_row.clear_focus()
        self._tag_basket_row.clear_focus()
        for era_row in self._era_rows.values():
            era_row.clear_focus()
        self._scope_row.clear_focus()
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
            "speakers": self._handle_panel_row_key,
            "said_by_list": self._handle_said_by_list_key,
            "scope": self._handle_panel_row_key,
            "basket": self._handle_basket_key,
            "era": self._handle_panel_row_key,
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
                # At the text's end: the x beside the box, which clears the search (its
                # picked words or tags, and the era, too); Right again is the results.
                self._blur_all_inputs()
                self._nav_focus_area = "clear"
                self._draw_clear_focus()
            else:
                return False
        else:
            # Let the text input handle the key
            return False
        return True

    def _nav_to_tags_or_results(self) -> None:
        if self._active_basket_has_items():
            self._nav_enter_basket()
            return
        self._nav_list_sub = "word"
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
        elif self._panel_rows():
            # The panel's lowest chip row sits directly above the results.
            self._clear_result_focus()
            self._nav_enter_panel_row(self._panel_rows()[-1][0])

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
            self._nav_back_to_tag_chips()
        else:
            self._clear_result_focus()
            self._nav_focus_area = "clear"
            self._draw_clear_focus()
        return True

    def _nav_back_to_tag_chips(self) -> None:
        """Focus the tag list: the selected member chip if one is active, else the tag's."""
        self._nav_focus_area = "tags"
        self._nav_list_sub = "word"
        tag_chips = self._get_tag_chip_buttons()
        target = self._selected_member or self._selected_tag
        self._nav_focused_chip_idx = next(
            (i for i, c in enumerate(tag_chips) if c.text == target), 0
        )
        self._draw_chip_focus()

    def _nav_back_to_word_chips(self) -> None:
        """Focus the word chip list, on the selected word."""
        self._nav_focus_area = "tags"
        self._nav_list_sub = "word"
        word_buttons = self._get_word_chip_buttons()
        selected = self._get_selected_chip_text()
        self._nav_focused_chip_idx = next(
            (i for i, b in enumerate(word_buttons) if b.text == selected), 0
        )
        self._draw_chip_focus()

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
        self._basket_row.clear_focus()
        self._tag_basket_row.clear_focus()
        for era_row in self._era_rows.values():
            era_row.clear_focus()
        self._scope_row.clear_focus()
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
            if self._get_active_result_rows():  # with none, the focus stays on the x
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
        if self._active_mode in ("Tag", "Word") and self._handle_list_row_key(key, chips):
            return True
        if key == KEY_DOWN:
            if chips and self._nav_focused_chip_idx < len(chips) - 1:
                self._nav_focused_chip_idx += 1
                self._draw_chip_focus()
        elif key == KEY_RIGHT:
            self._clear_chip_focus()
            self._nav_list_sub = "word"
            # The panel's top chip row is the first thing to the right of the list.
            self._nav_enter_panel_row(self._panel_rows()[0][0])
        elif key in (KEY_LEFT, KEY_UP):
            self._handle_tags_up()
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

    def _handle_tags_up(self) -> None:
        """Up (or Left) on a list: the chip before; off the first, what sits above."""
        if self._nav_focused_chip_idx > 0:
            self._nav_focused_chip_idx -= 1
            self._draw_chip_focus()
            return
        self._clear_chip_focus()
        if self._active_basket_has_items():
            self._nav_enter_basket()  # the picked words or tags sit above the list
        else:
            self._nav_focus_area = "input"
            self._focus_active_input()

    def _handle_list_row_key(self, key: int, chips: list[Button]) -> bool:
        """Keys between a word's or tag's row and its +; False for the list's own keys.

        Right on the word or tag moves to its +, Left back; Enter on the + picks it
        or puts it back, and stays there.
        """
        if not chips:
            return False
        chip = chips[min(self._nav_focused_chip_idx, len(chips) - 1)]
        row = chip.parent if isinstance(chip.parent, (_WordRow, _TagRow)) else None
        on_plus = row is not None and self._nav_list_sub == "plus"
        if key == KEY_RIGHT and row is not None and not on_plus:
            self._nav_list_sub = "plus"
        elif key == KEY_LEFT and on_plus:
            self._nav_list_sub = "word"
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER) and row is not None and on_plus:
            if isinstance(row, _TagRow):
                self._toggle_tag_basket(_tag_name(row.chip.text))
            else:
                self._toggle_basket_word(row.item.text)
        else:
            return False
        self._draw_chip_focus()
        return True

    def _handle_tags_enter(self, chips: list[Button]) -> None:
        if not chips or self._nav_focused_chip_idx >= len(chips):
            return
        focused_chip = chips[self._nav_focused_chip_idx]
        if isinstance(focused_chip, (_QueryRowButton, _SuggestionButton, _TagQueryChip)):
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
                result.extend(_chips_of(stack))
        return result

    def _get_member_chip_buttons(self) -> list[_TagChipButton]:
        if not hasattr(self.ids, "tag_chips_layout"):
            return []
        result: list[_TagChipButton] = []
        for stack in reversed(self.ids.tag_chips_layout.children):
            if getattr(stack, "is_member_layout", False):
                result.extend(_chips_of(stack))
        return result

    def _get_tag_chip_buttons(self) -> list[_TagChipButton]:
        """Return all tag chips (main + member) in visual order for keyboard nav."""
        if not hasattr(self.ids, "tag_chips_layout"):
            return []
        result: list[_TagChipButton] = []
        for stack in reversed(self.ids.tag_chips_layout.children):
            result.extend(_chips_of(stack))
        return result

    def _get_word_chip_buttons(self) -> list[Button]:
        if not hasattr(self.ids, "word_chips_layout"):
            return []
        # A word row's text, and the query and suggestion rows; not a notice, nor the
        # disabled "... N more" row that ends a long list.
        return [
            c.word_button if isinstance(c, _WordRow) else c
            for c in reversed(self.ids.word_chips_layout.children)
            if not c.disabled
        ]

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
            target = chips[self._nav_focused_chip_idx]
            if self._nav_list_sub == "plus" and isinstance(target.parent, _WordRow):
                target = target.parent.plus_button
            else:
                self._nav_list_sub = "word"
            widgets = self._word_list_focus_widgets(chips)
            update_focus_in_list(widgets, widgets.index(target), _SEARCH_NAV_FOCUS_GROUP)
            self.ids.word_chips_scroll.scroll_to(target)
        else:
            self._draw_tag_chip_focus(chips)

    def _draw_tag_chip_focus(self, chips: list[_TagChipButton]) -> None:
        """Border the focused tag chip; or, on its +, ring the + and border no chip."""
        chip = chips[self._nav_focused_chip_idx]
        pluses = [row.plus_button for row in self._tag_rows()]
        if self._nav_list_sub == "plus" and isinstance(chip.parent, _TagRow):
            self._update_tag_chip_colors(chips)
            update_focus_in_list(
                pluses, pluses.index(chip.parent.plus_button), _SEARCH_NAV_FOCUS_GROUP
            )
            return
        self._nav_list_sub = "word"
        clear_focus_in_list(pluses, _SEARCH_NAV_FOCUS_GROUP)
        self._update_tag_chip_colors(chips, self._nav_focused_chip_idx)

    def _clear_chip_focus(self) -> None:
        chips = self._get_active_chip_buttons()
        if self._active_mode == "Word":
            clear_focus_in_list(self._word_list_focus_widgets(chips), _SEARCH_NAV_FOCUS_GROUP)
        else:
            clear_focus_in_list(
                [row.plus_button for row in self._tag_rows()], _SEARCH_NAV_FOCUS_GROUP
            )
            self._update_tag_chip_colors(chips)

    def _word_list_focus_widgets(self, chips: list[Button]) -> list[Button]:
        """Return the word list's rows and their + buttons: all a focus ring can be on."""
        return [*chips, *(row.plus_button for row in self._word_rows())]

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
