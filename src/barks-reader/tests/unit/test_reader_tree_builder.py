from __future__ import annotations

from unittest.mock import MagicMock, patch

import barks_reader.ui.reader_tree_builder
import pytest
from barks_fantagraphics.barks_tags import Tags
from barks_reader.core.navigation import (
    NodeKind,
    NodeRegistration,
    NodeSpec,
    PressAction,
    SeriesDestination,
    TagDestination,
    YearRangeDestination,
    YearRangeKind,
)
from barks_reader.ui.reader_tree_builder import ReaderTreeBuilder
from barks_reader.ui.tree_view_nodes import (
    MainTreeViewNode,
    StoryGroupTreeViewNode,
    TitleTreeViewNode,
    YearRangeTreeViewNode,
)


@pytest.fixture
def mock_dependencies() -> dict[str, MagicMock]:
    tree_view = MagicMock()
    # add_node returns the node it was given (like the real TreeView).
    tree_view.add_node.side_effect = lambda node, parent=None: node  # noqa: ARG005
    return {
        "reader_settings": MagicMock(),
        "reader_tree_view": tree_view,
        "reader_tree_events": MagicMock(),
        "tree_view_manager": MagicMock(),
        "title_lists": MagicMock(),
    }


@pytest.fixture
def tree_builder(mock_dependencies: dict[str, MagicMock]) -> ReaderTreeBuilder:
    return ReaderTreeBuilder(**mock_dependencies, include_one_pagers_in_chrono=False)


def _build_with_spec(tree_builder: ReaderTreeBuilder, *specs: NodeSpec) -> None:
    with patch.object(
        barks_reader.ui.reader_tree_builder, "build_reader_tree_spec", return_value=specs
    ):
        tree_builder.build_main_screen_tree()


