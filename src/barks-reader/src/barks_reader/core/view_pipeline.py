# ruff: noqa: ERA001
"""Kivy-free view-rendering pipeline.

`ViewPipeline` owns the navigation-context state, the view-state → image
dispatch, the fun-image theme policy, and the periodic image-rotation timer.
It produces a `ViewSnapshot` describing the desired UI; an external
`SnapshotSink` (e.g. `ui.snapshot_applicator.SnapshotApplicator`) then pushes
that snapshot into the actual Kivy widgets.

External dependencies arrive as ports (`Scheduler`, `ColorSource`) so
the pipeline can be tested end-to-end without Kivy.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, ClassVar

from barks_fantagraphics.barks_tags import (
    BARKS_TAG_GROUPS_TITLES,
    BARKS_TAGGED_TITLES,
    TagGroups,
    Tags,
)
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, STR_TITLE_TO_ENUM, Titles
from barks_fantagraphics.comic_book_info import ONE_PAGERS, is_one_pager_collection
from barks_fantagraphics.comics_utils import get_abbrev_path
from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    ALL_LISTS,
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
from loguru import logger

from .filtered_title_lists import FilteredTitleLists
from .image_selector import FIT_MODE_COVER, ImageInfo, ImageSelector
from .navigation.view_states import ViewStates
from .ports import CancelHandle, ColorSource, PaletteId, Scheduler
from .reader_file_paths import ALL_TYPES, FileTypes
from .reader_formatter import get_formatted_color
from .view_request import ImageThemes, ViewRequest
from .view_snapshot import (
    FunViewSnapshot,
    ScreenVisibility,
    SearchViewSnapshot,
    TitleViewSnapshot,
    TopViewSnapshot,
    ViewSnapshot,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from comic_utils.comic_consts import PanelPath

    from .reader_colors import Color
    from .reader_settings import ReaderSettings


_TOP_VIEW_IMAGE_TYPES: set[FileTypes] = {
    t for t in FileTypes if t not in [FileTypes.NONTITLE, FileTypes.ORIGINAL_ART]
}
_TITLE_VIEW_IMAGE_TYPES: set[FileTypes] = {
    t for t in FileTypes if t not in [FileTypes.INSET, FileTypes.ORIGINAL_ART]
}

_DEBUG_FUN_IMAGE_TITLES = None
# _DEBUG_FUN_IMAGE_TITLES = [Titles.LOST_IN_THE_ANDES]


IMAGE_THEME_TO_FILE_TYPE_MAP = {
    ImageThemes.AI: FileTypes.AI,
    ImageThemes.BLACK_AND_WHITE: FileTypes.BLACK_AND_WHITE,
    ImageThemes.CENSORSHIP: FileTypes.CENSORSHIP,
    ImageThemes.FAVOURITES: FileTypes.FAVOURITE,
    ImageThemes.INSETS: FileTypes.INSET,
    ImageThemes.SILHOUETTES: FileTypes.SILHOUETTE,
    ImageThemes.SPLASHES: FileTypes.SPLASH,
}
IMAGE_THEMES_WITH_NO_FILES = {
    ImageThemes.CLASSICS,
    ImageThemes.FORTIES,
    ImageThemes.FIFTIES,
    ImageThemes.SIXTIES,
}
assert len(ImageThemes) == (len(IMAGE_THEME_TO_FILE_TYPE_MAP) + len(IMAGE_THEMES_WITH_NO_FILES))

_BOTTOM_VIEW_MAIN_INDEX_OPACITY_1_STATES = {
    ViewStates.ON_INDEX_MAIN_NODE,
}
_BOTTOM_VIEW_SPEECH_INDEX_OPACITY_1_STATES = {
    ViewStates.ON_INDEX_SPEECH_NODE,
    ViewStates.ON_INDEX_SPEECH_WORDS_NODE,
}
_BOTTOM_VIEW_NAMES_INDEX_OPACITY_1_STATES = {
    ViewStates.ON_INDEX_NAMES_NODE,
}
_BOTTOM_VIEW_LOCATIONS_INDEX_OPACITY_1_STATES = {
    ViewStates.ON_INDEX_LOCATIONS_NODE,
}
_BOTTOM_VIEW_STATISTICS_OPACITY_1_STATES = {
    ViewStates.ON_APPENDIX_STATISTICS_NODE,
}
_BOTTOM_VIEW_SEARCH_SCREEN_OPACITY_1_STATES = {
    ViewStates.ON_TITLE_SEARCH_NODE,
    ViewStates.ON_TAG_SEARCH_NODE,
    ViewStates.ON_WORD_SEARCH_NODE,
}
_BOTTOM_VIEW_TITLE_OPACITY_1_STATES = {
    ViewStates.ON_TITLE_NODE,
}
_BOTTOM_VIEW_FUN_IMAGE_OPACITY_1_STATES = (
    set(ViewStates)
    - _BOTTOM_VIEW_TITLE_OPACITY_1_STATES
    - _BOTTOM_VIEW_MAIN_INDEX_OPACITY_1_STATES
    - _BOTTOM_VIEW_STATISTICS_OPACITY_1_STATES
    - _BOTTOM_VIEW_SEARCH_SCREEN_OPACITY_1_STATES
    - _BOTTOM_VIEW_NAMES_INDEX_OPACITY_1_STATES
    - _BOTTOM_VIEW_LOCATIONS_INDEX_OPACITY_1_STATES
)
_SEARCH_MODE_MAP: dict[ViewStates, str] = {
    ViewStates.ON_TITLE_SEARCH_NODE: "Title",
    ViewStates.ON_TAG_SEARCH_NODE: "Tag",
    ViewStates.ON_WORD_SEARCH_NODE: "Word",
}


class ViewPipeline:
    """Owns navigation-context state and emits `ViewSnapshot`s.

    The pipeline holds the seven mutable context fields (category, year ranges,
    tag, tag group, current title, fun-image themes) plus the periodic-rotation
    timer state. `compute_snapshot()` returns an immutable description of the
    desired UI; callers (typically `ui.view_renderer.ViewRenderer`) feed that
    into a `SnapshotSink` to actually push to widgets.

    No Kivy imports here — periodic timing comes through the `Scheduler`
    port and color generation through the `ColorSource` port.
    """

    TOP_VIEW_EVENT_TIMEOUT_SECS = 1000.0
    BOTTOM_VIEW_EVENT_TIMEOUT_SECS = 1000.0

    _INTRO_VIEW_STATES: ClassVar[set[ViewStates]] = {
        ViewStates.ON_INTRO_NODE,
        ViewStates.ON_INTRO_COMPLEAT_BARKS_READER_NODE,
        ViewStates.ON_INTRO_DON_AULT_FANTA_INTRO_NODE,
    }

    _STORIES_VIEW_STATES: ClassVar[set[ViewStates]] = {
        ViewStates.ON_THE_STORIES_NODE,
        ViewStates.ON_CHRONO_BY_YEAR_NODE,
        ViewStates.ON_SERIES_NODE,
        ViewStates.ON_CATEGORIES_NODE,
        ViewStates.ON_TITLE_NODE,
    }

    _SERIES_VIEW_STATES: ClassVar[dict[ViewStates, str]] = {
        ViewStates.ON_CS_NODE: SERIES_CS,
        ViewStates.ON_DD_NODE: SERIES_DDA,
        ViewStates.ON_US_NODE: SERIES_USA,
        ViewStates.ON_DDS_NODE: SERIES_DDS,
        ViewStates.ON_USS_NODE: SERIES_USS,
        ViewStates.ON_GG_NODE: SERIES_GG,
        ViewStates.ON_MISC_NODE: SERIES_MISC,
        ViewStates.ON_ONE_PAGERS_NODE: SERIES_ONE_PAGERS,
    }

    _SEARCH_VIEW_STATES: ClassVar[set[ViewStates]] = {
        ViewStates.ON_SEARCH_NODE,
        ViewStates.ON_TITLE_SEARCH_NODE,
        ViewStates.ON_TAG_SEARCH_NODE,
        ViewStates.ON_WORD_SEARCH_NODE,
    }

    _APPENDIX_VIEW_STATES: ClassVar[set[ViewStates]] = {
        ViewStates.ON_APPENDIX_NODE,
        ViewStates.ON_APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_NODE,
        ViewStates.ON_APPENDIX_RICH_TOMMASO_ON_COLORING_BARKS_NODE,
        ViewStates.ON_APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_NODE,
        ViewStates.ON_APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_NODE,
        ViewStates.ON_APPENDIX_STATISTICS_NODE,
    }

    _INDEX_VIEW_STATES: ClassVar[set[ViewStates]] = {
        ViewStates.ON_INDEX_NODE,
        ViewStates.ON_INDEX_MAIN_NODE,
        ViewStates.ON_INDEX_SPEECH_NODE,
        ViewStates.ON_INDEX_SPEECH_WORDS_NODE,
        ViewStates.ON_INDEX_NAMES_NODE,
        ViewStates.ON_INDEX_LOCATIONS_NODE,
    }

    def __init__(
        self,
        *,
        reader_settings: ReaderSettings,
        title_lists: dict[str, list[FantaComicBookInfo]],
        image_selector: ImageSelector,
        scheduler: Scheduler,
        colors: ColorSource,
    ) -> None:
        self._reader_settings = reader_settings
        self._title_lists = title_lists
        self._image_selector = image_selector
        self._scheduler = scheduler
        self._colors = colors

        self._top_view_image_opacity = 0.0
        self._top_view_image_info: ImageInfo = ImageInfo()
        self._top_view_image_color: Color = (0, 0, 0, 0)
        self._top_view_change_event: CancelHandle | None = None

        self._bottom_view_title_opacity = 0.0

        self._bottom_view_fun_image_opacity = 0.0
        self._bottom_view_fun_image_info: ImageInfo | None = None
        self._bottom_view_fun_image_color: Color = (0, 0, 0, 0)
        self._bottom_view_change_fun_image_event: CancelHandle | None = None

        self._bottom_view_title_image_info: ImageInfo = ImageInfo()
        self._bottom_view_title_image_color: Color = (0, 0, 0, 0)

        self._current_year_range = ""
        self._current_cs_year_range = ""
        self._current_us_year_range = ""
        self._current_category = ""
        self._current_tag_group: TagGroups | None = None
        self._current_tag: Tags | None = None
        self._current_bottom_view_title = ""

        self._search_screen_image_info: ImageInfo = ImageInfo()

        self._fun_image_themes: set[ImageThemes] | None = None
        self._cached_fun_titles: tuple[list[FantaComicBookInfo], set[FileTypes]] | None = None
        self._set_fun_image_themes(None)

        self._view_state = ViewStates.PRE_INIT

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def render(self, request: ViewRequest, *, force_fresh_fun_image: bool = False) -> ViewSnapshot:
        """Apply *request*, refresh all derived view fields, and return a snapshot.

        This is the single entry point. It writes the request's navigation
        context onto the internal fields, applies the fun-image theme policy,
        transitions to `request.view_state`, and returns the resulting
        `ViewSnapshot`. The one-shot `request.title_image_file` is consumed by
        this call and then cleared. Pass `force_fresh_fun_image=True` (used by
        `refresh`) to re-pick the fun-image even in states that would keep it.
        """
        self._current_category = request.category
        self._current_year_range = request.year_range
        self._current_cs_year_range = request.cs_year_range
        self._current_us_year_range = request.us_year_range
        self._current_tag_group = request.tag_group
        self._current_tag = request.tag
        self._current_bottom_view_title = request.title_str
        if force_fresh_fun_image:
            self._bottom_view_fun_image_info = None
        self._set_bottom_view_title_image_file(request.title_image_file)
        self._set_fun_image_themes(request.fun_image_themes)

        logger.info(f"Updating background view state to {request.view_state.name}.")
        self._view_state = request.view_state
        self._update_views(preserve_top_view=request.preserve_top_view)

        snapshot = self._compute_snapshot()
        # The provided title image file is one-shot - clear it now it's been used.
        self._set_bottom_view_title_image_file(None)
        return snapshot

    def current_request(self) -> ViewRequest:
        """Return a `ViewRequest` describing the live navigation context.

        Used by `refresh` to re-render the current view. The one-shot
        `title_image_file` is deliberately not carried.
        """
        return ViewRequest(
            view_state=self._view_state,
            category=self._current_category,
            year_range=self._current_year_range,
            cs_year_range=self._current_cs_year_range,
            us_year_range=self._current_us_year_range,
            tag_group=self._current_tag_group,
            tag=self._current_tag,
            title_str=self._current_bottom_view_title,
            fun_image_themes=self._fun_image_themes,
        )

    def set_title(self, title_str: str, title_image_file: PanelPath | None) -> None:
        """Set the current title and pick its bottom title-view image in place.

        Used for the "configure the title view without a view-state transition"
        flow (`ViewRenderer.set_title_without_render`).
        """
        self._current_bottom_view_title = title_str
        self._set_bottom_view_title_image_file(title_image_file)
        self._set_next_bottom_view_title_image()

    def get_view_state(self) -> ViewStates:
        """Return the currently active view state."""
        return self._view_state

    def get_search_screen_image_info(self) -> ImageInfo:
        """Return the currently chosen search-screen image info."""
        return self._search_screen_image_info

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _set_fun_image_themes(self, image_themes: set[ImageThemes] | None) -> None:
        """Set the active fun-image themes; resets the cached title list."""
        logger.debug(f"Set self._fun_image_themes = {image_themes}.")
        self._fun_image_themes = image_themes
        self._cached_fun_titles = self._get_fun_image_titles()

    def _compute_snapshot(self) -> ViewSnapshot:
        """Build an immutable snapshot of the current view state.

        Called by `render()` after `_update_views()` has refreshed internal
        fields. Reads those fields and returns a `ViewSnapshot` that fully
        describes the desired UI.
        """
        search_mode = _SEARCH_MODE_MAP.get(self._view_state, "")
        search_visible = self._view_state in _BOTTOM_VIEW_SEARCH_SCREEN_OPACITY_1_STATES

        return ViewSnapshot(
            view_state=self._view_state,
            top_view=TopViewSnapshot(
                image_info=self._top_view_image_info,
                image_opacity=self._top_view_image_opacity,
                image_color=self._top_view_image_color,
            ),
            fun_view=FunViewSnapshot(
                is_visible=self._bottom_view_fun_image_opacity > 0.0,
                image_info=self._bottom_view_fun_image_info,
                image_color=self._bottom_view_fun_image_color,
            ),
            title_view=TitleViewSnapshot(
                is_visible=self._bottom_view_title_opacity > 0.0,
                image_info=self._bottom_view_title_image_info,
                image_color=self._bottom_view_title_image_color,
            ),
            screen_visibility=ScreenVisibility(
                main_index=self._view_state in _BOTTOM_VIEW_MAIN_INDEX_OPACITY_1_STATES,
                speech_index=self._view_state in _BOTTOM_VIEW_SPEECH_INDEX_OPACITY_1_STATES,
                names_index=self._view_state in _BOTTOM_VIEW_NAMES_INDEX_OPACITY_1_STATES,
                locations_index=self._view_state in _BOTTOM_VIEW_LOCATIONS_INDEX_OPACITY_1_STATES,
                statistics=self._view_state in _BOTTOM_VIEW_STATISTICS_OPACITY_1_STATES,
            ),
            search_view=SearchViewSnapshot(
                is_visible=search_visible,
                mode=search_mode,
                image_info=self._search_screen_image_info if search_visible else None,
            ),
        )

    def _update_views(self, *, preserve_top_view: bool = False) -> None:
        if self._view_state == ViewStates.PRE_INIT:
            self._top_view_image_opacity = 0.5
            self._set_next_top_view_image()
            self._bottom_view_fun_image_opacity = 0.5
            self._set_next_bottom_view_fun_image()
            self._bottom_view_title_opacity = 0.0
            return

        self._bottom_view_fun_image_opacity = (
            1.0 if self._view_state in _BOTTOM_VIEW_FUN_IMAGE_OPACITY_1_STATES else 0.0
        )
        self._bottom_view_title_opacity = (
            1.0 if self._view_state in _BOTTOM_VIEW_TITLE_OPACITY_1_STATES else 0.0
        )

        if not preserve_top_view:
            self._set_next_top_view_image()
        self._set_next_bottom_view_fun_image()
        self._set_next_search_screen_image()
        self._set_next_bottom_view_title_image()
        self._set_bottom_view_title_image_color()

    def _set_next_top_view_image(self) -> None:
        # Dispatch table: (predicate, handler) pairs checked in order.
        dispatch: list[tuple[bool, Callable[[], None]]] = [
            (
                self._view_state in self._SERIES_VIEW_STATES,
                self._set_top_view_image_for_series,
            ),
            (
                self._view_state in {ViewStates.PRE_INIT, ViewStates.INITIAL},
                lambda: self._set_top_view_image_fixed(Titles.COLD_BARGAIN_A),
            ),
            (
                self._view_state in self._INTRO_VIEW_STATES,
                lambda: self._set_top_view_image_fixed(Titles.ADVENTURE_DOWN_UNDER),
            ),
            (
                self._view_state in self._STORIES_VIEW_STATES,
                self._set_top_view_image_for_stories,
            ),
            (
                self._view_state == ViewStates.ON_CS_YEAR_RANGE_NODE,
                self._set_top_view_image_for_cs_year_range,
            ),
            (
                self._view_state == ViewStates.ON_US_YEAR_RANGE_NODE,
                self._set_top_view_image_for_us_year_range,
            ),
            (
                self._view_state == ViewStates.ON_YEAR_RANGE_NODE,
                self._set_top_view_image_for_year_range,
            ),
            (
                self._view_state == ViewStates.ON_CATEGORY_NODE,
                self._set_top_view_image_for_category,
            ),
            (
                self._view_state == ViewStates.ON_TAG_GROUP_NODE,
                self._set_top_view_image_for_tag_group,
            ),
            (self._view_state == ViewStates.ON_TAG_NODE, self._set_top_view_image_for_tag),
            (self._view_state in self._SEARCH_VIEW_STATES, self._set_top_view_image_for_search),
            (
                self._view_state in self._APPENDIX_VIEW_STATES,
                lambda: self._set_top_view_image_fixed(Titles.FABULOUS_PHILOSOPHERS_STONE_THE),
            ),
            (
                self._view_state == ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE,
                self._set_top_view_image_for_appendix_censorship_fixes,
            ),
            (
                self._view_state in self._INDEX_VIEW_STATES,
                lambda: self._set_top_view_image_fixed(Titles.TRUANT_OFFICER_DONALD),
            ),
        ]

        for predicate, handler in dispatch:
            if predicate:
                handler()
                break
        else:
            msg = f"Unhandled view state: {self._view_state}"
            raise AssertionError(msg)

        self._set_top_view_image_color()
        self._schedule_top_view_event()

        assert self._top_view_image_info.filename

        logger.debug(
            f"Top view image:"
            f" State: {self._view_state.name},"
            f" Image: '{get_abbrev_path(self._top_view_image_info.filename)}',"
            f" FitMode: '{self._top_view_image_info.fit_mode}',"
            f" Color: {get_formatted_color(self._top_view_image_color)},"
            f" Opacity: {self._top_view_image_opacity}."
        )

    def _set_top_view_image_for_series(self) -> None:
        series_key = self._SERIES_VIEW_STATES[self._view_state]
        self._top_view_image_info = self._get_top_view_random_image(self._title_lists[series_key])

    def _set_top_view_image_for_stories(self) -> None:
        self._top_view_image_info = self._get_top_view_random_image(self._title_lists[ALL_LISTS])

    def _set_top_view_image_fixed(self, title: Titles) -> None:
        self._top_view_image_info = ImageInfo(
            self._reader_settings.file_paths.get_comic_inset_file(title), title, FIT_MODE_COVER
        )

    def _set_top_view_image_from_titles_or_fixed[T](
        self,
        current: T | None,
        get_title_list: Callable[[T], list[FantaComicBookInfo]],
        fallback_title: Titles = Titles.GOOD_NEIGHBORS,
    ) -> None:
        """Set a random top-view image from *get_title_list*.

        Falls back to *fallback_title* if *current* (the navigation context the
        list depends on) is unset.
        """
        if not current:
            self._set_top_view_image_fixed(fallback_title)
        else:
            self._top_view_image_info = self._get_top_view_random_image(get_title_list(current))

    def _set_top_view_image_for_category(self) -> None:
        logger.debug(f"Current category: '{self._current_category}'.")
        self._set_top_view_image_from_titles_or_fixed(
            self._current_category,
            lambda category: self._title_lists[category],
        )

    def _set_top_view_image_for_tag_group(self) -> None:
        logger.debug(f"Current tag_group: '{self._current_tag_group}'.")
        self._set_top_view_image_from_titles_or_fixed(
            self._current_tag_group,
            lambda tag_group: self._get_fanta_title_list(BARKS_TAG_GROUPS_TITLES[tag_group]),
        )

    def _set_top_view_image_for_tag(self) -> None:
        logger.debug(f"Current tag: '{self._current_tag}'.")
        self._set_top_view_image_from_titles_or_fixed(
            self._current_tag,
            lambda tag: self._get_fanta_title_list(BARKS_TAGGED_TITLES[tag]),
        )

    def _set_top_view_image_for_year_range(self) -> None:
        logger.debug(f"Year range: '{self._current_year_range}'.")
        self._set_top_view_image_from_titles_or_fixed(
            self._current_year_range,
            lambda year_range: self._title_lists[year_range],
        )

    def _set_top_view_image_for_cs_year_range(self) -> None:
        logger.debug(f"CS Year range: '{self._current_cs_year_range}'.")

        def get_titles(year_range: str) -> list[FantaComicBookInfo]:
            cs_range = FilteredTitleLists.get_cs_year_range_key_from_range(year_range)
            logger.debug(f"CS Year range key: '{cs_range}'.")
            return self._title_lists[cs_range]

        self._set_top_view_image_from_titles_or_fixed(self._current_cs_year_range, get_titles)

    def _set_top_view_image_for_us_year_range(self) -> None:
        logger.debug(f"US Year range: '{self._current_us_year_range}'.")

        def get_titles(year_range: str) -> list[FantaComicBookInfo]:
            us_range = FilteredTitleLists.get_us_year_range_key_from_range(year_range)
            logger.debug(f"US Year range key: '{us_range}'.")
            return self._title_lists[us_range]

        self._set_top_view_image_from_titles_or_fixed(
            self._current_us_year_range, get_titles, fallback_title=Titles.BACK_TO_THE_KLONDIKE
        )

    def _get_top_view_random_image(self, title_list: list[FantaComicBookInfo]) -> ImageInfo:
        return self._image_selector.get_random_image(
            title_list, file_types=_TOP_VIEW_IMAGE_TYPES, use_only_edited_if_possible=True
        )

    def _set_top_view_image_for_search(self) -> None:
        self._top_view_image_info = self._image_selector.get_random_search_image()

    def _set_top_view_image_for_appendix_censorship_fixes(self) -> None:
        self._top_view_image_info = self._image_selector.get_random_censorship_fix_image()

    def _set_top_view_image_color(self) -> None:
        self._top_view_image_color = self._colors.next_color(PaletteId.TOP_VIEW)

    def set_bottom_view_fun_image(self, image_info: ImageInfo) -> None:
        """Override the fun-view image directly (used by the fun-image screen)."""
        self._bottom_view_fun_image_info = image_info

    def _set_next_bottom_view_fun_image(self) -> None:
        if self._view_state in [
            ViewStates.ON_TITLE_NODE,
            ViewStates.ON_INDEX_MAIN_NODE,
            ViewStates.ON_INDEX_SPEECH_NODE,
            ViewStates.ON_INDEX_SPEECH_WORDS_NODE,
            ViewStates.ON_INDEX_NAMES_NODE,
            ViewStates.ON_INDEX_LOCATIONS_NODE,
            ViewStates.ON_APPENDIX_STATISTICS_NODE,
            ViewStates.ON_TITLE_SEARCH_NODE,
            ViewStates.ON_TAG_SEARCH_NODE,
            ViewStates.ON_WORD_SEARCH_NODE,
        ]:
            return

        if (self._view_state == ViewStates.INITIAL) and self._bottom_view_fun_image_info:
            return

        self._bottom_view_fun_image_info = self._get_next_fun_view_image_info()
        self._set_bottom_view_fun_image_color()
        self._schedule_bottom_view_fun_image_event()

        assert self._bottom_view_fun_image_info is not None
        assert self._bottom_view_fun_image_info.filename

        logger.debug(
            f"Bottom view fun image:"
            f" State: {self._view_state.name},"
            f" Image: '{get_abbrev_path(self._bottom_view_fun_image_info.filename)}',"
            f" FitMode: '{self._bottom_view_fun_image_info.fit_mode}',"
            f" Color: {get_formatted_color(self._bottom_view_fun_image_color)},"
            f" Opacity: {self._bottom_view_fun_image_opacity}."
        )

    def set_search_screen_image_for_title(self, title: Titles) -> None:
        """Pick a search-screen background image for the given title."""
        self._search_screen_image_info = self._image_selector.get_search_image_for_title(title)

    def _set_next_search_screen_image(self) -> None:
        if self._view_state not in _BOTTOM_VIEW_SEARCH_SCREEN_OPACITY_1_STATES:
            return
        self._search_screen_image_info = self._image_selector.get_random_search_image()

    def _get_next_fun_view_image_info(self) -> ImageInfo:
        if self._view_state == ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE:
            fanta_title_list = self._get_fanta_title_list(
                BARKS_TAGGED_TITLES[Tags.CENSORED_STORIES_BUT_FIXED]
            )
            return self._image_selector.get_random_image(fanta_title_list, use_random_fit_mode=True)

        assert self._cached_fun_titles
        titles, file_types = self._cached_fun_titles

        return self._image_selector.get_random_image(
            titles,
            file_types=file_types,
            use_random_fit_mode=True,
        )

    def _get_fun_image_titles(self) -> tuple[list[FantaComicBookInfo], set[FileTypes]]:
        if _DEBUG_FUN_IMAGE_TITLES:
            return [
                t
                for t in self._title_lists[ALL_LISTS]
                if t.comic_book_info.title in _DEBUG_FUN_IMAGE_TITLES
            ], self._get_file_types_to_use()

        if not self._fun_image_themes:
            return self._title_lists[ALL_LISTS], self._get_file_types_to_use()

        return self._get_themed_fun_image_titles()

    def _get_themed_fun_image_titles(self) -> tuple[list[FantaComicBookInfo], set[FileTypes]]:
        file_types = self._get_file_types_to_use()

        theme_titles: set[Titles] = set()

        assert self._fun_image_themes

        for theme, year_range in {
            ImageThemes.FORTIES: (1942, 1949),
            ImageThemes.FIFTIES: (1950, 1959),
            ImageThemes.SIXTIES: (1960, 1961),
        }.items():
            if theme in self._fun_image_themes:
                self._update_titles(theme_titles, year_range)

        if ImageThemes.CLASSICS in self._fun_image_themes:
            theme_titles.update(BARKS_TAGGED_TITLES[Tags.CLASSICS])

        for file_type in file_types:
            # `get_file_type_titles` works in filesystem title strings, so project the
            # accumulated enum set to strings for filtering and convert the result back.
            allowed_title_strs = {ENUM_TO_STR_TITLE[title] for title in theme_titles}
            theme_titles.update(
                STR_TITLE_TO_ENUM[title_str]
                for title_str in self._reader_settings.file_paths.get_file_type_titles(
                    file_type, allowed_title_strs
                )
            )

        return [ALL_FANTA_COMIC_BOOK_INFO[title] for title in theme_titles], file_types

    def _update_titles(self, title_set: set[Titles], year_range: tuple[int, int]) -> None:
        for year in range(year_range[0], year_range[1] + 1):
            title_set.update(info.comic_book_info.title for info in self._title_lists[str(year)])

    def _get_file_types_to_use(self) -> set[FileTypes]:
        if self._fun_image_themes is None:
            return ALL_TYPES

        file_types_to_use = set()

        for theme in self._fun_image_themes:
            if theme not in IMAGE_THEME_TO_FILE_TYPE_MAP:
                continue
            file_types_to_use.add(IMAGE_THEME_TO_FILE_TYPE_MAP[theme])

        if len(file_types_to_use) == 0:
            file_types_to_use = ALL_TYPES.copy()
            file_types_to_use.discard(FileTypes.NONTITLE)

        logger.debug(f"file_types_to_use = {file_types_to_use}")

        return file_types_to_use

    @staticmethod
    def _get_fanta_title_list(titles: list[Titles]) -> list[FantaComicBookInfo]:
        from barks_fantagraphics.fanta_comics_info import get_fanta_info  # noqa: PLC0415

        fanta_title_list = [get_fanta_info(title) for title in titles]
        return [title for title in fanta_title_list if title is not None]

    # TODO: Rationalize image color setters - make more responsive to individual images
    #       have fun images weighted to larger opacity and full color
    def _set_bottom_view_fun_image_color(self) -> None:
        self._bottom_view_fun_image_color = self._colors.next_color(PaletteId.FUN)

    def _set_next_bottom_view_title_image(self) -> None:
        """Pick the large bottom title-view image.

        One-pagers always draw their large image at random from the synthetic
        "All One-Pagers" collection (across whatever image types that collection
        has), rather than from the individual gag's title, since they are read
        as a page of that collection. This wins even over an explicitly provided
        image file. Otherwise an explicitly provided file is kept, falling back
        to a random image picked for the current title.
        """
        if self._current_title_is_one_pager():
            self._set_bottom_view_title_image_for(ENUM_TO_STR_TITLE[Titles.ALL_ONE_PAGERS])
            return

        if self._bottom_view_title_image_info.filename:
            logger.debug(
                f'Using provided title image file "{self._bottom_view_title_image_info.filename}".'
            )
            return

        if not self._current_bottom_view_title:
            logger.debug("No bottom view title set. Nothing to do.")
            return

        self._set_bottom_view_title_image_for(self._current_bottom_view_title)

    def _set_bottom_view_title_image_for(self, title_str: str) -> None:
        image_file = self._image_selector.get_random_image_for_title(
            title_str,
            _TITLE_VIEW_IMAGE_TYPES,
            use_only_edited_if_possible=True,
        )
        logger.debug(f'Using random title image file "{image_file}" for "{title_str}".')
        self._set_bottom_view_title_image_file(image_file)

    def _current_title_is_one_pager(self) -> bool:
        """Whether the current bottom-view title is a one-pager or the collection itself."""
        title = STR_TITLE_TO_ENUM.get(self._current_bottom_view_title)
        return title is not None and (title in ONE_PAGERS or is_one_pager_collection(title))

    def _set_bottom_view_title_image_file(self, image_file: PanelPath | None) -> None:
        """Replace the title-view image filename, preserving the other fields."""
        self._bottom_view_title_image_info = replace(
            self._bottom_view_title_image_info, filename=image_file
        )
        self._log_bottom_view_title_state()

    def _set_bottom_view_title_image_color(self) -> None:
        self._bottom_view_title_image_color = self._colors.next_color(PaletteId.TITLE)
        self._log_bottom_view_title_state()

    def _log_bottom_view_title_state(self) -> None:
        logger.debug(
            f"Bottom view title image:"
            f" State: {self._view_state.name},"
            f" Image: '{self._bottom_view_title_image_info.filename}',"
            f" FitMode: '{self._bottom_view_title_image_info.fit_mode}',"
            f" Color: {get_formatted_color(self._bottom_view_title_image_color)},"
            f" Opacity: {self._bottom_view_title_opacity}."
        )

    def _schedule_top_view_event(self) -> None:
        if self._top_view_change_event:
            self._top_view_change_event.cancel()

        self._top_view_change_event = self._scheduler.schedule_interval(
            self._set_next_top_view_image, self.TOP_VIEW_EVENT_TIMEOUT_SECS
        )

    def _schedule_bottom_view_fun_image_event(self) -> None:
        if self._bottom_view_change_fun_image_event:
            self._bottom_view_change_fun_image_event.cancel()

        self._bottom_view_change_fun_image_event = self._scheduler.schedule_interval(
            self._set_next_bottom_view_fun_image, self.BOTTOM_VIEW_EVENT_TIMEOUT_SECS
        )
