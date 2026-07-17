# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

import barks_reader.ui.tree_view_manager
import pytest
from barks_fantagraphics.barks_tags import TagGroups
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.navigation import (
    ArticleDestination,
    IntroDestination,
    MainIndexDestination,
    TagGroupDestination,
    TitleDestination,
    WikiIndexDestination,
)
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.ui.screen_bundle import ScreenBundle
from barks_reader.ui.tree_view_manager import TreeViewManager
from barks_reader.ui.tree_view_nodes import (
    ButtonTreeViewNode,
    TitleTreeViewNode,
)

if TYPE_CHECKING:
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo


def _fake_fanta() -> FantaComicBookInfo:
    """Sentinel fanta_info — identity-comparable, not type-checked at runtime."""
    return cast("FantaComicBookInfo", object())


@pytest.fixture
def screen_mocks() -> dict[str, MagicMock]:
    return {
        "tree_view": MagicMock(),
        "bottom_title_view": MagicMock(),
        "fun_image_view": MagicMock(),
        "main_index": MagicMock(),
        "speech_index": MagicMock(),
        "names_index": MagicMock(),
        "locations_index": MagicMock(),
        "statistics": MagicMock(),
        "history": MagicMock(),
        "search": MagicMock(),
    }


@pytest.fixture
def mock_screens(screen_mocks: dict[str, MagicMock]) -> ScreenBundle:
    return ScreenBundle(**screen_mocks)


@pytest.fixture
def mock_dependencies(mock_screens: ScreenBundle) -> dict[str, Any]:
    nav_coordinator = MagicMock()
    nav_coordinator.update_title.return_value = True
    return {
        "renderer": MagicMock(),
        "screens": mock_screens,
        "nav_coordinator": nav_coordinator,
    }


@pytest.fixture
def tree_view_manager(
    mock_dependencies: dict[str, Any],
    screen_mocks: dict[str, MagicMock],
) -> TreeViewManager:
    # We need to mock the bind calls in __init__
    _mock_tree = screen_mocks["tree_view"].ids.reader_tree_view

    return TreeViewManager(**mock_dependencies)


