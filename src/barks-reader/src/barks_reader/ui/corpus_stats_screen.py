"""The Introduction "By the Numbers" screen: the whole corpus as a fact sheet.

A hero band of three headline figures over grouped, striped label/value rows.
All of the arithmetic lives in ``barks_reader.core.corpus_stats``; this module
only turns its ``CorpusStats`` into widgets.

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

    from barks_reader.core.corpus_stats import CorpusStats, StatSection

CORPUS_STATS_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

# The same face the index screens use: a plain, tabular-friendly sans.
_FONT_NAME = FontManager.main_index_item_font_name

_HERO_HEIGHT = 92
_HERO_CAPTION_HEIGHT = 26
_HEADING_HEIGHT = 34
_ROW_HEIGHT = 26
_FOOTNOTE_HEIGHT = 24
_SECTION_GAP = 10

_HAIRLINE_ALPHA = 0.35
_ROW_SIDE_PADDING = 14

# One arrow press moves the view by this fraction of the scrollable height; a
# page key moves by this much again. Tuned so a remote's cursor keys walk the
# page at a readable pace rather than jumping it.
_SCROLL_STEP = 0.08
_PAGE_SCROLL_STEP = 0.4


class CorpusStatsScreen(FloatLayout):
    """Screen showing corpus-wide statistics as a hero band plus grouped rows.

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

        self._add_hero_band(self._stats.hero)
        sections = list(self._stats.sections)
        if self._text_section is not None:
            sections.append(self._text_section)
        for section in sections:
            self._add_section(section)

    def _add_hero_band(self, hero_stats: tuple) -> None:
        band = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(_HERO_HEIGHT), spacing=dp(4)
        )
        for stat in hero_stats:
            cell = BoxLayout(orientation="vertical")
            cell.add_widget(
                Label(
                    text=f"[b]{stat.value}[/b]",
                    markup=True,
                    color=theme().text_display,
                    font_name=_FONT_NAME,
                    font_size=self._font_manager.main_title_font_size,
                    halign="center",
                    valign="bottom",
                )
            )
            cell.add_widget(
                Label(
                    text=stat.caption,
                    color=theme().text_secondary,
                    font_name=_FONT_NAME,
                    font_size=self._font_manager.search_label_font_size,
                    halign="center",
                    valign="top",
                    size_hint_y=None,
                    height=dp(_HERO_CAPTION_HEIGHT),
                )
            )
            band.add_widget(cell)

        self.ids.corpus_stats_rows.add_widget(band)

    def _add_section(self, section: StatSection) -> None:
        rows = self.ids.corpus_stats_rows
        rows.add_widget(self._make_heading(section.heading))
        for row_index, stat_row in enumerate(section.rows):
            rows.add_widget(self._make_row(stat_row.label, stat_row.value, row_index))
        if section.footnote:
            rows.add_widget(self._make_footnote(section.footnote))
        rows.add_widget(BoxLayout(size_hint_y=None, height=dp(_SECTION_GAP)))

    def _make_heading(self, text: str) -> Label:
        label = Label(
            text=f"[b]{text.upper()}[/b]",
            markup=True,
            color=theme().search_heading,
            font_name=_FONT_NAME,
            font_size=self._font_manager.text_block_heading_font_size,
            halign="left",
            valign="bottom",
            size_hint_y=None,
            height=dp(_HEADING_HEIGHT),
        )
        label.bind(size=lambda w, _s: setattr(w, "text_size", (w.width - dp(4), w.height)))
        _add_heading_hairline(label)
        return label

    def _make_row(self, label_text: str, value_text: str, row_index: int) -> BoxLayout:
        """Build one striped label/value line."""
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(_ROW_HEIGHT))
        stripe = list(theme().row_stripe_even if row_index % 2 == 0 else theme().row_stripe_odd)
        _fill_background(row, stripe)

        row.add_widget(self._make_cell(label_text, theme().text_secondary, "left", bold=False))
        row.add_widget(self._make_cell(value_text, theme().text_title, "right", bold=True))
        return row

    def _make_cell(self, text: str, color: tuple, halign: str, *, bold: bool) -> Label:
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
        label.bind(
            size=lambda w, _s: setattr(w, "text_size", (w.width - dp(_ROW_SIDE_PADDING), w.height))
        )
        return label

    def _make_footnote(self, text: str) -> Label:
        label = Label(
            text=f"[i]{text}[/i]",
            markup=True,
            color=theme().text_secondary,
            font_name=_FONT_NAME,
            font_size=self._font_manager.main_title_footnote_font_size,
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(_FOOTNOTE_HEIGHT),
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
            self._rebuild()

        Clock.schedule_once(_apply, 0)

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


def _fill_background(widget: BoxLayout, rgba: list[float]) -> None:
    """Paint a flat background behind a row that tracks its geometry."""
    canvas = widget.canvas
    assert canvas is not None  # Kivy populates this on widget construction.
    with canvas.before:
        color = Color(*rgba)
        rect = Rectangle(pos=widget.pos, size=widget.size)

    def _update(*_args: object) -> None:
        color.rgba = rgba
        rect.pos = widget.pos
        rect.size = widget.size

    widget.bind(pos=_update, size=_update)


def _add_heading_hairline(label: Label) -> None:
    """Draw a faint rule beneath a section heading, as a divider."""
    rgb = tuple(theme().search_heading[:3])
    canvas = label.canvas
    assert canvas is not None  # Kivy populates this on widget construction.
    with canvas.after:
        color = Color(*rgb, _HAIRLINE_ALPHA)
        rule = Rectangle()

    def _update(*_args: object) -> None:
        color.rgba = (*rgb, _HAIRLINE_ALPHA)
        rule.pos = (label.x, label.y + dp(4))
        rule.size = (label.width, dp(1))

    label.bind(pos=_update, size=_update)
