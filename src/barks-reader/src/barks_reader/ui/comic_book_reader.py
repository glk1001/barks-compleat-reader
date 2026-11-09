from __future__ import annotations

import io
import weakref
from pathlib import Path
from typing import TYPE_CHECKING, override

from barks_fantagraphics.barks_covers import get_cover_display_title, get_located_covers
from barks_fantagraphics.comic_book_info import (
    get_located_one_pagers,
    get_one_pager_display_title,
    is_covers_collection,
    is_one_pager_collection,
)
from barks_fantagraphics.comics_consts import PageType
from barks_kivy_ui.scrolling import ReaderDropDown
from comic_utils.timing import Timing
from kivy.clock import Clock, ClockEvent
from kivy.core.image import Image as CoreImage
from kivy.core.image import Texture
from kivy.core.window import Window, WindowBase
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    NumericProperty,
    StringProperty,
)
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.archive_page_image_source import ArchivePageImageSource
from barks_reader.core.comic_book_loader import ComicBookLoader
from barks_reader.core.comic_page_manager import ComicPageManager
from barks_reader.core.main_layout import SPREAD_WIDTH_IN_PAGES, MainLayoutMode
from barks_reader.core.page_placement import PagePlacement, fitted_page_rect, log_page_placement
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE
from barks_reader.core.reader_formatter import get_action_bar_title, get_comic_display_title
from barks_reader.core.reader_navigation import ReaderNavigation
from barks_reader.core.reader_utils import (
    COMIC_PAGE_ASPECT_RATIO,
    PNG_EXT_FOR_KIVY,
    get_win_dimensions,
)
from barks_reader.core.screen_metrics import SCREEN_METRICS

from .action_bar_helpers import (
    ACTION_BAR_SIZE_Y,
    ActionBarVisibility,
    is_action_bar_visible,
    set_action_bar_visibility,
    set_fullscreen_button,
)
from .adapters import KivyClockScheduler, KivyCursor
from .platform_window_utils import (
    WindowManager,
    WindowModeCallbacks,
    WindowModeController,
    log_window_geometry,
)
from .reader_close_mixin import ReaderCloseMixin
from .reader_keyboard_nav import ActionBarNavMixin, DropdownNavMixin, open_dropdown
from .reader_screens import ReaderScreen
from .tap_targets import Rect, window_rect
from .ui_helpers import is_tap

if TYPE_CHECKING:
    from collections import OrderedDict
    from collections.abc import Callable, Sequence

    from barks_build_comic_images.build_comic_images import ComicBookImageBuilder
    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from comic_utils.comic_consts import PanelPath
    from kivy.input import MotionEvent
    from kivy.uix.actionbar import ActionBar
    from kivy.uix.widget import Widget

    from barks_reader.core.comic_book_page_info import ComicLayout, PageInfo
    from barks_reader.core.display_unit import DisplayUnit
    from barks_reader.core.page_image import PageImage
    from barks_reader.core.reader_settings import ReaderSettings

    from .font_manager import FontManager


# How often, while a not-yet-loaded page is being awaited, the reader re-checks
# whether that page has finished loading (seconds). Small enough to feel instant,
# large enough not to burn a frame budget while the loader thread works.
PENDING_PAGE_POLL_INTERVAL_SECS = 0.05

# How long opening a comic will hold the *calling* screen up, waiting for page one to
# be drawn, before switching to the reader anyway and showing the blank loading page.
# A warm local archive reaches the first page in well under a second, so this timeout
# is the failure path - a cold volume, a slow disk, a load that errors out - and not
# the common one. Without it, a comic that never loads would never switch at all.
FIRST_PAGE_REVEAL_TIMEOUT_SECS = 2.0

GOTO_PAGE_DROPDOWN_FRAC_OF_HEIGHT = 0.97
GOTO_PAGE_BUTTON_HEIGHT = dp(25)
GOTO_PAGE_BUTTON_BODY_COLOR = (0, 1, 1, 1)
GOTO_PAGE_BUTTON_NONBODY_COLOR = (0, 0.5, 0.5, 1)
GOTO_PAGE_BUTTON_CURRENT_PAGE_COLOR = (1, 1, 0, 1)
# A page the tag the comic was opened through marks.
GOTO_PAGE_BUTTON_TAGGED_COLOR = (1, 0.55, 0, 1)

COMIC_BOOK_READER_KV_FILE = Path(__file__).with_suffix(".kv")


def _call_if_alive[T](owner: weakref.ref[T], method_name: str) -> None:
    """Call `owner`'s method `method_name`, or do nothing once `owner` is gone.

    The method is looked up by name on each call, as Kivy's own WeakMethod does (the
    stdlib's keeps the function it was made with), so a method patched on the
    instance is the one called.
    """
    obj = owner()
    if obj is not None:
        getattr(obj, method_name)()


def _get_collection_titles(title: Titles) -> list[str] | None:
    """Return the name of each page's item in a one-item-a-page collection, else None."""
    if is_one_pager_collection(title):
        return [get_one_pager_display_title(one_pager) for one_pager in get_located_one_pagers()]
    if is_covers_collection(title):
        return [get_cover_display_title(cover) for cover in get_located_covers()]
    return None


