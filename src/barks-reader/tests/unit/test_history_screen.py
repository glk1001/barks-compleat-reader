# ruff: noqa: SLF001, PLR2004

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core.reader_palette import theme
from barks_reader.core.reading_history import ReadEvent
from barks_reader.ui import history_screen as history_screen_module
from barks_reader.ui.history_screen import (
    _BAR_CLEAR,
    _BAR_JOURNAL,
    _BAR_TITLES,
    _JOURNAL_VIEW,
    _NO_EVENTS_TEXT,
    _TITLES_VIEW,
    _ZONE_BAR,
    _ZONE_LIST,
    HistoryScreen,
    _NavRow,
)
from barks_reader.ui.reader_keyboard_nav import (
    KEY_DELETE,
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_PAGE_DOWN,
    KEY_PAGE_UP,
    KEY_RIGHT,
    KEY_UP,
)
from kivy.uix.floatlayout import FloatLayout

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def screen() -> Generator[HistoryScreen]:
    """Fixture for the HistoryScreen with mocked Kivy dependencies."""
    with (
        patch.object(FloatLayout, "__init__", autospec=True) as mock_layout_init,
        patch.object(history_screen_module, "PanelTextureLoader"),
    ):
        mock_ids = {
            "journal_button": MagicMock(),
            "titles_button": MagicMock(),
            "clear_button": MagicMock(),
            "history_rows": MagicMock(),
            "history_scroll": MagicMock(),
        }

        def side_effect(instance: HistoryScreen, **_kwargs) -> None:  # noqa: ANN003
            instance.ids = mock_ids

        mock_layout_init.side_effect = side_effect

        yield HistoryScreen()


@pytest.fixture
def nav_screen(screen: HistoryScreen) -> Generator[HistoryScreen]:
    """Provide the screen with the focus-highlight drawing and Clock patched out."""
    with (
        patch.object(history_screen_module, "draw_focus_highlight"),
        patch.object(history_screen_module, "clear_focus_highlight"),
        patch.object(history_screen_module, "update_focus_in_list"),
        patch.object(history_screen_module, "clear_focus_in_list"),
        patch.object(history_screen_module, "Clock"),
    ):
        yield screen


def _add_nav_rows(screen: HistoryScreen, n: int) -> list[_NavRow]:
    rows = [_NavRow(widget=MagicMock(), activate=MagicMock(), delete=MagicMock()) for _ in range(n)]
    screen._nav_rows.extend(rows)
    return rows


