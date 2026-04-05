from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from loguru import logger

from barks_reader.core.reader_formatter import get_clean_text_without_extra
from barks_reader.ui.background_views import ImageThemes

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_tags import TagGroups, Tags
    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from comic_utils.comic_consts import PanelPath

    from barks_reader.core.image_selector import ImageInfo
    from barks_reader.core.reader_settings import ReaderSettings
    from barks_reader.ui.background_views import BackgroundViews
    from barks_reader.ui.screen_bundle import ScreenBundle
    from barks_reader.ui.snapshot_applicator import SnapshotApplicator
    from barks_reader.ui.view_states import ViewStates


class ImageThemesToUse(Enum):
    ALL = auto()
    CUSTOM = auto()


class ImageThemesChange(Enum):
    ADD = auto()
    DISCARD = auto()


class ViewStateManager:
    """Manage the visual state of the main screen's views."""

    def __init__(
        self,
        reader_settings: ReaderSettings,
        background_views: BackgroundViews,
        screens: ScreenBundle,
        applicator: SnapshotApplicator,
        on_view_state_changed_func: Callable[[ViewStates], None],
    ) -> None:
        self._reader_settings = reader_settings
        self._background_views = background_views
        self._applicator = applicator

        self._bottom_title_view_screen = screens.bottom_title_view
        self._fun_image_view_screen = screens.fun_image_view
        self._search_screen = screens.search

        self._fun_image_view_screen.set_load_image_func(self._load_new_fun_view_image)

        self._on_view_state_changed = on_view_state_changed_func

        self._bottom_view_fun_image_themes: set[ImageThemes] | None = None
        self._bottom_view_fun_custom_image_themes: set[ImageThemes] = set(ImageThemes)

        # Set initial visibilities
        screens.bottom_title_view.is_visible = False
        screens.fun_image_view.is_visible = False
        screens.main_index.is_visible = False
        screens.speech_index.is_visible = False
        screens.names_index.is_visible = False
        screens.locations_index.is_visible = False
        screens.statistics.is_visible = False
        screens.search.is_visible = False

    def get_top_view_image_info(self) -> ImageInfo:
        """Return the last-applied top view image info."""
        return self._applicator.get_prev_top_view_image_info()

    def get_bottom_view_fun_image_info(self) -> ImageInfo:
        """Return the last-applied fun view image info."""
        return self._applicator.get_prev_fun_view_image_info()

    def bottom_view_fun_image_themes_changed(self, themes_to_use: ImageThemesToUse) -> None:
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
        if alteration == ImageThemesChange.ADD:
            self._bottom_view_fun_custom_image_themes.add(image_theme)
        else:
            self._bottom_view_fun_custom_image_themes.discard(image_theme)

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
        """Set the current context and update all views accordingly.

        If ``preserve_top_view`` is True the top background image is kept as-is
        (used when auto-selecting the only child of a tag node on expand).
        """
        self._background_views.set_current_category(category)
        self._background_views.set_current_year_range(get_clean_text_without_extra(year_range))
        self._background_views.set_current_cs_year_range(
            get_clean_text_without_extra(cs_year_range),
        )
        self._background_views.set_current_us_year_range(
            get_clean_text_without_extra(us_year_range),
        )
        self._background_views.set_current_tag_group(tag_group)
        self._background_views.set_current_tag(tag)
        self._background_views.set_current_bottom_view_title(title_str)

        self._background_views.set_fun_image_themes(self._bottom_view_fun_image_themes)
        self._background_views.set_view_state(view_state, preserve_top_view=preserve_top_view)

        snapshot = self._background_views.compute_snapshot()
        self._applicator.apply(snapshot)

        # Reset the title image file now that we've used it.
        self._background_views.set_bottom_view_title_image_file(None)

        self._on_view_state_changed(view_state)

    def update_search_background(self, title: Titles) -> None:
        self._background_views.set_search_screen_image_for_title(title)
        search_image_info = self._background_views.get_search_screen_image_info()
        if search_image_info.filename:
            self._search_screen.set_background_image(search_image_info)
            self._applicator.load_search_texture(
                search_image_info,
                lambda tex: setattr(self._search_screen, "image_texture", tex),
            )

    def change_background_views(self) -> None:
        logger.debug("Changing background views.")
        logger.debug(f'Current title: "{self._background_views.get_current_bottom_view_title()}".')

        if self._fun_image_view_screen.is_visible:
            self._background_views.reset_bottom_view_fun_image_info()

        self.set_view_state(
            self._background_views.get_view_state(),
            self._background_views.get_current_category(),
            self._background_views.get_current_year_range(),
            self._background_views.get_current_cs_year_range(),
            self._background_views.get_current_us_year_range(),
            self._background_views.get_current_tag_group(),
            self._background_views.get_current_tag(),
            self._background_views.get_current_bottom_view_title(),
        )

    def update_view_for_node_with_title(
        self, view_state: ViewStates, *, preserve_top_view: bool = False
    ) -> None:
        self.update_view_for_node(
            view_state,
            title_str=self._background_views.get_current_bottom_view_title(),
            preserve_top_view=preserve_top_view,
        )

    def update_view_for_node(
        self,
        view_state: ViewStates,
        *,
        preserve_top_view: bool = False,
        **args: str | TagGroups | Tags | None,
    ) -> None:
        logger.debug(f'Updating background views for node "{view_state}".')
        # TODO: Not sure how to deal with 'ty' and **args.
        self.set_view_state(view_state, preserve_top_view=preserve_top_view, **args)  # ty: ignore[invalid-argument-type]

    def set_title(
        self, fanta_info: FantaComicBookInfo, title_image_file: PanelPath | None = None
    ) -> None:
        """Public method to set the title view with new information."""
        self._bottom_title_view_screen.fade_in_bottom_view_title()

        logger.debug(
            f'Setting title to "{fanta_info.comic_book_info.get_title_str()}".'
            f' Title image file is "{title_image_file}".'
        )

        title_str = fanta_info.comic_book_info.get_title_str()
        self._background_views.set_current_bottom_view_title(title_str)

        if title_image_file:
            assert self._background_views.get_current_bottom_view_title() != ""
            title_image_file = self._reader_settings.file_paths.get_edited_version_if_possible(
                title_image_file
            )[0]

        self._background_views.set_bottom_view_title_image_file(title_image_file)
        self._background_views.set_next_bottom_view_title_image()

        self._bottom_title_view_screen.set_title_view(fanta_info)

    def _load_new_fun_view_image(self, image_info: ImageInfo) -> None:
        self._applicator.load_new_fun_view_image(image_info)
        self._background_views.set_bottom_view_fun_image(image_info)
