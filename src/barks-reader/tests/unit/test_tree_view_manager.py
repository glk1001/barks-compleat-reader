# ruff: noqa: SLF001

from __future__ import annotations

from unittest.mock import MagicMock, patch

import barks_reader.ui.tree_view_manager
import pytest
from barks_reader.ui.reader_ui_classes import (
    ButtonTreeViewNode,
    TagGroupStoryGroupTreeViewNode,
    TagSearchBoxTreeViewNode,
    TitleSearchBoxTreeViewNode,
    TitleTreeViewNode,
)
from barks_reader.ui.tree_view_manager import TreeViewManager
from barks_reader.ui.view_states import ViewStates


@pytest.fixture
def mock_dependencies() -> dict[str, MagicMock]:
    return {
        "background_views": MagicMock(),
        "view_state_manager": MagicMock(),
        "tree_view_screen": MagicMock(),
        "main_index_screen": MagicMock(),
        "speech_index_screen": MagicMock(),
        "update_title_func": MagicMock(return_value=True),
        "read_article_func": MagicMock(),
        "read_intro_compleat_barks_reader_func": MagicMock(),
        "set_tag_goto_page_checkbox_func": MagicMock(),
        "set_next_title_func": MagicMock(),
    }


@pytest.fixture
def tree_view_manager(mock_dependencies: dict[str, MagicMock]) -> TreeViewManager:
    # We need to mock the bind calls in __init__
    _mock_tree = mock_dependencies["tree_view_screen"].ids.reader_tree_view

    return TreeViewManager(**mock_dependencies)


