"""The Reading History screen: a browsable journal of every comic read.

Two toggleable views over the same event log: "Journal" (sessions grouped by
day, newest first) and "Titles" (one row per title with a read count). Rows
navigate to the title's tree view; each row also has a delete button, and the
top bar has a clear-all button (with confirmation popup).

Building rows is by far the most expensive thing this screen does (roughly
1 ms per row, against a fraction of a millisecond for all the derivation put
together), so three things keep a long log responsive: each view's widgets are
built once and cached until the store changes, the first screenful is built up
front with the rest filled in a chunk per frame, and a delete patches the live
rows instead of rebuilding them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Self

from barks_fantagraphics.barks_titles import STR_TITLE_TO_ENUM
from barks_fantagraphics.fanta_comics_info import get_fanta_info
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    ObjectProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.togglebutton import ToggleButton
from loguru import logger

from barks_reader.core.reader_palette import theme
from barks_reader.core.reading_history import (
    ReadEvent,
    TitleSummary,
    format_event_duration,
    format_event_page,
    format_event_time,
    format_unfinished_page,
    group_events_by_day,
    summarize_titles,
)

from .panel_texture_loader import PanelTextureLoader
from .popup_widgets import open_confirm_popup
from .reader_keyboard_nav import (
    KEY_DELETE,
    KEY_DOWN,
    KEY_ENTER,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_PAGE_DOWN,
    KEY_PAGE_UP,
    KEY_RIGHT,
    KEY_UP,
    MENU_FOCUS_HIGHLIGHT_GROUP,
    clear_focus_highlight,
    clear_focus_in_list,
    draw_focus_highlight,
    is_escape_key,
    update_focus_in_list,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_titles import Titles
    from kivy.clock import ClockEvent
    from kivy.core.image import Texture
    from kivy.uix.widget import Widget

    from barks_reader.core.image_selector import ImageInfo
    from barks_reader.core.reading_history import ReadingHistoryStore

HISTORY_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

_ROW_HEIGHT = 38  # dp
_HEADER_HEIGHT = 42  # dp
_DELETE_BUTTON_WIDTH = 40  # dp
_TIME_COL_WIDTH = 60  # dp
_DURATION_COL_WIDTH = 110  # dp
_LAST_READ_COL_WIDTH = 190  # dp
_PAGE_COL_WIDTH = 80  # dp
_COUNT_COL_WIDTH = 56  # dp
_ROW_FONT_SIZE = 14  # dp
_TITLE_FONT_SIZE = 16  # dp
_HEADER_FONT_SIZE = 13  # dp — a small "eyebrow" divider under the row titles (16dp)
_HEADER_HAIRLINE_ALPHA = 0.45  # Faintness of the rule beneath each day-group header.
_CELL_PADDING = 10  # dp — gap between a cell's text box and its right edge.

_TEXT_COLOR = (1, 1, 1, 1)
_DELETE_COLOR = (0.8, 0.35, 0.35, 1)

_JOURNAL_VIEW = "journal"
_TITLES_VIEW = "titles"

_NO_EVENTS_TEXT = "No comics read yet."

# Rows built before the first frame is drawn: enough to fill a 4K viewport, so
# the page never appears part-empty. The rest arrive a chunk per frame, keeping
# the app responsive to keys and scrolling while a long log fills in. A row
# costs roughly 2 ms, so a chunk of 12 is about 25 ms of work per frame - short
# enough to stay interactive, long enough to finish a 300-entry log in ~0.5 s.
_FIRST_CHUNK_ITEMS = 50
_CHUNK_ITEMS = 12

_NAV_PAGE_STEP = 10  # Rows jumped by Page Up/Down in keyboard navigation.

# Keyboard focus is split into two zones: the scrolling row list and the top
# bar (the Journal/Titles tabs plus Clear History). Up from the first row moves
# into the bar; Down from the bar returns to the list.
_ZONE_LIST = "list"
_ZONE_BAR = "bar"
_BAR_JOURNAL, _BAR_TITLES, _BAR_CLEAR = 0, 1, 2
_BAR_FOCUS_GROUP = "history_bar_focus"

_NAV_MOVE_DELTAS = {
    KEY_UP: -1,
    KEY_DOWN: 1,
    KEY_PAGE_UP: -_NAV_PAGE_STEP,
    KEY_PAGE_DOWN: _NAV_PAGE_STEP,
}


class _HistoryRow(ButtonBehavior, BoxLayout):
    """One history row: a whole-row button whose cells are plain labels.

    Making the row itself the touch target means one clickable widget per row
    instead of one per cell, and the alternating stripe is a single rectangle
    on the row rather than a background on every cell — so re-striping after a
    delete touches one canvas instruction instead of five widgets.
    """

    def __init__(self) -> None:
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(_ROW_HEIGHT))
        # pyrefly: ignore[missing-attribute]  # Kivy sets `canvas` in Widget.__init__.
        with self.canvas.before:  # ty: ignore[unresolved-attribute]
            self._stripe_color = Color(*theme().row_stripe_even)
            self._stripe_rect = Rectangle()
        self.bind(pos=self._update_stripe, size=self._update_stripe)

    def _update_stripe(self, *_args: object) -> None:
        self._stripe_rect.pos = self.pos
        self._stripe_rect.size = self.size

    def set_stripe(self, row_index: int) -> None:
        """Apply the alternating row color for this position within its group."""
        palette = theme()
        self._stripe_color.rgba = (
            palette.row_stripe_even if row_index % 2 == 0 else palette.row_stripe_odd
        )


@dataclass(frozen=True)
class _NavRow:
    """A keyboard-navigable history row: its widget and its two actions."""

    widget: BoxLayout
    activate: Callable[[], None]
    delete: Callable[[], None]
    group: str = ""  # The day heading in the journal view; "" in the titles view.
    key: str = ""  # Event id (journal) or title (titles) — what a delete removes.


@dataclass
class _BuiltView:
    """One view's built widgets, reusable until the store's revision moves on."""

    view: str
    revision: object
    widgets: list[Widget] = field(default_factory=list)
    nav_rows: list[_NavRow] = field(default_factory=list)
    headers: dict[str, Label] = field(default_factory=dict)


def _get_display_title(title_str: str) -> str:
    """Return the title decorated per the parentheses convention, or as-is."""
    title = STR_TITLE_TO_ENUM.get(title_str)
    fanta_info = None if title is None else get_fanta_info(title)
    if fanta_info is None:
        return title_str
    return fanta_info.comic_book_info.get_display_title()


def _fit_text_to_cell(cell: Label, _size: tuple[float, float]) -> None:
    """Keep a flexible cell's text box in step with its width."""
    cell.text_size = (cell.width - dp(_CELL_PADDING), cell.height)


