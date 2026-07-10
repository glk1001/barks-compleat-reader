# ruff: noqa: PLR2004

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import barks_reader.core.navigation.tree_spec
import pytest
from barks_fantagraphics.barks_tags import (
    BARKS_TAG_CATEGORIES,
    BARKS_TAG_GROUPS,
    TagCategories,
    TagGroups,
    Tags,
    get_sorted_tagged_titles,
)
from barks_fantagraphics.fanta_comics_info import (
    SERIES_CS,
    SERIES_ONE_PAGERS,
    SERIES_USA,
    get_num_comic_book_titles,
)
from barks_reader.core.filtered_title_lists import FilteredTitleLists
from barks_reader.core.navigation import (
    NodeKind,
    NodeRegistration,
    NodeSpec,
    PressAction,
    SeriesDestination,
    TagDestination,
    YearRangeDestination,
    YearRangeKind,
    build_reader_tree_spec,
)
from barks_reader.core.reader_consts_and_types import (
    APPENDIX_NODE_TEXT,
    CHRONO_YEAR_RANGES,
    CS_YEAR_RANGES,
    INDEX_NODE_TEXT,
    INTRO_NODE_TEXT,
    SEARCH_NODE_TEXT,
    THE_STORIES_NODE_TEXT,
    US_YEAR_RANGES,
)

if TYPE_CHECKING:
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo


@pytest.fixture(scope="module")
def title_lists() -> dict[str, list[FantaComicBookInfo]]:
    return FilteredTitleLists(include_one_pagers_in_chrono=False).get_title_lists()


@pytest.fixture
def reader_settings() -> MagicMock:
    settings = MagicMock()
    settings.wiki_bundle_dir = None
    return settings


@pytest.fixture
def specs(
    reader_settings: MagicMock, title_lists: dict[str, list[FantaComicBookInfo]]
) -> tuple[NodeSpec, ...]:
    # Favourites are read from a user file and mutate global tag data; keep the
    # spec build hermetic.
    with (
        patch.object(barks_reader.core.navigation.tree_spec, "read_title_list", return_value=[]),
        patch.object(
            barks_reader.core.navigation.tree_spec,
            "special_case_personal_favourites_tag_update",
        ),
    ):
        return build_reader_tree_spec(
            reader_settings, title_lists, include_one_pagers_in_chrono=False
        )


class TestTopLevelStructure:
    def test_top_level_nodes_in_display_order(self, specs: tuple[NodeSpec, ...]) -> None:
        assert [spec.text for spec in specs] == [
            INTRO_NODE_TEXT,
            THE_STORIES_NODE_TEXT,
            SEARCH_NODE_TEXT,
            APPENDIX_NODE_TEXT,
            INDEX_NODE_TEXT,
        ]
        assert all(spec.kind is NodeKind.MAIN for spec in specs)

    def test_intro_children_are_press_leaves_starting_closed(
        self, specs: tuple[NodeSpec, ...]
    ) -> None:
        intro = specs[0]
        assert len(intro.children) == 2
        assert intro.children[0].press_action is PressAction.OPEN_INTRO_DOC
        assert intro.children[1].press_action is PressAction.OPEN_ARTICLE
        assert all(child.start_closed for child in intro.children)


class TestStoriesSubtree:
    def test_stories_has_chrono_series_categories(self, specs: tuple[NodeSpec, ...]) -> None:
        stories = specs[1]
        assert len(stories.children) == 3
        assert all(child.kind is NodeKind.STORY_GROUP for child in stories.children)

    def test_chrono_year_ranges(self, specs: tuple[NodeSpec, ...]) -> None:
        chrono = specs[1].children[0]
        assert len(chrono.children) == len(CHRONO_YEAR_RANGES)

        for year_range, spec in zip(CHRONO_YEAR_RANGES, chrono.children, strict=True):
            assert spec.kind is NodeKind.YEAR_RANGE
            assert spec.destination == YearRangeDestination(
                start=year_range[0], end=year_range[1], kind=YearRangeKind.CHRONO
            )
            assert spec.year_range_kind is YearRangeKind.CHRONO
            assert spec.lazy_children is not None

    def test_chrono_lazy_title_rows_match_expected_counts(
        self, specs: tuple[NodeSpec, ...]
    ) -> None:
        chrono = specs[1].children[0]
        first_range_spec = chrono.children[0]

        assert first_range_spec.lazy_children is not None
        title_rows = first_range_spec.lazy_children()

        expected = get_num_comic_book_titles(CHRONO_YEAR_RANGES[0], include_one_pagers=False)
        assert len(title_rows) == expected
        assert all(row.kind is NodeKind.TITLE_ROW for row in title_rows)
        assert all(row.fanta_info is not None for row in title_rows)

    def test_series_nodes(self, specs: tuple[NodeSpec, ...]) -> None:
        series = specs[1].children[1]
        series_names = [
            spec.destination.series_name  # ty: ignore[unresolved-attribute]
            for spec in series.children
        ]

        assert len(series.children) == 8
        assert all(isinstance(spec.destination, SeriesDestination) for spec in series.children)
        assert SERIES_ONE_PAGERS in series_names

    def test_cs_and_us_series_split_into_year_ranges(self, specs: tuple[NodeSpec, ...]) -> None:
        series = specs[1].children[1]
        by_name = {
            spec.destination.series_name: spec  # ty: ignore[unresolved-attribute]
            for spec in series.children
        }

        cs_spec = by_name[SERIES_CS]
        assert len(cs_spec.children) == len(CS_YEAR_RANGES)
        assert all(child.year_range_kind is YearRangeKind.CS for child in cs_spec.children)
        assert all("WDCS" in child.text for child in cs_spec.children)

        us_spec = by_name[SERIES_USA]
        assert len(us_spec.children) == len(US_YEAR_RANGES)
        assert all(child.year_range_kind is YearRangeKind.US for child in us_spec.children)

    def test_simple_series_defer_their_title_rows(self, specs: tuple[NodeSpec, ...]) -> None:
        series = specs[1].children[1]
        by_name = {
            spec.destination.series_name: spec  # ty: ignore[unresolved-attribute]
            for spec in series.children
        }

        one_pagers = by_name[SERIES_ONE_PAGERS]
        assert one_pagers.children == ()
        assert one_pagers.lazy_children is not None
        title_rows = one_pagers.lazy_children()
        assert len(title_rows) > 0
        assert all(row.kind is NodeKind.TITLE_ROW for row in title_rows)

    def test_categories_cover_all_tag_categories(self, specs: tuple[NodeSpec, ...]) -> None:
        categories = specs[1].children[2]
        assert len(categories.children) == len(TagCategories)

    def test_tag_specs_have_destinations_and_lazy_rows(self, specs: tuple[NodeSpec, ...]) -> None:
        categories = specs[1].children[2]

        def find_tag_spec(spec: NodeSpec) -> NodeSpec | None:
            if isinstance(spec.destination, TagDestination):
                return spec
            for child in spec.children:
                found = find_tag_spec(child)
                if found is not None:
                    return found
            return None

        tag_spec = next(found for found in (find_tag_spec(c) for c in categories.children) if found)

        assert tag_spec.lazy_children is not None
        title_rows = tag_spec.lazy_children()
        assert isinstance(tag_spec.destination, TagDestination)
        tagged_titles = get_sorted_tagged_titles(tag_spec.destination.tag)
        # Rows are the tagged titles minus any not (yet) in the Fanta info.
        assert 0 < len(title_rows) <= len(tagged_titles)
        assert all(row.fanta_info is not None for row in title_rows)