class ComicBookReader(FloatLayout):
    """Main layout for the comic reader."""

    # The window/action-bar title. A Kivy property so the screen can bind to it and
    # reflect per-page title changes (e.g. the "All One-Pagers" collection).
    action_bar_title = StringProperty()
    # Whether this comic is in double-page mode, set with the mode: the screen's bar is
    # the pair's width all through it, under a solo unit (the cover, an odd last page)
    # too, so the bar's buttons stay put as the pages turn.
    two_up = BooleanProperty(defaultvalue=False)

    def __init__(
        self,
        reader_settings: ReaderSettings,
        font_manager: FontManager,
        on_comic_is_ready_to_read: Callable[[], None],
        hide_action_bar: Callable[[], None],
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)

        self._reader_settings = reader_settings
        # Whether a comic opens two pages at a time: the main screen's layout is the
        # spread (`ComicBookReaderScreen.layout_mode`). The bar's toggle is per comic.
        self.opens_two_up = False
        self._font_manager = font_manager
        self._on_comic_is_ready_to_read = on_comic_is_ready_to_read
        self._hide_action_bar = hide_action_bar
        self._goto_page_widget: Widget | None = None

        self._current_comic_path = ""
        self._current_title_str = ""
        self.action_bar_title = ""

        # When reading the "All One-Pagers" or "All Covers" collection, the window
        # title tracks the item on the current page (updated per page turn in
        # _show_page). None for any other comic.
        self._collection_titles: list[str] | None = None

        self._add_reader_widgets()

        self._comic_book_loader = ComicBookLoader(
            self._reader_settings,
            self._first_image_loaded,
            self._all_images_loaded,
            self._load_error,
            scheduler=KivyClockScheduler(),
            cursor=KivyCursor(),
        )

        self._all_loaded = False
        self._closed = False
        # Kivy Clock handle for the "waiting for a not-yet-loaded page" poll, or
        # None when no page is currently being awaited. See _show_page.
        self._pending_poll_ev: ClockEvent | None = None
        # Kivy Clock handle for the reveal timeout armed while page one loads, and the
        # "not yet revealed" flag in one: it is None both before a comic is opened and
        # once the reader screen has been shown. See _arm_reveal.
        self._reveal_ev: ClockEvent | None = None
        # Told once, when page one of the comic just opened has drawn, then dropped: a
        # comic closed before that (a load error) never opened. See read_comic.
        self._on_comic_opened: Callable[[], None] | None = None
        # Told if the comic's pages cannot be read: the user hears why from whoever
        # opened it. See _load_error.
        self._on_load_failed: Callable[[], None] | None = None
        self._goto_page_dropdown: ReaderDropDown | None = None
        self._goto_page_buttons: list[Button] = []
        self._tagged_pages: frozenset[str] = frozenset()

        # Every change of the current page index shows that page. The manager holds
        # the reader weakly, as the Kivy bind it replaced did: the reader owns the
        # manager, and a strong callback would be a cycle only a full gc frees.
        reader = weakref.ref(self)
        self._page_manager = ComicPageManager(lambda: _call_if_alive(reader, "_show_page"))

        self._navigation = ReaderNavigation(0.09, is_fullscreen=WindowManager.is_fullscreen_now)

        self._time_to_load_comic = Timing()

    def _add_reader_widgets(self) -> None:
        self._loading_page_texture = file_texture(
            self._reader_settings.sys_file_paths.get_empty_page_file()
        )

        self._comic_image = Image()
        self._comic_image.fit_mode = "contain"
        self._comic_image.mipmap = False
        self.add_widget(self._comic_image)

        # Where the page lands, logged once a frame at most and only when it moves:
        # the GUI harness holds it centred (log_markers.PAGE_PLACED).
        self._last_page_placement: PagePlacement | None = None
        self._log_page_placement_trigger = Clock.create_trigger(self._log_page_placement, 0)
        self._comic_image.bind(
            pos=self._on_page_layout_changed,
            size=self._on_page_layout_changed,
            norm_image_size=self._on_page_layout_changed,
            texture=self._on_page_layout_changed,
        )

    def _on_page_layout_changed(self, *_args: object) -> None:
        self._log_page_placement_trigger()

    def log_page_placement_afresh(self) -> None:
        """Log where the page is, even unchanged: its screen has just come to rest.

        A screen transition moves the whole screen, not the page within it, so the
        place logged as the screen slid in can stand unreplaced; this is the one the
        page settles at once the transition is over.
        """
        self._last_page_placement = None
        self._log_page_placement_trigger()

    def _log_page_placement(self, _dt: float) -> None:
        image = self._comic_image
        # Not the "loading" placeholder: it shows before the reader has laid itself
        # out, at the image's default size, and is no page the reader placed.
        if image.texture is None or image.texture is self._loading_page_texture:
            return
        fitted_width, fitted_height = image.norm_image_size
        x, y, width, height = fitted_page_rect(
            image.center_x, image.center_y, fitted_width, fitted_height
        )
        window_x, window_y = image.to_window(x, y)
        placement = PagePlacement(
            round(window_x), round(window_y), width, height, int(Window.width), int(Window.height)
        )
        self._last_page_placement = log_page_placement(placement, self._last_page_placement)

    def set_goto_page_widget(self, goto_page_widget: Widget) -> None:
        self._goto_page_widget = goto_page_widget

    def set_reader_navigation_regions(self, width: int, height: int) -> None:
        self._navigation.update_regions(width, height, self.x, self.y)

    @property
    def _current_page_index(self) -> int:
        return self._page_manager.get_current_page_index()

    @property
    def _current_page_str(self) -> str:
        return self._page_manager.get_current_page_str()

    @property
    def _page_map(self) -> OrderedDict[str, PageInfo]:
        page_map = self._page_manager.page_map
        assert page_map is not None  # set by set_layout before any page is shown
        return page_map

    def get_last_read_page(self) -> str:
        return self._current_page_str

    def get_current_display_unit(self) -> DisplayUnit | None:
        """Return the current display unit (for double page mode awareness)."""
        return self._page_manager.get_current_display_unit()

    def is_click_in_top_margin(self, touch: MotionEvent) -> bool:
        x_rel = round(touch.x - self.x)
        y_rel = round(touch.y - self.y)
        return self._navigation.is_in_top_margin(x_rel, y_rel)

    def tap_target_regions(self) -> dict[str, Rect]:
        """Return the page-turn margins and the top margin, for a GUI test to tap."""
        regions = self._navigation.tap_regions(round(self.width), round(self.height))
        return {
            name: window_rect(self, self.x + x, self.y + y, w, h)
            for name, (x, y, w, h) in regions.items()
        }

    @override
    def on_touch_down(self, touch: MotionEvent) -> bool:
        logger.debug(
            f"Touch down event: self.x,self.y = {self.x},{self.y},"
            f" touch.x,touch.y = {round(touch.x)},{round(touch.y)},"
            f" window_width = {round(self.width)},"
            f" window_height = {round(self.height)}."
            f" x_mid = {self._navigation.x_mid}, y_top_margin = {self._navigation.y_top_margin}."
        )

        if super().on_touch_down(touch):
            return True
        if self._closed:
            return False  # closing: no page to turn to
        if not is_tap(touch):
            return False  # a wheel tick's position says nothing of which way to turn

        x_rel = round(touch.x - self.x)
        y_rel = round(touch.y - self.y)

        if self._navigation.is_in_left_margin(x_rel, y_rel):
            logger.debug(log_markers.LEFT_MARGIN_PRESSED.format(x=x_rel, y=y_rel))
            self._page_manager.prev_page()
            return True

        if self._navigation.is_in_right_margin(x_rel, y_rel):
            logger.debug(log_markers.RIGHT_MARGIN_PRESSED.format(x=x_rel, y=y_rel))
            self._page_manager.next_page()
            return True

        logger.debug(
            f"Dead zone: x_rel,y_rel = {x_rel},{y_rel},"
            f" Screen mode = {WindowManager.get_screen_mode_now()}."
        )
        return False

    def init_data(self) -> None:
        self._comic_book_loader.init_data()

    def read_comic(
        self,
        fanta_info: FantaComicBookInfo,
        use_fantagraphics_overrides: bool,
        comic_book_image_builder: ComicBookImageBuilder,
        page_to_first_goto: str,
        layout: ComicLayout,
        tagged_pages: Sequence[str] = (),
        on_comic_opened: Callable[[], None] | None = None,
        on_load_failed: Callable[[], None] | None = None,
    ) -> None:
        page_map = layout.page_map
        assert (page_to_first_goto == COMIC_BEGIN_PAGE) or (page_to_first_goto in page_map)
        self._tagged_pages = frozenset(tagged_pages)
        self._on_comic_opened = on_comic_opened
        self._on_load_failed = on_load_failed

        self._current_title_str = get_comic_display_title(fanta_info.comic_book_info)

        # For the collections the window title is per-page (set in _show_page); for
        # everything else it is the comic's title, set once here.
        self._collection_titles = _get_collection_titles(fanta_info.comic_book_info.title)

        self._stop_pending_poll()
        self._all_loaded = False
        self._goto_page_dropdown = None
        self._page_manager.reset_current_page_index()
        self.action_bar_title = get_action_bar_title(self._font_manager, self._current_title_str)

        # The collections are always single-page: each page is a separate gag or
        # cover, so a two-page spread would pair unrelated items.
        self._set_double_page_mode(
            False if self.is_single_page_only_collection else self.opens_two_up
        )
        self._page_manager.set_layout(layout, page_to_first_goto)

        self._time_to_load_comic.restart()

        archive_path, fanta_volume_archive = self._comic_book_loader.resolve_archive_for_comic(
            fanta_info, page_map, use_fantagraphics_overrides=use_fantagraphics_overrides
        )
        # Asked at each open: a monitor plugged in since the last comic counts.
        max_width, max_height = SCREEN_METRICS.largest_screen_size()
        image_source = ArchivePageImageSource(
            archive_path=archive_path,
            fanta_volume_archive=fanta_volume_archive,
            comic_book_image_builder=comic_book_image_builder,
            empty_page_image=self._comic_book_loader.empty_page_image,
            use_fantagraphics_overrides=use_fantagraphics_overrides,
            max_width=max_width,
            max_height=max_height,
            decode_whole=self._reader_settings.decode_pages_whole,
        )
        archive_desc = str(archive_path)
        self._comic_book_loader.set_comic(
            image_source,
            self._page_manager.get_image_load_order(),
            page_map,
            archive_desc=archive_desc,
            num_pages_awaited=len(self._page_manager.get_first_pages_to_read()),
        )

        self._closed = False

        # Wipe the outgoing comic's page before anyone can see the reader, then wait for
        # page one instead of switching to it now: _render_page reveals the screen as soon
        # as it has drawn, so the screen transition uncovers the comic itself rather than
        # a blank page. This clear must be immediate, not scheduled - a page that loads
        # inside the frame would be wiped by a clear arriving after it.
        self._show_loading_page()
        self._arm_reveal()

    def close_comic_book_reader(self) -> None:
        if self._closed:
            return

        # A comic abandoned before page one drew (a load error) must not go on to
        # reveal an empty reader when its timeout fires, and never opened.
        self._cancel_reveal()
        self._on_comic_opened = None
        self._on_load_failed = None
        self._stop_pending_poll()
        self._comic_book_loader.stop_now()
        self._comic_book_loader.close_comic()
        # Closed from here on, not only once reset: leaving fullscreen on the way
        # out takes a moment, and a page turn in it would ask the closed loader
        # for a page (an assertion, and the app down).
        self._closed = True

    def reset_comic_book_reader(self) -> None:
        self._page_manager.reset_current_page_index()
        self._goto_page_dropdown = None
        self._goto_page_buttons.clear()
        self._closed = True

    def _first_image_loaded(self) -> None:
        # Past the reveal timeout the reader is up on the loading page, and the user may
        # have picked a page from the goto list: that is where they want to be.
        if self._current_page_index == -1:
            self._page_manager.set_to_first_page_to_read()
        logger.debug(f"First image loaded: current page index = {self._current_page_index}.")

    def _all_images_loaded(self) -> None:
        self._all_loaded = True
        logger.info(
            log_markers.ALL_IMAGES_LOADED.format(
                elapsed=self._time_to_load_comic.get_elapsed_time_with_unit(),
                index=self._current_page_index,
            )
        )

    def _load_error(self) -> None:
        self._all_loaded = False
        on_load_failed = self._on_load_failed
        # Closed now, whatever follows: the loader has dropped the pages, so a reveal, a
        # page poll or a page turn from here on would ask it for one that is gone.
        self.close_comic_book_reader()
        if on_load_failed is not None:
            on_load_failed()

    def _show_loading_page(self) -> None:
        self._comic_image.texture = self._loading_page_texture

    def _set_collection_action_bar_title(self, titles: list[str], page_str: str) -> None:
        """Set the window title to the item shown on the collection's *page_str*.

        Collection display pages are ``1..N`` in the order of *titles*, so page ``N``
        maps to ``titles[N - 1]``.
        """
        try:
            title = titles[int(page_str) - 1]
        except (ValueError, IndexError):
            return
        self.action_bar_title = get_action_bar_title(self._font_manager, title)

    def _show_page(self) -> None:
        """Display the image for the current_page_index.

        If the page is already loaded (the common case) it is drawn immediately.
        If it has not been prefetched yet (e.g. paging backward into a large comic
        that is still loading), the reader shows the loading page and a busy cursor,
        asks the loader to fetch this page next, and polls on the Kivy Clock until
        it is ready - never blocking the UI thread (which would freeze the app and
        trigger the OS "Force Quit" dialog).
        """
        if self._current_page_index == -1:
            logger.debug("Show page not ready: current_page_index = -1.")
            return

        page_str = self._current_page_str
        logger.debug(
            log_markers.PAGE_IMAGE_SHOWN.format(
                index=self._current_page_index,
                page_type=self._page_map[page_str].page_type.name,
                image=self._comic_book_loader.get_image_info_str(page_str),
            )
        )

        if self._collection_titles is not None:
            self._set_collection_action_bar_title(self._collection_titles, page_str)

        left_idx, right_idx = self._get_current_display_indices()

        if self._pages_ready(left_idx, right_idx):
            self._render_page(left_idx, right_idx)
            return

        # Page not loaded yet: keep the current page on screen with a busy cursor
        # (rather than flashing a blank loading page) and wait without blocking the
        # UI thread. _render_page swaps to the new page once it is ready. The initial
        # comic open has no current page, so read_comic shows the loading page there.
        logger.info(log_markers.PAGE_AWAITING_LOAD.format(index=self._current_page_index))
        self._prioritize_pending(left_idx, right_idx)
        self._start_pending_poll()

    def _get_current_display_indices(self) -> tuple[int, int | None]:
        """Return the (left, right) page indices to display for the current page.

        ``right`` is ``None`` outside double-page mode (a single page).
        """
        display_unit = self._page_manager.get_current_display_unit()
        if display_unit is not None and self._page_manager.double_page_mode:
            return display_unit.left_page_index, display_unit.right_page_index
        return self._current_page_index, None

    @staticmethod
    def _needed_indices(left_page_index: int, right_page_index: int | None) -> list[int]:
        """Return the page indices to display (drops the absent right page)."""
        return [idx for idx in (left_page_index, right_page_index) if idx is not None]

    def _pages_ready(self, left_page_index: int, right_page_index: int | None) -> bool:
        """Return whether every page needed to display is loaded (non-blocking)."""
        if self._all_loaded:
            return True
        return all(
            self._comic_book_loader.wait_load_event(idx, 0)
            for idx in self._needed_indices(left_page_index, right_page_index)
        )

    def _prioritize_pending(self, left_page_index: int, right_page_index: int | None) -> None:
        """Ask the loader to fetch the awaited page(s) next, ahead of prefetch order."""
        for idx in self._needed_indices(left_page_index, right_page_index):
            self._comic_book_loader.prioritize_page(self._page_manager.get_page_str(idx))

    def _start_pending_poll(self) -> None:
        """Start (once) the Clock poll that renders a page as soon as it loads.

        Sets the busy cursor here, under the same ``is None`` guard, so each
        ``set_busy`` is paired one-to-one with the single ``set_normal`` in
        ``_stop_pending_poll`` - the cursor stays balanced no matter how many
        times ``_show_page`` re-enters the not-ready branch while awaiting.
        """
        if self._pending_poll_ev is None:
            self._comic_book_loader.cursor.set_busy()
            self._pending_poll_ev = Clock.schedule_interval(
                self._poll_pending_page, PENDING_PAGE_POLL_INTERVAL_SECS
            )

    def _stop_pending_poll(self) -> None:
        """Cancel the pending-page poll (if any) and restore the normal cursor."""
        if self._pending_poll_ev is not None:
            self._pending_poll_ev.cancel()
            self._pending_poll_ev = None
            self._comic_book_loader.cursor.set_normal()

    def _arm_reveal(self) -> None:
        """Hold the reader screen back until page one is drawn, or the wait times out.

        The calling screen stays up meanwhile, which is the point of the exercise: the
        loader has already set a busy cursor for this window, so the wait is signposted,
        and the screen transition that follows then uncovers the comic itself instead of
        a blank page.
        """
        self._cancel_reveal()
        self._reveal_ev = Clock.schedule_once(
            self._reveal_on_timeout, FIRST_PAGE_REVEAL_TIMEOUT_SECS
        )

    def _cancel_reveal(self) -> None:
        """Drop any pending reveal, so the reader screen will not be switched to."""
        if self._reveal_ev is not None:
            self._reveal_ev.cancel()
            self._reveal_ev = None

    def _reveal_on_timeout(self, _dt: float) -> None:
        """Switch to the reader anyway, on the loading page, when page one is too slow."""
        logger.warning(
            f"Page one was not drawn within {FIRST_PAGE_REVEAL_TIMEOUT_SECS}s;"
            f" showing the reader on the loading page."
        )
        self._reveal_reader()

    def _reveal_reader(self) -> None:
        """Switch to the comic reader screen - once only, for the comic just opened.

        ``_reveal_ev`` doubles as the guard: it is non-None only between ``_arm_reveal``
        and the reveal, so the ``_render_page`` call on every later page turn is a no-op.
        """
        if self._reveal_ev is None:
            return
        self._cancel_reveal()
        self._on_comic_is_ready_to_read()

    def _poll_pending_page(self, _dt: float) -> bool:
        """Clock callback: render the current page once it has finished loading.

        Always re-reads the *current* page index, so if the user keeps paging while
        waiting, the latest target wins. Returns ``False`` to unschedule once the
        page is shown (or the comic has been closed), ``True`` to keep polling.
        """
        if self._current_page_index == -1:
            self._stop_pending_poll()
            return False

        left_idx, right_idx = self._get_current_display_indices()
        if not self._pages_ready(left_idx, right_idx):
            return True

        self._render_page(left_idx, right_idx)
        return False

    def _render_page(self, left_page_index: int, right_page_index: int | None) -> None:
        """Draw the given (already-loaded) page(s) into the comic image widget."""
        self._stop_pending_poll()

        timing = Timing()

        # noinspection PyBroadException
        try:
            if right_page_index is not None:
                page = self._comic_book_loader.get_double_page_image_ready_for_reading(
                    left_page_index, right_page_index
                )
            else:
                page = self._comic_book_loader.get_image_ready_for_reading(left_page_index)
            self._comic_image.texture = page_texture(page)
        except Exception:  # noqa: BLE001
            logger.exception(f"Error displaying image with index {self._current_page_index}: ")
            # Page one is what opening the comic waited for: it did not open, and is no read.
            if self._on_comic_opened is not None:
                self._load_error()
                return
            # One bad page further in need not end the read: the next may turn up fine.
            self._comic_image.texture = self._loading_page_texture

        logger.info(
            log_markers.SHOWED_PAGE.format(
                index=self._current_page_index, elapsed=timing.get_elapsed_time_with_unit()
            )
        )

        # Page one of a newly opened comic is what the reader screen was held back for.
        self._reveal_reader()
        if self._on_comic_opened is not None:
            on_comic_opened, self._on_comic_opened = self._on_comic_opened, None
            on_comic_opened()

    def _hide_action_bar_if_fullscreen(self) -> None:
        if WindowManager.is_fullscreen_now():
            self._hide_action_bar()

    def _ignored_once_closed(self, action: str) -> bool:
        """Return whether the comic is closed, so that *action* must not go ahead.

        A closed loader has no pages: a move would ask it for one, which is an assertion
        and the app down. A load error closes the comic about a second before the screen
        leaves, with the bar's buttons still live.
        """
        if self._closed:
            logger.debug(f"{action} ignored: the comic is closed.")
        return self._closed

    def goto_start_page(self) -> None:
        if self._ignored_once_closed("Goto start page"):
            return
        self._page_manager.goto_start_page()
        self._hide_action_bar_if_fullscreen()

    def goto_last_page(self) -> None:
        if self._ignored_once_closed("Goto last page"):
            return
        self._page_manager.goto_last_page()
        self._hide_action_bar_if_fullscreen()

    @property
    def double_page_mode(self) -> bool:
        """Return the current active double-page mode (not the config setting)."""
        return self._page_manager.double_page_mode

    def _set_double_page_mode(self, on: bool) -> None:
        self._page_manager.double_page_mode = on
        self.two_up = on

    @property
    def is_single_page_only_collection(self) -> bool:
        """Whether the current comic is a collection that is always single-page."""
        return self._collection_titles is not None

    def next_page(self) -> None:
        if self._ignored_once_closed("Next page"):
            return
        self._page_manager.next_page()

    def prev_page(self) -> None:
        if self._ignored_once_closed("Prev page"):
            return
        self._page_manager.prev_page()

    def toggle_double_page_mode(self) -> None:
        """Toggle double-page mode on/off for the current comic only (does not change config)."""
        if self._ignored_once_closed("Double page toggle"):
            return
        if self.is_single_page_only_collection:
            # The collections are always single-page - ignore the toggle.
            logger.debug(log_markers.DOUBLE_PAGE_IGNORED)
            return
        self._set_double_page_mode(not self._page_manager.double_page_mode)
        logger.info(
            log_markers.DOUBLE_PAGE_TOGGLED.format(mode=self._page_manager.double_page_mode)
        )
        self._show_page()

    def goto_page(self) -> bool:
        """Open the goto-page dropdown; return whether it opened."""
        if not self._goto_page_dropdown:
            self._create_goto_page_dropdown()
            assert self._goto_page_dropdown
        # Made once per comic, and the window may have been resized since.
        max_dropdown_height = round(GOTO_PAGE_DROPDOWN_FRAC_OF_HEIGHT * self.height)
        logger.debug(f"Goto page dropdown: max_dropdown_height = {max_dropdown_height}.")
        self._goto_page_dropdown.max_height = max_dropdown_height

        selected_index = self._get_current_page_button_index()
        # Update button colors to highlight the current page before opening
        for index, button in enumerate(self._goto_page_buttons):
            page_info = self._page_map[button.text]
            if index == selected_index:
                button.background_color = GOTO_PAGE_BUTTON_CURRENT_PAGE_COLOR
            elif button.text in self._tagged_pages:
                button.background_color = GOTO_PAGE_BUTTON_TAGGED_COLOR
            else:
                button.background_color = (
                    GOTO_PAGE_BUTTON_BODY_COLOR
                    if page_info.page_type == PageType.BODY
                    else GOTO_PAGE_BUTTON_NONBODY_COLOR
                )

        assert self._goto_page_widget is not None
        if not open_dropdown(self._goto_page_dropdown, self._goto_page_widget):
            return False
        if selected_index is not None:
            self._goto_page_dropdown.scroll_to(self._goto_page_buttons[selected_index])
        logger.debug(log_markers.GOTO_PAGE_DROPDOWN_OPENED)
        return True

    def _get_current_page_button_index(self) -> int | None:
        for index, button in enumerate(self._goto_page_buttons):
            if self._page_map[button.text].page_index == self._current_page_index:
                return index
        return None

    def on_page_selected(self, _instance: Widget, page: str) -> None:
        if self._ignored_once_closed("Goto page selection"):
            return
        logger.info(log_markers.GOTO_PAGE_SELECTED.format(page=page))
        self._page_manager.set_current_page_index_from_str(page)
        self._hide_action_bar_if_fullscreen()

    def open_goto_page_for_keyboard(self, on_dismiss: Callable) -> int | None:
        """Open the goto-page dropdown for keyboard nav.

        Returns:
            The index of the button to focus, or None if the dropdown did not open.

        """
        if not self.goto_page():
            return None
        assert self._goto_page_dropdown is not None  # goto_page made it, to open it
        self._goto_page_dropdown.bind(on_dismiss=on_dismiss)
        return self._get_current_page_button_index() or 0

    def get_goto_page_buttons(self) -> list[Button]:
        return self._goto_page_buttons

    def scroll_goto_page_to(self, button: Button) -> None:
        if self._goto_page_dropdown:
            self._goto_page_dropdown.scroll_to(button)

    def dismiss_goto_page_dropdown(self) -> None:
        if self._goto_page_dropdown:
            self._goto_page_dropdown.dismiss()

    def unbind_goto_page_dismiss(self, callback: Callable) -> None:
        if self._goto_page_dropdown:
            self._goto_page_dropdown.unbind(on_dismiss=callback)

    def _create_goto_page_dropdown(self) -> None:
        logger.debug("Creating goto page dropdown.")

        self._goto_page_dropdown = ReaderDropDown(
            auto_dismiss=True,
            dismiss_on_select=True,
            on_select=self.on_page_selected,
        )
        assert self._goto_page_dropdown is not None
        self._goto_page_buttons.clear()

        logger.debug(f"Adding {len(self._page_map)} page buttons to dropdown.")
        for page, page_info in self._page_map.items():
            button = Button(
                text=str(page),
                size_hint_y=None,
                height=GOTO_PAGE_BUTTON_HEIGHT,
                bold=page_info.page_type == PageType.BODY,
            )
            button.bind(on_press=lambda btn: self._goto_page_dropdown.select(btn.text))
            self._goto_page_dropdown.add_widget(button)
            self._goto_page_buttons.append(button)