class TestHistoryScreenNav:
    def test_handle_key_inactive_returns_false(self, nav_screen: HistoryScreen) -> None:
        assert nav_screen.handle_key(KEY_DOWN) is False

    def test_enter_nav_focus_highlights_first_row(self, nav_screen: HistoryScreen) -> None:
        rows = _add_nav_rows(nav_screen, 3)

        nav_screen.enter_nav_focus(MagicMock())

        assert nav_screen._nav_active
        assert nav_screen._nav_focused_idx == 0
        assert nav_screen._nav_focused_widget is rows[0].widget

    def test_up_down_moves_and_clamps(self, nav_screen: HistoryScreen) -> None:
        rows = _add_nav_rows(nav_screen, 3)
        nav_screen.enter_nav_focus(MagicMock())

        nav_screen.handle_key(KEY_DOWN)
        nav_screen.handle_key(KEY_DOWN)
        nav_screen.handle_key(KEY_DOWN)
        assert nav_screen._nav_focused_idx == 2  # clamped at bottom
        assert nav_screen._nav_focused_widget is rows[2].widget

        nav_screen.handle_key(KEY_UP)
        assert nav_screen._nav_focused_idx == 1  # moves back up within the list
        assert nav_screen._nav_zone == _ZONE_LIST

    def test_page_up_down_moves_by_step(self, nav_screen: HistoryScreen) -> None:
        _add_nav_rows(nav_screen, 25)
        nav_screen.enter_nav_focus(MagicMock())

        nav_screen.handle_key(KEY_PAGE_DOWN)
        assert nav_screen._nav_focused_idx == 10

        nav_screen.handle_key(KEY_PAGE_DOWN)
        nav_screen.handle_key(KEY_PAGE_DOWN)
        assert nav_screen._nav_focused_idx == 24  # clamped at bottom

        nav_screen.handle_key(KEY_PAGE_UP)
        assert nav_screen._nav_focused_idx == 14

    def test_enter_activates_focused_row(self, nav_screen: HistoryScreen) -> None:
        rows = _add_nav_rows(nav_screen, 2)
        nav_screen.enter_nav_focus(MagicMock())
        nav_screen.handle_key(KEY_DOWN)

        assert nav_screen.handle_key(KEY_ENTER) is True

        rows[1].activate.assert_called_once()  # ty: ignore[unresolved-attribute]
        rows[0].activate.assert_not_called()  # ty: ignore[unresolved-attribute]

    def test_delete_key_deletes_focused_row(self, nav_screen: HistoryScreen) -> None:
        rows = _add_nav_rows(nav_screen, 2)
        nav_screen.enter_nav_focus(MagicMock())

        assert nav_screen.handle_key(KEY_DELETE) is True

        rows[0].delete.assert_called_once()  # ty: ignore[unresolved-attribute]

    def test_up_from_first_row_enters_top_bar_on_active_tab(
        self, nav_screen: HistoryScreen
    ) -> None:
        _add_nav_rows(nav_screen, 2)
        nav_screen.enter_nav_focus(MagicMock())  # list zone, first row

        assert nav_screen.handle_key(KEY_UP) is True
        assert nav_screen._nav_zone == _ZONE_BAR
        assert nav_screen._bar_focused_idx == _BAR_JOURNAL  # lands on the active tab

    def test_list_left_right_are_not_consumed(self, nav_screen: HistoryScreen) -> None:
        _add_nav_rows(nav_screen, 2)
        nav_screen.enter_nav_focus(MagicMock())

        # In the list zone Left/Right no longer switch tabs (bar-only now).
        assert nav_screen.handle_key(KEY_LEFT) is False
        assert nav_screen.handle_key(KEY_RIGHT) is False
        assert nav_screen._nav_zone == _ZONE_LIST

    def test_bar_left_right_move_focus_and_clamp(self, nav_screen: HistoryScreen) -> None:
        _add_nav_rows(nav_screen, 2)
        nav_screen.enter_nav_focus(MagicMock())
        nav_screen.handle_key(KEY_UP)  # enter bar, on Journal (0)

        assert nav_screen.handle_key(KEY_RIGHT) is True
        assert nav_screen._bar_focused_idx == _BAR_TITLES
        nav_screen.handle_key(KEY_RIGHT)
        assert nav_screen._bar_focused_idx == _BAR_CLEAR
        nav_screen.handle_key(KEY_RIGHT)
        assert nav_screen._bar_focused_idx == _BAR_CLEAR  # clamped at the right

        nav_screen.handle_key(KEY_LEFT)
        nav_screen.handle_key(KEY_LEFT)
        nav_screen.handle_key(KEY_LEFT)
        assert nav_screen._bar_focused_idx == _BAR_JOURNAL  # clamped at the left

    def test_bar_down_returns_to_list(self, nav_screen: HistoryScreen) -> None:
        _add_nav_rows(nav_screen, 2)
        nav_screen.enter_nav_focus(MagicMock())
        nav_screen.handle_key(KEY_UP)  # enter bar

        assert nav_screen.handle_key(KEY_DOWN) is True
        assert nav_screen._nav_zone == _ZONE_LIST
        assert nav_screen._nav_focused_idx == 0

    def test_bar_enter_on_clear_opens_confirm(self, nav_screen: HistoryScreen) -> None:
        _add_nav_rows(nav_screen, 2)
        nav_screen.enter_nav_focus(MagicMock())
        nav_screen.handle_key(KEY_UP)  # bar, Journal
        nav_screen.handle_key(KEY_RIGHT)  # Titles
        nav_screen.handle_key(KEY_RIGHT)  # Clear
        on_clear = MagicMock()
        nav_screen.on_clear_pressed = on_clear

        assert nav_screen.handle_key(KEY_ENTER) is True
        on_clear.assert_called_once()

    def test_bar_enter_on_tab_switches_view(self, nav_screen: HistoryScreen) -> None:
        _add_nav_rows(nav_screen, 2)
        nav_screen.enter_nav_focus(MagicMock())
        nav_screen.handle_key(KEY_UP)  # bar, Journal (current)
        nav_screen.handle_key(KEY_RIGHT)  # Titles
        select_view = MagicMock()
        nav_screen._select_view = select_view

        assert nav_screen.handle_key(KEY_ENTER) is True
        select_view.assert_called_once_with("titles")

    def test_bar_enter_on_current_tab_is_a_no_op(self, nav_screen: HistoryScreen) -> None:
        _add_nav_rows(nav_screen, 2)
        nav_screen.enter_nav_focus(MagicMock())
        nav_screen.handle_key(KEY_UP)  # bar, Journal (already current)
        select_view = MagicMock()
        nav_screen._select_view = select_view

        assert nav_screen.handle_key(KEY_ENTER) is True
        select_view.assert_not_called()

    def test_escape_calls_exit_request(self, nav_screen: HistoryScreen) -> None:
        _add_nav_rows(nav_screen, 1)
        on_exit_request = MagicMock()
        nav_screen.enter_nav_focus(on_exit_request)

        assert nav_screen.handle_key(KEY_ESCAPE) is True

        on_exit_request.assert_called_once()

    def test_exit_nav_focus_clears_highlight(self, nav_screen: HistoryScreen) -> None:
        _add_nav_rows(nav_screen, 1)
        nav_screen.enter_nav_focus(MagicMock())

        nav_screen.exit_nav_focus()

        assert not nav_screen._nav_active
        assert nav_screen._nav_focused_widget is None
        assert nav_screen.handle_key(KEY_DOWN) is False

    def test_unhandled_key_returns_false(self, nav_screen: HistoryScreen) -> None:
        _add_nav_rows(nav_screen, 1)
        nav_screen.enter_nav_focus(MagicMock())

        assert nav_screen.handle_key(ord("q")) is False

    def test_keys_with_no_rows_do_not_crash(self, nav_screen: HistoryScreen) -> None:
        nav_screen.enter_nav_focus(MagicMock())

        assert nav_screen.handle_key(KEY_DOWN) is True
        assert nav_screen.handle_key(KEY_ENTER) is True
        assert nav_screen.handle_key(KEY_DELETE) is True

    def test_scroll_skipped_when_rows_fit_in_viewport(self, nav_screen: HistoryScreen) -> None:
        nav_screen.ids.history_rows.height = 200
        nav_screen.ids.history_scroll.height = 500
        nav_screen.ids.history_scroll.scroll_y = 0.4

        nav_screen._scroll_to_focused_row(MagicMock())

        nav_screen.ids.history_scroll.scroll_to.assert_not_called()
        assert nav_screen.ids.history_scroll.scroll_y == 1.0  # list pinned to the top

    def test_scroll_follows_focus_when_rows_overflow(self, nav_screen: HistoryScreen) -> None:
        nav_screen.ids.history_rows.height = 900
        nav_screen.ids.history_scroll.height = 500
        widget = MagicMock()

        nav_screen._scroll_to_focused_row(widget)

        nav_screen.ids.history_scroll.scroll_to.assert_called_once()
        assert nav_screen.ids.history_scroll.scroll_to.call_args.args[0] is widget

    def test_refresh_clamps_focus_after_rows_shrink(self, nav_screen: HistoryScreen) -> None:
        _add_nav_rows(nav_screen, 3)
        nav_screen.enter_nav_focus(MagicMock())
        nav_screen._nav_focused_idx = 2

        store = MagicMock()
        store.get_events.return_value = []
        nav_screen.set_history_store(store)
        with patch.object(HistoryScreen, "_make_header_label"):
            nav_screen._refresh()

        assert nav_screen._nav_focused_idx == 0
        assert nav_screen._nav_focused_widget is None  # no rows left to highlight


