# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import barks_reader.ui.tree_view_nodes
import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.navigation import TitleDestination
from barks_reader.core.reader_formatter import ReaderFormatter
from barks_reader.ui.tree_view_nodes import (
    BaseTreeViewNode,
    ButtonTreeViewNode,
    IntroTextTreeViewNode,
    ReaderTreeBuilderEventDispatcher,
    ReaderTreeView,
    TitleTreeViewNode,
)
from kivy.lang.parser import Parser


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

    def test_go_back_returns_to_the_node_it_was_given(self) -> None:
        tree = ReaderTreeView()
        back_node, next_node = MagicMock(), MagicMock()
        back_node.get_name.return_value = "Back"
        next_node.get_name.return_value = "Next"

        tree.set_back_node(back_node)
        tree.on_selected_node(tree, next_node)

        assert tree.previous_selected_node == back_node


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

    def test_a_press_shuts_an_open_node_that_has_children(self) -> None:
        node = ButtonTreeViewNode()
        node.is_open = True
        node.nodes = [ButtonTreeViewNode()]
        mock_tree = MagicMock()

        with patch.object(node, "_get_nodes_treeview", return_value=mock_tree):
            node.on_press()
        mock_tree.toggle_node.assert_called_once_with(node)

    def test_a_press_shuts_an_open_node_whose_children_are_made_on_expansion(self) -> None:
        node = ButtonTreeViewNode()
        node.is_open = True
        node.populate_callback = MagicMock()
        mock_tree = MagicMock()

        with patch.object(node, "_get_nodes_treeview", return_value=mock_tree):
            node.on_press()
        mock_tree.toggle_node.assert_called_once_with(node)

    def test_a_press_leaves_an_open_leaf_open(self) -> None:
        """Toggled shut, every second press of a leaf went down the collapse path."""
        node = ButtonTreeViewNode()
        node.is_open = True
        mock_tree = MagicMock()

        with patch.object(node, "_get_nodes_treeview", return_value=mock_tree):
            node.on_press()
        mock_tree.toggle_node.assert_not_called()

    def test_its_tree_is_found_through_the_rows_between(self) -> None:
        """A node can sit in a layout inside the tree, not straight under it."""
        tree = ReaderTreeView()
        node = SimpleNamespace(parent=SimpleNamespace(parent=tree))
        assert ButtonTreeViewNode._get_nodes_treeview(node) is tree  # ty: ignore[invalid-argument-type]

    def test_a_node_in_no_tree_is_not_toggled(self) -> None:
        node = ButtonTreeViewNode()
        assert ButtonTreeViewNode._get_nodes_treeview(node) is None
        node.on_press()  # nothing to toggle, and no error

    def test_ensure_populated_populates_once(self) -> None:
        """A second goto into a year range must not add its titles again."""
        node = ButtonTreeViewNode()
        node.populate_callback = MagicMock()

        node.ensure_populated()
        node.ensure_populated()

        node.populate_callback.assert_called_once_with()
        assert node.populated is True

    def test_ensure_populated_without_a_callback_does_nothing(self) -> None:
        node = ButtonTreeViewNode()
        node.ensure_populated()
        assert node.populated is False


class TestNodeNames:
    """The names the selection log line gives the rows that are not titles."""

    def test_a_plain_node_has_no_name_of_its_own(self) -> None:
        assert BaseTreeViewNode().get_name() == "<unknown>"

    def test_a_playlist_intro_is_named_for_what_it_is_and_cannot_be_selected(self) -> None:
        node = IntroTextTreeViewNode()
        assert node.get_name() == "<playlist-intro>"
        assert node.no_selection is True


class TestReaderTreeViewRule:
    def test_the_tree_leaves_its_minimum_height_to_its_layout(self) -> None:
        """The kv bound minimum_height to the height the builder binds to minimum_height."""
        kv_file = Path(barks_reader.ui.tree_view_nodes.__file__).parent / "reader-tree-view.kv"
        parsed = Parser(content=kv_file.read_text(encoding="utf-8"), filename=str(kv_file))
        [tree_rule] = [rule for _sel, rule in parsed.rules if rule.name == "<ReaderTreeView>"]

        assert "minimum_height" not in tree_rule.properties


def _fanta_info(title: Titles = Titles.LOST_IN_THE_ANDES) -> MagicMock:
    info = MagicMock()
    info.fanta_chronological_number = 7
    info.comic_book_info.title = title
    info.comic_book_info.get_display_title.return_value = "Lost in the Andes!"
    return info


