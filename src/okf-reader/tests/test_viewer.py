# ruff: noqa: SLF001
# cspell:ignore ffcc pytestmark
"""The viewer's desktop and mouse paths, on a real viewer over a small bundle.

The remote's paths are the GUI suite's (``src/barks-reader/tests/gui/test_wiki.py``);
what a remote cannot reach is here: the standalone app's keys, PageUp/PageDown/
Home/End, the mouse's hover and back button, a link inside a footnote, and the
search index failing to build. A viewer needs a Kivy window, so these are skipped
where there is none (KIVY_HEADLESS_CI); every CI runner draws one now (macOS on
Apple's software renderer, Windows through ANGLE) and runs them.
"""

from __future__ import annotations

import gc
import os
import weakref
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from okf_reader.core.actions import PageAction
from okf_reader.core.render import TableBlock
from okf_reader.core.search import SearchHit
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
    KEY_RIGHT,
    KEY_TAB,
)
from okf_reader.ui.viewer import (
    LAZY_TABLE_MARGIN,
    LAZY_TABLE_MIN_ROWS,
    SEARCH_ERROR_TEXT,
    TABLE_FONT_NAME,
    FocusRegion,
    OKFApp,
    OKFViewer,
    _LazyTable,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from kivy.uix.widget import Widget

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
    okf_viewer = OKFViewer(bundle)
    yield okf_viewer
    # A focused box holds the window's one keyboard until it lets go, and the main
    # screen leaves every key to a focused text input: its key tests then fail (a
    # random-order run found it, after focus_search's test).
    okf_viewer.search_field.focus = False
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


class TestUnreadablePage:
    def test_a_page_gone_since_the_tree_was_built_shows_page_unavailable(
        self, viewer: OKFViewer
    ) -> None:
        """The wiki regenerated under the reader: an error page, not a crash."""
        gone = viewer.bundle / "concept" / "a.md"
        gone.unlink()
        with patch.object(viewer_module, "render_page", wraps=viewer_module.render_page) as render:
            viewer.show_page(gone)
        text = render.call_args.args[0]
        assert text.startswith("# Page unavailable")
        assert "`a.md`" in text
        assert _page(viewer) == "concept/a.md"


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


class TestSearchFocus:
    def test_any_focus_is_logged_a_tap_too(self, viewer: OKFViewer) -> None:
        """A test waits on this line after tapping the box, before it types."""
        with patch.object(viewer_module.trace, "search_focused") as focused:
            viewer._on_search_focus(None, focused=True)  # as a tap focuses it
            viewer._on_search_focus(None, focused=False)
        focused.assert_called_once()

    def test_focus_search_is_logged_once(self, viewer: OKFViewer) -> None:
        with patch.object(viewer_module.trace, "search_focused") as focused:
            viewer.focus_search()
        focused.assert_called_once()


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


# A long table's rows, as the core pads them: a colored header, one- and two-line rows.
LONG_TABLE_ROWS = [
    "[color=ffcc00]Title             Year[/color]",
    *(
        f"Story {i:<12}{1940 + i % 30}" if i % 7 else f"Story {i:<12}{1940 + i % 30}\n  (cont.)"
        for i in range(1, LAZY_TABLE_MIN_ROWS + 150)
    ),
]


def _eager_heights(rows: list[str], font_size: int) -> list[int]:
    """Each row's height as the eager table's own row Labels take it."""
    heights = []
    for row in rows:
        lbl = Label(text=row, markup=True, font_name=TABLE_FONT_NAME, font_size=font_size)
        lbl.texture_update()
        heights.append(lbl.texture_size[1])
    return heights


class TestLazyTable:
    """A long, link-free table builds Labels only for the rows near the viewport."""

    FONT_SIZE = 13

    @pytest.fixture
    def viewport(self) -> ScrollView:
        return ScrollView(size_hint=(None, None), size=(400, 300), pos=(0, 0))

    @pytest.fixture
    def table(self, viewport: ScrollView) -> _LazyTable:
        table = _LazyTable(LONG_TABLE_ROWS, self.FONT_SIZE, viewport)
        table.y = viewport.top - table.height  # the table's top at the viewport's top
        table._update()
        return table

    def test_it_takes_the_eager_tables_size_at_once(self, table: _LazyTable) -> None:
        heights = _eager_heights(LONG_TABLE_ROWS, self.FONT_SIZE)
        assert table.height == sum(heights)
        widths = []
        for row in LONG_TABLE_ROWS:
            lbl = Label(text=row, markup=True, font_name=TABLE_FONT_NAME, font_size=self.FONT_SIZE)
            lbl.texture_update()
            widths.append(lbl.texture_size[0])
        assert table.width == max(widths)

    def test_only_the_rows_near_the_viewport_are_built(
        self, table: _LazyTable, viewport: ScrollView
    ) -> None:
        heights = _eager_heights(LONG_TABLE_ROWS, self.FONT_SIZE)
        reach = viewport.height * (1 + LAZY_TABLE_MARGIN)
        expected = next(i for i in range(len(heights)) if sum(heights[:i]) >= reach)
        assert table.built_rows == list(range(expected))
        assert len(table.children) == expected < len(LONG_TABLE_ROWS)

    def test_each_built_row_sits_where_the_eager_table_puts_it(self, table: _LazyTable) -> None:
        heights = _eager_heights(LONG_TABLE_ROWS, self.FONT_SIZE)
        for index in table.built_rows[:20]:
            label = table._built[index]
            assert label.top == table.height - sum(heights[:index])
            assert label.size == label.texture_size

    def test_scrolling_to_the_end_builds_the_last_rows_and_reuses_labels(
        self, table: _LazyTable, viewport: ScrollView
    ) -> None:
        labels_before = {id(lbl) for lbl in table.children}
        table.y = viewport.y  # the table's bottom at the viewport's bottom
        table._update()
        assert table.built_rows[-1] == len(LONG_TABLE_ROWS) - 1
        assert 0 not in table.built_rows
        assert {id(lbl) for lbl in table.children} <= labels_before  # reused, none new

    def test_a_row_of_another_height_than_reserved_is_logged_once(
        self, viewport: ScrollView
    ) -> None:
        table = _LazyTable(LONG_TABLE_ROWS, self.FONT_SIZE, viewport)
        table._tops = [top * 2 for top in table._tops]  # every row's slot twice its height
        table.y = viewport.top - table.height
        with patch.object(viewer_module.trace, "lazy_row_height_differs") as logged:
            table._update()
        logged.assert_called_once()
        row, real, reserved = logged.call_args.args
        assert (row, reserved) == (0, 2 * real)

    def test_rows_of_the_reserved_height_log_nothing(self, viewport: ScrollView) -> None:
        table = _LazyTable(LONG_TABLE_ROWS, self.FONT_SIZE, viewport)
        table.y = viewport.top - table.height
        with patch.object(viewer_module.trace, "lazy_row_height_differs") as logged:
            table._update()
        logged.assert_not_called()

    def test_the_page_scroll_view_does_not_keep_a_table_alive(self, viewport: ScrollView) -> None:
        table = weakref.ref(_LazyTable(LONG_TABLE_ROWS, self.FONT_SIZE, viewport))
        gc.collect()
        assert table() is None
        viewport.scroll_y = 0.5  # its dead binding must not break the scroll view


class TestTableWidget:
    """Which tables the viewer builds lazily: long ones without a link."""

    def _table(self, viewer: OKFViewer, rows: list[str]) -> Widget:
        return viewer._table_widget(TableBlock(rows), viewer.bundle / "index.md").children[0]

    def test_a_long_table_without_links_is_lazy(self, viewer: OKFViewer) -> None:
        assert isinstance(self._table(viewer, LONG_TABLE_ROWS), _LazyTable)

    def test_a_short_table_is_built_whole(self, viewer: OKFViewer) -> None:
        table = self._table(viewer, LONG_TABLE_ROWS[: LAZY_TABLE_MIN_ROWS - 1])
        assert not isinstance(table, _LazyTable)
        assert len(table.children) == LAZY_TABLE_MIN_ROWS - 1

    def test_a_long_table_with_a_link_is_built_whole(self, viewer: OKFViewer) -> None:
        rows = [*LONG_TABLE_ROWS, "[ref=concept/a.md]A[/ref]"]
        assert not isinstance(self._table(viewer, rows), _LazyTable)


def _concept(viewer: OKFViewer) -> Any:  # noqa: ANN401
    """Return the tree's one directory node, the bundle's ``concept`` folder."""
    return next(n for n in viewer.tree.iterate_open_nodes() if n.text == "Concept")


def _left_texts(viewer: OKFViewer) -> list[str]:
    return [w.text for w in viewer._left_body.walk(restrict=True) if isinstance(w, Label)]


class _Hits:
    """A ready search provider with fixed hits."""

    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits

    def search(self, query: str) -> list[SearchHit]:  # noqa: ARG002
        return self.hits


def _hit(path: Path, title: str) -> SearchHit:
    return SearchHit(path=path, title=title, breadcrumb="", matched_on="title", score=1)


class TestTreeKeys:
    """The sidebar's tree on the keys a desktop adds, and the edges of the remote's."""

    def test_home_and_end_go_to_the_first_and_last_node(self, viewer: OKFViewer) -> None:
        concept = _concept(viewer)
        viewer.tree.toggle_node(concept)
        viewer._add_tree_nodes(viewer_module.list_children(concept.bundle_path), concept)
        nodes = list(viewer.tree.iterate_open_nodes())

        assert viewer.handle_key(KEY_END) is True
        assert viewer.tree.selected_node is nodes[-1]
        assert viewer.handle_key(KEY_HOME) is True
        assert viewer.tree.selected_node is nodes[0]

    def test_an_unmapped_key_is_left_to_the_host(self, viewer: OKFViewer) -> None:
        assert viewer.handle_key(KEY_F) is False

    def test_with_nothing_selected_right_crosses_to_the_page(self, viewer: OKFViewer) -> None:
        assert viewer.tree.selected_node is None
        viewer.handle_key(KEY_RIGHT)
        assert viewer._focus_region is FocusRegion.PAGE

    def test_with_nothing_selected_left_and_enter_do_nothing(self, viewer: OKFViewer) -> None:
        assert viewer.handle_key(KEY_LEFT) is True
        assert viewer.handle_key(KEY_ENTER) is True
        assert _page(viewer) == "index.md"
        assert viewer._focus_region is FocusRegion.SIDEBAR

    def test_right_on_an_open_empty_folder_stays_put(self, viewer: OKFViewer) -> None:
        concept = _concept(viewer)
        viewer.tree.toggle_node(concept)
        for child in list(concept.nodes):  # a folder whose pages have all gone
            viewer.tree.remove_node(child)
        viewer._focus_tree_node(concept)

        viewer.handle_key(KEY_RIGHT)

        assert viewer.tree.selected_node is concept

    def test_an_empty_tree_takes_only_the_navigation_keys(self, viewer: OKFViewer) -> None:
        with patch.object(viewer.tree, "iterate_open_nodes", return_value=iter(())):
            assert viewer.handle_key(KEY_DOWN) is True
        with patch.object(viewer.tree, "iterate_open_nodes", return_value=iter(())):
            assert viewer.handle_key(KEY_ENTER) is False

    def test_a_folder_without_an_index_page_opens_no_page(self, viewer: OKFViewer) -> None:
        viewer._on_node(_concept(viewer))
        viewer._on_node(SimpleNamespace())  # neither a page nor a folder
        assert _page(viewer) == "index.md"

    def test_a_folder_with_an_index_page_opens_it(self, viewer: OKFViewer) -> None:
        (viewer.bundle / "concept" / "index.md").write_text("# Concept\n", encoding="utf-8")
        viewer._on_node(_concept(viewer))
        assert _page(viewer) == "concept/index.md"


class TestSidebarWhileSearching:
    def _type(self, viewer: OKFViewer, text: str) -> None:
        viewer.search_field.text = text

    def test_before_the_index_is_ready_it_says_it_is_searching(self, viewer: OKFViewer) -> None:
        self._type(viewer, "grotto")
        assert _left_texts(viewer) == ["Searching…"]

    def test_while_waiting_right_crosses_and_the_rest_are_held(self, viewer: OKFViewer) -> None:
        self._type(viewer, "grotto")
        assert viewer.handle_key(KEY_DOWN) is True
        assert viewer.handle_key(KEY_F) is False
        assert viewer.handle_key(KEY_RIGHT) is True
        assert viewer._focus_region is FocusRegion.PAGE

    def test_typing_after_a_failed_build_shows_the_error(self, viewer: OKFViewer) -> None:
        viewer._mark_search_ready(failed=True)
        self._type(viewer, "grotto")
        assert _left_texts(viewer) == [SEARCH_ERROR_TEXT]

    def test_typing_once_ready_lists_the_hits(self, viewer: OKFViewer) -> None:
        a_page = viewer.bundle / "concept" / "a.md"
        viewer._searcher = _Hits([_hit(a_page, "A")])
        viewer._mark_search_ready(failed=False)

        self._type(viewer, "a")

        assert [path for path, _btn in viewer._result_rows] == [a_page]

    def test_the_clear_button_puts_the_tree_back(self, viewer: OKFViewer) -> None:
        self._type(viewer, "grotto")
        viewer._clear_search()
        assert viewer.search_field.text == ""
        assert viewer.tree_scroll.parent is viewer._left_body

    def test_clearing_twice_leaves_the_tree_alone(self, viewer: OKFViewer) -> None:
        viewer._show_tree_panel()
        assert viewer.tree_scroll.parent is viewer._left_body


class TestResultKeys:
    @pytest.fixture
    def results(self, viewer: OKFViewer) -> OKFViewer:
        hits = [_hit(viewer.bundle / f"p{i}.md", f"Page {i}") for i in range(3)]
        viewer._searcher = _Hits(hits)
        viewer._mark_search_ready(failed=False)
        viewer.search_field.text = "page"
        viewer._set_focus_region(FocusRegion.SIDEBAR)
        return viewer

    def test_end_and_home_go_to_the_last_and_first_row(self, results: OKFViewer) -> None:
        results.handle_key(KEY_END)
        assert results._sidebar_index == 2  # noqa: PLR2004
        results.handle_key(KEY_HOME)
        assert results._sidebar_index == 0

    def test_left_is_held_and_others_are_left_to_the_host(self, results: OKFViewer) -> None:
        assert results.handle_key(KEY_LEFT) is True
        assert results.handle_key(KEY_F) is False

    def test_a_row_out_of_view_is_scrolled_to(self, results: OKFViewer) -> None:
        scroll = results._results_scroll
        assert scroll is not None
        scroll.height = 10
        scroll.children[0].height = 1000
        with patch.object(scroll, "scroll_to") as scroll_to:
            results.handle_key(KEY_END)
        scroll_to.assert_called_once()


class TestBarKeys:
    def test_with_no_bar_buttons_escape_stays_where_it_is(self, viewer: OKFViewer) -> None:
        with patch.object(viewer, "_bar_nav_buttons", return_value=[]):
            viewer.handle_key(KEY_ESCAPE)
        assert viewer._focus_region is FocusRegion.SIDEBAR

    def test_buttons_gone_under_the_ring_drop_the_focus_out(self, viewer: OKFViewer) -> None:
        viewer.handle_key(KEY_ESCAPE)
        with patch.object(viewer, "_bar_nav_buttons", return_value=[]):
            assert viewer.handle_key(KEY_RIGHT) is True
        assert viewer._focus_region is FocusRegion.SIDEBAR

    def test_a_ringed_button_gone_re_seeds_on_the_first(self, viewer: OKFViewer) -> None:
        viewer.handle_key(KEY_ESCAPE)
        first = viewer._bar_nav_buttons()[0]
        viewer._bar_focus_widget = Label()  # no longer one of the bar's buttons
        viewer.handle_key(KEY_RIGHT)
        assert viewer._bar_focus_widget is first

    def test_enter_on_a_ringed_button_gone_does_nothing(self, viewer: OKFViewer) -> None:
        viewer.handle_key(KEY_ESCAPE)
        viewer._bar_focus_widget = Label()
        assert viewer.handle_key(KEY_ENTER) is True
        assert viewer._focus_region is FocusRegion.TOP_BAR

    def test_tab_leaves_the_bar_for_where_it_came_from(self, viewer: OKFViewer) -> None:
        viewer.handle_key(KEY_ESCAPE)
        assert viewer.handle_key(KEY_TAB) is True
        assert viewer._focus_region is FocusRegion.SIDEBAR

    def test_tab_switches_between_the_sidebar_and_the_page(self, viewer: OKFViewer) -> None:
        viewer.handle_key(KEY_TAB)
        assert viewer._focus_region is FocusRegion.PAGE
        viewer.handle_key(KEY_TAB)
        assert viewer._focus_region is FocusRegion.SIDEBAR


class TestPageKeys:
    @pytest.fixture
    def on_page(self, viewer: OKFViewer) -> OKFViewer:
        viewer._set_focus_region(FocusRegion.PAGE)
        return viewer

    def test_an_unmapped_key_is_left_to_the_host(self, on_page: OKFViewer) -> None:
        assert on_page.handle_key(KEY_F) is False

    def test_a_focused_link_scrolled_out_of_view_loses_the_focus(self, on_page: OKFViewer) -> None:
        on_page._set_link_focus(0)
        lbl = on_page._page_links[0][0]
        with patch.object(lbl, "to_window", return_value=(0, -10_000)):
            on_page._prune_offscreen_link_focus()
        assert on_page._focused_link is None

    def test_clearing_a_focus_never_drawn_restores_nothing(self, on_page: OKFViewer) -> None:
        on_page._focused_link = 0
        text = on_page._page_links[0][0].text
        on_page._set_link_focus(None)
        assert on_page._page_links[0][0].text == text
        assert on_page._focused_link is None

    def test_a_footnote_with_no_definition_opens_nothing(self, on_page: OKFViewer) -> None:
        on_page._on_ref(on_page._page_links[0][0], "fn:missing")
        assert on_page._footnote_popup is None

    def test_a_link_that_resolves_nowhere_stays_on_the_page(self, on_page: OKFViewer) -> None:
        on_page._on_ref(on_page._page_links[0][0], "no/such/page.md")
        assert _page(on_page) == "index.md"

    def test_a_footnote_link_that_resolves_nowhere_only_closes_it(self, on_page: OKFViewer) -> None:
        note_label = next(lbl for lbl, ref, _ in on_page._page_links if ref == "fn:note")
        on_page._on_ref(note_label, "fn:note")
        popup_label = on_page._popup_link_label
        assert popup_label is not None
        popup_label.dispatch("on_ref_press", "no/such/page.md")
        assert _page(on_page) == "index.md"

    def test_returning_to_the_page_before_any_page_is_shown(self, on_page: OKFViewer) -> None:
        on_page.history.clear()
        on_page._set_focus_region(FocusRegion.PAGE)
        assert on_page._focus_region is FocusRegion.PAGE


class TestSyncTree:
    def test_a_page_outside_the_bundle_leaves_the_tree_alone(
        self, viewer: OKFViewer, tmp_path: Path
    ) -> None:
        viewer._sync_tree_to(tmp_path / "elsewhere.md")
        assert viewer.tree.selected_node is None

    def test_a_page_in_a_folder_the_tree_lacks_leaves_it_alone(self, viewer: OKFViewer) -> None:
        viewer._sync_tree_to(viewer.bundle / ".hidden" / "x.md")
        assert viewer.tree.selected_node is None


class TestHistory:
    def test_back_at_the_root_without_an_exit_does_nothing(self, viewer: OKFViewer) -> None:
        viewer.go_back()
        assert _page(viewer) == "index.md"

    def test_reset_before_any_page_lands_on_the_home_page(self, viewer: OKFViewer) -> None:
        viewer.history.clear()
        viewer.reset_to()
        assert _page(viewer) == "index.md"
        assert len(viewer.history) == 1

    def test_without_a_state_file_nothing_is_saved(self, viewer: OKFViewer) -> None:
        with patch.object(viewer_module, "save_session_state") as save:
            viewer.save_session()
        save.assert_not_called()


class TestPageAction:
    def test_an_action_without_an_icon_is_a_text_button(self, viewer: OKFViewer) -> None:
        run = MagicMock()
        viewer._set_page_action(PageAction(label="Read Comic", run=run))
        assert viewer.action_btn is not None
        assert viewer.action_btn.text == "Read Comic"

        viewer.action_btn.dispatch("on_release")

        run.assert_called_once_with()

    def test_replacing_the_ringed_action_drops_the_ring(self, viewer: OKFViewer) -> None:
        viewer._set_page_action(PageAction(label="Read Comic", run=MagicMock()))
        assert viewer.action_btn is not None
        viewer._set_bar_focus(viewer.action_btn)

        viewer._set_page_action(None)

        assert viewer._bar_focus_widget is None
        assert viewer.action_btn is None

    def test_with_no_action_running_one_does_nothing(self, viewer: OKFViewer) -> None:
        viewer._set_page_action(None)
        viewer._run_page_action()

    def test_a_white_tint_leaves_an_icon_as_it_is(self) -> None:
        button = MagicMock()
        viewer_module._tint_bar_icon(button, (1.0, 1.0, 1.0, 1.0))
        button.add_widget.assert_not_called()


class TestBackground:
    def test_a_page_with_no_background_clears_the_last(self, bundle: Path) -> None:
        provider = MagicMock()
        provider.background_for.return_value = None
        viewer = OKFViewer(bundle, image_provider=provider)
        try:
            assert viewer.bg_image.source == ""
            assert viewer.bg_image.texture is None
        finally:
            _remove_popups_left_open()


class TestBlocks:
    def test_a_page_that_starts_with_a_table_puts_it_in_a_section(self, viewer: OKFViewer) -> None:
        page = viewer.bundle / "concept" / "table.md"
        page.write_text("| a | b |\n|---|---|\n| 1 | 2 |\n", encoding="utf-8")
        viewer.show_page(page)
        assert viewer.body.children

    def test_a_nested_list_item_is_indented(self, viewer: OKFViewer) -> None:
        page = viewer.bundle / "concept" / "list.md"
        page.write_text("- outer\n  - inner\n", encoding="utf-8")
        with patch.object(viewer_module, "Widget", wraps=viewer_module.Widget) as spacer:
            viewer.show_page(page)
        assert any(c.kwargs.get("height") == 1 for c in spacer.call_args_list)


class TestOverLink:
    def test_a_link_under_the_pointer_in_the_page_counts(self, viewer: OKFViewer) -> None:
        with (
            patch.object(viewer, "get_root_window", return_value=object()),
            patch.object(viewer.body_scroll, "collide_point", return_value=True),
            patch.object(viewer_module, "_ref_under", return_value="concept/a.md"),
        ):
            assert viewer._over_link((10, 10)) is True


class TestStandaloneAppWindow:
    @pytest.fixture
    def app(self, bundle: Path) -> OKFApp:
        app = OKFApp(bundle)
        app.build()
        return app

    def test_on_start_takes_the_titlebar_and_the_keys(self, app: OKFApp) -> None:
        with patch("kivy.core.window.Window") as window:
            window.set_custom_titlebar.return_value = True
            app.on_start()
        assert window.custom_titlebar is True
        window.bind.assert_called_once_with(on_keyboard=app._on_keyboard)

    def test_a_system_refusing_a_custom_title_bar_keeps_its_own(
        self, app: OKFApp, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch("kivy.core.window.Window") as window:
            window.set_custom_titlebar.return_value = False
            app.on_start()
        assert "custom titlebar not allowed" in capsys.readouterr().out

    def test_on_stop_before_a_build_saves_nothing(self, bundle: Path) -> None:
        OKFApp(bundle).on_stop()

    def test_a_key_neither_takes_is_left_to_kivy(self, app: OKFApp) -> None:
        assert app._on_keyboard(None, KEY_F, 0, "", []) is False

    def test_run_starts_the_app(self, bundle: Path) -> None:
        with patch.object(OKFApp, "run") as run:
            viewer_module.run(bundle)
        run.assert_called_once_with()
