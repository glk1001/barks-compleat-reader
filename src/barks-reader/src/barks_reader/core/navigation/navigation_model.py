"""`NavigationModel` — answers navigation-policy questions from destinations alone.

Consumers pass `Destination` descriptors and get back view-state resolutions,
auto-select decisions, the child a node opens on, and tag context. Pure — no Kivy
or UI imports. The widgets and coordinators in `ui/` route through it rather than
switching on widget subclass or node text.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

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
)

from barks_reader.core.filtered_title_lists import FilteredTitleLists
from barks_reader.core.view_request import ViewRequest

from .destinations import (
    AllSeriesDestination,
    AppendixDestination,
    ArticleDestination,
    CategoriesDestination,
    CategoryDestination,
    CensorshipFixesDocDestination,
    ChooseForMeDestination,
    ChronologicalDestination,
    ContinueReadingDestination,
    CorpusStatsDestination,
    Destination,
    DocumentDestination,
    HistoryDestination,
    HowToDocDestination,
    IllustratedHistoryDestination,
    IndexDestination,
    IntroDestination,
    IntroDocDestination,
    LocationsIndexDestination,
    MainIndexDestination,
    NamesIndexDestination,
    OnlyUnreadDestination,
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
    ThisMonthDestination,
    TitleDestination,
    TitleSearchDestination,
    WikiIndexDestination,
    WordSearchDestination,
    YearRangeDestination,
    YearRangeKind,
)
from .view_states import ViewStates

if TYPE_CHECKING:
    from collections.abc import Sequence

    from barks_fantagraphics.barks_tags import TagGroups, Tags


_SERIES_TO_VIEW_STATE: dict[str, ViewStates] = {
    SERIES_CS: ViewStates.ON_CS_NODE,
    SERIES_DDA: ViewStates.ON_DD_NODE,
    SERIES_USA: ViewStates.ON_US_NODE,
    SERIES_DDS: ViewStates.ON_DDS_NODE,
    SERIES_USS: ViewStates.ON_USS_NODE,
    SERIES_GG: ViewStates.ON_GG_NODE,
    SERIES_MISC: ViewStates.ON_MISC_NODE,
    SERIES_ONE_PAGERS: ViewStates.ON_ONE_PAGERS_NODE,
    SERIES_COVERS: ViewStates.ON_COVERS_NODE,
}


_SIMPLE_DESTINATION_TO_VIEW_STATE: dict[type[Destination], ViewStates] = {
    IntroDestination: ViewStates.ON_INTRO_NODE,
    IntroDocDestination: ViewStates.ON_INTRO_COMPLEAT_BARKS_READER_NODE,
    HowToDocDestination: ViewStates.ON_INTRO_HOW_TO_NODE,
    StoriesDestination: ViewStates.ON_THE_STORIES_NODE,
    ChronologicalDestination: ViewStates.ON_CHRONO_BY_YEAR_NODE,
    AllSeriesDestination: ViewStates.ON_SERIES_NODE,
    CategoriesDestination: ViewStates.ON_CATEGORIES_NODE,
    SearchDestination: ViewStates.ON_SEARCH_NODE,
    TitleSearchDestination: ViewStates.ON_TITLE_SEARCH_NODE,
    TagSearchDestination: ViewStates.ON_TAG_SEARCH_NODE,
    WordSearchDestination: ViewStates.ON_WORD_SEARCH_NODE,
    ReadingDestination: ViewStates.ON_READING_NODE,
    HistoryDestination: ViewStates.ON_HISTORY_NODE,
    # A list of title rows and nothing else: it keeps the view of the node it is under.
    ContinueReadingDestination: ViewStates.ON_READING_NODE,
    ChooseForMeDestination: ViewStates.ON_CHOOSE_FOR_ME_NODE,
    # A tick and nothing else: it keeps the view of the node it is under.
    OnlyUnreadDestination: ViewStates.ON_CHOOSE_FOR_ME_NODE,
    PlaylistsDestination: ViewStates.ON_PLAYLISTS_NODE,
    CorpusStatsDestination: ViewStates.ON_INTRO_BY_THE_NUMBERS_NODE,
    IllustratedHistoryDestination: ViewStates.ON_INTRO_ILLUSTRATED_HISTORY_NODE,
    AppendixDestination: ViewStates.ON_APPENDIX_NODE,
    StatisticsDestination: ViewStates.ON_APPENDIX_STATISTICS_NODE,
    CensorshipFixesDocDestination: ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE,
    IndexDestination: ViewStates.ON_INDEX_NODE,
    MainIndexDestination: ViewStates.ON_INDEX_MAIN_NODE,
    SpeechIndexDestination: ViewStates.ON_INDEX_SPEECH_NODE,
    SpeechWordsDestination: ViewStates.ON_INDEX_SPEECH_WORDS_NODE,
    NamesIndexDestination: ViewStates.ON_INDEX_NAMES_NODE,
    LocationsIndexDestination: ViewStates.ON_INDEX_LOCATIONS_NODE,
    WikiIndexDestination: ViewStates.ON_INDEX_WIKI_NODE,
    TitleDestination: ViewStates.ON_TITLE_NODE,
}


# The three searches under the Search node, the kinds Search can open on.
_SEARCH_KINDS: tuple[type[Destination], ...] = (
    TitleSearchDestination,
    TagSearchDestination,
    WordSearchDestination,
)


class BottomScreen(Enum):
    """A bottom screen with keys of its own, that Enter on its tree node moves them into."""

    MAIN_INDEX = auto()
    SPEECH_INDEX = auto()
    NAMES_INDEX = auto()
    LOCATIONS_INDEX = auto()
    STATISTICS = auto()
    HISTORY = auto()


class ReopenKind(Enum):
    """A full-window screen that Go Back onto its tree node opens again."""

    WIKI = auto()
    CORPUS_STATS = auto()
    DOCUMENT = auto()


# The Words node under the Speech Bubble Index shows the speech index's own screen.
_DESTINATION_TO_BOTTOM_SCREEN: dict[type[Destination], BottomScreen] = {
    MainIndexDestination: BottomScreen.MAIN_INDEX,
    SpeechIndexDestination: BottomScreen.SPEECH_INDEX,
    SpeechWordsDestination: BottomScreen.SPEECH_INDEX,
    NamesIndexDestination: BottomScreen.NAMES_INDEX,
    LocationsIndexDestination: BottomScreen.LOCATIONS_INDEX,
    StatisticsDestination: BottomScreen.STATISTICS,
    HistoryDestination: BottomScreen.HISTORY,
}

# Destinations whose node opens a full-window screen. Back onto one of these means
# "take me back in", not "show me the static view the node falls back to": a chapter
# left for one of its stories comes back at the page it was left on.
_DESTINATION_TO_REOPEN_KIND: dict[type[Destination], ReopenKind] = {
    WikiIndexDestination: ReopenKind.WIKI,
    CorpusStatsDestination: ReopenKind.CORPUS_STATS,
    DocumentDestination: ReopenKind.DOCUMENT,
}


class NavigationModel:
    """Kivy-free navigation policy engine.

    Methods are pure and side-effect-free. The instance is stateless today; it's
    a class rather than a module of free functions so callers have a single
    object to inject and future extensions (e.g., a tree of destinations) have a
    natural home.
    """

    @staticmethod
    def view_state_for(dest: Destination) -> ViewRequest:  # noqa: C901, PLR0911
        """Resolve the `ViewRequest` to render when `dest` is selected.

        Only the navigation-context fields are populated here; renderer-owned
        fields (fun-image themes, preserve-top-view, one-shot title image) are
        layered on by the caller. For year-range destinations the value is a
        formatted range string (matching what the tree-view node used to pass
        via `node.text`).
        """
        simple_state = _SIMPLE_DESTINATION_TO_VIEW_STATE.get(type(dest))
        if simple_state is not None:
            return ViewRequest(view_state=simple_state)

        if isinstance(dest, YearRangeDestination):
            return NavigationModel._year_range_view_state_for(dest)

        if isinstance(dest, SeriesDestination):
            return ViewRequest(view_state=_SERIES_TO_VIEW_STATE[dest.series_name])

        if isinstance(dest, CategoryDestination):
            return ViewRequest(view_state=ViewStates.ON_CATEGORY_NODE, category=dest.category)

        if isinstance(dest, TagGroupDestination):
            return ViewRequest(view_state=ViewStates.ON_TAG_GROUP_NODE, tag_group=dest.tag_group)

        if isinstance(dest, TagDestination | TagYearRangeDestination):
            # A tag's year group keeps the tag's own top view.
            return ViewRequest(view_state=ViewStates.ON_TAG_NODE, tag=dest.tag)

        if isinstance(dest, RandomTitlesDestination):
            year_range = (
                "" if dest.year_range is None else FilteredTitleLists.get_range_str(dest.year_range)
            )
            category = "" if dest.category is None else dest.category.value
            return ViewRequest(
                view_state=ViewStates.ON_RANDOM_TITLES_NODE,
                year_range=year_range,
                tag=dest.tag,
                category=category,
            )

        if isinstance(dest, PlaylistDestination):
            return ViewRequest(view_state=ViewStates.ON_PLAYLIST_NODE, playlist_id=dest.playlist_id)

        if isinstance(dest, ThisMonthDestination):
            return ViewRequest(view_state=ViewStates.ON_THIS_MONTH_NODE, month=dest.month)

        if isinstance(dest, ArticleDestination | DocumentDestination):
            return ViewRequest(view_state=dest.view_state)

        msg = f"No view state mapping for destination: {type(dest).__name__}"
        raise RuntimeError(msg)

    @staticmethod
    def _year_range_view_state_for(dest: YearRangeDestination) -> ViewRequest:
        """Resolve the `ViewRequest` for a year-range container node."""
        range_str = FilteredTitleLists.get_range_str((dest.start, dest.end))
        if dest.kind is YearRangeKind.CS:
            return ViewRequest(view_state=ViewStates.ON_CS_YEAR_RANGE_NODE, cs_year_range=range_str)
        if dest.kind is YearRangeKind.US:
            return ViewRequest(view_state=ViewStates.ON_US_YEAR_RANGE_NODE, us_year_range=range_str)
        # One-pager / cover year-range groups reuse their parent series' top-view
        # background rather than theming per range.
        if dest.kind is YearRangeKind.ONE_PAGER:
            return ViewRequest(view_state=ViewStates.ON_ONE_PAGERS_NODE)
        if dest.kind is YearRangeKind.COVER:
            return ViewRequest(view_state=ViewStates.ON_COVERS_NODE)
        if dest.kind is YearRangeKind.CHRONO:
            return ViewRequest(view_state=ViewStates.ON_YEAR_RANGE_NODE, year_range=range_str)
        # TAG: a tag's year group is a TagYearRangeDestination, which keeps the tag's
        # view; as a YearRangeDestination it would silently get the chronological one.
        msg = f"A {dest.kind.value} year range is not a YearRangeDestination: {dest}"
        raise RuntimeError(msg)

    @staticmethod
    def is_title(dest: Destination | None) -> bool:
        """Whether `dest` is a story's own row, not a group of them.

        A title row is the only node with a `TitleDestination`: selecting it shows the
        title, and it has nothing to open or close.
        """
        return isinstance(dest, TitleDestination)

    @staticmethod
    def bottom_screen_on_enter(dest: Destination | None) -> BottomScreen | None:
        """Return the bottom screen that Enter on `dest`'s node moves the keys into.

        None for a node whose screen has no keys of its own to move into: Enter there
        is a press.
        """
        return None if dest is None else _DESTINATION_TO_BOTTOM_SCREEN.get(type(dest))

    @staticmethod
    def reopens_on_back(dest: Destination | None) -> ReopenKind | None:
        """Return the full-window screen that Go Back onto `dest`'s node opens again.

        None for the rest: Go Back shows the node's view as it was left.
        """
        return None if dest is None else _DESTINATION_TO_REOPEN_KIND.get(type(dest))

    @staticmethod
    def auto_select_target(
        _parent: Destination, children: Sequence[Destination]
    ) -> TitleDestination | None:
        """Single-title-child rule: if exactly one child is a title, return it.

        When a parent node is expanded and contains exactly one title child, the
        UI auto-selects that title to skip an intermediate view-state flicker.
        """
        title_children = [c for c in children if isinstance(c, TitleDestination)]
        if len(title_children) == 1:
            return title_children[0]
        return None

    @staticmethod
    def search_kind_of(dest: Destination | None) -> type[Destination] | None:
        """Return which of the three searches `dest` is, or None if it is not one."""
        return type(dest) if isinstance(dest, _SEARCH_KINDS) else None

    @staticmethod
    def child_to_open_on(
        parent: Destination, last_search: type[Destination] | None = None
    ) -> type[Destination] | None:
        """Return the kind of child a parent goes straight to when the user opens it.

        Search opens on the search last used, and on its title search, the one most
        used, before any is: its own view is only a backdrop, and the other searches
        are a key or two down from it. The Speech Bubble Index opens on Words, the
        index its own view already shows.

        Args:
            parent: The node being opened.
            last_search: The search the user last went to this session, if any.

        """
        if isinstance(parent, SearchDestination):
            return last_search if last_search in _SEARCH_KINDS else TitleSearchDestination
        if isinstance(parent, SpeechIndexDestination):
            return SpeechWordsDestination
        return None

    @staticmethod
    def keep_top_view_for_title_under(parent: Destination | None) -> bool:
        """Whether selecting a title under *parent* should keep the current top view.

        The 'Choose for me' nodes theme the top view (character tag, decade, or
        the all-titles surprise image) and a playlist themes it from its own
        titles; keep that theme up while the user browses the list instead of
        re-rolling a generic image.
        """
        return isinstance(parent, RandomTitlesDestination | PlaylistDestination)

    @staticmethod
    def tag_context(dest: Destination) -> Tags | TagGroups | None:
        """Return the tag/tag-group carried by a destination, if any.

        Used when a title is selected under a tag container to determine which
        page to jump to (via `BARKS_TAGGED_PAGES`).
        """
        if isinstance(dest, TagDestination | TagYearRangeDestination):
            return dest.tag
        if isinstance(dest, TagGroupDestination):
            return dest.tag_group
        if isinstance(dest, RandomTitlesDestination):
            return dest.tag  # the 'With <character>' nodes; None for the decades and favourites
        return None
