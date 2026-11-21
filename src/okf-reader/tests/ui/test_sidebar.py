# ruff: noqa: SLF001
# cspell:ignore ffcc pytestmark
"""The sidebar through a real viewer: the search box, its index, its results, and their keys."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from kivy.uix.label import Label
from okf_reader.core.search import SearchHit
from okf_reader.ui import sidebar
from okf_reader.ui import viewer as viewer_module
from okf_reader.ui.keynav import (
    KEY_DOWN,
    KEY_END,
    KEY_ENTER,
    KEY_F,
    KEY_HOME,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_UP,
)
from okf_reader.ui.sidebar import SEARCH_ERROR_TEXT
from okf_reader.ui.viewer import (
    FocusRegion,
    OKFViewer,
)
from viewer_test_helpers import (
    NEEDS_A_WINDOW,
    Hits,
    hit,
    left_texts,
    page_of,
)

pytestmark = NEEDS_A_WINDOW


class TestSearchFocus:
    def test_any_focus_is_logged_a_tap_too(self, viewer: OKFViewer) -> None:
        """A test waits on this line after tapping the box, before it types."""
        with patch.object(viewer_module.trace, "search_focused") as focused:
            viewer._sidebar._on_focus(viewer.search_field, focused=True)  # as a tap focuses it
            viewer._sidebar._on_focus(viewer.search_field, focused=False)
        focused.assert_called_once()

    def test_focus_search_is_logged_once(self, viewer: OKFViewer) -> None:
        with patch.object(viewer_module.trace, "search_focused") as focused:
            viewer.focus_search()
        focused.assert_called_once()


class TestSearchIndexFailure:
    def test_a_failed_build_shows_the_error_note(self, viewer: OKFViewer) -> None:
        viewer.search_field.text = "grotto"
        viewer._sidebar.mark_ready(failed=True)
        notes = [w.text for w in viewer._sidebar.body.children if isinstance(w, Label)]
        assert notes == [SEARCH_ERROR_TEXT]

    def test_the_worker_reports_a_failure_on_the_ui_thread(self, viewer: OKFViewer) -> None:
        def broken() -> None:
            raise OSError

        with patch.object(sidebar, "Clock") as clock:
            viewer._sidebar._warm_index(broken)
        with patch.object(viewer._sidebar, "mark_ready") as mark:
            clock.schedule_once.call_args.args[0](0)
        mark.assert_called_once_with(failed=True)

    def test_the_worker_logs_a_failed_build_with_its_error(self, viewer: OKFViewer) -> None:
        error = OSError("gone")

        def broken() -> None:
            raise error

        with (
            patch.object(sidebar, "Clock"),
            patch.object(sidebar, "trace") as trace,
        ):
            viewer._sidebar._warm_index(broken)
        trace.search_index_building.assert_called_once_with()
        trace.search_index_failed.assert_called_once()
        assert trace.search_index_failed.call_args.args[1] is error
        trace.search_index_built.assert_not_called()

    def test_the_worker_logs_the_build_before_handing_it_to_the_ui(self, viewer: OKFViewer) -> None:
        """A stall on "Searching…" then shows whether the build or the hand-over stopped."""
        calls = MagicMock()
        with (
            patch.object(sidebar, "Clock", calls.clock),
            patch.object(sidebar, "trace", calls.trace),
        ):
            viewer._sidebar._warm_index(calls.warm)
        assert [name for name, _args, _kwargs in calls.mock_calls] == [
            "trace.search_index_building",
            "warm",
            "trace.search_index_built",
            "clock.schedule_once",
        ]
        with patch.object(viewer._sidebar, "mark_ready") as mark:
            calls.clock.schedule_once.call_args.args[0](0)
        mark.assert_called_once_with(failed=False)

    def test_taking_the_outcome_is_logged_with_the_query_typed_meanwhile(
        self, viewer: OKFViewer
    ) -> None:
        viewer.search_field.text = "grotto"
        with patch.object(viewer_module.trace, "search_ready") as ready:
            viewer._sidebar.mark_ready(failed=True)
        ready.assert_called_once_with(failed=True, text="grotto")

    def test_a_provider_that_needs_no_warming_is_ready_at_once(self, viewer: OKFViewer) -> None:
        viewer._sidebar.searcher = Hits([])  # no `warm` to call
        viewer._sidebar._on_focus(viewer.search_field, focused=True)
        assert viewer._sidebar.ready is True

    def test_warm_search_starts_one_build_however_often_asked(self, viewer: OKFViewer) -> None:
        """The host's call at open and the box's first focus share one build."""
        with patch.object(sidebar.threading, "Thread") as thread:
            viewer.warm_search()
            viewer._sidebar._on_focus(viewer.search_field, focused=True)
            viewer.warm_search()
        thread.assert_called_once()
        thread.return_value.start.assert_called_once_with()

    def test_a_focus_before_any_warming_starts_the_build(self, viewer: OKFViewer) -> None:
        with patch.object(sidebar.threading, "Thread") as thread:
            viewer._sidebar._on_focus(viewer.search_field, focused=True)
        assert thread.call_args.kwargs["target"] == viewer._sidebar._warm_index

    def test_losing_focus_starts_no_build(self, viewer: OKFViewer) -> None:
        with patch.object(sidebar.threading, "Thread") as thread:
            viewer._sidebar._on_focus(viewer.search_field, focused=False)
        thread.assert_not_called()


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
        viewer._sidebar.mark_ready(failed=True)
        self._type(viewer, "grotto")
        assert left_texts(viewer) == [SEARCH_ERROR_TEXT]

    def test_typing_once_ready_lists_the_hits(self, viewer: OKFViewer) -> None:
        a_page = viewer.bundle / "concept" / "a.md"
        viewer._sidebar.searcher = Hits([hit(a_page, "A")])
        viewer._sidebar.mark_ready(failed=False)

        self._type(viewer, "a")

        assert [path for path, _btn in viewer._sidebar.result_rows] == [a_page]

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
        viewer._sidebar.searcher = Hits([text_hit, hit(a_page, "Glen [Brown]")])
        viewer._sidebar.mark_ready(failed=False)

        self._type(viewer, "glen brown")

        (_, text_row), (_, title_row) = viewer._sidebar.result_rows
        assert "…to the artist [b][color=" in text_row.text
        assert "]Glen Brown[/color][/b], Barks" in text_row.text
        assert "Topics" not in text_row.text  # the snippet takes the breadcrumb's line
        assert text_row.height > title_row.height  # room for two lines of snippet
        assert "Glen &bl;Brown&br;" in title_row.text  # markup in a title is escaped

    def test_the_clear_button_puts_the_tree_back(self, viewer: OKFViewer) -> None:
        self._type(viewer, "grotto")
        viewer._sidebar.clear()
        assert viewer.search_field.text == ""
        assert viewer.tree_scroll.parent is viewer._sidebar.body

    def test_clearing_twice_leaves_the_tree_alone(self, viewer: OKFViewer) -> None:
        """An empty box asked again rebuilds nothing: the sidebar's ringed row is kept."""
        self._type(viewer, "grotto")
        viewer._sidebar.clear()
        viewer._sidebar.index = 0  # a row ringed since the tree came back

        with patch.object(viewer._sidebar.body, "clear_widgets") as cleared:
            viewer._sidebar.clear()
            viewer._sidebar.show_tree()

        cleared.assert_not_called()
        assert viewer._sidebar.index == 0
        assert viewer.tree_scroll.parent is viewer._sidebar.body


