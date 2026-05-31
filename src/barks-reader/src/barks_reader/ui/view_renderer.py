"""`ViewRenderer` — caller-facing API for driving the view-rendering pipeline.

`ViewRenderer` is the thin orchestrator that sits between callers (tree-view
manager, navigation coordinator, main screen) and the lower-level
`core.view_pipeline.ViewPipeline` + `SnapshotApplicator` collaborators. The
primary call site is `render(destination)`; auxiliary flows live on the same
object so tests and call sites only deal with one facade.

This module owns the small amount of ScreenBundle-specific Kivy glue
(`fade_in_bottom_view_title`, search-screen background, fun-image callback
wiring) that doesn't belong in `core/`.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from loguru import logger

from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.reader_formatter import get_clean_text_without_extra
from barks_reader.core.view_pipeline import ImageThemes, ViewPipeline

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_tags import TagGroups, Tags
    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from comic_utils.comic_consts import PanelPath

    from barks_reader.core.image_selector import ImageInfo
    from barks_reader.core.navigation import NavigationModel
    from barks_reader.core.navigation.destinations import Destination
    from barks_reader.core.reader_settings import ReaderSettings

    from .screen_bundle import ScreenBundle
    from .snapshot_applicator import SnapshotApplicator


class ImageThemesToUse(Enum):
    """Whether to use all themes or the user's custom selection."""

    ALL = auto()
    CUSTOM = auto()


class ImageThemesChange(Enum):
    """Mutation kinds for the custom fun-image-theme set."""

    ADD = auto()
    DISCARD = auto()


