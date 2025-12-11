from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from comic_utils.timing import Timing
from loguru import logger

from barks_reader.background_views import ImageThemes
from barks_reader.panel_image_loader import PanelImageLoader
from barks_reader.random_title_images import ImageInfo
from barks_reader.reader_consts_and_types import CLOSE_TO_ZERO
from barks_reader.reader_formatter import get_clean_text_without_extra

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_tags import TagGroups, Tags
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from comic_utils.comic_consts import PanelPath
    from kivy.core.image import Texture

    from barks_reader.background_views import BackgroundViews, ViewStates
    from barks_reader.bottom_title_view_screen import BottomTitleViewScreen
    from barks_reader.fun_image_view_screen import FunImageViewScreen
    from barks_reader.main_index_screen import MainIndexScreen
    from barks_reader.reader_settings import ReaderSettings
    from barks_reader.speech_index_screen import SpeechIndexScreen
    from barks_reader.tree_view_screen import TreeViewScreen


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
        tree_view_screen: TreeViewScreen,
        bottom_title_view_screen: BottomTitleViewScreen,
        fun_image_view_screen: FunImageViewScreen,
        main_index_screen: MainIndexScreen,
        speech_index_screen: SpeechIndexScreen,
        on_views_updated_func: Callable[[], None],
    ) -> None:
        self._reader_settings = reader_settings
        self._background_views = background_views

        self._tree_view_screen = tree_view_screen
        self._bottom_title_view_screen = bottom_title_view_screen
        self._fun_image_view_screen = fun_image_view_screen
        self._main_index_screen = main_index_screen
        self._speech_index_screen = speech_index_screen
        self._on_views_updated_func = on_views_updated_func

        self._top_view_image_loader = PanelImageLoader(
            self._reader_settings.file_paths.barks_panels_are_encrypted
        )
        self._fun_view_image_loader = PanelImageLoader(
            self._reader_settings.file_paths.barks_panels_are_encrypted
        )
        self._bottom_title_view_image_loader = PanelImageLoader(
            self._reader_settings.file_paths.barks_panels_are_encrypted
        )

        # Take ownership of the view-specific state
        self._top_view_image_info: ImageInfo = ImageInfo()
        self._bottom_view_title_image_info: ImageInfo = ImageInfo()
        self._bottom_view_fun_image_info: ImageInfo = ImageInfo()
        self._bottom_view_fun_image_themes: set[ImageThemes] | None = None
        self._bottom_view_fun_custom_image_themes: set[ImageThemes] = set(ImageThemes)

        # Set initial visibilities
        self._bottom_title_view_screen.is_visible = False
        self._fun_image_view_screen.is_visible = False
        self._main_index_screen.is_visible = False
        self._speech_index_screen.is_visible = False

    def get_top_view_image_info(self) -> ImageInfo:
        return self._top_view_image_info

    def get_bottom_view_fun_image_info(self) -> ImageInfo:
        return self._bottom_view_fun_image_info

    def bottom_view_fun_image_themes_changed(self, themes_to_use: ImageThemesToUse) -> None:
        if themes_to_use == ImageThemesToUse.ALL:
            self._bottom_view_fun_image_themes = None
        elif themes_to_use == ImageThemesToUse.CUSTOM:
            self._bottom_view_fun_image_themes = self._bottom_view_fun_custom_image_themes
        else:
            msg = f'"Unimplemented ImageThemesToUse: "{themes_to_use}"'
            raise ValueError(msg)

    def bottom_view_alter_fun_image_themes(
        self, image_theme: ImageThemes, alteration: ImageThemesChange
    ) -> None:
        if alteration == ImageThemesChange.ADD:
            self._bottom_view_fun_custom_image_themes.add(image_theme)
        else:
            self._bottom_view_fun_custom_image_themes.discard(image_theme)

    def update_background_views(
        self,
        tree_node: ViewStates,
        category: str = "",
        year_range: str = "",
        cs_year_range: str = "",
        us_year_range: str = "",
        tag_group: TagGroups | None = None,
        tag: Tags | None = None,
        title_str: str = "",
    ) -> None:
        """Set the current context and update all views accordingly."""
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

        self._background_views.set_view_state(tree_node)

        self._set_views()

    def change_background_views(self) -> None:
        logger.debug("Changing background views.")
        logger.debug(f'Current title: "{self._background_views.get_current_bottom_view_title()}".')

        self.update_background_views(
            self._background_views.get_view_state(),
            self._background_views.get_current_category(),
            self._background_views.get_current_year_range(),
            self._background_views.get_current_cs_year_range(),
            self._background_views.get_current_us_year_range(),
            self._background_views.get_current_tag_group(),
            self._background_views.get_current_tag(),
            self._background_views.get_current_bottom_view_title(),
        )

    def update_view_for_node_with_title(self, view_state: ViewStates) -> None:
        self.update_view_for_node(
            view_state,
            title_str=self._background_views.get_current_bottom_view_title(),
        )

    def update_view_for_node(
        self,
        view_state: ViewStates,
        **args: str | TagGroups | Tags | None,
    ) -> None:
        logger.debug(f'Updating background views for node "{view_state}".')
        # TODO: Not sure how to deal with 'ty' and **args.
        self.update_background_views(view_state, **args)  # ty: ignore[invalid-argument-type]

    def _set_views(self) -> None:
        """Update all the visual components of the main screen."""
        self._set_top_view_image()
        self._set_fun_view()
        self._set_bottom_view()
        self._set_index_view()

        self._fun_image_view_screen.goto_title_button_active = (
            self._fun_image_view_screen.fun_view_from_title
            and (not self._bottom_title_view_screen.is_visible)
        )

        # Reset the title image file now that we've used it. This makes sure we can get
        # a random image next time around.
        self._background_views.set_bottom_view_title_image_file(None)

        assert self._on_views_updated_func
        self._on_views_updated_func()

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
        self._background_views.set_bottom_view_title_image()

        self._bottom_title_view_screen.set_title_view(fanta_info)

    # noinspection PyNoneFunctionAssignment
    def _set_top_view_image(self) -> None:
        """Set the image and properties for the top view (behind the TreeView)."""
        self._top_view_image_info = self._background_views.get_top_view_image_info()

        logger.debug(f"Setting new top view: {self._top_view_image_info.filename}.")

        timing = Timing()

        def on_ready(tex: Texture, err: Exception) -> None:
            if err:
                raise RuntimeError(err)
            assert tex is not None

            self._tree_view_screen.top_view_image_opacity = (
                self._background_views.get_top_view_image_opacity()
            )
            self._tree_view_screen.top_view_image_fit_mode = self._top_view_image_info.fit_mode
            self._tree_view_screen.top_view_image_color = (
                self._background_views.get_top_view_image_color()
            )
            self._tree_view_screen.top_view_image_texture = tex

            assert self._top_view_image_info.filename is not None
            logger.debug(
                f"Time taken to set top image:"
                f' "{self._top_view_image_info.filename.name}",'
                f" {timing.get_elapsed_time_with_unit()}."
            )

        # noinspection LongLine
        self._top_view_image_loader.load_texture(self._top_view_image_info.filename, on_ready)  # ty: ignore[invalid-argument-type]

        assert self._top_view_image_info.from_title is not None
        self._tree_view_screen.set_title(self._top_view_image_info.from_title)

    def _set_fun_view(self) -> None:
        """Set the image and properties for the 'fun' bottom view."""
        opacity = self._background_views.get_bottom_view_fun_image_opacity()

        logger.debug(f"Setting new fun view opacity to {opacity}.")

        self._fun_image_view_screen.is_visible = opacity > (1.0 - CLOSE_TO_ZERO)

        self._bottom_view_fun_image_info = self._background_views.get_bottom_view_fun_image_info()

        if not self._bottom_view_fun_image_info.filename:
            self._fun_image_view_screen.image_texture = None
        else:
            timing = Timing()

            def on_ready(tex: Texture, err: Exception) -> None:
                if err:
                    raise RuntimeError(err)
                assert tex is not None

                self._fun_image_view_screen.image_fit_mode = (
                    self._bottom_view_fun_image_info.fit_mode
                )
                self._fun_image_view_screen.image_color = (
                    self._background_views.get_bottom_view_fun_image_color()
                )
                self._fun_image_view_screen.image_texture = tex
                logger.debug(f"Time taken to set fun image: {timing.get_elapsed_time_with_unit()}.")

            # noinspection LongLine
            self._fun_view_image_loader.load_texture(
                self._bottom_view_fun_image_info.filename,
                on_ready,  # ty: ignore[invalid-argument-type]
            )

            self._fun_image_view_screen.set_title(self._bottom_view_fun_image_info.from_title)

    def _set_bottom_view(self) -> None:
        """Set the image and properties for the title information bottom view."""
        opacity = self._background_views.get_bottom_view_title_opacity()

        logger.debug(f"Setting new bottom view opacity to {opacity}.")

        self._bottom_title_view_screen.is_visible = opacity > (1.0 - CLOSE_TO_ZERO)

        self._bottom_view_title_image_info = (
            self._background_views.get_bottom_view_title_image_info()
        )

        if not self._bottom_view_title_image_info.filename:
            self._bottom_title_view_screen.title_image_texture = None
        else:
            timing = Timing()

            def on_ready(tex: Texture, err: Exception) -> None:
                if err:
                    raise RuntimeError(err)
                assert tex is not None

                self._bottom_title_view_screen.title_image_fit_mode = (
                    self._bottom_view_title_image_info.fit_mode
                )
                self._bottom_title_view_screen.title_image_color = (
                    self._background_views.get_bottom_view_title_image_color()
                )
                self._bottom_title_view_screen.title_image_texture = tex
                logger.debug(
                    f"Time taken to set title image: {timing.get_elapsed_time_with_unit()}."
                )

            # noinspection LongLine
            self._bottom_title_view_image_loader.load_texture(
                self._bottom_view_title_image_info.filename,
                on_ready,  # ty: ignore[invalid-argument-type]
            )

    def _set_index_view(self) -> None:
        opacity = self._background_views.get_main_index_view_opacity()
        self._main_index_screen.is_visible = opacity > (1.0 - CLOSE_TO_ZERO)

        opacity = self._background_views.get_speech_index_view_opacity()
        self._speech_index_screen.is_visible = opacity > (1.0 - CLOSE_TO_ZERO)

        logger.debug(
            f"Setting new index view."
            f" Main index visibility: {self._main_index_screen.is_visible}."
            f" Speech index visibility: {self._speech_index_screen.is_visible}."
        )
