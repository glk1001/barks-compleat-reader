"""Unit tests for the Kivy-free NavigationModel.

These tests must import only from `barks_reader.core.navigation` and from
domain packages (`barks_fantagraphics`). Any import of Kivy, `barks_reader.ui`,
or a widget-level module would violate the core/ui boundary this refactor
is establishing.
"""

from __future__ import annotations

import sys
from typing import cast

import barks_reader.core.navigation as _nav_pkg  # noqa: F401
import barks_reader.core.navigation.destinations as _nav_destinations  # noqa: F401
import barks_reader.core.navigation.navigation_model as _nav_model_mod  # noqa: F401
import barks_reader.core.navigation.view_states as _nav_view_states  # noqa: F401
import pytest
from barks_fantagraphics.barks_tags import TagCategories, TagGroups, Tags
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.fanta_comics_info import (
    SERIES_COVERS,
    SERIES_CS,
    SERIES_DDA,
    SERIES_DDS,
    SERIES_GG,
    SERIES_MISC,
    SERIES_ONE_PAGERS,
    SERIES_USA,
    SERIES_USS,
    FantaComicBookInfo,
)
from barks_reader.core.filtered_title_lists import FilteredTitleLists
from barks_reader.core.navigation import (
    AppendixDestination,
    ArticleDestination,
    CategoriesDestination,
    CategoryDestination,
    CensorshipFixesDocDestination,
    ChooseForMeDestination,
    ChronologicalDestination,
    Destination,
    HistoryDestination,
    IndexDestination,
    IntroDestination,
    IntroDocDestination,
    LocationsIndexDestination,
    MainIndexDestination,
    NamesIndexDestination,
    NavigationModel,
    RandomTitlesDestination,
    ReadingDestination,
    SearchDestination,
    SeriesDestination,
    SpeechIndexDestination,
    SpeechWordsDestination,
    StatisticsDestination,
    StoriesDestination,
    TagDestination,
    TagGroupDestination,
    TagSearchDestination,
    TitleDestination,
    TitleSearchDestination,
    WordSearchDestination,
    YearRangeDestination,
    YearRangeKind,
)
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.view_request import ViewRequest


def _fake_fanta() -> FantaComicBookInfo:
    """Return a typed placeholder for `fanta_info`. NavigationModel never dereferences it."""
    return cast("FantaComicBookInfo", object())


@pytest.fixture
def model() -> NavigationModel:
    return NavigationModel()


# --- view_state_for: simple no-payload destinations -----------------------


@pytest.mark.parametrize(
    ("destination", "expected_state"),
    [
        (IntroDestination(), ViewStates.ON_INTRO_NODE),
        (IntroDocDestination(), ViewStates.ON_INTRO_COMPLEAT_BARKS_READER_NODE),
        (StoriesDestination(), ViewStates.ON_THE_STORIES_NODE),
        (ChronologicalDestination(), ViewStates.ON_CHRONO_BY_YEAR_NODE),
        (CategoriesDestination(), ViewStates.ON_CATEGORIES_NODE),
        (SearchDestination(), ViewStates.ON_SEARCH_NODE),
        (TitleSearchDestination(), ViewStates.ON_TITLE_SEARCH_NODE),
        (TagSearchDestination(), ViewStates.ON_TAG_SEARCH_NODE),
        (WordSearchDestination(), ViewStates.ON_WORD_SEARCH_NODE),
        (ReadingDestination(), ViewStates.ON_READING_NODE),
        (HistoryDestination(), ViewStates.ON_HISTORY_NODE),
        (ChooseForMeDestination(), ViewStates.ON_CHOOSE_FOR_ME_NODE),
        (AppendixDestination(), ViewStates.ON_APPENDIX_NODE),
        (StatisticsDestination(), ViewStates.ON_APPENDIX_STATISTICS_NODE),
        (CensorshipFixesDocDestination(), ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE),
        (IndexDestination(), ViewStates.ON_INDEX_NODE),
        (MainIndexDestination(), ViewStates.ON_INDEX_MAIN_NODE),
        (SpeechIndexDestination(), ViewStates.ON_INDEX_SPEECH_NODE),
        (SpeechWordsDestination(), ViewStates.ON_INDEX_SPEECH_WORDS_NODE),
        (NamesIndexDestination(), ViewStates.ON_INDEX_NAMES_NODE),
        (LocationsIndexDestination(), ViewStates.ON_INDEX_LOCATIONS_NODE),
    ],
)
def test_view_state_for_simple_destination(
    model: NavigationModel, destination: Destination, expected_state: ViewStates
) -> None:
    request = model.view_state_for(destination)
    assert request.view_state is expected_state
    assert request == ViewRequest(view_state=expected_state)


def test_view_state_for_title_destination(model: NavigationModel) -> None:
    request = model.view_state_for(TitleDestination(fanta_info=_fake_fanta()))
    assert request.view_state is ViewStates.ON_TITLE_NODE
    assert request == ViewRequest(view_state=ViewStates.ON_TITLE_NODE)


