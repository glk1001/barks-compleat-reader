# ruff: noqa: SLF001

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import barks_reader.ui.tree_view_nodes
from barks_reader.ui.action_bar_helpers import hide_action_bar, show_action_bar
from barks_reader.ui.tree_view_nodes import (
    BaseTreeViewNode,
    ButtonTreeViewNode,
    IntroTextTreeViewNode,
    ReaderTreeBuilderEventDispatcher,
    ReaderTreeView,
    TitleTreeViewNode,
)


class TestHelperFunctions:
    def test_show_action_bar(self) -> None:
        mock_bar = MagicMock()
        show_action_bar(mock_bar)
        assert mock_bar.opacity == 1
        assert mock_bar.disabled is False
        assert mock_bar.height > 0

    def test_hide_action_bar(self) -> None:
        mock_bar = MagicMock()
        hide_action_bar(mock_bar)
        assert mock_bar.opacity == 0
        assert mock_bar.disabled is True
        assert mock_bar.height == 0


class TestReaderTreeView:
    def test_selection_tracking(self) -> None:
        tree = ReaderTreeView()
        node1 = MagicMock()
        node1.get_name.return_value = "Node1"
        node2 = MagicMock()
        node2.get_name.return_value = "Node2"

        # Initial state
        assert tree.previous_selected_node is None
        assert tree._current_selection_tracker is None

        # Select Node 1
        tree.on_selected_node(tree, node1)
        assert tree.previous_selected_node is None
        assert tree._current_selection_tracker == node1

        # Select Node 2
        tree.on_selected_node(tree, node2)
        assert tree.previous_selected_node == node1
        assert tree._current_selection_tracker == node2

        # Reset
        tree.reset_selection_tracking()
        assert tree.previous_selected_node is None
        assert tree._current_selection_tracker is None


class TestReaderTreeBuilderEventDispatcher:
    def test_finished_building(self) -> None:
        dispatcher = ReaderTreeBuilderEventDispatcher()
        mock_handler = MagicMock()
        dispatcher.bind(on_finished_building_event=mock_handler)

        dispatcher.finished_building()
        mock_handler.assert_called_once()


class TestButtonTreeViewNode:
    def test_get_name(self) -> None:
        node = ButtonTreeViewNode(text="[b]Bold[/b]")
        assert node.get_name() == "Bold"

    def test_on_press(self) -> None:
        node = ButtonTreeViewNode()
        mock_tree = MagicMock()

        with patch.object(node, "_get_nodes_treeview", return_value=mock_tree):
            node.on_press()
            mock_tree.toggle_node.assert_called_with(node)

    def test_its_tree_is_found_through_the_rows_between(self) -> None:
        """A node can sit in a layout inside the tree, not straight under it."""
        tree = ReaderTreeView()
        node = SimpleNamespace(parent=SimpleNamespace(parent=tree))
        assert ButtonTreeViewNode._get_nodes_treeview(node) is tree  # ty: ignore[invalid-argument-type]

    def test_a_node_in_no_tree_is_not_toggled(self) -> None:
        node = ButtonTreeViewNode()
        assert ButtonTreeViewNode._get_nodes_treeview(node) is None
        node.on_press()  # nothing to toggle, and no error


class TestNodeNames:
    """The names the selection log line gives the rows that are not titles."""

    def test_a_plain_node_has_no_name_of_its_own(self) -> None:
        assert BaseTreeViewNode().get_name() == "<unknown>"

    def test_a_playlist_intro_is_named_for_what_it_is_and_cannot_be_selected(self) -> None:
        node = IntroTextTreeViewNode()
        assert node.get_name() == "<playlist-intro>"
        assert node.no_selection is True


class TestTitleTreeViewNode:
    def test_create_from_fanta_info(self) -> None:
        mock_info = MagicMock()
        mock_info.fanta_chronological_number = 1
        mock_info.comic_book_info.get_display_title.return_value = "Title"
        mock_info.comic_book_info.title = "TITLE_ENUM"
        # Configure attributes needed by ReaderFormatter
        mock_info.comic_book_info.issue_month = -1
        mock_info.comic_book_info.issue_year = 1950
        mock_info.comic_book_info.submitted_year = 1949
        mock_info.comic_book_info.submitted_month = 1
        mock_info.comic_book_info.submitted_day = 1
        mock_info.comic_book_info.get_short_issue_title.return_value = "FC 1"

        mock_app = MagicMock()
        mock_app.font_manager.tree_view_issue_label_font_size = 10

        with patch.object(  # noqa: SIM117
            barks_reader.ui.tree_view_nodes.App, "get_running_app", return_value=mock_app
        ):
            # Patch __init__ to avoid Kivy widget initialization and manually populate ids
            with patch.object(
                TitleTreeViewNode, "__init__", return_value=None, autospec=True
            ) as mock_init:
                # noinspection PyShadowingNames,LongLine
                def init_side_effect(self: TitleTreeViewNode, fanta_info: Any, **_kwargs) -> None:  # noqa: ANN003, ANN401
                    self.fanta_info = fanta_info
                    self.ids = MagicMock()
                    self.ids.num_label = MagicMock()
                    self.ids.title_label = MagicMock()
                    self.ids.issue_label = MagicMock()

                mock_init.side_effect = init_side_effect

                node = TitleTreeViewNode.create_from_fanta_info(mock_info, MagicMock())

                assert node.ids.num_label.text == "1"
                assert node.ids.title_label.text == "Title"
