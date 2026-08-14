"""Declarative spec for the reader's navigation tree.

`build_reader_tree_spec` composes the entire tree — node texts, destinations,
press behavior, registration hooks, and lazily-created title rows — as pure
data, with no Kivy involvement. `ui.reader_tree_builder.ReaderTreeBuilder`
walks the returned specs and instantiates the tree-view widgets.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import partial
from typing import TYPE_CHECKING, assert_never

from barks_fantagraphics.barks_tags import (
    BARKS_TAG_CATEGORIES,
    BARKS_TAG_CATEGORIES_TITLES,
    BARKS_TAG_GROUPS,
    TagCategories,
    TagGroups,
    Tags,
    get_sorted_tagged_titles,
    special_case_personal_favourites_tag_update,
)
from barks_fantagraphics.barks_titles import (
    US_1_FC_ISSUE_NUM,
    US_2_FC_ISSUE_NUM,
    US_3_FC_ISSUE_NUM,
    Titles,
)
from barks_fantagraphics.comic_issues import Issues
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
    get_fanta_info,
    get_num_comic_book_titles,
)

from barks_reader.core.filtered_title_lists import FilteredTitleLists
from barks_reader.core.playlists import PLAYLISTS, Playlist, get_playlist_title_infos
from barks_reader.core.reader_consts_and_types import (
    APPENDIX_CENSORSHIP_FIXES_NODE_TEXT,
    APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_TEXT,
    APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_TEXT,
    APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_TEXT,
    APPENDIX_NODE_TEXT,
    APPENDIX_RICH_TOMMASO_ON_COLORING_BARKS_TEXT,
    APPENDIX_STATISTICS_NODE_TEXT,
    CATEGORIES_NODE_TEXT,
    CHOOSE_FOR_ME_NODE_TEXT,
    CHRONO_YEAR_RANGES,
    CHRONOLOGICAL_NODE_TEXT,
    COVER_YEAR_RANGES,
    CS_YEAR_RANGES,
    FROM_FAVOURITES_NODE_TEXT,
    FROM_THE_1940S_NODE_TEXT,
    FROM_THE_1950S_NODE_TEXT,
    FROM_THE_1960S_NODE_TEXT,
    HISTORY_NODE_TEXT,
    INDEX_LOCATIONS_TEXT,
    INDEX_MAIN_TEXT,
    INDEX_NAMES_TEXT,
    INDEX_NODE_TEXT,
    INDEX_SPEECH_TEXT,
    INDEX_SPEECH_WORDS_TEXT,
    INDEX_WIKI_TEXT,
    INTRO_COMPLEAT_BARKS_READER_TEXT,
    INTRO_DON_AULT_FANTA_INTRO_TEXT,
    INTRO_NODE_TEXT,
    ONE_PAGER_YEAR_RANGES,
    PLAYLISTS_NODE_TEXT,
    RANDOM_TITLE_YEAR_RANGES,
    READING_NODE_TEXT,
    SEARCH_NODE_TEXT,
    SERIES_NODE_TEXT,
    SURPRISE_ME_NODE_TEXT,
    TAG_SEARCH_NODE_TEXT,
    THE_STORIES_NODE_TEXT,
    TITLE_SEARCH_NODE_TEXT,
    US_YEAR_RANGES,
    WITH_BEAGLE_BOYS_NODE_TEXT,
    WITH_DAISY_NODE_TEXT,
    WITH_GLADSTONE_NODE_TEXT,
    WITH_GRANDMA_DUCK_NODE_TEXT,
    WITH_GYRO_NODE_TEXT,
    WITH_SCROOGE_NODE_TEXT,
    WORD_SEARCH_NODE_TEXT,
)
from barks_reader.core.reader_formatter import (
    escape_editorial_brackets,
    get_bold_markup_text,
    get_markup_text_with_extra,
    get_markup_text_with_num_titles,
    hyphenate_text,
)
from barks_reader.core.reader_utils import read_title_list

from .destinations import (
    AllSeriesDestination,
    AppendixDestination,
    ArticleDestination,
    CategoriesDestination,
    CategoryDestination,
    CensorshipFixesDocDestination,
    ChooseForMeDestination,
    ChronologicalDestination,
    HistoryDestination,
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
    TitleSearchDestination,
    WikiIndexDestination,
    WordSearchDestination,
    YearRangeDestination,
    YearRangeKind,
)
from .view_states import ViewStates

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from barks_reader.core.reader_settings import ReaderSettings

    from .destinations import Destination


class NodeKind(Enum):
    """Which tree-view widget class the walker instantiates.

    `INTRO_TEXT` is a non-selectable prose row (a playlist's introduction); its
    already-hyphenated paragraph is carried in `NodeSpec.text`.
    """

    MAIN = auto()
    STORY_GROUP = auto()
    YEAR_RANGE = auto()
    TITLE_ROW = auto()
    INTRO_TEXT = auto()


class PressAction(Enum):
    """Which press handler the walker binds to the node.

    `TOGGLE_ONLY` nodes keep the widget's default expand/collapse behavior.
    """

    TOGGLE_ONLY = auto()
    SET_VIEW_STATE = auto()
    OPEN_INTRO_DOC = auto()
    OPEN_ARTICLE = auto()
    OPEN_CENSORSHIP_FIXES_DOC = auto()
    OPEN_SPEECH_INDEX = auto()
    OPEN_SPEECH_WORDS = auto()
    OPEN_WIKI_INDEX = auto()


class NodeRegistration(Enum):
    """Which 'node created' hook the walker calls with the built widget."""

    SEARCH = auto()
    HISTORY = auto()
    STATISTICS = auto()
    MAIN_INDEX = auto()
    SPEECH_INDEX = auto()
    SPEECH_WORDS = auto()
    NAMES_INDEX = auto()
    LOCATIONS_INDEX = auto()


@dataclass(frozen=True, slots=True)
class NodeSpec:
    """One navigable node: everything the walker needs to build its widget.

    `children` are built immediately; `lazy_children` is a zero-arg factory
    whose specs are built on the node's first expansion (title rows are
    deferred this way to keep the startup tree build fast). With
    `repopulate_on_expand`, the factory is instead re-run on *every*
    expansion, replacing the previous children (the random-title nodes).
    """

    kind: NodeKind
    text: str = ""
    destination: Destination | None = None
    press_action: PressAction = PressAction.TOGGLE_ONLY
    register_as: NodeRegistration | None = None
    start_closed: bool = False
    year_range_kind: YearRangeKind | None = None
    fanta_info: FantaComicBookInfo | None = None
    children: tuple[NodeSpec, ...] = field(default=())
    lazy_children: Callable[[], tuple[NodeSpec, ...]] | None = None
    repopulate_on_expand: bool = False


def build_reader_tree_spec(
    reader_settings: ReaderSettings,
    title_lists: dict[str, list[FantaComicBookInfo]],
    *,
    include_one_pagers_in_chrono: bool = False,
) -> tuple[NodeSpec, ...]:
    """Compose the full reader navigation tree as `NodeSpec`s.

    Args:
        reader_settings: Source of the favourite-titles path and wiki bundle dir.
        title_lists: Filtered title lists keyed as by `FilteredTitleLists`
            (series names, chrono years, and CS/US year keys).
        include_one_pagers_in_chrono: Whether `title_lists`' chrono year lists
            include one-pagers (checked against the expected title counts).

    Returns:
        The top-level specs in display order: Intro, The Stories, Search,
        Reading, Appendix, Index.

    """
    builder = _SpecBuilder(reader_settings, title_lists, include_one_pagers_in_chrono)
    return (
        builder.intro_spec(),
        builder.stories_spec(),
        builder.search_spec(),
        builder.reading_spec(),
        builder.appendix_spec(),
        builder.index_spec(),
    )


def _title_rows(title_infos: Iterable[FantaComicBookInfo]) -> tuple[NodeSpec, ...]:
    return tuple(
        NodeSpec(kind=NodeKind.TITLE_ROW, fanta_info=title_info) for title_info in title_infos
    )


NUM_RANDOM_TITLES = 5

# The 'With <character>' filter nodes under 'Choose for me': node text and the
# character's tag. Only characters with enough tagged titles (30+) to keep a
# random 5 fresh across re-rolls.
_CHARACTER_RANDOM_NODES: tuple[tuple[str, Tags], ...] = (
    (WITH_SCROOGE_NODE_TEXT, Tags.SCROOGE_NOT_IN_US),
    (WITH_GLADSTONE_NODE_TEXT, Tags.GLADSTONE_GANDER),
    (WITH_GYRO_NODE_TEXT, Tags.GYRO_GEARLOOSE),
    (WITH_DAISY_NODE_TEXT, Tags.DAISY),
    (WITH_BEAGLE_BOYS_NODE_TEXT, Tags.BEAGLE_BOYS),
    (WITH_GRANDMA_DUCK_NODE_TEXT, Tags.GRANDMA_DUCK),
)


def _random_title_rows(title_infos: list[FantaComicBookInfo]) -> tuple[NodeSpec, ...]:
    """Make title rows for a fresh random sample, displayed chronologically."""
    sample = random.sample(title_infos, min(len(title_infos), NUM_RANDOM_TITLES))
    sample.sort(key=lambda info: info.fanta_chronological_number)
    return _title_rows(sample)


def _playlist_rows(intro_text: str, title_infos: list[FantaComicBookInfo]) -> tuple[NodeSpec, ...]:
    """Make a playlist's children: its intro paragraph, then its titles.

    The titles keep the curated order they were written in — unlike every other
    title list in the tree, they are deliberately not sorted.
    """
    intro_row = NodeSpec(kind=NodeKind.INTRO_TEXT, text=intro_text)
    return (intro_row, *_title_rows(title_infos))


def _tagged_title_rows(titles: Iterable[Titles]) -> tuple[NodeSpec, ...]:
    """Make title rows for tagged titles, skipping any not in the Fanta info."""
    title_infos = (get_fanta_info(title) for title in titles)
    return _title_rows(info for info in title_infos if info is not None)


def _get_cs_year_range_extra_text(title_list: list[FantaComicBookInfo]) -> str:
    # Every Comics and Stories title ran in a numbered WDCS issue -- unlike the Uncle
    # Scrooge series there are no Dell Giants here, so this filter should never drop
    # anything. It is here so that a stray non-WDCS title cannot silently corrupt the
    # label; `test_comics_and_stories_series_is_all_wdcs` fails loudly if one appears.
    issue_numbers = [
        info.comic_book_info.issue_number
        for info in title_list
        if info.comic_book_info.issue_name is Issues.CS
    ]
    if not issue_numbers:
        return ""

    return f"WDCS {min(issue_numbers)}-{max(issue_numbers)}"


def _get_count_extra_text(title_list: list[FantaComicBookInfo]) -> str:
    """Extra label text for one-pager/cover year ranges: just the title count."""
    return str(len(title_list))


# US 1-3 shipped as Four Color issues, so they carry an 'FC' issue name and an issue number
# in the hundreds. They are matched by that number rather than by their issue name.
_US_ISSUE_NUM_FOR_FC_ISSUE_NUM = {
    US_1_FC_ISSUE_NUM: 1,
    US_2_FC_ISSUE_NUM: 2,
    US_3_FC_ISSUE_NUM: 3,
}


def _get_us_issue_number(fanta_info: FantaComicBookInfo) -> int | None:
    """Return the Uncle Scrooge issue number a title appeared in.

    Args:
        fanta_info: The title to look up.

    Returns:
        The Uncle Scrooge issue number, or ``None`` if the title did not run in one.

    """
    comic_book_info = fanta_info.comic_book_info
    if comic_book_info.issue_name is Issues.US:
        return comic_book_info.issue_number

    return _US_ISSUE_NUM_FOR_FC_ISSUE_NUM.get(comic_book_info.issue_number)


def _get_us_year_range_extra_text(title_list: list[FantaComicBookInfo]) -> str:
    # Some Uncle Scrooge Adventures ran in Dell Giants ('Uncle Scrooge Goes to Disneyland',
    # 'Disneyland Birthday Party') rather than in a numbered Uncle Scrooge. Those carry
    # their own issue #1, which would drag the lower bound of the range down to 1, so
    # only titles with a real Uncle Scrooge issue number count towards the label.
    issue_numbers = [
        issue_number
        for issue_number in (_get_us_issue_number(info) for info in title_list)
        if issue_number is not None
    ]
    if not issue_numbers:
        return ""

    return f"US {min(issue_numbers)}-{max(issue_numbers)}"


class _SpecBuilder:
    def __init__(
        self,
        reader_settings: ReaderSettings,
        title_lists: dict[str, list[FantaComicBookInfo]],
        include_one_pagers_in_chrono: bool,
    ) -> None:
        self._reader_settings = reader_settings
        self._title_lists = title_lists
        self._include_one_pagers_in_chrono = include_one_pagers_in_chrono

        self._series_names = [
            SERIES_CS,
            SERIES_DDA,
            SERIES_USA,
            SERIES_DDS,
            SERIES_USS,
            SERIES_GG,
            SERIES_MISC,
            SERIES_ONE_PAGERS,
            SERIES_COVERS,
        ]

    # --- Top-level nodes ---

    def intro_spec(self) -> NodeSpec:
        return NodeSpec(
            kind=NodeKind.MAIN,
            text=INTRO_NODE_TEXT,
            destination=IntroDestination(),
            children=(
                NodeSpec(
                    kind=NodeKind.MAIN,
                    text=INTRO_COMPLEAT_BARKS_READER_TEXT,
                    destination=IntroDocDestination(),
                    press_action=PressAction.OPEN_INTRO_DOC,
                    start_closed=True,
                ),
                self._article_spec(
                    INTRO_DON_AULT_FANTA_INTRO_TEXT,
                    ViewStates.ON_INTRO_DON_AULT_FANTA_INTRO_NODE,
                    Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION,
                ),
            ),
        )

    def stories_spec(self) -> NodeSpec:
        return NodeSpec(
            kind=NodeKind.MAIN,
            text=THE_STORIES_NODE_TEXT,
            destination=StoriesDestination(),
            children=(
                NodeSpec(
                    kind=NodeKind.STORY_GROUP,
                    text=get_bold_markup_text(CHRONOLOGICAL_NODE_TEXT),
                    destination=ChronologicalDestination(),
                    children=tuple(
                        self._chrono_year_range_spec(year_range)
                        for year_range in CHRONO_YEAR_RANGES
                    ),
                ),
                NodeSpec(
                    kind=NodeKind.STORY_GROUP,
                    text=get_bold_markup_text(SERIES_NODE_TEXT),
                    destination=AllSeriesDestination(),
                    children=tuple(
                        self._series_spec(series_name) for series_name in self._series_names
                    ),
                ),
                NodeSpec(
                    kind=NodeKind.STORY_GROUP,
                    text=get_bold_markup_text(CATEGORIES_NODE_TEXT),
                    destination=CategoriesDestination(),
                    children=tuple(self._category_spec(category) for category in TagCategories),
                ),
            ),
        )

    def search_spec(self) -> NodeSpec:
        return NodeSpec(
            kind=NodeKind.MAIN,
            text=SEARCH_NODE_TEXT,
            destination=SearchDestination(),
            register_as=NodeRegistration.SEARCH,
            children=(
                NodeSpec(
                    kind=NodeKind.STORY_GROUP,
                    text=TITLE_SEARCH_NODE_TEXT,
                    destination=TitleSearchDestination(),
                    press_action=PressAction.SET_VIEW_STATE,
                ),
                NodeSpec(
                    kind=NodeKind.STORY_GROUP,
                    text=TAG_SEARCH_NODE_TEXT,
                    destination=TagSearchDestination(),
                    press_action=PressAction.SET_VIEW_STATE,
                ),
                NodeSpec(
                    kind=NodeKind.STORY_GROUP,
                    text=WORD_SEARCH_NODE_TEXT,
                    destination=WordSearchDestination(),
                    press_action=PressAction.SET_VIEW_STATE,
                ),
            ),
        )

    def reading_spec(self) -> NodeSpec:
        return NodeSpec(
            kind=NodeKind.MAIN,
            text=READING_NODE_TEXT,
            destination=ReadingDestination(),
            children=(
                NodeSpec(
                    kind=NodeKind.STORY_GROUP,
                    text=CHOOSE_FOR_ME_NODE_TEXT,
                    destination=ChooseForMeDestination(),
                    children=(
                        self._random_titles_spec(SURPRISE_ME_NODE_TEXT, None),
                        self._random_titles_spec(
                            FROM_THE_1940S_NODE_TEXT, RANDOM_TITLE_YEAR_RANGES[0]
                        ),
                        self._random_titles_spec(
                            FROM_THE_1950S_NODE_TEXT, RANDOM_TITLE_YEAR_RANGES[1]
                        ),
                        self._random_titles_spec(
                            FROM_THE_1960S_NODE_TEXT, RANDOM_TITLE_YEAR_RANGES[2]
                        ),
                        self._category_random_titles_spec(
                            FROM_FAVOURITES_NODE_TEXT, TagCategories.FAVOURITES
                        ),
                        *(
                            self._character_random_titles_spec(text, tag)
                            for text, tag in _CHARACTER_RANDOM_NODES
                        ),
                    ),
                ),
                self._playlists_spec(),
                NodeSpec(
                    kind=NodeKind.STORY_GROUP,
                    text=HISTORY_NODE_TEXT,
                    destination=HistoryDestination(),
                    press_action=PressAction.SET_VIEW_STATE,
                    register_as=NodeRegistration.HISTORY,
                    start_closed=True,
                ),
            ),
        )

    def _playlists_spec(self) -> NodeSpec:
        return NodeSpec(
            kind=NodeKind.STORY_GROUP,
            text=PLAYLISTS_NODE_TEXT,
            destination=PlaylistsDestination(),
            children=tuple(self._playlist_spec(playlist) for playlist in PLAYLISTS),
        )

    @staticmethod
    def _playlist_spec(playlist: Playlist) -> NodeSpec:
        # Resolve the titles and hyphenate the intro here rather than inside the
        # lazy factory, so a curated title that is not in the Fanta collection
        # fails at startup rather than on the node's first expansion.
        title_infos = get_playlist_title_infos(playlist)
        intro_text = hyphenate_text(escape_editorial_brackets(playlist.intro))
        return NodeSpec(
            kind=NodeKind.STORY_GROUP,
            text=get_markup_text_with_num_titles(playlist.heading, len(title_infos)),
            destination=PlaylistDestination(playlist_id=playlist.playlist_id),
            lazy_children=partial(_playlist_rows, intro_text, title_infos),
        )

    def _random_titles_spec(self, text: str, year_range: tuple[int, int] | None) -> NodeSpec:
        all_years = (CHRONO_YEAR_RANGES[0][0], CHRONO_YEAR_RANGES[-1][1])
        title_list = self._year_range_titles(year_range or all_years, str)
        return NodeSpec(
            kind=NodeKind.STORY_GROUP,
            text=text,
            destination=RandomTitlesDestination(year_range=year_range),
            lazy_children=partial(_random_title_rows, title_list),
            repopulate_on_expand=True,
        )

    def _character_random_titles_spec(self, text: str, tag: Tags) -> NodeSpec:
        # Tag lists can contain titles outside the Fanta collection — skip those,
        # as _tagged_title_rows does.
        title_list = [
            info
            for title in get_sorted_tagged_titles(tag)
            if (info := get_fanta_info(title)) is not None
        ]
        return NodeSpec(
            kind=NodeKind.STORY_GROUP,
            text=text,
            destination=RandomTitlesDestination(tag=tag),
            lazy_children=partial(_random_title_rows, title_list),
            repopulate_on_expand=True,
        )

    def _category_random_titles_spec(self, text: str, category: TagCategories) -> NodeSpec:
        # A category aggregates every tag/group it contains (e.g. FAVOURITES spans
        # Barks', EveryGeek, personal, and Peter Schilling picks). As with the
        # character nodes, skip titles outside the Fanta collection.
        title_list = [
            info
            for title in BARKS_TAG_CATEGORIES_TITLES[category]
            if (info := get_fanta_info(title)) is not None
        ]
        return NodeSpec(
            kind=NodeKind.STORY_GROUP,
            text=text,
            destination=RandomTitlesDestination(category=category),
            lazy_children=partial(_random_title_rows, title_list),
            repopulate_on_expand=True,
        )

    def appendix_spec(self) -> NodeSpec:
        return NodeSpec(
            kind=NodeKind.MAIN,
            text=APPENDIX_NODE_TEXT,
            destination=AppendixDestination(),
            children=(
                self._article_spec(
                    APPENDIX_RICH_TOMMASO_ON_COLORING_BARKS_TEXT,
                    ViewStates.ON_APPENDIX_RICH_TOMMASO_ON_COLORING_BARKS_NODE,
                    Titles.RICH_TOMMASO___ON_COLORING_BARKS,
                ),
                self._article_spec(
                    APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_TEXT,
                    ViewStates.ON_APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_NODE,
                    Titles.DON_AULT___LIFE_AMONG_THE_DUCKS,
                ),
                self._article_spec(
                    APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_TEXT,
                    ViewStates.ON_APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_NODE,
                    Titles.MAGGIE_THOMPSON___COMICS_READERS_FIND_COMIC_BOOK_GOLD,
                ),
                self._article_spec(
                    APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_TEXT,
                    ViewStates.ON_APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_NODE,
                    Titles.GEORGE_LUCAS___AN_APPRECIATION,
                ),
                NodeSpec(
                    kind=NodeKind.MAIN,
                    text=APPENDIX_CENSORSHIP_FIXES_NODE_TEXT,
                    destination=CensorshipFixesDocDestination(),
                    press_action=PressAction.OPEN_CENSORSHIP_FIXES_DOC,
                    start_closed=True,
                ),
                NodeSpec(
                    kind=NodeKind.MAIN,
                    text=APPENDIX_STATISTICS_NODE_TEXT,
                    destination=StatisticsDestination(),
                    press_action=PressAction.SET_VIEW_STATE,
                    register_as=NodeRegistration.STATISTICS,
                    start_closed=True,
                ),
            ),
        )

    def index_spec(self) -> NodeSpec:
        children = [
            NodeSpec(
                kind=NodeKind.MAIN,
                text=INDEX_MAIN_TEXT,
                destination=MainIndexDestination(),
                press_action=PressAction.SET_VIEW_STATE,
                register_as=NodeRegistration.MAIN_INDEX,
            ),
            NodeSpec(
                kind=NodeKind.MAIN,
                text=INDEX_SPEECH_TEXT,
                destination=SpeechIndexDestination(),
                press_action=PressAction.OPEN_SPEECH_INDEX,
                register_as=NodeRegistration.SPEECH_INDEX,
                children=(
                    NodeSpec(
                        kind=NodeKind.MAIN,
                        text=INDEX_SPEECH_WORDS_TEXT,
                        destination=SpeechWordsDestination(),
                        press_action=PressAction.OPEN_SPEECH_WORDS,
                        register_as=NodeRegistration.SPEECH_WORDS,
                    ),
                    NodeSpec(
                        kind=NodeKind.MAIN,
                        text=INDEX_NAMES_TEXT,
                        destination=NamesIndexDestination(),
                        press_action=PressAction.SET_VIEW_STATE,
                        register_as=NodeRegistration.NAMES_INDEX,
                    ),
                    NodeSpec(
                        kind=NodeKind.MAIN,
                        text=INDEX_LOCATIONS_TEXT,
                        destination=LocationsIndexDestination(),
                        press_action=PressAction.SET_VIEW_STATE,
                        register_as=NodeRegistration.LOCATIONS_INDEX,
                    ),
                ),
            ),
        ]

        # Optional entry: shown only when the wiki-bundle setting resolves to a
        # real OKF bundle. Pressing it switches to the wiki reader screen. Like
        # the other side-effect leaves, a saved-node restore must render the
        # destination view, not replay the press (which would auto-open the
        # wiki screen at startup) — hence start_closed.
        if self._reader_settings.wiki_bundle_dir is not None:
            children.append(
                NodeSpec(
                    kind=NodeKind.MAIN,
                    text=INDEX_WIKI_TEXT,
                    destination=WikiIndexDestination(),
                    press_action=PressAction.OPEN_WIKI_INDEX,
                    start_closed=True,
                )
            )

        return NodeSpec(
            kind=NodeKind.MAIN,
            text=INDEX_NODE_TEXT,
            destination=IndexDestination(),
            children=tuple(children),
        )

    # --- Story subtree helpers ---

    def _chrono_year_range_spec(self, year_range: tuple[int, int]) -> NodeSpec:
        year_range_titles = self._year_range_titles(year_range, str)
        assert len(year_range_titles) == get_num_comic_book_titles(
            year_range, include_one_pagers=self._include_one_pagers_in_chrono
        )

        return self._year_range_spec(
            year_range,
            year_range_titles,
            extra_text=str(len(year_range_titles)),
            kind=YearRangeKind.CHRONO,
        )

    def _series_spec(self, series_name: str) -> NodeSpec:
        title_list = self._title_lists[series_name]
        text = get_markup_text_with_num_titles(series_name, len(title_list))
        destination = SeriesDestination(series_name=series_name)

        if series_name == SERIES_CS:
            return NodeSpec(
                kind=NodeKind.STORY_GROUP,
                text=text,
                destination=destination,
                children=tuple(
                    self._series_year_range_spec(
                        year_range,
                        kind=YearRangeKind.CS,
                        year_key_func=FilteredTitleLists.get_cs_year_key_from_year,
                        extra_text_func=_get_cs_year_range_extra_text,
                    )
                    for year_range in CS_YEAR_RANGES
                ),
            )

        if series_name == SERIES_USA:
            return NodeSpec(
                kind=NodeKind.STORY_GROUP,
                text=text,
                destination=destination,
                children=tuple(
                    self._series_year_range_spec(
                        year_range,
                        kind=YearRangeKind.US,
                        year_key_func=FilteredTitleLists.get_us_year_key_from_year,
                        extra_text_func=_get_us_year_range_extra_text,
                    )
                    for year_range in US_YEAR_RANGES
                ),
            )

        if series_name == SERIES_ONE_PAGERS:
            return self._year_range_series_spec(
                text,
                destination,
                title_list,
                year_ranges=ONE_PAGER_YEAR_RANGES,
                kind=YearRangeKind.ONE_PAGER,
                year_key_func=FilteredTitleLists.get_one_pager_year_key_from_year,
            )

        if series_name == SERIES_COVERS:
            return self._year_range_series_spec(
                text,
                destination,
                title_list,
                year_ranges=COVER_YEAR_RANGES,
                kind=YearRangeKind.COVER,
                year_key_func=FilteredTitleLists.get_cover_year_key_from_year,
            )

        return NodeSpec(
            kind=NodeKind.STORY_GROUP,
            text=text,
            destination=destination,
            lazy_children=partial(_title_rows, title_list),
        )

    def _year_range_series_spec(
        self,
        text: str,
        destination: SeriesDestination,
        title_list: list[FantaComicBookInfo],
        *,
        year_ranges: list[tuple[int, int]],
        kind: YearRangeKind,
        year_key_func: Callable[[int], str],
    ) -> NodeSpec:
        """Build a series node split into year-range groups (One Pagers / Covers).

        Unlike CS/US, these groups reuse their parent series' background and label
        themselves with a plain title count. The assert guards against a title
        falling outside every range (e.g. an undated cover) and silently vanishing.
        """
        children: list[NodeSpec] = []
        grouped_count = 0
        for year_range in year_ranges:
            year_range_titles = self._year_range_titles(year_range, year_key_func)
            grouped_count += len(year_range_titles)
            children.append(
                self._year_range_spec(
                    year_range,
                    year_range_titles,
                    extra_text=_get_count_extra_text(year_range_titles),
                    kind=kind,
                )
            )
        assert grouped_count == len(title_list), (
            f"{kind} year-range groups hold {grouped_count} titles"
            f" but the series has {len(title_list)}"
        )
        return NodeSpec(
            kind=NodeKind.STORY_GROUP,
            text=text,
            destination=destination,
            children=tuple(children),
        )

    def _series_year_range_spec(
        self,
        year_range: tuple[int, int],
        *,
        kind: YearRangeKind,
        year_key_func: Callable[[int], str],
        extra_text_func: Callable[[list[FantaComicBookInfo]], str],
    ) -> NodeSpec:
        year_range_titles = self._year_range_titles(year_range, year_key_func)
        return self._year_range_spec(
            year_range,
            year_range_titles,
            extra_text=extra_text_func(year_range_titles),
            kind=kind,
        )

    def _year_range_spec(
        self,
        year_range: tuple[int, int],
        year_range_titles: list[FantaComicBookInfo],
        *,
        extra_text: str,
        kind: YearRangeKind,
    ) -> NodeSpec:
        year_range_str = FilteredTitleLists.get_range_str(year_range)
        return NodeSpec(
            kind=NodeKind.YEAR_RANGE,
            text=get_markup_text_with_extra(year_range_str, extra_text),
            destination=YearRangeDestination(start=year_range[0], end=year_range[1], kind=kind),
            year_range_kind=kind,
            lazy_children=partial(_title_rows, year_range_titles),
        )

    def _year_range_titles(
        self, year_range: tuple[int, int], year_key_func: Callable[[int], str]
    ) -> list[FantaComicBookInfo]:
        year_range_titles: list[FantaComicBookInfo] = []
        for year in range(year_range[0], year_range[1] + 1):
            year_range_titles.extend(self._title_lists[year_key_func(year)])
        return year_range_titles

    # --- Category subtree helpers ---

    def _category_spec(self, category: TagCategories) -> NodeSpec:
        return NodeSpec(
            kind=NodeKind.STORY_GROUP,
            text=get_bold_markup_text(category.value),
            destination=CategoryDestination(category=category.value),
            children=self._tag_or_group_specs(BARKS_TAG_CATEGORIES[category]),
        )

    def _tag_or_group_specs(
        self, tags_or_groups: Iterable[Tags | TagGroups]
    ) -> tuple[NodeSpec, ...]:
        specs = []
        for tag_or_group in tags_or_groups:
            if isinstance(tag_or_group, Tags):
                specs.append(self._tag_spec(tag_or_group))
            elif isinstance(tag_or_group, TagGroups):
                specs.append(self._tag_group_spec(tag_or_group))
            else:
                # Fail loudly on malformed tag data instead of silently
                # dropping the entry from the Categories subtree.
                assert_never(tag_or_group)
        return tuple(specs)

    def _tag_group_spec(self, tag_group: TagGroups) -> NodeSpec:
        return NodeSpec(
            kind=NodeKind.STORY_GROUP,
            text=get_bold_markup_text(tag_group.value),
            destination=TagGroupDestination(tag_group=tag_group),
            children=self._tag_or_group_specs(BARKS_TAG_GROUPS[tag_group]),
        )

    def _tag_spec(self, tag: Tags) -> NodeSpec:
        titles = self._get_tagged_titles(tag)
        return NodeSpec(
            kind=NodeKind.STORY_GROUP,
            text=get_markup_text_with_num_titles(tag.value, len(titles)),
            destination=TagDestination(tag=tag),
            lazy_children=partial(_tagged_title_rows, titles),
        )

    def _get_tagged_titles(self, tag: Tags) -> list[Titles]:
        if tag != Tags.PERSONAL_FAVOURITES:
            return get_sorted_tagged_titles(tag)

        return self._get_favourite_titles()

    def _get_favourite_titles(self) -> list[Titles]:
        titles = read_title_list(self._reader_settings.sys_file_paths.get_favourite_titles_path())

        special_case_personal_favourites_tag_update(titles)

        return titles

    # --- Shared leaf helpers ---

    @staticmethod
    def _article_spec(text: str, view_state: ViewStates, article_title: Titles) -> NodeSpec:
        return NodeSpec(
            kind=NodeKind.MAIN,
            text=text,
            destination=ArticleDestination(view_state=view_state, article_title=article_title),
            press_action=PressAction.OPEN_ARTICLE,
            start_closed=True,
        )
