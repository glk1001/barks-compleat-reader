from __future__ import annotations

import io
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
from comic_utils.timing import Timing
from kivy.clock import Clock, ClockEvent
from kivy.core.image import Image as CoreImage
from kivy.core.image import Texture
from kivy.core.window import Window, WindowBase
from kivy.event import EventDispatcher
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    NumericProperty,
    StringProperty,
)
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from loguru import logger
from screeninfo import get_monitors

from barks_reader.core.archive_page_image_source import ArchivePageImageSource
from barks_reader.core.comic_book_loader import ComicBookLoader
from barks_reader.core.display_unit import DisplayUnit
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE
from barks_reader.core.reader_formatter import get_action_bar_title
from barks_reader.core.reader_utils import PNG_EXT_FOR_KIVY, get_win_dimensions

from .action_bar_helpers import (
    ACTION_BAR_SIZE_Y,
    ActionBarVisibility,
    is_action_bar_visible,
    set_action_bar_visibility,
    set_fullscreen_button,
)
from .adapters import KivyClockScheduler, KivyCursor
from .platform_window_utils import WindowManager, WindowModeCallbacks, WindowModeController
from .reader_keyboard_nav import (
    ActionBarNavMixin,
    DropdownNavMixin,
)
from .reader_navigation import ReaderNavigation
from .reader_screens import ReaderScreen

if TYPE_CHECKING:
    from collections import OrderedDict
    from collections.abc import Callable

    from barks_build_comic_images.build_comic_images import ComicBookImageBuilder
    from barks_fantagraphics.barks_covers import BarksCover
    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from comic_utils.comic_consts import PanelPath
    from kivy.input import MotionEvent
    from kivy.uix.widget import Widget

    from barks_reader.core.comic_book_page_info import PageInfo
    from barks_reader.core.reader_settings import ReaderSettings

    from .font_manager import FontManager


# How often, while a not-yet-loaded page is being awaited, the reader re-checks
# whether that page has finished loading (seconds). Small enough to feel instant,
# large enough not to burn a frame budget while the loader thread works.
PENDING_PAGE_POLL_INTERVAL_SECS = 0.05

GOTO_PAGE_DROPDOWN_FRAC_OF_HEIGHT = 0.97
GOTO_PAGE_BUTTON_HEIGHT = dp(25)
GOTO_PAGE_BUTTON_BODY_COLOR = (0, 1, 1, 1)
GOTO_PAGE_BUTTON_NONBODY_COLOR = (0, 0.5, 0.5, 1)
GOTO_PAGE_BUTTON_CURRENT_PAGE_COLOR = (1, 1, 0, 1)

COMIC_BOOK_READER_KV_FILE = Path(__file__).with_suffix(".kv")


