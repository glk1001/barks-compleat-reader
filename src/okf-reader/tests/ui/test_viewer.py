# ruff: noqa: SLF001
# cspell:ignore ffcc pytestmark
"""The viewer's paths, on a real viewer over a small bundle.

First what a remote cannot reach: the standalone app's keys, PageUp/PageDown/Home/End,
the mouse's hover and back button, a link inside a footnote, and the search index
failing to build. Then the remote's own paths, which the GUI suite walks in the real app
(``src/barks-reader/tests/gui/test_wiki.py``): here each is one step, so a failure names
the line. A viewer needs a Kivy window, so these are skipped where there is none
(KIVY_HEADLESS_CI); every CI runner draws one now (macOS on Apple's software renderer,
Windows through ANGLE) and runs them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.treeview import TreeViewLabel
from okf_reader.core.actions import PageAction
from okf_reader.core.backgrounds import PageBackground
from okf_reader.core.render import Block, TableBlock
from okf_reader.core.search import SearchHit
from okf_reader.core.session import load_session_state
from okf_reader.core.theme import ViewerThemeSpec
from okf_reader.core.top_bar import TopBarSpec
from okf_reader.ui import page_links
from okf_reader.ui import viewer as viewer_module
from okf_reader.ui.keynav import (
    KEY_DOWN,
    KEY_END,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_F,
    KEY_HOME,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_TAB,
    KEY_UP,
)
from okf_reader.ui.viewer import (
    LAZY_TABLE_MIN_ROWS,
    SEARCH_ERROR_TEXT,
    FocusRegion,
    OKFApp,
    OKFViewer,
)
from okf_reader.ui.widgets import LazyTable
from PIL import Image as PilImage
from viewer_test_helpers import (
    LONG_TABLE_ROWS,
    NEEDS_A_WINDOW,
    Hits,
    clock_patched,
    concept_node,
    hit,
    left_texts,
    node_at,
    open_footnote,
    page_of,
    remove_popups_left_open,
    run_scheduled,
    tree_node,
    window_patched,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from kivy.uix.widget import Widget

pytestmark = NEEDS_A_WINDOW


class TestFootnoteLink:
    def test_a_link_inside_a_footnote_closes_it_and_opens_the_page(self, viewer: OKFViewer) -> None:
        open_footnote(viewer)
        popup = viewer._footnote_popup
        assert popup is not None
        popup_label = viewer._links.popup_label
        assert popup_label is not None
        with patch.object(popup, "dismiss", wraps=popup.dismiss) as dismiss:
            popup_label.dispatch("on_ref_press", "concept/a.md")
        dismiss.assert_called_once()
        assert page_of(viewer) == "concept/a.md"
        assert len(viewer.history) == 2  # noqa: PLR2004

    def test_the_popup_takes_escape_and_holds_the_arrows(self, viewer: OKFViewer) -> None:
        open_footnote(viewer)
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
        assert page_of(viewer) == "concept/a.md"


class TestMouse:
    def test_the_back_button_goes_back(self, viewer: OKFViewer) -> None:
        viewer.show_page(viewer.bundle / "concept" / "a.md")
        assert viewer.on_touch_down(MagicMock(button="mouse4")) is True
        assert page_of(viewer) == "index.md"

    def test_a_press_drops_the_keyboard_focus_out_of_the_bar(self, viewer: OKFViewer) -> None:
        viewer.handle_key(KEY_ESCAPE)  # up to the bar
        assert viewer._focus_region is FocusRegion.TOP_BAR
        touch = MagicMock(button="left", pos=(-1000, -1000))
        viewer.on_touch_down(touch)
        assert viewer._focus_region is FocusRegion.SIDEBAR

    def test_no_link_is_under_the_mouse_when_the_viewer_is_not_on_screen(
        self, viewer: OKFViewer
    ) -> None:
        assert viewer._links.over_link((10, 10)) is False

    def test_an_open_footnote_owns_the_hover(self, viewer: OKFViewer) -> None:
        label = Label()
        viewer._links.popup_label = label
        with (
            patch.object(viewer.body_scroll, "get_root_window", return_value=object()),
            patch.object(page_links, "ref_under", return_value="concept/a.md") as under,
        ):
            assert viewer._links.over_link((10, 10)) is True
        under.assert_called_once_with(label, 10, 10)

    def test_the_cursor_changes_only_on_a_change(self, viewer: OKFViewer) -> None:
        with window_patched() as window:
            viewer._links.set_hand_cursor(over=True)
            viewer._links.set_hand_cursor(over=True)
            viewer._links.set_hand_cursor(over=False)
        assert [c.args[0] for c in window.set_system_cursor.call_args_list] == ["hand", "arrow"]


class TestSearchFocus:
    def test_any_focus_is_logged_a_tap_too(self, viewer: OKFViewer) -> None:
        """A test waits on this line after tapping the box, before it types."""
        with patch.object(viewer_module.trace, "search_focused") as focused:
            viewer._on_search_focus(viewer.search_field, focused=True)  # as a tap focuses it
            viewer._on_search_focus(viewer.search_field, focused=False)
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

    def test_the_worker_logs_a_failed_build_with_its_error(self, viewer: OKFViewer) -> None:
        error = OSError("gone")

        def broken() -> None:
            raise error

        with (
            patch.object(viewer_module, "Clock"),
            patch.object(viewer_module, "trace") as trace,
        ):
            viewer._warm_search_index(broken)
        trace.search_index_building.assert_called_once_with()
        trace.search_index_failed.assert_called_once()
        assert trace.search_index_failed.call_args.args[1] is error
        trace.search_index_built.assert_not_called()

    def test_the_worker_logs_the_build_before_handing_it_to_the_ui(self, viewer: OKFViewer) -> None:
        """A stall on "Searching…" then shows whether the build or the hand-over stopped."""
        calls = MagicMock()
        with (
            patch.object(viewer_module, "Clock", calls.clock),
            patch.object(viewer_module, "trace", calls.trace),
        ):
            viewer._warm_search_index(calls.warm)
        assert [name for name, _args, _kwargs in calls.mock_calls] == [
            "trace.search_index_building",
            "warm",
            "trace.search_index_built",
            "clock.schedule_once",
        ]
        with patch.object(viewer, "_mark_search_ready") as mark:
            calls.clock.schedule_once.call_args.args[0](0)
        mark.assert_called_once_with(failed=False)

    def test_taking_the_outcome_is_logged_with_the_query_typed_meanwhile(
        self, viewer: OKFViewer
    ) -> None:
        viewer.search_field.text = "grotto"
        with patch.object(viewer_module.trace, "search_ready") as ready:
            viewer._mark_search_ready(failed=True)
        ready.assert_called_once_with(failed=True, text="grotto")

    def test_a_provider_that_needs_no_warming_is_ready_at_once(self, viewer: OKFViewer) -> None:
        viewer._searcher = Hits([])  # no `warm` to call
        viewer._on_search_focus(viewer.search_field, focused=True)
        assert viewer._search_ready is True

    def test_warm_search_starts_one_build_however_often_asked(self, viewer: OKFViewer) -> None:
        """The host's call at open and the box's first focus share one build."""
        with patch.object(viewer_module.threading, "Thread") as thread:
            viewer.warm_search()
            viewer._on_search_focus(viewer.search_field, focused=True)
            viewer.warm_search()
        thread.assert_called_once()
        thread.return_value.start.assert_called_once_with()

    def test_a_focus_before_any_warming_starts_the_build(self, viewer: OKFViewer) -> None:
        with patch.object(viewer_module.threading, "Thread") as thread:
            viewer._on_search_focus(viewer.search_field, focused=True)
        assert thread.call_args.kwargs["target"] == viewer._warm_search_index

    def test_losing_focus_starts_no_build(self, viewer: OKFViewer) -> None:
        with patch.object(viewer_module.threading, "Thread") as thread:
            viewer._on_search_focus(viewer.search_field, focused=False)
        thread.assert_not_called()


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
        assert page_of(app._viewer) == "index.md"

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


class TestTableWidget:
    """Which tables the viewer builds lazily: long ones without a link."""

    def _table(self, viewer: OKFViewer, rows: list[str]) -> Widget:
        return viewer._table_widget(TableBlock(rows), viewer.bundle / "index.md").children[0]

    def test_a_long_table_without_links_is_lazy(self, viewer: OKFViewer) -> None:
        assert isinstance(self._table(viewer, LONG_TABLE_ROWS), LazyTable)

    def test_a_short_table_is_built_whole(self, viewer: OKFViewer) -> None:
        table = self._table(viewer, LONG_TABLE_ROWS[: LAZY_TABLE_MIN_ROWS - 1])
        assert not isinstance(table, LazyTable)
        assert len(table.children) == LAZY_TABLE_MIN_ROWS - 1

    def test_a_long_table_with_a_link_is_built_whole(self, viewer: OKFViewer) -> None:
        rows = [*LONG_TABLE_ROWS, "[ref=concept/a.md]A[/ref]"]
        assert not isinstance(self._table(viewer, rows), LazyTable)


class TestTreeKeys:
    """The sidebar's tree on the keys a desktop adds, and the edges of the remote's."""

    def test_home_and_end_go_to_the_first_and_last_node(self, viewer: OKFViewer) -> None:
        concept = concept_node(viewer)
        viewer.tree.toggle_node(concept)  # opening it loads its pages
        nodes = list(viewer.tree.iterate_open_nodes())
        assert [n.text for n in nodes].count("A") == 1

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
        assert page_of(viewer) == "index.md"
        assert viewer._focus_region is FocusRegion.SIDEBAR

    def test_right_on_an_open_empty_folder_stays_put(self, viewer: OKFViewer) -> None:
        concept = concept_node(viewer)
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
        viewer._on_node(concept_node(viewer))
        viewer._on_node(TreeViewLabel())  # neither a page nor a folder
        assert page_of(viewer) == "index.md"

    def test_a_folder_with_an_index_page_opens_it(self, viewer: OKFViewer) -> None:
        (viewer.bundle / "concept" / "index.md").write_text("# Concept\n", encoding="utf-8")
        viewer._on_node(concept_node(viewer))
        assert page_of(viewer) == "concept/index.md"


class TestSidebarWhileSearching:
    def _type(self, viewer: OKFViewer, text: str) -> None:
        viewer.search_field.text = text

    def test_before_the_index_is_ready_it_says_it_is_searching(self, viewer: OKFViewer) -> None:
        self._type(viewer, "grotto")
        assert left_texts(viewer) == ["Searching…"]

    def test_while_waiting_right_crosses_and_the_rest_are_held(self, viewer: OKFViewer) -> None:
        self._type(viewer, "grotto")
        assert viewer.handle_key(KEY_DOWN) is True
        assert viewer.handle_key(KEY_F) is False
        assert viewer.handle_key(KEY_RIGHT) is True
        assert viewer._focus_region is FocusRegion.PAGE

    def test_typing_after_a_failed_build_shows_the_error(self, viewer: OKFViewer) -> None:
        viewer._mark_search_ready(failed=True)
        self._type(viewer, "grotto")
        assert left_texts(viewer) == [SEARCH_ERROR_TEXT]

    def test_typing_once_ready_lists_the_hits(self, viewer: OKFViewer) -> None:
        a_page = viewer.bundle / "concept" / "a.md"
        viewer._searcher = Hits([hit(a_page, "A")])
        viewer._mark_search_ready(failed=False)

        self._type(viewer, "a")

        assert [path for path, _btn in viewer._result_rows] == [a_page]

    def test_a_text_hit_shows_its_snippet_with_the_match_bold(self, viewer: OKFViewer) -> None:
        a_page = viewer.bundle / "concept" / "a.md"
        text_hit = SearchHit(
            path=a_page,
            title="Carl Barks",
            breadcrumb="Topics",
            matched_on="text",
            score=1,
            snippet="…to the artist Glen Brown, Barks",
            snippet_match=(15, 25),
        )
        viewer._searcher = Hits([text_hit, hit(a_page, "Glen [Brown]")])
        viewer._mark_search_ready(failed=False)

        self._type(viewer, "glen brown")

        (_, text_row), (_, title_row) = viewer._result_rows
        assert "…to the artist [b][color=" in text_row.text
        assert "]Glen Brown[/color][/b], Barks" in text_row.text
        assert "Topics" not in text_row.text  # the snippet takes the breadcrumb's line
        assert text_row.height > title_row.height  # room for two lines of snippet
        assert "Glen &bl;Brown&br;" in title_row.text  # markup in a title is escaped

    def test_the_clear_button_puts_the_tree_back(self, viewer: OKFViewer) -> None:
        self._type(viewer, "grotto")
        viewer._clear_search()
        assert viewer.search_field.text == ""
        assert viewer.tree_scroll.parent is viewer._left_body

    def test_clearing_twice_leaves_the_tree_alone(self, viewer: OKFViewer) -> None:
        """An empty box asked again rebuilds nothing: the sidebar's ringed row is kept."""
        self._type(viewer, "grotto")
        viewer._clear_search()
        viewer._sidebar_index = 0  # a row ringed since the tree came back

        with patch.object(viewer._left_body, "clear_widgets") as cleared:
            viewer._clear_search()
            viewer._show_tree_panel()

        cleared.assert_not_called()
        assert viewer._sidebar_index == 0
        assert viewer.tree_scroll.parent is viewer._left_body