_DAY_1 = datetime(2026, 9, 5, 10, 0)  # noqa: DTZ001
_DAY_2 = datetime(2026, 9, 6, 11, 0)  # noqa: DTZ001


class _FakeStore:
    """A minimal stand-in for ReadingHistoryStore, with the same revision contract."""

    def __init__(self, events: list[ReadEvent]) -> None:
        self._events = list(events)
        self.revision = 0

    def get_events(self) -> list[ReadEvent]:
        return list(self._events)

    def delete_event(self, event_id: str) -> None:
        self._events = [e for e in self._events if e.event_id != event_id]
        self.revision += 1

    def delete_events_for_title(self, title_str: str) -> None:
        self._events = [e for e in self._events if e.title_str != title_str]
        self.revision += 1

    def clear(self) -> None:
        self._events = []
        self.revision += 1


def _event(event_id: str, title: str, opened_at: datetime) -> ReadEvent:
    return ReadEvent(event_id=event_id, title_str=title, opened_at=opened_at)


# Two days: day 1 has three events (one title read twice), day 2 has one.
_EVENTS = [
    _event("e1", "Omelet", _DAY_1),
    _event("e2", "Good Deeds", _DAY_1.replace(hour=12)),
    _event("e3", "Omelet", _DAY_1.replace(hour=14)),
    _event("e4", "Lifeguard Daze", _DAY_2),
]


