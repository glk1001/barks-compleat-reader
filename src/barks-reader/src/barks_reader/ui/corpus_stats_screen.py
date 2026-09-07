"""The Introduction "By the Numbers" screen: the whole corpus as a fact sheet.

Two opening lines over grouped label/value rows. All of the arithmetic lives in
``barks_reader.core.corpus_stats``; this module only turns its ``CorpusStats``
into widgets.

The one piece of ornament on the page is load-bearing. Rows that are slices of
the same whole - the five attribution buckets, the three length bands - carry a
``share``, and it is drawn as a bar behind the row. Nothing else gets one, so
the presence of a bar is itself the signal that a group adds up to something,
and its absence marks a total, a rate or a named story. That replaces the plain
zebra striping this page used to have, which cost the same to draw and said
nothing.

The dialogue section is filled in a beat late: everything else is instant, but
the word counts need a full pass over the Whoosh speech index, so that runs on a
background thread and appends its section when it lands. The result is cached,
so the scan happens at most once per app run.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty  # ty: ignore[unresolved-import]
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from loguru import logger

from barks_reader.core.corpus_stats import compute_static_stats, compute_text_stats
from barks_reader.core.reader_palette import theme

from .font_manager import FontManager
from .reader_keyboard_nav import (
    KEY_DOWN,
    KEY_LEFT,
    KEY_PAGE_DOWN,
    KEY_PAGE_UP,
    KEY_UP,
    is_escape_key,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.scrollview import ScrollView
    from kivy.uix.widget import Widget

    from barks_reader.core.corpus_stats import CorpusStats, Opening, StatRow, StatSection

CORPUS_STATS_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

# The same face the index screens use: a plain, tabular-friendly sans.
_FONT_NAME = FontManager.main_index_item_font_name

# The app's own hand-lettered face, used once, for the opening line.
_DISPLAY_FONT_NAME = FontManager.main_title_font_name

_HEADLINE_HEIGHT = 54
_STANDFIRST_HEIGHT = 30
_OPENING_GAP = 16
_HEADING_HEIGHT = 38
_ROW_HEIGHT = 28
_PROSE_LABEL_HEIGHT = 22
_PROSE_ROW_HEIGHT = 52
_FOOTNOTE_HEIGHT = 28
_SECTION_GAP = 12

_ROW_SIDE_PADDING = 14

# The share bar: an unfilled track the width of the row, and the row's own slice
# filled over it. The track is what makes a one-percent slice read as "almost
# none of it" rather than as a rendering artefact.
_BAR_TRACK_ALPHA = 0.45
_BAR_FILL_ALPHA = 1.0

# One arrow press moves the view by this fraction of the scrollable height; a
# page key moves by this much again. Tuned so a remote's cursor keys walk the
# page at a readable pace rather than jumping it.
_SCROLL_STEP = 0.08
_PAGE_SCROLL_STEP = 0.4


class CorpusStatsScreen(FloatLayout):
    """Screen showing corpus-wide statistics as an opening plus grouped rows.

    Args:
        indexes_dir: The Barks Reader ``Indexes`` directory, used for the
            dialogue statistics. The section is omitted if it holds no index.
        font_manager: Supplies the resolution-appropriate font family.

    """

    is_visible = BooleanProperty(defaultvalue=False)

    def __init__(self, indexes_dir: Path, font_manager: FontManager, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self._indexes_dir = indexes_dir
        self._font_manager = font_manager
        self._stats: CorpusStats | None = None
        self._text_section: StatSection | None = None
        self._text_scan_started = False
        self._nav_active = False
        self._nav_on_exit_request: Callable | None = None

    def on_is_visible(self, _instance: object, visible: bool) -> None:
        """Build the page the first time it is shown, then keep it."""
        if not visible or self._stats is not None:
            return

        self._stats = compute_static_stats()
        self._rebuild()
        self._start_text_scan()

    # --- Content ---------------------------------------------------------

    def _rebuild(self) -> None:
        """Repopulate the row list from the cached stats."""
        if self._stats is None:
            return

        rows = self.ids.corpus_stats_rows
        rows.clear_widgets()

        self._add_opening(self._stats.opening)
        sections = list(self._stats.sections)
        if self._text_section is not None:
            sections.append(self._text_section)
        for section in sections:
            self._add_section(section)

    def _add_opening(self, opening: Opening) -> None:
        """Add the two lines the page opens with."""
        rows = self.ids.corpus_stats_rows

        rows.add_widget(
            self._make_line(
                opening.headline,
                color=theme().text_display,
                font_name=_DISPLAY_FONT_NAME,
                font_size=self._font_manager.main_title_font_size,
                height=dp(_HEADLINE_HEIGHT),
                valign="bottom",
            )
        )
        rows.add_widget(
            self._make_line(
                opening.standfirst,
                color=theme().text_secondary,
                font_name=_FONT_NAME,
                font_size=self._font_manager.title_info_font_size,
                height=dp(_STANDFIRST_HEIGHT),
                valign="top",
            )
        )
        rows.add_widget(BoxLayout(size_hint_y=None, height=dp(_OPENING_GAP)))

    def _add_section(self, section: StatSection) -> None:
        rows = self.ids.corpus_stats_rows
        rows.add_widget(self._make_heading(section.heading))
        for stat_row in section.rows:
            rows.add_widget(self._make_row(stat_row))
        if section.footnote:
            rows.add_widget(self._make_footnote(section.footnote))
        rows.add_widget(BoxLayout(size_hint_y=None, height=dp(_SECTION_GAP)))

    def _make_heading(self, text: str) -> Label:
        """Build a section heading.

        Set as written rather than upper-cased, and with no rule beneath it: the
        weight, the colour and the space above already separate it from the rows.
        """
        return self._make_line(
            text,
            color=theme().search_heading,
            font_name=_FONT_NAME,
            font_size=self._font_manager.text_block_heading_font_size,
            height=dp(_HEADING_HEIGHT),
            valign="bottom",
            bold=True,
        )

    def _make_row(self, stat_row: StatRow) -> BoxLayout:
        """Build one statistics line, in whichever of the two shapes it needs."""
        if stat_row.prose:
            return self._make_prose_row(stat_row)

        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(_ROW_HEIGHT))
        if stat_row.share is not None:
            _add_share_bar(row, stat_row.share)

        row.add_widget(self._make_cell(stat_row.label, theme().text_secondary, "left", bold=False))
        row.add_widget(self._make_cell(stat_row.value, theme().text_title, "right", bold=True))
        return row

    def _make_prose_row(self, stat_row: StatRow) -> BoxLayout:
        """Build a row whose value is a name, stacked so it reads as one.

        A story title or a character name squeezed into the right-hand figure
        column reads as a number that failed to be a number, and is the first
        thing to be truncated. Given its own line it reads as what it is.
        """
        box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(_PROSE_ROW_HEIGHT))
        box.add_widget(
            self._make_cell(
                stat_row.label,
                theme().text_secondary,
                "left",
                bold=False,
                height=dp(_PROSE_LABEL_HEIGHT),
            )
        )
        box.add_widget(self._make_cell(stat_row.value, theme().text_title, "left", bold=True))
        return box

    def _make_cell(
        self,
        text: str,
        color: tuple,
        halign: str,
        *,
        bold: bool,
        height: float | None = None,
    ) -> Label:
        label = Label(
            text=f"[b]{text}[/b]" if bold else text,
            markup=True,
            color=color,
            font_name=_FONT_NAME,
            font_size=self._font_manager.main_index_item_font_size,
            halign=halign,
            valign="middle",
            shorten=True,
            shorten_from="right",
        )
        if height is not None:
            label.size_hint_y = None
            label.height = height
        label.bind(
            size=lambda w, _s: setattr(w, "text_size", (w.width - dp(_ROW_SIDE_PADDING), w.height))
        )
        return label

    def _make_footnote(self, text: str) -> Label:
        """Build a section's caveat line.

        Sized as fine print rather than as the smallest type in the app: these
        lines are where the page admits what it does not know, and a caveat
        nobody can read across a room is not a caveat.
        """
        return self._make_line(
            text,
            color=theme().text_secondary,
            font_name=_FONT_NAME,
            font_size=self._font_manager.about_box_fine_print_font_size,
            height=dp(_FOOTNOTE_HEIGHT),
            valign="middle",
            italic=True,
        )

    def _make_line(
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
        label.bind(
            size=lambda w, _s: setattr(w, "text_size", (w.width - dp(_ROW_SIDE_PADDING), w.height))
        )
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
            # perfectly usable without this one section.
            logger.exception("CorpusStats: dialogue statistics scan failed.")
            return

        if section is None:
            logger.info("CorpusStats: no speech index; omitting the dialogue statistics.")
            return

        def _apply(_dt: float) -> None:
            self._text_section = section
            self._append_text_section(section)

        Clock.schedule_once(_apply, 0)

    def _append_text_section(self, section: StatSection) -> None:
        """Add the late section without moving the page under the reader.

        The section always lands last, so it can be appended rather than
        rebuilt. Appending still grows the content, and ``scroll_y`` is a
        *fraction* of the scrollable distance, so the same fraction points
        somewhere else once the content is taller - hence the offset dance.
        """
        if self._stats is None:
            # The page was never built, so there is nothing to append to; the
            # cached section will be picked up by the next `_rebuild`.
            return

        scroll = self.ids.corpus_stats_scroll
        rows = self.ids.corpus_stats_rows
        offset = _scroll_offset_from_top(scroll, rows)

        self._add_section(section)

        # Restore after Kivy has relaid the grid out and `minimum_height` is current.
        Clock.schedule_once(lambda _dt: _set_scroll_offset_from_top(scroll, rows, offset), 0)

    # --- Keyboard navigation ---------------------------------------------

    def enter_nav_focus(self, on_exit_request: Callable) -> None:
        """Enter keyboard navigation mode. The page scrolls; it has no controls."""
        self._nav_on_exit_request = on_exit_request
        self._nav_active = True
        logger.debug("CorpusStatsScreen: entered nav focus.")

    def exit_nav_focus(self) -> None:
        """Leave keyboard navigation mode."""
        self._nav_active = False
        logger.debug("CorpusStatsScreen: exited nav focus.")

    def handle_key(self, key: int) -> bool:
        """Handle a keyboard key. Return True if consumed."""
        if not self._nav_active:
            return False

        if key == KEY_UP:
            self._scroll_by(_SCROLL_STEP)
        elif key == KEY_DOWN:
            self._scroll_by(-_SCROLL_STEP)
        elif key == KEY_PAGE_UP:
            self._scroll_by(_PAGE_SCROLL_STEP)
        elif key == KEY_PAGE_DOWN:
            self._scroll_by(-_PAGE_SCROLL_STEP)
        elif is_escape_key(key) or key == KEY_LEFT:
            if self._nav_on_exit_request:
                self._nav_on_exit_request()
        else:
            return False
        return True

    def _scroll_by(self, fraction: float) -> None:
        scroll = self.ids.corpus_stats_scroll
        scroll.scroll_y = min(1.0, max(0.0, scroll.scroll_y + fraction))


def _scroll_offset_from_top(scroll: ScrollView, content: Widget) -> float:
    """Return how far the view is scrolled from the top, in pixels."""
    return (1.0 - scroll.scroll_y) * _scrollable_distance(scroll, content)


def _set_scroll_offset_from_top(scroll: ScrollView, content: Widget, offset: float) -> None:
    """Scroll the view to ``offset`` pixels from the top, clamped to the content."""
    distance = _scrollable_distance(scroll, content)
    if distance <= 0:
        scroll.scroll_y = 1.0
        return
    scroll.scroll_y = min(1.0, max(0.0, 1.0 - (offset / distance)))


def _scrollable_distance(scroll: ScrollView, content: Widget) -> float:
    """Return the pixels of content that lie outside the viewport."""
    return max(0.0, content.height - scroll.height)


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