class TestWalking:
    def test_builds_widgets_for_each_spec_kind(
        self, tree_builder: ReaderTreeBuilder, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        spec = NodeSpec(
            kind=NodeKind.MAIN,
            text="Root",
            children=(
                NodeSpec(kind=NodeKind.STORY_GROUP, text="Group"),
                NodeSpec(
                    kind=NodeKind.YEAR_RANGE,
                    text="1942-1946",
                    destination=YearRangeDestination(
                        start=1942, end=1946, kind=YearRangeKind.CHRONO
                    ),
                    year_range_kind=YearRangeKind.CHRONO,
                ),
            ),
        )

        _build_with_spec(tree_builder, spec)

        added_nodes = [
            call.args[0] for call in mock_dependencies["reader_tree_view"].add_node.call_args_list
        ]
        assert isinstance(added_nodes[0], MainTreeViewNode)
        assert added_nodes[0].text == "Root"
        assert isinstance(added_nodes[1], StoryGroupTreeViewNode)
        assert isinstance(added_nodes[2], YearRangeTreeViewNode)

        # Children are parented to the root node.
        _, kwargs = mock_dependencies["reader_tree_view"].add_node.call_args_list[1]
        assert kwargs["parent"] is added_nodes[0]

        mock_dependencies["reader_tree_events"].finished_building.assert_called_once()
        mock_dependencies["reader_tree_view"].bind.assert_called()

    def test_press_action_binds_manager_handler(
        self, tree_builder: ReaderTreeBuilder, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        spec = NodeSpec(kind=NodeKind.MAIN, text="Leaf", press_action=PressAction.OPEN_ARTICLE)

        _build_with_spec(tree_builder, spec)

        node = mock_dependencies["reader_tree_view"].add_node.call_args.args[0]
        handler = mock_dependencies["tree_view_manager"].on_article_node_pressed
        node.dispatch("on_press")
        handler.assert_called_once_with(node)

    def test_start_closed_sets_saved_state(
        self, tree_builder: ReaderTreeBuilder, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        spec = NodeSpec(kind=NodeKind.MAIN, text="Leaf", start_closed=True)

        _build_with_spec(tree_builder, spec)

        node = mock_dependencies["reader_tree_view"].add_node.call_args.args[0]
        assert node.saved_state["open"] is False

    def test_registration_hook_receives_created_node(
        self, tree_builder: ReaderTreeBuilder, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        spec = NodeSpec(kind=NodeKind.MAIN, text="Search", register_as=NodeRegistration.SEARCH)

        _build_with_spec(tree_builder, spec)

        node = mock_dependencies["reader_tree_view"].add_node.call_args.args[0]
        mock_dependencies["tree_view_manager"].on_search_node_created.assert_called_once_with(node)


class TestLookupNodeCollection:
    def test_chrono_year_range_nodes_are_indexed(self, tree_builder: ReaderTreeBuilder) -> None:
        spec = NodeSpec(
            kind=NodeKind.YEAR_RANGE,
            text="1942-1946",
            destination=YearRangeDestination(start=1942, end=1946, kind=YearRangeKind.CHRONO),
            year_range_kind=YearRangeKind.CHRONO,
        )

        _build_with_spec(tree_builder, spec)

        assert (1942, 1946) in tree_builder.chrono_year_range_nodes

    def test_cs_year_range_nodes_are_not_indexed_as_chrono(
        self, tree_builder: ReaderTreeBuilder
    ) -> None:
        spec = NodeSpec(
            kind=NodeKind.YEAR_RANGE,
            text="1942-1946",
            destination=YearRangeDestination(start=1942, end=1946, kind=YearRangeKind.CS),
            year_range_kind=YearRangeKind.CS,
        )

        _build_with_spec(tree_builder, spec)

        assert tree_builder.chrono_year_range_nodes == {}

    def test_series_nodes_are_indexed(self, tree_builder: ReaderTreeBuilder) -> None:
        spec = NodeSpec(
            kind=NodeKind.STORY_GROUP,
            text="Some Series",
            destination=SeriesDestination(series_name="Some Series"),
        )

        _build_with_spec(tree_builder, spec)

        assert "Some Series" in tree_builder.series_nodes


class TestDeferredPopulation:
    def test_lazy_children_defer_until_populate_callback(
        self, tree_builder: ReaderTreeBuilder, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        fanta_info = MagicMock()
        lazy_rows = (NodeSpec(kind=NodeKind.TITLE_ROW, fanta_info=fanta_info),)
        spec = NodeSpec(
            kind=NodeKind.STORY_GROUP,
            text="Tag",
            destination=TagDestination(tag=Tags.AIRPLANES),
            lazy_children=lambda: lazy_rows,
        )

        _build_with_spec(tree_builder, spec)

        node = mock_dependencies["reader_tree_view"].add_node.call_args.args[0]
        assert node.populate_callback is not None
        assert node.populated is False
        assert node.is_leaf is False
        # No title row created yet.
        assert mock_dependencies["reader_tree_view"].add_node.call_count == 1

        title_node = MagicMock()
        with patch.object(
            TitleTreeViewNode, "create_from_fanta_info", return_value=title_node
        ) as mock_create:
            node.populate_callback()

        mock_create.assert_called_once_with(
            fanta_info, mock_dependencies["tree_view_manager"].on_title_row_button_pressed
        )
        mock_dependencies["reader_tree_view"].add_node.assert_called_with(title_node, parent=node)

    def test_repopulate_on_expand_flag_defaults_to_false(
        self, tree_builder: ReaderTreeBuilder, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        spec = NodeSpec(
            kind=NodeKind.STORY_GROUP,
            text="Tag",
            destination=TagDestination(tag=Tags.AIRPLANES),
            lazy_children=lambda: (),
        )

        _build_with_spec(tree_builder, spec)

        node = mock_dependencies["reader_tree_view"].add_node.call_args.args[0]
        assert node.repopulate_on_expand is False

    def test_repopulate_on_expand_flag_is_copied_to_node(
        self, tree_builder: ReaderTreeBuilder, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        spec = NodeSpec(
            kind=NodeKind.STORY_GROUP,
            text="Surprise me",
            lazy_children=lambda: (),
            repopulate_on_expand=True,
        )

        _build_with_spec(tree_builder, spec)

        node = mock_dependencies["reader_tree_view"].add_node.call_args.args[0]
        assert node.repopulate_on_expand is True
        assert node.populate_callback is not None
        assert node.is_leaf is False