class TestTreeViewManager:
    @pytest.mark.usefixtures("tree_view_manager")
    def test_init(self, mock_dependencies: dict[str, MagicMock]) -> None:
        mock_tree = mock_dependencies["tree_view_screen"].ids.reader_tree_view
        assert mock_tree.bind.call_count == 2  # noqa: PLR2004

    def test_setup_and_select_node_title_node(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        node = MagicMock(spec=TitleTreeViewNode)
        node.get_name.return_value = "Title Node"
        node.ids.num_label.parent.fanta_info = "Fanta Info"

        with patch.object(barks_reader.ui.tree_view_manager.Clock, "schedule_once") as mock_clock:
            tree_view_manager.setup_and_select_node(node)

            mock_dependencies["tree_view_screen"].deselect_and_close_open_nodes.assert_called_once()
            mock_dependencies["tree_view_screen"].open_all_parent_nodes.assert_called_with(node)
            mock_dependencies["tree_view_screen"].select_node.assert_called_with(node)

            mock_dependencies["set_next_title_func"].assert_called_with("Fanta Info", None)

            # Check scroll_to_node scheduled
            mock_clock.assert_called()

    def test_setup_and_select_node_button_node_trigger(
        self, tree_view_manager: TreeViewManager
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        node.saved_state = {"open": True}

        tree_view_manager.setup_and_select_node(node)
        node.trigger_action.assert_called_once()

    def test_setup_and_select_node_button_node_view_state(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        node.saved_state = {"open": False}

        with patch.object(
            barks_reader.ui.tree_view_manager,
            "get_view_state_from_node",
            return_value=(ViewStates.ON_INTRO_NODE, {}),
        ):
            tree_view_manager.setup_and_select_node(node)

            mock_dependencies["view_state_manager"].set_view_state.assert_called_with(
                ViewStates.ON_INTRO_NODE
            )

    def test_setup_and_select_node_search_box(self, tree_view_manager: TreeViewManager) -> None:
        node = MagicMock(spec=TitleSearchBoxTreeViewNode)
        node.saved_state = {"text": "search term"}

        with patch.object(barks_reader.ui.tree_view_manager.Clock, "schedule_once") as mock_clock:
            tree_view_manager.setup_and_select_node(node)

            node.press_search_box.assert_called_once()

            # Verify text setting lambda
            args, _ = mock_clock.call_args
            lambda_func = args[0]
            lambda_func(0)
            assert node.text == "search term"

    def test_deselect_and_close_open_nodes(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_dependencies["tree_view_screen"].deselect_and_close_open_nodes.return_value = 1

        tree_view_manager.deselect_and_close_open_nodes()

        mock_dependencies["view_state_manager"].set_view_state.assert_called_with(
            ViewStates.INITIAL
        )

    def test_go_back_to_previous_node(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_tree = mock_dependencies["tree_view_screen"].ids.reader_tree_view
        mock_dependencies["tree_view_screen"].deselect_and_close_open_nodes.return_value = 0

        # Case 1: No previous node
        mock_tree.previous_selected_node = None
        tree_view_manager.go_back_to_previous_node()
        mock_dependencies["tree_view_screen"].deselect_and_close_open_nodes.assert_called()

        # Case 2: Previous node exists
        prev_node = MagicMock(spec=ButtonTreeViewNode)
        mock_tree.previous_selected_node = prev_node

        # We need to mock setup_and_select_node to avoid recursion/complexity
        with patch.object(tree_view_manager, "setup_and_select_node") as mock_setup:
            tree_view_manager.go_back_to_previous_node()
            mock_setup.assert_called_with(prev_node)

    def test_on_node_collapsed(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)

        with patch.object(
            barks_reader.ui.tree_view_manager,
            "get_view_state_from_node",
            return_value=(ViewStates.ON_INTRO_NODE, {}),
        ):
            tree_view_manager.on_node_collapsed(MagicMock(), node)

            mock_dependencies["view_state_manager"].set_view_state.assert_called_with(
                ViewStates.ON_INTRO_NODE
            )

    def test_on_node_expanded(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        node.populate_callback = MagicMock()
        node.populated = False
        node.parent_node = MagicMock()
        node.parent_node.nodes = [node]  # No siblings to close

        with patch.object(  # noqa: SIM117
            barks_reader.ui.tree_view_manager,
            "get_view_state_from_node",
            return_value=(ViewStates.ON_INTRO_NODE, {}),
        ):
            # Mock _pin_parent_position_while_populating to avoid complex scroll logic
            with patch.object(
                tree_view_manager, "_pin_parent_position_while_populating"
            ) as mock_pin:
                tree_view_manager.on_node_expanded(MagicMock(), node)

                mock_pin.assert_called_with(node, run_populate=True)
                assert node.populated is True
                mock_dependencies["view_state_manager"].set_view_state.assert_called_with(
                    ViewStates.ON_INTRO_NODE
                )

    def test_close_siblings(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        sibling = MagicMock(spec=ButtonTreeViewNode)
        sibling.is_open = True

        parent = MagicMock()
        parent.nodes = [node, sibling]
        node.parent_node = parent

        # noinspection PyProtectedMember
        tree_view_manager._close_siblings(node)

        mock_dependencies["tree_view_screen"].ids.reader_tree_view.toggle_node.assert_called_with(
            sibling
        )

    def test_pin_parent_position_while_populating(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        scroll_view = mock_dependencies["tree_view_screen"].ids.scroll_view
        scroll_view.children = [MagicMock()]  # Container
        scroll_view.to_window.return_value = (0, 100)

        parent_node = MagicMock(spec=ButtonTreeViewNode)
        parent_node.text = "Parent Node"
        parent_node.to_window.return_value = (0, 200)
        parent_node.populate_callback = MagicMock()

        with patch.object(
            barks_reader.ui.tree_view_manager.Clock, "schedule_once"
        ) as mock_schedule:
            # noinspection PyProtectedMember
            tree_view_manager._pin_parent_position_while_populating(parent_node, run_populate=True)

            parent_node.populate_callback.assert_called_once()
            mock_schedule.assert_called_once()

    def test_on_title_row_button_pressed(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        button = MagicMock()
        button.parent.fanta_info = "Fanta Info"
        button.parent.parent_node = MagicMock()  # Not a tag node

        tree_view_manager.on_title_row_button_pressed(button)

        mock_dependencies["set_next_title_func"].assert_called_with("Fanta Info", None)

    def test_on_title_row_button_pressed_with_tag(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        button = MagicMock()
        button.parent.fanta_info = "Fanta Info"
        tag_node = MagicMock(spec=TagGroupStoryGroupTreeViewNode)
        tag_node.tag = "Tag"
        button.parent.parent_node = tag_node

        tree_view_manager.on_title_row_button_pressed(button)

        mock_dependencies["set_next_title_func"].assert_called_with("Fanta Info", "Tag")

    def test_on_title_search_box_title_changed(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        # Case 1: Empty title
        tree_view_manager.on_title_search_box_title_changed(MagicMock(), "")
        mock_dependencies["view_state_manager"].update_view_for_node.assert_called_with(
            ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET
        )

        # Case 2: Valid title
        mock_dependencies["update_title_func"].return_value = True
        tree_view_manager.on_title_search_box_title_changed(MagicMock(), "Title")
        mock_dependencies["view_state_manager"].update_view_for_node_with_title.assert_called_with(
            ViewStates.ON_TITLE_SEARCH_BOX_NODE
        )

    def test_on_tag_search_box_tag_changed(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        # Case 1: Empty tag
        tree_view_manager.on_tag_search_box_tag_changed(MagicMock(), "")
        mock_dependencies["view_state_manager"].update_view_for_node.assert_not_called()

        # Case 2: Tag changed, no current title
        instance = MagicMock(spec=TagSearchBoxTreeViewNode)
        instance.get_current_title.return_value = ""
        tree_view_manager.on_tag_search_box_tag_changed(instance, "Tag")
        mock_dependencies["view_state_manager"].update_view_for_node.assert_called_with(
            ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET
        )

    def test_on_article_node_pressed(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        mock_title = MagicMock()
        mock_title.name = "Title"
        with patch.object(
            barks_reader.ui.tree_view_manager,
            "get_view_state_and_article_title_from_node",
            return_value=(ViewStates.ON_INTRO_NODE, mock_title),
        ):
            tree_view_manager.on_article_node_pressed(node)
            mock_dependencies["read_article_func"].assert_called_with(
                mock_title, ViewStates.ON_INTRO_NODE
            )
