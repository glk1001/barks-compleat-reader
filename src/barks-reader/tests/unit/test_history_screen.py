# ruff: noqa: SLF001, PLR2004

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui import history_screen as history_screen_module
from barks_reader.ui.history_screen import HistoryScreen, _NavRow
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

        assert nav_screen.handle_key(KEY_UP) is True
        assert nav_screen._nav_focused_idx == 0  # clamped at top

        nav_screen.handle_key(KEY_DOWN)
        nav_screen.handle_key(KEY_DOWN)
        nav_screen.handle_key(KEY_DOWN)
        assert nav_screen._nav_focused_idx == 2  # clamped at bottom
        assert nav_screen._nav_focused_widget is rows[2].widget

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

    def test_left_right_switch_view(self, nav_screen: HistoryScreen) -> None:
        _add_nav_rows(nav_screen, 2)
        nav_screen.enter_nav_focus(MagicMock())
        nav_screen._nav_focused_idx = 1
        select_view = MagicMock()
        nav_screen._select_view = select_view

        assert nav_screen.handle_key(KEY_RIGHT) is True
        select_view.assert_called_once_with("titles")
        assert nav_screen._nav_focused_idx == 0  # focus resets to the top

        nav_screen._current_view = "titles"
        assert nav_screen.handle_key(KEY_LEFT) is True
        select_view.assert_called_with("journal")

    def test_switch_to_current_view_is_a_no_op(self, nav_screen: HistoryScreen) -> None:
        _add_nav_rows(nav_screen, 2)
        nav_screen.enter_nav_focus(MagicMock())
        select_view = MagicMock()
        nav_screen._select_view = select_view

        assert nav_screen.handle_key(KEY_LEFT) is True  # journal is already current

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