class TestResultKeys:
    @pytest.fixture
    def results(self, viewer: OKFViewer) -> OKFViewer:
        hits = [hit(viewer.bundle / f"p{i}.md", f"Page {i}") for i in range(3)]
        viewer._searcher = Hits(hits)
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
        assert page_of(viewer) == "index.md"

    def test_reset_before_any_page_lands_on_the_home_page(self, viewer: OKFViewer) -> None:
        viewer.history.clear()
        viewer.reset_to()
        assert page_of(viewer) == "index.md"
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
        with patch.object(viewer_module.trace, "page_action") as logged:
            viewer._run_page_action()
        logged.assert_not_called()


class TestBackground:
    """The art behind a page is the provider's answer for that page, each time one is shown."""

    @pytest.fixture
    def art(self, tmp_path: Path) -> Path:
        path = tmp_path / "art.png"
        PilImage.new("RGB", (4, 2), "red").save(path)
        return path

    @staticmethod
    def _viewer(
        bundle: Path, home: PageBackground | None, a_page: PageBackground | None = None
    ) -> tuple[OKFViewer, MagicMock]:
        """Open a viewer (on the home page) whose provider answers for each of the two pages."""
        answers = {"index.md": home, "a.md": a_page}
        provider = MagicMock()
        provider.background_for.side_effect = lambda _frontmatter, page: answers.get(page.name)
        return OKFViewer(bundle, image_provider=provider), provider

    def test_a_file_is_shown_by_its_path(self, bundle: Path, art: Path) -> None:
        viewer, provider = self._viewer(bundle, PageBackground(ext=".png", path=art))

        assert viewer.bg_image.source == str(art)
        provider.background_for.assert_called_with({}, bundle / "index.md")

    def test_the_provider_is_given_the_page_s_frontmatter(self, bundle: Path) -> None:
        viewer, provider = self._viewer(bundle, None)

        viewer.show_page(bundle / "concept" / "a.md")

        provider.background_for.assert_called_with({"title": "A"}, bundle / "concept" / "a.md")

    def test_bytes_are_decoded_to_a_texture_with_no_file_named(
        self, bundle: Path, art: Path
    ) -> None:
        viewer, _ = self._viewer(bundle, PageBackground(ext=".png", data=art.read_bytes()))

        assert viewer.bg_image.source == ""
        assert viewer.bg_image.texture.size == (4, 2)

    def test_a_page_with_no_background_clears_the_last(self, bundle: Path, art: Path) -> None:
        viewer, _ = self._viewer(bundle, PageBackground(ext=".png", data=art.read_bytes()))
        assert viewer.bg_image.texture is not None

        viewer.show_page(bundle / "concept" / "a.md")

        assert viewer.bg_image.source == ""
        assert viewer.bg_image.texture is None

    def test_bytes_after_a_file_drop_the_file_s_name(self, bundle: Path, art: Path) -> None:
        """Or Kivy would load the old file again over the new texture."""
        viewer, _ = self._viewer(
            bundle,
            PageBackground(ext=".png", path=art),
            PageBackground(ext=".png", data=art.read_bytes()),
        )
        assert viewer.bg_image.source == str(art)

        viewer.show_page(bundle / "concept" / "a.md")

        assert viewer.bg_image.source == ""
        assert viewer.bg_image.texture.size == (4, 2)


