from __future__ import annotations

import random
from pathlib import Path
from typing import TYPE_CHECKING

from comic_utils.timing import Timing
from kivy.animation import Animation
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    ColorProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.floatlayout import FloatLayout
from loguru import logger

from barks_reader.panel_image_loader import PanelImageLoader
from barks_reader.random_title_images import FIT_MODE_COVER
from barks_reader.reader_formatter import LONG_TITLE_SPLITS, ReaderFormatter
from barks_reader.reader_utils import title_needs_footnote

if TYPE_CHECKING:
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from kivy.core.image import Texture

    from barks_reader.font_manager import FontManager
    from barks_reader.reader_consts_and_types import PanelPath
    from barks_reader.reader_settings import ReaderSettings
    from barks_reader.special_overrides_handler import SpecialFantaOverrides

BOTTOM_TITLE_VIEW_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

TITLE_PORTAL_OPENING_ANIMATION_MAX_DURATION_SECS = 4


class BottomTitleViewScreen(FloatLayout):
    """Screen for displaying title information.

    NOTE: This is a parent container (FloatLayout).
          Any other widgets (e.g., layouts) that are added to this will be on top of it.
    """

    DEBUG_BACKGROUND_OPACITY = 0

    is_first_use_of_reader = BooleanProperty(defaultvalue=False)

    MAIN_TITLE_BACKGROUND_COLOR = (0.01, 0.01, 0.01, 0.075)
    MAIN_TITLE_COLOR = (1, 1, 0, 1)
    MAIN_TITLE_FOOTNOTE_COLOR = (1, 1, 0, 1)
    main_title_text = StringProperty()
    main_title_footnote = StringProperty()

    TITLE_INFO_LABEL_COLOR = (1.0, 0.99, 0.9, 1.0)
    TITLE_EXTRA_INFO_LABEL_COLOR = (1.0, 1.0, 1.0, 1.0)
    MAX_TITLE_INFO_LEN_BEFORE_SHORTEN = 36
    title_info_text = StringProperty()
    title_extra_info_text = StringProperty()
    title_inset_image_texture = ObjectProperty()

    is_visible = BooleanProperty(defaultvalue=False)
    title_image_texture = ObjectProperty(allownone=True)
    title_image_fit_mode = StringProperty(FIT_MODE_COVER)
    title_image_color = ColorProperty()

    goto_page_num = StringProperty()
    goto_page_active = BooleanProperty(default=False)
    use_overrides_active = BooleanProperty(default=True)
    use_overrides_description = StringProperty()

    def __init__(
        self, reader_settings: ReaderSettings, font_manager: FontManager, **kwargs: str
    ) -> None:
        super().__init__(**kwargs)
        self._reader_settings = reader_settings
        self._formatter = ReaderFormatter(font_manager)
        self._special_fanta_overrides: SpecialFantaOverrides | None = None
        self._fanta_info: FantaComicBookInfo | None = None
        self.is_first_use_of_reader = self._reader_settings.is_first_use_of_reader
        self.on_title_portal_image_pressed_func = None

        self.ids.use_overrides_checkbox.bind(active=self._on_use_overrides_checkbox_changed)

    def set_special_fanta_overrides(self, special_fanta_overrides: SpecialFantaOverrides) -> None:
        self._special_fanta_overrides = special_fanta_overrides

    def set_title_view(self, fanta_info: FantaComicBookInfo) -> None:
        self._fanta_info = fanta_info

        title_text = self._get_main_title_str(fanta_info)
        add_footnote = title_needs_footnote(self._fanta_info)
        self.main_title_text = self._formatter.get_main_title(title_text, add_footnote)
        self.title_info_text = self._formatter.get_title_info(
            fanta_info, self.MAX_TITLE_INFO_LEN_BEFORE_SHORTEN, add_footnote
        )
        self.main_title_footnote = "" if not add_footnote else self._get_footnote_text()
        self.title_extra_info_text = self._formatter.get_title_extra_info(fanta_info)

        inset_image_source = self._reader_settings.file_paths.get_comic_inset_file(
            fanta_info.comic_book_info.title,
            use_only_edited_if_possible=True,
        )
        logger.debug(f'Using title image source "{inset_image_source}".')

        self._set_title_inset_image(inset_image_source)

    def _get_footnote_text(self) -> str:
        return (
            f"[*] Rejected by Western but intended for {self._fanta_info.get_short_issue_title()}"
        )

    # noinspection PyNoneFunctionAssignment
    def _on_use_overrides_checkbox_changed(self, _instance: object, use_overrides: bool) -> None:
        logger.debug(f"Use overrides checkbox changed: use_overrides = {use_overrides}.")

        if not self._fanta_info:
            return

        inset_image_source = self._special_fanta_overrides.get_title_page_inset_file(
            self._fanta_info.comic_book_info.title,
            use_overrides,
        )
        logger.debug(f"Use overrides changed: inset source = '{inset_image_source}'.")

        self._set_title_inset_image(inset_image_source)

    def fade_in_bottom_view_title(self) -> None:
        self.ids.bottom_view_box.opacity = 0
        anim = Animation(
            opacity=1, duration=self._get_title_portal_opening_animation_duration_secs()
        )
        anim.start(self.ids.bottom_view_box)
        self.ids.title_show_button.opacity = 1

    @staticmethod
    def _get_title_portal_opening_animation_duration_secs() -> int:
        return random.randrange(0, TITLE_PORTAL_OPENING_ANIMATION_MAX_DURATION_SECS + 1)

    def set_goto_page_state(self, page_to_goto: str = "", active: bool = False) -> None:
        self.goto_page_num = page_to_goto
        self.goto_page_active = active

    def set_overrides_state(self, description: str = "", active: bool = True) -> None:
        self.use_overrides_active = active
        self.use_overrides_description = description

    def on_title_portal_image_pressed(self) -> None:
        assert self.on_title_portal_image_pressed_func is not None
        self.on_title_portal_image_pressed_func()

    def _set_title_inset_image(self, inset_image_source: PanelPath) -> None:
        timing = Timing()

        def on_ready(tex: Texture | None, err: Exception) -> None:
            if err:
                raise RuntimeError(err)

            self.title_inset_image_texture = tex
            logger.debug(
                f"Time taken to set title inset image: {timing.get_elapsed_time_with_unit()}."
            )

        image_loader = PanelImageLoader()
        image_loader.load_texture(inset_image_source, on_ready)  # ty: ignore[invalid-argument-type]

    @staticmethod
    def _get_main_title_str(fanta_info: FantaComicBookInfo) -> str:
        if fanta_info.comic_book_info.is_barks_title:
            if fanta_info.comic_book_info.title in LONG_TITLE_SPLITS:
                return LONG_TITLE_SPLITS[fanta_info.comic_book_info.title]
            return fanta_info.comic_book_info.get_title_str()

        return fanta_info.comic_book_info.get_title_from_issue_name()