class TestResultKeys:
    @pytest.fixture
    def results(self, viewer: OKFViewer) -> OKFViewer:
        hits = [hit(viewer.bundle / f"p{i}.md", f"Page {i}") for i in range(3)]
        viewer._sidebar.searcher = Hits(hits)
        viewer._sidebar.mark_ready(failed=False)
        viewer.search_field.text = "page"
        viewer._set_focus_region(FocusRegion.SIDEBAR)
        return viewer

    def test_end_and_home_go_to_the_last_and_first_row(self, results: OKFViewer) -> None:
        results.handle_key(KEY_END)
        assert results._sidebar.index == 2  # noqa: PLR2004
        results.handle_key(KEY_HOME)
        assert results._sidebar.index == 0

    def test_left_is_held_and_others_are_left_to_the_host(self, results: OKFViewer) -> None:
        assert results.handle_key(KEY_LEFT) is True
        assert results.handle_key(KEY_F) is False

    def test_a_row_out_of_view_is_scrolled_to(self, results: OKFViewer) -> None:
        scroll = results._sidebar.results_scroll
        assert scroll is not None
        scroll.height = 10
        scroll.children[0].height = 1000
        with patch.object(scroll, "scroll_to") as scroll_to:
            results.handle_key(KEY_END)
        scroll_to.assert_called_once()


class TestTheSearchFieldsBorder:
    """A faint outline keeps to the search field's edges as it moves and resizes."""

    def test_the_outline_follows_the_field(self, viewer: OKFViewer) -> None:
        field = viewer.search_field
        field.pos = (10, 20)
        field.size = (200, 32)
        lines = [i for i in field.canvas.after.children if isinstance(i, sidebar.Line)]
        assert len(lines) == 1
        assert list(lines[0].points) == [10, 20, 210, 20, 210, 52, 10, 52]
        assert lines[0].close
        assert lines[0].width == sidebar.SEARCH_FIELD_BORDER_WIDTH


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
        assert btn.width == viewer_module.dp(sidebar.SEARCH_CLEAR_BTN_WIDTH)
        assert (btn.right, btn.y) == (row.right, row.y)
        assert not btn.disabled

    def test_hidden_the_button_takes_no_touches_from_the_field(self, viewer: OKFViewer) -> None:
        viewer.search_field.text = "duck"
        viewer.search_field.text = ""
        btn = viewer.search_clear_btn
        assert btn.width == 0
        assert btn.disabled


