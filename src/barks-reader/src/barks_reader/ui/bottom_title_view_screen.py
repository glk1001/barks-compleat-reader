from __future__ import annotations

import random
from math import ceil
from pathlib import Path
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_covers import COVER_BY_TITLE, get_cover_display_title
from barks_fantagraphics.comic_book_info import (
    COVERS_SET,
    ONE_PAGERS,
    get_one_pager_display_title,
)
from comic_utils.timing import Timing
from kivy.animation import Animation
from kivy.graphics.texture import Texture  # ty: ignore[unresolved-import]
from kivy.properties import (  # ty: ignore[unresolved-import]
    AliasProperty,
    BooleanProperty,
    ColorProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.floatlayout import FloatLayout
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.goto_page import GotoPageOffer
from barks_reader.core.image_selector import FIT_MODE_COVER
from barks_reader.core.keys import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    KEY_UP,
    is_escape_key,
)
from barks_reader.core.main_layout import MainLayoutMode
from barks_reader.core.reader_formatter import (
    LONG_TITLE_SPLITS,
    ReaderFormatter,
    get_comic_display_title,
)
from barks_reader.core.reader_utils import (
    title_needs_footnote,
)
from barks_reader.core.wiki_integration import wiki_page_for_title

# HyphenatingLabel must be imported (Factory-registered) before this screen's kv
# rule instantiates the ExtraInfoLabel dynamic class.
from .hyphen_label import HyphenatingLabel  # noqa: F401
from .panel_texture_loader import PanelTextureLoader
from .reader_keyboard_nav import clear_focus_in_list, update_focus_in_list

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

# A short random fade: at up to 4s a clicked title took its time to arrive.
TITLE_PORTAL_OPENING_ANIMATION_MAX_DURATION_SECS = 1

