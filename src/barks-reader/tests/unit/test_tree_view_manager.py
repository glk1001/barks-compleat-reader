# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, call, patch

import barks_reader.ui.tree_view_manager
import pytest
from barks_fantagraphics.barks_tags import TagGroups, Tags
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core import log_markers
from barks_reader.core.navigation import (
    ArticleDestination,
    ChronologicalDestination,
    DocumentDestination,
    IntroDestination,
    MainIndexDestination,
    RandomTitlesDestination,
    SearchDestination,
    SpeechIndexDestination,
    SpeechWordsDestination,
    StoriesDestination,
    TagDestination,
    TagGroupDestination,
    TagSearchDestination,
    TitleDestination,
    TitleSearchDestination,
    WikiIndexDestination,
)
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.testing import fake_fanta_info
from barks_reader.ui.tree_view_manager import TreeViewManager
from barks_reader.ui.tree_view_nodes import (
    BaseTreeViewNode,
    ButtonTreeViewNode,
    IntroTextTreeViewNode,
    ReaderTreeView,
    TitleTreeViewNode,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from barks_reader.core.navigation import Destination
    from barks_reader.ui.screen_bundle import ScreenBundle


@pytest.fixture
def mock_dependencies(screens: ScreenBundle) -> dict[str, Any]:
    nav_coordinator = MagicMock()
    return {
        "renderer": MagicMock(),
        "screens": screens,
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
        fanta = fake_fanta_info()
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

    @pytest.mark.parametrize("is_open", [True, False])
    def test_setting_up_a_button_node_never_presses_it(
        self, tree_view_manager: TreeViewManager, is_open: bool
    ) -> None:
        """A simulated press toggled the node it had just opened shut again."""
        node = MagicMock(spec=ButtonTreeViewNode)
        node.is_open = is_open
        node.destination = IntroDestination()

        tree_view_manager.setup_and_select_node(node)

        node.trigger_action.assert_not_called()

    def test_setting_up_a_button_node_left_open_shows_its_view(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        """No expansion fires for a node that is open already, so it is shown here."""
        node = MagicMock(spec=ButtonTreeViewNode)
        node.is_open = True
        node.destination = IntroDestination()

        tree_view_manager.setup_and_select_node(node)

        mock_dependencies["renderer"].render.assert_called_with(
            IntroDestination(), preserve_top_view=False, preserve_fun_view=False
        )

    def test_set_view_state_for_node_renders_destination(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        # The generic handler bound as on_press for the simple index/search/statistics
        # nodes: it renders the node's destination (replacing ~7 boilerplate handlers).
        node = MagicMock(spec=ButtonTreeViewNode)
        node.destination = MainIndexDestination()

        tree_view_manager.set_view_state_for_node(node)

        mock_dependencies["renderer"].render.assert_called_with(
            MainIndexDestination(), preserve_top_view=False, preserve_fun_view=False
        )

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
            # Under the images the node was left with, as a collapse keeps them.
            mock_setup.assert_called_with(prev_node, keep_images=True)
        mock_dependencies["nav_coordinator"].open_wiki.assert_not_called()

    def test_setting_up_a_node_for_go_back_keeps_the_images_through_its_renders(
        self,
        tree_view_manager: TreeViewManager,
        mock_dependencies: dict[str, Any],
        screen_mocks: dict[str, MagicMock],
        loguru_sink: list[str],
    ) -> None:
        """The node's view is rendered once, by its expansion, and keeps the images."""
        node = MagicMock(spec=ButtonTreeViewNode)
        node.populate_callback = None
        node.destination = SearchDestination()
        node.get_name.return_value = "Search"
        node.is_open = False
        node.nodes = []
        node.parent_node = MagicMock()
        node.parent_node.nodes = [node]
        tree_view = screen_mocks["tree_view"]
        tree_view.open_node.side_effect = lambda n: tree_view_manager.on_node_expanded(
            MagicMock(), n
        )
        renderer = mock_dependencies["renderer"]

        with patch.object(tree_view_manager._scroll_pinner, "pin_while_populating"):
            tree_view_manager.setup_and_select_node(node, keep_images=True)
        assert renderer.render.call_args_list == [
            call(SearchDestination(), preserve_top_view=True, preserve_fun_view=True),
        ]
        assert log_markers.NODE_IMAGES_KEPT.format(name="Search") in loguru_sink
        assert tree_view_manager._keep_images_for_caller is False

        # A plain setup (the saved-node restore at boot) picks fresh images as before.
        renderer.render.reset_mock()
        with patch.object(tree_view_manager._scroll_pinner, "pin_while_populating"):
            tree_view_manager.setup_and_select_node(node)
        assert renderer.render.call_args_list == [
            call(SearchDestination(), preserve_top_view=False, preserve_fun_view=False),
        ]

    def test_a_failed_open_on_go_back_leaves_later_renders_fresh(
        self,
        tree_view_manager: TreeViewManager,
        screen_mocks: dict[str, MagicMock],
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        node.get_name.return_value = "Search"
        screen_mocks["tree_view"].open_node.side_effect = RuntimeError("populate failed")

        with pytest.raises(RuntimeError, match="populate failed"):
            tree_view_manager.setup_and_select_node(node, keep_images=True)

        assert tree_view_manager._keep_images_for_caller is False
        assert tree_view_manager._opening_for_caller is False

    def test_go_back_to_a_node_left_open_keeps_the_images(
        self,
        tree_view_manager: TreeViewManager,
        mock_dependencies: dict[str, Any],
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        node.is_open = True
        node.destination = TitleSearchDestination()
        node.get_name.return_value = "Title Search"
        renderer = mock_dependencies["renderer"]

        tree_view_manager.setup_and_select_node(node, keep_images=True)

        renderer.render.assert_called_once_with(
            TitleSearchDestination(), preserve_top_view=True, preserve_fun_view=True
        )

        # A press of its own, outside Go Back, picks fresh images.
        renderer.render.reset_mock()
        tree_view_manager.set_view_state_for_node(node)
        renderer.render.assert_called_once_with(
            TitleSearchDestination(), preserve_top_view=False, preserve_fun_view=False
        )

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

    def test_go_back_to_a_chapter_reopens_it_where_it_was_left(
        self,
        tree_view_manager: TreeViewManager,
        mock_dependencies: dict[str, MagicMock],
        screen_mocks: dict[str, MagicMock],
    ) -> None:
        # Back after a chapter's Go to Story opens the chapter again, at the page the
        # story was picked from, not the chapter node's static view.
        mock_tree = screen_mocks["tree_view"].ids.reader_tree_view
        chapter_node = MagicMock(spec=ButtonTreeViewNode)
        chapter_node.destination = DocumentDestination(
            view_state=ViewStates.ON_INTRO_ILLUSTRATED_HISTORY_NODE,
            doc_dir=Path("/docs/illustrated-history/04-becoming-himself"),
            title="Becoming Himself",
        )
        mock_tree.previous_selected_node = chapter_node

        with (
            patch.object(tree_view_manager, "setup_and_select_node") as mock_setup,
            patch.object(tree_view_manager, "scroll_to_node") as mock_scroll,
        ):
            tree_view_manager.go_back_to_previous_node()

        # The tree as a fresh open leaves it, so the chapter's close lands on its node
        # and not on the story's branch it was left for.
        screen_mocks["tree_view"].deselect_and_close_open_nodes.assert_called_once_with()
        screen_mocks["tree_view"].open_all_parent_nodes.assert_called_once_with(chapter_node)
        screen_mocks["tree_view"].select_node.assert_called_with(chapter_node)
        mock_scroll.assert_called_once_with(chapter_node)
        mock_dependencies["nav_coordinator"].open_document.assert_called_once_with(
            Path("/docs/illustrated-history/04-becoming-himself"),
            "Becoming Himself",
            ViewStates.ON_INTRO_ILLUSTRATED_HISTORY_NODE,
            resume=True,
        )
        mock_setup.assert_not_called()

    def test_on_node_collapsed(
        self,
        tree_view_manager: TreeViewManager,
        mock_dependencies: dict[str, MagicMock],
        loguru_sink: list[str],
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        node.destination = IntroDestination()
        node.get_name.return_value = "Themes"

        with patch.object(tree_view_manager._scroll_pinner, "pin_while_collapsing") as pin:
            tree_view_manager.on_node_collapsed(MagicMock(), node)

        # The row stays put as its children go.
        pin.assert_called_once_with(node)
        # A collapse renders the node's view under the images already on show.
        mock_dependencies["renderer"].render.assert_called_with(
            IntroDestination(), preserve_top_view=True, preserve_fun_view=True
        )
        assert log_markers.NODE_IMAGES_KEPT.format(name="Themes") in loguru_sink

    def test_a_collapse_with_state_changes_suppressed_is_not_pinned(
        self, tree_view_manager: TreeViewManager
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        node.destination = IntroDestination()

        with (
            patch.object(tree_view_manager._scroll_pinner, "pin_while_collapsing") as pin,
            tree_view_manager.suppress_view_state_changes(),
        ):
            tree_view_manager.on_node_collapsed(MagicMock(), node)

        pin.assert_not_called()

    def test_scrolling_to_a_node_lets_the_pins_under_way_go(
        self, tree_view_manager: TreeViewManager, screen_mocks: dict[str, MagicMock]
    ) -> None:
        node = MagicMock()
        with (
            patch.object(tree_view_manager._scroll_pinner, "cancel_pending_pins") as let_go,
            patch.object(barks_reader.ui.tree_view_manager.Clock, "schedule_once") as mock_clock,
        ):
            tree_view_manager.scroll_to_node(node)
            mock_clock.call_args.args[0](0)

        let_go.assert_called_once_with()
        screen_mocks["tree_view"].scroll_to_node.assert_called_once_with(node)

    def test_on_node_expanded(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        node.populate_callback = MagicMock()
        node.populated = False
        node.repopulate_on_expand = False
        node.destination = IntroDestination()
        node.parent_node = MagicMock()
        node.parent_node.nodes = [node]  # No siblings to close

        # Mock the scroll pinner to avoid the complex scroll-stabilization logic.
        with patch.object(tree_view_manager._scroll_pinner, "pin_while_populating") as mock_pin:
            tree_view_manager.on_node_expanded(MagicMock(), node)

            # The node populates itself under the pin, and marks itself populated.
            mock_pin.assert_called_with(node, populate=node.ensure_populated)
            mock_dependencies["renderer"].render.assert_called_with(
                IntroDestination(), preserve_top_view=False, preserve_fun_view=False
            )

    def test_a_node_opened_under_suppression_is_tracked_but_shows_no_view(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        # No pin runs on this path to lift the overlay's suppression: it is lifted here.
        node = MagicMock(spec=ButtonTreeViewNode)
        overlay = cast("MagicMock", tree_view_manager._collapse_overlay)

        with (
            tree_view_manager.suppress_view_state_changes(),
            patch.object(tree_view_manager._scroll_pinner, "pin_while_populating") as mock_pin,
        ):
            tree_view_manager.on_node_expanded(MagicMock(), node)

        overlay.track_node.assert_called_once_with(node)
        overlay.end_suppression.assert_called_once_with()
        mock_pin.assert_not_called()
        mock_dependencies["renderer"].render.assert_not_called()

    def test_opening_search_selects_and_shows_its_title_search(
        self,
        tree_view_manager: TreeViewManager,
        screen_mocks: dict[str, MagicMock],
        mock_dependencies: dict[str, MagicMock],
        loguru_sink: list[str],
    ) -> None:
        children = []
        for name, destination in (
            ("Tags", TagSearchDestination()),
            ("Titles", TitleSearchDestination()),
        ):
            child = MagicMock(spec=ButtonTreeViewNode)
            child.destination = destination
            child.get_name.return_value = name
            children.append(child)
        tags, titles = children
        node = MagicMock(spec=ButtonTreeViewNode)
        node.populate_callback = None
        node.destination = SearchDestination()
        node.get_name.return_value = "Search"
        node.nodes = [tags, titles]  # found by its destination, not its place
        node.parent_node = MagicMock()
        node.parent_node.nodes = [node]

        with patch.object(tree_view_manager._scroll_pinner, "pin_while_populating"):
            tree_view_manager.on_node_expanded(MagicMock(), node)

        screen_mocks["tree_view"].select_node.assert_called_once_with(titles)
        mock_dependencies["renderer"].render.assert_called_once_with(
            TitleSearchDestination(), preserve_top_view=False, preserve_fun_view=False
        )
        assert log_markers.NODE_OPENED_ON_CHILD.format(name="Search", child="Titles") in loguru_sink

    def test_setup_and_select_search_keeps_search_selected(
        self,
        tree_view_manager: TreeViewManager,
        screen_mocks: dict[str, MagicMock],
        mock_dependencies: dict[str, MagicMock],
        loguru_sink: list[str],
    ) -> None:
        """Go Back (and the saved-node restore) land on Search itself, not its Titles.

        The open-on-child rule is for the user's own press on Search: a re-open on
        the caller's behalf would select Titles and then Search, leaving Titles as
        the previous node and rendering two views.
        """
        titles = MagicMock(spec=ButtonTreeViewNode)
        titles.destination = TitleSearchDestination()
        titles.get_name.return_value = "Titles"
        node = MagicMock(spec=ButtonTreeViewNode)
        node.populate_callback = None
        node.destination = SearchDestination()
        node.get_name.return_value = "Search"
        node.is_open = False
        node.nodes = [titles]
        node.parent_node = MagicMock()
        node.parent_node.nodes = [node]
        tree_view = screen_mocks["tree_view"]
        # The real tree fires on_node_expand from open_node.
        tree_view.open_node.side_effect = lambda n: tree_view_manager.on_node_expanded(
            MagicMock(), n
        )

        with patch.object(tree_view_manager._scroll_pinner, "pin_while_populating"):
            tree_view_manager.setup_and_select_node(node)

        tree_view.select_node.assert_called_once_with(node)
        rendered = [call.args[0] for call in mock_dependencies["renderer"].render.call_args_list]
        assert SearchDestination() in rendered
        assert TitleSearchDestination() not in rendered
        assert not any("opened on its child" in line for line in loguru_sink)

    def test_on_node_expanded_repopulates_flagged_node(
        self,
        tree_view_manager: TreeViewManager,
        screen_mocks: dict[str, MagicMock],
        loguru_sink: list[str],
    ) -> None:
        # A repopulate-on-expand node (the random-title nodes) rebuilds its
        # children on every expansion, even when already populated.
        mock_tree = screen_mocks["tree_view"].ids.reader_tree_view
        old_children = [MagicMock(spec=TitleTreeViewNode) for _ in range(2)]
        for child in old_children:
            child.destination = TitleDestination(fanta_info=fake_fanta_info())
        mock_tree.selected_node = None
        mock_tree.previous_selected_node = None

        node = MagicMock(spec=ButtonTreeViewNode)
        node.populate_callback = MagicMock()
        node.populated = True
        node.repopulate_on_expand = True
        node.destination = IntroDestination()
        node.nodes = old_children
        node.parent_node = MagicMock()
        node.parent_node.nodes = [node]  # No siblings to close

        with patch.object(tree_view_manager._scroll_pinner, "pin_while_populating") as mock_pin:
            tree_view_manager.on_node_expanded(MagicMock(), node)

        populate = mock_pin.call_args.kwargs["populate"]
        assert populate is not node.populate_callback
        populate()

        for child in old_children:
            mock_tree.remove_node.assert_any_call(child)
        node.populate_callback.assert_called_once()
        assert any(m.startswith("Repopulated '") for m in loguru_sink)

    def test_clear_and_repopulate_detaches_selection_tracking(
        self, tree_view_manager: TreeViewManager, screen_mocks: dict[str, MagicMock]
    ) -> None:
        # If a stale child is the selected or go-back node, tracking must be
        # moved off the soon-to-be-removed widget before removal.
        mock_tree = screen_mocks["tree_view"].ids.reader_tree_view
        selected_child = MagicMock(spec=TitleTreeViewNode)
        previous_child = MagicMock(spec=TitleTreeViewNode)
        mock_tree.selected_node = selected_child
        mock_tree.previous_selected_node = previous_child

        node = MagicMock(spec=ButtonTreeViewNode)
        node.populate_callback = MagicMock()
        node.nodes = [selected_child, previous_child]

        tree_view_manager._clear_and_repopulate(node)

        mock_tree.deselect_node.assert_called_once()
        assert mock_tree.previous_selected_node is node
        mock_tree.set_back_node.assert_called_once_with(node)
        assert mock_tree.remove_node.call_count == len(node.nodes)
        node.populate_callback.assert_called_once()

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
        fanta = fake_fanta_info()
        button = MagicMock()
        button.parent = MagicMock(name="its row")  # the widget tree's: a row, not the node
        button.node.destination = TitleDestination(fanta_info=fanta)
        button.node.parent_node.destination = None

        tree_view_manager.on_title_row_button_pressed(button)

        mock_dependencies["nav_coordinator"].select_title.assert_called_once()
        kwargs = mock_dependencies["nav_coordinator"].select_title.call_args.kwargs
        assert kwargs["preserve_top_view"] is False

    def test_on_title_row_button_pressed_with_tag(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        fanta = fake_fanta_info()
        button = MagicMock()
        button.node.destination = TitleDestination(fanta_info=fanta)
        button.node.parent_node.destination = TagGroupDestination(tag_group=TagGroups.AFRICA)

        tree_view_manager.on_title_row_button_pressed(button)

        mock_dependencies["nav_coordinator"].select_title.assert_called_once()

    def test_on_title_row_button_pressed_under_random_titles_keeps_top_view(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        # A pick under a 'Choose for me' node keeps the themed top view
        # (character/decade backdrop) instead of re-rolling a generic image.
        fanta = fake_fanta_info()
        button = MagicMock()
        button.node.destination = TitleDestination(fanta_info=fanta)
        button.node.parent_node.destination = RandomTitlesDestination(tag=Tags.SCROOGE_NOT_IN_US)

        tree_view_manager.on_title_row_button_pressed(button)

        kwargs = mock_dependencies["nav_coordinator"].select_title.call_args.kwargs
        assert kwargs["preserve_top_view"] is True

    def test_render_title_node_without_scroll(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, Any]
    ) -> None:
        fanta = fake_fanta_info()
        node = MagicMock(spec=TitleTreeViewNode)
        node.destination = TitleDestination(fanta_info=fanta)

        with patch.object(barks_reader.ui.tree_view_manager.Clock, "schedule_once") as mock_clock:
            tree_view_manager.render_title_node(node)

        target = mock_dependencies["nav_coordinator"].select_title.call_args.args[0]
        assert target.fanta_info is fanta
        mock_clock.assert_not_called()

    def test_render_title_node_under_random_titles_keeps_top_view(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, Any]
    ) -> None:
        # Arrow-key navigation renders titles through render_title_node: picks
        # under a 'Choose for me' node keep the themed top view there too.
        node = MagicMock(spec=TitleTreeViewNode)
        node.destination = TitleDestination(fanta_info=fake_fanta_info())
        node.parent_node.destination = RandomTitlesDestination(tag=Tags.SCROOGE_NOT_IN_US)

        tree_view_manager.render_title_node(node)

        kwargs = mock_dependencies["nav_coordinator"].select_title.call_args.kwargs
        assert kwargs["preserve_top_view"] is True

    def test_render_title_node_under_a_tag_offers_the_tags_pages(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, Any]
    ) -> None:
        # Arrow keys and the saved-node restore at boot render titles here: one under a
        # tag carries the tag, as a click on its row does, so its goto page is offered.
        node = MagicMock(spec=TitleTreeViewNode)
        node.destination = TitleDestination(fanta_info=fake_fanta_info())
        node.parent_node.destination = TagDestination(tag=Tags.AWFULTONIANS)

        tree_view_manager.render_title_node(node)

        target = mock_dependencies["nav_coordinator"].select_title.call_args.args[0]
        assert target.tag is Tags.AWFULTONIANS

    def test_render_title_node_outside_a_tag_carries_none(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, Any]
    ) -> None:
        node = MagicMock(spec=TitleTreeViewNode)
        node.destination = TitleDestination(fanta_info=fake_fanta_info())
        node.parent_node = None

        tree_view_manager.render_title_node(node)

        target = mock_dependencies["nav_coordinator"].select_title.call_args.args[0]
        assert target.tag is None

    def test_render_title_node_with_scroll(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, Any]
    ) -> None:
        node = MagicMock(spec=TitleTreeViewNode)
        node.destination = TitleDestination(fanta_info=fake_fanta_info())

        with patch.object(barks_reader.ui.tree_view_manager.Clock, "schedule_once") as mock_clock:
            tree_view_manager.render_title_node(node, scroll_to=True)

        mock_dependencies["nav_coordinator"].select_title.assert_called_once()
        mock_clock.assert_called_once()

    def test_activate_node_title_selects_renders_and_scrolls(
        self,
        tree_view_manager: TreeViewManager,
        mock_dependencies: dict[str, Any],
        screen_mocks: dict[str, MagicMock],
    ) -> None:
        node = MagicMock(spec=TitleTreeViewNode)
        node.destination = TitleDestination(fanta_info=fake_fanta_info())

        with patch.object(barks_reader.ui.tree_view_manager.Clock, "schedule_once") as mock_clock:
            tree_view_manager.activate_node(node)

        screen_mocks["tree_view"].select_node.assert_called_with(node)
        mock_dependencies["nav_coordinator"].select_title.assert_called_once()
        mock_clock.assert_called_once()

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

    def test_on_document_node_pressed(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        node.destination = DocumentDestination(
            view_state=ViewStates.ON_INTRO_ILLUSTRATED_HISTORY_NODE,
            doc_dir=Path("/docs/illustrated-history/04-becoming-himself"),
            title="Becoming Himself",
        )

        tree_view_manager.on_document_node_pressed(node)
        mock_dependencies["nav_coordinator"].open_document.assert_called_with(
            Path("/docs/illustrated-history/04-becoming-himself"),
            "Becoming Himself",
            ViewStates.ON_INTRO_ILLUSTRATED_HISTORY_NODE,
            resume=True,
        )

    def test_on_node_expanded_with_one_title_child_selects_that_title(
        self,
        tree_view_manager: TreeViewManager,
        mock_dependencies: dict[str, Any],
        screen_mocks: dict[str, MagicMock],
        loguru_sink: list[str],
    ) -> None:
        # A tag holding a single title skips the tag's own view and goes straight
        # to the title, keeping the top view (no fun-image flicker in between).
        fanta = fake_fanta_info()
        only_title = MagicMock(spec=TitleTreeViewNode)
        only_title.destination = TitleDestination(fanta_info=fanta)

        node = MagicMock(spec=ButtonTreeViewNode)
        node.get_name.return_value = "Africa"
        node.populate_callback = None
        node.repopulate_on_expand = False
        node.destination = TagGroupDestination(tag_group=TagGroups.AFRICA)
        node.nodes = [only_title]
        node.parent_node = None

        with patch.object(tree_view_manager._scroll_pinner, "pin_while_populating"):
            tree_view_manager.on_node_expanded(MagicMock(), node)

        screen_mocks["tree_view"].select_node.assert_called_once_with(only_title)
        select_title = mock_dependencies["nav_coordinator"].select_title
        target = select_title.call_args.args[0]
        assert target.fanta_info is fanta
        assert target.tag is TagGroups.AFRICA
        assert select_title.call_args.kwargs["preserve_top_view"] is True
        mock_dependencies["renderer"].render.assert_not_called()
        assert "Single-child node 'Africa': auto-selecting only title." in loguru_sink

    def test_close_siblings_of_a_root_node_toggles_nothing(
        self, tree_view_manager: TreeViewManager, screen_mocks: dict[str, MagicMock]
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        node.parent_node = None

        tree_view_manager._close_siblings(node)

        screen_mocks["tree_view"].ids.reader_tree_view.toggle_node.assert_not_called()

    @pytest.mark.usefixtures("tree_view_manager")
    def test_collapse_overlay_press_on_open_node_closes_selects_and_scrolls(
        self, screen_mocks: dict[str, MagicMock]
    ) -> None:
        tree_view = screen_mocks["tree_view"]
        on_pressed = tree_view.setup_collapse_overlay.call_args.args[0]
        node = MagicMock(spec=ButtonTreeViewNode)
        node.is_open = True

        with patch.object(barks_reader.ui.tree_view_manager.Clock, "schedule_once") as mock_clock:
            on_pressed(node)
            mock_clock.call_args.args[0](0)

        tree_view.ids.reader_tree_view.toggle_node.assert_called_once_with(node)
        tree_view.select_node.assert_called_once_with(node)
        tree_view.scroll_to_node.assert_called_once_with(node)

    def test_collapse_overlay_press_pins_the_collapse_then_lets_it_go(
        self, tree_view_manager: TreeViewManager, screen_mocks: dict[str, MagicMock]
    ) -> None:
        """The node is scrolled off the top: the scroll brings it back, no pin holds it."""
        tree_view = screen_mocks["tree_view"]
        on_pressed = tree_view.setup_collapse_overlay.call_args.args[0]
        node = MagicMock(spec=ButtonTreeViewNode)
        node.is_open = True
        node.destination = IntroDestination()
        events: list[str] = []
        tree_view.ids.reader_tree_view.toggle_node.side_effect = lambda n: (
            tree_view_manager.on_node_collapsed(MagicMock(), n)
        )

        with (
            patch.object(
                tree_view_manager._scroll_pinner,
                "pin_while_collapsing",
                side_effect=lambda _n: events.append("pinned"),
            ),
            patch.object(
                tree_view_manager._scroll_pinner,
                "cancel_pending_pins",
                side_effect=lambda: events.append("let go"),
            ),
            patch.object(barks_reader.ui.tree_view_manager.Clock, "schedule_once"),
        ):
            on_pressed(node)

        assert events == ["pinned", "let go"]

    @pytest.mark.usefixtures("tree_view_manager")
    def test_collapse_overlay_press_on_closed_node_only_selects_and_scrolls(
        self, screen_mocks: dict[str, MagicMock]
    ) -> None:
        tree_view = screen_mocks["tree_view"]
        on_pressed = tree_view.setup_collapse_overlay.call_args.args[0]
        node = MagicMock(spec=ButtonTreeViewNode)
        node.is_open = False

        with patch.object(barks_reader.ui.tree_view_manager.Clock, "schedule_once") as mock_clock:
            on_pressed(node)
            mock_clock.call_args.args[0](0)

        tree_view.ids.reader_tree_view.toggle_node.assert_not_called()
        tree_view.select_node.assert_called_once_with(node)
        tree_view.scroll_to_node.assert_called_once_with(node)

    def test_search_node_is_the_one_created(self, tree_view_manager: TreeViewManager) -> None:
        assert tree_view_manager.search_node is None
        node = MagicMock()

        tree_view_manager.on_search_node_created(node)

        assert tree_view_manager.search_node is node


class TestNodesThatDoNothingMore:
    """A node with nothing to do on selection is selected, and that is all."""

    def test_activating_an_intro_text_node_only_selects_it(
        self,
        tree_view_manager: TreeViewManager,
        mock_dependencies: dict[str, Any],
        screen_mocks: dict[str, MagicMock],
    ) -> None:
        node = MagicMock(spec=IntroTextTreeViewNode)
        tree_view_manager.activate_node(node)
        screen_mocks["tree_view"].select_node.assert_called_once_with(node)
        mock_dependencies["nav_coordinator"].select_title.assert_not_called()
        mock_dependencies["renderer"].render.assert_not_called()

    def test_setting_up_an_intro_text_node_opens_and_selects_it_only(
        self,
        tree_view_manager: TreeViewManager,
        mock_dependencies: dict[str, Any],
        screen_mocks: dict[str, MagicMock],
    ) -> None:
        node = MagicMock(spec=IntroTextTreeViewNode)
        tree_view_manager.setup_and_select_node(node)
        screen_mocks["tree_view"].open_node.assert_called_once_with(node)
        screen_mocks["tree_view"].select_node.assert_called_once_with(node)
        mock_dependencies["nav_coordinator"].select_title.assert_not_called()
        mock_dependencies["renderer"].render.assert_not_called()

    def test_an_open_button_node_with_no_destination_renders_nothing(
        self, tree_view_manager: TreeViewManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        node = MagicMock(spec=ButtonTreeViewNode)
        node.is_open = True
        node.destination = None

        tree_view_manager.setup_and_select_node(node)

        mock_dependencies["renderer"].render.assert_not_called()

    def test_going_to_a_node_without_scrolling_selects_it_next_frame(
        self, tree_view_manager: TreeViewManager, screen_mocks: dict[str, MagicMock]
    ) -> None:
        node = MagicMock()
        with (
            patch.object(barks_reader.ui.tree_view_manager.Clock, "schedule_once") as mock_clock,
            patch.object(tree_view_manager, "scroll_to_node") as scroll,
        ):
            tree_view_manager.goto_node(node)
            mock_clock.call_args.args[0](0)

        screen_mocks["tree_view"].select_node.assert_called_once_with(node)
        scroll.assert_not_called()

    def test_the_speech_words_node_is_the_one_created(
        self, tree_view_manager: TreeViewManager
    ) -> None:
        assert tree_view_manager.speech_words_node is None
        words = MagicMock()
        tree_view_manager.on_speech_words_node_created(words)
        assert tree_view_manager.speech_words_node is words


class _TreeScreen:
    """The tree-view screen's node methods over a real tree, as TreeViewScreen has them."""

    def __init__(self, tree: ReaderTreeView) -> None:
        self.ids = MagicMock()
        self.ids.reader_tree_view = tree
        self._tree = tree

    def setup_collapse_overlay(self, _on_pressed: object) -> None:
        pass

    def select_node(self, node: BaseTreeViewNode) -> None:
        self._tree.select_node(node)

    def open_node(self, node: BaseTreeViewNode) -> None:
        if not node.is_open:
            self._tree.toggle_node(node)

    def open_all_parent_nodes(self, node: BaseTreeViewNode) -> None:
        parents = []
        parent = node.parent_node
        while isinstance(parent, BaseTreeViewNode):
            parents.append(parent)
            parent = parent.parent_node
        for parent in reversed(parents):
            self.open_node(parent)

    def deselect_and_close_open_nodes(self) -> int:
        count = 0
        for node in list(self._tree.iterate_all_nodes()):
            if node is not self._tree.root and node.is_open:
                self._tree.toggle_node(node)
                count += 1
        return count

    def scroll_to_node(self, node: BaseTreeViewNode) -> None:
        pass


class TestPressesOnARealTree:
    """Real nodes in a real tree, laid out: a mock node's press toggles nothing.

    Go Back to an open group node passed every mock-node test while the simulated
    press in it shut the node again (2026-11-13).
    """

    @pytest.fixture
    def tree(self) -> ReaderTreeView:
        return ReaderTreeView(hide_root=True)

    @pytest.fixture
    def manager(
        self, tree: ReaderTreeView, mock_dependencies: dict[str, Any]
    ) -> Generator[TreeViewManager]:
        screens = MagicMock()
        screens.tree_view = _TreeScreen(tree)
        manager = TreeViewManager(
            renderer=mock_dependencies["renderer"],
            screens=screens,
            nav_coordinator=mock_dependencies["nav_coordinator"],
        )
        with (
            patch.object(manager._scroll_pinner, "pin_while_populating"),
            patch.object(manager._scroll_pinner, "pin_while_collapsing"),
            patch.object(manager._scroll_pinner, "cancel_pending_reveals"),
        ):
            yield manager

    @staticmethod
    def _add(
        tree: ReaderTreeView,
        text: str,
        destination: Destination,
        parent: ButtonTreeViewNode | None = None,
    ) -> ButtonTreeViewNode:
        node = ButtonTreeViewNode(text=text, destination=destination)
        tree.add_node(node, parent)
        return node

    @staticmethod
    def _lay_out(tree: ReaderTreeView) -> None:
        """Put the visible rows under the tree, as a frame does: a press then finds it."""
        tree._do_layout()

    @pytest.fixture
    def speech(self, tree: ReaderTreeView) -> ButtonTreeViewNode:
        return self._add(tree, "Speech Bubble Index", SpeechIndexDestination())

    @pytest.fixture
    def words(self, tree: ReaderTreeView, speech: ButtonTreeViewNode) -> ButtonTreeViewNode:
        return self._add(tree, "Words", SpeechWordsDestination(), parent=speech)

    def test_go_back_to_a_group_node_leaves_it_open_and_shows_it_once(
        self, tree: ReaderTreeView, manager: TreeViewManager, mock_dependencies: dict[str, Any]
    ) -> None:
        stories = self._add(tree, "The Stories", StoriesDestination())
        self._add(tree, "Chronological", ChronologicalDestination(), parent=stories)
        self._lay_out(tree)

        manager.setup_and_select_node(stories, keep_images=True)

        assert stories.is_open
        assert tree.selected_node is stories
        mock_dependencies["renderer"].render.assert_called_once_with(
            StoriesDestination(), preserve_top_view=True, preserve_fun_view=True
        )

    def test_pressing_the_speech_index_opens_it_on_words(
        self,
        tree: ReaderTreeView,
        manager: TreeViewManager,
        speech: ButtonTreeViewNode,
        words: ButtonTreeViewNode,
        mock_dependencies: dict[str, Any],
    ) -> None:
        self._lay_out(tree)

        manager.activate_node(speech)

        assert speech.is_open
        assert tree.selected_node is words
        mock_dependencies["renderer"].render.assert_called_once_with(
            SpeechWordsDestination(), preserve_top_view=False, preserve_fun_view=False
        )

    def test_collapsing_the_speech_index_keeps_it_selected_under_the_same_images(
        self,
        tree: ReaderTreeView,
        manager: TreeViewManager,
        speech: ButtonTreeViewNode,
        words: ButtonTreeViewNode,
        mock_dependencies: dict[str, Any],
        loguru_sink: list[str],
    ) -> None:
        """Its press once selected Words, the row the collapse was about to hide."""
        self._lay_out(tree)
        manager.activate_node(speech)
        self._lay_out(tree)
        renderer = mock_dependencies["renderer"]
        renderer.render.reset_mock()

        manager.activate_node(speech)

        assert not speech.is_open
        assert tree.selected_node is speech
        assert tree.selected_node is not words
        renderer.render.assert_called_once_with(
            SpeechIndexDestination(), preserve_top_view=True, preserve_fun_view=True
        )
        renderer.render_state.assert_not_called()
        assert log_markers.NODE_COLLAPSED.format(name="Speech Bubble Index") in loguru_sink

    def test_a_second_press_of_a_leaf_does_not_collapse_it(
        self,
        tree: ReaderTreeView,
        manager: TreeViewManager,
        speech: ButtonTreeViewNode,
        words: ButtonTreeViewNode,
        mock_dependencies: dict[str, Any],
        loguru_sink: list[str],
    ) -> None:
        words.bind(on_press=manager.set_view_state_for_node)
        with manager.suppress_view_state_changes():
            tree.toggle_node(speech)
        self._lay_out(tree)
        renderer = mock_dependencies["renderer"]

        manager.activate_node(words)
        assert words.is_open
        renderer.render.reset_mock()
        manager.activate_node(words)

        assert words.is_open
        assert log_markers.NODE_COLLAPSED.format(name="Words") not in loguru_sink
        # The press shows the view afresh; a collapse kept the images.
        renderer.render.assert_called_once_with(
            SpeechWordsDestination(), preserve_top_view=False, preserve_fun_view=False
        )
