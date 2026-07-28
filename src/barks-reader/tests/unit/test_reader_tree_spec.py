# ruff: noqa: PLR2004

from __future__ import annotations

import dataclasses
from enum import Enum
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
    get_tag_titles,
)
from barks_fantagraphics.barks_titles import (
    US_1_FC_ISSUE_NUM,
    US_2_FC_ISSUE_NUM,
    US_3_FC_ISSUE_NUM,
)
from barks_fantagraphics.fanta_comics_info import (
    SERIES_COVERS,
    SERIES_CS,
    SERIES_DDA,
    SERIES_ONE_PAGERS,
    SERIES_USA,
    get_num_comic_book_titles,
)
from barks_reader.core.filtered_title_lists import FilteredTitleLists
from barks_reader.core.navigation import (
    CategoryDestination,
    ChooseForMeDestination,
    HistoryDestination,
    NodeKind,
    NodeRegistration,
    NodeSpec,
    PressAction,
    RandomTitlesDestination,
    ReadingDestination,
    TagDestination,
    TagGroupDestination,
    build_reader_tree_spec,
)
from barks_reader.core.navigation.tree_spec import (
    NUM_RANDOM_TITLES,
    _get_count_extra_text,
    _get_cs_year_range_extra_text,
    _get_us_year_range_extra_text,
)
from barks_reader.core.reader_consts_and_types import (
    APPENDIX_NODE_TEXT,
    CHOOSE_FOR_ME_NODE_TEXT,
    CHRONO_YEAR_RANGES,
    COVER_YEAR_RANGES,
    CS_YEAR_RANGES,
    FROM_FAVOURITES_NODE_TEXT,
    FROM_THE_1940S_NODE_TEXT,
    FROM_THE_1950S_NODE_TEXT,
    FROM_THE_1960S_NODE_TEXT,
    HISTORY_NODE_TEXT,
    INDEX_NODE_TEXT,
    INTRO_NODE_TEXT,
    ONE_PAGER_YEAR_RANGES,
    RANDOM_TITLE_YEAR_RANGES,
    READING_NODE_TEXT,
    SEARCH_NODE_TEXT,
    SURPRISE_ME_NODE_TEXT,
    THE_STORIES_NODE_TEXT,
    US_YEAR_RANGES,
    WITH_BEAGLE_BOYS_NODE_TEXT,
    WITH_DAISY_NODE_TEXT,
    WITH_GLADSTONE_NODE_TEXT,
    WITH_GRANDMA_DUCK_NODE_TEXT,
    WITH_GYRO_NODE_TEXT,
    WITH_SCROOGE_NODE_TEXT,
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


# --- Structural snapshots -------------------------------------------------------
#
# The hand-written subtrees (everything except the generated year-range/series/tag
# rows) are compared field-by-field against a rendered snapshot rather than by
# spot-checking one attribute at a time. Every `NodeSpec` field is a hand-typed
# literal, so a wrong destination, a dropped `start_closed`, or a swapped
# registration hook is invisible to a partial assertion but changes what the tree
# actually navigates to.


def _render_value(value: object) -> str:
    # Enums render by name: their `auto()` values shift whenever a member is
    # inserted, and a snapshot must not churn on that.
    if isinstance(value, Enum):
        return f"{type(value).__name__}.{value.name}"
    return repr(value)


def _render_destination(destination: object) -> str:
    if destination is None:
        return "None"
    fields = ", ".join(
        f"{field.name}={_render_value(getattr(destination, field.name))}"
        for field in dataclasses.fields(destination)  # ty: ignore[invalid-argument-type]
    )
    return f"{type(destination).__name__}({fields})"


def _summarise(spec: NodeSpec, depth: int = 0, max_depth: int | None = None) -> list[str]:
    """Render `spec` and its children as one indented line per node."""
    lines = [
        "  " * depth
        + " ".join(
            [
                spec.kind.name,
                f"text={spec.text!r}",
                f"dest={_render_destination(spec.destination)}",
                f"press={spec.press_action.name}",
                f"register={spec.register_as.name if spec.register_as else None}",
                f"closed={spec.start_closed}",
                f"yrk={spec.year_range_kind.name if spec.year_range_kind else None}",
                f"lazy={spec.lazy_children is not None}",
                f"repopulate={spec.repopulate_on_expand}",
            ]
        )
    ]
    if max_depth is None or depth < max_depth:
        for child in spec.children:
            lines.extend(_summarise(child, depth + 1, max_depth))
    return lines


def _assert_snapshot(spec: NodeSpec, expected: str, max_depth: int | None = None) -> None:
    assert _summarise(spec, max_depth=max_depth) == expected.strip("\n").split("\n")


_INTRO_SNAPSHOT = """
MAIN text='Introduction' dest=IntroDestination() press=TOGGLE_ONLY register=None closed=False yrk=None lazy=False repopulate=False
  MAIN text='The Compleat Barks Disney Reader' dest=IntroDocDestination() press=OPEN_INTRO_DOC register=None closed=True yrk=None lazy=False repopulate=False
  MAIN text='Don Ault: Fantagraphics Introduction' dest=ArticleDestination(view_state=ViewStates.ON_INTRO_DON_AULT_FANTA_INTRO_NODE, article_title=Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION) press=OPEN_ARTICLE register=None closed=True yrk=None lazy=False repopulate=False
"""  # noqa: E501

# Depth-limited: the three group headers are hand-written, everything below them is
# generated and covered by `TestStoriesSubtree`.
_STORIES_SNAPSHOT = """
MAIN text='The Stories' dest=StoriesDestination() press=TOGGLE_ONLY register=None closed=False yrk=None lazy=False repopulate=False
  STORY_GROUP text='[b]Chronological[/b]' dest=ChronologicalDestination() press=TOGGLE_ONLY register=None closed=False yrk=None lazy=False repopulate=False
  STORY_GROUP text='[b]Series[/b]' dest=AllSeriesDestination() press=TOGGLE_ONLY register=None closed=False yrk=None lazy=False repopulate=False
  STORY_GROUP text='[b]Categories[/b]' dest=CategoriesDestination() press=TOGGLE_ONLY register=None closed=False yrk=None lazy=False repopulate=False
"""  # noqa: E501

_SEARCH_SNAPSHOT = """
MAIN text='Search' dest=SearchDestination() press=TOGGLE_ONLY register=SEARCH closed=False yrk=None lazy=False repopulate=False
  STORY_GROUP text='Titles' dest=TitleSearchDestination() press=SET_VIEW_STATE register=None closed=False yrk=None lazy=False repopulate=False
  STORY_GROUP text='Tags' dest=TagSearchDestination() press=SET_VIEW_STATE register=None closed=False yrk=None lazy=False repopulate=False
  STORY_GROUP text='Words' dest=WordSearchDestination() press=SET_VIEW_STATE register=None closed=False yrk=None lazy=False repopulate=False
"""  # noqa: E501

_APPENDIX_SNAPSHOT = """
MAIN text='Appendix' dest=AppendixDestination() press=TOGGLE_ONLY register=None closed=False yrk=None lazy=False repopulate=False
  MAIN text='Rich Tommaso: On Coloring Barks' dest=ArticleDestination(view_state=ViewStates.ON_APPENDIX_RICH_TOMMASO_ON_COLORING_BARKS_NODE, article_title=Titles.RICH_TOMMASO___ON_COLORING_BARKS) press=OPEN_ARTICLE register=None closed=True yrk=None lazy=False repopulate=False
  MAIN text='Don Ault: Life Among the Ducks' dest=ArticleDestination(view_state=ViewStates.ON_APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_NODE, article_title=Titles.DON_AULT___LIFE_AMONG_THE_DUCKS) press=OPEN_ARTICLE register=None closed=True yrk=None lazy=False repopulate=False
  MAIN text='Maggie Thompson: Comics Readers Find...' dest=ArticleDestination(view_state=ViewStates.ON_APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_NODE, article_title=Titles.MAGGIE_THOMPSON___COMICS_READERS_FIND_COMIC_BOOK_GOLD) press=OPEN_ARTICLE register=None closed=True yrk=None lazy=False repopulate=False
  MAIN text='George Lucas: An Appreciation' dest=ArticleDestination(view_state=ViewStates.ON_APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_NODE, article_title=Titles.GEORGE_LUCAS___AN_APPRECIATION) press=OPEN_ARTICLE register=None closed=True yrk=None lazy=False repopulate=False
  MAIN text='Censorship Fixes and Other Changes' dest=CensorshipFixesDocDestination() press=OPEN_CENSORSHIP_FIXES_DOC register=None closed=True yrk=None lazy=False repopulate=False
  MAIN text='Statistics' dest=StatisticsDestination() press=SET_VIEW_STATE register=STATISTICS closed=True yrk=None lazy=False repopulate=False
"""  # noqa: E501

_INDEX_SNAPSHOT = """
MAIN text='Indexes' dest=IndexDestination() press=TOGGLE_ONLY register=None closed=False yrk=None lazy=False repopulate=False
  MAIN text='Main Index' dest=MainIndexDestination() press=SET_VIEW_STATE register=MAIN_INDEX closed=False yrk=None lazy=False repopulate=False
  MAIN text='Speech Bubble Index' dest=SpeechIndexDestination() press=OPEN_SPEECH_INDEX register=SPEECH_INDEX closed=False yrk=None lazy=False repopulate=False
    MAIN text='Words' dest=SpeechWordsDestination() press=OPEN_SPEECH_WORDS register=SPEECH_WORDS closed=False yrk=None lazy=False repopulate=False
    MAIN text='Names' dest=NamesIndexDestination() press=SET_VIEW_STATE register=NAMES_INDEX closed=False yrk=None lazy=False repopulate=False
    MAIN text='Locations' dest=LocationsIndexDestination() press=SET_VIEW_STATE register=LOCATIONS_INDEX closed=False yrk=None lazy=False repopulate=False
"""  # noqa: E501

# The generated year-range subtrees. Their labels are assembled from the range string,
# a per-kind "extra text" (issue span for CS/US, plain count for one-pagers/covers/
# chrono) and the markup helpers — none of which a count-only assertion can see.
_CHRONO_SNAPSHOT = """
STORY_GROUP text='[b]Chronological[/b]' dest=ChronologicalDestination() press=TOGGLE_ONLY register=None closed=False yrk=None lazy=False repopulate=False
  YEAR_RANGE text='[b]1942-1946[/b] [i](65)[/i]' dest=YearRangeDestination(start=1942, end=1946, kind=YearRangeKind.CHRONO) press=TOGGLE_ONLY register=None closed=False yrk=CHRONO lazy=True repopulate=False
  YEAR_RANGE text='[b]1947-1950[/b] [i](70)[/i]' dest=YearRangeDestination(start=1947, end=1950, kind=YearRangeKind.CHRONO) press=TOGGLE_ONLY register=None closed=False yrk=CHRONO lazy=True repopulate=False
  YEAR_RANGE text='[b]1951-1954[/b] [i](74)[/i]' dest=YearRangeDestination(start=1951, end=1954, kind=YearRangeKind.CHRONO) press=TOGGLE_ONLY register=None closed=False yrk=CHRONO lazy=True repopulate=False
  YEAR_RANGE text='[b]1955-1957[/b] [i](76)[/i]' dest=YearRangeDestination(start=1955, end=1957, kind=YearRangeKind.CHRONO) press=TOGGLE_ONLY register=None closed=False yrk=CHRONO lazy=True repopulate=False
  YEAR_RANGE text='[b]1958-1961[/b] [i](138)[/i]' dest=YearRangeDestination(start=1958, end=1961, kind=YearRangeKind.CHRONO) press=TOGGLE_ONLY register=None closed=False yrk=CHRONO lazy=True repopulate=False
  YEAR_RANGE text='[b]1962-1971[/b] [i](20)[/i]' dest=YearRangeDestination(start=1962, end=1971, kind=YearRangeKind.CHRONO) press=TOGGLE_ONLY register=None closed=False yrk=CHRONO lazy=True repopulate=False
"""  # noqa: E501

_SERIES_SNAPSHOT = """
STORY_GROUP text='[b]Series[/b]' dest=AllSeriesDestination() press=TOGGLE_ONLY register=None closed=False yrk=None lazy=False repopulate=False
  STORY_GROUP text='[b]Comics and Stories[/b] [i](227)[/i]' dest=SeriesDestination(series_name='Comics and Stories') press=TOGGLE_ONLY register=None closed=False yrk=None lazy=False repopulate=False
    YEAR_RANGE text='[b]1942-1946[/b] [i](WDCS 31-79)[/i]' dest=YearRangeDestination(start=1942, end=1946, kind=YearRangeKind.CS) press=TOGGLE_ONLY register=None closed=False yrk=CS lazy=True repopulate=False
    YEAR_RANGE text='[b]1947-1950[/b] [i](WDCS 80-130)[/i]' dest=YearRangeDestination(start=1947, end=1950, kind=YearRangeKind.CS) press=TOGGLE_ONLY register=None closed=False yrk=CS lazy=True repopulate=False
    YEAR_RANGE text='[b]1951-1954[/b] [i](WDCS 131-179)[/i]' dest=YearRangeDestination(start=1951, end=1954, kind=YearRangeKind.CS) press=TOGGLE_ONLY register=None closed=False yrk=CS lazy=True repopulate=False
    YEAR_RANGE text='[b]1955-1957[/b] [i](WDCS 180-217)[/i]' dest=YearRangeDestination(start=1955, end=1957, kind=YearRangeKind.CS) press=TOGGLE_ONLY register=None closed=False yrk=CS lazy=True repopulate=False
    YEAR_RANGE text='[b]1958-1961[/b] [i](WDCS 218-263)[/i]' dest=YearRangeDestination(start=1958, end=1961, kind=YearRangeKind.CS) press=TOGGLE_ONLY register=None closed=False yrk=CS lazy=True repopulate=False
    YEAR_RANGE text='[b]1962-1966[/b] [i](WDCS 264-265)[/i]' dest=YearRangeDestination(start=1962, end=1966, kind=YearRangeKind.CS) press=TOGGLE_ONLY register=None closed=False yrk=CS lazy=True repopulate=False
  STORY_GROUP text='[b]Donald Duck Adventures[/b] [i](39)[/i]' dest=SeriesDestination(series_name='Donald Duck Adventures') press=TOGGLE_ONLY register=None closed=False yrk=None lazy=True repopulate=False
  STORY_GROUP text='[b]Uncle Scrooge Adventures[/b] [i](41)[/i]' dest=SeriesDestination(series_name='Uncle Scrooge Adventures') press=TOGGLE_ONLY register=None closed=False yrk=None lazy=False repopulate=False
    YEAR_RANGE text='[b]1951-1954[/b] [i](US 1-10)[/i]' dest=YearRangeDestination(start=1951, end=1954, kind=YearRangeKind.US) press=TOGGLE_ONLY register=None closed=False yrk=US lazy=True repopulate=False
    YEAR_RANGE text='[b]1955-1957[/b] [i](US 11-23)[/i]' dest=YearRangeDestination(start=1955, end=1957, kind=YearRangeKind.US) press=TOGGLE_ONLY register=None closed=False yrk=US lazy=True repopulate=False
    YEAR_RANGE text='[b]1958-1961[/b] [i](US 24-38)[/i]' dest=YearRangeDestination(start=1958, end=1961, kind=YearRangeKind.US) press=TOGGLE_ONLY register=None closed=False yrk=US lazy=True repopulate=False
    YEAR_RANGE text='[b]1962-1966[/b] [i](US 39-40)[/i]' dest=YearRangeDestination(start=1962, end=1966, kind=YearRangeKind.US) press=TOGGLE_ONLY register=None closed=False yrk=US lazy=True repopulate=False
  STORY_GROUP text='[b]Donald Duck Short Stories[/b] [i](14)[/i]' dest=SeriesDestination(series_name='Donald Duck Short Stories') press=TOGGLE_ONLY register=None closed=False yrk=None lazy=True repopulate=False
  STORY_GROUP text='[b]Uncle Scrooge Short Stories[/b] [i](28)[/i]' dest=SeriesDestination(series_name='Uncle Scrooge Short Stories') press=TOGGLE_ONLY register=None closed=False yrk=None lazy=True repopulate=False
  STORY_GROUP text='[b]Gyro Gearloose[/b] [i](41)[/i]' dest=SeriesDestination(series_name='Gyro Gearloose') press=TOGGLE_ONLY register=None closed=False yrk=None lazy=True repopulate=False
  STORY_GROUP text='[b]Misc[/b] [i](53)[/i]' dest=SeriesDestination(series_name='Misc') press=TOGGLE_ONLY register=None closed=False yrk=None lazy=True repopulate=False
  STORY_GROUP text='[b]One Pagers[/b] [i](128)[/i]' dest=SeriesDestination(series_name='One Pagers') press=TOGGLE_ONLY register=None closed=False yrk=None lazy=False repopulate=False
    YEAR_RANGE text='[b]1946-1952[/b] [i](43)[/i]' dest=YearRangeDestination(start=1946, end=1952, kind=YearRangeKind.ONE_PAGER) press=TOGGLE_ONLY register=None closed=False yrk=ONE_PAGER lazy=True repopulate=False
    YEAR_RANGE text='[b]1953-1956[/b] [i](49)[/i]' dest=YearRangeDestination(start=1953, end=1956, kind=YearRangeKind.ONE_PAGER) press=TOGGLE_ONLY register=None closed=False yrk=ONE_PAGER lazy=True repopulate=False
    YEAR_RANGE text='[b]1957-1962[/b] [i](36)[/i]' dest=YearRangeDestination(start=1957, end=1962, kind=YearRangeKind.ONE_PAGER) press=TOGGLE_ONLY register=None closed=False yrk=ONE_PAGER lazy=True repopulate=False
  STORY_GROUP text='[b]Covers[/b] [i](186)[/i]' dest=SeriesDestination(series_name='Covers') press=TOGGLE_ONLY register=None closed=False yrk=None lazy=False repopulate=False
    YEAR_RANGE text='[b]1948-1952[/b] [i](52)[/i]' dest=YearRangeDestination(start=1948, end=1952, kind=YearRangeKind.COVER) press=TOGGLE_ONLY register=None closed=False yrk=COVER lazy=True repopulate=False
    YEAR_RANGE text='[b]1953-1955[/b] [i](38)[/i]' dest=YearRangeDestination(start=1953, end=1955, kind=YearRangeKind.COVER) press=TOGGLE_ONLY register=None closed=False yrk=COVER lazy=True repopulate=False
    YEAR_RANGE text='[b]1956-1959[/b] [i](55)[/i]' dest=YearRangeDestination(start=1956, end=1959, kind=YearRangeKind.COVER) press=TOGGLE_ONLY register=None closed=False yrk=COVER lazy=True repopulate=False
    YEAR_RANGE text='[b]1960-1965[/b] [i](41)[/i]' dest=YearRangeDestination(start=1960, end=1965, kind=YearRangeKind.COVER) press=TOGGLE_ONLY register=None closed=False yrk=COVER lazy=True repopulate=False
"""  # noqa: E501

_FAVOURITES_CATEGORY_SNAPSHOT = """
STORY_GROUP text='[b]Favourites[/b]' dest=CategoryDestination(category='Favourites') press=TOGGLE_ONLY register=None closed=False yrk=None lazy=False repopulate=False
  STORY_GROUP text="[b]Barks' Picks[/b] [i](15)[/i]" dest=TagDestination(tag=Tags.BARKS_FAVOURITES) press=TOGGLE_ONLY register=None closed=False yrk=None lazy=True repopulate=False
  STORY_GROUP text='[b]everygeek.net[/b] [i](7)[/i]' dest=TagDestination(tag=Tags.EVERY_GEEK_FAVOURITES) press=TOGGLE_ONLY register=None closed=False yrk=None lazy=True repopulate=False
  STORY_GROUP text='[b]My Picks[/b] [i](0)[/i]' dest=TagDestination(tag=Tags.PERSONAL_FAVOURITES) press=TOGGLE_ONLY register=None closed=False yrk=None lazy=True repopulate=False
  STORY_GROUP text='[b]Peter Schilling[/b] [i](13)[/i]' dest=TagDestination(tag=Tags.PETER_SCHILLING_FAVOURITES) press=TOGGLE_ONLY register=None closed=False yrk=None lazy=True repopulate=False
  STORY_GROUP text='[b]Wiki Notable Stories[/b] [i](22)[/i]' dest=TagDestination(tag=Tags.WIKI_NOTABLE_STORIES) press=TOGGLE_ONLY register=None closed=False yrk=None lazy=True repopulate=False
  STORY_GROUP text='[b]The Classics[/b] [i](16)[/i]' dest=TagDestination(tag=Tags.CLASSICS) press=TOGGLE_ONLY register=None closed=False yrk=None lazy=True repopulate=False
"""  # noqa: E501

# The wiki entry is appended only when the bundle setting resolves; it must start
# closed so a saved-node restore renders the destination instead of replaying the
# press (which would auto-open the wiki screen at startup).
_WIKI_INDEX_ENTRY = (
    "  MAIN text='Carl Barks Wiki' dest=WikiIndexDestination() press=OPEN_WIKI_INDEX"
    " register=None closed=True yrk=None lazy=False repopulate=False"
)


class TestTopLevelStructure:
    def test_top_level_nodes_in_display_order(self, specs: tuple[NodeSpec, ...]) -> None:
        assert [spec.text for spec in specs] == [
            INTRO_NODE_TEXT,
            THE_STORIES_NODE_TEXT,
            SEARCH_NODE_TEXT,
            READING_NODE_TEXT,
            APPENDIX_NODE_TEXT,
            INDEX_NODE_TEXT,
        ]
        assert all(spec.kind is NodeKind.MAIN for spec in specs)

    def test_intro_subtree(self, specs: tuple[NodeSpec, ...]) -> None:
        _assert_snapshot(specs[0], _INTRO_SNAPSHOT)

    def test_stories_group_headers(self, specs: tuple[NodeSpec, ...]) -> None:
        _assert_snapshot(specs[1], _STORIES_SNAPSHOT, max_depth=1)


class TestStoriesSubtree:
    def test_stories_has_chrono_series_categories(self, specs: tuple[NodeSpec, ...]) -> None:
        stories = specs[1]
        assert len(stories.children) == 3
        assert all(child.kind is NodeKind.STORY_GROUP for child in stories.children)

    def test_chrono_year_ranges(self, specs: tuple[NodeSpec, ...]) -> None:
        _assert_snapshot(specs[1].children[0], _CHRONO_SNAPSHOT)
        assert len(specs[1].children[0].children) == len(CHRONO_YEAR_RANGES)

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

    def test_series_subtree(self, specs: tuple[NodeSpec, ...]) -> None:
        _assert_snapshot(specs[1].children[1], _SERIES_SNAPSHOT)

    def test_series_subtree_matches_the_configured_year_ranges(
        self, specs: tuple[NodeSpec, ...]
    ) -> None:
        """The snapshot above is a literal; check it still tracks the range constants."""
        by_name = {
            spec.destination.series_name: spec  # ty: ignore[unresolved-attribute]
            for spec in specs[1].children[1].children
        }

        assert len(by_name) == 9
        assert len(by_name[SERIES_CS].children) == len(CS_YEAR_RANGES)
        assert len(by_name[SERIES_USA].children) == len(US_YEAR_RANGES)
        assert len(by_name[SERIES_ONE_PAGERS].children) == len(ONE_PAGER_YEAR_RANGES)
        assert len(by_name[SERIES_COVERS].children) == len(COVER_YEAR_RANGES)

    @pytest.mark.parametrize(
        "series_name",
        [SERIES_ONE_PAGERS, SERIES_COVERS, SERIES_CS, SERIES_USA],
        ids=["one_pagers", "covers", "cs", "us"],
    )
    def test_year_range_groups_defer_real_title_rows(
        self, specs: tuple[NodeSpec, ...], series_name: str
    ) -> None:
        """Each year-range group carries its own titles into its lazy rows.

        The rows are built by a `partial` closed over the range's title list, so the
        wrong list (or none at all) only shows up when the node is actually expanded.
        """
        by_name = {
            spec.destination.series_name: spec  # ty: ignore[unresolved-attribute]
            for spec in specs[1].children[1].children
        }
        series = by_name[series_name]

        assert series.lazy_children is None
        total_rows = 0
        for child in series.children:
            assert child.lazy_children is not None
            rows = child.lazy_children()
            assert all(row.kind is NodeKind.TITLE_ROW for row in rows)
            assert all(row.fanta_info is not None for row in rows)
            total_rows += len(rows)

        assert total_rows > 0

    def test_one_pager_and_cover_groups_hold_every_title(
        self, specs: tuple[NodeSpec, ...], title_lists: dict[str, list[FantaComicBookInfo]]
    ) -> None:
        """The year-range groups partition the whole series — nothing is dropped.

        In particular the 6 undated covers (submitted_year == -1) fold into the
        final Covers group rather than vanishing.
        """
        series = specs[1].children[1]
        by_name = {
            spec.destination.series_name: spec  # ty: ignore[unresolved-attribute]
            for spec in series.children
        }

        def group_rows(group: NodeSpec) -> tuple[NodeSpec, ...]:
            assert group.lazy_children is not None
            return group.lazy_children()

        for series_name in (SERIES_ONE_PAGERS, SERIES_COVERS):
            node = by_name[series_name]
            grouped = sum(len(group_rows(child)) for child in node.children)
            assert grouped == len(title_lists[series_name])

        final_cover_group = by_name[SERIES_COVERS].children[-1]
        undated = [
            row
            for row in group_rows(final_cover_group)
            if row.fanta_info is not None and row.fanta_info.comic_book_info.submitted_year == -1
        ]
        assert len(undated) == 6

    def test_simple_series_defer_their_title_rows(self, specs: tuple[NodeSpec, ...]) -> None:
        series = specs[1].children[1]
        by_name = {
            spec.destination.series_name: spec  # ty: ignore[unresolved-attribute]
            for spec in series.children
        }

        dda = by_name[SERIES_DDA]
        assert dda.children == ()
        assert dda.lazy_children is not None
        title_rows = dda.lazy_children()
        assert len(title_rows) > 0
        assert all(row.kind is NodeKind.TITLE_ROW for row in title_rows)

    def test_categories_cover_all_tag_categories(self, specs: tuple[NodeSpec, ...]) -> None:
        categories = specs[1].children[2]
        assert len(categories.children) == len(TagCategories)

    def test_favourites_category_subtree(self, specs: tuple[NodeSpec, ...]) -> None:
        """One category in full, to pin the category → tag nesting and label format."""
        favourites = next(
            spec
            for spec in specs[1].children[2].children
            if spec.destination == CategoryDestination(category=TagCategories.FAVOURITES.value)
        )
        _assert_snapshot(favourites, _FAVOURITES_CATEGORY_SNAPSHOT)

    def test_every_category_node_matches_its_destination(self, specs: tuple[NodeSpec, ...]) -> None:
        """Every node in the Categories subtree is labelled from its own destination.

        The subtree is far too large to snapshot, but each node's text is derived
        mechanically from its destination, so the relationship can be asserted for all
        of them at once — which is what pins the markup helpers and their arguments.
        """
        categories = specs[1].children[2]
        seen = {"category": 0, "group": 0, "tag": 0}

        def check(spec: NodeSpec) -> None:
            assert spec.kind is NodeKind.STORY_GROUP
            destination = spec.destination

            if isinstance(destination, CategoryDestination):
                seen["category"] += 1
                assert spec.text == f"[b]{destination.category}[/b]"
                assert spec.lazy_children is None
            elif isinstance(destination, TagGroupDestination):
                seen["group"] += 1
                assert spec.text == f"[b]{destination.tag_group.value}[/b]"
                assert spec.lazy_children is None
                # A group node is only useful if it holds the group's tags.
                assert len(spec.children) == len(BARKS_TAG_GROUPS[destination.tag_group])
            elif isinstance(destination, TagDestination):
                seen["tag"] += 1
                # Favourites are patched to an empty list by the `specs` fixture.
                num_titles = (
                    0
                    if destination.tag is Tags.PERSONAL_FAVOURITES
                    else len(get_sorted_tagged_titles(destination.tag))
                )
                assert spec.text == f"[b]{destination.tag.value}[/b] [i]({num_titles})[/i]"
                assert spec.lazy_children is not None
            else:
                pytest.fail(f"unexpected destination in Categories subtree: {destination!r}")

            for child in spec.children:
                check(child)

        for category in categories.children:
            check(category)

        # The traversal actually reached all three node kinds.
        assert all(count > 0 for count in seen.values()), seen

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


class TestReadingSubtree:
    def test_reading_has_history_and_choose_for_me(self, specs: tuple[NodeSpec, ...]) -> None:
        reading = specs[3]
        assert reading.text == READING_NODE_TEXT
        assert isinstance(reading.destination, ReadingDestination)
        assert len(reading.children) == 2
        assert all(child.kind is NodeKind.STORY_GROUP for child in reading.children)

    def test_history_registration_and_press_action(self, specs: tuple[NodeSpec, ...]) -> None:
        history = specs[3].children[1]
        assert history.text == HISTORY_NODE_TEXT
        assert isinstance(history.destination, HistoryDestination)
        assert history.register_as is NodeRegistration.HISTORY
        assert history.press_action is PressAction.SET_VIEW_STATE
        assert history.start_closed
        assert not history.children
        assert history.lazy_children is None

    def test_choose_for_me_filter_nodes(self, specs: tuple[NodeSpec, ...]) -> None:
        choose_for_me = specs[3].children[0]
        assert choose_for_me.text == CHOOSE_FOR_ME_NODE_TEXT
        assert isinstance(choose_for_me.destination, ChooseForMeDestination)

        expected = [
            (SURPRISE_ME_NODE_TEXT, RandomTitlesDestination()),
            (FROM_THE_1940S_NODE_TEXT, RandomTitlesDestination(RANDOM_TITLE_YEAR_RANGES[0])),
            (FROM_THE_1950S_NODE_TEXT, RandomTitlesDestination(RANDOM_TITLE_YEAR_RANGES[1])),
            (FROM_THE_1960S_NODE_TEXT, RandomTitlesDestination(RANDOM_TITLE_YEAR_RANGES[2])),
            (
                FROM_FAVOURITES_NODE_TEXT,
                RandomTitlesDestination(category=TagCategories.FAVOURITES),
            ),
            (WITH_SCROOGE_NODE_TEXT, RandomTitlesDestination(tag=Tags.SCROOGE_NOT_IN_US)),
            (WITH_GLADSTONE_NODE_TEXT, RandomTitlesDestination(tag=Tags.GLADSTONE_GANDER)),
            (WITH_GYRO_NODE_TEXT, RandomTitlesDestination(tag=Tags.GYRO_GEARLOOSE)),
            (WITH_DAISY_NODE_TEXT, RandomTitlesDestination(tag=Tags.DAISY)),
            (WITH_BEAGLE_BOYS_NODE_TEXT, RandomTitlesDestination(tag=Tags.BEAGLE_BOYS)),
            (WITH_GRANDMA_DUCK_NODE_TEXT, RandomTitlesDestination(tag=Tags.GRANDMA_DUCK)),
        ]
        assert len(choose_for_me.children) == len(expected)
        for spec, (text, destination) in zip(choose_for_me.children, expected, strict=True):
            assert spec.kind is NodeKind.STORY_GROUP
            assert spec.text == text
            assert spec.destination == destination
            assert spec.lazy_children is not None
            assert spec.repopulate_on_expand

    def test_random_title_rows_are_sampled_within_year_bounds(
        self, specs: tuple[NodeSpec, ...]
    ) -> None:
        all_years = (CHRONO_YEAR_RANGES[0][0], CHRONO_YEAR_RANGES[-1][1])

        for spec in specs[3].children[0].children:
            assert isinstance(spec.destination, RandomTitlesDestination)
            if spec.destination.tag is not None:
                continue  # Character nodes are covered by the tagged-rows test.

            assert spec.lazy_children is not None
            title_rows = spec.lazy_children()

            assert len(title_rows) == NUM_RANDOM_TITLES
            assert all(row.kind is NodeKind.TITLE_ROW for row in title_rows)

            year_range = spec.destination.year_range or all_years
            submitted_years = []
            chrono_numbers = []
            for row in title_rows:
                assert row.fanta_info is not None
                submitted_years.append(row.fanta_info.comic_book_info.submitted_year)
                chrono_numbers.append(row.fanta_info.fanta_chronological_number)

            assert all(year_range[0] <= year <= year_range[1] for year in submitted_years)
            # Samples are displayed in chronological order.
            assert chrono_numbers == sorted(chrono_numbers)

    def test_character_random_title_rows_are_tagged(self, specs: tuple[NodeSpec, ...]) -> None:
        character_specs = [
            spec
            for spec in specs[3].children[0].children
            if isinstance(spec.destination, RandomTitlesDestination)
            and spec.destination.tag is not None
        ]
        assert len(character_specs) == 6

        for spec in character_specs:
            assert spec.lazy_children is not None
            title_rows = spec.lazy_children()

            assert len(title_rows) == NUM_RANDOM_TITLES
            assert all(row.kind is NodeKind.TITLE_ROW for row in title_rows)

            assert isinstance(spec.destination, RandomTitlesDestination)
            assert spec.destination.tag is not None
            tagged_titles = get_tag_titles(spec.destination.tag)
            chrono_numbers = []
            for row in title_rows:
                assert row.fanta_info is not None
                assert row.fanta_info.comic_book_info.title in tagged_titles
                chrono_numbers.append(row.fanta_info.fanta_chronological_number)

            # Samples are displayed in chronological order.
            assert chrono_numbers == sorted(chrono_numbers)

    def test_each_expansion_resamples(self, specs: tuple[NodeSpec, ...]) -> None:
        surprise_me = specs[3].children[0].children[0]
        assert surprise_me.lazy_children is not None

        tree_spec_module = barks_reader.core.navigation.tree_spec
        with patch.object(
            tree_spec_module.random, "sample", wraps=tree_spec_module.random.sample
        ) as mock_sample:
            surprise_me.lazy_children()
            surprise_me.lazy_children()

        assert mock_sample.call_count == 2


class TestSearchAppendixIndex:
    def test_search_subtree(self, specs: tuple[NodeSpec, ...]) -> None:
        _assert_snapshot(specs[2], _SEARCH_SNAPSHOT)

    def test_appendix_subtree(self, specs: tuple[NodeSpec, ...]) -> None:
        _assert_snapshot(specs[4], _APPENDIX_SNAPSHOT)

    def test_index_without_wiki_bundle(self, specs: tuple[NodeSpec, ...]) -> None:
        _assert_snapshot(specs[5], _INDEX_SNAPSHOT)

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

        # Same tree as without the bundle, plus the wiki entry appended last.
        _assert_snapshot(specs[5], _INDEX_SNAPSHOT + _WIKI_INDEX_ENTRY + "\n")


def _info_with_issue(issue_number: int) -> MagicMock:
    info = MagicMock()
    info.comic_book_info.issue_number = issue_number
    return info


class TestYearRangeExtraText:
    """The per-kind label suffix. Pure functions over the range's title list."""

    def test_cs_extra_text_spans_first_to_last_issue(self) -> None:
        titles = [_info_with_issue(n) for n in (95, 31, 79)]
        assert _get_cs_year_range_extra_text(titles) == "WDCS 31-95"  # ty: ignore[invalid-argument-type]

    def test_count_extra_text_is_the_title_count(self) -> None:
        assert _get_count_extra_text([_info_with_issue(1)] * 43) == "43"
        assert _get_count_extra_text([]) == "0"

    def test_us_extra_text_spans_first_to_last_issue(self) -> None:
        titles = [_info_with_issue(n) for n in (24, 11, 38)]
        assert _get_us_year_range_extra_text(titles) == "US 11-38"  # ty: ignore[invalid-argument-type]

    @pytest.mark.parametrize(
        ("fc_issue_num", "expected_us_number"),
        [
            pytest.param(US_1_FC_ISSUE_NUM, 1, id="us_1"),
            pytest.param(US_2_FC_ISSUE_NUM, 2, id="us_2"),
            pytest.param(US_3_FC_ISSUE_NUM, 3, id="us_3"),
        ],
    )
    def test_us_extra_text_remaps_the_four_color_issues(
        self, fc_issue_num: int, expected_us_number: int
    ) -> None:
        """The first three Uncle Scrooges shipped as Four Color issues.

        Their real issue numbers are in the hundreds, so without the remap they would
        sort last and the label would read e.g. 'US 4-386' instead of 'US 1-4'.
        """
        titles = [_info_with_issue(fc_issue_num), _info_with_issue(4)]
        assert _get_us_year_range_extra_text(titles) == f"US {expected_us_number}-4"  # ty: ignore[invalid-argument-type]


def test_random_titles_sample_from_the_whole_chronological_span(
    reader_settings: MagicMock, title_lists: dict[str, list[FantaComicBookInfo]]
) -> None:
    """'Surprise me' draws from every chronological year range, not a subset."""
    with (
        patch.object(barks_reader.core.navigation.tree_spec, "read_title_list", return_value=[]),
        patch.object(
            barks_reader.core.navigation.tree_spec,
            "special_case_personal_favourites_tag_update",
        ),
        patch.object(
            barks_reader.core.navigation.tree_spec.random, "sample", return_value=[]
        ) as mock_sample,
    ):
        specs = build_reader_tree_spec(
            reader_settings, title_lists, include_one_pagers_in_chrono=False
        )
        surprise_me = specs[3].children[0].children[0]
        assert surprise_me.lazy_children is not None
        surprise_me.lazy_children()

    expected_pool = sum(
        len(title_lists[str(year)])
        for year in range(CHRONO_YEAR_RANGES[0][0], CHRONO_YEAR_RANGES[-1][1] + 1)
    )
    pool = mock_sample.call_args.args[0]
    assert len(pool) == expected_pool


def test_chrono_includes_one_pagers_when_asked() -> None:
    """The other half of the `include_one_pagers_in_chrono` switch.

    The flag has to reach `get_num_comic_book_titles` for the chronological node's
    row-count assert to agree with title lists built the same way — and the resulting
    year ranges genuinely hold more titles than the default build does.
    """
    settings = MagicMock()
    settings.wiki_bundle_dir = None
    with_one_pagers = FilteredTitleLists(include_one_pagers_in_chrono=True).get_title_lists()

    with (
        patch.object(barks_reader.core.navigation.tree_spec, "read_title_list", return_value=[]),
        patch.object(
            barks_reader.core.navigation.tree_spec,
            "special_case_personal_favourites_tag_update",
        ),
    ):
        specs = build_reader_tree_spec(settings, with_one_pagers, include_one_pagers_in_chrono=True)

    chrono = specs[1].children[0]
    for year_range, spec in zip(CHRONO_YEAR_RANGES, chrono.children, strict=True):
        assert spec.lazy_children is not None
        assert len(spec.lazy_children()) == get_num_comic_book_titles(
            year_range, include_one_pagers=True
        )


def test_one_pagers_are_excluded_from_chrono_by_default(
    reader_settings: MagicMock, title_lists: dict[str, list[FantaComicBookInfo]]
) -> None:
    """`title_lists` here was built with one-pagers excluded.

    The chronological node asserts its row count against `get_num_comic_book_titles`,
    so a default of `True` would trip that assert rather than build the tree.
    """
    with (
        patch.object(barks_reader.core.navigation.tree_spec, "read_title_list", return_value=[]),
        patch.object(
            barks_reader.core.navigation.tree_spec,
            "special_case_personal_favourites_tag_update",
        ),
    ):
        # No exception expected.
        build_reader_tree_spec(reader_settings, title_lists)


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
        # Read from the configured favourites file specifically — not some other path.
        mock_read.assert_called_once_with(
            reader_settings.sys_file_paths.get_favourite_titles_path.return_value
        )
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
