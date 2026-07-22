from __future__ import annotations

import random
from pathlib import Path
from typing import TYPE_CHECKING

from barks_fantagraphics.comic_book_info import ONE_PAGERS, get_one_pager_display_title
from comic_utils.timing import Timing
from kivy.animation import Animation
from kivy.graphics.texture import Texture  # ty: ignore[unresolved-import]
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    ColorProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.floatlayout import FloatLayout
from loguru import logger

from barks_reader.core.image_selector import FIT_MODE_COVER
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE
from barks_reader.core.reader_formatter import LONG_TITLE_SPLITS, ReaderFormatter
from barks_reader.core.reader_utils import title_needs_footnote
from barks_reader.core.wiki_integration import wiki_page_for_title

# HyphenatingLabel must be imported (Factory-registered) before this screen's kv
# rule instantiates the ExtraInfoLabel dynamic class.
from .hyphen_label import HyphenatingLabel  # noqa: F401
from .panel_texture_loader import PanelTextureLoader
from .reader_keyboard_nav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_NUMPAD_ENTER,
    KEY_UP,
    clear_focus_in_list,
    is_escape_key,
    update_focus_in_list,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from comic_utils.comic_consts import PanelPath
    from kivy.uix.widget import Widget

    from barks_reader.core.reader_settings import ReaderSettings
    from barks_reader.core.special_overrides_handler import SpecialFantaOverrides

    from .font_manager import FontManager

BOTTOM_TITLE_VIEW_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

TITLE_PORTAL_OPENING_ANIMATION_MAX_DURATION_SECS = 4

_NAV_FOCUS_GROUP = "title_view_nav_focus"
# Matches the `bottom_view_box.opacity > 0.9` threshold the kv rules use for the peek toggle.
_PANEL_VISIBLE_OPACITY = 0.9


def _make_title_banner_texture(
    color: tuple[float, float, float], peak_alpha: float, height: int = 128
) -> Texture:
    """Build a 1px-wide vertical-fade texture for the main-title banner.

    The alpha is solid through the middle and fades to fully transparent at the top and
    bottom edges, giving a soft "lower-third" band when the 1px-wide texture is stretched
    across the full title row.

    Args:
        color: The banner RGB colour, each channel in 0.0..1.0.
        peak_alpha: The maximum (mid-band) opacity, 0.0..1.0.
        height: The texture height in texels (the gradient's vertical resolution).

    Returns:
        An RGBA Kivy texture suitable for a full-width ``Rectangle``.

    """
    red, green, blue = round(color[0] * 255), round(color[1] * 255), round(color[2] * 255)
    half = (height - 1) / 2
    plateau = 0.6  # fraction of the half-height kept fully opaque before fading to the edges
    buffer = bytearray()
    for row in range(height):
        dist = abs(row - half) / half
        fade = 1.0 if dist <= plateau else 1.0 - (dist - plateau) / (1.0 - plateau)
        buffer.extend((red, green, blue, round(peak_alpha * fade * 255)))

    texture = Texture.create(size=(1, height), colorfmt="rgba")
    texture.blit_buffer(bytes(buffer), colorfmt="rgba", bufferfmt="ubyte")
    texture.wrap = "clamp_to_edge"
    return texture


