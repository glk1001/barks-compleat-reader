# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.reader_ui_classes import BaseTreeViewNode
from barks_reader.tree_view_screen import TreeViewScreen
from kivy.uix.widget import Widget

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.show_top_view_title_info = True
    return settings


@pytest.fixture
def tree_view_screen(mock_settings: MagicMock) -> Generator[TreeViewScreen]:
    # Patch BoxLayout.__init__ to avoid Kivy window creation but initialize Widget properties
    with patch("kivy.uix.boxlayout.BoxLayout.__init__", autospec=True) as mock_init:

        def side_effect(self, **kwargs) -> None:  # noqa: ANN001, ANN003
            Widget.__init__(self, **kwargs)
            self.ids = MagicMock()
            self.ids.reader_tree_view = MagicMock()
            self.ids.scroll_view = MagicMock()

        mock_init.side_effect = side_effect

        # Patch settings_notifier to avoid side effects
        with patch("barks_reader.tree_view_screen.settings_notifier"):
            screen = TreeViewScreen(mock_settings)
            yield screen


class TestTreeViewScreen:
    def test_init(self, tree_view_screen: TreeViewScreen, mock_settings: MagicMock) -> None:
        # noinspection PyProtectedMember
        assert tree_view_screen._reader_settings == mock_settings
        assert tree_view_screen.show_current_title is True

    def test_set_title(self, tree_view_screen: TreeViewScreen) -> None:
        # Test with None
        tree_view_screen.set_title(None)
        assert tree_view_screen.current_title_str == ""

        # Test with Title
        tree_view_screen.set_title(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD)
        assert tree_view_screen.current_title_str != ""

    def test_get_selected_node(self, tree_view_screen: TreeViewScreen) -> None:
        mock_node = MagicMock()
        tree_view_screen.ids.reader_tree_view.selected_node = mock_node
        assert tree_view_screen.get_selected_node() == mock_node

    def test_find_node_by_path(self, tree_view_screen: TreeViewScreen) -> None:
        with patch("barks_reader.tree_view_screen.find_node_by_path") as mock_find:
            path = ["root", "child"]
            tree_view_screen.find_node_by_path(path)
            # It reverses the path before calling the util
            mock_find.assert_called_with(tree_view_screen.ids.reader_tree_view, ["child", "root"])

    def test_select_node(self, tree_view_screen: TreeViewScreen) -> None:
        node = MagicMock()
        tree_view_screen.select_node(node)
        tree_view_screen.ids.reader_tree_view.select_node.assert_called_with(node)

    def test_scroll_to_node(self, tree_view_screen: TreeViewScreen) -> None:
        node = MagicMock()
        tree_view_screen.scroll_to_node(node)
        tree_view_screen.ids.scroll_view.scroll_to.assert_called_with(node, padding=50)

    def test_open_all_parent_nodes(self, tree_view_screen: TreeViewScreen) -> None:
        # Setup node hierarchy: root -> parent -> node
        root = MagicMock(spec=BaseTreeViewNode)
        root.parent_node = None
        root.is_open = True  # Already open

        parent = MagicMock(spec=BaseTreeViewNode)
        parent.parent_node = root
        parent.is_open = False  # Needs opening

        node = MagicMock(spec=BaseTreeViewNode)
        node.parent_node = parent
        node.is_open = False  # Leaf

        # The function iterates up from node.
        # parent_nodes list will be [node, parent, root]
        # Then reversed: root, parent, node.

        tree_view_screen.open_all_parent_nodes(node)

        # root is open, so toggle_node shouldn't be called for it.
        # parent is closed, so toggle_node should be called.
        # node is closed, so toggle_node should be called.

        assert tree_view_screen.ids.reader_tree_view.toggle_node.call_count == 2  # noqa: PLR2004
        tree_view_screen.ids.reader_tree_view.toggle_node.assert_any_call(parent)
        tree_view_screen.ids.reader_tree_view.toggle_node.assert_any_call(node)

    def test_deselect_and_close_open_nodes(self, tree_view_screen: TreeViewScreen) -> None:
        # Setup tree structure
        # root -> child1 (open) -> grandchild1 (open)
        #      -> child2 (closed)

        root = MagicMock(spec=BaseTreeViewNode)
        child1 = MagicMock(spec=BaseTreeViewNode)
        child1.is_open = True
        grandchild1 = MagicMock(spec=BaseTreeViewNode)
        grandchild1.is_open = True
        grandchild1.nodes = []
        child1.nodes = [grandchild1]

        child2 = MagicMock(spec=BaseTreeViewNode)
        child2.is_open = False
        child2.nodes = []

        root.nodes = [child1, child2]

        tree_view_screen.ids.reader_tree_view.root = root

        # Setup selected node
        selected_node = MagicMock()
        tree_view_screen.ids.reader_tree_view.selected_node = selected_node

        # Execute
        count = tree_view_screen.deselect_and_close_open_nodes()

        # Verify deselect
        tree_view_screen.ids.reader_tree_view.deselect_node.assert_called_with(selected_node)

        # Verify close calls
        # Should close grandchild1, then child1.
        # count should be 2.
        assert count == 2  # noqa: PLR2004
        tree_view_screen.ids.reader_tree_view.toggle_node.assert_any_call(grandchild1)
        tree_view_screen.ids.reader_tree_view.toggle_node.assert_any_call(child1)

        # Verify reset tracking
        tree_view_screen.ids.reader_tree_view.reset_selection_tracking.assert_called_once()

    def test_on_change_show_current_title(
        self, tree_view_screen: TreeViewScreen, mock_settings: MagicMock
    ) -> None:
        mock_settings.show_top_view_title_info = False
        tree_view_screen.on_change_show_current_title()
        assert tree_view_screen.show_current_title is False
