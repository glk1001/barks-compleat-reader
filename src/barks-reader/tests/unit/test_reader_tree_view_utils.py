from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.reader_tree_view_utils import (
    find_node_by_path,
    find_tree_view_node,
    find_tree_view_title_node,
    get_tree_view_node_path,
)


class TestReaderTreeViewUtils:
    @pytest.fixture
    def mock_tree(self) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
        """Create a mock tree structure for testing."""
        root = MagicMock()
        root.level = 0
        root.parent_node = None
        root.get_name.return_value = "root"  # Fix: Root node should return "root" for its name

        child1 = MagicMock()
        child1.get_name.return_value = "Child 1"
        child1.level = 1
        child1.parent_node = root
        child1.nodes = []

        child2 = MagicMock()
        child2.get_name.return_value = "Child 2"
        child2.level = 1
        child2.parent_node = root

        grandchild1 = MagicMock()
        grandchild1.get_name.return_value = "Grandchild 1"
        grandchild1.level = 2
        grandchild1.parent_node = child2
        grandchild1.nodes = []

        child2.nodes = [grandchild1]
        root.nodes = [child1, child2]

        tree = MagicMock()
        tree.root = root

        return tree, root, child1, grandchild1

    def test_get_tree_view_node_path(
        self, mock_tree: tuple[MagicMock, MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test retrieving the path of a node."""
        _, root, child1, grandchild1 = mock_tree

        # Test root node
        assert get_tree_view_node_path(root) == ["root"]

        # Test first-level child
        assert get_tree_view_node_path(child1) == ["Child 1", "root"]

        # Test nested child
        assert get_tree_view_node_path(grandchild1) == ["Grandchild 1", "Child 2", "root"]

    def test_find_node_by_path(
        self, mock_tree: tuple[MagicMock, MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test finding a node by its path."""
        tree, root, child1, grandchild1 = mock_tree

        # Test finding the root (not supported by this function, should be None)
        assert find_node_by_path(tree, ["root"]) is None

        # Test finding a first-level child
        found_node = find_node_by_path(tree, ["root", "Child 1"])
        assert found_node == child1

        # Test finding a nested child
        child2 = root.nodes[1]
        child2.is_open = False  # Ensure we test the toggle logic

        found_node = find_node_by_path(tree, ["root", "Child 2", "Grandchild 1"])
        assert found_node == grandchild1
        tree.toggle_node.assert_called_once_with(child2)  # Check that it was opened

        # Test finding a non-existent node
        assert find_node_by_path(tree, ["root", "Child 2", "Non-existent"]) is None

    def test_find_tree_view_node(
        self, mock_tree: tuple[MagicMock, MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test finding a node by its text recursively."""
        _, root, _, grandchild1 = mock_tree

        # Test finding a nested node
        found_node = find_tree_view_node(root, "Grandchild 1")
        assert found_node == grandchild1

        # Test finding a non-existent node
        assert find_tree_view_node(root, "Non-existent") is None

    def test_find_tree_view_title_node(self) -> None:
        """Test finding a title node by its title enum."""
        # Create mock title nodes
        node1 = MagicMock()
        node1.get_title.return_value = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        node1.nodes = []

        node2 = MagicMock()
        node2.get_title.return_value = Titles.LOST_IN_THE_ANDES
        node2.nodes = []

        nodes = [node1, node2]

        # Test finding an existing title
        found_node = find_tree_view_title_node(nodes, Titles.LOST_IN_THE_ANDES)
        assert found_node == node2

        # Test finding a non-existent title
        assert find_tree_view_title_node(nodes, Titles.LAND_OF_THE_TOTEM_POLES) is None
