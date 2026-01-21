# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_tags import TagCategories, TagGroups, Tags
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.fanta_comics_info import SERIES_CS
from barks_reader.reader_tree_builder import ReaderTreeBuilder
from barks_reader.reader_ui_classes import (
    MainTreeViewNode,
    TagGroupStoryGroupTreeViewNode,
    TagStoryGroupTreeViewNode,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_dependencies() -> dict[str, MagicMock]:
    return {
        "reader_settings": MagicMock(),
        "reader_tree_view": MagicMock(),
        "reader_tree_events": MagicMock(),
        "tree_view_manager": MagicMock(),
        "title_lists": MagicMock(),
    }


@pytest.fixture
def tree_builder(
    mock_dependencies: dict[str, MagicMock],
) -> Generator[ReaderTreeBuilder]:
    # Patch BarksTitleSearch to avoid loading whoosh index
    with patch("barks_reader.reader_tree_builder.BarksTitleSearch"):
        builder = ReaderTreeBuilder(**mock_dependencies)
        yield builder


class TestReaderTreeBuilder:
    def test_init(self, tree_builder: ReaderTreeBuilder) -> None:
        # noinspection PyProtectedMember
        assert tree_builder._reader_tree_view is not None
        # noinspection PyProtectedMember
        assert tree_builder._title_search is not None

    def test_build_main_screen_tree(
        self, tree_builder: ReaderTreeBuilder, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        # Mock internal build methods to verify orchestration
        with (
            patch.object(tree_builder, "_add_intro_node") as mock_intro,
            patch.object(tree_builder, "_add_the_stories_node") as mock_stories,
            patch.object(tree_builder, "_add_search_node") as mock_search,
            patch.object(tree_builder, "_add_appendix_node") as mock_appendix,
            patch.object(tree_builder, "_add_index_node") as mock_index,
            patch.object(tree_builder, "_build_story_nodes") as mock_build_stories,
        ):
            tree_builder.build_main_screen_tree()

            mock_intro.assert_called_once()
            mock_stories.assert_called_once()
            mock_search.assert_called_once()
            mock_appendix.assert_called_once()
            mock_index.assert_called_once()
            mock_build_stories.assert_called_once()

            # Verify binding
            mock_dependencies["reader_tree_view"].bind.assert_called()

    def test_build_story_nodes_structure(
        self, tree_builder: ReaderTreeBuilder, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        """Verify that the main structure (Chrono, Series, Categories) is created."""
        mock_tree = mock_dependencies["reader_tree_view"]
        mock_parent = MagicMock()

        # Mock the generators to avoid deep recursion during this test
        with (
            patch.object(tree_builder, "_add_chrono_year_range_nodes_gen", return_value=iter([])),
            patch.object(tree_builder, "_populate_series_node_gen", return_value=iter([])),
            patch.object(tree_builder, "_add_category_node_gen", return_value=iter([])),
            patch.object(tree_builder, "_finished_all_nodes") as mock_finished,
        ):
            # noinspection PyProtectedMember
            tree_builder._build_story_nodes(mock_tree, mock_parent)

            # Verify main nodes creation
            # We expect calls to add_node for Chrono, Series, Categories
            # Since we can't easily inspect the exact node instances passed to add_node without
            # capturing them, we can check call count or arguments.
            # add_node is called for:
            # 1. Chrono
            # 2. Series
            # 3. Categories
            # 4. Each Series sub-node (7 series)
            # 5. Each Category sub-node (len(TagCategories))
            assert mock_tree.add_node.call_count >= 3 + 7 + len(TagCategories)

            mock_finished.assert_called_once()

    def test_create_and_add_simple_node(
        self, tree_builder: ReaderTreeBuilder, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_tree = mock_dependencies["reader_tree_view"]
        mock_tree.add_node.side_effect = lambda n, parent=None: n  # noqa: ARG005
        mock_parent = MagicMock()

        # noinspection PyProtectedMember
        node = tree_builder._create_and_add_simple_node(
            mock_tree, "Test Node", MainTreeViewNode, parent_node=mock_parent
        )

        assert isinstance(node, MainTreeViewNode)
        assert node.text == "Test Node"
        mock_tree.add_node.assert_called_with(node, parent=mock_parent)

    def test_add_tag_node_gen(
        self, tree_builder: ReaderTreeBuilder, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_tree = mock_dependencies["reader_tree_view"]
        mock_parent = MagicMock()
        tag = Tags.AIRPLANES

        # Mock _get_tagged_titles
        with patch.object(
            tree_builder, "_get_tagged_titles", return_value=[Titles.VICTORY_GARDEN_THE]
        ):
            # noinspection PyProtectedMember
            gen = tree_builder._add_tag_node_gen(mock_tree, tag, mock_parent)
            # Run generator
            list(gen)

            # Verify node added
            args, _ = mock_tree.add_node.call_args
            node = args[0]
            assert isinstance(node, TagStoryGroupTreeViewNode)
            assert node.tag == tag
            assert node.populate_callback is not None

    def test_add_tag_group_node_gen(
        self, tree_builder: ReaderTreeBuilder, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_tree = mock_dependencies["reader_tree_view"]
        mock_parent = MagicMock()
        tag_group = TagGroups.AFRICA

        # Mock BARKS_TAG_GROUPS to return a simple list
        with patch(
            "barks_reader.reader_tree_builder.BARKS_TAG_GROUPS", {tag_group: [Tags.AIRPLANES]}
        ):
            # noinspection PyProtectedMember
            gen = tree_builder._add_tag_group_node_gen(mock_tree, tag_group, mock_parent)
            list(gen)

            # Should add the group node
            # And then recursively add the tag node (which calls add_node again)
            assert mock_tree.add_node.call_count >= 1
            # First call should be the group node
            node = mock_tree.add_node.call_args_list[0][0][0]
            assert isinstance(node, TagGroupStoryGroupTreeViewNode)
            assert node.tag == tag_group

    def test_populate_series_node_gen_cs(
        self, tree_builder: ReaderTreeBuilder, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_tree = mock_dependencies["reader_tree_view"]
        mock_parent = MagicMock()

        # Mock _populate_splittable_series_node_gen to verify dispatch
        with patch.object(
            tree_builder, "_populate_splittable_series_node_gen", return_value=iter([])
        ) as mock_split:
            # noinspection PyProtectedMember
            gen = tree_builder._populate_series_node_gen(mock_tree, SERIES_CS, mock_parent)
            list(gen)

            mock_split.assert_called_once()
