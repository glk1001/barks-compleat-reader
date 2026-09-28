# ruff: noqa: SLF001
# cspell:ignore pytestmark
"""The viewer's desktop and mouse paths, on a real viewer over a small bundle.

The remote's paths are the GUI suite's (``src/barks-reader/tests/gui/test_wiki.py``);
what a remote cannot reach is here: the standalone app's keys, PageUp/PageDown/
Home/End, the mouse's hover and back button, a link inside a footnote, and the
search index failing to build. A viewer needs a Kivy window, which the macOS and
Windows CI runners do not have (KIVY_HEADLESS_CI), so there these are skipped.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from okf_reader.core.session import load_session_state
from okf_reader.ui import viewer as viewer_module
from okf_reader.ui.keynav import (
    KEY_DOWN,
    KEY_END,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_F,
    KEY_HOME,
    KEY_LEFT,
    KEY_PAGE_DOWN,
    KEY_PAGE_UP,
)
from okf_reader.ui.viewer import SEARCH_ERROR_TEXT, FocusRegion, OKFApp, OKFViewer

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from okf_reader.core.search import SearchHit

pytestmark = pytest.mark.skipif(
    os.environ.get("KIVY_HEADLESS_CI", "") == "1",
    reason="a viewer needs a Kivy window, and headless CI has none",
)

HOME_PAGE = """# Home

See [the page](concept/a.md).[^note]

[^note]: A note that links to [the page](concept/a.md).
"""
A_PAGE = """---
title: A
---
# A

Body.
"""


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    """Make a two-page bundle: a home page with a link and a footnote, and the linked page."""
    root = tmp_path / "bundle"
    (root / "concept").mkdir(parents=True)
    (root / "index.md").write_text(HOME_PAGE, encoding="utf-8")
    (root / "concept" / "a.md").write_text(A_PAGE, encoding="utf-8")
    return root


@pytest.fixture
def viewer(bundle: Path) -> Iterator[OKFViewer]:
    yield OKFViewer(bundle)
    _remove_popups_left_open()


def _remove_popups_left_open() -> None:
    """Take any popup a test opened off the window, at once.

    A dismissed popup animates out, and a unit test never ticks the clock, so it
    would stay on the window for every test after; the main screen hands an open
    popup every key, and its key tests then fail (a random-order run found it).
    """
    from kivy.core.window import Window  # noqa: PLC0415 — the realized window

    for widget in list(Window.children):
        if isinstance(widget, ModalView):
            Window.remove_widget(widget)


def _page(viewer: OKFViewer) -> str:
    return viewer.history[-1].path.relative_to(viewer.bundle).as_posix()


class TestPageScrollKeys:
    """The desktop's page keys scroll a page taller than its view."""

    @pytest.fixture
    def long_page(self, viewer: OKFViewer) -> OKFViewer:
        viewer._set_focus_region(FocusRegion.PAGE)
        viewer.body_scroll.height = 100
        viewer.body.height = 1000
        viewer.body_scroll.scroll_y = 1.0
        return viewer

    def test_page_down_and_up_move_by_a_view(self, long_page: OKFViewer) -> None:
        assert long_page.handle_key(KEY_PAGE_DOWN) is True
        down = long_page.body_scroll.scroll_y
        assert down < 1.0
        long_page.handle_key(KEY_PAGE_UP)
        assert long_page.body_scroll.scroll_y > down

    def test_end_and_home_jump_to_the_ends(self, long_page: OKFViewer) -> None:
        long_page.handle_key(KEY_END)
        assert long_page.body_scroll.scroll_y == 0.0
        long_page.handle_key(KEY_HOME)
        assert long_page.body_scroll.scroll_y == 1.0

    def test_end_on_a_page_that_fits_stays_at_the_top(self, long_page: OKFViewer) -> None:
        long_page.body.height = 50
        long_page.handle_key(KEY_END)
        assert long_page.body_scroll.scroll_y == 1.0


class TestFootnoteLink:
    def test_a_link_inside_a_footnote_closes_it_and_opens_the_page(self, viewer: OKFViewer) -> None:
        note_label = next(lbl for lbl, ref, _ in viewer._page_links if ref == "fn:note")
        viewer._on_ref(note_label, "fn:note")
        popup = viewer._footnote_popup
        assert popup is not None
        popup_label = viewer._popup_link_label
        assert popup_label is not None
        with patch.object(popup, "dismiss", wraps=popup.dismiss) as dismiss:
            popup_label.dispatch("on_ref_press", "concept/a.md")
        dismiss.assert_called_once()
        assert _page(viewer) == "concept/a.md"
        assert len(viewer.history) == 2  # noqa: PLR2004

    def test_the_popup_takes_escape_and_holds_the_arrows(self, viewer: OKFViewer) -> None:
        note_label = next(lbl for lbl, ref, _ in viewer._page_links if ref == "fn:note")
        viewer._on_ref(note_label, "fn:note")
        popup = viewer._footnote_popup
        assert popup is not None
        with patch.object(popup, "dismiss") as dismiss:
            assert viewer.handle_key(KEY_DOWN) is True  # nothing moves under the modal
            dismiss.assert_not_called()
            assert viewer.handle_key(KEY_ESCAPE) is True
            dismiss.assert_called_once()


