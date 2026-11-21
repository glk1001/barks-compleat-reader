# ruff: noqa: SLF001
# cspell:ignore ffcc pytestmark
"""The page's links through a real viewer: the keys that walk them, and the pointer over them."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from kivy.metrics import dp
from okf_reader.core.theme import ViewerThemeSpec
from okf_reader.ui import page_links
from okf_reader.ui.keynav import (
    KEY_DOWN,
    KEY_END,
    KEY_ENTER,
    KEY_F,
    KEY_HOME,
    KEY_LEFT,
    KEY_PAGE_DOWN,
    KEY_PAGE_UP,
    KEY_RIGHT,
    KEY_UP,
    LINK_FOCUS_COLOR,
    PAGE_LINE_STEP,
    PAGE_STEP_OVERLAP,
)
from okf_reader.ui.viewer import (
    FocusRegion,
    OKFViewer,
)
from viewer_test_helpers import (
    NEEDS_A_WINDOW,
    open_footnote,
    page_of,
    window_patched,
)

if TYPE_CHECKING:
    from pathlib import Path


pytestmark = NEEDS_A_WINDOW


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
        """A view less the overlap that keeps the last lines read in sight."""
        view, scrollable = 100, 1000 - 100
        assert long_page.handle_key(KEY_PAGE_DOWN) is True
        step = view - dp(PAGE_STEP_OVERLAP)
        assert long_page.body_scroll.scroll_y == pytest.approx(1 - step / scrollable)
        long_page.handle_key(KEY_PAGE_DOWN)
        assert long_page.body_scroll.scroll_y == pytest.approx(1 - 2 * step / scrollable)
        long_page.handle_key(KEY_PAGE_UP)
        long_page.handle_key(KEY_PAGE_UP)
        assert long_page.body_scroll.scroll_y == pytest.approx(1.0)

    def test_end_and_home_jump_to_the_ends(self, long_page: OKFViewer) -> None:
        long_page.handle_key(KEY_END)
        assert long_page.body_scroll.scroll_y == 0.0
        long_page.handle_key(KEY_HOME)
        assert long_page.body_scroll.scroll_y == 1.0

    def test_end_on_a_page_that_fits_stays_at_the_top(self, long_page: OKFViewer) -> None:
        long_page.body.height = 50
        long_page.handle_key(KEY_END)
        assert long_page.body_scroll.scroll_y == 1.0


class TestPageKeys:
    @pytest.fixture
    def on_page(self, viewer: OKFViewer) -> OKFViewer:
        viewer._set_focus_region(FocusRegion.PAGE)
        return viewer

    def test_an_unmapped_key_is_left_to_the_host(self, on_page: OKFViewer) -> None:
        assert on_page.handle_key(KEY_F) is False

    def test_a_focused_link_scrolled_out_of_view_loses_the_focus(self, on_page: OKFViewer) -> None:
        on_page._links.set_focus(0)
        lbl = on_page._links.links[0][0]
        with patch.object(lbl, "to_window", return_value=(0, -10_000)):
            on_page._links.prune_offscreen_focus()
        assert on_page._links.focused is None

    def test_clearing_a_focus_never_drawn_restores_nothing(self, on_page: OKFViewer) -> None:
        on_page._links.focused = 0
        text = on_page._links.links[0][0].text
        on_page._links.set_focus(None)
        assert on_page._links.links[0][0].text == text
        assert on_page._links.focused is None

    def test_a_footnote_with_no_definition_opens_nothing(self, on_page: OKFViewer) -> None:
        on_page._on_ref(on_page._links.links[0][0], "fn:missing")
        assert on_page._footnote_popup is None

    def test_a_link_that_resolves_nowhere_stays_on_the_page(self, on_page: OKFViewer) -> None:
        on_page._on_ref(on_page._links.links[0][0], "no/such/page.md")
        assert page_of(on_page) == "index.md"

    def test_a_footnote_link_that_resolves_nowhere_only_closes_it(self, on_page: OKFViewer) -> None:
        open_footnote(on_page)
        popup_label = on_page._links.popup_label
        assert popup_label is not None
        popup_label.dispatch("on_ref_press", "no/such/page.md")
        assert page_of(on_page) == "index.md"

    def test_returning_to_the_page_before_any_page_is_shown(self, on_page: OKFViewer) -> None:
        on_page.history.clear()
        on_page._set_focus_region(FocusRegion.PAGE)
        assert on_page._focus_region is FocusRegion.PAGE


class TestOverLink:
    def test_a_link_under_the_pointer_in_the_page_counts(self, viewer: OKFViewer) -> None:
        with (
            patch.object(viewer.body_scroll, "get_root_window", return_value=object()),
            patch.object(viewer.body_scroll, "collide_point", return_value=True),
            patch.object(page_links, "ref_under", return_value="concept/a.md"),
        ):
            assert viewer._links.over_link((10, 10)) is True


class TestLinkFocusColour:
    """The focused link is recoloured from whatever colour the page's links were drawn in."""

    @pytest.mark.parametrize("theme", [None, ViewerThemeSpec(link_hex="00ff00")])
    def test_the_focused_link_takes_the_focus_colour(
        self, bundle: Path, theme: ViewerThemeSpec | None
    ) -> None:
        viewer = OKFViewer(bundle, theme=theme)
        label = viewer._links.links[0][0]
        before = label.text
        assert LINK_FOCUS_COLOR not in before

        viewer._links.set_focus(0)

        assert f"[color={LINK_FOCUS_COLOR}]" in label.text
        viewer._links.set_focus(None)
        assert label.text == before