class ComicBookReaderScreen(ReaderScreen, ReaderCloseMixin, DropdownNavMixin, ActionBarNavMixin):
    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
    # Opacity for an action-bar button that is greyed out (e.g. the double-page
    # toggle while reading the single-page-only one-pager collection).
    _GREYED_BUTTON_OPACITY = 0.4
    action_bar_title = StringProperty()
    # Width of the inner action bar (centered to match the comic image's aspect-fit width).
    action_bar_width = NumericProperty(1)  # must be non-zero for initial build
    app_icon_filepath = StringProperty()
    is_fullscreen = BooleanProperty(defaultvalue=False)
    # The main screen's layout ("single" or "spread"); the app sets it. On the spread a
    # comic opens two pages at a time; a change under an open comic waits for the next
    # (the bar's Double Page is there meanwhile).
    layout_mode = StringProperty(MainLayoutMode.SINGLE.value)
    # Declared so a caller's `screen.comic_book_reader.read_comic(...)` is type-checked:
    # the Kivy base has no stubs, so an undeclared attribute reads as Unknown.
    comic_book_reader: ComicBookReader

    def on_enter(self, *args: object) -> None:
        super().on_enter(*args)
        self.comic_book_reader.log_page_placement_afresh()

    def on_layout_mode(self, _instance: Widget, mode: str) -> None:
        """Have the next comic open two-up on the spread, one page at a time otherwise."""
        self.comic_book_reader.opens_two_up = mode == MainLayoutMode.SPREAD.value

    @property
    @override
    def drag_region(self) -> Widget | None:
        # The reader's bar is a page wide and centred (`action_bar_width`), not the
        # main bar's layout, so it takes the window-drag hit test over while it is up.
        return self.ids.action_bar_inner.drag_region

    def __init__(
        self,
        reader_settings: ReaderSettings,
        reader_app_icon_file: str,
        font_manager: FontManager,
        window_manager: WindowManager,
        on_comic_is_ready_to_read_func: Callable[[], None],
        on_close_reader_func: Callable[[], None],
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)

        self._reader_settings = reader_settings
        self.app_icon_filepath = reader_app_icon_file
        self._on_comic_is_ready_to_read_func = on_comic_is_ready_to_read_func
        self._on_close_reader = on_close_reader_func
        self.can_benefit_from_fullscreen = True
        self._active = False

        # The window-mode engine is shared with the main screen (one geometry
        # store); this controller carries the toggle policy + this screen's
        # completion callbacks.
        self._mode = WindowModeController(
            ComicBookReaderScreen.__name__,
            window_manager,
            WindowModeCallbacks(
                on_windowed_first_resize=self._set_hints_for_windowed_mode,
                on_finished_windowed=self._on_finished_goto_windowed_mode,
                on_finished_fullscreen=self._on_finished_goto_fullscreen_mode,
            ),
        )

        self._action_bar = self.ids.action_bar
        self._action_bar_fullscreen_icon = str(
            self._reader_settings.sys_file_paths.get_barks_reader_fullscreen_icon_file()
        )
        self._action_bar_fullscreen_exit_icon = str(
            self._reader_settings.sys_file_paths.get_barks_reader_fullscreen_exit_icon_file()
        )

        self._was_fullscreen_on_entry = False
        self._fullscreen_button = self.ids.fullscreen_button
        self._is_closing = False

        self._resize_binding()

        self.comic_book_reader = ComicBookReader(
            self._reader_settings,
            font_manager,
            self._on_comic_is_ready_to_read,
            self._hide_action_bar,
        )
        self.comic_book_reader.set_goto_page_widget(self.ids.goto_page_button)
        # Mirror the reader's title onto the screen so per-page title changes (e.g. the
        # "All One-Pagers" collection) reach the action bar automatically.
        self.comic_book_reader.bind(action_bar_title=self.setter("action_bar_title"))
        # The bar is as wide as the comic's mode, a page or the pair (see
        # _reset_action_bar_width).
        self.comic_book_reader.bind(two_up=self._on_two_up)
        self.ids.image_layout.add_widget(self.comic_book_reader)
        self._reset_action_bar_width()

        # Ordered left-to-right as they appear in the action bar.
        self._setup_action_bar_nav(
            [
                self.ids.close_button,
                self.ids.fullscreen_button,
                self.ids.double_page_button,
                self.ids.goto_start_button,
                self.ids.goto_end_button,
                self.ids.goto_page_button,
            ]
        )
        self._setup_dropdown_nav()

    _dropdown_wraps: bool = False
    _dropdown_page_step: int = 10

    @override
    def _activate_focused_button(self) -> None:
        if self._menu_buttons[self._focused_btn_idx] is self.ids.goto_page_button:
            self._last_used_btn_idx = self._focused_btn_idx
            self._open_goto_page_for_keyboard()
        else:
            super()._activate_focused_button()

    def _get_dropdown_buttons(self) -> list[Button]:
        return self.comic_book_reader.get_goto_page_buttons()

    def _dismiss_dropdown(self) -> None:
        self.comic_book_reader.dismiss_goto_page_dropdown()

    def _scroll_to_dropdown_button(self, btn: object) -> None:
        assert isinstance(btn, Button)
        self.comic_book_reader.scroll_goto_page_to(btn)

    def open_goto_page_from_bar(self) -> None:
        """Open the goto-page dropdown from its bar button, with the arrow keys live in it.

        It opens as the keyboard opens it, focused on the current page; its dismissal
        leaves menu mode again.
        """
        self._open_list_from_bar(self.ids.goto_page_button, self._activate_focused_button)

    def _open_goto_page_for_keyboard(self) -> None:
        self._clear_menu_focus()
        focused_idx = self.comic_book_reader.open_goto_page_for_keyboard(
            self._on_goto_page_dropdown_dismissed
        )
        if focused_idx is None:
            self._update_menu_focus()
            return
        self._enter_dropdown_nav(initial_idx=focused_idx)

    def _on_goto_page_dropdown_dismissed(self, instance: Widget) -> None:
        self.comic_book_reader.unbind_goto_page_dismiss(self._on_goto_page_dropdown_dismissed)
        self._on_dropdown_dismissed(instance)

    @override
    def is_active(self, active: bool) -> None:
        logger.info(f"ComicBookReaderScreen active changed from {self._active} to {active}.")

        self._active = active

        if not self._active:
            if self._menu_mode:
                self._exit_menu_mode()
            Window.unbind(on_key_down=self._on_key_down)
            self._was_fullscreen_on_entry = False
            self.is_fullscreen = False
            return

        Window.bind(on_key_down=self._on_key_down)

        self._update_window_mode()
        self._update_window_state()
        self._update_widget_states()

        logger.debug(
            f"Screen mode = {WindowManager.get_screen_mode_now()},"
            f" self._was_fullscreen_on_entry = {self._was_fullscreen_on_entry}."
            f" self._goto_fullscreen_on_comic_read = {self._goto_fullscreen_on_comic_read}."
            f" self.is_fullscreen = {self.is_fullscreen}."
            f" self._action_bar.height = {self._action_bar.height}."
        )

    @override
    def on_touch_down(self, touch: MotionEvent) -> bool:
        if self._is_closing:
            return True  # as for keys (_on_key_down): nothing left to act on
        if is_tap(touch):
            return self._on_tap_down(touch)
        # A wheel tick or another button: not a tap on the margin, nor one leaving the menu.
        return bool(super().on_touch_down(touch))

    # In fullscreen a click in the top margin toggles the action bar: it reveals a hidden
    # bar, and a click in the strip of the margin left below a shown bar hides it again.
    # Clicks on the bar itself go to its buttons (which sit above the image area thanks
    # to the BoxLayout reflow). Windowed, the bar is always up and the margin does nothing.
    # The bar's state is read before the tap leaves menu mode: a bar the menu showed is
    # hidden again by that, and the margin under it must not then bring it straight back.
    # A tap on such a bar keeps it, for the button under the tap to take the press.
    def _on_tap_down(self, touch: MotionEvent) -> bool:
        bar_was_hidden = self._is_action_bar_hidden()
        self._clear_menu_on_touch(on_bar=self._action_bar.collide_point(*touch.pos))

        if super().on_touch_down(touch):
            # Another button has been pressed.
            return True

        if not self.comic_book_reader.is_click_in_top_margin(touch):
            return False

        if bar_was_hidden:
            logger.debug(log_markers.ACTION_BAR_SHOWN_ON_TOP_MARGIN)
            self._show_action_bar()
            return True

        if WindowManager.is_fullscreen_now() and not self._action_bar.collide_point(*touch.pos):
            logger.debug(log_markers.ACTION_BAR_HIDDEN_ON_TOP_MARGIN)
            self._hide_action_bar()
            return True

        return False

    def _on_comic_is_ready_to_read(self) -> None:
        self._on_comic_is_ready_to_read_func()
        self._sync_double_page_button()

    def _on_key_down(
        self, _window: WindowBase, key: int, _scancode: int, _codepoint: str, _modifier: list[str]
    ) -> bool:
        if self._is_closing:
            # Leaving fullscreen on the way out takes a moment, with the comic
            # already closed: a page turn or bar action now has nothing to act on.
            return True
        return self._handle_reader_key(key)

    def _reading_next_page(self) -> None:
        self.comic_book_reader.next_page()

    def _reading_prev_page(self) -> None:
        self.comic_book_reader.prev_page()

    def _is_action_bar_hidden(self) -> bool:
        return not is_action_bar_visible(self._action_bar)

    def _on_action_bar_shown_for_menu(self) -> None:
        self._show_action_bar()

    def _on_action_bar_hidden_after_menu(self) -> None:
        if not self._is_action_bar_hidden():
            self._hide_action_bar()

    @override
    def _dismiss_shown_bar_on_escape(self) -> bool:
        if not WindowManager.is_fullscreen_now() or self._is_action_bar_hidden():
            return False
        logger.debug(log_markers.ACTION_BAR_HIDDEN_ON_ESCAPE)
        self._hide_action_bar()
        return True

    def close_comic_book_reader(self) -> None:
        self._is_closing = True
        self.comic_book_reader.close_comic_book_reader()
        self._exit_fullscreen()

    @property
    def _goto_fullscreen_on_comic_read(self) -> bool:
        return (
            self.can_benefit_from_fullscreen and self._reader_settings.goto_fullscreen_on_comic_read
        )

    def _update_window_mode(self) -> None:
        self._was_fullscreen_on_entry = bool(WindowManager.is_fullscreen_now())

        if not self._was_fullscreen_on_entry and self._goto_fullscreen_on_comic_read:
            self._mode.goto_fullscreen()

        # Reflect the mode the window is actually in; if a goto was issued
        # above, its finish callback updates this when the transition lands
        # (setting it optimistically here would leave the UI state inverted if
        # the transition fails).
        self.is_fullscreen = self._was_fullscreen_on_entry

    def toggle_screen_mode(self) -> None:
        self._mode.toggle()

    def toggle_double_page_mode(self) -> None:
        """Toggle double-page mode on/off for the current comic (does not change config)."""
        self.comic_book_reader.toggle_double_page_mode()
        self._sync_double_page_button()
        if WindowManager.is_fullscreen_now():
            self._hide_action_bar()

    def _sync_double_page_button(self) -> None:
        """Sync the double-page button to the current mode; grey it for the collection.

        The one-pager collection is single-page only, so the toggle is greyed out.
        We dim via opacity rather than the ``disabled`` flag: this is an icon
        ActionButton, and Kivy's disabled state drops the icon and reveals the faint
        "Double Page" text label. ``toggle_double_page_mode`` is already a no-op for
        the collection, so the greyed (but technically enabled) button is inert.
        """
        button = self.ids.double_page_button
        button.opacity = (
            self._GREYED_BUTTON_OPACITY
            if self.comic_book_reader.is_single_page_only_collection
            else 1.0
        )

        if self.comic_book_reader.double_page_mode:
            button.icon = str(
                self._reader_settings.sys_file_paths.get_barks_reader_single_page_icon_file()
            )
        else:
            button.icon = str(
                self._reader_settings.sys_file_paths.get_barks_reader_double_page_icon_file()
            )

    def _on_finished_goto_windowed_mode(self) -> None:
        if self._is_closing:
            logger.debug("Entering windowed mode finished, now closing reader.")
            self._finish_closing_once_laid_out()

        self.is_fullscreen = False
        self._update_widget_states()
        self._update_fullscreen_button()
        logger.info(log_markers.ENTERED_WINDOWED.format(screen="ComicBookReaderScreen"))
        log_window_geometry("ComicBookReaderScreen windowed")

    def _exit_fullscreen(self) -> None:
        # Both branches delegate unconditionally: when the window is already in
        # the target mode the manager skips the transition but still fires the
        # finish callback, so the closing logic in the callbacks runs on the
        # same single completion path either way.
        # A comic that failed before its reader came up never ran is_active(True), so
        # there is no entry mode to restore: the window stays as the main screen has it.
        restore_fullscreen = (
            self._was_fullscreen_on_entry if self._active else WindowManager.is_fullscreen_now()
        )
        if restore_fullscreen:
            logger.debug("Fullscreen is required.")
            self._mode.goto_fullscreen()
        else:
            logger.debug("Fullscreen not required.")
            self._mode.goto_windowed()

    def _on_finished_goto_fullscreen_mode(self) -> None:
        self.is_fullscreen = self._is_fullscreen_now_after_goto()
        self._update_widget_states()
        self._update_fullscreen_button()

        logger.info(log_markers.ENTERED_FULLSCREEN.format(screen="ComicBookReaderScreen"))
        log_window_geometry("ComicBookReaderScreen fullscreen")

        if self._is_closing:
            logger.debug("Entering fullscreen mode finished, now closing reader.")
            self._finish_closing_once_laid_out()

    @override
    def _reader_action_bar(self) -> ActionBar:
        return self._action_bar

    @override
    def _finish_closing(self) -> None:
        logger.debug(
            log_markers.READER_CLOSING.format(
                width=round(self.width),
                height=round(self.height),
                win_width=int(Window.width),
                win_height=int(Window.height),
            )
        )
        self._on_close_reader()
        self._is_closing = False
        self.comic_book_reader.reset_comic_book_reader()

    def _on_window_resize(self, _window: WindowBase, width: int, height: int) -> None:
        if not self._active:
            return

        logger.debug(
            f"Active comic book reader window resize event:"
            f" self.x, self.y = {self.x},{self.y},"
            f" self.width, self.height = {self.width},{self.height}."
            f" Window.size = {Window.size},"
            f" width, height = {width},{height},"
            f" Screen mode = {WindowManager.get_screen_mode_now()},"
            f" self._actionbar height = {self._action_bar.height}."
        )

        self._update_window_state()

    def _resize_binding(self) -> None:
        Window.bind(on_resize=self._on_window_resize)

    def _update_window_state(self) -> None:
        self._reset_action_bar_width()
        self.comic_book_reader.set_reader_navigation_regions(Window.width, Window.height)

    def _on_two_up(self, _reader: ComicBookReader, _two_up: bool) -> None:
        self._reset_action_bar_width()

    def _reset_action_bar_width(self) -> None:
        # Match the inner action bar's width to the comic's aspect-fit width so it spans
        # the visible image area, not the full monitor width in fullscreen: a page's
        # in single-page mode, the pair's in double-page mode (the two pages are
        # composited as one landscape image, `SPREAD_WIDTH_IN_PAGES` pages wide: the
        # spread window's width). In double-page mode it
        # stays the pair's under a solo unit, the cover or an odd last page, as the
        # document reader's does on the spread: a bar that narrowed there moved its
        # buttons at a page turn, the first of every comic. It refits with the window
        # and with the mode (`two_up`: a comic's load and the Double Page toggle).
        aspect_ratio = COMIC_PAGE_ASPECT_RATIO
        if self.comic_book_reader.two_up:
            aspect_ratio /= SPREAD_WIDTH_IN_PAGES
        w, _ = get_win_dimensions(Window.height - ACTION_BAR_SIZE_Y, Window.width, aspect_ratio)
        self.action_bar_width = max(1, w)

    def _update_widget_states(self) -> None:
        visibility = (
            ActionBarVisibility.HIDDEN if self.is_fullscreen else ActionBarVisibility.VISIBLE
        )
        set_action_bar_visibility(self._action_bar, visibility)

        self._update_fullscreen_button()

    def _update_fullscreen_button(self) -> None:
        set_fullscreen_button(
            self._fullscreen_button,
            is_fullscreen=self.is_fullscreen,
            fullscreen_icon=self._action_bar_fullscreen_icon,
            fullscreen_exit_icon=self._action_bar_fullscreen_exit_icon,
        )