class TestMouse:
    def test_the_back_button_goes_back(self, viewer: OKFViewer) -> None:
        viewer.show_page(viewer.bundle / "concept" / "a.md")
        assert viewer.on_touch_down(SimpleNamespace(button="mouse4")) is True
        assert _page(viewer) == "index.md"

    def test_a_press_drops_the_keyboard_focus_out_of_the_bar(self, viewer: OKFViewer) -> None:
        viewer.handle_key(KEY_ESCAPE)  # up to the bar
        assert viewer._focus_region is FocusRegion.TOP_BAR
        touch = MagicMock(button="left", pos=(-1000, -1000))
        viewer.on_touch_down(touch)
        assert viewer._focus_region is FocusRegion.SIDEBAR

    def test_no_link_is_under_the_mouse_when_the_viewer_is_not_on_screen(
        self, viewer: OKFViewer
    ) -> None:
        assert viewer._over_link((10, 10)) is False

    def test_an_open_footnote_owns_the_hover(self, viewer: OKFViewer) -> None:
        label = Label()
        viewer._popup_link_label = label
        with (
            patch.object(viewer, "get_root_window", return_value=object()),
            patch.object(viewer_module, "_ref_under", return_value="concept/a.md") as under,
        ):
            assert viewer._over_link((10, 10)) is True
        under.assert_called_once_with(label, 10, 10)

    def test_the_cursor_changes_only_on_a_change(self, viewer: OKFViewer) -> None:
        with patch("kivy.core.window.Window") as window:
            viewer._set_hand_cursor(over=True)
            viewer._set_hand_cursor(over=True)
            viewer._set_hand_cursor(over=False)
        assert [c.args[0] for c in window.set_system_cursor.call_args_list] == ["hand", "arrow"]


class TestRefUnder:
    """The hit test behind the hand cursor: which of a label's links is under a point."""

    @pytest.fixture
    def label(self) -> Label:
        lbl = Label(size=(200, 40), pos=(0, 0))
        lbl.texture_size = (100, 20)  # centred: spans x 50..150, y 10..30
        lbl.refs = {"here": [(0, 0, 50, 20)], "there": [(50, 0, 100, 20)]}
        return lbl

    def test_each_link_by_where_the_point_is(self, label: Label) -> None:
        assert viewer_module._ref_under(label, 60, 20) == "here"
        assert viewer_module._ref_under(label, 140, 20) == "there"

    def test_outside_the_label_is_no_link(self, label: Label) -> None:
        assert viewer_module._ref_under(label, 500, 20) is None

    def test_inside_the_label_but_off_its_text_is_no_link(self, label: Label) -> None:
        assert viewer_module._ref_under(label, 10, 20) is None


class _NoWarmSearcher:
    """A search provider with no index to warm."""

    def search(self, query: str) -> list[SearchHit]:  # noqa: ARG002
        return []


class TestSearchIndexFailure:
    def test_a_failed_build_shows_the_error_note(self, viewer: OKFViewer) -> None:
        viewer.search_field.text = "grotto"
        viewer._mark_search_ready(failed=True)
        notes = [w.text for w in viewer._left_body.children if isinstance(w, Label)]
        assert notes == [SEARCH_ERROR_TEXT]

    def test_the_worker_reports_a_failure_on_the_ui_thread(self, viewer: OKFViewer) -> None:
        def broken() -> None:
            raise OSError

        with patch.object(viewer_module, "Clock") as clock:
            viewer._warm_search_index(broken)
        with patch.object(viewer, "_mark_search_ready") as mark:
            clock.schedule_once.call_args.args[0](0)
        mark.assert_called_once_with(failed=True)

    def test_a_provider_that_needs_no_warming_is_ready_at_once(self, viewer: OKFViewer) -> None:
        viewer._searcher = _NoWarmSearcher()
        viewer._on_search_focus(None, focused=True)
        assert viewer._search_ready is True


class TestStandaloneApp:
    """The standalone reader's own keys: Ctrl+F, Alt+Left, and Escape while typing."""

    @pytest.fixture
    def app(self, bundle: Path, tmp_path: Path) -> OKFApp:
        app = OKFApp(bundle, state_path=tmp_path / "session.json")
        app.build()
        return app

    def _key(self, app: OKFApp, key: int, *modifiers: str) -> bool:
        return app._on_keyboard(None, key, 0, "", list(modifiers))

    def test_ctrl_f_focuses_the_search_box(self, app: OKFApp) -> None:
        assert app._viewer is not None
        with patch.object(app._viewer, "focus_search") as focus:
            assert self._key(app, KEY_F, "ctrl") is True
        focus.assert_called_once()

    def test_alt_left_goes_back(self, app: OKFApp) -> None:
        assert app._viewer is not None
        app._viewer.show_page(app._viewer.bundle / "concept" / "a.md")
        assert self._key(app, KEY_LEFT, "alt") is True
        assert _page(app._viewer) == "index.md"

    def test_alt_left_is_left_to_the_search_box_while_it_types(self, app: OKFApp) -> None:
        assert app._viewer is not None
        with patch.object(type(app._viewer), "search_focused", new=True):
            assert self._key(app, KEY_LEFT, "alt") is False

    def test_escape_while_typing_backs_out_of_the_search(self, app: OKFApp) -> None:
        assert app._viewer is not None
        with (
            patch.object(type(app._viewer), "search_focused", new=True),
            patch.object(app._viewer, "escape_search") as escape,
        ):
            assert self._key(app, KEY_ESCAPE) is True
        escape.assert_called_once()

    def test_the_viewer_takes_the_rest(self, app: OKFApp) -> None:
        assert self._key(app, KEY_ENTER) is True  # the sidebar's Enter

    def test_on_stop_saves_where_the_reader_was(self, app: OKFApp, tmp_path: Path) -> None:
        assert app._viewer is not None
        app._viewer.show_page(app._viewer.bundle / "concept" / "a.md")
        app.on_stop()
        state = load_session_state(tmp_path / "session.json", app._viewer.bundle)
        assert state is not None
        assert state.page.name == "a.md"