class TestTheRemoteOnThePage:
    @pytest.fixture
    def on_page(self, viewer: OKFViewer) -> OKFViewer:
        viewer._set_focus_region(FocusRegion.PAGE)
        return viewer

    def test_down_takes_the_first_link_in_view_and_enter_follows_it(
        self, on_page: OKFViewer
    ) -> None:
        assert on_page.handle_key(KEY_DOWN) is True
        assert on_page._links.focused == 0

        assert on_page.handle_key(KEY_ENTER) is True

        assert page_of(on_page) == "concept/a.md"

    def test_up_takes_the_last_link_in_view(self, on_page: OKFViewer) -> None:
        on_page.handle_key(KEY_UP)
        assert on_page._links.focused == len(on_page._links.links) - 1

    def test_enter_on_a_footnote_marker_opens_the_footnote(self, on_page: OKFViewer) -> None:
        on_page.handle_key(KEY_DOWN)
        on_page.handle_key(KEY_DOWN)
        assert on_page._links.links[on_page._links.focused or 0][1] == "fn:note"

        on_page.handle_key(KEY_ENTER)

        assert on_page._footnote_popup is not None

    def test_enter_with_no_link_focused_is_left_to_the_host(self, on_page: OKFViewer) -> None:
        assert on_page.handle_key(KEY_ENTER) is False

    @pytest.mark.parametrize(("key", "sign"), [(KEY_DOWN, 1), (KEY_UP, -1)])
    def test_a_page_with_no_links_scrolls_a_step(
        self, on_page: OKFViewer, key: int, sign: int
    ) -> None:
        on_page.show_page(on_page.bundle / "concept" / "a.md")
        with patch.object(on_page._links, "scroll_by") as scroll:
            assert on_page.handle_key(key) is True
        scroll.assert_called_once_with(sign * dp(PAGE_LINE_STEP))

    def test_a_link_is_placed_by_how_far_it_is_below_the_views_top(
        self, on_page: OKFViewer
    ) -> None:
        label = on_page._links.links[0][0]
        label.height = 30
        others = [(0.0, 100.0)] * (len(on_page._links.links) - 1)
        with (
            patch.object(on_page.body_scroll, "to_window", return_value=(0, 500)),
            patch.object(label, "to_window", return_value=(0, 420)),
        ):
            geometry = on_page._links.geometry()

        assert geometry[0] == (80, 110)
        assert len(geometry) == 1 + len(others)

    def test_a_focused_link_on_a_page_taller_than_the_view_is_scrolled_to(
        self, on_page: OKFViewer
    ) -> None:
        on_page.body.height = 5000
        with patch.object(on_page.body_scroll, "scroll_to") as scroll_to:
            on_page._links.set_focus(0)
        scroll_to.assert_called_once_with(on_page._links.links[0][0], padding=24)

    def test_a_focused_link_still_in_view_keeps_the_focus(self, on_page: OKFViewer) -> None:
        on_page._links.set_focus(0)
        on_page._links.prune_offscreen_focus()
        assert on_page._links.focused == 0

    def test_left_goes_to_the_sidebar_and_right_goes_nowhere(self, on_page: OKFViewer) -> None:
        assert on_page.handle_key(KEY_RIGHT) is True
        assert on_page._focus_region is FocusRegion.PAGE
        assert on_page.handle_key(KEY_LEFT) is True
        assert on_page._focus_region is FocusRegion.SIDEBAR


class TestThePointer:
    def test_moving_onto_a_link_and_off_it_flips_the_cursor(self, viewer: OKFViewer) -> None:
        with window_patched(), patch.object(viewer._links, "over_link", side_effect=[True, False]):
            viewer._links.on_mouse_pos(None, (10, 10))
            assert viewer._links.hand_cursor is True
            viewer._links.on_mouse_pos(None, (500, 500))
            assert viewer._links.hand_cursor is False

    def test_outside_the_page_pane_nothing_is_a_link(self, viewer: OKFViewer) -> None:
        with (
            patch.object(viewer.body_scroll, "get_root_window", return_value=object()),
            patch.object(viewer.body_scroll, "collide_point", return_value=False),
            patch.object(page_links, "ref_under", return_value="concept/a.md") as ref_under,
        ):
            assert viewer._links.over_link((10, 10)) is False
        ref_under.assert_not_called()

    def test_with_a_footnote_open_only_its_links_count(self, viewer: OKFViewer) -> None:
        open_footnote(viewer)
        popup_label = viewer._links.popup_label
        assert popup_label is not None
        with (
            patch.object(viewer.body_scroll, "get_root_window", return_value=object()),
            patch.object(page_links, "ref_under", return_value=None) as ref_under,
        ):
            assert viewer._links.over_link((10, 10)) is False
        ref_under.assert_called_once_with(popup_label, 10, 10)
