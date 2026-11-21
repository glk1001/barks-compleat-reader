# ruff: noqa: SLF001
# cspell:ignore ffcc pytestmark
"""The contents tree through a real viewer: its branches, its keys, its scroll to a node."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from kivy.uix.treeview import TreeViewLabel
from okf_reader.ui import tree_panel
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
from okf_reader.ui.viewer import (
    FocusRegion,
    OKFViewer,
)
from viewer_test_helpers import (
    NEEDS_A_WINDOW,
    Hits,
    clock_patched,
    concept_node,
    hit,
    node_at,
    page_of,
    run_scheduled,
    tree_node,
)

if TYPE_CHECKING:
    from pathlib import Path


pytestmark = NEEDS_A_WINDOW


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
        viewer._tree_panel.focus_node(concept)

        viewer.handle_key(KEY_RIGHT)

        assert viewer.tree.selected_node is concept

    def test_an_empty_tree_takes_only_the_navigation_keys(self, viewer: OKFViewer) -> None:
        with patch.object(viewer.tree, "iterate_open_nodes", return_value=iter(())):
            assert viewer.handle_key(KEY_DOWN) is True
        with patch.object(viewer.tree, "iterate_open_nodes", return_value=iter(())):
            assert viewer.handle_key(KEY_ENTER) is False

    def test_a_folder_without_an_index_page_opens_no_page(self, viewer: OKFViewer) -> None:
        viewer._tree_panel.on_node(concept_node(viewer))
        viewer._tree_panel.on_node(TreeViewLabel())  # neither a page nor a folder
        assert page_of(viewer) == "index.md"

    def test_a_folder_with_an_index_page_opens_it(self, viewer: OKFViewer) -> None:
        (viewer.bundle / "concept" / "index.md").write_text("# Concept\n", encoding="utf-8")
        viewer._tree_panel.on_node(concept_node(viewer))
        assert page_of(viewer) == "concept/index.md"


class TestSyncTree:
    def test_a_page_outside_the_bundle_leaves_the_tree_alone(
        self, viewer: OKFViewer, tmp_path: Path
    ) -> None:
        viewer._tree_panel.sync_to(tmp_path / "elsewhere.md")
        assert viewer.tree.selected_node is None

    def test_a_page_in_a_folder_the_tree_lacks_leaves_it_alone(self, viewer: OKFViewer) -> None:
        viewer._tree_panel.sync_to(viewer.bundle / ".hidden" / "x.md")
        assert viewer.tree.selected_node is None


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
        viewer._tree_panel.on_node(tree_node(viewer, "A"))
        assert page_of(viewer) == "concept/a.md"

    def test_a_selection_made_to_mirror_the_page_opens_nothing(self, viewer: OKFViewer) -> None:
        viewer.tree.toggle_node(concept_node(viewer))
        viewer._tree_panel.syncing = True
        viewer._tree_panel.on_node(tree_node(viewer, "A"))
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
        viewer._tree_panel.focus_node(concept)

        with clock_patched(tree_panel) as clock:
            viewer.handle_key(KEY_RIGHT)
            assert concept.is_open
            with patch.object(viewer._tree_panel, "scroll_node_into_view") as scrolled:
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
        viewer._tree_panel.focus_node(tree_node(viewer, "A"))

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
        viewer._tree_panel.focus_node(concept)

        viewer.handle_key(KEY_ENTER)
        assert concept.is_open
        assert page_of(viewer) == "concept/index.md"
        assert viewer._focus_region is FocusRegion.SIDEBAR

        viewer._tree_panel.focus_node(concept)
        viewer.handle_key(KEY_ENTER)
        assert not concept.is_open

    def test_right_on_an_open_folder_with_nothing_in_it_stays_put(self, viewer: OKFViewer) -> None:
        concept = concept_node(viewer)
        viewer._tree_panel.focus_node(concept)
        empty = TreeViewLabel(is_leaf=False, is_open=True)

        viewer._tree_panel.expand(empty)

        assert viewer.tree.selected_node is concept
        assert viewer._focus_region is FocusRegion.SIDEBAR

    def test_enter_on_a_page_opens_it_and_crosses_to_it(self, viewer: OKFViewer) -> None:
        viewer.tree.toggle_node(concept_node(viewer))
        viewer._tree_panel.focus_node(tree_node(viewer, "A"))

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
        tall._tree_panel.scroll_node_into_view(node_at(node_top))
        assert tall.tree_scroll.scroll_y == pytest.approx(expected)

    def test_a_tree_that_fits_is_left_where_it_is(self, tall: OKFViewer) -> None:
        tall.tree.height = 80
        tall.tree_scroll.scroll_y = 0.5
        tall._tree_panel.scroll_node_into_view(node_at(40))
        assert tall.tree_scroll.scroll_y == 0.5  # noqa: PLR2004

    def test_it_waits_for_two_frames_to_agree(self, tall: OKFViewer) -> None:
        node = node_at(500)
        with (
            clock_patched(tree_panel) as clock,
            patch.object(tall._tree_panel, "scroll_node_into_view") as scroll,
        ):
            tall._tree_panel.reveal_when_settled(node)
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
        with (
            clock_patched(tree_panel) as clock,
            patch.object(tall._tree_panel, "scroll_node_into_view") as scroll,
        ):
            tall._tree_panel.reveal_when_settled(node)
            for _ in range(tree_panel.TREE_REVEAL_MAX_FRAMES):
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
            patch.object(viewer._tree_panel, "scroll_node_into_view") as scroll,
        ):
            viewer.search_field.text = ""
            run_scheduled(clock)

        scroll.assert_called_with(selected)
        assert viewer.tree_scroll.parent is viewer._left_body