def _add_header_hairline(label: Label) -> None:
    """Draw a faint full-width rule beneath a day-group header, as a divider.

    The rule tracks the label's geometry (it is re-laid-out after the header is
    added to the grid) and sits just below the centred heading text.
    """
    rgb = tuple(theme().search_heading[:3])
    with label.canvas.after:  # ty: ignore[unresolved-attribute]
        color = Color(*rgb, _HEADER_HAIRLINE_ALPHA)
        rule = Rectangle()

    def _update(*_args: object) -> None:
        color.rgba = (*rgb, _HEADER_HAIRLINE_ALPHA)
        rule.pos = (label.x, label.y + dp(8))
        rule.size = (label.width, dp(1))

    label.bind(pos=_update, size=_update)
    _update()


class HistoryViewButton(ToggleButton):
    """A tab button for the history top bar (Journal/Titles)."""

    def _do_press(self) -> None:
        """Prevent deselecting the active tab by suppressing press when already down."""
        if self.state == "normal":
            super()._do_press()


class HistoryScreen(FloatLayout):
    """Screen that shows the reading-history event log.

    The store is injected after construction via `set_history_store`. The
    screen re-reads the store every time it becomes visible or is modified, so
    it never holds stale rows — but it reuses the widgets it already built when
    the store has not changed since.
    """

    is_visible = BooleanProperty(defaultvalue=False)
    image_texture = ObjectProperty(allownone=True)

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self._history_store: ReadingHistoryStore | None = None
        self._current_view = _JOURNAL_VIEW
        self._texture_loader = PanelTextureLoader()
        self.on_goto_title: Callable[[Titles], None] | None = None
        self.get_background_image: Callable[[list[Titles]], ImageInfo] | None = None

        # Built-view cache and the state of an in-progress chunked build.
        self._view_cache: dict[str, _BuiltView] = {}
        self._building: _BuiltView | None = None
        self._build_event: ClockEvent | None = None
        self._pending_items: list[Callable[[], Widget]] = []

        # Keyboard navigation state
        self._nav_active: bool = False
        self._nav_on_exit_request: Callable[[], None] | None = None
        self._nav_zone: str = _ZONE_LIST
        self._nav_focused_idx: int = 0
        self._nav_rows: list[_NavRow] = []
        self._nav_focused_widget: BoxLayout | None = None
        self._bar_focused_idx: int = _BAR_JOURNAL

    def set_history_store(self, history_store: ReadingHistoryStore) -> None:
        """Inject the persistent event log to display."""
        self._history_store = history_store

    def on_is_visible(self, _instance: Self, value: bool) -> None:
        """Refresh the rows and background whenever the screen becomes visible."""
        if value:
            self._select_view(self._current_view)
            self.update_background_image()

    def update_background_image(self) -> None:
        """Show a random panel from the comics in the history as the backdrop.

        Also called by the action bar's change-view-images button so the
        history backdrop refreshes along with the other themed images.
        """
        if self.get_background_image is None or self._history_store is None:
            return

        titles = list(
            {
                title
                for event in self._history_store.get_events()
                if (title := STR_TITLE_TO_ENUM.get(event.title_str)) is not None
            }
        )
        image_info = self.get_background_image(titles)
        if not image_info.filename:
            return

        def on_texture_loaded(texture: Texture | None, error: Exception | None) -> None:
            if error is not None:
                logger.warning(f"History: Could not load background image: {error}.")
                return
            self.image_texture = texture

        self._texture_loader.cancel()
        self._texture_loader.load_texture(image_info.filename, on_texture_loaded)

    def on_journal_pressed(self) -> None:
        """Switch to the day-grouped journal view (kv callback)."""
        self._select_view(_JOURNAL_VIEW)

    def on_titles_pressed(self) -> None:
        """Switch to the per-title summary view (kv callback)."""
        self._select_view(_TITLES_VIEW)

    def _select_view(self, view: str) -> None:
        self._current_view = view
        self.ids.journal_button.state = "down" if view == _JOURNAL_VIEW else "normal"
        self.ids.titles_button.state = "down" if view == _TITLES_VIEW else "normal"
        self._refresh()

    # --- Building and caching the rows ---

    def _refresh(self) -> None:
        """Show the current view, reusing its widgets when the store is unchanged."""
        if self._history_store is None:
            return

        self._cancel_pending_build()

        revision = self._history_store.revision
        built = self._view_cache.get(self._current_view)
        if built is not None and built.revision == revision:
            self._mount(built)
        else:
            self._start_build(revision)

    def _mount(self, built: _BuiltView) -> None:
        """Re-attach an already-built view's widgets to the scrolling grid."""
        rows = self.ids.history_rows
        rows.clear_widgets()
        self._nav_rows = built.nav_rows
        self._nav_focused_widget = None
        for widget in built.widgets:
            rows.add_widget(widget)
        self._restore_nav_focus()

    def _start_build(self, revision: object) -> None:
        """Build the current view: the first screenful now, the rest per frame."""
        assert self._history_store is not None

        self.ids.history_rows.clear_widgets()
        self._nav_rows = []
        self._nav_focused_widget = None

        built = _BuiltView(view=self._current_view, revision=revision, nav_rows=self._nav_rows)
        self._view_cache[self._current_view] = built
        self._building = built

        events = self._history_store.get_events()
        if not events:
            self._pending_items = [partial(self._make_header_label, _NO_EVENTS_TEXT)]
        elif self._current_view == _JOURNAL_VIEW:
            self._pending_items = self._journal_items(events)
        else:
            self._pending_items = self._titles_items(events)

        self._add_items(_FIRST_CHUNK_ITEMS)
        if self._building is not None:
            # Still filling in: show the focus ring on the rows that exist now.
            self._restore_nav_focus()

    def _add_items(self, count: int) -> None:
        """Build and attach the next ``count`` items, then schedule or finish."""
        assert self._building is not None

        rows = self.ids.history_rows
        chunk = self._pending_items[:count]
        self._pending_items = self._pending_items[count:]
        for make_widget in chunk:
            widget = make_widget()
            self._building.widgets.append(widget)
            rows.add_widget(widget)

        if self._pending_items:
            self._build_event = Clock.schedule_once(self._build_next_chunk, 0)
        else:
            self._finish_build()

    def _build_next_chunk(self, _dt: float) -> None:
        self._build_event = None
        self._add_items(_CHUNK_ITEMS)

    def _finish_build(self) -> None:
        self._build_event = None
        self._building = None
        self._restore_nav_focus()

    def _cancel_pending_build(self) -> None:
        """Abandon a part-finished build so it is never cached as complete."""
        if self._build_event is not None:
            self._build_event.cancel()
            self._build_event = None
        if self._building is not None:
            self._view_cache.pop(self._building.view, None)
            self._building = None
        self._pending_items = []

    def _journal_items(self, events: list[ReadEvent]) -> list[Callable[[], Widget]]:
        items: list[Callable[[], Widget]] = []
        for day_group in group_events_by_day(events, datetime.now().date()):  # noqa: DTZ005
            heading = day_group.heading
            items.append(partial(self._make_group_header, heading))
            items.extend(
                partial(self._make_journal_row, event, row_index, heading)
                for row_index, event in enumerate(day_group.events)
            )
        return items

    def _titles_items(self, events: list[ReadEvent]) -> list[Callable[[], Widget]]:
        return [
            partial(self._make_titles_row, summary, row_index)
            for row_index, summary in enumerate(summarize_titles(events))
        ]

    def _make_group_header(self, heading: str) -> Label:
        """Build a day heading and register it, so an emptied day loses its header."""
        label = self._make_header_label(heading)
        assert self._building is not None
        self._building.headers[heading] = label
        return label

    @staticmethod
    def _make_header_label(text: str) -> Label:
        label = Label(
            text=f"[b]{text}[/b]",
            markup=True,
            color=theme().search_heading,
            font_size=dp(_HEADER_FONT_SIZE),
            halign="center",
            valign="middle",
            size_hint_y=None,
            height=dp(_HEADER_HEIGHT),
            text_size=(None, None),
            pos_hint={"x": 0},
        )
        _add_header_hairline(label)
        return label

    def _make_journal_row(self, event: ReadEvent, row_index: int, heading: str) -> _HistoryRow:
        return self._make_row(
            cells=(
                (f"[color=bbbbbb]{format_event_time(event)}[/color]", _TIME_COL_WIDTH),
                (f"[b]{_get_display_title(event.title_str)}[/b]", None),
                (f"[color=aaaaaa]{format_event_duration(event)}[/color]", _DURATION_COL_WIDTH),
                (f"[color=aaaaaa]{format_event_page(event)}[/color]", _PAGE_COL_WIDTH),
            ),
            row_index=row_index,
            group=heading,
            key=event.event_id,
            on_press=lambda: self._on_row_pressed(event.title_str),
            on_delete=lambda: self._on_delete_event(event.event_id),
        )

    def _make_titles_row(self, summary: TitleSummary, row_index: int) -> _HistoryRow:
        return self._make_row(
            cells=(
                (f"[b]{_get_display_title(summary.title_str)}[/b]", None),
                (
                    f"[color=aaaaaa]{summary.last_opened_at:%d %b %Y %H:%M}[/color]",
                    _LAST_READ_COL_WIDTH,
                ),
                (f"[color=aaaaaa]{format_unfinished_page(summary)}[/color]", _PAGE_COL_WIDTH),
                (f"[color=aaaaaa]x{summary.read_count}[/color]", _COUNT_COL_WIDTH),
            ),
            row_index=row_index,
            group="",
            key=summary.title_str,
            on_press=lambda: self._on_row_pressed(summary.title_str),
            on_delete=lambda: self._on_delete_title(summary.title_str),
        )

    def _make_row(
        self,
        cells: tuple[tuple[str, int | None], ...],
        row_index: int,
        group: str,
        key: str,
        on_press: Callable[[], None],
        on_delete: Callable[[], None],
    ) -> _HistoryRow:
        """Build one clickable row from ``(markup_text, column_dp_width)`` cells.

        A ``None`` width marks the flexible (title) column, and it is the only
        cell whose ``text_size`` has to track its width — the fixed columns get
        theirs once, up front. The row itself is the button, so the whole row is
        clickable; the delete button sits inside it and consumes its own touch,
        which stops the row's press from firing too.
        """
        row = _HistoryRow()
        row.set_stripe(row_index)
        title_color = theme().text_title

        for markup_text, col_width in cells:
            cell = Label(
                text=markup_text,
                markup=True,
                halign="left",
                valign="middle",
                # The flexible column is the title - give it slightly larger,
                # tree-view-yellow type.
                font_size=dp(_TITLE_FONT_SIZE if col_width is None else _ROW_FONT_SIZE),
                color=title_color if col_width is None else _TEXT_COLOR,
            )
            if col_width is None:
                cell.bind(size=_fit_text_to_cell)
            else:
                cell.size_hint_x = None
                cell.width = dp(col_width)
                cell.text_size = (dp(col_width) - dp(_CELL_PADDING), dp(_ROW_HEIGHT))
            row.add_widget(cell)

        delete_button = Button(
            text="X",
            size_hint_x=None,
            width=dp(_DELETE_BUTTON_WIDTH),
            font_size=dp(_ROW_FONT_SIZE),
            background_normal="",
            background_down="",
            background_color=(0, 0, 0, 0),  # Transparent: the row's stripe shows through.
            color=_DELETE_COLOR,
        )
        delete_button.bind(on_press=lambda _b: on_delete())
        row.add_widget(delete_button)
        row.bind(on_press=lambda _r: on_press())

        self._nav_rows.append(
            _NavRow(widget=row, activate=on_press, delete=on_delete, group=group, key=key)
        )
        return row

    def _on_row_pressed(self, title_str: str) -> None:
        title = STR_TITLE_TO_ENUM.get(title_str)
        if title is None:
            logger.warning(f'History: No title enum for "{title_str}".')
            return
        if self.on_goto_title is not None:
            self.on_goto_title(title)

    def _on_delete_event(self, event_id: str) -> None:
        assert self._history_store is not None
        self._history_store.delete_event(event_id)
        self._drop_rows({event_id})

    def _on_delete_title(self, title_str: str) -> None:
        assert self._history_store is not None
        self._history_store.delete_events_for_title(title_str)
        self._drop_rows({title_str})

    def _drop_rows(self, keys: set[str]) -> None:
        """Remove just the deleted rows from the live view, instead of rebuilding it.

        Rebuilding costs about a millisecond per row, so deleting one entry used
        to redraw the entire log. The other view's cached widgets no longer match
        the store, so they are dropped and rebuilt on demand.
        """
        assert self._history_store is not None

        built = self._view_cache.get(self._current_view)
        if built is None or self._building is not None:
            # Never built, or still filling in: a plain refresh is the safe path.
            self._refresh()
            return

        rows = self.ids.history_rows
        for nav_row in [r for r in built.nav_rows if r.key in keys]:
            rows.remove_widget(nav_row.widget)
            built.widgets.remove(nav_row.widget)
        # Slice-assigned: built.nav_rows is the same list object as self._nav_rows.
        built.nav_rows[:] = [r for r in built.nav_rows if r.key not in keys]

        live_groups = {r.group for r in built.nav_rows}
        for heading in [h for h in built.headers if h not in live_groups]:
            header = built.headers.pop(heading)
            rows.remove_widget(header)
            built.widgets.remove(header)

        self._restripe(built.nav_rows)

        if not built.nav_rows:
            empty = self._make_header_label(_NO_EVENTS_TEXT)
            built.widgets.append(empty)
            rows.add_widget(empty)

        built.revision = self._history_store.revision
        other_view = _TITLES_VIEW if self._current_view == _JOURNAL_VIEW else _JOURNAL_VIEW
        self._view_cache.pop(other_view, None)

        self._restore_nav_focus()

    @staticmethod
    def _restripe(nav_rows: list[_NavRow]) -> None:
        """Re-apply the alternating row colors after rows were removed.

        The stripe index restarts at each group boundary, matching the journal's
        per-day numbering; the titles view is one unnamed group, so it runs on.
        """
        group: str | None = None
        row_index = 0
        for nav_row in nav_rows:
            if nav_row.group != group:
                group, row_index = nav_row.group, 0
            nav_row.widget.set_stripe(row_index)
            row_index += 1

    # --- Keyboard navigation ---

    def enter_nav_focus(self, on_exit_request: Callable[[], None]) -> None:
        """Enter keyboard navigation mode, focusing the first history row."""
        self._nav_on_exit_request = on_exit_request
        self._nav_active = True
        self._nav_zone = _ZONE_LIST
        self._nav_focused_idx = 0
        self._update_nav_focus()
        logger.debug("HistoryScreen: entered nav focus.")

    def exit_nav_focus(self) -> None:
        """Exit keyboard navigation mode and clear every highlight."""
        if not self._nav_active:
            return
        self._nav_active = False
        self._nav_on_exit_request = None
        self._nav_zone = _ZONE_LIST
        self._clear_nav_focus()
        self._clear_bar_focus()
        logger.debug("HistoryScreen: exited nav focus.")

    def _restore_nav_focus(self) -> None:
        """Redraw the focus ring after the rows underneath it changed."""
        if not self._nav_active:
            return
        if self._nav_zone == _ZONE_BAR:
            self._update_bar_focus()
        else:
            self._nav_focused_idx = min(self._nav_focused_idx, max(0, len(self._nav_rows) - 1))
            self._update_nav_focus()

    def handle_key(self, key: int) -> bool:
        """Handle a keyboard key. Return True if consumed."""
        if not self._nav_active:
            return False
        if self._nav_zone == _ZONE_BAR:
            return self._handle_bar_key(key)
        return self._handle_list_key(key)

    def _handle_list_key(self, key: int) -> bool:
        # Up from the first row leaves the list and enters the top bar.
        if key == KEY_UP and self._nav_focused_idx == 0:
            self._enter_bar_zone()
        elif key in _NAV_MOVE_DELTAS:
            self._move_nav_focus(_NAV_MOVE_DELTAS[key])
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._activate_focused_row()
        elif key == KEY_DELETE:
            self._delete_focused_row()
        elif is_escape_key(key):
            self._request_nav_exit()
        else:
            return False
        return True

    def _handle_bar_key(self, key: int) -> bool:
        if key == KEY_LEFT:
            self._move_bar_focus(-1)
        elif key == KEY_RIGHT:
            self._move_bar_focus(1)
        elif key == KEY_DOWN:
            self._enter_list_zone()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._activate_bar_focus()
        elif is_escape_key(key):
            self._request_nav_exit()
        else:
            return False
        return True

    def _request_nav_exit(self) -> None:
        if self._nav_on_exit_request is not None:
            self._nav_on_exit_request()

    # --- Top-bar zone (Journal | Titles | Clear History) ---

    def _bar_buttons(self) -> list[Button]:
        return [self.ids.journal_button, self.ids.titles_button, self.ids.clear_button]

    def _enter_bar_zone(self) -> None:
        self._clear_nav_focus()
        self._nav_zone = _ZONE_BAR
        # Land on the tab matching the current view (Clear is one step to the right).
        self._bar_focused_idx = _BAR_JOURNAL if self._current_view == _JOURNAL_VIEW else _BAR_TITLES
        self._update_bar_focus()

    def _enter_list_zone(self) -> None:
        self._clear_bar_focus()
        self._nav_zone = _ZONE_LIST
        self._nav_focused_idx = 0
        self._update_nav_focus()

    def _move_bar_focus(self, delta: int) -> None:
        new_idx = max(_BAR_JOURNAL, min(_BAR_CLEAR, self._bar_focused_idx + delta))
        if new_idx != self._bar_focused_idx:
            self._bar_focused_idx = new_idx
            self._update_bar_focus()

    def _activate_bar_focus(self) -> None:
        if self._bar_focused_idx == _BAR_CLEAR:
            self.on_clear_pressed()
            return
        view = _JOURNAL_VIEW if self._bar_focused_idx == _BAR_JOURNAL else _TITLES_VIEW
        if view != self._current_view:
            # _select_view refreshes the rows, which redraws the bar highlight.
            self._select_view(view)

    def _update_bar_focus(self) -> None:
        update_focus_in_list(self._bar_buttons(), self._bar_focused_idx, _BAR_FOCUS_GROUP)

    def _clear_bar_focus(self) -> None:
        clear_focus_in_list(self._bar_buttons(), _BAR_FOCUS_GROUP)

    def _move_nav_focus(self, delta: int) -> None:
        if not self._nav_rows:
            return
        new_idx = max(0, min(len(self._nav_rows) - 1, self._nav_focused_idx + delta))
        if new_idx != self._nav_focused_idx:
            self._nav_focused_idx = new_idx
            self._update_nav_focus()

    def _activate_focused_row(self) -> None:
        if self._nav_rows:
            self._nav_rows[self._nav_focused_idx].activate()

    def _delete_focused_row(self) -> None:
        # The delete action drops the row, which re-clamps the focus index.
        if self._nav_rows:
            self._nav_rows[self._nav_focused_idx].delete()

    def _update_nav_focus(self) -> None:
        self._clear_nav_focus()
        if not self._nav_rows:
            return
        widget = self._nav_rows[self._nav_focused_idx].widget
        draw_focus_highlight(widget, MENU_FOCUS_HIGHLIGHT_GROUP)
        self._nav_focused_widget = widget
        # Rows may not be laid out yet (fresh refresh), so scroll after the next frame.
        Clock.schedule_once(lambda _dt: self._scroll_to_focused_row(widget), 0)

    def _scroll_to_focused_row(self, widget: BoxLayout) -> None:
        """Scroll so the focused row is visible, pinning the list top when it all fits.

        ``scroll_to`` must only run when the rows overflow the viewport: with
        undersized content its scroll math runs on a negative scrollable range
        and shoves the whole list to the bottom of the panel.
        """
        scroll = self.ids.history_scroll
        if self.ids.history_rows.height > scroll.height:
            scroll.scroll_to(widget, padding=dp(30))
        else:
            scroll.scroll_y = 1.0

    def _clear_nav_focus(self) -> None:
        if self._nav_focused_widget is not None:
            clear_focus_highlight(self._nav_focused_widget, MENU_FOCUS_HIGHLIGHT_GROUP)
            self._nav_focused_widget = None

    def on_clear_pressed(self) -> None:
        """Ask for confirmation, then clear the whole history (kv callback).

        Uses the shared keyboard-operable confirm popup so the dialog works with
        a 6-button remote (Left/Right pick a button, Enter confirms, Escape stays).
        """

        def do_clear() -> None:
            assert self._history_store is not None
            self._history_store.clear()
            self._refresh()

        open_confirm_popup(
            title="Clear Reading History",
            text="Clear all reading history?",
            ok_text="Clear",
            cancel_text="Cancel",
            on_ok=do_clear,
        )