class BottomTitleViewScreen(FloatLayout):
    """Screen for displaying title information.

    NOTE: This is a parent container (FloatLayout).
          Any other widgets (e.g., layouts) that are added to this will be on top of it.
    """

    DEBUG_BACKGROUND_OPACITY = 0

    is_first_use_of_reader = BooleanProperty(defaultvalue=False)

    # Dark text outline so the title/footnote stay legible over the busy mosaic background.
    MAIN_TITLE_OUTLINE_COLOR = (0, 0, 0, 1)
    # Soft "lower-third" gradient banner behind the main title (replaces the old flat box):
    # solid-dark through the middle, fading to transparent at the top and bottom edges.
    MAIN_TITLE_BANNER_COLOR = (0.0, 0.0, 0.0)
    MAIN_TITLE_BANNER_PEAK_ALPHA = 0.55
    # One-pagers sit over the busy collage and keep the full banner; other titles get a
    # lighter banner (the baked texture alpha scaled by this factor).
    MAIN_TITLE_BANNER_DIM_FACTOR = 0.3
    main_title_banner_texture = ObjectProperty(allownone=True)
    main_title_text = StringProperty()
    main_title_footnote = StringProperty()

    TITLE_INFO_LABEL_COLOR = (1.0, 0.99, 0.9, 1.0)
    TITLE_EXTRA_INFO_LABEL_COLOR = (1.0, 1.0, 1.0, 1.0)
    # Dark text outline for the left-column info text, for the same reason.
    TITLE_INFO_OUTLINE_COLOR = (0, 0, 0, 1)
    # Background scrim behind the main info label. One-pagers use a darker scrim because their
    # info sits over the busy "All One-Pagers" collage rather than a calmer title page.
    TITLE_INFO_BACKGROUND_COLOR = (0.01, 0.01, 0.01, 0.1)
    TITLE_INFO_ONE_PAGER_BACKGROUND_COLOR = (0.01, 0.01, 0.01, 0.5)
    MAX_TITLE_INFO_LEN_BEFORE_SHORTEN = 36
    is_one_pager_title = BooleanProperty(defaultvalue=False)
    title_info_text = StringProperty()
    title_extra_info_text = StringProperty()
    title_inset_image_texture = ObjectProperty()

    is_visible = BooleanProperty(defaultvalue=False)
    title_image_texture = ObjectProperty(allownone=True)
    title_image_fit_mode = StringProperty(FIT_MODE_COVER)
    title_image_color = ColorProperty()

    wiki_button_visible = BooleanProperty(defaultvalue=False)

    goto_page_num = StringProperty()
    goto_page_active = BooleanProperty(default=False)
    use_overrides_active = BooleanProperty(default=True)
    use_overrides_description = StringProperty()

    def __init__(
        self, reader_settings: ReaderSettings, font_manager: FontManager, **kwargs: str
    ) -> None:
        super().__init__(**kwargs)
        self._reader_settings = reader_settings
        self._texture_loader = PanelTextureLoader()
        self._formatter = ReaderFormatter(font_manager)
        self._special_fanta_overrides: SpecialFantaOverrides | None = None
        self._fanta_info: FantaComicBookInfo | None = None
        self.is_first_use_of_reader = self._reader_settings.is_first_use_of_reader
        self.on_title_portal_image_pressed_func = None
        self.on_wiki_page_button_pressed_func: Callable[[], None] | None = None
        self._nav_active = False
        self._nav_on_exit_request: Callable[[], None] | None = None
        self._nav_focused_widget: Widget | None = None
        self.main_title_banner_texture = _make_title_banner_texture(
            self.MAIN_TITLE_BANNER_COLOR, self.MAIN_TITLE_BANNER_PEAK_ALPHA
        )

        self.ids.use_overrides_checkbox.bind(active=self._on_use_overrides_checkbox_changed)

    def set_special_fanta_overrides(self, special_fanta_overrides: SpecialFantaOverrides) -> None:
        self._special_fanta_overrides = special_fanta_overrides

    def set_title_view(self, fanta_info: FantaComicBookInfo) -> None:
        self._fanta_info = fanta_info
        self.is_one_pager_title = fanta_info.comic_book_info.title in ONE_PAGERS

        title_text = self._get_main_title_str(fanta_info)
        add_footnote = title_needs_footnote(fanta_info)
        self.main_title_text = self._formatter.get_main_title(title_text, add_footnote)
        self.title_info_text = self._formatter.get_title_info(
            fanta_info, self.MAX_TITLE_INFO_LEN_BEFORE_SHORTEN, add_footnote
        )
        self.main_title_footnote = "" if not add_footnote else self._get_footnote_text()
        self.title_extra_info_text = self._formatter.get_title_extra_info(fanta_info)
        self.wiki_button_visible = self._title_has_wiki_page(fanta_info.comic_book_info.title)

        inset_image_source = self._reader_settings.file_paths.get_comic_inset_file(
            fanta_info.comic_book_info.title,
            use_only_edited_if_possible=True,
        )
        logger.debug(f'Using title image source "{inset_image_source}".')

        self._set_title_inset_image(inset_image_source)

    def _get_footnote_text(self) -> str:
        assert self._fanta_info is not None
        return (
            f"[*] Rejected by Western but intended for {self._fanta_info.get_short_issue_title()}"
        )

    def _on_use_overrides_checkbox_changed(self, _instance: object, use_overrides: bool) -> None:
        logger.debug(f"Use overrides checkbox changed: use_overrides = {use_overrides}.")

        if not self._fanta_info:
            return

        assert self._special_fanta_overrides is not None
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
        self.goto_page_num = "" if page_to_goto == COMIC_BEGIN_PAGE else page_to_goto
        self.goto_page_active = active

    def set_overrides_state(self, description: str = "", active: bool = True) -> None:
        self.use_overrides_active = active
        self.use_overrides_description = description

    def on_title_portal_image_pressed(self) -> None:
        assert self.on_title_portal_image_pressed_func is not None
        self.on_title_portal_image_pressed_func()

    def on_wiki_page_button_pressed(self) -> None:
        assert self.on_wiki_page_button_pressed_func is not None
        self.on_wiki_page_button_pressed_func()

    # --- Keyboard navigation ---

    @property
    def is_nav_active(self) -> bool:
        """True while keyboard navigation focus is on this screen."""
        return self._nav_active

    def enter_nav_focus(self, on_exit_request: Callable[[], None]) -> None:
        """Enter keyboard navigation mode, focusing the title portal image.

        Args:
            on_exit_request: Called when the user asks to leave nav focus (Escape).

        """
        self._nav_on_exit_request = on_exit_request
        self._nav_active = True
        self._nav_focused_widget = (
            self.ids.title_portal_image_button
            if self._is_panel_content_visible()
            else self.ids.title_show_button
        )
        self._update_nav_focus()
        logger.debug("BottomTitleViewScreen: entered nav focus.")

    def exit_nav_focus(self) -> None:
        """Exit keyboard navigation mode and clear every highlight."""
        if not self._nav_active:
            return
        self._nav_active = False
        self._nav_on_exit_request = None
        self._nav_focused_widget = None
        self._clear_nav_focus()
        logger.debug("BottomTitleViewScreen: exited nav focus.")

    def handle_key(self, key: int) -> bool:
        """Handle a keyboard key. Return True if consumed."""
        if not self._nav_active:
            return False
        if key == KEY_UP:
            self._move_nav_focus(-1)
        elif key == KEY_DOWN:
            self._move_nav_focus(1)
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._activate_focused_widget()
        elif is_escape_key(key):
            self._request_nav_exit()
        else:
            return False
        return True

    def _all_nav_widgets(self) -> list[Widget]:
        """Return every nav-focusable widget, in visual top-to-bottom order."""
        ids = self.ids
        return [
            ids.title_show_button,
            ids.wiki_page_button,
            ids.use_overrides_layout,
            ids.goto_page_layout,
            ids.title_portal_image_button,
        ]

    def _focusable_widgets(self) -> list[Widget]:
        """Return the currently visible nav widgets, in visual top-to-bottom order."""
        ids = self.ids
        widgets: list[Widget] = [ids.title_show_button]
        if not self._is_panel_content_visible():
            # The panel is peeked away: only the eye toggle is visible.
            return widgets
        if self.wiki_button_visible:
            widgets.append(ids.wiki_page_button)
        if self.use_overrides_description:
            widgets.append(ids.use_overrides_layout)
        if self.goto_page_num:
            widgets.append(ids.goto_page_layout)
        widgets.append(ids.title_portal_image_button)
        return widgets

    def _is_panel_content_visible(self) -> bool:
        return self.ids.bottom_view_box.opacity > _PANEL_VISIBLE_OPACITY

    def _move_nav_focus(self, delta: int) -> None:
        focusable = self._focusable_widgets()
        if self._nav_focused_widget not in focusable:
            # E.g. the panel was mouse-peeked away under the focus: fall back to the eye.
            self._nav_focused_widget = focusable[0]
        else:
            idx = (focusable.index(self._nav_focused_widget) + delta) % len(focusable)
            self._nav_focused_widget = focusable[idx]
        self._update_nav_focus()

    def _activate_focused_widget(self) -> None:
        widget = self._nav_focused_widget
        ids = self.ids
        if widget is ids.title_portal_image_button:
            self.on_title_portal_image_pressed()
        elif widget is ids.goto_page_layout:
            ids.goto_page_checkbox.active = not ids.goto_page_checkbox.active
        elif widget is ids.use_overrides_layout:
            ids.use_overrides_checkbox.active = not ids.use_overrides_checkbox.active
        elif widget is ids.wiki_page_button:
            ids.wiki_page_button.trigger_action()
        elif widget is ids.title_show_button:
            # The kv on_press toggles the panel peek synchronously; focus stays on the eye,
            # the only focusable widget while the panel is peeked away.
            ids.title_show_button.trigger_action()
            self._update_nav_focus()

    def _update_nav_focus(self) -> None:
        # Highlight against the full list so stale rings on newly hidden widgets are cleared.
        widgets = self._all_nav_widgets()
        assert self._nav_focused_widget is not None
        update_focus_in_list(widgets, widgets.index(self._nav_focused_widget), _NAV_FOCUS_GROUP)

    def _clear_nav_focus(self) -> None:
        clear_focus_in_list(self._all_nav_widgets(), _NAV_FOCUS_GROUP)

    def _request_nav_exit(self) -> None:
        if self._nav_on_exit_request is not None:
            self._nav_on_exit_request()

    def _title_has_wiki_page(self, title: Titles) -> bool:
        bundle = self._reader_settings.wiki_bundle_dir
        return bundle is not None and wiki_page_for_title(bundle, title) is not None

    def _set_title_inset_image(self, inset_image_source: PanelPath) -> None:
        timing = Timing()

        def on_ready(tex: Texture | None, err: Exception) -> None:
            if err:
                raise RuntimeError(err)

            self.title_inset_image_texture = tex
            logger.debug(
                f"Time taken to set title inset image: {timing.get_elapsed_time_with_unit()}."
            )

        self._texture_loader.load_texture(inset_image_source, on_ready)

    @staticmethod
    def _get_main_title_str(fanta_info: FantaComicBookInfo) -> str:
        comic_book_info = fanta_info.comic_book_info

        # One-pagers always show their issue plus the page within that issue
        # (rather than the gag's own title), since they are read as a page of the
        # "All One-Pagers" collection rather than as a standalone comic.
        if comic_book_info.title in ONE_PAGERS:
            return get_one_pager_display_title(comic_book_info.title)

        if comic_book_info.is_barks_title:
            if comic_book_info.title in LONG_TITLE_SPLITS:
                return LONG_TITLE_SPLITS[comic_book_info.title]
            return comic_book_info.get_title_str()

        return comic_book_info.get_title_from_issue_name()