class ViewRenderer:
    """Caller-facing renderer over the view pipeline and snapshot applicator."""

    def __init__(
        self,
        *,
        reader_settings: ReaderSettings,
        pipeline: ViewPipeline,
        applicator: SnapshotApplicator,
        screens: ScreenBundle,
        nav_model: NavigationModel,
        on_view_state_changed: Callable[[ViewStates], None],
    ) -> None:
        self._reader_settings = reader_settings
        self._pipeline = pipeline
        self._applicator = applicator
        self._screens = screens
        self._nav_model = nav_model
        self._on_view_state_changed = on_view_state_changed

        self._bottom_view_fun_image_themes: set[ImageThemes] | None = None
        self._bottom_view_fun_custom_image_themes: set[ImageThemes] = set(ImageThemes)

        screens.bottom_title_view.is_visible = False
        screens.fun_image_view.is_visible = False
        screens.main_index.is_visible = False
        screens.speech_index.is_visible = False
        screens.names_index.is_visible = False
        screens.locations_index.is_visible = False
        screens.statistics.is_visible = False
        screens.search.is_visible = False

        screens.fun_image_view.set_load_image_func(self._load_new_fun_view_image)

    # ------------------------------------------------------------------
    # Last-applied image info (used by main_screen for goto-title flow)
    # ------------------------------------------------------------------
    def get_top_view_image_info(self) -> ImageInfo:
        """Return the last-applied top view image info."""
        return self._applicator.get_prev_top_view_image_info()

    def get_bottom_view_fun_image_info(self) -> ImageInfo:
        """Return the last-applied fun view image info."""
        return self._applicator.get_prev_fun_view_image_info()

    # ------------------------------------------------------------------
    # Theme policy
    # ------------------------------------------------------------------
    def bottom_view_fun_image_themes_changed(self, themes_to_use: ImageThemesToUse) -> None:
        """Switch between using all themes vs the user's custom theme set."""
        if themes_to_use == ImageThemesToUse.ALL:
            self._bottom_view_fun_image_themes = None
        elif themes_to_use == ImageThemesToUse.CUSTOM:
            self._bottom_view_fun_image_themes = self._bottom_view_fun_custom_image_themes
        else:
            msg = f'Unimplemented ImageThemesToUse: "{themes_to_use}"'
            raise ValueError(msg)

    def bottom_view_alter_fun_image_themes(
        self, image_theme: ImageThemes, alteration: ImageThemesChange
    ) -> None:
        """Add or discard an `ImageTheme` from the user's custom theme set."""
        if alteration == ImageThemesChange.ADD:
            self._bottom_view_fun_custom_image_themes.add(image_theme)
        else:
            self._bottom_view_fun_custom_image_themes.discard(image_theme)

    # ------------------------------------------------------------------
    # Primary render paths
    # ------------------------------------------------------------------
    def render(self, destination: Destination, *, preserve_top_view: bool = False) -> None:
        """Resolve *destination* via `NavigationModel` and render the resulting view state."""
        view_state, params = self._nav_model.view_state_for(destination)
        self._apply_view_state(view_state, params, preserve_top_view=preserve_top_view)

    def render_state(self, view_state: ViewStates, *, preserve_top_view: bool = False) -> None:
        """Render *view_state* without any destination context (for boot / return paths)."""
        self._apply_view_state(view_state, {}, preserve_top_view=preserve_top_view)

    def render_view_state_with_params(
        self,
        view_state: ViewStates,
        params: dict[str, Any],
        *,
        preserve_top_view: bool = False,
    ) -> None:
        """Render *view_state* with explicit *params* (used by the legacy shim)."""
        self._apply_view_state(view_state, params, preserve_top_view=preserve_top_view)

    def render_title(
        self,
        fanta_info: FantaComicBookInfo,
        *,
        title_image_file: PanelPath | None = None,
        preserve_top_view: bool = False,
    ) -> None:
        """Render the title view for *fanta_info*.

        Performs the bottom-title-view fade-in side effect, resolves an edited
        version of *title_image_file* if one exists, and then transitions to
        `ON_TITLE_NODE` carrying the title.
        """
        self._screens.bottom_title_view.fade_in_bottom_view_title()

        title_str = fanta_info.comic_book_info.get_title_str()
        logger.debug(f'Setting title to "{title_str}". Title image file is "{title_image_file}".')

        if title_image_file is not None:
            title_image_file = self._reader_settings.file_paths.get_edited_version_if_possible(
                title_image_file
            )[0]

        self._pipeline.set_current_bottom_view_title(title_str)
        self._pipeline.set_bottom_view_title_image_file(title_image_file)
        self._screens.bottom_title_view.set_title_view(fanta_info)

        # NOTE: Don't pick the title image here - `_apply_view_state` triggers exactly
        # one pick via `_update_views`. Picking here too would re-roll twice per title
        # change, and the one-pager re-roll (which ignores any provided file) flips back
        # to the same image when the collection has an even number of candidates.
        self._apply_view_state(
            ViewStates.ON_TITLE_NODE,
            {"title_str": title_str},
            preserve_top_view=preserve_top_view,
        )

    def set_title_without_render(
        self,
        fanta_info: FantaComicBookInfo,
        title_image_file: PanelPath | None = None,
    ) -> None:
        """Configure the bottom-title view for *fanta_info* without transitioning state.

        Mirrors the legacy `ViewStateManager.set_title` behavior. Most callers
        should prefer `render_title`, which also drives the view-state change.
        """
        self._screens.bottom_title_view.fade_in_bottom_view_title()

        title_str = fanta_info.comic_book_info.get_title_str()
        logger.debug(f'Setting title to "{title_str}". Title image file is "{title_image_file}".')

        self._pipeline.set_current_bottom_view_title(title_str)

        if title_image_file is not None:
            assert self._pipeline.get_current_bottom_view_title() != ""
            title_image_file = self._reader_settings.file_paths.get_edited_version_if_possible(
                title_image_file
            )[0]

        self._pipeline.set_bottom_view_title_image_file(title_image_file)
        self._pipeline.set_next_bottom_view_title_image()
        self._screens.bottom_title_view.set_title_view(fanta_info)

    def refresh(self) -> None:
        """Re-apply the current view state, picking fresh decorative images."""
        logger.debug("Refreshing background views.")
        logger.debug(f'Current title: "{self._pipeline.get_current_bottom_view_title()}".')

        if self._screens.fun_image_view.is_visible:
            self._pipeline.reset_bottom_view_fun_image_info()

        self._apply_view_state(self._pipeline.get_view_state(), self._collect_current_params())

    def update_search_background(self, title: Titles) -> None:
        """Refresh the search-screen background to one drawn from *title*."""
        self._pipeline.set_search_screen_image_for_title(title)
        search_image_info = self._pipeline.get_search_screen_image_info()
        if search_image_info.filename:
            self._screens.search.set_background_image(search_image_info)
            self._applicator.load_search_texture(
                search_image_info,
                lambda tex: setattr(self._screens.search, "image_texture", tex),
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _apply_view_state(
        self,
        view_state: ViewStates,
        params: dict[str, Any],
        *,
        preserve_top_view: bool = False,
    ) -> None:
        """Apply view state + params: update pipeline context, compute, apply, notify."""
        self._apply_params(params)
        self._pipeline.set_fun_image_themes(self._bottom_view_fun_image_themes)
        self._pipeline.set_view_state(view_state, preserve_top_view=preserve_top_view)
        self._applicator.apply(self._pipeline.compute_snapshot())
        # Reset the title image file now that we've used it.
        self._pipeline.set_bottom_view_title_image_file(None)
        self._on_view_state_changed(view_state)

    def _apply_params(self, params: dict[str, Any]) -> None:
        """Forward `NavigationModel` params dict to the pipeline's context setters.

        Missing keys clear their respective context fields, matching the legacy
        `ViewStateManager.set_view_state` defaults.
        """
        category: str = params.get("category", "")
        year_range: str = params.get("year_range", "")
        cs_year_range: str = params.get("cs_year_range", "")
        us_year_range: str = params.get("us_year_range", "")
        tag_group: TagGroups | None = params.get("tag_group")
        tag: Tags | None = params.get("tag")
        title_str: str = params.get("title_str", "")

        self._pipeline.set_current_category(category)
        self._pipeline.set_current_year_range(get_clean_text_without_extra(year_range))
        self._pipeline.set_current_cs_year_range(get_clean_text_without_extra(cs_year_range))
        self._pipeline.set_current_us_year_range(get_clean_text_without_extra(us_year_range))
        self._pipeline.set_current_tag_group(tag_group)
        self._pipeline.set_current_tag(tag)
        self._pipeline.set_current_bottom_view_title(title_str)

    def _collect_current_params(self) -> dict[str, Any]:
        return {
            "category": self._pipeline.get_current_category(),
            "year_range": self._pipeline.get_current_year_range(),
            "cs_year_range": self._pipeline.get_current_cs_year_range(),
            "us_year_range": self._pipeline.get_current_us_year_range(),
            "tag_group": self._pipeline.get_current_tag_group(),
            "tag": self._pipeline.get_current_tag(),
            "title_str": self._pipeline.get_current_bottom_view_title(),
        }

    def _load_new_fun_view_image(self, image_info: ImageInfo) -> None:
        self._applicator.load_new_fun_view_image(image_info)
        self._pipeline.set_bottom_view_fun_image(image_info)