class TestSearchAppendixIndex:
    def test_search_registration_and_children(self, specs: tuple[NodeSpec, ...]) -> None:
        search = specs[2]
        assert search.register_as is NodeRegistration.SEARCH
        assert len(search.children) == 3
        assert all(child.press_action is PressAction.SET_VIEW_STATE for child in search.children)

    def test_appendix_children(self, specs: tuple[NodeSpec, ...]) -> None:
        appendix = specs[3]
        assert len(appendix.children) == 6
        assert all(child.start_closed for child in appendix.children)

        press_actions = [child.press_action for child in appendix.children]
        assert press_actions.count(PressAction.OPEN_ARTICLE) == 4
        assert press_actions.count(PressAction.OPEN_CENSORSHIP_FIXES_DOC) == 1

        statistics = appendix.children[-1]
        assert statistics.press_action is PressAction.SET_VIEW_STATE
        assert statistics.register_as is NodeRegistration.STATISTICS

    def test_index_without_wiki_bundle(self, specs: tuple[NodeSpec, ...]) -> None:
        index = specs[4]
        assert len(index.children) == 2

        speech = index.children[1]
        assert speech.register_as is NodeRegistration.SPEECH_INDEX
        assert [child.register_as for child in speech.children] == [
            NodeRegistration.SPEECH_WORDS,
            NodeRegistration.NAMES_INDEX,
            NodeRegistration.LOCATIONS_INDEX,
        ]

    def test_index_with_wiki_bundle(self, title_lists: dict[str, list[FantaComicBookInfo]]) -> None:
        settings = MagicMock()
        settings.wiki_bundle_dir = "/a/wiki/bundle"

        with (
            patch.object(
                barks_reader.core.navigation.tree_spec, "read_title_list", return_value=[]
            ),
            patch.object(
                barks_reader.core.navigation.tree_spec,
                "special_case_personal_favourites_tag_update",
            ),
        ):
            specs = build_reader_tree_spec(
                settings, title_lists, include_one_pagers_in_chrono=False
            )

        index = specs[4]
        assert len(index.children) == 3
        wiki = index.children[-1]
        assert wiki.press_action is PressAction.OPEN_WIKI_INDEX
        assert wiki.start_closed


def test_favourites_tag_uses_the_favourites_file(
    reader_settings: MagicMock, title_lists: dict[str, list[FantaComicBookInfo]]
) -> None:
    with (
        patch.object(
            barks_reader.core.navigation.tree_spec, "read_title_list", return_value=[]
        ) as mock_read,
        patch.object(
            barks_reader.core.navigation.tree_spec,
            "special_case_personal_favourites_tag_update",
        ) as mock_special_case,
    ):
        build_reader_tree_spec(reader_settings, title_lists, include_one_pagers_in_chrono=False)

    if Tags.PERSONAL_FAVOURITES in _all_category_tags():
        mock_read.assert_called_once()
        mock_special_case.assert_called_once_with([])


def _all_category_tags() -> set[Tags]:
    tags: set[Tags] = set()

    def collect(items: list) -> None:
        for item in items:
            if isinstance(item, Tags):
                tags.add(item)
            elif isinstance(item, TagGroups):
                collect(BARKS_TAG_GROUPS[item])

    for category_items in BARKS_TAG_CATEGORIES.values():
        collect(list(category_items))

    return tags
