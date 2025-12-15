from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from barks_fantagraphics.comics_consts import PageType
from comic_utils.timing import Timing
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
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

from barks_reader.comic_book_loader import ComicBookLoader
from barks_reader.platform_utils import WindowManager
from barks_reader.reader_consts_and_types import CLOSE_TO_ZERO, COMIC_BEGIN_PAGE
from barks_reader.reader_formatter import get_action_bar_title
from barks_reader.reader_screens import ReaderScreen
from barks_reader.reader_ui_classes import ACTION_BAR_SIZE_Y
from barks_reader.reader_utils import get_image_stream, get_win_width_from_height

if TYPE_CHECKING:
    from collections import OrderedDict
    from collections.abc import Callable

    from barks_build_comic_images.build_comic_images import ComicBookImageBuilder
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from kivy.input import MotionEvent
    from kivy.uix.widget import Widget

    from barks_reader.comic_book_page_info import PageInfo
    from barks_reader.font_manager import FontManager
    from barks_reader.reader_settings import ReaderSettings

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

        # noinspection PyTypeHints
        # Reason: inspection seems broken here.
        self.page_map: OrderedDict[str, PageInfo] | None = None
        self._index_to_page_map: dict[int, str] = {}
        self._first_page_to_read_index = -1

        self._first_page_index = -1
        self._last_page_index = -1

    def get_current_page_index(self) -> int:
        return self._current_page_index

    def reset_current_page_index(self) -> None:
        self._current_page_index = -1

    def get_current_page_str(self) -> str:
        return self._index_to_page_map.get(self._current_page_index, "")

    def set_current_page_index_from_str(self, page_str: str) -> None:
        self._current_page_index = self.page_map[page_str].page_index

    def set_to_first_page_to_read(self) -> None:
        self._current_page_index = self._first_page_to_read_index

    def goto_start_page(self) -> None:
        if self._current_page_index == self._first_page_index:
            logger.debug(f"Already on the first page: current index = {self._current_page_index}.")
        else:
            logger.debug("Goto start page: requested index = 0.")
            self._current_page_index = self._first_page_index

    def goto_last_page(self) -> None:
        if self._current_page_index == self._last_page_index:
            logger.debug(f"Already on the last page: current index = {self._current_page_index}.")
        else:
            logger.debug(f"Last page: requested index = {self._last_page_index}.")
            self._current_page_index = self._last_page_index

    def next_page(self) -> None:
        if self._current_page_index >= self._last_page_index:
            logger.debug(f"Already on the last page: current index = {self._current_page_index}.")
        else:
            logger.debug(f"Next page: requested index = {self._current_page_index + 1}")
            self._current_page_index += 1

    def prev_page(self) -> None:
        if self._current_page_index <= self._first_page_index:
            logger.debug("Already on the first page: current index = 0.")
        else:
            logger.debug(f"Prev page: requested index = {self._current_page_index - 1}")
            self._current_page_index -= 1

    def set_page_map(self, page_map: OrderedDict[str, PageInfo], page_to_first_goto: str) -> None:
        self.page_map = page_map
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

    def get_image_load_order(self) -> list[str]:
        """Determine the optimal order to load images for a smooth user experience."""
        image_load_order = []
        page_to_first_goto = self._index_to_page_map[self._first_page_to_read_index]

        if self._first_page_to_read_index == 0:
            image_load_order.extend(self.page_map.keys())
            return image_load_order

        image_load_order.append(page_to_first_goto)
        prev_page = self._index_to_page_map[self._first_page_to_read_index - 1]
        image_load_order.append(prev_page)

        for page_index in range(self._first_page_to_read_index + 1, self._last_page_index + 1):
            page = self._index_to_page_map[page_index]
            image_load_order.append(page)

        for page_index in range(self._first_page_to_read_index - 2, -1, -1):
            page = self._index_to_page_map[page_index]
            image_load_order.append(page)

        return image_load_order


