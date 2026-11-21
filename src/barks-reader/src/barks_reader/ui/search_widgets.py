"""The search screen's own widgets, and the small functions that fill them.

Result rows, the chips of the tag list and of the filter rows, the syntax help: each a
class the kv rules in ``search_widgets.kv`` draw, none knowing of `SearchScreen`. The
classes keep their names, underscore and all: a focused widget is logged by its class
name, and the GUI tests wait on those lines.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Self

from barks_fantagraphics.barks_titles import STR_TITLE_TO_ENUM, Titles
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO, ComicBookInfo
from barks_fantagraphics.speech_speakers import speaker_display_name
from kivy.metrics import dp
from kivy.properties import (  # ty: ignore[import-not-found]
    BooleanProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

from barks_reader.core.reader_palette import theme
from barks_reader.core.search_chip_row import CHIP_BORDER_NONE, chip_bg_normal
from barks_reader.core.search_state import ALL_SPEAKERS

if TYPE_CHECKING:
    from collections.abc import Sequence

    from barks_fantagraphics.search_evaluate import Suggestion
    from kivy.input import MotionEvent
    from kivy.uix.widget import Widget

    from barks_reader.core.reader_colors import Color
    from barks_reader.core.search_help import HelpExamples

SEARCH_WIDGETS_KV_FILE = Path(__file__).with_suffix(".kv")


class _SearchResultButton(Button):
    """A clickable result row in a search results list."""

    row_index = NumericProperty(0)
    # Shown faintly at the row's right: a story's issue and year.
    detail = StringProperty("")
    # A cover's row says only that it is one, faintly: its issue is the detail.
    is_cover = BooleanProperty(defaultvalue=False)
    detail_width = NumericProperty(0)
    # Persistently highlights the last result the user opened (mouse or keyboard), so it
    # stays marked when they navigate away and come back. Distinct from the keyboard
    # focus ring, which tracks the live nav cursor.
    selected = BooleanProperty(defaultvalue=False)


COVER_ROW_TEXT = "[Cover]"


def _row_holding(part: Widget | None, rows: Sequence[Widget]) -> int | None:
    """Return the index of the row that is ``part`` or holds it, or None if none does."""
    if part is None:
        return None
    return next((i for i, row in enumerate(rows) if part is row or part in row.children), None)


def _show_from_the_top(layout: BoxLayout) -> None:
    """Show a list just filled from its first row: its scroll view keeps its place otherwise."""
    if isinstance(layout.parent, ScrollView):
        layout.parent.scroll_y = 1


def _listed_title(title_str: str) -> Titles | None:
    """Return the title a listed display title is, or None for a row that is no title."""
    return STR_TITLE_TO_ENUM.get(ComicBookInfo.get_title_str_from_display_title(title_str))


def _title_detail(title_str: str) -> str:
    """Return a listed story's issue and the year it came out: "FC 408, 1952"."""
    title = _listed_title(title_str)
    if title is None:
        return ""
    info = BARKS_TITLE_INFO[title]
    return f"{info.get_shortest_issue_title()}, {info.issue_year}"


class _QueryRowButton(_SearchResultButton):
    """The word list's first row while the box holds a query: pressing it runs the query."""


class _SuggestionButton(_SearchResultButton):
    """A close spelling for a word of the query that is in no story: pressing it swaps it in."""

    def __init__(self, suggestion: Suggestion, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.suggestion = suggestion


class _NoticeLabel(Label):
    """A line of the word list the user reads but cannot pick: a notice, a heading."""


class _SyntaxExample(Label):
    """Something to type, in a search box's syntax help."""


class _SyntaxMeaning(Label):
    """What an example in a search box's syntax help does."""


class SearchModeContent(BoxLayout):
    """One search mode's box and lists: shown, or hidden and kept out of the way of presses.

    Hidden, it is sized (0, 0) at the screen's bottom centre, but its fixed-size chips
    (the era row's, the picked tags') are not: each wraps to its own row there, over the
    shown mode's stories, and a press meant for a story pressed a hidden era chip.
    """

    shown = BooleanProperty(defaultvalue=True)

    def on_touch_down(self, touch: MotionEvent) -> bool:
        """Pass every press by while hidden; else as a BoxLayout does."""
        if not self.shown:
            return False
        return bool(super().on_touch_down(touch))


class SearchSyntaxHelp(BoxLayout):
    """A search box's syntax help: a heading, each example beside what it does, a note.

    Read, not picked: nothing in it takes focus or a tap.
    """

    heading = StringProperty()
    examples: HelpExamples = ObjectProperty(())
    note = StringProperty()  # under the examples; none takes no room

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._show_examples()

    def on_examples(self, _instance: Self, _examples: HelpExamples) -> None:
        """Show the examples again when they change."""
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
    ``is_group`` marks a tag group, with an arrow drawn beside the count (drawn:
    the font has no arrow glyph), pointing down while ``is_open`` (its members
    listed under it).
    """

    chip_bg_color = ObjectProperty(CHIP_BORDER_NONE)
    chip_border_color = ObjectProperty(CHIP_BORDER_NONE)
    count_text = StringProperty("")
    is_group = BooleanProperty(defaultvalue=False)
    is_open = BooleanProperty(defaultvalue=False)

    def __init__(self, **kwargs: object) -> None:
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


class _TagQueryChip(_TagChipButton):
    """The tag list's first chip while the box holds typed tags: pressing it combines them."""


class _BasketChipButton(_SpeakerChipButton):
    """A chip of the picked-words row: ALL/ANY, which flips, or a word, which comes out."""


def _make_basket_chip(value: str, label: str) -> _BasketChipButton:
    return _BasketChipButton(text=label, value=value)


# The speaker filter's one chip, by its value in its row: picked (filled) while a
# speaker is.
_SAID_BY = "said by"


def _speaker_label(speaker: str) -> str:
    """Return how the speaker filter names a stored speaker; anyone, for none."""
    return "anyone" if speaker == ALL_SPEAKERS else speaker_display_name(speaker) or speaker
