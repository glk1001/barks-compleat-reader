from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from barks_reader import view_states
from barks_reader.reader_ui_classes import (
    ButtonTreeViewNode,
    CsYearRangeTreeViewNode,
    TagSearchBoxTreeViewNode,
    TitleSearchBoxTreeViewNode,
    UsYearRangeTreeViewNode,
    YearRangeTreeViewNode,
)
from barks_reader.view_states import ViewStates


class TestViewStates(unittest.TestCase):
    # noinspection PyMethodMayBeStatic
    def create_dummy_node(self, cls: type, text: str = "") -> Any:  # noqa: ANN401
        """Create a dummy object that mimics the class of a Kivy widget.

        Using MagicMock with spec satisfies isinstance() checks without instantiation.
        """
        node = MagicMock(spec=cls)
        node.text = text
        return node

    def test_get_view_state_from_node_types(self) -> None:
        # Test YearRangeTreeViewNode -> ON_YEAR_RANGE_NODE
        node = self.create_dummy_node(YearRangeTreeViewNode, "1940-1950")
        state, params = view_states.get_view_state_from_node(node)
        assert state == ViewStates.ON_YEAR_RANGE_NODE
        assert params == {"year_range": "1940-1950"}

        # Test CsYearRangeTreeViewNode -> ON_CS_YEAR_RANGE_NODE
        node = self.create_dummy_node(CsYearRangeTreeViewNode, "CS 1940")
        state, params = view_states.get_view_state_from_node(node)
        assert state == ViewStates.ON_CS_YEAR_RANGE_NODE
        assert params == {"cs_year_range": "CS 1940"}

        # Test UsYearRangeTreeViewNode -> ON_US_YEAR_RANGE_NODE
        node = self.create_dummy_node(UsYearRangeTreeViewNode, "US 1950")
        state, params = view_states.get_view_state_from_node(node)
        assert state == ViewStates.ON_US_YEAR_RANGE_NODE
        assert params == {"us_year_range": "US 1950"}

        # Test TitleSearchBoxTreeViewNode
        node = self.create_dummy_node(TitleSearchBoxTreeViewNode)
        state, params = view_states.get_view_state_from_node(node)
        assert state == ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET
        assert params == {}

        # Test TagSearchBoxTreeViewNode
        node = self.create_dummy_node(TagSearchBoxTreeViewNode)
        state, params = view_states.get_view_state_from_node(node)
        assert state == ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET
        assert params == {}

    def test_get_view_state_from_node_text_static_mappings(self) -> None:
        # Test simple text mapping (Introduction)
        node = self.create_dummy_node(ButtonTreeViewNode, view_states.INTRO_NODE_TEXT)
        state, params = view_states.get_view_state_from_node(node)
        assert state == ViewStates.ON_INTRO_NODE
        assert params == {}

        # Test text mapping with markup (should be stripped)
        node = self.create_dummy_node(ButtonTreeViewNode, f"[b]{view_states.INTRO_NODE_TEXT}[/b]")
        state, params = view_states.get_view_state_from_node(node)
        assert state == ViewStates.ON_INTRO_NODE

        # Test Series mapping
        node = self.create_dummy_node(ButtonTreeViewNode, view_states.SERIES_DDA)
        state, params = view_states.get_view_state_from_node(node)
        assert state == ViewStates.ON_DD_NODE

    @patch("barks_reader.view_states.BARKS_TAG_CATEGORIES_DICT", {"My Category": "val"})
    def test_get_view_state_category(self) -> None:
        node = self.create_dummy_node(ButtonTreeViewNode, "My Category")
        state, params = view_states.get_view_state_from_node(node)
        assert state == ViewStates.ON_CATEGORY_NODE
        assert params == {"category": "My Category"}

    @patch("barks_reader.view_states.is_tag_group_enum")
    @patch("barks_reader.view_states.TagGroups")
    def test_get_view_state_tag_group(
        self, mock_tag_groups: MagicMock, mock_is_group: MagicMock
    ) -> None:
        mock_is_group.return_value = True
        node = self.create_dummy_node(ButtonTreeViewNode, "Some Tag Group")

        state, params = view_states.get_view_state_from_node(node)

        assert state == ViewStates.ON_TAG_GROUP_NODE
        assert "tag_group" in params
        mock_tag_groups.assert_called_with("Some Tag Group")

    @patch("barks_reader.view_states.is_tag_enum")
    @patch("barks_reader.view_states.Tags")
    def test_get_view_state_tag(self, mock_tags: MagicMock, mock_is_tag: MagicMock) -> None:
        mock_is_tag.return_value = True
        node = self.create_dummy_node(ButtonTreeViewNode, "Some Tag")

        state, params = view_states.get_view_state_from_node(node)

        assert state == ViewStates.ON_TAG_NODE
        assert "tag" in params
        mock_tags.assert_called_with("Some Tag")

    def test_get_view_state_and_article_title_from_node(self) -> None:
        # Test a known article node text
        node = self.create_dummy_node(
            ButtonTreeViewNode, view_states.INTRO_DON_AULT_FANTA_INTRO_TEXT
        )
        state, title = view_states.get_view_state_and_article_title_from_node(node)

        assert state == ViewStates.ON_INTRO_DON_AULT_FANTA_INTRO_NODE
        assert title.name == "DON_AULT___FANTAGRAPHICS_INTRODUCTION"

        # Test unknown article
        node = self.create_dummy_node(ButtonTreeViewNode, "Unknown Article")
        with pytest.raises(RuntimeError):
            view_states.get_view_state_and_article_title_from_node(node)