class TestTreeViewManager:
    @pytest.mark.usefixtures("tree_view_manager")
    def test_init(self, screen_mocks: dict[str, MagicMock]) -> None:
        mock_tree = screen_mocks["tree_view"].ids.reader_tree_view
        assert mock_tree.bind.call_count == 2  # noqa: PLR2004

    def test_setup_and_select_node_title_node(
        self,
        tree_view_manager: TreeViewManager,
        mock_dependencies: dict[str, Any],
        screen_mocks: dict[str, MagicMock],
    ) -> None:
        fanta = _fake_fanta()
        node = MagicMock(spec=TitleTreeViewNode)
        node.get_name.return_value = "Title Node"
        node.destination = TitleDestination(fanta_info=fanta)

        with patch.object(barks_reader.ui.tree_view_manager.Clock, "schedule_once") as mock_clock:
            tree_view_manager.setup_and_select_node(node)

            screen_mocks["tree_view"].deselect_and_close_open_nodes.assert_called_once()
            screen_mocks["tree_view"].open_all_parent_nodes.assert_called_with(node)
            screen_mocks["tree_view"].select_node.assert_called_with(node)

            mock_dependencies["nav_coordinator"].select_title.assert_called_once()

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
        node.destination = IntroDestination()

        tree_view_manager.setup_and_select_node(node)

        mock_dependencies["renderer"].render.assert_called_with(IntroDestination())

    def test_set_view_state_for_node_renders_destination(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        # The generic handler bound as on_press for the simple index/search/statistics
        # nodes: it renders the node's destination (replacing ~7 boilerplate handlers).
        node = MagicMock(spec=ButtonTreeViewNode)
        node.destination = MainIndexDestination()

        tree_view_manager.set_view_state_for_node(node)

        mock_dependencies["renderer"].render.assert_called_with(MainIndexDestination())

    def test_set_view_state_for_node_without_destination_raises(
        self, tree_view_manager: TreeViewManager
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        node.destination = None
        node.get_name.return_value = "Bad Node"

        with pytest.raises(RuntimeError, match="no destination"):
            tree_view_manager.set_view_state_for_node(node)

    def test_deselect_and_close_open_nodes(
        self,
        tree_view_manager: TreeViewManager,
        mock_dependencies: dict[str, MagicMock],
        screen_mocks: dict[str, MagicMock],
    ) -> None:
        screen_mocks["tree_view"].deselect_and_close_open_nodes.return_value = 1

        tree_view_manager.deselect_and_close_open_nodes()

        mock_dependencies["renderer"].render_state.assert_called_with(ViewStates.INITIAL)

    def test_go_back_to_previous_node(
        self,
        tree_view_manager: TreeViewManager,
        mock_dependencies: dict[str, MagicMock],
        screen_mocks: dict[str, MagicMock],
    ) -> None:
        mock_tree = screen_mocks["tree_view"].ids.reader_tree_view
        screen_mocks["tree_view"].deselect_and_close_open_nodes.return_value = 0

        # Case 1: No previous node
        mock_tree.previous_selected_node = None
        tree_view_manager.go_back_to_previous_node()
        screen_mocks["tree_view"].deselect_and_close_open_nodes.assert_called()

        # Case 2: Ordinary previous node -> re-select it, don't touch the wiki.
        prev_node = MagicMock(spec=ButtonTreeViewNode)
        prev_node.destination = IntroDestination()
        mock_tree.previous_selected_node = prev_node

        # We need to mock setup_and_select_node to avoid recursion/complexity
        with patch.object(tree_view_manager, "setup_and_select_node") as mock_setup:
            tree_view_manager.go_back_to_previous_node()
            mock_setup.assert_called_with(prev_node)
        mock_dependencies["nav_coordinator"].open_wiki.assert_not_called()

    def test_go_back_to_previous_node_reopens_wiki(
        self,
        tree_view_manager: TreeViewManager,
        mock_dependencies: dict[str, MagicMock],
        screen_mocks: dict[str, MagicMock],
    ) -> None:
        # Back to the 'Carl Barks Wiki' node re-opens the wiki reader (which resumes
        # its last-viewed page) instead of rendering the static index placeholder.
        mock_tree = screen_mocks["tree_view"].ids.reader_tree_view
        wiki_node = MagicMock(spec=ButtonTreeViewNode)
        wiki_node.destination = WikiIndexDestination()
        mock_tree.previous_selected_node = wiki_node

        with patch.object(tree_view_manager, "setup_and_select_node") as mock_setup:
            tree_view_manager.go_back_to_previous_node()

        screen_mocks["tree_view"].select_node.assert_called_with(wiki_node)
        mock_dependencies["nav_coordinator"].open_wiki.assert_called_once_with()
        mock_setup.assert_not_called()

    def test_on_node_collapsed(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        node.destination = IntroDestination()

        tree_view_manager.on_node_collapsed(MagicMock(), node)

        mock_dependencies["renderer"].render.assert_called_with(IntroDestination())

    def test_on_node_expanded(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        node.populate_callback = MagicMock()
        node.populated = False
        node.destination = IntroDestination()
        node.parent_node = MagicMock()
        node.parent_node.nodes = [node]  # No siblings to close

        # Mock the scroll pinner to avoid the complex scroll-stabilization logic.
        with patch.object(tree_view_manager._scroll_pinner, "pin_while_populating") as mock_pin:
            tree_view_manager.on_node_expanded(MagicMock(), node)

            mock_pin.assert_called_with(node, populate=node.populate_callback)
            assert node.populated is True
            mock_dependencies["renderer"].render.assert_called_with(IntroDestination())

    def test_close_siblings(
        self, tree_view_manager: TreeViewManager, screen_mocks: dict[str, MagicMock]
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        sibling = MagicMock(spec=ButtonTreeViewNode)
        sibling.is_open = True

        parent = MagicMock()
        parent.nodes = [node, sibling]
        node.parent_node = parent

        tree_view_manager._close_siblings(node)

        screen_mocks["tree_view"].ids.reader_tree_view.toggle_node.assert_called_with(sibling)

    def test_on_title_row_button_pressed(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        fanta = _fake_fanta()
        button = MagicMock()
        button.parent.destination = TitleDestination(fanta_info=fanta)
        button.parent.parent_node.destination = None

        tree_view_manager.on_title_row_button_pressed(button)

        mock_dependencies["nav_coordinator"].select_title.assert_called_once()

    def test_on_title_row_button_pressed_with_tag(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        fanta = _fake_fanta()
        button = MagicMock()
        button.parent.destination = TitleDestination(fanta_info=fanta)
        button.parent.parent_node.destination = TagGroupDestination(tag_group=TagGroups.AFRICA)

        tree_view_manager.on_title_row_button_pressed(button)

        mock_dependencies["nav_coordinator"].select_title.assert_called_once()

    def test_on_article_node_pressed(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        node.destination = ArticleDestination(
            view_state=ViewStates.ON_INTRO_NODE,
            article_title=Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION,
        )

        tree_view_manager.on_article_node_pressed(node)
        mock_dependencies["nav_coordinator"].read_article.assert_called_with(
            Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION, ViewStates.ON_INTRO_NODE
        )