class TestBlocks:
    def test_a_page_that_starts_with_a_table_puts_it_in_a_section(self, viewer: OKFViewer) -> None:
        page = viewer.bundle / "concept" / "table.md"
        page.write_text("| a | b |\n|---|---|\n| 1 | 2 |\n", encoding="utf-8")
        viewer.show_page(page)

        (section,) = viewer.body.children  # one banded box, as a run of text gets
        assert isinstance(section, BoxLayout)
        assert [type(w) for w in section.walk(restrict=True) if isinstance(w, Label)]
        assert not any(isinstance(w, Label) for w in viewer.body.children)

    def test_a_nested_list_item_is_indented(self, viewer: OKFViewer) -> None:
        page = viewer.bundle / "concept" / "list.md"
        page.write_text("- outer\n  - inner\n", encoding="utf-8")
        with patch.object(viewer_module, "Widget", wraps=viewer_module.Widget) as spacer:
            viewer.show_page(page)
        assert any(c.kwargs.get("height") == 1 for c in spacer.call_args_list)


class TestStandaloneAppWindow:
    @pytest.fixture
    def app(self, bundle: Path) -> OKFApp:
        app = OKFApp(bundle)
        app.build()
        return app

    def test_on_start_takes_the_titlebar_and_the_keys(self, app: OKFApp) -> None:
        with window_patched() as window:
            window.set_custom_titlebar.return_value = True
            app.on_start()
        assert window.custom_titlebar is True
        window.bind.assert_called_once_with(on_keyboard=app._on_keyboard)

    def test_a_system_refusing_a_custom_title_bar_keeps_its_own(
        self, app: OKFApp, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with window_patched() as window:
            window.set_custom_titlebar.return_value = False
            app.on_start()
        assert "custom titlebar not allowed" in capsys.readouterr().out

    def test_on_stop_before_a_build_saves_nothing(self, bundle: Path, tmp_path: Path) -> None:
        state_path = tmp_path / "session.json"
        with patch.object(viewer_module, "save_session_state") as save:
            OKFApp(bundle, state_path=state_path).on_stop()
        save.assert_not_called()
        assert not state_path.exists()

    def test_a_key_neither_takes_is_left_to_kivy(self, app: OKFApp) -> None:
        assert app._on_keyboard(None, KEY_F, 0, "", []) is False

    def test_run_starts_the_app(self, bundle: Path) -> None:
        with patch.object(OKFApp, "run") as run:
            viewer_module.run(bundle)
        run.assert_called_once_with()


class TestContrast:
    """The toggle darkens the article panel alone: the sidebar's scrim stays put."""

    def test_down_darkens_the_article_and_up_restores_it(self, viewer: OKFViewer) -> None:
        viewer.contrast_btn.state = "down"
        assert viewer._pane_scrim_color.a == pytest.approx(
            viewer_module.READING_PANE_SCRIM_CONTRAST_ALPHA
        )
        viewer.contrast_btn.state = "normal"
        assert viewer._pane_scrim_color.a == pytest.approx(viewer_module.READING_PANE_SCRIM[3])

    def test_the_sidebar_scrim_ignores_the_toggle(self, viewer: OKFViewer) -> None:
        assert viewer._sidebar_scrim_color.a == pytest.approx(viewer_module.SIDEBAR_SCRIM[3])
        viewer.contrast_btn.state = "down"
        assert viewer._sidebar_scrim_color.a == pytest.approx(viewer_module.SIDEBAR_SCRIM[3])


class TestTheReadingColumnsCap:
    """The body column fills its pane up to a cap an embedding app may move."""

    def test_the_column_fills_a_narrow_pane_and_stops_at_the_cap(self, viewer: OKFViewer) -> None:
        narrow = 500
        viewer.body_scroll.width = narrow
        assert viewer.body.width == narrow
        viewer.body_scroll.width = 5000
        assert viewer.body.width == viewer_module.dp(viewer_module.BODY_MAX_WIDTH)

    def test_a_wider_cap_widens_the_column_at_once(self, viewer: OKFViewer) -> None:
        viewer.body_scroll.width = 5000
        viewer.set_body_max_width(880)
        assert viewer.body.width == viewer_module.dp(880)
        viewer.set_body_max_width(viewer_module.BODY_MAX_WIDTH)
        assert viewer.body.width == viewer_module.dp(viewer_module.BODY_MAX_WIDTH)


class TestTheContentPadding:
    """The panels sit CONTENT_PADDING in from every side until an app moves them."""

    def test_the_default_and_an_apps_padding(self, viewer: OKFViewer) -> None:
        assert list(viewer._content.padding) == [viewer_module.CONTENT_PADDING] * 4
        viewer.set_content_padding(40, 0, 8, 2)
        assert list(viewer._content.padding) == [40, 0, 8, 2]


class TestTheSearchFieldsBorder:
    """A faint outline keeps to the search field's edges as it moves and resizes."""

    def test_the_outline_follows_the_field(self, viewer: OKFViewer) -> None:
        field = viewer.search_field
        field.pos = (10, 20)
        field.size = (200, 32)
        lines = [i for i in field.canvas.after.children if isinstance(i, viewer_module.Line)]
        assert len(lines) == 1
        assert list(lines[0].points) == [10, 20, 210, 20, 210, 52, 10, 52]
        assert lines[0].close
        assert lines[0].width == viewer_module.SEARCH_FIELD_BORDER_WIDTH


class TestTheClearButtonInsideTheField:
    """The field spans the sidebar; the clear button sits over its right end."""

    def test_the_field_fills_the_row(self, viewer: OKFViewer) -> None:
        field = viewer.search_field
        row = field.parent
        row.pos, row.size = (8, 720), (300, 32)
        row.do_layout()
        assert (*field.pos, *field.size) == (*row.pos, *row.size)

    def test_text_shows_the_button_at_the_fields_right_end(self, viewer: OKFViewer) -> None:
        row = viewer.search_field.parent
        row.pos, row.size = (8, 720), (300, 32)
        viewer.search_field.text = "duck"
        row.do_layout()
        btn = viewer.search_clear_btn
        assert btn.width == viewer_module.dp(viewer_module.SEARCH_CLEAR_BTN_WIDTH)
        assert (btn.right, btn.y) == (row.right, row.y)
        assert not btn.disabled

    def test_hidden_the_button_takes_no_touches_from_the_field(self, viewer: OKFViewer) -> None:
        viewer.search_field.text = "duck"
        viewer.search_field.text = ""
        btn = viewer.search_clear_btn
        assert btn.width == 0
        assert btn.disabled


class TestTheCentredBlock:
    """Centred, the sidebar and the capped column sit with even art either side."""

    def _lay_out(self, viewer: OKFViewer, width: float) -> None:
        viewer.size = (width, 800)
        viewer._content.size = (width, 700)
        viewer._content.do_layout()  # the scroll's new width refits the column

    def test_the_pair_is_centred_with_the_sidebars_share_kept(self, viewer: OKFViewer) -> None:
        viewer.set_body_max_width(880)
        viewer.set_centre_block(True)
        self._lay_out(viewer, 1876)
        sidebar = viewer._left_column
        assert sidebar.width == pytest.approx(1876 * viewer_module.TREE_PANEL_WIDTH)
        pane = viewer.body_scroll
        assert sidebar.x == pytest.approx(viewer._content.right - pane.right)
        assert viewer.body.width == viewer_module.dp(880)

    def test_centred_the_pane_is_the_columns_width(self, viewer: OKFViewer) -> None:
        """So its scroll bar sits at the column's edge, not a margin away."""
        viewer.set_body_max_width(880)
        viewer.set_centre_block(True)
        self._lay_out(viewer, 1876)
        assert viewer.body_scroll.width == pytest.approx(viewer_module.dp(880))

    def test_too_narrow_to_centre_it_keeps_the_plain_layout(self, viewer: OKFViewer) -> None:
        viewer.set_content_padding(40, 0, 8, 0)
        viewer.set_centre_block(True)
        self._lay_out(viewer, 1000)
        assert viewer._left_column.size_hint_x == viewer_module.TREE_PANEL_WIDTH
        assert list(viewer._content.padding) == [40, 0, 8, 0]

    def test_off_restores_the_plain_layout(self, viewer: OKFViewer) -> None:
        viewer.set_centre_block(True)
        self._lay_out(viewer, 1876)
        viewer.set_centre_block(False)
        assert viewer._left_column.size_hint_x == viewer_module.TREE_PANEL_WIDTH
        assert list(viewer._content.padding) == [viewer_module.CONTENT_PADDING] * 4


class TestContrastSetByTheApp:
    def test_set_contrast_presses_the_toggle_and_resets_the_scrims(self, viewer: OKFViewer) -> None:
        viewer.set_contrast(True)
        assert viewer.contrast_btn.state == "down"
        assert viewer._pane_scrim_color.a == viewer_module.READING_PANE_SCRIM_CONTRAST_ALPHA
        viewer.set_contrast(False)
        assert viewer.contrast_btn.state == "normal"
        assert viewer._pane_scrim_color.a == viewer_module.READING_PANE_SCRIM[3]


class TestTheReadingPaneScrim:
    """The scrim behind the column is the pane's height, the column's width."""

    def test_the_scrim_reaches_the_panes_bottom_under_a_short_page(self, viewer: OKFViewer) -> None:
        viewer.body_scroll.pos = (300, 50)
        viewer.body_scroll.size = (1000, 900)
        viewer.body.height = 120  # A short page.
        viewer.body.x = 40  # An offset in the pane: its content is kept at the origin.
        assert viewer._pane_scrim_rect.pos == (340, 50)
        assert viewer._pane_scrim_rect.size == (viewer.body.width, 900)

    def test_the_scrim_is_the_columns_width(self, viewer: OKFViewer) -> None:
        viewer.body_scroll.width = 5000
        assert viewer._pane_scrim_rect.size[0] == viewer_module.dp(viewer_module.BODY_MAX_WIDTH)


class TestTheSideScrims:
    """The art beside the panels is dimmed a little; the panels' own scrims are not changed."""

    def test_the_left_strip_runs_from_the_rows_edge_to_the_sidebar(self, viewer: OKFViewer) -> None:
        viewer._content.pos = (0, 20)
        viewer._content.size = (2000, 900)
        viewer._left_column.x = 300

        assert viewer._left_side_scrim.pos == (0, 20)
        assert viewer._left_side_scrim.size == (300, 900)

    def test_the_right_strip_starts_at_the_columns_edge(self, viewer: OKFViewer) -> None:
        viewer._content.pos = (0, 20)
        viewer._content.size = (2000, 900)
        viewer.body_scroll.x = 500
        viewer.body.x = 0
        viewer.body.width = 760

        assert viewer._right_side_scrim.pos == (1260, 20)
        assert viewer._right_side_scrim.size == (740, 900)

    def test_no_room_at_a_side_draws_nothing_there(self, viewer: OKFViewer) -> None:
        viewer._content.pos = (0, 0)
        viewer._content.size = (1000, 900)
        viewer._left_column.x = 0
        viewer.body_scroll.x = 300
        viewer.body.width = 800

        assert viewer._left_side_scrim.size[0] == 0
        assert viewer._right_side_scrim.size[0] == 0

    def test_the_side_scrims_are_light(self) -> None:
        assert viewer_module.SIDE_SCRIM[3] < viewer_module.READING_PANE_SCRIM[3]


class TestTheIndexReadyWithAQueryTyped:
    def test_a_query_typed_during_the_build_gets_its_hits_when_it_ends(
        self, viewer: OKFViewer
    ) -> None:
        """Or it stays on "Searching…" until something more is typed."""
        a_page = viewer.bundle / "concept" / "a.md"
        viewer._searcher = Hits([hit(a_page, "A")])
        viewer.search_field.text = "a"
        assert left_texts(viewer) == ["Searching…"]

        viewer._mark_search_ready(failed=False)

        assert [path for path, _btn in viewer._result_rows] == [a_page]

    def test_with_nothing_typed_the_tree_stays(self, viewer: OKFViewer) -> None:
        viewer._searcher = Hits([])

        viewer._mark_search_ready(failed=False)

        assert viewer.tree_scroll.parent is viewer._left_body

    def test_a_query_nothing_matches_says_so(self, viewer: OKFViewer) -> None:
        viewer._searcher = Hits([])
        viewer._mark_search_ready(failed=False)

        viewer.search_field.text = "zzzz"

        assert left_texts(viewer) == ["No matches"]
        assert viewer._result_rows == []

    def test_a_title_hit_s_row_names_where_the_page_is(self, viewer: OKFViewer) -> None:
        a_page = viewer.bundle / "concept" / "a.md"
        hit = SearchHit(path=a_page, title="A", breadcrumb="Concept", matched_on="title", score=1)
        viewer._searcher = Hits([hit])
        viewer._mark_search_ready(failed=False)

        viewer.search_field.text = "a"

        ((_path, row),) = viewer._result_rows
        assert "A" in row.text
        assert "Concept" in row.text


class TestEscapeSearch:
    """What a host asks before its own Back: an active search takes the Escape."""

    def test_a_query_is_cleared_and_the_escape_taken(self, viewer: OKFViewer) -> None:
        viewer.search_field.text = "grotto"
        with patch.object(viewer_module.trace, "search_cleared") as cleared:
            assert viewer.escape_search() is True

        assert viewer.search_field.text == ""
        assert viewer.search_field.focus is False
        cleared.assert_called_once_with()

    def test_an_idle_search_leaves_the_escape_to_the_host(self, viewer: OKFViewer) -> None:
        with patch.object(viewer_module.trace, "search_cleared") as cleared:
            assert viewer.escape_search() is False

        cleared.assert_not_called()


class TestHistoryRoot:
    def test_back_at_the_root_leaves_the_reader(self, bundle: Path) -> None:
        on_exit = MagicMock()
        viewer = OKFViewer(bundle, on_exit=on_exit)

        viewer.go_back()

        on_exit.assert_called_once_with()
        assert page_of(viewer) == "index.md"

    def test_back_from_a_second_page_returns_to_the_first(self, bundle: Path) -> None:
        on_exit = MagicMock()
        viewer = OKFViewer(bundle, on_exit=on_exit)
        viewer.show_page(bundle / "concept" / "a.md")

        viewer.go_back()

        on_exit.assert_not_called()
        assert page_of(viewer) == "index.md"

    def test_a_reset_keeps_the_page_showing_as_the_new_root(self, bundle: Path) -> None:
        """Re-entered, the reader's Back leaves it and does not walk the last visit."""
        on_exit = MagicMock()
        viewer = OKFViewer(bundle, on_exit=on_exit)
        viewer.show_page(bundle / "concept" / "a.md")

        viewer.reset_to(None)

        assert [e.path for e in viewer.history] == [bundle / "concept" / "a.md"]
        viewer.go_back()
        on_exit.assert_called_once_with()

    def test_a_reset_to_a_page_roots_the_history_there(self, bundle: Path) -> None:
        viewer = OKFViewer(bundle)

        viewer.reset_to(bundle / "concept" / "a.md")

        assert [e.path for e in viewer.history] == [bundle / "concept" / "a.md"]


def test_run_hands_every_option_to_the_app(bundle: Path) -> None:
    options = {
        "image_provider": MagicMock(),
        "table_rewriter": MagicMock(),
        "start_page": bundle / "concept" / "a.md",
        "action_provider": MagicMock(),
        "top_bar": MagicMock(),
        "state_path": bundle / "session.json",
        "search_provider": MagicMock(),
    }
    with patch.object(viewer_module, "OKFApp") as app:
        viewer_module.run(bundle, **options)

    app.assert_called_once_with(bundle, **options)
    app.return_value.run.assert_called_once_with()


# What follows is the remote's paths again, at the size of a unit test: the GUI suite
# walks them in the real app, and these say which line broke when it fails.

TINT = (0.9, 0.8, 0.5, 1.0)


class TestAnIconBar:
    """A host's bar: icon buttons tinted to its theme, and its icon as the way home."""

    @pytest.fixture
    def icons(self, tmp_path: Path) -> dict[str, Path]:
        paths = {}
        for name in ("home", "back", "on", "off", "close", "action"):
            paths[name] = tmp_path / f"{name}.png"
            PilImage.new("RGBA", (8, 8), (255, 255, 255, 255)).save(paths[name])
        return paths

    @pytest.fixture
    def themed(self, bundle: Path, icons: dict[str, Path]) -> Iterator[OKFViewer]:
        self.on_close = MagicMock()
        spec = TopBarSpec(
            icon_path=icons["home"],
            back_icon_path=icons["back"],
            contrast_on_icon_path=icons["on"],
            contrast_off_icon_path=icons["off"],
            close_icon_path=icons["close"],
            on_close=self.on_close,
        )
        okf_viewer = OKFViewer(bundle, top_bar=spec, theme=ViewerThemeSpec(icon_tint=TINT))
        yield okf_viewer
        remove_popups_left_open()

    @staticmethod
    def _overlay(button: Widget) -> Image:
        return next(w for w in button.children if isinstance(w, Image) and w.color == list(TINT))

    def test_each_button_wears_its_icon(self, themed: OKFViewer, icons: dict[str, Path]) -> None:
        assert themed.back_btn.icon == str(icons["back"])
        assert themed.contrast_btn.icon == str(icons["on"])
        assert themed._quit_btn.icon == str(icons["close"])

    def test_the_contrast_icon_shows_what_pressing_will_do(
        self, themed: OKFViewer, icons: dict[str, Path]
    ) -> None:
        themed.contrast_btn.state = "down"
        assert themed.contrast_btn.icon == str(icons["off"])
        themed.contrast_btn.state = "normal"
        assert themed.contrast_btn.icon == str(icons["on"])

    def test_a_tinted_copy_lies_over_each_glyph_inside_its_inset(self, themed: OKFViewer) -> None:
        for button in (themed.back_btn, themed.contrast_btn, themed._quit_btn):
            button.pos, button.size = (200, 10), (48, 40)
            overlay = self._overlay(button)
            assert overlay.source == button.icon
            assert tuple(overlay.pos) == (200 + dp(4), 10 + dp(4))
            assert tuple(overlay.size) == (48 - dp(8), 40 - dp(8))

    def test_the_tinted_copy_follows_the_contrast_icons_swap(
        self, themed: OKFViewer, icons: dict[str, Path]
    ) -> None:
        themed.contrast_btn.state = "down"
        assert self._overlay(themed.contrast_btn).source == str(icons["off"])

    def test_the_quit_button_does_what_the_host_asked(self, themed: OKFViewer) -> None:
        themed._quit_btn.dispatch("on_release")
        self.on_close.assert_called_once_with()

    def test_the_bars_icon_dims_while_pressed_and_goes_home(self, themed: OKFViewer) -> None:
        home = themed._bar_home_btn
        assert home is not None
        icon = next(w for w in home.parent.children if isinstance(w, Image))
        home.parent.size = (70, 40)
        assert tuple(icon.size) == (70 - dp(8), 40 - dp(8))
        themed.show_page(themed.bundle / "concept" / "a.md")

        home.state = "down"
        assert icon.opacity == 0.5  # noqa: PLR2004
        home.state = "normal"
        assert icon.opacity == 1.0
        home.dispatch("on_release")

        assert page_of(themed) == "index.md"
        assert home in themed._bar_nav_buttons()

    def test_a_page_action_with_an_icon_is_a_tinted_icon_button(
        self, themed: OKFViewer, icons: dict[str, Path]
    ) -> None:
        run = MagicMock()
        themed._set_page_action(PageAction(label="Read Comic", run=run, icon_path=icons["action"]))
        assert themed.action_btn is not None
        assert themed.action_btn.icon == str(icons["action"])
        assert self._overlay(themed.action_btn).source == str(icons["action"])

        themed.action_btn.dispatch("on_release")

        run.assert_called_once_with()


class TestOneOpenBranch:
    """Opening a folder closes every open one that is not on the way to it."""

    def test_opening_another_folder_closes_the_open_one_and_all_inside_it(
        self, deep_bundle: Path
    ) -> None:
        viewer = OKFViewer(deep_bundle)
        other = tree_node(viewer, "Other")
        viewer.tree.toggle_node(other)
        deep = tree_node(viewer, "Deep")
        viewer.tree.toggle_node(deep)
        assert (other.is_open, deep.is_open) == (True, True)  # the inner one closes neither

        viewer.tree.toggle_node(concept_node(viewer))

        assert (other.is_open, deep.is_open) == (False, False)
        assert concept_node(viewer).is_open

    def test_a_branch_closing_is_logged_and_loads_nothing(
        self, viewer: OKFViewer, kivy_log: list[str]
    ) -> None:
        concept = concept_node(viewer)
        viewer.tree.toggle_node(concept)
        pages = list(concept.nodes)

        viewer.tree.toggle_node(concept)

        assert list(concept.nodes) == pages
        assert any("Concept" in line for line in kivy_log[-1:])

    def test_a_page_node_opens_its_page(self, viewer: OKFViewer) -> None:
        viewer.tree.toggle_node(concept_node(viewer))
        viewer._on_node(tree_node(viewer, "A"))
        assert page_of(viewer) == "concept/a.md"

    def test_a_selection_made_to_mirror_the_page_opens_nothing(self, viewer: OKFViewer) -> None:
        viewer.tree.toggle_node(concept_node(viewer))
        viewer._syncing_tree = True
        viewer._on_node(tree_node(viewer, "A"))
        assert page_of(viewer) == "index.md"


class TestTheRemoteInTheTree:
    """Up, Down, Left, Right and Enter on the contents tree."""

    def test_down_starts_on_the_first_node_and_up_on_the_last(self, deep_bundle: Path) -> None:
        viewer = OKFViewer(deep_bundle)
        nodes = list(viewer.tree.iterate_open_nodes())

        viewer.handle_key(KEY_DOWN)
        assert viewer.tree.selected_node is nodes[0]

        viewer.tree.deselect_node()
        viewer.handle_key(KEY_UP)
        assert viewer.tree.selected_node is nodes[-1]

    def test_down_steps_to_the_next_node_and_stops_at_the_last(self, deep_bundle: Path) -> None:
        viewer = OKFViewer(deep_bundle)
        nodes = list(viewer.tree.iterate_open_nodes())
        viewer.handle_key(KEY_DOWN)

        viewer.handle_key(KEY_DOWN)
        assert viewer.tree.selected_node is nodes[1]
        viewer.handle_key(KEY_DOWN)
        assert viewer.tree.selected_node is nodes[1]
        viewer.handle_key(KEY_UP)
        assert viewer.tree.selected_node is nodes[0]

    def test_up_from_the_first_node_goes_to_the_search_box(self, viewer: OKFViewer) -> None:
        viewer.handle_key(KEY_DOWN)
        assert viewer.handle_key(KEY_UP) is True
        assert viewer.search_focused

    def test_right_opens_a_folder_then_steps_in_then_opens_the_page(
        self, viewer: OKFViewer
    ) -> None:
        concept = concept_node(viewer)
        viewer._focus_tree_node(concept)

        with clock_patched() as clock:
            viewer.handle_key(KEY_RIGHT)
            assert concept.is_open
            with patch.object(viewer, "_scroll_tree_node_into_view") as scrolled:
                run_scheduled(clock)
            scrolled.assert_called_once_with(concept)
        assert viewer.tree.selected_node is concept

        viewer.handle_key(KEY_RIGHT)
        assert viewer.tree.selected_node is tree_node(viewer, "A")

        viewer.handle_key(KEY_RIGHT)
        assert page_of(viewer) == "concept/a.md"
        assert viewer._focus_region is FocusRegion.PAGE

    def test_left_goes_up_to_the_folder_then_closes_it_then_stays(self, viewer: OKFViewer) -> None:
        concept = concept_node(viewer)
        viewer.tree.toggle_node(concept)
        viewer._focus_tree_node(tree_node(viewer, "A"))

        viewer.handle_key(KEY_LEFT)
        assert viewer.tree.selected_node is concept
        assert concept.is_open

        viewer.handle_key(KEY_LEFT)
        assert not concept.is_open

        viewer.handle_key(KEY_LEFT)  # a closed folder at the top: nowhere further left
        assert viewer.tree.selected_node is concept
        assert viewer._focus_region is FocusRegion.SIDEBAR

    def test_enter_opens_a_folder_and_its_index_then_closes_it(self, viewer: OKFViewer) -> None:
        (viewer.bundle / "concept" / "index.md").write_text("# Concept\n", encoding="utf-8")
        concept = concept_node(viewer)
        viewer._focus_tree_node(concept)

        viewer.handle_key(KEY_ENTER)
        assert concept.is_open
        assert page_of(viewer) == "concept/index.md"
        assert viewer._focus_region is FocusRegion.SIDEBAR

        viewer._focus_tree_node(concept)
        viewer.handle_key(KEY_ENTER)
        assert not concept.is_open

    def test_right_on_an_open_folder_with_nothing_in_it_stays_put(self, viewer: OKFViewer) -> None:
        concept = concept_node(viewer)
        viewer._focus_tree_node(concept)
        empty = TreeViewLabel(is_leaf=False, is_open=True)

        viewer._tree_expand(empty)

        assert viewer.tree.selected_node is concept
        assert viewer._focus_region is FocusRegion.SIDEBAR

    def test_enter_on_a_page_opens_it_and_crosses_to_it(self, viewer: OKFViewer) -> None:
        viewer.tree.toggle_node(concept_node(viewer))
        viewer._focus_tree_node(tree_node(viewer, "A"))

        viewer.handle_key(KEY_ENTER)

        assert page_of(viewer) == "concept/a.md"
        assert viewer._focus_region is FocusRegion.PAGE


class TestTheTreeScrolledToANode:
    """A node is put a quarter of the way down the panel, once the tree has settled."""

    @pytest.fixture
    def tall(self, viewer: OKFViewer) -> OKFViewer:
        viewer.tree_scroll.height = 100
        viewer.tree.height = 1000
        viewer.tree.y = 0
        return viewer

    @pytest.mark.parametrize(
        ("node_top", "expected"),
        [
            pytest.param(500, (500 - 100 + 25) / 900, id="a-quarter-down"),
            pytest.param(1000, 1.0, id="the-first-row"),
            pytest.param(960, 1.0, id="within-a-row-of-the-top-snaps-to-it"),
            pytest.param(10, 0.0, id="the-last-row"),
        ],
    )
    def test_the_node_sits_a_quarter_of_the_way_down(
        self, tall: OKFViewer, node_top: int, expected: float
    ) -> None:
        tall.tree_scroll.scroll_y = 0.5
        tall._scroll_tree_node_into_view(node_at(node_top))
        assert tall.tree_scroll.scroll_y == pytest.approx(expected)

    def test_a_tree_that_fits_is_left_where_it_is(self, tall: OKFViewer) -> None:
        tall.tree.height = 80
        tall.tree_scroll.scroll_y = 0.5
        tall._scroll_tree_node_into_view(node_at(40))
        assert tall.tree_scroll.scroll_y == 0.5  # noqa: PLR2004

    def test_it_waits_for_two_frames_to_agree(self, tall: OKFViewer) -> None:
        node = node_at(500)
        with clock_patched() as clock, patch.object(tall, "_scroll_tree_node_into_view") as scroll:
            tall._reveal_tree_node_when_settled(node)
            run_scheduled(clock)  # the first look: nothing to compare with
            node.top = 400  # still moving
            run_scheduled(clock)
            scroll.assert_not_called()
            run_scheduled(clock)  # the same twice

            scroll.assert_called_once_with(node)
            clock.schedule_once.assert_not_called()

    def test_a_tree_that_never_settles_is_scrolled_after_its_frame_limit(
        self, tall: OKFViewer
    ) -> None:
        node = node_at(0)
        with clock_patched() as clock, patch.object(tall, "_scroll_tree_node_into_view") as scroll:
            tall._reveal_tree_node_when_settled(node)
            for _ in range(viewer_module._TREE_REVEAL_MAX_FRAMES):
                node.top += 1
                run_scheduled(clock)
            scroll.assert_not_called()
            node.top += 1
            run_scheduled(clock)

            scroll.assert_called_once_with(node)

    def test_the_tree_coming_back_from_a_search_shows_the_pages_node(
        self, viewer: OKFViewer
    ) -> None:
        viewer.show_page(viewer.bundle / "concept" / "a.md")
        selected = viewer.tree.selected_node
        assert selected is not None
        viewer._searcher = Hits([hit(viewer.bundle / "index.md", "Home")])
        viewer._mark_search_ready(failed=False)
        viewer.search_field.text = "home"

        with (
            clock_patched() as clock,
            patch.object(viewer, "_scroll_tree_node_into_view") as scroll,
        ):
            viewer.search_field.text = ""
            run_scheduled(clock)

        scroll.assert_called_with(selected)
        assert viewer.tree_scroll.parent is viewer._left_body


class TestTheRemoteInTheSearchBox:
    def test_down_leaves_the_box_for_the_sidebar(self, viewer: OKFViewer) -> None:
        viewer.focus_search()

        assert viewer.handle_key(KEY_DOWN) is True

        assert not viewer.search_focused
        assert viewer._focus_region is FocusRegion.SIDEBAR

    def test_the_box_keeps_every_other_key(self, viewer: OKFViewer) -> None:
        viewer.focus_search()
        assert viewer.handle_key(KEY_LEFT) is False
        assert viewer.search_focused

    def test_enter_opens_the_top_hit_and_gives_the_keys_back(self, viewer: OKFViewer) -> None:
        top, second = viewer.bundle / "concept" / "a.md", viewer.bundle / "index.md"
        viewer._searcher = Hits([hit(top, "A"), hit(second, "Home")])
        viewer._mark_search_ready(failed=False)
        viewer.focus_search()
        viewer.search_field.text = "a"

        viewer.search_field.dispatch("on_text_validate")

        assert page_of(viewer) == "concept/a.md"
        assert not viewer.search_focused
        assert len(viewer._result_rows) == 2  # noqa: PLR2004 — the list stays for the next

    def test_enter_with_no_hits_opens_nothing(self, viewer: OKFViewer) -> None:
        viewer._searcher = Hits([])
        viewer._mark_search_ready(failed=False)
        viewer.search_field.text = "nothing"
        viewer.search_field.dispatch("on_text_validate")
        assert page_of(viewer) == "index.md"

    def test_enter_before_the_index_is_ready_opens_nothing(self, viewer: OKFViewer) -> None:
        viewer._searcher = Hits([hit(viewer.bundle / "concept" / "a.md", "A")])
        viewer.search_field.text = "a"
        viewer.search_field.dispatch("on_text_validate")
        assert page_of(viewer) == "index.md"


class TestTheRemoteInTheResults:
    @pytest.fixture
    def results(self, viewer: OKFViewer) -> OKFViewer:
        pages = [viewer.bundle / "index.md", viewer.bundle / "concept" / "a.md"]
        viewer._searcher = Hits([hit(page, page.stem) for page in pages])
        viewer._mark_search_ready(failed=False)
        viewer.search_field.text = "page"
        viewer._active_result_path = None
        viewer._set_focus_region(FocusRegion.SIDEBAR)
        viewer._clear_result_focus()
        return viewer

    def test_down_starts_on_the_top_hit_and_steps_from_there(self, results: OKFViewer) -> None:
        results.handle_key(KEY_DOWN)
        assert results._sidebar_index == 0
        results.handle_key(KEY_DOWN)
        assert results._sidebar_index == 1
        results.handle_key(KEY_DOWN)
        assert results._sidebar_index == 1  # the last row: no wrap
        results.handle_key(KEY_UP)
        assert results._sidebar_index == 0

    def test_it_starts_on_the_row_of_the_page_showing(self, results: OKFViewer) -> None:
        results._active_result_path = results.bundle / "concept" / "a.md"
        results.handle_key(KEY_DOWN)
        assert results._sidebar_index == 1

    def test_up_from_the_top_hit_goes_back_to_the_box(self, results: OKFViewer) -> None:
        results.handle_key(KEY_DOWN)
        assert results.handle_key(KEY_UP) is True
        assert results.search_focused
        assert results._sidebar_index is None

    def test_enter_opens_the_ringed_hit_and_keeps_the_list(self, results: OKFViewer) -> None:
        results.handle_key(KEY_END)

        assert results.handle_key(KEY_ENTER) is True

        assert page_of(results) == "concept/a.md"
        assert len(results._result_rows) == 2  # noqa: PLR2004

    def test_enter_with_no_row_ringed_opens_nothing(self, results: OKFViewer) -> None:
        assert results.handle_key(KEY_ENTER) is True
        assert page_of(results) == "index.md"

    def test_right_crosses_to_the_page(self, results: OKFViewer) -> None:
        assert results.handle_key(KEY_RIGHT) is True
        assert results._focus_region is FocusRegion.PAGE


class TestEscape:
    def test_it_clears_a_search_before_it_goes_to_the_bar(self, viewer: OKFViewer) -> None:
        viewer.search_field.text = "a"

        assert viewer.handle_key(KEY_ESCAPE) is True

        assert viewer.search_field.text == ""
        assert viewer._focus_region is not FocusRegion.TOP_BAR

    def test_a_second_escape_drops_out_of_the_bar_to_where_it_came_from(
        self, viewer: OKFViewer
    ) -> None:
        viewer._set_focus_region(FocusRegion.PAGE)
        viewer.handle_key(KEY_ESCAPE)
        assert viewer._focus_region is FocusRegion.TOP_BAR

        viewer.handle_key(KEY_ESCAPE)

        assert viewer._focus_region is FocusRegion.PAGE


class TestTheRemoteOnTheBar:
    @pytest.fixture
    def on_bar(self, viewer: OKFViewer) -> OKFViewer:
        viewer.handle_key(KEY_ESCAPE)
        return viewer

    def test_right_and_left_walk_the_buttons_and_wrap(self, viewer: OKFViewer) -> None:
        viewer.show_page(viewer.bundle / "concept" / "a.md")  # Back comes alive: three buttons
        viewer.handle_key(KEY_ESCAPE)
        back, contrast, close = viewer._bar_nav_buttons()
        assert viewer._bar_focus_widget is back

        viewer.handle_key(KEY_RIGHT)
        assert viewer._bar_focus_widget is contrast
        viewer.handle_key(KEY_LEFT)
        viewer.handle_key(KEY_LEFT)
        assert viewer._bar_focus_widget is close
        viewer.handle_key(KEY_RIGHT)
        assert viewer._bar_focus_widget is back

    def test_it_starts_on_back_when_there_is_a_page_to_go_back_to(self, viewer: OKFViewer) -> None:
        viewer.show_page(viewer.bundle / "concept" / "a.md")
        viewer.handle_key(KEY_ESCAPE)
        assert viewer._bar_focus_widget is viewer.back_btn

    def test_enter_presses_the_ringed_button_and_leaves_the_bar(self, on_bar: OKFViewer) -> None:
        assert on_bar._bar_focus_widget is on_bar.contrast_btn

        assert on_bar.handle_key(KEY_ENTER) is True

        assert on_bar.contrast_btn.state == "down"
        assert on_bar._focus_region is FocusRegion.SIDEBAR

    def test_down_drops_out_and_up_is_held(self, on_bar: OKFViewer) -> None:
        assert on_bar.handle_key(KEY_UP) is True
        assert on_bar._focus_region is FocusRegion.TOP_BAR
        assert on_bar.handle_key(KEY_DOWN) is True
        assert on_bar._focus_region is FocusRegion.SIDEBAR

    def test_an_unmapped_key_is_left_to_the_host(self, on_bar: OKFViewer) -> None:
        assert on_bar.handle_key(KEY_F) is False


class TestAPageShownAgain:
    def test_the_page_already_showing_adds_nothing_to_the_history(self, viewer: OKFViewer) -> None:
        viewer.show_page(viewer.bundle / "index.md")
        assert len(viewer.history) == 1

    def test_the_page_left_remembers_how_far_it_was_scrolled(self, viewer: OKFViewer) -> None:
        viewer.body_scroll.scroll_y = 0.4
        viewer.show_page(viewer.bundle / "concept" / "a.md")
        assert viewer.history[0].scroll_y == pytest.approx(0.4)

    def test_a_page_opened_part_way_down_is_put_there_again_once_laid_out(
        self, viewer: OKFViewer
    ) -> None:
        with clock_patched() as clock:
            viewer.show_page(viewer.bundle / "concept" / "a.md", scroll_y=0.25)
            assert viewer.body_scroll.scroll_y == pytest.approx(0.25)
            viewer.body_scroll.scroll_y = 0.9  # the labels' sizes arriving shift it
            run_scheduled(clock)

        assert viewer.body_scroll.scroll_y == pytest.approx(0.25)


class TestATableUnderAHeading:
    def test_it_goes_in_the_headings_section_and_starts_none(self, viewer: OKFViewer) -> None:
        page = viewer.bundle / "table.md"
        page.write_text("# Table\n\n| a |\n|---|\n| 1 |\n", encoding="utf-8")
        with patch.object(viewer, "_new_section", wraps=viewer._new_section) as new_section:
            viewer.show_page(page)
        assert new_section.call_count == 1


class TestAListItem:
    """A list item's marker sits in its own column and keeps the text's height."""

    def test_the_row_and_its_marker_follow_the_texts_height(self) -> None:
        text = Label(size_hint_y=None)
        row = OKFViewer._hanging_row(text, Block(markup="item", indent=1, marker="•"))

        text.height = 77

        marker = next(w for w in row.children if isinstance(w, Label) and w is not text)
        assert (row.height, marker.height) == (77, 77)
        assert marker.text == "•"

    def test_a_nested_item_is_stepped_in_by_its_depth(self) -> None:
        text = Label(size_hint_y=None)
        row = OKFViewer._hanging_row(text, Block(markup="item", indent=3, marker="1."))

        spacer = row.children[-1]  # added first: the leftmost
        assert spacer.width == dp(2 * viewer_module.LIST_INDENT_STEP)
        assert row.children[0] is text