@pytest.fixture
def stocked_screen(screen: HistoryScreen) -> Generator[tuple[HistoryScreen, _FakeStore]]:
    """Wire the screen to a four-event store, holding the frame Clock still."""
    with patch.object(history_screen_module, "Clock"):
        store = _FakeStore(_EVENTS)
        # Assigned directly: _FakeStore is a structural stand-in, not a subclass.
        screen._history_store = store
        yield screen, store


def _stripe(nav_row: _NavRow) -> list[float]:
    return list(nav_row.widget._stripe_color.rgba)


class TestHistoryScreenBuildCache:
    def test_second_refresh_reuses_the_built_widgets(
        self, stocked_screen: tuple[HistoryScreen, _FakeStore]
    ) -> None:
        screen, _store = stocked_screen
        screen._refresh()
        first = list(screen._nav_rows)

        screen._refresh()

        assert [r.widget for r in screen._nav_rows] == [r.widget for r in first]

    def test_refresh_rebuilds_after_the_store_changes(
        self, stocked_screen: tuple[HistoryScreen, _FakeStore]
    ) -> None:
        screen, store = stocked_screen
        screen._refresh()
        first_widgets = [r.widget for r in screen._nav_rows]

        store.revision += 1
        screen._refresh()

        assert [r.widget for r in screen._nav_rows] != first_widgets

    def test_each_view_is_cached_separately(
        self, stocked_screen: tuple[HistoryScreen, _FakeStore]
    ) -> None:
        screen, _store = stocked_screen
        screen._select_view(_JOURNAL_VIEW)
        journal_widgets = [r.widget for r in screen._nav_rows]

        screen._select_view(_TITLES_VIEW)
        assert [r.widget for r in screen._nav_rows] != journal_widgets

        screen._select_view(_JOURNAL_VIEW)
        assert [r.widget for r in screen._nav_rows] == journal_widgets

    def test_build_is_chunked_across_frames(
        self, stocked_screen: tuple[HistoryScreen, _FakeStore], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        screen, _store = stocked_screen
        monkeypatch.setattr(history_screen_module, "_FIRST_CHUNK_ITEMS", 2)
        monkeypatch.setattr(history_screen_module, "_CHUNK_ITEMS", 2)

        screen._refresh()
        # Journal items are [header, row, row, row, header, row]: two so far.
        assert screen._building is not None
        assert len(screen._nav_rows) == 1

        while screen._building is not None:
            screen._build_next_chunk(0)

        assert len(screen._nav_rows) == len(_EVENTS)

    def test_interrupted_build_is_not_cached(
        self, stocked_screen: tuple[HistoryScreen, _FakeStore], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        screen, _store = stocked_screen
        monkeypatch.setattr(history_screen_module, "_FIRST_CHUNK_ITEMS", 2)

        screen._select_view(_JOURNAL_VIEW)
        assert screen._building is not None  # Still part-built.

        screen._select_view(_TITLES_VIEW)

        assert _JOURNAL_VIEW not in screen._view_cache

    def test_clearing_shows_the_empty_message(
        self, stocked_screen: tuple[HistoryScreen, _FakeStore]
    ) -> None:
        screen, store = stocked_screen
        screen._refresh()

        store.clear()
        screen._refresh()

        assert screen._nav_rows == []
        built = screen._view_cache[_JOURNAL_VIEW]
        assert built.widgets[0].text == f"[b]{_NO_EVENTS_TEXT}[/b]"


class TestHistoryScreenIncrementalDelete:
    def test_delete_removes_only_the_deleted_row(
        self, stocked_screen: tuple[HistoryScreen, _FakeStore]
    ) -> None:
        screen, _store = stocked_screen
        screen._refresh()
        survivors = [r.widget for r in screen._nav_rows if r.key != "e2"]

        screen._on_delete_event("e2")

        # The other rows are the same widget objects: they were never rebuilt.
        assert [r.widget for r in screen._nav_rows] == survivors

    def test_delete_removes_a_day_header_left_empty(
        self, stocked_screen: tuple[HistoryScreen, _FakeStore]
    ) -> None:
        screen, _store = stocked_screen
        screen._refresh()
        built = screen._view_cache[_JOURNAL_VIEW]
        day_2_heading = screen._nav_rows[0].group  # Newest day first: day 2's lone event.
        assert day_2_heading in built.headers

        screen._on_delete_event("e4")

        assert day_2_heading not in built.headers
        assert len(built.headers) == 1  # Day 1's header survives.

    def test_delete_restripes_the_remaining_rows(
        self, stocked_screen: tuple[HistoryScreen, _FakeStore]
    ) -> None:
        screen, _store = stocked_screen
        screen._refresh()
        palette = theme()
        # Day 1's three events, newest first: e3, e2, e1 - striped even/odd/even.
        day_1_rows = [r for r in screen._nav_rows if r.key in ("e1", "e2", "e3")]
        assert _stripe(day_1_rows[1]) == pytest.approx(list(palette.row_stripe_odd))

        screen._on_delete_event("e3")  # Drop the first of that day.

        day_1_rows = [r for r in screen._nav_rows if r.key in ("e1", "e2")]
        assert _stripe(day_1_rows[0]) == pytest.approx(list(palette.row_stripe_even))
        assert _stripe(day_1_rows[1]) == pytest.approx(list(palette.row_stripe_odd))

    def test_delete_drops_the_other_views_cache(
        self, stocked_screen: tuple[HistoryScreen, _FakeStore]
    ) -> None:
        screen, _store = stocked_screen
        screen._select_view(_TITLES_VIEW)
        screen._select_view(_JOURNAL_VIEW)
        assert _TITLES_VIEW in screen._view_cache

        screen._on_delete_event("e2")

        assert _TITLES_VIEW not in screen._view_cache
        assert screen._view_cache[_JOURNAL_VIEW].revision == screen._history_store.revision

    def test_deleting_a_title_removes_its_row_from_the_titles_view(
        self, stocked_screen: tuple[HistoryScreen, _FakeStore]
    ) -> None:
        screen, _store = stocked_screen
        screen._select_view(_TITLES_VIEW)
        assert "Omelet" in [r.key for r in screen._nav_rows]

        screen._on_delete_title("Omelet")

        assert "Omelet" not in [r.key for r in screen._nav_rows]

    def test_deleting_the_last_row_shows_the_empty_message(
        self, stocked_screen: tuple[HistoryScreen, _FakeStore]
    ) -> None:
        screen, store = stocked_screen
        store._events = [_event("only", "Omelet", _DAY_1)]
        screen._refresh()

        screen._on_delete_event("only")

        assert screen._nav_rows == []
        built = screen._view_cache[_JOURNAL_VIEW]
        assert built.widgets[-1].text == f"[b]{_NO_EVENTS_TEXT}[/b]"

    def test_delete_mid_build_falls_back_to_a_refresh(
        self, stocked_screen: tuple[HistoryScreen, _FakeStore], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        screen, _store = stocked_screen
        monkeypatch.setattr(history_screen_module, "_FIRST_CHUNK_ITEMS", 2)
        screen._refresh()
        assert screen._building is not None

        screen._on_delete_event("e2")

        # The part-built view was abandoned and a fresh build started; drain it.
        while screen._building is not None:
            screen._build_next_chunk(0)

        assert [r.key for r in screen._nav_rows] == ["e4", "e3", "e1"]
