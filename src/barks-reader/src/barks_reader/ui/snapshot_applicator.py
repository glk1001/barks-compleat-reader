"""Apply a ViewSnapshot to the actual Kivy screen widgets.

This is the only new class that directly touches Kivy widgets. It reads from
an immutable ``ViewSnapshot`` and pushes values to the screens in a
``ScreenBundle``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from comic_utils.timing import Timing
from loguru import logger

from barks_reader.core.image_selector import ImageInfo, get_title_str
from barks_reader.ui.panel_texture_loader import PanelTextureLoader

if TYPE_CHECKING:
    from collections.abc import Callable

    # noinspection PyProtectedMember
    from kivy.core.image import Texture

    from barks_reader.core.view_snapshot import (
        FunViewSnapshot,
        SearchViewSnapshot,
        TitleViewSnapshot,
        TopViewSnapshot,
        ViewSnapshot,
    )
    from barks_reader.ui.screen_bundle import ScreenBundle


class SnapshotApplicator:
    """Push a ``ViewSnapshot`` to the Kivy widgets in a ``ScreenBundle``."""

    def __init__(self, screens: ScreenBundle, panels_are_encrypted: bool) -> None:
        self._screens = screens

        self._top_view_texture_loader = PanelTextureLoader(panels_are_encrypted)
        self._fun_view_texture_loader = PanelTextureLoader(panels_are_encrypted)
        self._bottom_title_view_texture_loader = PanelTextureLoader(panels_are_encrypted)
        self._search_texture_loader = PanelTextureLoader(panels_are_encrypted)

        # Track the last-applied image infos.
        self._prev_top_view_image_info: ImageInfo = ImageInfo()
        self._prev_fun_view_from_title = None
        self._prev_fun_view_image_info: ImageInfo = ImageInfo()

    def apply(self, snapshot: ViewSnapshot) -> None:
        """Apply *snapshot* to the screen widgets."""
        self._apply_top_view(snapshot.top_view)
        self._apply_fun_view(snapshot.fun_view)
        self._apply_title_view(snapshot.title_view)
        self._apply_screen_visibility(snapshot)
        self._apply_search_view(snapshot.search_view)

        self._screens.fun_image_view.goto_title_button_active = (
            self._screens.fun_image_view.fun_view_from_title
            and (not self._screens.bottom_title_view.is_visible)
        )

    # ------------------------------------------------------------------
    # Top view
    # ------------------------------------------------------------------
    def get_prev_top_view_image_info(self) -> ImageInfo:
        """Return the last-applied top view image info."""
        return self._prev_top_view_image_info

    def _apply_top_view(self, top: TopViewSnapshot) -> None:
        self._prev_top_view_image_info = top.image_info
        if not top.image_info.filename:
            return

        def apply_tex(tex: Texture) -> None:
            tree = self._screens.tree_view
            tree.top_view_image_opacity = top.image_opacity
            tree.top_view_image_fit_mode = top.image_info.fit_mode
            tree.top_view_image_color = top.image_color
            tree.top_view_image_texture = tex

        self._load_texture(self._top_view_texture_loader, top.image_info, apply_tex)

        if top.image_info.from_title is not None:
            self._screens.tree_view.set_title(top.image_info.from_title)

    # ------------------------------------------------------------------
    # Fun (bottom decorative) view
    # ------------------------------------------------------------------
    def _apply_fun_view(self, fun: FunViewSnapshot) -> None:
        self._screens.fun_image_view.is_visible = fun.is_visible

        if not fun.is_visible:
            return

        if fun.image_info is None:
            return

        # Skip if the title hasn't changed (avoids redundant texture loads).
        if fun.image_info.from_title == self._prev_fun_view_from_title:
            return

        self._prev_fun_view_from_title = fun.image_info.from_title
        self._prev_fun_view_image_info = fun.image_info

        logger.debug(
            f'Applying fun view: from_title = "{get_title_str(fun.image_info.from_title)}".'
        )

        fun_info = fun.image_info
        if not fun_info.filename:
            self._screens.fun_image_view.image_texture = None
        else:

            def apply_tex(tex: Texture) -> None:
                self._screens.fun_image_view.image_fit_mode = fun_info.fit_mode
                self._screens.fun_image_view.image_color = fun.image_color
                self._screens.fun_image_view.image_texture = tex

            self._load_texture(self._fun_view_texture_loader, fun_info, apply_tex)
            self._screens.fun_image_view.set_last_loaded_image_info(fun_info)

    def load_new_fun_view_image(self, image_info: ImageInfo) -> None:
        """Load a new fun-view image triggered by the fun-image screen callback."""

        def apply_tex(tex: Texture) -> None:
            self._screens.fun_image_view.image_texture = tex

        self._load_texture(self._fun_view_texture_loader, image_info, apply_tex)

        self._prev_fun_view_from_title = image_info.from_title
        self._prev_fun_view_image_info = image_info

    def get_prev_fun_view_image_info(self) -> ImageInfo:
        """Return the last-applied fun view image info."""
        return self._prev_fun_view_image_info

    def load_search_texture(
        self,
        image_info: ImageInfo,
        apply_texture: Callable[[Texture], None],
    ) -> None:
        """Load a search background texture via the search texture loader."""
        self._load_texture(self._search_texture_loader, image_info, apply_texture)

    # ------------------------------------------------------------------
    # Title (bottom title info) view
    # ------------------------------------------------------------------
    def _apply_title_view(self, title: TitleViewSnapshot) -> None:
        self._screens.bottom_title_view.is_visible = title.is_visible

        title_info = title.image_info
        if title_info is None or not title_info.filename:
            self._screens.bottom_title_view.title_image_texture = None
        else:
            _title_info = title_info

            def apply_tex(tex: Texture) -> None:
                self._screens.bottom_title_view.title_image_fit_mode = _title_info.fit_mode
                self._screens.bottom_title_view.title_image_color = title.image_color
                self._screens.bottom_title_view.title_image_texture = tex

            self._load_texture(self._bottom_title_view_texture_loader, title_info, apply_tex)

    # ------------------------------------------------------------------
    # Index / Statistics / Search visibility
    # ------------------------------------------------------------------
    def _apply_screen_visibility(self, snapshot: ViewSnapshot) -> None:
        vis = snapshot.screen_visibility
        self._screens.main_index.is_visible = vis.main_index
        self._screens.speech_index.is_visible = vis.speech_index
        self._screens.names_index.is_visible = vis.names_index
        self._screens.locations_index.is_visible = vis.locations_index
        self._screens.statistics.is_visible = vis.statistics

    # ------------------------------------------------------------------
    # Search view
    # ------------------------------------------------------------------
    def _apply_search_view(self, search: SearchViewSnapshot) -> None:
        self._screens.search.is_visible = search.is_visible
        if not search.is_visible:
            return

        if search.mode:
            self._screens.search.set_mode(search.mode)

        if search.image_info and search.image_info.filename:
            self._screens.search.set_background_image(search.image_info)

            def apply_tex(tex: Texture) -> None:
                self._screens.search.image_texture = tex

            self._load_texture(self._search_texture_loader, search.image_info, apply_tex)

    # ------------------------------------------------------------------
    # Texture loading helper
    # ------------------------------------------------------------------
    @staticmethod
    def _load_texture(
        texture_loader: PanelTextureLoader,
        image_info: ImageInfo,
        apply_texture: Callable[[Texture], None],
    ) -> None:
        image_filename = image_info.filename

        timing = Timing()

        def on_ready(tex: Texture, err: Exception) -> None:
            if err:
                raise RuntimeError(err)
            assert tex is not None

            apply_texture(tex)

            assert image_filename is not None
            logger.debug(
                f'Time taken to load image "{image_filename.name}" was'
                f" {timing.get_elapsed_time_with_unit()}."
            )

        assert image_info.filename is not None
        texture_loader.load_texture(image_filename, on_ready)  # ty:ignore[invalid-argument-type]
