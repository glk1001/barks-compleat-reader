from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.search_filters import tag_titles
from barks_fantagraphics.search_query import (
    NEAR_DEFAULT_DISTANCE,
    Not,
    TagQualifier,
    VolumeQualifier,
    YearQualifier,
    parse_query,
)
from barks_fantagraphics.tag_query import parse_tag_query
from barks_reader.core.search_help import TAG_HELP, WORD_HELP
from barks_reader.ui.search_screen import SearchSyntaxHelp, _SyntaxExample, _SyntaxMeaning

_NO_QUERY_ALONE = (Not, TagQualifier, VolumeQualifier, YearQualifier)
_WORD_EXAMPLES = [example for example, _ in WORD_HELP]
_TAG_EXAMPLES = [example for example, _ in TAG_HELP]


class TestTheHelpMatchesTheSyntax:
    """Every example is read by the search's own parser as it says, so the help cannot drift."""

    @pytest.mark.parametrize("example", _WORD_EXAMPLES)
    def test_a_word_example_parses(self, example: str) -> None:
        parsed = parse_query(example)
        assert parsed.error is None
        # A filter or NOT alone is no query: the search asks for a word with it.
        assert parsed.root is not None
        assert not isinstance(parsed.root, _NO_QUERY_ALONE)

    @pytest.mark.parametrize("example", _WORD_EXAMPLES)
    def test_a_word_example_names_only_real_tags(self, example: str) -> None:
        for name in re.findall(r"tag:(\w+)", example):
            assert tag_titles(name) is not None, name

    @pytest.mark.parametrize("example", _TAG_EXAMPLES)
    def test_a_tag_example_parses_and_names_real_tags(self, example: str) -> None:
        parsed = parse_tag_query(example)
        assert parsed.error is None
        assert parsed.selection is not None
        for name in (*parsed.selection.included, *parsed.selection.excluded):
            assert tag_titles(name) is not None, name

    def test_near_s_distance_is_the_parser_s(self) -> None:
        meaning = dict(WORD_HELP)["gold NEAR mine"]
        assert meaning == f"within {NEAR_DEFAULT_DISTANCE} words"


class TestSearchSyntaxHelp:
    """The help lays each example beside what it does, in its two-column grid."""

    def test_each_example_is_shown_beside_its_meaning(self) -> None:
        grid = MagicMock()
        with patch.object(SearchSyntaxHelp, "ids", {"examples_grid": grid}):
            help_view = SearchSyntaxHelp()
            help_view.examples = (("gold mine", "both"), ("gold OR silver", "either"))

        shown = [call.args[0] for call in grid.add_widget.call_args_list[-4:]]
        assert [type(w) for w in shown] == [_SyntaxExample, _SyntaxMeaning] * 2
        assert [w.text for w in shown] == ["gold mine", "both", "gold OR silver", "either"]

    def test_examples_given_before_the_grid_exists_wait_for_it(self) -> None:
        with patch.object(SearchSyntaxHelp, "ids", {}):
            help_view = SearchSyntaxHelp()
            help_view.examples = TAG_HELP  # no grid yet: nothing to fill, no error
        assert help_view.examples == TAG_HELP