@pytest.mark.parametrize(
    ("year_range", "expected_range_str"),
    [
        (None, ""),
        ((1942, 1949), "1942-1949"),
        ((1950, 1959), "1950-1959"),
        ((1960, 1971), "1960-1971"),
    ],
)
def test_view_state_for_random_titles_destination(
    model: NavigationModel, year_range: tuple[int, int] | None, expected_range_str: str
) -> None:
    request = model.view_state_for(RandomTitlesDestination(year_range=year_range))
    assert request.view_state is ViewStates.ON_RANDOM_TITLES_NODE
    assert request.year_range == expected_range_str
    assert request.tag is None


def test_view_state_for_character_random_titles_destination(model: NavigationModel) -> None:
    request = model.view_state_for(RandomTitlesDestination(tag=Tags.SCROOGE_NOT_IN_US))
    assert request.view_state is ViewStates.ON_RANDOM_TITLES_NODE
    assert request.year_range == ""
    assert request.tag is Tags.SCROOGE_NOT_IN_US


def test_view_state_for_category_random_titles_destination(model: NavigationModel) -> None:
    request = model.view_state_for(RandomTitlesDestination(category=TagCategories.FAVOURITES))
    assert request.view_state is ViewStates.ON_RANDOM_TITLES_NODE
    assert request.year_range == ""
    assert request.tag is None
    assert request.category == TagCategories.FAVOURITES.value


@pytest.mark.parametrize(
    ("parent", "expected"),
    [
        (RandomTitlesDestination(), True),
        (RandomTitlesDestination(year_range=(1950, 1959)), True),
        (RandomTitlesDestination(tag=Tags.SCROOGE_NOT_IN_US), True),
        (RandomTitlesDestination(category=TagCategories.FAVOURITES), True),
        (TagDestination(tag=Tags.SCROOGE_NOT_IN_US), False),
        (SeriesDestination(series_name=SERIES_CS), False),
        (None, False),
    ],
)
def test_keep_top_view_for_title_under(
    model: NavigationModel, parent: Destination | None, expected: bool
) -> None:
    assert model.keep_top_view_for_title_under(parent) is expected


# --- view_state_for: series --------------------------------------------


@pytest.mark.parametrize(
    ("series_name", "expected_state"),
    [
        (SERIES_CS, ViewStates.ON_CS_NODE),
        (SERIES_DDA, ViewStates.ON_DD_NODE),
        (SERIES_USA, ViewStates.ON_US_NODE),
        (SERIES_DDS, ViewStates.ON_DDS_NODE),
        (SERIES_USS, ViewStates.ON_USS_NODE),
        (SERIES_GG, ViewStates.ON_GG_NODE),
        (SERIES_MISC, ViewStates.ON_MISC_NODE),
        (SERIES_ONE_PAGERS, ViewStates.ON_ONE_PAGERS_NODE),
        (SERIES_COVERS, ViewStates.ON_COVERS_NODE),
    ],
)
def test_view_state_for_series(
    model: NavigationModel, series_name: str, expected_state: ViewStates
) -> None:
    request = model.view_state_for(SeriesDestination(series_name=series_name))
    assert request.view_state is expected_state
    assert request == ViewRequest(view_state=expected_state)


# --- view_state_for: year ranges --------------------------------------


@pytest.mark.parametrize(
    ("kind", "expected_state", "expected_param"),
    [
        (YearRangeKind.CHRONO, ViewStates.ON_YEAR_RANGE_NODE, "year_range"),
        (YearRangeKind.CS, ViewStates.ON_CS_YEAR_RANGE_NODE, "cs_year_range"),
        (YearRangeKind.US, ViewStates.ON_US_YEAR_RANGE_NODE, "us_year_range"),
    ],
)
def test_view_state_for_year_range(
    model: NavigationModel,
    kind: YearRangeKind,
    expected_state: ViewStates,
    expected_param: str,
) -> None:
    dest = YearRangeDestination(start=1942, end=1946, kind=kind)
    request = model.view_state_for(dest)
    assert request.view_state is expected_state
    assert getattr(request, expected_param) == FilteredTitleLists.get_range_str((1942, 1946))


@pytest.mark.parametrize(
    ("kind", "expected_state"),
    [
        (YearRangeKind.ONE_PAGER, ViewStates.ON_ONE_PAGERS_NODE),
        (YearRangeKind.COVER, ViewStates.ON_COVERS_NODE),
    ],
)
def test_view_state_for_one_pager_and_cover_year_range_reuses_series_state(
    model: NavigationModel,
    kind: YearRangeKind,
    expected_state: ViewStates,
) -> None:
    """One-pager/cover year groups reuse the parent series view state (no range param)."""
    dest = YearRangeDestination(start=1946, end=1952, kind=kind)
    request = model.view_state_for(dest)
    assert request.view_state is expected_state
    assert request.year_range == ""
    assert request.cs_year_range == ""
    assert request.us_year_range == ""


# --- view_state_for: category / tag_group / tag -----------------------


