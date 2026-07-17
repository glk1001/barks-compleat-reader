"""The Reading History screen: a browsable journal of every comic read.

Two toggleable views over the same event log: "Journal" (sessions grouped by
day, newest first) and "Titles" (one row per title with a read count). Rows
navigate to the title's tree view; each row also has a delete button, and the
top bar has a clear-all button (with confirmation popup).
"""

from __future__ import annotations

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

        events = self._history_store.get_events()
        if not events:
            rows.add_widget(self._make_header_label("No comics read yet."))
        elif self._current_view == _JOURNAL_VIEW:
            self._populate_journal(events)
        else:
            self._populate_titles(events)

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
