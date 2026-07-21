"""`NavigationModel` — answers navigation-policy questions from destinations alone.

Consumers pass `Destination` descriptors and get back view-state resolutions,
auto-select decisions, and tag context. Pure — no Kivy or UI imports.

This replaces the isinstance ladders and text-based lookups currently scattered
across `ui/tree_view_manager.py`, `ui/navigation_coordinator.py`, and
`ui/view_states.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_fantagraphics.comic_book_info import NON_COMIC_TITLES
from barks_fantagraphics.fanta_comics_info import (
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
    Destination,
    HistoryDestination,
    IndexDestination,
    IntroDestination,
    IntroDocDestination,
    LocationsIndexDestination,
    MainIndexDestination,
    NamesIndexDestination,
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
}


_SIMPLE_DESTINATION_TO_VIEW_STATE: dict[type[Destination], ViewStates] = {
    IntroDestination: ViewStates.ON_INTRO_NODE,
    IntroDocDestination: ViewStates.ON_INTRO_COMPLEAT_BARKS_READER_NODE,
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
    ChooseForMeDestination: ViewStates.ON_CHOOSE_FOR_ME_NODE,
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


_ARTICLE_VIEW_STATE_TO_TITLE_MAP_KEYS: set[ViewStates] = {
    ViewStates.ON_APPENDIX_RICH_TOMMASO_ON_COLORING_BARKS_NODE,
    ViewStates.ON_INTRO_DON_AULT_FANTA_INTRO_NODE,
    ViewStates.ON_APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_NODE,
    ViewStates.ON_APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_NODE,
    ViewStates.ON_APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_NODE,
}
# Invariant: the article view states correspond 1:1 with NON_COMIC_TITLES.
assert len(_ARTICLE_VIEW_STATE_TO_TITLE_MAP_KEYS) == len(NON_COMIC_TITLES)


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
            range_str = FilteredTitleLists.get_range_str((dest.start, dest.end))
            if dest.kind is YearRangeKind.CS:
                return ViewRequest(
                    view_state=ViewStates.ON_CS_YEAR_RANGE_NODE, cs_year_range=range_str
                )
            if dest.kind is YearRangeKind.US:
                return ViewRequest(
                    view_state=ViewStates.ON_US_YEAR_RANGE_NODE, us_year_range=range_str
                )
            return ViewRequest(view_state=ViewStates.ON_YEAR_RANGE_NODE, year_range=range_str)

        if isinstance(dest, SeriesDestination):
            return ViewRequest(view_state=_SERIES_TO_VIEW_STATE[dest.series_name])

        if isinstance(dest, CategoryDestination):
            return ViewRequest(view_state=ViewStates.ON_CATEGORY_NODE, category=dest.category)

        if isinstance(dest, TagGroupDestination):
            return ViewRequest(view_state=ViewStates.ON_TAG_GROUP_NODE, tag_group=dest.tag_group)

        if isinstance(dest, TagDestination):
            return ViewRequest(view_state=ViewStates.ON_TAG_NODE, tag=dest.tag)

        if isinstance(dest, RandomTitlesDestination):
            year_range = (
                "" if dest.year_range is None else FilteredTitleLists.get_range_str(dest.year_range)
            )
            return ViewRequest(
                view_state=ViewStates.ON_RANDOM_TITLES_NODE, year_range=year_range, tag=dest.tag
            )

        if isinstance(dest, ArticleDestination):
            return ViewRequest(view_state=dest.view_state)

        msg = f"No view state mapping for destination: {type(dest).__name__}"
        raise RuntimeError(msg)

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
    def keep_top_view_for_title_under(parent: Destination | None) -> bool:
        """Whether selecting a title under *parent* should keep the current top view.

        The 'Choose for me' nodes theme the top view (character tag, decade, or
        the all-titles surprise image); keep that theme up while the user
        browses the random picks instead of re-rolling a generic image.
        """
        return isinstance(parent, RandomTitlesDestination)

    @staticmethod
    def tag_context(dest: Destination) -> Tags | TagGroups | None:
        """Return the tag/tag-group carried by a destination, if any.

        Used when a title is selected under a tag container to determine which
        page to jump to (via `BARKS_TAGGED_PAGES`).
        """
        if isinstance(dest, TagDestination):
            return dest.tag
        if isinstance(dest, TagGroupDestination):
            return dest.tag_group
        return None