_NAV_FOCUS_GROUP = "title_view_nav_focus"
# Above this the panel counts as shown, for the peek toggle's eye and for keyboard nav.
PANEL_VISIBLE_OPACITY = 0.9


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
    # The main title's top below its band's top, in dp: on a single page and on the
    # two-page spread (the bands are 18% and 12% of the view). A long title that wraps
    # rises from there as far as its lines need to stay in the band.
    MAIN_TITLE_TOP_OFFSET_SINGLE = 28
    MAIN_TITLE_TOP_OFFSET_SPREAD = 50
    main_title_banner_texture = ObjectProperty(allownone=True)
    main_title_text = StringProperty()
    main_title_footnote = StringProperty()

    TITLE_INFO_LABEL_COLOR = (1.0, 0.99, 0.9, 1.0)
    # The share of a label's font size between its texture's top and its glyphs' tops
    # (the font's ascent over its cap height): what lines the portal up with the text.
    TEXT_LEADING = 0.25
    # The same for the notes' font, whose ascent stands further above its capitals.
    EXTRA_INFO_TEXT_LEADING = 0.366
    # The notes' font's line height, as a share of its size: its ascent plus its descent.
    EXTRA_INFO_LINE_HEIGHT = 1.371
    TITLE_EXTRA_INFO_LABEL_COLOR = TITLE_INFO_LABEL_COLOR
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
    # The height left for the notes in the info box, under its info rows: what ends the
    # notes at a whole line and what places them must agree, so the kv rule writes it once.
    space_under_title_info = NumericProperty(0)
    title_inset_image_texture = ObjectProperty(allownone=True)

    is_visible = BooleanProperty(defaultvalue=False)
    title_image_texture = ObjectProperty(allownone=True)
    title_image_fit_mode = StringProperty(FIT_MODE_COVER)
    # The book's layout (core.main_layout): the view is the right page on the spread.
    layout_mode = StringProperty(MainLayoutMode.SINGLE.value)
    title_image_color = ColorProperty()

    def _get_compact_colophon(self) -> bool:
        return self.layout_mode == MainLayoutMode.SPREAD.value and not self.title_extra_info_text

    # On the spread a title without notes packs its colophon (the info rows beside the
    # portal column) into a short foot and the picture takes the rest of the page: with
    # the colophon at half the page, the notes' empty room made the page look unfinished.
    compact_colophon = AliasProperty(
        _get_compact_colophon, None, bind=("layout_mode", "title_extra_info_text"), cache=True
    )

    wiki_button_visible = BooleanProperty(defaultvalue=False)

    goto_page_num = StringProperty()
    goto_page_active = BooleanProperty(defaultvalue=False)
    # A tag's pages in this title: every one (handed on to the comic), and the start of
    # each run of them, which the goto-page row steps through.
    tagged_pages = ListProperty()
    goto_pages = ListProperty()

    def _get_can_step_goto_page(self) -> bool:
        return len(self.goto_pages) > 1

    # Whether the goto-page row has more than one page to step through.
    can_step_goto_page = AliasProperty(_get_can_step_goto_page, None, bind=("goto_pages",))

    # The row's label: "Goto page 7 (1 of 3):", or "Goto pages 16-23 (3 of 3):" for a
    # run, so a run shows as one.
    goto_page_text = StringProperty()
    use_overrides_active = BooleanProperty(defaultvalue=True)
    use_overrides_description = StringProperty()

    @staticmethod
    def extra_info_line_pitch(font_size: float) -> int:
        """Return the pixels from one line of the notes to the next.

        Args:
            font_size: The notes' font size, in pixels.

        Returns:
            The font's line height, which Kivy rounds up to a whole pixel.

        """
        return ceil(max(font_size, 1) * BottomTitleViewScreen.EXTRA_INFO_LINE_HEIGHT)

    def __init__(
        self, reader_settings: ReaderSettings, font_manager: FontManager, **kwargs: str
    ) -> None:
        super().__init__(**kwargs)
        self._reader_settings = reader_settings
        self._texture_loader = PanelTextureLoader()
        self._formatter = ReaderFormatter(font_manager)
        font_manager.bind(title_info_font_size=self._on_title_info_font_size)
        self._special_fanta_overrides: SpecialFantaOverrides | None = None
        self._fanta_info: FantaComicBookInfo | None = None
        self._goto_offer = GotoPageOffer()
        self.is_first_use_of_reader = self._reader_settings.is_first_use_of_reader
        self.on_title_portal_image_pressed_func = None
        self.on_wiki_page_button_pressed_func: Callable[[], None] | None = None
        self._nav_active = False
        self._nav_on_exit_request: Callable[[], None] | None = None
        self._nav_focused_widget: Widget | None = None
        self._last_nav_focused_widget: Widget | None = None
        # The title fade-in currently running, or None. Held as the animation
        # itself rather than a flag so an earlier fade finishing cannot clear a
        # later one that is still going. See _is_panel_content_visible.
        self._panel_fade_anim: Animation | None = None
        self.main_title_banner_texture = _make_title_banner_texture(
            self.MAIN_TITLE_BANNER_COLOR, self.MAIN_TITLE_BANNER_PEAK_ALPHA
        )

        self.ids.use_overrides_checkbox.bind(active=self._on_use_overrides_checkbox_changed)

    def set_special_fanta_overrides(self, special_fanta_overrides: SpecialFantaOverrides) -> None:
        """Set where the view finds the overrides it offers for a title."""
        self._special_fanta_overrides = special_fanta_overrides

    def set_title_view(self, fanta_info: FantaComicBookInfo) -> None:
        """Show *fanta_info*'s title in the view."""
        # A remembered nav position belongs to the previous title's widgets.
        self._last_nav_focused_widget = None
        self._fanta_info = fanta_info
        # Covers share the one-pagers' compact title-panel styling (the .kv keys
        # off this property), since both are single pages read via a collection.
        self.is_one_pager_title = (
            fanta_info.comic_book_info.title in ONE_PAGERS
            or fanta_info.comic_book_info.title in COVERS_SET
        )

        title_text = self._get_main_title_str(fanta_info)
        add_footnote = title_needs_footnote(fanta_info)
        self.main_title_text = self._formatter.get_main_title(title_text, add_footnote)
        self._set_title_info_text(fanta_info)
        self.main_title_footnote = "" if not add_footnote else self._get_footnote_text()
        self.title_extra_info_text = self._formatter.get_title_extra_info(fanta_info)
        self.wiki_button_visible = self._title_has_wiki_page(fanta_info.comic_book_info.title)

        inset_image_source = self._reader_settings.file_paths.get_comic_inset_file(
            fanta_info.comic_book_info.title,
            use_only_edited_if_possible=True,
        )
        logger.debug(f'Using title image source "{inset_image_source}".')

        self._set_title_inset_image(inset_image_source)

    def _set_title_info_text(self, fanta_info: FantaComicBookInfo) -> None:
        self.title_info_text = self._formatter.get_title_info(
            fanta_info, self.MAX_TITLE_INFO_LEN_BEFORE_SHORTEN, title_needs_footnote(fanta_info)
        )

    def _on_title_info_font_size(self, *_args: object) -> None:
        # The footnote star's size is written into the text, and the rows' size changes
        # with the window's height: left alone, it stretched or shrank against them.
        if self._fanta_info is not None:
            self._set_title_info_text(self._fanta_info)

    def _get_footnote_text(self) -> str:
        assert self._fanta_info is not None
        return (
            f"[*] Rejected by Western but intended for {self._fanta_info.get_short_issue_title()}"
        )

    def _on_use_overrides_checkbox_changed(self, _instance: object, use_overrides: bool) -> None:
        logger.debug(log_markers.USE_OVERRIDES_CHANGED.format(value=use_overrides))
        self._show_title_inset_for_overrides(use_overrides)

    def _show_title_inset_for_overrides(self, use_overrides: bool) -> None:
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
        """Fade the panel in from nothing, over a short random time."""
        # Stepping through titles starts a fade over one still running. Left going, the old
        # one drags the opacity back down after a shorter new one has finished, and the
        # panel, with no fade on record, reads as peeked away.
        if self._panel_fade_anim is not None:
            self._panel_fade_anim.cancel(self.ids.bottom_view_box)
        self.ids.bottom_view_box.opacity = 0
        duration = self._get_title_portal_opening_animation_duration_secs()
        anim = Animation(opacity=1, duration=duration)
        anim.bind(on_complete=self._on_panel_fade_finished)
        anim.start(self.ids.bottom_view_box)
        logger.debug(log_markers.TITLE_FADE_STARTED.format(duration=f"{duration:.2f}"))
        # Recorded after start(), so this is the animation that actually ended up
        # running; the guard in _on_panel_fade_finished then knows it from any other.
        self._panel_fade_anim = anim
        self.ids.title_show_button.opacity = 1

    def _on_panel_fade_finished(self, anim: Animation, _widget: Widget) -> None:
        """Forget a finished fade, so opacity alone decides visibility again."""
        if anim is self._panel_fade_anim:
            self._panel_fade_anim = None
            # The one signal that the panel is fully drawn: nothing else is logged
            # while it animates, and the duration is random.
            logger.debug(log_markers.TITLE_FADE_FINISHED)

    @staticmethod
    def _get_title_portal_opening_animation_duration_secs() -> float:
        return random.uniform(0, TITLE_PORTAL_OPENING_ANIMATION_MAX_DURATION_SECS)

    def show_goto_page(self, offer: GotoPageOffer) -> None:
        """Show `offer` on the goto-page row: its page, ticked or not, and the pages to step."""
        self._goto_offer = offer
        self.tagged_pages = list(offer.tagged_pages)
        self.goto_page_num = offer.page
        self.goto_pages = list(offer.pages)
        self.goto_page_active = offer.active
        self.goto_page_text = offer.text
        if offer.page:
            logger.debug(
                log_markers.GOTO_PAGE_OFFERED.format(
                    page=offer.page, active=offer.active, text=self.goto_page_text
                )
            )

    def step_goto_page(self, delta: int) -> None:
        """Offer the next (or previous) of a tag's goto pages, wrapping round, and tick it.

        Args:
            delta: How many goto pages to move: 1 for the next, -1 for the previous.

        """
        if not self.can_step_goto_page:
            return
        offer = self._goto_offer.stepped(delta)
        self._goto_offer = offer
        self.goto_page_num = offer.page
        self.goto_page_active = True  # Choosing a page means wanting to go there.
        self.goto_page_text = offer.text
        assert offer.index is not None
        logger.debug(
            log_markers.GOTO_PAGE_STEPPED.format(
                page=offer.page,
                index=offer.index + 1,
                count=len(offer.pages),
                text=self.goto_page_text,
            )
        )

    def set_overrides_state(self, description: str = "", active: bool = True) -> None:
        """Set the use-overrides row for the title in view.

        Args:
            description: The row's text, empty for a title with no overrides.
            active: Whether the overrides are in use.

        """
        # The kv rule's checkbox is ticked unless there is a description and this is off.
        box_was_off = bool(self.use_overrides_description) and not self.use_overrides_active
        box_stays_off = box_was_off and bool(description) and not active

        self.use_overrides_active = active
        self.use_overrides_description = description

        # The box swaps the inset only when it changes, and set_title_view has just put the
        # standard one back: left at that, a title with its overrides off would show them.
        if box_stays_off:
            self._show_title_inset_for_overrides(use_overrides=False)

    def on_title_portal_image_pressed(self) -> None:
        """Pass a press of the title portal on to its handler."""
        assert self.on_title_portal_image_pressed_func is not None
        self.on_title_portal_image_pressed_func()

    def on_wiki_page_button_pressed(self) -> None:
        """Pass a press of the wiki page button on to its handler."""
        assert self.on_wiki_page_button_pressed_func is not None
        self.on_wiki_page_button_pressed_func()

    # --- Keyboard navigation ---

    @property
    def is_nav_active(self) -> bool:
        """True while keyboard navigation focus is on this screen."""
        return self._nav_active

    def enter_nav_focus(self, on_exit_request: Callable[[], None]) -> None:
        """Enter keyboard navigation mode.

        Focus returns to the widget that was focused when nav was last exited by a
        screen switch (e.g. coming back from the wiki reader), falling back to the
        title portal image.

        Args:
            on_exit_request: Called when the user asks to leave nav focus (Escape).

        """
        self._nav_on_exit_request = on_exit_request
        self._nav_active = True
        default = (
            self.ids.title_portal_image_button
            if self._is_panel_content_visible()
            else self.ids.title_show_button
        )
        remembered = self._last_nav_focused_widget
        if remembered not in self._focusable_widgets():
            remembered = None
        self._nav_focused_widget = remembered or default
        self._update_nav_focus()
        logger.debug(log_markers.TITLE_VIEW_ENTERED_NAV)

    def enter_nav_focus_at_portal(self, on_exit_request: Callable[[], None]) -> None:
        """Enter keyboard navigation focus landing directly on the title portal image.

        Pressing Enter on a title node is a deliberate "read this title" gesture, so
        focus always lands on the portal (the read action) — ignoring any remembered
        position. The portal is targeted directly rather than via `enter_nav_focus`'s
        opacity-based default: the title render that precedes this call restarts the
        panel's fade-in from zero opacity, so `_is_panel_content_visible()` reads False
        for the (randomly timed) duration of the fade and would send focus to the eye
        toggle by mistake. The ring fades in with the content.

        Args:
            on_exit_request: Called when the user asks to leave nav focus (Escape).

        """
        self._nav_on_exit_request = on_exit_request
        self._nav_active = True
        self._last_nav_focused_widget = None
        self._nav_focused_widget = self.ids.title_portal_image_button
        self._update_nav_focus()
        logger.debug(log_markers.TITLE_VIEW_ENTERED_AT_PORTAL)

    def exit_nav_focus(self) -> None:
        """Exit keyboard navigation mode and clear every highlight."""
        if not self._nav_active:
            return
        self._last_nav_focused_widget = self._nav_focused_widget
        self._nav_active = False
        self._nav_on_exit_request = None
        self._nav_focused_widget = None
        self._clear_nav_focus()
        logger.debug(log_markers.TITLE_VIEW_EXITED_NAV)

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
        elif (
            key in (KEY_LEFT, KEY_RIGHT)
            and self._nav_focused_widget is self.ids.goto_page_layout
            and self.can_step_goto_page
        ):
            self.step_goto_page(-1 if key == KEY_LEFT else 1)
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
        """Return whether the panel content counts as on screen, for keyboard nav.

        Opacity is the panel's only state: the eye toggle peeks the content away by
        setting ``bottom_view_box.opacity`` to 0 (in the kv rule), and the title
        fade-in animates that same property up from 0 over a short random time. Opacity
        alone therefore cannot tell "the user hid this" from "this is still arriving",
        and mid-fade it reads as hidden - which left only the eye toggle focusable, so
        an Enter after a *mouse*-driven goto-title toggled the panel instead of opening
        the comic. (A keyboard goto-title is unaffected: it routes through
        ``enter_nav_focus_at_portal``, which targets the portal outright.)

        A fade in progress counts as visible: the content is on its way in, and the
        focus ring fades in with it.
        """
        if self._panel_fade_anim is not None:
            return True
        return self.ids.bottom_view_box.opacity > PANEL_VISIBLE_OPACITY

    def _focus_eye_if_focus_is_gone(self, focusable: list[Widget]) -> bool:
        """Move the focus to the eye if its widget has gone, and return whether it had.

        E.g. the panel was mouse-peeked away under the focus.
        """
        if self._nav_focused_widget in focusable:
            return False
        self._nav_focused_widget = focusable[0]
        self._update_nav_focus()
        return True

    def _move_nav_focus(self, delta: int) -> None:
        focusable = self._focusable_widgets()
        if self._focus_eye_if_focus_is_gone(focusable):
            return
        idx = (focusable.index(self._nav_focused_widget) + delta) % len(focusable)
        self._nav_focused_widget = focusable[idx]
        self._update_nav_focus()

    def _activate_focused_widget(self) -> None:
        # Enter on a widget no longer on screen must not act on what cannot be seen.
        if self._focus_eye_if_focus_is_gone(self._focusable_widgets()):
            return
        widget = self._nav_focused_widget
        ids = self.ids
        if widget is ids.title_portal_image_button:
            self.on_title_portal_image_pressed()
        elif widget is ids.goto_page_layout:
            ids.goto_page_checkbox.active = not ids.goto_page_checkbox.active
            logger.debug(
                log_markers.GOTO_PAGE_CHECKBOX_TOGGLED.format(value=ids.goto_page_checkbox.active)
            )
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
        # A deliberate Escape forgets the position: the next entry starts at the portal.
        self._last_nav_focused_widget = None

    def _title_has_wiki_page(self, title: Titles) -> bool:
        bundle = self._reader_settings.wiki_bundle_dir
        return bundle is not None and wiki_page_for_title(bundle, title) is not None

    def _set_title_inset_image(self, inset_image_source: PanelPath) -> None:
        timing = Timing()

        def on_ready(tex: Texture | None, err: Exception | None) -> None:
            if err:
                # It costs the portal its picture, not the app: the title can still be read,
                # or say why not, and the previous title's inset must not stay up as this one's.
                logger.error(f'Could not load the title inset "{inset_image_source}": {err}')
                self.title_inset_image_texture = None
                return

            self.title_inset_image_texture = tex
            logger.debug(
                log_markers.TITLE_INSET_IMAGE_SET.format(
                    elapsed=timing.get_elapsed_time_with_unit()
                )
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

        # Covers similarly show their issue plus cover date, e.g.
        # "Uncle Scrooge #7 (Sep 1954)".
        if comic_book_info.title in COVERS_SET:
            return get_cover_display_title(COVER_BY_TITLE[comic_book_info.title])

        if comic_book_info.is_barks_title and comic_book_info.title in LONG_TITLE_SPLITS:
            return LONG_TITLE_SPLITS[comic_book_info.title]

        return get_comic_display_title(comic_book_info)
