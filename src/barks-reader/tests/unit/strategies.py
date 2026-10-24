"""Hypothesis strategies for the reader's domain types, shared by its property tests.

The "shared strategies" item of docs/BACKLOG.md: the builders a property test needs to
reach past plain strings and numbers into the reader's own types. Titles and tags come
from the real enums, a title's info from the real table, so a property holds over the
corpus and not over a stand-in. ``destinations`` builds one of every ``Destination``
kind; ``test_navigation_properties.py`` fails when a kind is added and not here.

Beside the tests, reached through ``conftest.py`` putting this directory on
``sys.path`` (the tests run under ``--import-mode=importlib``), as the barks-fantagraphics
tests do for ``panel_factories``.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from barks_fantagraphics.barks_tags_enums import TagCategories, TagGroups, Tags
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import NON_COMIC_TITLES
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    SERIES_COVERS,
    SERIES_CS,
    SERIES_DDA,
    SERIES_DDS,
    SERIES_GG,
    SERIES_MISC,
    SERIES_ONE_PAGERS,
    SERIES_USA,
    SERIES_USS,
)
from barks_reader.core.comic_book_page_info import PageInfo
from barks_reader.core.navigation.destinations import (
    AllSeriesDestination,
    AppendixDestination,
    ArticleDestination,
    CategoriesDestination,
    CategoryDestination,
    CensorshipFixesDocDestination,
    ChooseForMeDestination,
    ChronologicalDestination,
    CorpusStatsDestination,
    Destination,
    DocumentDestination,
    HistoryDestination,
    IllustratedHistoryDestination,
    IndexDestination,
    IntroDestination,
    IntroDocDestination,
    LocationsIndexDestination,
    MainIndexDestination,
    NamesIndexDestination,
    PlaylistDestination,
    PlaylistsDestination,
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
    TagYearRangeDestination,
    TitleDestination,
    TitleSearchDestination,
    WikiIndexDestination,
    WordSearchDestination,
    YearRangeDestination,
    YearRangeKind,
)
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.playlists import PLAYLISTS_BY_ID
from hypothesis import strategies as st

if TYPE_CHECKING:
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo

# The span Barks submitted stories in, for a year range drawn without a corpus lookup.
FIRST_BARKS_YEAR = 1942
LAST_BARKS_YEAR = 1966

SERIES_NAMES = (
    SERIES_CS,
    SERIES_DDA,
    SERIES_USA,
    SERIES_DDS,
    SERIES_USS,
    SERIES_GG,
    SERIES_MISC,
    SERIES_ONE_PAGERS,
    SERIES_COVERS,
)

ARTICLE_VIEW_STATES = (
    ViewStates.ON_APPENDIX_RICH_TOMMASO_ON_COLORING_BARKS_NODE,
    ViewStates.ON_INTRO_DON_AULT_FANTA_INTRO_NODE,
    ViewStates.ON_APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_NODE,
    ViewStates.ON_APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_NODE,
    ViewStates.ON_APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_NODE,
)

# The destinations that carry nothing: one instance each is every value they have.
NO_PAYLOAD_DESTINATION_TYPES: tuple[type[Destination], ...] = (
    IntroDestination,
    IntroDocDestination,
    CorpusStatsDestination,
    IllustratedHistoryDestination,
    StoriesDestination,
    ChronologicalDestination,
    AllSeriesDestination,
    CategoriesDestination,
    SearchDestination,
    TitleSearchDestination,
    TagSearchDestination,
    WordSearchDestination,
    ReadingDestination,
    HistoryDestination,
    ChooseForMeDestination,
    PlaylistsDestination,
    AppendixDestination,
    StatisticsDestination,
    CensorshipFixesDocDestination,
    IndexDestination,
    MainIndexDestination,
    SpeechIndexDestination,
    SpeechWordsDestination,
    NamesIndexDestination,
    LocationsIndexDestination,
    WikiIndexDestination,
)


# --- the corpus's enums and tables ---------------------------------------------


def titles() -> st.SearchStrategy[Titles]:
    """Draw any title the reader knows, the articles included."""
    return st.sampled_from(list(Titles))


def comic_titles() -> st.SearchStrategy[Titles]:
    """Draw a title that is a comic, not an article read through the comic reader."""
    return st.sampled_from([t for t in Titles if t not in NON_COMIC_TITLES])


def article_titles() -> st.SearchStrategy[Titles]:
    """Draw one of the articles read through the comic reader."""
    return st.sampled_from(NON_COMIC_TITLES)


def fanta_infos() -> st.SearchStrategy[FantaComicBookInfo]:
    """Draw a title's Fantagraphics info, from the real table."""
    return st.sampled_from(list(ALL_FANTA_COMIC_BOOK_INFO.values()))