def test_view_state_for_category(model: NavigationModel) -> None:
    request = model.view_state_for(CategoryDestination(category="My Category"))
    assert request.view_state is ViewStates.ON_CATEGORY_NODE
    assert request.category == "My Category"


def test_view_state_for_tag_group(model: NavigationModel) -> None:
    request = model.view_state_for(TagGroupDestination(tag_group=TagGroups.AFRICA))
    assert request.view_state is ViewStates.ON_TAG_GROUP_NODE
    assert request.tag_group == TagGroups.AFRICA


def test_view_state_for_tag(model: NavigationModel) -> None:
    request = model.view_state_for(TagDestination(tag=Tags.AIRPLANES))
    assert request.view_state is ViewStates.ON_TAG_NODE
    assert request.tag == Tags.AIRPLANES


# --- view_state_for: article ----------------------------------------


def test_view_state_for_article_returns_carried_state(model: NavigationModel) -> None:
    dest = ArticleDestination(
        view_state=ViewStates.ON_APPENDIX_RICH_TOMMASO_ON_COLORING_BARKS_NODE,
        article_title=Titles.RICH_TOMMASO___ON_COLORING_BARKS,
    )
    request = model.view_state_for(dest)
    assert request.view_state is ViewStates.ON_APPENDIX_RICH_TOMMASO_ON_COLORING_BARKS_NODE
    assert request == ViewRequest(
        view_state=ViewStates.ON_APPENDIX_RICH_TOMMASO_ON_COLORING_BARKS_NODE
    )


# --- view_state_for: unknown destination ------------------------------


def test_view_state_for_unknown_destination_raises(model: NavigationModel) -> None:
    class UnregisteredDestination(Destination):
        pass

    with pytest.raises(RuntimeError, match="No view state mapping"):
        model.view_state_for(UnregisteredDestination())


# --- auto_select_target -----------------------------------------------


def test_auto_select_target_returns_single_title_child(model: NavigationModel) -> None:
    only_child = TitleDestination(fanta_info=_fake_fanta())
    parent = TagDestination(tag=Tags.AIRPLANES)

    result = model.auto_select_target(parent, [only_child])
    assert result is only_child


def test_auto_select_target_none_when_no_title_children(model: NavigationModel) -> None:
    parent = TagGroupDestination(tag_group=TagGroups.AFRICA)
    children = [TagDestination(tag=Tags.AIRPLANES), TagDestination(tag=Tags.ALASKA)]

    assert model.auto_select_target(parent, children) is None


def test_auto_select_target_none_when_multiple_title_children(model: NavigationModel) -> None:
    parent = TagDestination(tag=Tags.AIRPLANES)
    children = [
        TitleDestination(fanta_info=_fake_fanta()),
        TitleDestination(fanta_info=_fake_fanta()),
    ]

    assert model.auto_select_target(parent, children) is None


def test_auto_select_target_ignores_non_title_siblings(model: NavigationModel) -> None:
    """One title + one non-title sibling still counts as a single-title-child parent."""
    title = TitleDestination(fanta_info=_fake_fanta())
    other = TagDestination(tag=Tags.AIRPLANES)
    parent = CategoryDestination(category="X")

    assert model.auto_select_target(parent, [other, title]) is title


# --- tag_context ------------------------------------------------------


def test_tag_context_extracts_tag(model: NavigationModel) -> None:
    assert model.tag_context(TagDestination(tag=Tags.AIRPLANES)) is Tags.AIRPLANES


def test_tag_context_extracts_tag_group(model: NavigationModel) -> None:
    assert model.tag_context(TagGroupDestination(tag_group=TagGroups.AFRICA)) is TagGroups.AFRICA


@pytest.mark.parametrize(
    "destination",
    [
        IntroDestination(),
        TitleDestination(fanta_info=_fake_fanta()),
        CategoryDestination(category="X"),
        YearRangeDestination(start=1942, end=1946, kind=YearRangeKind.CHRONO),
    ],
)
def test_tag_context_returns_none_for_non_tag_destinations(
    model: NavigationModel, destination: Destination
) -> None:
    assert model.tag_context(destination) is None


# --- purity check ----------------------------------------------------


def test_navigation_module_does_not_import_kivy() -> None:
    """Assert NavigationModel never imports kivy — the whole point of the refactor."""
    offenders = {name for name in sys.modules if name == "kivy" or name.startswith("kivy.")}
    # A previous test in the suite may have imported kivy; we can't assert absolute
    # purity once the process has loaded it. Instead, assert that the core.navigation
    # package itself does not reference the kivy namespace in any of its module
    # globals.
    for mod_name in (
        "barks_reader.core.navigation",
        "barks_reader.core.navigation.destinations",
        "barks_reader.core.navigation.navigation_model",
        "barks_reader.core.navigation.view_states",
    ):
        mod = sys.modules[mod_name]
        for attr_value in vars(mod).values():
            mod_attr = getattr(attr_value, "__module__", "")
            if isinstance(mod_attr, str):
                assert not mod_attr.startswith("kivy"), (
                    f"{mod_name} references kivy via {attr_value!r}; "
                    f"offenders-in-sys.modules={offenders}"
                )
