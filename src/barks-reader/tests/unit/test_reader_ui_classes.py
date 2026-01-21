# ruff: noqa: SLF001

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.reader_ui_classes import (
    BaseSearchBoxTreeViewNode,
    ButtonTreeViewNode,
    ReaderTreeBuilderEventDispatcher,
    ReaderTreeView,
    TagSearchBoxTreeViewNode,
    TitleSearchBoxTreeViewNode,
    TitleTreeViewNode,
    hide_action_bar,
    show_action_bar,
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
        # noinspection PyProtectedMember
        assert tree._current_selection_tracker is None

        # Select Node 1
        tree.on_selected_node(tree, node1)
        assert tree.previous_selected_node is None
        # noinspection PyProtectedMember
        assert tree._current_selection_tracker == node1

        # Select Node 2
        tree.on_selected_node(tree, node2)
        assert tree.previous_selected_node == node1
        # noinspection PyProtectedMember
        assert tree._current_selection_tracker == node2

        # Reset
        tree.reset_selection_tracking()
        assert tree.previous_selected_node is None
        # noinspection PyProtectedMember
        assert tree._current_selection_tracker is None


class TestReaderTreeBuilderEventDispatcher:
    def test_finished_building(self) -> None:
        dispatcher = ReaderTreeBuilderEventDispatcher()
        mock_handler = MagicMock()
        dispatcher.bind(on_finished_building_event=mock_handler)

        dispatcher.finished_building()
        mock_handler.assert_called_once()


class TestBaseSearchBoxTreeViewNode:
    def test_set_spinner_values(self) -> None:
        mock_spinner = MagicMock()

        # Empty
        BaseSearchBoxTreeViewNode._set_spinner_values(mock_spinner, [])
        assert mock_spinner.values == []
        assert mock_spinner.text == ""
        assert mock_spinner.is_open is False

        # Single
        BaseSearchBoxTreeViewNode._set_spinner_values(mock_spinner, ["A"])
        assert mock_spinner.values == ["A"]
        assert mock_spinner.text == "A"
        assert mock_spinner.is_open is False

        # Multiple
        BaseSearchBoxTreeViewNode._set_spinner_values(mock_spinner, ["A", "B"])
        assert mock_spinner.values == ["A", "B"]
        assert mock_spinner.text == ""
        assert mock_spinner.is_open is True


class TestTitleSearchBoxTreeViewNode:
    @pytest.fixture
    def node(self) -> TitleSearchBoxTreeViewNode:
        mock_search = MagicMock()
        # Patch __init__ to avoid Kivy widget creation issues and manually set up state
        with patch.object(TitleSearchBoxTreeViewNode, "__init__", return_value=None):
            node = TitleSearchBoxTreeViewNode(mock_search)
            node.title_search = mock_search
            node.ids = MagicMock()
            node.ids.title_spinner = MagicMock()
            node.ids.title_search_box = MagicMock()
            node.saved_state = {}
            node.dispatch = MagicMock()
            return node

    def test_get_name(self, node: TitleSearchBoxTreeViewNode) -> None:
        assert node.get_name() == "Title Search Box"

    def test_get_current_title(self, node: TitleSearchBoxTreeViewNode) -> None:
        node.ids.title_search_box.text = "Duck"
        assert node.get_current_title() == "Duck"

    def test_on_internal_search_box_text_changed(self, node: TitleSearchBoxTreeViewNode) -> None:
        node.title_search.get_titles_matching_prefix.return_value = ["Duck"]
        node.title_search.get_titles_as_strings.return_value = ["Donald Duck"]

        # Short text
        # noinspection PyProtectedMember
        node._on_internal_search_box_text_changed(None, "D")  # type: ignore[arg-type]
        assert node.ids.title_spinner.values == []  # Mock default or empty

        # Long text
        # noinspection PyProtectedMember
        node._on_internal_search_box_text_changed(None, "Duck")  # type: ignore[arg-type]
        # noinspection PyUnresolvedReferences
        node.title_search.get_titles_matching_prefix.assert_called_with("Duck")
        # _set_spinner_values logic is tested separately, but we can check values were set on mock
        assert node.ids.title_spinner.values == ["Donald Duck"]
        assert node.saved_state["text"] == "Duck"


class TestTagSearchBoxTreeViewNode:
    @pytest.fixture
    def node(self) -> TagSearchBoxTreeViewNode:
        mock_search = MagicMock()
        with patch.object(TagSearchBoxTreeViewNode, "__init__", return_value=None):
            node = TagSearchBoxTreeViewNode(mock_search)
            # noinspection PyProtectedMember
            node._title_search = mock_search
            node.ids = MagicMock()
            node.ids.tag_spinner = MagicMock()
            node.ids.tag_title_spinner = MagicMock()
            node.saved_state = {}
            node.dispatch = MagicMock()
            return node

    def test_on_internal_tag_search_box_text_changed(self, node: TagSearchBoxTreeViewNode) -> None:
        # Mock _get_tags_matching_search_tag_str
        mock_tag = MagicMock()
        mock_tag.value = "Adventure"
        with patch.object(node, "_get_tags_matching_search_tag_str", return_value=[mock_tag]):
            # noinspection PyProtectedMember
            node._on_internal_tag_search_box_text_changed(None, "Adv")  # type: ignore[arg-type]

            assert node.ids.tag_spinner.values == ["Adventure"]
            assert node.saved_state["text"] == "Adv"

    def test_on_internal_tag_search_box_tag_changed(self, node: TagSearchBoxTreeViewNode) -> None:
        # noinspection PyProtectedMember
        node._title_search.get_titles_from_alias_tag.return_value = (MagicMock(), ["Title1"])
        # noinspection PyProtectedMember
        node._title_search.get_titles_as_strings.return_value = ["Title 1"]

        # noinspection PyProtectedMember
        node._on_internal_tag_search_box_tag_changed(node.ids.tag_spinner, "Adventure")

        assert node.ids.tag_spinner.text == "[b]Adventure[/b] [i](1)[/i]"
        assert node.ids.tag_title_spinner.values == ["Title 1"]


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

        # noinspection LongLine
        with patch("barks_reader.reader_ui_classes.App.get_running_app", return_value=mock_app):  # noqa: SIM117
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
