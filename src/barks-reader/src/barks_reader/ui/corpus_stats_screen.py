"""The Introduction "By the Numbers" screen: the whole corpus on one page.

A full-window screen shaped like a comic page, sitting beside the other two
Introduction pages (the Compleat Barks Reader document and the Don Ault article),
which are also full-window and also do not scroll. Two opening lines run the width
of the page; below them the six sections are split into two columns.

Nothing here scrolls, so the fit is arithmetic rather than negotiated: every size
is a constant from ``core.corpus_stats_layout`` multiplied by one scale factor
derived from the page width. That module is Kivy-free and carries the test that
proves the content fits.

The one piece of ornament is load-bearing. Rows that are slices of the same whole -
the five attribution buckets, the three length bands - carry a ``share``, drawn as
a bar behind the row. Nothing else gets one, so the presence of a bar signals that
a group adds up to something, and its absence marks a total, a rate or a named
story.

The dialogue section is filled in a beat late: the word counts need a full pass
over the Whoosh speech index, so that runs on a background thread. Its slot is
reserved at full height from the start, because a page that cannot scroll must not
reflow when the scan lands.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.lang import Builder
from kivy.properties import StringProperty  # ty: ignore[unresolved-import]
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from loguru import logger

from barks_reader.core import corpus_stats_layout as layout
from barks_reader.core.corpus_stats import (
    TEXT_SECTION_SHAPE,
    compute_static_stats,
    compute_text_stats,
)
from barks_reader.core.reader_consts_and_types import INTRO_BY_THE_NUMBERS_TEXT
from barks_reader.core.reader_formatter import get_action_bar_title
from barks_reader.core.reader_palette import theme
from barks_reader.core.reader_utils import COMIC_PAGE_ASPECT_RATIO

from .action_bar_helpers import ACTION_BAR_SIZE_Y
from .font_manager import FontManager
from .reader_keyboard_nav import KEY_LEFT, KEY_UP, ActionBarNavMixin, is_escape_key
from .reader_screens import ReaderScreen

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from barks_reader.core.corpus_stats import CorpusStats, Opening, StatRow, StatSection

CORPUS_STATS_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

# The same face the index screens use: a plain, tabular-friendly sans.
_FONT_NAME = FontManager.main_index_item_font_name

# The app's own hand-lettered face, used once, for the opening line.
_DISPLAY_FONT_NAME = FontManager.main_title_font_name

# The share bar: an unfilled track the width of the row, and the row's own slice
# filled over it. The track is what makes a one-percent slice read as "almost none
# of it" rather than as a rendering artefact.
_BAR_TRACK_ALPHA = 0.45
_BAR_FILL_ALPHA = 1.0


class CorpusStatsScreen(ReaderScreen, ActionBarNavMixin):
    """Full-window page showing corpus-wide statistics in two columns.

    Args:
        indexes_dir: The Barks Reader ``Indexes`` directory, used for the dialogue
            statistics. That section is left empty if it holds no index.
        font_manager: Supplies the action bar's title size. The page body sizes
            itself; see the module docstring.
        on_close_screen: Called to hand the window back to the main screen.

    """

    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
    ASPECT_RATIO = COMIC_PAGE_ASPECT_RATIO
    action_bar_title = StringProperty()
    app_icon_filepath = StringProperty()

    def __init__(
        self,
        indexes_dir: Path,
        font_manager: FontManager,
        on_close_screen: Callable[[], None],
        **kwargs: str,
    ) -> None:
        super().__init__(**kwargs)

        self._indexes_dir = indexes_dir
        self._font_manager = font_manager
        self._on_close_screen = on_close_screen
        self._stats: CorpusStats | None = None
        self._text_section: StatSection | None = None
        self._text_scan_started = False

        self._setup_action_bar_nav([self.ids.close_button])

        # A resize drag would otherwise rebuild the page on every frame.
        self._rebuild_trigger = Clock.create_trigger(lambda _dt: self._rebuild(), 0)
        self.ids.stats_page.bind(width=lambda *_args: self._rebuild_trigger())

    # --- Lifecycle -------------------------------------------------------

    def open(self) -> None:
        """Show the page, computing the statistics the first time."""
        self.action_bar_title = get_action_bar_title(self._font_manager, INTRO_BY_THE_NUMBERS_TEXT)
        if self._stats is None:
            self._stats = compute_static_stats()
        self._rebuild()
        self._start_text_scan()

        # Unbind first: re-opening without a close in between would double-bind.
        Window.unbind(on_key_down=self._on_key_down)
        Window.bind(on_key_down=self._on_key_down)

    def close(self) -> None:
        """Hand the window back to the main screen."""
        if self._menu_mode:
            self._exit_menu_mode()
        Window.unbind(on_key_down=self._on_key_down)
        self._on_close_screen()

    # --- Content ---------------------------------------------------------

    def _rebuild(self) -> None:
        """Lay the whole page out at the current scale."""
        if self._stats is None:
            return

        page = self.ids.stats_page
        scale = layout.scale_for(page.width)
        side_pad = layout.PAGE_SIDE_PADDING_FRACTION * page.width
        vertical_pad = layout.PAGE_VERTICAL_PADDING_FRACTION * page.width

        page.padding = [
            side_pad,
            self.ACTION_BAR_HEIGHT + vertical_pad,
            side_pad,
            vertical_pad,
        ]
        self.ids.stats_columns.spacing = layout.COLUMN_GUTTER_FRACTION * page.width

        self._build_opening(self._stats.opening, scale)

        left, right = layout.split_columns(self._stats.sections)
        self._build_column(self.ids.stats_left, left, scale)
        self._build_column(self.ids.stats_right, right, scale, words_slot=True)

    def _build_opening(self, opening: Opening, scale: float) -> None:
        box = self.ids.stats_opening
        box.clear_widgets()
        box.height = layout.opening_height() * scale

        box.add_widget(
            self._line(
                opening.headline,
                color=theme().text_display,
                font_name=_DISPLAY_FONT_NAME,
                font_size=layout.DESIGN.headline * scale,
                height=layout.DESIGN.headline_height * scale,
                valign="bottom",
            )
        )
        box.add_widget(
            self._line(
                opening.standfirst,
                color=theme().text_secondary,
                font_name=_FONT_NAME,
                font_size=layout.DESIGN.standfirst * scale,
                height=layout.DESIGN.standfirst_height * scale,
                valign="top",
            )
        )
        box.add_widget(Widget(size_hint_y=None, height=layout.DESIGN.opening_gap * scale))

    def _build_column(
        self,
        column: BoxLayout,
        sections: Sequence[StatSection],
        scale: float,
        *,
        words_slot: bool = False,
    ) -> None:
        column.clear_widgets()
        for section in sections:
            column.add_widget(self._build_section(section, scale))
            column.add_widget(Widget(size_hint_y=None, height=layout.DESIGN.section_gap * scale))

        if words_slot:
            column.add_widget(self._build_words_slot(scale))
            column.add_widget(Widget(size_hint_y=None, height=layout.DESIGN.section_gap * scale))

        # Everything stacks from the top; this soaks up whatever is left over.
        column.add_widget(Widget())

    def _build_words_slot(self, scale: float) -> BoxLayout:
        """Build the dialogue section's slot at its full declared height.

        The slot is the same height whether or not the background scan has landed,
        so a page that cannot scroll never reflows under the reader.
        """
        slot = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=layout.reserved_height(TEXT_SECTION_SHAPE) * scale,
        )
        if self._text_section is not None:
            self._fill_section(slot, self._text_section, scale)
        else:
            slot.add_widget(self._heading("The words", scale))
            slot.add_widget(Widget())
        return slot

    def _build_section(self, section: StatSection, scale: float) -> BoxLayout:
        box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=layout.section_height(section) * scale,
        )
        self._fill_section(box, section, scale)
        return box

    def _fill_section(self, box: BoxLayout, section: StatSection, scale: float) -> None:
        box.add_widget(self._heading(section.heading, scale))
        for stat_row in section.rows:
            box.add_widget(self._row(stat_row, scale))
        if section.footnote:
            box.add_widget(self._footnote(section.footnote, scale))

    def _heading(self, text: str, scale: float) -> Label:
        """Build a section heading.

        Set as written rather than upper-cased, and with no rule beneath it: the
        weight, the colour and the space above already separate it from the rows.
        """
        return self._line(
            text,
            color=theme().search_heading,
            font_name=_FONT_NAME,
            font_size=layout.DESIGN.heading * scale,
            height=layout.DESIGN.heading_height * scale,
            valign="bottom",
            bold=True,
        )

    def _row(self, stat_row: StatRow, scale: float) -> BoxLayout:
        """Build one statistics line, in whichever of the two shapes it needs."""
        if stat_row.prose:
            return self._prose_row(stat_row, scale)

        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=layout.DESIGN.row_height * scale,
            spacing=layout.DESIGN.label_value_gap * scale,
        )
        if stat_row.share is not None:
            _add_share_bar(row, stat_row.share)

        row.add_widget(self._label_cell(stat_row.label, scale))
        row.add_widget(self._value_cell(stat_row.value, scale))
        return row

    def _label_cell(self, text: str, scale: float) -> Label:
        """Build the left-hand label, which takes whatever the value leaves."""
        label = self._cell(text, theme().text_secondary, "left", scale)
        # Cut with an ellipsis rather than wrap. A label too wide for its column
        # would otherwise wrap to a second line the row has no height to show, and
        # go silently missing. The real width constraint is tested in the layout
        # module; this is the visible failure mode if it is ever violated.
        label.shorten = True
        label.shorten_from = "right"
        label.bind(size=lambda w, _s: setattr(w, "text_size", (w.width, w.height)))
        return label

    def _value_cell(self, text: str, scale: float) -> Label:
        """Build the right-hand figure, sized to its own text.

        The value takes exactly the width it needs so the label can have the rest;
        splitting the row evenly would leave the longer labels too little room.
        """
        value = self._cell(text, theme().text_title, "right", scale, bold=True)
        value.size_hint_x = None
        value.bind(texture_size=lambda w, size: setattr(w, "width", size[0]))
        return value

    def _prose_row(self, stat_row: StatRow, scale: float) -> BoxLayout:
        """Build a row whose value is a name, stacked so it reads as one.

        A story title squeezed into the right-hand figure column reads as a number
        that failed to be a number, and is the first thing to be truncated. Given
        its own lines it reads as what it is.
        """
        box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=layout.DESIGN.row_height * layout.PROSE_ROW_HEIGHT_UNITS * scale,
        )
        label = self._cell(
            stat_row.label,
            theme().text_secondary,
            "left",
            scale,
            height=layout.DESIGN.row_height * scale,
        )
        label.bind(size=lambda w, _s: setattr(w, "text_size", (w.width, w.height)))
        box.add_widget(label)

        value = self._cell(stat_row.value, theme().text_title, "left", scale, bold=True)
        value.valign = "top"
        value.bind(size=lambda w, _s: setattr(w, "text_size", (w.width, w.height)))
        box.add_widget(value)
        return box

    def _cell(
        self,
        text: str,
        color: tuple,
        halign: str,
        scale: float,
        *,
        bold: bool = False,
        height: float | None = None,
    ) -> Label:
        label = Label(
            text=f"[b]{text}[/b]" if bold else text,
            markup=True,
            color=color,
            font_name=_FONT_NAME,
            font_size=layout.DESIGN.row * scale,
            halign=halign,
            valign="middle",
        )
        if height is not None:
            label.size_hint_y = None
            label.height = height
        return label

    def _footnote(self, text: str, scale: float) -> Label:
        """Build a section's caveat line.

        Sized as fine print rather than as the smallest type on the page: these
        lines are where the page admits what it does not know, and a caveat nobody
        can read across a room is not a caveat.
        """
        return self._line(
            text,
            color=theme().text_secondary,
            font_name=_FONT_NAME,
            font_size=layout.DESIGN.footnote * scale,
            height=2.0 * layout.DESIGN.footnote_line_height * scale,
            valign="middle",
            italic=True,
        )

    def _line(
        self,
        text: str,
        *,
        color: tuple,
        font_name: str,
        font_size: float,
        height: float,
        valign: str,
        bold: bool = False,
        italic: bool = False,
    ) -> Label:
        """Build a full-width, left-aligned line of text."""
        markup_text = text
        if bold:
            markup_text = f"[b]{markup_text}[/b]"
        if italic:
            markup_text = f"[i]{markup_text}[/i]"

        label = Label(
            text=markup_text,
            markup=True,
            color=color,
            font_name=font_name,
            font_size=font_size,
            halign="left",
            valign=valign,
            size_hint_y=None,
            height=height,
        )
        label.bind(size=lambda w, _s: setattr(w, "text_size", (w.width, w.height)))
        return label

    # --- Background text scan --------------------------------------------

    def _start_text_scan(self) -> None:
        """Scan the speech index off the UI thread; it takes about half a second."""
        if self._text_scan_started:
            return
        self._text_scan_started = True
        threading.Thread(target=self._scan_text_stats, daemon=True).start()

    def _scan_text_stats(self) -> None:
        try:
            section = compute_text_stats(self._indexes_dir)
        except Exception:  # noqa: BLE001
            # A background thread must not take the app down, and the page is
            # perfectly usable with that one section left empty.
            logger.exception("CorpusStats: dialogue statistics scan failed.")
            return

        if section is None:
            logger.info("CorpusStats: no speech index; leaving the dialogue section empty.")
            return

        def _apply(_dt: float) -> None:
            self._text_section = section
            self._rebuild()

        Clock.schedule_once(_apply, 0)

    # --- Keyboard --------------------------------------------------------

    def _on_key_down(
        self, _window: object, key: int, _scancode: int, _codepoint: str, _modifier: list[str]
    ) -> bool:
        return self._handle_reader_key(key)

    def _handle_reading_key(self, key: int) -> bool:
        """Handle a key while not in the action bar.

        Deliberately different from the readers this screen otherwise copies: they
        map Escape to the action-bar menu because they have pages to turn, but this
        page has neither, and Escape that did not leave would be a regression on the
        bottom-panel version. Up still reaches the Close button for a remote.
        """
        if is_escape_key(key) or key == KEY_LEFT:
            self.close()
        elif key == KEY_UP:
            self._enter_menu_mode()
        else:
            return False
        return True

    def _reading_next_page(self) -> None:
        """No-op: the fact sheet is a single page."""

    def _reading_prev_page(self) -> None:
        """No-op: the fact sheet is a single page."""

    def on_touch_down(self, touch: object) -> bool:
        self._clear_menu_on_touch()
        return bool(super().on_touch_down(touch))


def _add_share_bar(row: BoxLayout, share: float) -> None:
    """Draw a row's share of its section's whole as a bar behind it.

    Args:
        row: The row widget to paint behind.
        share: The fraction of the whole, in ``[0.0, 1.0]``.

    """
    track_rgb = tuple(theme().row_stripe_even[:3])
    fill_rgb = tuple(theme().row_stripe_odd[:3])
    fraction = min(1.0, max(0.0, share))

    canvas = row.canvas
    assert canvas is not None  # Kivy populates this on widget construction.
    with canvas.before:
        track_color = Color(*track_rgb, _BAR_TRACK_ALPHA)
        track = Rectangle()
        fill_color = Color(*fill_rgb, _BAR_FILL_ALPHA)
        fill = Rectangle()

    def _update(*_args: object) -> None:
        track_color.rgba = (*track_rgb, _BAR_TRACK_ALPHA)
        track.pos = row.pos
        track.size = row.size
        fill_color.rgba = (*fill_rgb, _BAR_FILL_ALPHA)
        fill.pos = row.pos
        fill.size = (row.width * fraction, row.height)

    _update()
    row.bind(pos=_update, size=_update)


def get_corpus_stats_screen(
    screen_name: str,
    indexes_dir: Path,
    font_manager: FontManager,
    on_close_screen: Callable[[], None],
) -> CorpusStatsScreen:
    """Load the page's kv and build the screen."""
    Builder.load_file(str(CORPUS_STATS_SCREEN_KV_FILE))

    return CorpusStatsScreen(
        indexes_dir,
        font_manager,
        on_close_screen,
        name=screen_name,
    )