class ComicBookReader(FloatLayout):
    """Main layout for the comic reader."""

    MAX_WINDOW_WIDTH = get_monitors()[0].width
    MAX_WINDOW_HEIGHT = get_monitors()[0].height

    def __init__(
        self,
        reader_settings: ReaderSettings,
        font_manager: FontManager,
        on_comic_is_ready_to_read: Callable[[], None],
        on_toggle_action_bar_visibility: Callable[[], None],
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)

        self._reader_settings = reader_settings
        self._font_manager = font_manager
        self._on_comic_is_ready_to_read = on_comic_is_ready_to_read
        self._on_toggle_action_bar_visibility = on_toggle_action_bar_visibility
        self._goto_page_widget: Widget | None = None

        self._current_comic_path = ""
        self._current_title_str = ""
        self.action_bar_title = ""

        self._add_reader_widgets()

        self._comic_book_loader = ComicBookLoader(
            self._reader_settings,
            self._first_image_loaded,
            self._all_images_loaded,
            self._load_error,
            self.MAX_WINDOW_WIDTH,
            self.MAX_WINDOW_HEIGHT,
        )

        self._all_loaded = False
        self._closed = False
        self._goto_page_dropdown: DropDown | None = None

        # Bind property changes to update the display
        self._page_manager = _ComicPageManager(self._show_page)

        self._x_mid = -1
        self._y_top_margin = -1
        self._fullscreen_left_margin = -1
        self._fullscreen_right_margin = -1

        self._time_to_load_comic = Timing()

    # noinspection PyNoneFunctionAssignment
    def _add_reader_widgets(self) -> None:
        self._loading_page_image = get_image_stream(
            self._reader_settings.sys_file_paths.get_empty_page_file()
        )

        self._comic_image = Image()
        self._comic_image.fit_mode = "contain"
        self._comic_image.mipmap = False
        self.add_widget(self._comic_image)

    def set_goto_page_widget(self, goto_page_widget: Widget) -> None:
        self._goto_page_widget = goto_page_widget

    def set_reader_navigation_regions(self, width: int, height: int) -> None:
        self._x_mid = round(width / 2 - self.x)
        self._y_top_margin = round(height - self.y - (0.09 * height))
        logger.debug(
            f"Reader navigation: x_mid = {self._x_mid}, y_top_margin = {self._y_top_margin}."
        )

        self._fullscreen_left_margin = round(self.MAX_WINDOW_WIDTH / 4.0)
        self._fullscreen_right_margin = self.MAX_WINDOW_WIDTH - self._fullscreen_left_margin
        logger.debug(
            f"Reader navigation:"
            f" fullscreen_left_margin = {self._fullscreen_left_margin},"
            f" fullscreen_right_margin = {self._fullscreen_right_margin}."
        )

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

    @override
    def on_touch_down(self, touch: MotionEvent) -> bool:
        logger.debug(
            f"Touch down event: self.x,self.y = {self.x},{self.y},"
            f" touch.x,touch.y = {round(touch.x)},{round(touch.y)},"
            f" width = {round(self.width)}, height = {round(self.height)}."
            f" x_mid = {self._x_mid}, y_top_margin = {self._y_top_margin}."
        )

        x_rel = round(touch.x - self.x)
        y_rel = round(touch.y - self.y)

        if self._is_in_top_margin(x_rel, y_rel):
            logger.debug(f"Top margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            if WindowManager.is_fullscreen_now():
                self._on_toggle_action_bar_visibility()
        elif self._is_in_left_margin(x_rel, y_rel):
            logger.debug(f"Left margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            self._page_manager.prev_page()
        elif self._is_in_right_margin(x_rel, y_rel):
            logger.debug(f"Right margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            self._page_manager.next_page()
        else:
            logger.debug(
                f"Dead zone: x_rel,y_rel = {x_rel},{y_rel},"
                f" Screen mode = {WindowManager.get_screen_mode_now()}."
            )

        return super().on_touch_down(touch)

    def _is_in_top_margin(self, x: int, y: int) -> bool:
        if y <= self._y_top_margin:
            return False

        if not WindowManager.is_fullscreen_now():
            return True

        return self._fullscreen_left_margin < x <= self._fullscreen_right_margin

    def _is_in_left_margin(self, x: int, y: int) -> bool:
        return (x < self._x_mid) and (y <= self._y_top_margin)

    def _is_in_right_margin(self, x: int, y: int) -> bool:
        return (x >= self._x_mid) and (y <= self._y_top_margin)

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

        self._current_title_str = fanta_info.comic_book_info.get_title_str()

        self._all_loaded = False
        self._goto_page_dropdown = None
        self._page_manager.reset_current_page_index()
        self.action_bar_title = get_action_bar_title(self._font_manager, self._current_title_str)

        self._page_manager.set_page_map(page_map, page_to_first_goto)

        self._time_to_load_comic.restart()

        self._comic_book_loader.set_comic(
            fanta_info,
            use_fantagraphics_overrides,
            comic_book_image_builder,
            self._page_manager.get_image_load_order(),
            page_map,
        )

        self._closed = False

        self._on_comic_is_ready_to_read()
        Clock.schedule_once(lambda _dt: self._show_loading_page(), 0)

    def close_comic_book_reader(self) -> None:
        if self._closed:
            return

        self._comic_book_loader.stop_now()
        self._wait_for_image_to_load()
        self._comic_book_loader.close_comic()

    def reset_comic_book_reader(self) -> None:
        self._page_manager.reset_current_page_index()
        self._goto_page_dropdown = None
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
        self._comic_image.texture = self._loading_page_image

    def _show_page(self, _instance: Widget, _value: str) -> None:
        """Display the image for the current_page_index."""
        if self._current_page_index == -1:
            logger.debug("Show page not ready: current_page_index = -1.")
            return

        page_str = self._current_page_str
        logger.debug(
            f"Displaying image {self._current_page_index}:"
            f" {self._comic_book_loader.get_image_info_str(page_str)}."
        )

        self._wait_for_image_to_load()

        # noinspection PyBroadException
        try:
            # Kivy Image widget can load from BytesIO
            self._comic_image.texture = None  # Clear previous texture
            self._comic_image.source = ""  # Clear previous source
            self._comic_image.reload()  # Ensure reload if source was same BytesIO object

            image_stream, image_ext = self._comic_book_loader.get_image_ready_for_reading(
                self._current_page_index
            )
            self._comic_image.texture = CoreImage(image_stream, ext=image_ext).texture
        except Exception:  # noqa: BLE001
            logger.exception(f"Error displaying image with index {self._current_page_index}: ")
            # Optionally display a placeholder image or error message

    def goto_start_page(self) -> None:
        self._page_manager.goto_start_page()

    def goto_last_page(self) -> None:
        self._page_manager.goto_last_page()

    def _wait_for_image_to_load(self) -> None:
        if self._all_loaded:
            return

        logger.info(f"Waiting for image with index {self._current_page_index} to finish loading.")
        while not self._comic_book_loader.wait_load_event(self._current_page_index, 2):
            logger.info(
                f"Still waiting for image with index {self._current_page_index} to finish loading."
            )
        logger.info(f"Finished waiting for image with index {self._current_page_index} to load.")

    def goto_page(self) -> None:
        """Go to user requested page."""
        if not self._goto_page_dropdown:
            self._create_goto_page_dropdown()
            assert self._goto_page_dropdown

        selected_button = None
        # Update button colors to highlight the current page before opening
        # noinspection PyUnresolvedReferences
        # Reason: inspection seems broken here.
        for button in self._goto_page_dropdown.children[0].children:
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

        # noinspection PyUnresolvedReferences
        # Reason: inspection seems broken here.
        self._goto_page_dropdown.open(self._goto_page_widget)
        if selected_button:
            # noinspection PyUnresolvedReferences
            # Reason: inspection seems broken here.
            self._goto_page_dropdown.scroll_to(selected_button)

    def on_page_selected(self, _instance: Widget, page: str) -> None:
        self._page_manager.set_current_page_index_from_str(page)

    def _create_goto_page_dropdown(self) -> None:
        max_dropdown_height = round(GOTO_PAGE_DROPDOWN_FRAC_OF_HEIGHT * self.height)
        logger.debug(f"Creating goto page dropdown. max_dropdown_height = {max_dropdown_height}.")

        self._goto_page_dropdown = DropDown(
            auto_dismiss=True,
            dismiss_on_select=True,
            on_select=self.on_page_selected,
            max_height=max_dropdown_height,
        )

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


class ComicBookReaderScreen(ReaderScreen):
    ACTION_BAR_TITLE_COLOR = (0.0, 1.0, 0.0, 1.0)
    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
    action_bar_title = StringProperty()
    action_bar_width = NumericProperty(1)  # must be non-zero for initial build
    app_icon_filepath = StringProperty()
    is_fullscreen = BooleanProperty(defaultvalue=False)

    def __init__(
        self,
        reader_settings: ReaderSettings,
        reader_app_icon_file: str,
        font_manager: FontManager,
        on_comic_is_ready_to_read_func: Callable[[], None],
        on_close_reader_func: Callable[[], None],
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)

        self._reader_settings = reader_settings
        self.app_icon_filepath = reader_app_icon_file
        self._on_comic_is_ready_to_read_func = on_comic_is_ready_to_read_func
        self._on_close_reader = on_close_reader_func
        self._active = False

        self._window_manager = WindowManager(
            ComicBookReaderScreen.__name__,
            self._set_hints_for_windowed_mode,
            self._on_finished_goto_windowed_mode,
            self._on_finished_goto_fullscreen_mode,
        )

        self._action_bar = self.ids.action_bar
        self._action_bar_fullscreen_icon = str(
            self._reader_settings.sys_file_paths.get_barks_reader_fullscreen_icon_file()
        )
        self._action_bar_fullscreen_exit_icon = str(
            self._reader_settings.sys_file_paths.get_barks_reader_fullscreen_exit_icon_file()
        )
        self.action_bar_width = self.width

        self._was_fullscreen_on_entry = False
        self._fullscreen_button = self.ids.fullscreen_button
        self._is_closing = False

        self._resize_binding()

        self.comic_book_reader = ComicBookReader(
            self._reader_settings,
            font_manager,
            self._on_comic_is_ready_to_read,
            self._toggle_action_bar_visibility,
        )
        self.comic_book_reader.set_goto_page_widget(self.ids.goto_page_button)
        self.ids.image_layout.add_widget(self.comic_book_reader)

    def is_active(self, active: bool) -> None:
        logger.info(f"ComicBookReaderScreen active changed from {self._active} to {active}.")

        self._active = active

        if not self._active:
            self._was_fullscreen_on_entry = False
            self.is_fullscreen = False
            return

        self.update_window_mode()
        self._update_window_state()
        self._update_widget_states()

        logger.debug(
            f"Screen mode = {WindowManager.get_screen_mode_now()},"
            f" self._was_fullscreen_on_entry = {self._was_fullscreen_on_entry}."
            f" self.goto_fullscreen_on_comic_read"
            f" = {self._reader_settings.goto_fullscreen_on_comic_read}."
            f" self.is_fullscreen = {self.is_fullscreen}."
            f" self._action_bar.width = {self._action_bar.width}."
            f" self._action_bar.opacity = {self._action_bar.opacity}."
        )

    def _on_comic_is_ready_to_read(self) -> None:
        self._on_comic_is_ready_to_read_func()
        self.action_bar_title = self.comic_book_reader.action_bar_title

    def close_comic_book_reader(self) -> None:
        self._is_closing = True
        self.comic_book_reader.close_comic_book_reader()
        self._exit_fullscreen()

    def clear_window_state(self) -> None:
        self._window_manager.clear_state()

    def save_window_state_now(self) -> None:
        self._window_manager.save_state_now()

    def update_window_mode(self) -> None:
        self._was_fullscreen_on_entry = WindowManager.is_fullscreen_now()
        if (
            not self._was_fullscreen_on_entry
            and self._reader_settings.goto_fullscreen_on_comic_read
        ):
            self._goto_fullscreen_mode()
        self.is_fullscreen = (
            self._was_fullscreen_on_entry or self._reader_settings.goto_fullscreen_on_comic_read
        )

    def toggle_screen_mode(self) -> None:
        if WindowManager.is_fullscreen_now():
            logger.info("Toggle screen mode to windowed mode.")
            Clock.schedule_once(lambda _dt: self._goto_windowed_mode(), 0)
        else:
            logger.info("Toggle screen mode to fullscreen mode.")
            Clock.schedule_once(lambda _dt: self._goto_fullscreen_mode(), 0)

    def _goto_windowed_mode(self) -> None:
        logger.info("Exiting fullscreen mode on ComicBookReaderScreen.")

        self._window_manager.goto_windowed_mode()

    def _set_hints_for_windowed_mode(self) -> None:
        # Restore the layout properties so the screen fills the window again.
        self.size_hint = (1, 1)
        self.pos_hint = {"center_x": 0.5, "center_y": 0.5}

    def _on_finished_goto_windowed_mode(self) -> None:
        if self._is_closing:
            logger.debug("Entering windowed mode finished, now closing reader.")
            self._finish_closing_comic()

        self.is_fullscreen = False
        self._update_fullscreen_button()
        logger.info("Entered windowed mode on ComicBookReaderScreen.")

    def _goto_fullscreen_mode(self) -> None:
        logger.info("Entering fullscreen mode on ComicBookReaderScreen.")
        self._window_manager.goto_fullscreen_mode()

    def _exit_fullscreen(self) -> None:
        if not WindowManager.is_fullscreen_now() and not self._was_fullscreen_on_entry:
            logger.debug("Fullscreen not on and not required.")
            self._on_finished_goto_windowed_mode()
            return

        if self._was_fullscreen_on_entry:
            logger.debug("Fullscreen is required.")
            self._goto_fullscreen_mode()
        else:
            logger.debug("Fullscreen not required.")
            self._goto_windowed_mode()

    def _on_finished_goto_fullscreen_mode(self) -> None:
        if not WindowManager.is_fullscreen_now():
            logger.error(
                f"Finishing goto fullscreen on ComicBookReaderScreen but Window fullscreen"
                f" = '{WindowManager.get_screen_mode_now()}'. "
            )
        if self.height < Window.height:
            logger.info(
                f"Finishing goto fullscreen on ComicBookReaderScreen but self.height"
                f" = {self.height} < Window.height = {Window.height} = Window.height."
            )
            self.height = Window.height
            logger.info(f"New height too low: adjusted new fullscreen height = {self.height}.")

        self.is_fullscreen = True
        self._update_fullscreen_button()

        self.height = max(self.height, Window.height)

        logger.info("Entered fullscreen mode on ComicBookReaderScreen.")

        if self._is_closing:
            logger.debug("Entering fullscreen mode finished, now closing reader.")
            self._finish_closing_comic()

    def _finish_closing_comic(self) -> None:
        self._on_close_reader()
        self._is_closing = False
        self.comic_book_reader.reset_comic_book_reader()

    # noinspection PyTypeHints
    # Reason: inspection seems broken here.
    def _on_window_resize(self, _window: Window, width: int, height: int) -> None:
        if not self._active:
            return

        if WindowManager.is_fullscreen_now():
            self.size = get_win_width_from_height(height - ACTION_BAR_SIZE_Y), height

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
        self.action_bar_width = max(0, get_win_width_from_height(Window.height - ACTION_BAR_SIZE_Y))
        logger.debug(f"self.action_bar_width = {self.action_bar_width}")

    def _toggle_action_bar_visibility(self) -> None:
        logger.debug(f"Toggling action bar visibility. Current opacity: {self._action_bar.opacity}")
        # Toggle the opacity. The .kv file handles the rest.
        self._action_bar.opacity = 1.0 if self._action_bar.opacity < CLOSE_TO_ZERO else 0.0

    def _update_widget_states(self) -> None:
        if self.is_fullscreen:
            self._action_bar.opacity = 0
        else:
            self._action_bar.opacity = 1

        self._update_fullscreen_button()

    def _update_fullscreen_button(self) -> None:
        if self.is_fullscreen:
            self._fullscreen_button.text = "Windowed"
            self._fullscreen_button.icon = self._action_bar_fullscreen_exit_icon
        else:
            self._fullscreen_button.text = "Fullscreen"
            self._fullscreen_button.icon = self._action_bar_fullscreen_icon


def get_barks_comic_reader_screen(
    screen_name: str,
    reader_settings: ReaderSettings,
    reader_app_icon_file: str,
    font_manager: FontManager,
    on_comic_is_ready_to_read: Callable[[], None],
    on_close_reader: Callable[[], None],
) -> ReaderScreen:
    Builder.load_file(str(COMIC_BOOK_READER_KV_FILE))

    return ComicBookReaderScreen(
        reader_settings,
        reader_app_icon_file,
        font_manager,
        on_comic_is_ready_to_read,
        on_close_reader,
        name=screen_name,
    )
