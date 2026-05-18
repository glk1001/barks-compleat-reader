"""Backward-compatibility shim — delegates to `core.view_pipeline.ViewPipeline`.

All logic moved to `barks_reader.core.view_pipeline`. This module exists for
the migration window so existing callers (`ViewStateManager`, tests) keep
working; once they migrate to `ViewRenderer` / `ViewPipeline` directly, this
file will be deleted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_reader.core.view_pipeline import (
    IMAGE_THEME_TO_FILE_TYPE_MAP,
    IMAGE_THEMES_WITH_NO_FILES,
    ImageThemes,
    ViewPipeline,
)

from .adapters import KivyClockScheduler, TintColorSource

if TYPE_CHECKING:
    from barks_fantagraphics.barks_tags import TagGroups, Tags
    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from comic_utils.comic_consts import PanelPath

    from barks_reader.core.image_selector import ImageInfo, ImageSelector
    from barks_reader.core.navigation.view_states import ViewStates
    from barks_reader.core.reader_settings import ReaderSettings
    from barks_reader.core.view_snapshot import ViewSnapshot

__all__ = [
    "IMAGE_THEMES_WITH_NO_FILES",
    "IMAGE_THEME_TO_FILE_TYPE_MAP",
    "BackgroundViews",
    "ImageThemes",
]


class BackgroundViews:
    """Thin shim that wraps a `ViewPipeline` configured with production adapters.

    Preserves the original `BackgroundViews` API while the rest of the codebase
    migrates to `ViewPipeline` / `ViewRenderer` directly.
    """

    TOP_VIEW_EVENT_TIMEOUT_SECS = ViewPipeline.TOP_VIEW_EVENT_TIMEOUT_SECS
    BOTTOM_VIEW_EVENT_TIMEOUT_SECS = ViewPipeline.BOTTOM_VIEW_EVENT_TIMEOUT_SECS

    def __init__(
        self,
        reader_settings: ReaderSettings,
        title_lists: dict[str, list[FantaComicBookInfo]],
        random_title_images: ImageSelector,
    ) -> None:
        self._pipeline = ViewPipeline(
            reader_settings=reader_settings,
            title_lists=title_lists,
            image_selector=random_title_images,
            scheduler=KivyClockScheduler(),
            colors=TintColorSource(),
        )

    @property
    def pipeline(self) -> ViewPipeline:
        """Expose the underlying pipeline (for callers migrating to it directly)."""
        return self._pipeline

    def set_fun_image_themes(self, image_themes: set[ImageThemes] | None) -> None:
        self._pipeline.set_fun_image_themes(image_themes)

    def get_view_state(self) -> ViewStates:
        return self._pipeline.get_view_state()

    def reset_bottom_view_fun_image_info(self) -> None:
        self._pipeline.reset_bottom_view_fun_image_info()

    def get_search_screen_image_info(self) -> ImageInfo:
        return self._pipeline.get_search_screen_image_info()

    def get_current_category(self) -> str:
        return self._pipeline.get_current_category()

    def set_current_category(self, cat: str) -> None:
        self._pipeline.set_current_category(cat)

    def get_current_tag_group(self) -> None | TagGroups:
        return self._pipeline.get_current_tag_group()

    def set_current_tag_group(self, tag_group: None | TagGroups) -> None:
        self._pipeline.set_current_tag_group(tag_group)

    def get_current_tag(self) -> None | Tags:
        return self._pipeline.get_current_tag()

    def set_current_tag(self, tag: None | Tags) -> None:
        self._pipeline.set_current_tag(tag)

    def get_current_year_range(self) -> str:
        return self._pipeline.get_current_year_range()

    def set_current_year_range(self, year_range: str) -> None:
        self._pipeline.set_current_year_range(year_range)

    def get_current_cs_year_range(self) -> str:
        return self._pipeline.get_current_cs_year_range()

    def set_current_cs_year_range(self, year_range: str) -> None:
        self._pipeline.set_current_cs_year_range(year_range)

    def get_current_us_year_range(self) -> str:
        return self._pipeline.get_current_us_year_range()

    def set_current_us_year_range(self, year_range: str) -> None:
        self._pipeline.set_current_us_year_range(year_range)

    def get_current_bottom_view_title(self) -> str:
        return self._pipeline.get_current_bottom_view_title()

    def set_current_bottom_view_title(self, title: str) -> None:
        self._pipeline.set_current_bottom_view_title(title)

    def set_view_state(self, view_state: ViewStates, *, preserve_top_view: bool = False) -> None:
        self._pipeline.set_view_state(view_state, preserve_top_view=preserve_top_view)

    def compute_snapshot(self) -> ViewSnapshot:
        return self._pipeline.compute_snapshot()

    def set_bottom_view_fun_image(self, image_info: ImageInfo) -> None:
        self._pipeline.set_bottom_view_fun_image(image_info)

    def set_search_screen_image_for_title(self, title: Titles) -> None:
        self._pipeline.set_search_screen_image_for_title(title)

    def set_next_bottom_view_title_image(self) -> None:
        self._pipeline.set_next_bottom_view_title_image()

    def set_bottom_view_title_image_file(self, image_file: PanelPath | None) -> None:
        self._pipeline.set_bottom_view_title_image_file(image_file)