class TestATitleNodeBuiltForReal:
    """The node's own constructor runs: the tests below it patch it away."""

    def test_it_keeps_its_story_and_goes_to_that_story(self) -> None:
        info = _fanta_info()

        node = TitleTreeViewNode(info)

        assert node.fanta_info is info
        assert node.destination == TitleDestination(fanta_info=info)
        assert node.saved_state == {}

    def test_a_destination_handed_in_is_kept(self) -> None:
        destination = TitleDestination(fanta_info=_fanta_info(Titles.CHRISTMAS_ON_BEAR_MOUNTAIN))

        node = TitleTreeViewNode(_fanta_info(), destination=destination)

        assert node.destination is destination

    def test_it_is_named_by_its_title(self) -> None:
        node = TitleTreeViewNode(_fanta_info(Titles.LOST_IN_THE_ANDES))

        assert node.get_title() is Titles.LOST_IN_THE_ANDES
        assert node.get_name() == "LOST_IN_THE_ANDES"


class TestATitleNodesRow:
    """What `create_from_fanta_info` writes into the row, and what a press reaches."""

    @pytest.fixture
    def issue_info(self) -> Any:  # noqa: ANN401
        with patch.object(
            ReaderFormatter, "get_issue_info", return_value="FC 223"
        ) as get_issue_info:
            yield get_issue_info

    @staticmethod
    def _create(info: MagicMock, on_press: MagicMock, *, footnote: bool) -> TitleTreeViewNode:
        app = MagicMock()
        app.font_manager.tree_view_issue_label_font_size = 11

        def init(self: TitleTreeViewNode, fanta_info: Any, **_kwargs: object) -> None:  # noqa: ANN401
            self.fanta_info = fanta_info
            self.ids = {
                "num_label": MagicMock(),
                "title_label": MagicMock(),
                "issue_label": MagicMock(),
            }

        with (
            patch.object(barks_reader.ui.tree_view_nodes.App, "get_running_app", return_value=app),
            patch.object(
                barks_reader.ui.tree_view_nodes, "title_needs_footnote", return_value=footnote
            ),
            patch.object(TitleTreeViewNode, "__init__", autospec=True, side_effect=init),
        ):
            return TitleTreeViewNode.create_from_fanta_info(info, on_press)

    def test_the_row_shows_the_number_the_title_and_the_issue(self, issue_info: MagicMock) -> None:
        node = self._create(_fanta_info(), MagicMock(), footnote=False)

        assert node.ids.num_label.text == "7"
        assert node.ids.title_label.text == "Lost in the Andes!"
        assert node.ids.issue_label.text == "FC 223"
        assert issue_info.call_count == 1

    def test_every_part_of_the_row_is_bound_to_the_press(self, issue_info: MagicMock) -> None:
        del issue_info
        on_press = MagicMock()

        node = self._create(_fanta_info(), on_press, footnote=False)

        for label in (node.ids.num_label, node.ids.title_label, node.ids.issue_label):
            label.bind.assert_called_once_with(on_press=on_press)

    def test_a_title_with_no_footnote_asks_for_none(self, issue_info: MagicMock) -> None:
        info = _fanta_info()

        self._create(info, MagicMock(), footnote=False)

        assert issue_info.call_args.args[:3] == (info, False, 0)

    def test_a_footnoted_title_gets_its_mark_at_twice_the_issue_size(
        self, issue_info: MagicMock
    ) -> None:
        info = _fanta_info()

        self._create(info, MagicMock(), footnote=True)

        assert issue_info.call_args.args[:3] == (info, True, 22)


class TestTitleTreeViewNode:
    def test_its_row_widgets_name_the_node_and_keep_their_real_parent(self) -> None:
        """The kv set each one's `parent` to the node, over the row it sits in."""
        kv_file = Path(barks_reader.ui.tree_view_nodes.__file__).parent / "reader-tree-view.kv"
        parsed = Parser(content=kv_file.read_text(encoding="utf-8"), filename=str(kv_file))
        [node_rule] = [rule for _sel, rule in parsed.rules if rule.name == "<TitleTreeViewNode>"]
        widgets = [widget for row in node_rule.children for widget in row.children]

        assert len(widgets) == 6  # noqa: PLR2004  # two rows of three
        assert all(widget.properties["node"].value == "root" for widget in widgets)
        assert not any("parent" in widget.properties for widget in widgets)

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