class _ComicPageManager(EventDispatcher):
    """Manages the state and navigation logic for a comic book's pages."""

    _current_page_index = NumericProperty(-1)

    def __init__(
        self,
        current_page_index_bound_func: Callable,
        *args,  # noqa: ANN002
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(*args, **kwargs)

        self.bind(_current_page_index=current_page_index_bound_func)

        self.page_map: OrderedDict[str, PageInfo] | None = None
        self._index_to_page_map: dict[int, str] = {}
        self._first_page_to_read_index = -1

        self._first_page_index = -1
        self._last_page_index = -1

        self._display_units: list[DisplayUnit] = []
        self._page_index_to_unit_idx: dict[int, int] = {}
        self.double_page_mode: bool = False

    def get_current_page_index(self) -> int:
        return self._current_page_index

    def reset_current_page_index(self) -> None:
        self._current_page_index = -1

    def get_current_page_str(self) -> str:
        return self._index_to_page_map.get(self._current_page_index, "")

    def get_current_display_unit(self) -> DisplayUnit | None:
        """Return the display unit that contains the current page index."""
        if not self._display_units:
            return None

        unit_idx = self._page_index_to_unit_idx.get(self._current_page_index)
        if unit_idx is None:
            return None

        return self._display_units[unit_idx]

    def set_current_page_index_from_str(self, page_str: str) -> None:
        assert self.page_map is not None
        page_index = self.page_map[page_str].page_index

        if self.double_page_mode and self._display_units:
            unit_idx = self._page_index_to_unit_idx.get(page_index)
            if unit_idx is not None:
                self._current_page_index = self._display_units[unit_idx].left_page_index
                return

        self._current_page_index = page_index

    def set_to_first_page_to_read(self) -> None:
        if self.double_page_mode and self._display_units:
            unit_idx = self._page_index_to_unit_idx.get(self._first_page_to_read_index)
            if unit_idx is not None:
                self._current_page_index = self._display_units[unit_idx].left_page_index
                return

        self._current_page_index = self._first_page_to_read_index

    def goto_start_page(self) -> None:
        first_idx = (
            self._display_units[0].left_page_index
            if self.double_page_mode and self._display_units
            else self._first_page_index
        )
        if self._current_page_index == first_idx:
            logger.debug(f"Already on the first page: current index = {self._current_page_index}.")
        else:
            logger.debug(f"Goto start page: requested index = {first_idx}.")
            self._current_page_index = first_idx

    def goto_last_page(self) -> None:
        last_idx = (
            self._display_units[-1].left_page_index
            if self.double_page_mode and self._display_units
            else self._last_page_index
        )
        if self._current_page_index == last_idx:
            logger.debug(f"Already on the last page: current index = {self._current_page_index}.")
        else:
            logger.debug(f"Last page: requested index = {last_idx}.")
            self._current_page_index = last_idx

    def next_page(self) -> None:
        if self.double_page_mode and self._display_units:
            unit_idx = self._page_index_to_unit_idx.get(self._current_page_index, -1)
            if unit_idx < 0 or unit_idx >= len(self._display_units) - 1:
                logger.debug(
                    f"Already on the last unit: current index = {self._current_page_index}."
                )
            else:
                next_unit = self._display_units[unit_idx + 1]
                logger.debug(f"Next unit: left_page_index = {next_unit.left_page_index}.")
                self._current_page_index = next_unit.left_page_index
        elif self._current_page_index >= self._last_page_index:
            logger.debug(f"Already on the last page: current index = {self._current_page_index}.")
        else:
            logger.debug(f"Next page: requested index = {self._current_page_index + 1}")
            self._current_page_index += 1

    def prev_page(self) -> None:
        if self.double_page_mode and self._display_units:
            unit_idx = self._page_index_to_unit_idx.get(self._current_page_index, -1)
            if unit_idx <= 0:
                logger.debug("Already on the first unit: current index = 0.")
            else:
                prev_unit = self._display_units[unit_idx - 1]
                logger.debug(f"Prev unit: left_page_index = {prev_unit.left_page_index}.")
                self._current_page_index = prev_unit.left_page_index
        elif self._current_page_index <= self._first_page_index:
            logger.debug("Already on the first page: current index = 0.")
        else:
            logger.debug(f"Prev page: requested index = {self._current_page_index - 1}")
            self._current_page_index -= 1

    def set_page_map(self, page_map: OrderedDict[str, PageInfo], page_to_first_goto: str) -> None:
        self.page_map = page_map
        assert self.page_map is not None
        self._index_to_page_map: dict[int, str] = {
            page_info.page_index: page_str for page_str, page_info in page_map.items()
        }

        self._first_page_to_read_index = (
            0
            if page_to_first_goto == COMIC_BEGIN_PAGE
            else self.page_map[page_to_first_goto].page_index
        )

        self._first_page_index = next(iter(self.page_map.values())).page_index
        self._last_page_index = next(reversed(self.page_map.values())).page_index

        assert self._first_page_index == 0
        assert (self._last_page_index + 1) == len(self.page_map)

        self._build_display_units(page_map)

    def _build_display_units(self, page_map: OrderedDict[str, PageInfo]) -> None:
        """Pre-compute display units for double-page mode from the page map."""
        pages = list(page_map.values())
        self._display_units = []
        self._page_index_to_unit_idx = {}

        i = 0
        while i < len(pages):
            if pages[i].is_solo or (i + 1 >= len(pages)) or pages[i + 1].is_solo:
                unit_idx = len(self._display_units)
                self._display_units.append(DisplayUnit(i, None))
                self._page_index_to_unit_idx[i] = unit_idx
                i += 1
            else:
                unit_idx = len(self._display_units)
                self._display_units.append(DisplayUnit(i, i + 1))
                self._page_index_to_unit_idx[i] = unit_idx
                self._page_index_to_unit_idx[i + 1] = unit_idx
                i += 2

    def get_image_load_order(self) -> list[str]:
        """Determine the optimal order to load images for a smooth user experience."""
        assert self.page_map is not None
        if self._first_page_to_read_index == 0:
            return list(self.page_map.keys())

        # Start with the current page
        image_load_order = [self._index_to_page_map[self._first_page_to_read_index]]

        # Then the previous page (for immediate back navigation).
        if self._first_page_to_read_index > 0:
            image_load_order.append(self._index_to_page_map[self._first_page_to_read_index - 1])

        # Then all subsequent pages.
        image_load_order.extend(
            self._index_to_page_map[page_index]
            for page_index in range(self._first_page_to_read_index + 1, self._last_page_index + 1)
        )

        # Finally, the rest of the previous pages in reverse order.
        image_load_order.extend(
            self._index_to_page_map[page_index]
            for page_index in range(self._first_page_to_read_index - 2, -1, -1)
        )

        return image_load_order


class ComicBookReader(FloatLayout):
    """Main layout for the comic reader."""

    # TODO: What happens if monitor changes??
    MAX_WINDOW_WIDTH = get_monitors()[0].width
    MAX_WINDOW_HEIGHT = get_monitors()[0].height

    # The window/action-bar title. A Kivy property so the screen can bind to it and
    # reflect per-page title changes (e.g. the "All One-Pagers" collection).
    action_bar_title = StringProperty()

    def __init__(
        self,
        reader_settings: ReaderSettings,
        font_manager: FontManager,
        on_comic_is_ready_to_read: Callable[[], None],
        toggle_action_bar_visibility: Callable[[], None],
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)

        self._reader_settings = reader_settings
        self._font_manager = font_manager
        self._on_comic_is_ready_to_read = on_comic_is_ready_to_read
        self._toggle_action_bar_visibility = toggle_action_bar_visibility
        self._goto_page_widget: Widget | None = None

        self._current_comic_path = ""
        self._current_title_str = ""
        self.action_bar_title = ""

        # When reading the "All One-Pagers" or "All Covers" collection, the window
        # title tracks the item on the current page (updated per page turn in
        # _show_page).
        self._is_one_pager_collection = False
        self._collection_one_pagers: list[Titles] = []
        self._is_covers_collection = False
        self._collection_covers: list[BarksCover] = []

        self._add_reader_widgets()

        self._comic_book_loader = ComicBookLoader(
            self._reader_settings,
            self._first_image_loaded,
            self._all_images_loaded,
            self._load_error,
            self.MAX_WINDOW_WIDTH,
            self.MAX_WINDOW_HEIGHT,
            scheduler=KivyClockScheduler(),
            cursor=KivyCursor(),
        )

        self._all_loaded = False
        self._closed = False
        # Kivy Clock handle for the "waiting for a not-yet-loaded page" poll, or
        # None when no page is currently being awaited. See _show_page.
        self._pending_poll_ev: ClockEvent | None = None
        self._goto_page_dropdown: DropDown | None = None
        self._goto_page_buttons: list[Button] = []

        # Bind property changes to update the display
        self._page_manager = _ComicPageManager(self._show_page)

        self._navigation = ReaderNavigation(self.MAX_WINDOW_WIDTH, 0.09)

        self._time_to_load_comic = Timing()

    def _add_reader_widgets(self) -> None:
        # Don't mess with this. Using CoreImage will result in a 25% slowdown.
        self._loading_page_texture = get_image_stream(
            self._reader_settings.sys_file_paths.get_empty_page_file()
        )

        self._comic_image = Image()
        self._comic_image.fit_mode = "contain"
        self._comic_image.mipmap = False
        self.add_widget(self._comic_image)

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
        return self._page_manager.page_map

    def get_last_read_page(self) -> str:
        return self._current_page_str

    def get_current_display_unit(self) -> DisplayUnit | None:
        """Return the current display unit (for double page mode awareness)."""
        return self._page_manager.get_current_display_unit()

    def is_click_in_top_margin(self, touch: MotionEvent) -> bool:
        x_rel = round(touch.x - self.x)
        y_rel = round(touch.y - self.y)
        return self._navigation.is_in_top_margin(x_rel, y_rel)

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

        x_rel = round(touch.x - self.x)
        y_rel = round(touch.y - self.y)

        if self._navigation.is_in_left_margin(x_rel, y_rel):
            logger.debug(f"Left margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            self._page_manager.prev_page()
            return True

        if self._navigation.is_in_right_margin(x_rel, y_rel):
            logger.debug(f"Right margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
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
        page_map: OrderedDict[str, PageInfo],
    ) -> None:
        assert (page_to_first_goto == COMIC_BEGIN_PAGE) or (page_to_first_goto in page_map)

        self._current_title_str = self.get_reader_comic_title(fanta_info)

        # For the collections the window title is per-page (set in _show_page); for
        # everything else it is the comic's title, set once here.
        self._is_one_pager_collection = is_one_pager_collection(fanta_info.comic_book_info.title)
        self._collection_one_pagers = (
            get_located_one_pagers() if self._is_one_pager_collection else []
        )
        self._is_covers_collection = is_covers_collection(fanta_info.comic_book_info.title)
        self._collection_covers = get_located_covers() if self._is_covers_collection else []

        self._stop_pending_poll()
        self._all_loaded = False
        self._goto_page_dropdown = None
        self._page_manager.reset_current_page_index()
        self.action_bar_title = get_action_bar_title(self._font_manager, self._current_title_str)

        # The collections are always single-page: each page is a separate gag or
        # cover, so a two-page spread would pair unrelated items.
        self._page_manager.double_page_mode = (
            False if self.is_single_page_only_collection else self._reader_settings.double_page_mode
        )
        self._page_manager.set_page_map(page_map, page_to_first_goto)

        self._time_to_load_comic.restart()

        archive_path, fanta_volume_archive = self._comic_book_loader.resolve_archive_for_comic(
            fanta_info, page_map
        )
        image_source = ArchivePageImageSource(
            archive_path=archive_path,
            fanta_volume_archive=fanta_volume_archive,
            comic_book_image_builder=comic_book_image_builder,
            empty_page_image=self._comic_book_loader.empty_page_image,
            use_fantagraphics_overrides=use_fantagraphics_overrides,
            max_width=self._comic_book_loader.max_window_width,
            max_height=self._comic_book_loader.max_window_height,
        )
        archive_desc = str(archive_path)
        self._comic_book_loader.set_comic(
            image_source,
            self._page_manager.get_image_load_order(),
            page_map,
            archive_desc=archive_desc,
        )

        self._closed = False

        self._on_comic_is_ready_to_read()
        Clock.schedule_once(lambda _dt: self._show_loading_page(), 0)

    @staticmethod
    def get_reader_comic_title(fanta_info: FantaComicBookInfo) -> str:
        if fanta_info.comic_book_info.is_barks_title:
            return fanta_info.comic_book_info.get_title_str()
        return fanta_info.comic_book_info.get_title_from_issue_name()

    def close_comic_book_reader(self) -> None:
        if self._closed:
            return

        self._stop_pending_poll()
        self._comic_book_loader.stop_now()
        self._comic_book_loader.close_comic()

    def reset_comic_book_reader(self) -> None:
        self._page_manager.reset_current_page_index()
        self._goto_page_dropdown = None
        self._goto_page_buttons.clear()
        self._closed = True

    def _first_image_loaded(self) -> None:
        self._page_manager.set_to_first_page_to_read()
        logger.debug(f"First image loaded: current page index = {self._current_page_index}.")

    def _all_images_loaded(self) -> None:
        self._all_loaded = True
        logger.info(
            f"All images loaded in {self._time_to_load_comic.get_elapsed_time_with_unit()}"
            f": current page index = {self._current_page_index}."
        )

    def _load_error(self, load_warning_only: bool) -> None:
        self._all_loaded = False
        if not load_warning_only:
            msg = "There was a comic book load error."
            raise RuntimeError(msg)
        self.close_comic_book_reader()

    def _show_loading_page(self) -> None:
        self._comic_image.texture = None  # Clear previous texture
        self._comic_image.source = ""  # Clear previous source
        self._comic_image.reload()  # Ensure reload if source was same BytesIO object
        self._comic_image.texture = self._loading_page_texture

    def _set_one_pager_action_bar_title(self, page_str: str) -> None:
        """Set the window title to the one-pager shown on the collection's *page_str*.

        Collection display pages are ``1..N`` in ``get_located_one_pagers()`` order,
        so page ``N`` maps to ``self._collection_one_pagers[N - 1]``.
        """
        try:
            one_pager = self._collection_one_pagers[int(page_str) - 1]
        except (ValueError, IndexError):
            return
        title = get_one_pager_display_title(one_pager)
        self.action_bar_title = get_action_bar_title(self._font_manager, title)

    def _set_cover_action_bar_title(self, page_str: str) -> None:
        """Set the window title to the cover shown on the collection's *page_str*.

        Collection display pages are ``1..N`` in ``get_located_covers()`` order,
        so page ``N`` maps to ``self._collection_covers[N - 1]``.
        """
        try:
            cover = self._collection_covers[int(page_str) - 1]
        except (ValueError, IndexError):
            return
        title = get_cover_display_title(cover)
        self.action_bar_title = get_action_bar_title(self._font_manager, title)

    def _show_page(self, _instance: Widget | None, _value: str | None) -> None:
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
            f"Displaying image {self._current_page_index}:"
            f" {self._comic_book_loader.get_image_info_str(page_str)}."
        )

        if self._is_one_pager_collection:
            self._set_one_pager_action_bar_title(page_str)
        elif self._is_covers_collection:
            self._set_cover_action_bar_title(page_str)

        left_idx, right_idx = self._get_current_display_indices()

        if self._pages_ready(left_idx, right_idx):
            self._render_page(left_idx, right_idx)
            return

        # Page not loaded yet: give feedback and wait without blocking the UI thread.
        logger.info(f"Page index {self._current_page_index} not loaded yet; showing loading page.")
        self._show_loading_page()
        self._comic_book_loader.cursor.set_busy()
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
            self._comic_book_loader.prioritize_page(idx)

    def _start_pending_poll(self) -> None:
        """Start (once) the Clock poll that renders a page as soon as it loads."""
        if self._pending_poll_ev is None:
            self._pending_poll_ev = Clock.schedule_interval(
                self._poll_pending_page, PENDING_PAGE_POLL_INTERVAL_SECS
            )

    def _stop_pending_poll(self) -> None:
        """Cancel the pending-page poll (if any) and restore the normal cursor."""
        if self._pending_poll_ev is not None:
            self._pending_poll_ev.cancel()
            self._pending_poll_ev = None
            self._comic_book_loader.cursor.set_normal()

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
            # Kivy Image widget can load from BytesIO
            self._comic_image.texture = None  # Clear previous texture
            self._comic_image.source = ""  # Clear previous source
            self._comic_image.reload()  # Ensure reload if source was same BytesIO object

            if right_page_index is not None:
                image_stream, image_ext = (
                    self._comic_book_loader.get_double_page_image_ready_for_reading(
                        left_page_index, right_page_index
                    )
                )
            else:
                image_stream, image_ext = self._comic_book_loader.get_image_ready_for_reading(
                    left_page_index
                )
            self._comic_image.texture = CoreImage(image_stream, ext=image_ext).texture
        except Exception:  # noqa: BLE001
            logger.exception(f"Error displaying image with index {self._current_page_index}: ")
            # Optionally display a placeholder image or error message

        logger.info(
            f"Showed page {self._current_page_index} in {timing.get_elapsed_time_with_unit()}."
        )

    def _hide_action_bar_if_fullscreen(self) -> None:
        if WindowManager.is_fullscreen_now():
            self._toggle_action_bar_visibility()

    def goto_start_page(self) -> None:
        self._page_manager.goto_start_page()
        self._hide_action_bar_if_fullscreen()

    def goto_last_page(self) -> None:
        self._page_manager.goto_last_page()
        self._hide_action_bar_if_fullscreen()

    @property
    def double_page_mode(self) -> bool:
        """Return the current active double-page mode (not the config setting)."""
        return self._page_manager.double_page_mode

    @property
    def is_one_pager_collection(self) -> bool:
        """Whether the comic currently being read is the All One-Pagers collection."""
        return self._is_one_pager_collection

    @property
    def is_single_page_only_collection(self) -> bool:
        """Whether the current comic is a collection that is always single-page."""
        return self._is_one_pager_collection or self._is_covers_collection

    def next_page(self) -> None:
        self._page_manager.next_page()

    def prev_page(self) -> None:
        self._page_manager.prev_page()

    def toggle_double_page_mode(self) -> None:
        """Toggle double-page mode on/off for the current comic only (does not change config)."""
        if self.is_single_page_only_collection:
            # The collections are always single-page - ignore the toggle.
            return
        self._page_manager.double_page_mode = not self._page_manager.double_page_mode
        self._show_page(None, None)

    def goto_page(self) -> None:
        """Go to user requested page."""
        if not self._goto_page_dropdown:
            self._create_goto_page_dropdown()
            assert self._goto_page_dropdown

        selected_button = None
        # Update button colors to highlight the current page before opening
        for button in self._goto_page_buttons:
            page_info = self._page_map[button.text]
            if page_info.page_index == self._current_page_index:
                button.background_color = GOTO_PAGE_BUTTON_CURRENT_PAGE_COLOR
                selected_button = button
            else:
                button.background_color = (
                    GOTO_PAGE_BUTTON_BODY_COLOR
                    if page_info.page_type == PageType.BODY
                    else GOTO_PAGE_BUTTON_NONBODY_COLOR
                )

        self._goto_page_dropdown.open(self._goto_page_widget)
        if selected_button:
            self._goto_page_dropdown.scroll_to(selected_button)

    def on_page_selected(self, _instance: Widget, page: str) -> None:
        self._page_manager.set_current_page_index_from_str(page)
        self._hide_action_bar_if_fullscreen()

    def open_goto_page_for_keyboard(self, on_dismiss: Callable) -> int:
        """Open the goto-page dropdown for keyboard nav. Returns focused button index."""
        self.goto_page()
        if self._goto_page_dropdown:
            self._goto_page_dropdown.bind(on_dismiss=on_dismiss)
        for i, btn in enumerate(self._goto_page_buttons):
            if self._page_map[btn.text].page_index == self._current_page_index:
                return i
        return 0

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
        max_dropdown_height = round(GOTO_PAGE_DROPDOWN_FRAC_OF_HEIGHT * self.height)
        logger.debug(f"Creating goto page dropdown. max_dropdown_height = {max_dropdown_height}.")

        self._goto_page_dropdown = DropDown(
            auto_dismiss=True,
            dismiss_on_select=True,
            on_select=self.on_page_selected,
            max_height=max_dropdown_height,
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


class ComicBookReaderScreen(ReaderScreen, DropdownNavMixin, ActionBarNavMixin):
    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
    # Opacity for an action-bar button that is greyed out (e.g. the double-page
    # toggle while reading the single-page-only one-pager collection).
    _GREYED_BUTTON_OPACITY = 0.4
    action_bar_title = StringProperty()
    # Width of the inner action bar (centered to match the comic image's aspect-fit width).
    action_bar_width = NumericProperty(1)  # must be non-zero for initial build
    app_icon_filepath = StringProperty()
    is_fullscreen = BooleanProperty(defaultvalue=False)

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
        self._reset_action_bar_width()

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
        self.ids.image_layout.add_widget(self.comic_book_reader)

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

    def _open_goto_page_for_keyboard(self) -> None:
        self._clear_menu_focus()
        focused_idx = self.comic_book_reader.open_goto_page_for_keyboard(
            self._on_goto_page_dropdown_dismissed
        )
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

    # In fullscreen with the action bar hidden, a click in the top margin reveals the bar.
    # When the action bar is visible, top-region clicks pass through to the action bar buttons
    # (which sit naturally above the image area thanks to the BoxLayout reflow).
    @override
    def on_touch_down(self, touch: MotionEvent) -> bool:
        self._clear_menu_on_touch()

        if super().on_touch_down(touch):
            # Another button has been pressed.
            return True

        if self._is_action_bar_hidden() and self.comic_book_reader.is_click_in_top_margin(touch):
            logger.debug("Showing action bar on top margin press.")
            self._show_action_bar()
            return True

        return False

    def _on_comic_is_ready_to_read(self) -> None:
        self._on_comic_is_ready_to_read_func()
        self.action_bar_title = self.comic_book_reader.action_bar_title
        self._sync_double_page_button()

    def _on_key_down(
        self, _window: WindowBase, key: int, _scancode: int, _codepoint: str, _modifier: list[str]
    ) -> bool:
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

    def _set_hints_for_windowed_mode(self) -> None:
        # Restore the layout properties so the screen fills the window again.
        self.size_hint = (1, 1)
        self.pos_hint = {"center_x": 0.5, "center_y": 0.5}

    def _on_finished_goto_windowed_mode(self) -> None:
        if self._is_closing:
            logger.debug("Entering windowed mode finished, now closing reader.")
            self._finish_closing_comic()

        self.is_fullscreen = False
        self._update_widget_states()
        self._update_fullscreen_button()
        logger.info("Entered windowed mode on ComicBookReaderScreen.")

    def _exit_fullscreen(self) -> None:
        # Both branches delegate unconditionally: when the window is already in
        # the target mode the manager skips the transition but still fires the
        # finish callback, so the closing logic in the callbacks runs on the
        # same single completion path either way.
        if self._was_fullscreen_on_entry:
            logger.debug("Fullscreen is required.")
            self._mode.goto_fullscreen()
        else:
            logger.debug("Fullscreen not required.")
            self._mode.goto_windowed()

    def _on_finished_goto_fullscreen_mode(self) -> None:
        is_fullscreen_now = bool(WindowManager.is_fullscreen_now())
        if not is_fullscreen_now:
            logger.error(
                f"Finishing goto fullscreen on ComicBookReaderScreen but Window fullscreen"
                f" = '{WindowManager.get_screen_mode_now()}'. "
            )

        # The actual mode, not an assumed True: if the transition failed, the
        # button and action-bar state must keep matching the real window.
        self.is_fullscreen = is_fullscreen_now
        self._update_widget_states()
        self._update_fullscreen_button()

        logger.info("Entered fullscreen mode on ComicBookReaderScreen.")

        if self._is_closing:
            logger.debug("Entering fullscreen mode finished, now closing reader.")
            self._finish_closing_comic()

    def _finish_closing_comic(self) -> None:
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

    def _reset_action_bar_width(self) -> None:
        # Match the inner action bar's width to the comic image's aspect-fit width so it
        # spans only the visible image area, not the full monitor width in fullscreen.
        w, _ = get_win_dimensions(Window.height - ACTION_BAR_SIZE_Y, Window.width)
        self.action_bar_width = max(1, w)

    def _show_action_bar(self) -> None:
        """Show the action bar if currently hidden. No-op if already visible."""
        if not is_action_bar_visible(self._action_bar):
            set_action_bar_visibility(self._action_bar, ActionBarVisibility.VISIBLE)

    def _hide_action_bar(self) -> None:
        """Hide the action bar if currently visible. No-op if already hidden."""
        if is_action_bar_visible(self._action_bar):
            set_action_bar_visibility(self._action_bar, ActionBarVisibility.HIDDEN)

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
) -> ReaderScreen:
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


def get_image_stream(file: PanelPath) -> Texture:
    if isinstance(file, Path):
        return CoreImage(str(file)).texture

    zip_bytes = file.read_bytes()
    image_stream = io.BytesIO(zip_bytes)
    image_stream.seek(0)
    return CoreImage(image_stream, ext=PNG_EXT_FOR_KIVY).texture