class TestTheIndexReadyWithAQueryTyped:
    def test_a_query_typed_during_the_build_gets_its_hits_when_it_ends(
        self, viewer: OKFViewer
    ) -> None:
        """Or it stays on "Searching…" until something more is typed."""
        a_page = viewer.bundle / "concept" / "a.md"
        viewer._sidebar.searcher = Hits([hit(a_page, "A")])
        viewer.search_field.text = "a"
        assert left_texts(viewer) == ["Searching…"]

        viewer._sidebar.mark_ready(failed=False)

        assert [path for path, _btn in viewer._sidebar.result_rows] == [a_page]

    def test_with_nothing_typed_the_tree_stays(self, viewer: OKFViewer) -> None:
        viewer._sidebar.searcher = Hits([])

        viewer._sidebar.mark_ready(failed=False)

        assert viewer.tree_scroll.parent is viewer._sidebar.body

    def test_a_query_nothing_matches_says_so(self, viewer: OKFViewer) -> None:
        viewer._sidebar.searcher = Hits([])
        viewer._sidebar.mark_ready(failed=False)

        viewer.search_field.text = "zzzz"

        assert left_texts(viewer) == ["No matches"]
        assert viewer._sidebar.result_rows == []

    def test_a_title_hit_s_row_names_where_the_page_is(self, viewer: OKFViewer) -> None:
        a_page = viewer.bundle / "concept" / "a.md"
        hit = SearchHit(path=a_page, title="A", breadcrumb="Concept", matched_on="title", score=1)
        viewer._sidebar.searcher = Hits([hit])
        viewer._sidebar.mark_ready(failed=False)

        viewer.search_field.text = "a"

        ((_path, row),) = viewer._sidebar.result_rows
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
        viewer._sidebar.searcher = Hits([hit(top, "A"), hit(second, "Home")])
        viewer._sidebar.mark_ready(failed=False)
        viewer.focus_search()
        viewer.search_field.text = "a"

        viewer.search_field.dispatch("on_text_validate")

        assert page_of(viewer) == "concept/a.md"
        assert not viewer.search_focused
        assert len(viewer._sidebar.result_rows) == 2  # noqa: PLR2004 — the list stays for the next

    def test_enter_with_no_hits_opens_nothing(self, viewer: OKFViewer) -> None:
        viewer._sidebar.searcher = Hits([])
        viewer._sidebar.mark_ready(failed=False)
        viewer.search_field.text = "nothing"
        viewer.search_field.dispatch("on_text_validate")
        assert page_of(viewer) == "index.md"

    def test_enter_before_the_index_is_ready_opens_nothing(self, viewer: OKFViewer) -> None:
        viewer._sidebar.searcher = Hits([hit(viewer.bundle / "concept" / "a.md", "A")])
        viewer.search_field.text = "a"
        viewer.search_field.dispatch("on_text_validate")
        assert page_of(viewer) == "index.md"


class TestTheRemoteInTheResults:
    @pytest.fixture
    def results(self, viewer: OKFViewer) -> OKFViewer:
        pages = [viewer.bundle / "index.md", viewer.bundle / "concept" / "a.md"]
        viewer._sidebar.searcher = Hits([hit(page, page.stem) for page in pages])
        viewer._sidebar.mark_ready(failed=False)
        viewer.search_field.text = "page"
        viewer._sidebar.active_result_path = None
        viewer._set_focus_region(FocusRegion.SIDEBAR)
        viewer._sidebar.clear_result_focus()
        return viewer

    def test_down_starts_on_the_top_hit_and_steps_from_there(self, results: OKFViewer) -> None:
        results.handle_key(KEY_DOWN)
        assert results._sidebar.index == 0
        results.handle_key(KEY_DOWN)
        assert results._sidebar.index == 1
        results.handle_key(KEY_DOWN)
        assert results._sidebar.index == 1  # the last row: no wrap
        results.handle_key(KEY_UP)
        assert results._sidebar.index == 0

    def test_it_starts_on_the_row_of_the_page_showing(self, results: OKFViewer) -> None:
        results._sidebar.active_result_path = results.bundle / "concept" / "a.md"
        results.handle_key(KEY_DOWN)
        assert results._sidebar.index == 1

    def test_up_from_the_top_hit_goes_back_to_the_box(self, results: OKFViewer) -> None:
        results.handle_key(KEY_DOWN)
        assert results.handle_key(KEY_UP) is True
        assert results.search_focused
        assert results._sidebar.index is None

    def test_enter_opens_the_ringed_hit_and_keeps_the_list(self, results: OKFViewer) -> None:
        results.handle_key(KEY_END)

        assert results.handle_key(KEY_ENTER) is True

        assert page_of(results) == "concept/a.md"
        assert len(results._sidebar.result_rows) == 2  # noqa: PLR2004

    def test_enter_with_no_row_ringed_opens_nothing(self, results: OKFViewer) -> None:
        assert results.handle_key(KEY_ENTER) is True
        assert page_of(results) == "index.md"

    def test_right_crosses_to_the_page(self, results: OKFViewer) -> None:
        assert results.handle_key(KEY_RIGHT) is True
        assert results._focus_region is FocusRegion.PAGE
