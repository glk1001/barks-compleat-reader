"""Backward-compatibility shim — delegates to `ui.view_renderer.ViewRenderer`.

All logic moved to `barks_reader.ui.view_renderer`. This module exists for the
migration window so existing callers (`MainScreen`, `NavigationCoordinator`,
`TreeViewManager`, tests) keep working; once they migrate to `ViewRenderer`
directly, this file will be deleted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_reader.core.navigation import NavigationModel

from .view_renderer import (
    ImageThemes,
    ImageThemesChange,
    ImageThemesToUse,
    ViewRenderer,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_tags import TagGroups, Tags
    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from comic_utils.comic_consts import PanelPath

    from barks_reader.core.image_selector import ImageInfo
    from barks_reader.core.navigation.view_states import ViewStates
    from barks_reader.core.reader_settings import ReaderSettings

    from .background_views import BackgroundViews
    from .screen_bundle import ScreenBundle
    from .snapshot_applicator import SnapshotApplicator

__all__ = [
    "ImageThemes",
    "ImageThemesChange",
    "ImageThemesToUse",
    "ViewStateManager",
]


class ViewStateManager:
    """Legacy facade — wraps a `ViewRenderer` and forwards every call."""

    def __init__(
        self,
        reader_settings: ReaderSettings,
        background_views: BackgroundViews,
        screens: ScreenBundle,
        applicator: SnapshotApplicator,
        on_view_state_changed_func: Callable[[ViewStates], None],
    ) -> None:
        self._renderer = ViewRenderer(
            reader_settings=reader_settings,
            pipeline=background_views.pipeline,
            applicator=applicator,
            screens=screens,
            nav_model=NavigationModel(),
            on_view_state_changed=on_view_state_changed_func,
        )

    @property
    def renderer(self) -> ViewRenderer:
        """Expose the underlying renderer (for callers migrating to it directly)."""
        return self._renderer

    def get_top_view_image_info(self) -> ImageInfo:
        return self._renderer.get_top_view_image_info()

    def get_bottom_view_fun_image_info(self) -> ImageInfo:
        return self._renderer.get_bottom_view_fun_image_info()

    def bottom_view_fun_image_themes_changed(self, themes_to_use: ImageThemesToUse) -> None:
        self._renderer.bottom_view_fun_image_themes_changed(themes_to_use)

    def bottom_view_alter_fun_image_themes(
        self, image_theme: ImageThemes, alteration: ImageThemesChange
    ) -> None:
        self._renderer.bottom_view_alter_fun_image_themes(image_theme, alteration)

    def set_view_state(
        self,
        view_state: ViewStates,
        category: str = "",
        year_range: str = "",
        cs_year_range: str = "",
        us_year_range: str = "",
        tag_group: TagGroups | None = None,
        tag: Tags | None = None,
        title_str: str = "",
        *,
        preserve_top_view: bool = False,
    ) -> None:
        params = {
            "category": category,
            "year_range": year_range,
            "cs_year_range": cs_year_range,
            "us_year_range": us_year_range,
            "tag_group": tag_group,
            "tag": tag,
            "title_str": title_str,
        }
        self._renderer.render_view_state_with_params(
            view_state, params, preserve_top_view=preserve_top_view
        )

    def update_search_background(self, title: Titles) -> None:
        self._renderer.update_search_background(title)

    def change_background_views(self) -> None:
        self._renderer.refresh()

    def update_view_for_node_with_title(
        self, view_state: ViewStates, *, preserve_top_view: bool = False
    ) -> None:
        self.update_view_for_node(
            view_state,
            title_str=self._renderer._pipeline.get_current_bottom_view_title(),  # noqa: SLF001
            preserve_top_view=preserve_top_view,
        )

    def update_view_for_node(
        self,
        view_state: ViewStates,
        *,
        preserve_top_view: bool = False,
        **args: str | TagGroups | Tags | None,
    ) -> None:
        self.set_view_state(
            view_state,
            preserve_top_view=preserve_top_view,
            **args,  # ty: ignore[invalid-argument-type]
        )

    def set_title(
        self, fanta_info: FantaComicBookInfo, title_image_file: PanelPath | None = None
    ) -> None:
        self._renderer.set_title_without_render(fanta_info, title_image_file)
