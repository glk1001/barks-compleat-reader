"""The Reading History screen: a browsable journal of every comic read.

Two toggleable views over the same event log: "Journal" (sessions grouped by
day, newest first) and "Titles" (one row per title with a read count). Rows
navigate to the title's tree view; each row also has a delete button, and the
top bar has a clear-all button (with confirmation popup).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Self

from barks_fantagraphics.barks_titles import STR_TITLE_TO_ENUM
from barks_fantagraphics.fanta_comics_info import get_fanta_info
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    ObjectProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.togglebutton import ToggleButton
from loguru import logger

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
from .popup_widgets import MessagePopup
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
    draw_focus_highlight,
    is_escape_key,
)
from .tree_view_nodes import TitleTreeViewNode

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_titles import Titles
    from kivy.core.image import Texture

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
_HEADER_FONT_SIZE = 16  # dp

# Match the story tree-view's alternating title-row and title-text colors.
_EVEN_ROW_COLOR = TitleTreeViewNode.EVEN_COLOR
_ODD_ROW_COLOR = TitleTreeViewNode.ODD_COLOR
_TITLE_COLOR = TitleTreeViewNode.TITLE_LABEL_COLOR
_TEXT_COLOR = (1, 1, 1, 1)

_JOURNAL_VIEW = "journal"
_TITLES_VIEW = "titles"

_NAV_PAGE_STEP = 10  # Rows jumped by Page Up/Down in keyboard navigation.

_NAV_MOVE_DELTAS = {
    KEY_UP: -1,
    KEY_DOWN: 1,
    KEY_PAGE_UP: -_NAV_PAGE_STEP,
    KEY_PAGE_DOWN: _NAV_PAGE_STEP,
}


@dataclass(frozen=True)
class _NavRow:
    """A keyboard-navigable history row: its widget and its two actions."""

    widget: BoxLayout
    activate: Callable[[], None]
    delete: Callable[[], None]


def _get_display_title(title_str: str) -> str:
    """Return the title decorated per the parentheses convention, or as-is."""
    title = STR_TITLE_TO_ENUM.get(title_str)
    fanta_info = None if title is None else get_fanta_info(title)
    if fanta_info is None:
        return title_str
    return fanta_info.comic_book_info.get_display_title()


class HistoryViewButton(ToggleButton):
    """A tab button for the history top bar (Journal/Titles)."""

    def _do_press(self) -> None:
        """Prevent deselecting the active tab by suppressing press when already down."""
        if self.state == "normal":
            super()._do_press()


class HistoryScreen(FloatLayout):
    """Screen that shows the reading-history event log.

    The store is injected after construction via `set_history_store`. The
    screen re-reads the store every time it becomes visible or is modified,
    so it never holds stale rows.
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

        # Keyboard navigation state
        self._nav_active: bool = False
        self._nav_on_exit_request: Callable[[], None] | None = None
        self._nav_focused_idx: int = 0
        self._nav_rows: list[_NavRow] = []
        self._nav_focused_widget: BoxLayout | None = None

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

    def _refresh(self) -> None:
        if self._history_store is None:
            return

        rows = self.ids.history_rows
        rows.clear_widgets()
        self._nav_rows.clear()
        self._nav_focused_widget = None

        events = self._history_store.get_events()
        if not events:
            rows.add_widget(self._make_header_label("No comics read yet."))
        elif self._current_view == _JOURNAL_VIEW:
            self._populate_journal(events)
        else:
            self._populate_titles(events)

        if self._nav_active:
            self._nav_focused_idx = min(self._nav_focused_idx, max(0, len(self._nav_rows) - 1))
            self._update_nav_focus()

    def _populate_journal(self, events: list[ReadEvent]) -> None:
        rows = self.ids.history_rows
        for day_group in group_events_by_day(events, datetime.now().date()):  # noqa: DTZ005
            rows.add_widget(self._make_header_label(day_group.heading))
            for row_index, event in enumerate(day_group.events):
                rows.add_widget(self._make_journal_row(event, row_index))

    def _populate_titles(self, events: list[ReadEvent]) -> None:
        rows = self.ids.history_rows
        for row_index, summary in enumerate(summarize_titles(events)):
            rows.add_widget(self._make_titles_row(summary, row_index))

    @staticmethod
    def _make_header_label(text: str) -> Label:
        return Label(
            text=f"[b]{text}[/b]",
            markup=True,
            color=(0.0, 1.0, 0.0, 1.0),
            font_size=dp(_HEADER_FONT_SIZE),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(_HEADER_HEIGHT),
            text_size=(None, None),
            pos_hint={"x": 0},
        )

    def _make_journal_row(self, event: ReadEvent, row_index: int) -> BoxLayout:
        return self._make_row(
            cells=(
                (f"[color=bbbbbb]{format_event_time(event)}[/color]", _TIME_COL_WIDTH),
                (f"[b]{_get_display_title(event.title_str)}[/b]", None),
                (f"[color=aaaaaa]{format_event_duration(event)}[/color]", _DURATION_COL_WIDTH),
                (f"[color=aaaaaa]{format_event_page(event)}[/color]", _PAGE_COL_WIDTH),
            ),
            row_index=row_index,
            on_press=lambda: self._on_row_pressed(event.title_str),
            on_delete=lambda: self._on_delete_event(event.event_id),
        )

    def _make_titles_row(self, summary: TitleSummary, row_index: int) -> BoxLayout:
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
            on_press=lambda: self._on_row_pressed(summary.title_str),
            on_delete=lambda: self._on_delete_title(summary.title_str),
        )

    def _make_row(
        self,
        cells: tuple[tuple[str, int | None], ...],
        row_index: int,
        on_press: Callable[[], None],
        on_delete: Callable[[], None],
    ) -> BoxLayout:
        """Build one clickable row from ``(markup_text, column_dp_width)`` cells.

        A ``None`` width marks the flexible (title) column. Every cell presses
        through to ``on_press`` so the whole row is clickable. Rows are striped
        (by ``row_index``) so they stay readable over the background image.
        """
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(_ROW_HEIGHT))
        row_color = _EVEN_ROW_COLOR if row_index % 2 == 0 else _ODD_ROW_COLOR

        for markup_text, col_width in cells:
            cell = Button(
                text=markup_text,
                markup=True,
                halign="left",
                valign="middle",
                # The flexible column is the title - give it slightly larger,
                # tree-view-yellow type.
                font_size=dp(_TITLE_FONT_SIZE if col_width is None else _ROW_FONT_SIZE),
                background_normal="",
                background_down="",
                background_color=row_color,
                color=_TITLE_COLOR if col_width is None else _TEXT_COLOR,
            )
            if col_width is not None:
                cell.size_hint_x = None
                cell.width = dp(col_width)
            cell.bind(size=lambda b, _s: setattr(b, "text_size", (b.width - dp(10), b.height)))
            cell.bind(on_press=lambda _b: on_press())
            row.add_widget(cell)

        delete_button = Button(
            text="X",
            size_hint_x=None,
            width=dp(_DELETE_BUTTON_WIDTH),
            font_size=dp(_ROW_FONT_SIZE),
            background_normal="",
            background_down="",
            background_color=row_color,
            color=(0.8, 0.35, 0.35, 1),
        )
        delete_button.bind(on_press=lambda _b: on_delete())
        row.add_widget(delete_button)

        self._nav_rows.append(_NavRow(widget=row, activate=on_press, delete=on_delete))
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
        self._refresh()

    def _on_delete_title(self, title_str: str) -> None:
        assert self._history_store is not None
        self._history_store.delete_events_for_title(title_str)
        self._refresh()

    # --- Keyboard navigation ---

    def enter_nav_focus(self, on_exit_request: Callable[[], None]) -> None:
        """Enter keyboard navigation mode, focusing the first history row."""
        self._nav_on_exit_request = on_exit_request
        self._nav_active = True
        self._nav_focused_idx = 0
        self._update_nav_focus()
        logger.debug("HistoryScreen: entered nav focus.")

    def exit_nav_focus(self) -> None:
        """Exit keyboard navigation mode and clear the row highlight."""
        if not self._nav_active:
            return
        self._nav_active = False
        self._nav_on_exit_request = None
        self._clear_nav_focus()
        logger.debug("HistoryScreen: exited nav focus.")

    def handle_key(self, key: int) -> bool:
        """Handle a keyboard key. Return True if consumed."""
        if not self._nav_active:
            return False
        if key in _NAV_MOVE_DELTAS:
            self._move_nav_focus(_NAV_MOVE_DELTAS[key])
        elif key == KEY_LEFT:
            self._nav_select_view(_JOURNAL_VIEW)
        elif key == KEY_RIGHT:
            self._nav_select_view(_TITLES_VIEW)
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._activate_focused_row()
        elif key == KEY_DELETE:
            self._delete_focused_row()
        elif is_escape_key(key):
            if self._nav_on_exit_request is not None:
                self._nav_on_exit_request()
        else:
            return False
        return True

    def _nav_select_view(self, view: str) -> None:
        if view == self._current_view:
            return
        self._nav_focused_idx = 0
        # _select_view refreshes the rows, which redraws the focus highlight.
        self._select_view(view)

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
        # The delete action refreshes the rows, which re-clamps the focus index.
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
        """Ask for confirmation, then clear the whole history (kv callback)."""
        popup: MessagePopup | None = None

        def do_clear() -> None:
            assert self._history_store is not None
            assert popup is not None
            self._history_store.clear()
            popup.dismiss()
            self._refresh()

        def do_cancel() -> None:
            assert popup is not None
            popup.dismiss()

        popup = MessagePopup(
            text="Clear all reading history?",
            ok_func=do_clear,
            ok_text="Clear",
            cancel_func=do_cancel,
            cancel_text="Cancel",
            title="Clear Reading History",
            msg_halign="center",
        )
        Clock.schedule_once(lambda _dt: popup.open(), 0)