def get_barks_comic_reader_screen(
    screen_name: str,
    reader_settings: ReaderSettings,
    reader_app_icon_file: str,
    font_manager: FontManager,
    window_manager: WindowManager,
    on_comic_is_ready_to_read: Callable[[], None],
    on_close_reader: Callable[[], None],
) -> ComicBookReaderScreen:
    Builder.load_file(str(COMIC_BOOK_READER_KV_FILE))

    return ComicBookReaderScreen(
        reader_settings,
        reader_app_icon_file,
        font_manager,
        window_manager,
        on_comic_is_ready_to_read,
        on_close_reader,
        name=screen_name,
    )


def page_texture(page: PageImage) -> Texture:
    """Fill a texture from a page's pixels: no image format, so no decode, in between.

    PIL's rows run top to bottom and a texture's bottom to top, so the texture is
    flipped, as Kivy's image loaders flip the ones they make.

    Args:
        page: The loaded page.

    Returns:
        A texture showing the page the right way up.

    """
    # Don't mess with this. Using CoreImage will result in a 25% slowdown.
    color_format = page.mode.lower()
    texture = Texture.create(size=(page.width, page.height), colorfmt=color_format)
    texture.blit_buffer(page.pixels, colorfmt=color_format, bufferfmt="ubyte")
    texture.flip_vertical()
    return texture


def file_texture(file: PanelPath) -> Texture:
    """Load an image file into a texture, through Kivy's own image loaders.

    Args:
        file: The image, on disk or inside a zip file.

    Returns:
        A texture showing the image.

    """
    if isinstance(file, Path):
        return CoreImage(str(file)).texture

    return CoreImage(io.BytesIO(file.read_bytes()), ext=PNG_EXT_FOR_KIVY).texture