def tags() -> st.SearchStrategy[Tags]:
    """Draw any tag."""
    return st.sampled_from(list(Tags))


def tag_groups() -> st.SearchStrategy[TagGroups]:
    """Draw any tag group."""
    return st.sampled_from(list(TagGroups))


def tag_categories() -> st.SearchStrategy[TagCategories]:
    """Draw any tag category."""
    return st.sampled_from(list(TagCategories))


@st.composite
def year_ranges(
    draw: st.DrawFn, min_year: int = FIRST_BARKS_YEAR, max_year: int = LAST_BARKS_YEAR
) -> tuple[int, int]:
    """Draw an inclusive range of submitted years, first no later than last."""
    years = st.integers(min_value=min_year, max_value=max_year)
    first, last = sorted((draw(years), draw(years)))
    return first, last


# --- pages ------------------------------------------------------------------------

PAGE_TYPES = st.sampled_from([PageType.FRONT, PageType.TITLE, PageType.BODY, PageType.BACK_MATTER])


@st.composite
def page_maps(draw: st.DrawFn, max_pages: int = 40) -> OrderedDict[str, PageInfo]:
    """Draw a page map as the layout builder makes them: indexes 0..n-1, display numbers 1..n.

    The source and destination pages are stand-ins: nothing in the pure core opens them.
    """
    count = draw(st.integers(min_value=1, max_value=max_pages))
    types = draw(st.lists(PAGE_TYPES, min_size=count, max_size=count))
    solos = draw(st.lists(st.booleans(), min_size=count, max_size=count))
    page_map: OrderedDict[str, PageInfo] = OrderedDict()
    for index in range(count):
        page_map[str(index + 1)] = PageInfo(
            page_index=index,
            display_page_num=str(index + 1),
            page_type=types[index],
            srce_page=MagicMock(),
            dest_page=MagicMock(),
            is_solo=solos[index],
        )
    return page_map


# --- destinations ---------------------------------------------------------------------


def no_payload_destinations() -> st.SearchStrategy[Destination]:
    """Draw one of the destinations that carry nothing."""
    return st.sampled_from([kind() for kind in NO_PAYLOAD_DESTINATION_TYPES])


def year_range_destinations() -> st.SearchStrategy[YearRangeDestination]:
    """Draw a year-range node of any kind."""
    return st.builds(
        lambda first_last, kind: YearRangeDestination(first_last[0], first_last[1], kind),
        year_ranges(),
        st.sampled_from(list(YearRangeKind)),
    )


def random_titles_destinations() -> st.SearchStrategy[RandomTitlesDestination]:
    """Draw a 'Choose for me' node: a decade, a character, favourites, or all titles."""
    return st.builds(
        RandomTitlesDestination,
        year_range=st.none() | year_ranges(),
        tag=st.none() | tags(),
        category=st.none() | tag_categories(),
    )


def payload_destinations() -> st.SearchStrategy[Destination]:
    """Draw one of the destinations that carry a payload, with a payload from the corpus."""
    return st.one_of(
        year_range_destinations(),
        st.builds(SeriesDestination, st.sampled_from(SERIES_NAMES)),
        st.builds(CategoryDestination, tag_categories().map(lambda c: c.value)),
        st.builds(TagGroupDestination, tag_groups()),
        st.builds(TagDestination, tags()),
        st.builds(
            lambda tag, first_last: TagYearRangeDestination(tag, first_last[0], first_last[1]),
            tags(),
            year_ranges(),
        ),
        random_titles_destinations(),
        st.builds(PlaylistDestination, st.sampled_from(sorted(PLAYLISTS_BY_ID))),
        st.builds(TitleDestination, fanta_infos()),
        st.builds(ArticleDestination, st.sampled_from(ARTICLE_VIEW_STATES), article_titles()),
        st.builds(
            DocumentDestination,
            st.just(ViewStates.ON_INTRO_ILLUSTRATED_HISTORY_NODE),
            st.text(min_size=1),
            st.text(min_size=1),
        ),
    )


def destinations() -> st.SearchStrategy[Destination]:
    """Draw any destination the tree can hold."""
    return st.one_of(no_payload_destinations(), payload_destinations())


# Every destination kind the strategies build; the navigation properties check it is
# every subclass of `Destination`, so a new kind cannot go untested.
DESTINATION_TYPES_BUILT: frozenset[type[Destination]] = frozenset(
    (
        *NO_PAYLOAD_DESTINATION_TYPES,
        YearRangeDestination,
        SeriesDestination,
        CategoryDestination,
        TagGroupDestination,
        TagDestination,
        TagYearRangeDestination,
        RandomTitlesDestination,
        PlaylistDestination,
        TitleDestination,
        ArticleDestination,
        DocumentDestination,
    )
)
