from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from barks_fantagraphics.comics_consts import PageType
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.event import EventDispatcher
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.image import Image
from kivy.uix.screenmanager import Screen
from screeninfo import get_monitors

from comic_book_loader import ComicBookLoader
from reader_consts_and_types import ACTION_BAR_SIZE_Y
from reader_formatter import get_action_bar_title

if TYPE_CHECKING:
    from collections import OrderedDict

    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from build_comic_images import ComicBookImageBuilder
    from kivy.input import MotionEvent
    from kivy.uix.actionbar import ActionBar, ActionButton
    from kivy.uix.widget import Widget

    from comic_book_page_info import PageInfo
    from font_manager import FontManager
    from reader_settings import ReaderSettings
    from system_file_paths import SystemFilePaths

GOTO_PAGE_DROPDOWN_FRAC_OF_HEIGHT = 0.97
GOTO_PAGE_BUTTON_HEIGHT = dp(25)
GOTO_PAGE_BUTTON_BODY_COLOR = (0, 1, 1, 1)
GOTO_PAGE_BUTTON_NONBODY_COLOR = (0, 0.5, 0.5, 1)
GOTO_PAGE_BUTTON_CURRENT_PAGE_COLOR = (1, 1, 0, 1)


class _ComicPageManager(EventDispatcher):
    """Manages the state and navigation logic for a comic book's pages."""

    _current_page_index = NumericProperty(-1)

    def __init__(
        self, current_page_index_bound_func: Callable, *args, **kwargs  # noqa: ANN002, ANN003
    ) -> None:
        super().__init__(*args, **kwargs)

        self.bind(_current_page_index=current_page_index_bound_func)

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
            logging.debug(f"Already on the first page: current index = {self._current_page_index}.")
        else:
            logging.debug("Goto start page: requested index = 0.")
            self._current_page_index = self._first_page_index

    def goto_last_page(self) -> None:
        if self._current_page_index == self._last_page_index:
            logging.debug(f"Already on the last page: current index = {self._current_page_index}.")
        else:
            logging.debug(f"Last page: requested index = {self._last_page_index}.")
            self._current_page_index = self._last_page_index

    def next_page(self) -> None:
        if self._current_page_index >= self._last_page_index:
            logging.debug(f"Already on the last page: current index = {self._current_page_index}.")
        else:
            logging.debug(f"Next page: requested index = {self._current_page_index + 1}")
            self._current_page_index += 1

    def prev_page(self) -> None:
        if self._current_page_index <= self._first_page_index:
            logging.debug("Already on the first page: current index = 0.")
        else:
            logging.debug(f"Prev page: requested index = {self._current_page_index - 1}")
            self._current_page_index -= 1

    def set_page_map(self, page_map: OrderedDict[str, PageInfo], page_to_first_goto: str) -> None:
        self.page_map = page_map
        self._index_to_page_map: dict[int, str] = {
            page_info.page_index: page_str for page_str, page_info in page_map.items()
        }
        self._first_page_to_read_index = self.page_map[page_to_first_goto].page_index

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


class ComicBookReader(BoxLayout):
    """Main layout for the comic reader."""

    MAX_WINDOW_WIDTH = get_monitors()[0].width
    MAX_WINDOW_HEIGHT = get_monitors()[0].height

    def __init__(
        self,
        root: ComicBookReaderScreen,
        reader_settings: ReaderSettings,
        font_manager: FontManager,
        on_comic_is_ready_to_read: Callable[[], None],
        on_close_reader: Callable[[], None],
        goto_page_widget: Widget,
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)

        self._root = root
        self._reader_settings = reader_settings
        self._font_manager = font_manager
        self._on_comic_is_ready_to_read = on_comic_is_ready_to_read
        self._on_close_reader = on_close_reader
        self._goto_page_widget = goto_page_widget

        self._action_bar = None
        self._action_bar_fullscreen_icon = (
            self._reader_settings.sys_file_paths.get_barks_reader_fullscreen_icon_file()
        )
        self._action_bar_fullscreen_exit_icon = (
            self._reader_settings.sys_file_paths.get_barks_reader_fullscreen_exit_icon_file()
        )
        self._current_comic_path = ""

        self.orientation = "vertical"
        self._comic_image = Image()
        self._comic_image.fit_mode = "contain"
        self._comic_image.mipmap = False
        self.add_widget(self._comic_image)

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

        Window.bind(on_resize=self._on_window_resize)

    def _on_window_resize(self, _window: Window, width: int, height: int) -> None:
        self._x_mid = round(width / 2 - self.x)
        self._y_top_margin = round(height - self.y - (0.09 * height))

        logging.debug(
            f"Comic reader window resize event: x,y = {self.x},{self.y},"
            f" width = {width}, height = {height},"
            f" self.width = {self.width}, self.height = {self.height}."
        )
        logging.debug(
            f"Comic reader window resize event:"
            f" x_mid = {self._x_mid}, y_top_margin = {self._y_top_margin}."
        )

        self._fullscreen_left_margin = round(self.MAX_WINDOW_WIDTH / 4.0)
        self._fullscreen_right_margin = self.MAX_WINDOW_WIDTH - self._fullscreen_left_margin
        logging.debug(
            f"Comic reader window resize event:"
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

    def set_action_bar(self, action_bar: ActionBar) -> None:
        self._action_bar = action_bar

    def on_touch_down(self, touch: MotionEvent) -> bool:
        logging.debug(
            f"Touch down event: self.x,self.y = {self.x},{self.y},"
            f" touch.x,touch.y = {round(touch.x)},{round(touch.y)},"
            f" width = {round(self.width)}, height = {round(self.height)}."
            f" x_mid = {self._x_mid}, y_top_margin = {self._y_top_margin}."
        )

        x_rel = round(touch.x - self.x)
        y_rel = round(touch.y - self.y)

        if self._is_in_top_margin(x_rel, y_rel):
            logging.debug(f"Top margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            if Window.fullscreen:
                self._toggle_action_bar()
        elif self._is_in_left_margin(x_rel, y_rel):
            logging.debug(f"Left margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            self._prev_page(None)
        elif self._is_in_right_margin(x_rel, y_rel):
            logging.debug(f"Right margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            self._next_page(None)
        else:
            logging.debug(
                f"Dead zone: x_rel,y_rel = {x_rel},{y_rel},"
                f" Windows.fullscreen = {Window.fullscreen}."
            )

        return super().on_touch_down(touch)

    def _is_in_top_margin(self, x: int, y: int) -> bool:
        if y <= self._y_top_margin:
            return False

        if not Window.fullscreen:
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
        assert page_to_first_goto in page_map

        self._all_loaded = False
        self._goto_page_dropdown = None
        self._page_manager.reset_current_page_index()

        self._root.action_bar_title = get_action_bar_title(
            self._font_manager, fanta_info.comic_book_info.get_title_str()
        )

        self._page_manager.set_page_map(page_map, page_to_first_goto)

        self._comic_book_loader.set_comic(
            fanta_info,
            use_fantagraphics_overrides,
            comic_book_image_builder,
            self._page_manager.get_image_load_order(),
            page_map,
        )

        self._closed = False

    def close_comic_book_reader(self, fullscreen_button: ActionButton | None) -> None:
        if self._closed:
            return

        self._comic_book_loader.stop_now()

        if fullscreen_button:
            self._exit_fullscreen(fullscreen_button)
        self._comic_book_loader.close_comic()
        self._on_close_reader()

        self._page_manager.reset_current_page_index()
        self._goto_page_dropdown = None
        self._closed = True

    def _first_image_loaded(self) -> None:
        self._page_manager.set_to_first_page_to_read()
        logging.debug(f"First image loaded: current page index = { self._current_page_index}.")

        self._on_comic_is_ready_to_read()

    def _all_images_loaded(self) -> None:
        self._all_loaded = True
        logging.debug(f"All images loaded: current page index = {self._current_page_index}.")

    def _load_error(self, load_warning_only: bool) -> None:
        self._all_loaded = False
        if not load_warning_only:
            msg = "There was a comic book load error."
            raise RuntimeError(msg)
        self.close_comic_book_reader(None)

    def _show_page(self, _instance: Widget, _value: str) -> None:
        """Display the image for the current_page_index."""
        if self._current_page_index == -1:
            logging.debug("Show page not ready: current_page_index = -1.")
            return

        page_str = self._current_page_str
        logging.debug(
            f"Display image {self._current_page_index}:"
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
        except Exception:
            logging.exception(f"Error displaying image with index {self._current_page_index}: ")
            # Optionally display a placeholder image or error message

    def goto_start_page(self, _instance: Widget) -> None:
        self._page_manager.goto_start_page()

    def goto_last_page(self, _instance: Widget) -> None:
        self._page_manager.goto_last_page()

    def _next_page(self, _instance: Widget | None) -> None:
        self._page_manager.next_page()

    def _prev_page(self, _instance: Widget | None) -> None:
        self._page_manager.prev_page()

    def _wait_for_image_to_load(self) -> None:
        if self._all_loaded:
            return

        logging.info(f"Waiting for image with index {self._current_page_index} to finish loading.")
        while not self._comic_book_loader.get_load_event(self._current_page_index).wait(timeout=1):
            logging.info(
                f"Still waiting for image with index {self._current_page_index} to finish loading."
            )
        logging.info(f"Finished waiting for image with index {self._current_page_index} to load.")

    def toggle_fullscreen(self, button: ActionButton) -> None:
        """Toggles fullscreen mode."""
        if Window.fullscreen:
            Window.fullscreen = False
            self._show_action_bar()
            button.text = "Fullscreen"
            button.icon = self._action_bar_fullscreen_icon
            logging.info("Exiting fullscreen.")
        else:
            self._hide_action_bar()
            button.text = "Windowed"
            button.icon = self._action_bar_fullscreen_exit_icon
            Window.fullscreen = "auto"  # Use 'auto' for best platform behavior
            logging.info("Entering fullscreen.")

    def _hide_action_bar(self) -> None:
        self._action_bar.height = 0
        self._action_bar.opacity = 0

    def _show_action_bar(self) -> None:
        self._action_bar.height = ACTION_BAR_SIZE_Y
        self._action_bar.opacity = 1

    def _exit_fullscreen(self, button: ActionButton) -> None:
        if not Window.fullscreen:
            return

        Window.fullscreen = False
        self._show_action_bar()
        button.text = "Fullscreen"
        logging.info("Exiting fullscreen.")

    def _toggle_action_bar(self) -> None:
        """Toggles the visibility of the action bar."""
        logging.debug(
            f"On toggle action bar entry: self.action_bar.height = {self._action_bar.height}"
        )

        close_enough_to_zero = 0.1
        if self._action_bar.height <= close_enough_to_zero:
            self._show_action_bar()
        else:
            self._hide_action_bar()

        logging.debug(
            f"On toggle action bar exit: self.action_bar.height = {self._action_bar.height}"
        )

    def goto_page(self, _instance: Widget) -> None:
        """Go to user requested page."""
        if not self._goto_page_dropdown:
            self._create_goto_page_dropdown()
            assert self._goto_page_dropdown

        selected_button = None
        # Update button colors to highlight the current page before opening
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

        self._goto_page_dropdown.open(self._goto_page_widget)
        if selected_button:
            self._goto_page_dropdown.scroll_to(selected_button)

    def on_page_selected(self, _instance: Widget, page: str) -> None:
        self._page_manager.set_current_page_index_from_str(page)

    def _create_goto_page_dropdown(self) -> None:
        max_dropdown_height = round(GOTO_PAGE_DROPDOWN_FRAC_OF_HEIGHT * self.height)

        self._goto_page_dropdown = DropDown(
            auto_dismiss=True,
            dismiss_on_select=True,
            on_select=self.on_page_selected,
            max_height=max_dropdown_height,
        )

        for page, page_info in self._page_map.items():
            button = Button(
                text=str(page),
                size_hint_y=None,
                height=GOTO_PAGE_BUTTON_HEIGHT,
                bold=page_info.page_type == PageType.BODY,
            )
            button.bind(on_press=lambda btn: self._goto_page_dropdown.select(btn.text))
            self._goto_page_dropdown.add_widget(button)


class ComicBookReaderScreen(BoxLayout, Screen):
    action_bar_title = StringProperty()
    ACTION_BAR_TITLE_COLOR = (0.0, 1.0, 0.0, 1.0)
    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
    app_icon_filepath = StringProperty()
    action_bar_close_icon_filepath = StringProperty()
    action_bar_fullscreen_filepath = StringProperty()
    action_bar_fullscreen_exit_filepath = StringProperty()
    action_bar_goto_icon_filepath = StringProperty()
    action_bar_goto_start_filepath = StringProperty()
    action_bar_goto_end_filepath = StringProperty()

    def __init__(
        self, reader_settings: ReaderSettings, reader_app_icon_file: str, **kwargs  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)

        self.comic_book_reader = None
        self._set_action_bar_icons(reader_settings.sys_file_paths, reader_app_icon_file)

    def _set_action_bar_icons(self, sys_paths: SystemFilePaths, reader_app_icon_file: str) -> None:
        self.app_icon_filepath = reader_app_icon_file
        self.action_bar_close_icon_filepath = str(sys_paths.get_barks_reader_close_icon_file())
        self.action_bar_fullscreen_filepath = str(sys_paths.get_barks_reader_fullscreen_icon_file())
        self.action_bar_fullscreen_exit_filepath = str(
            sys_paths.get_barks_reader_fullscreen_exit_icon_file()
        )
        self.action_bar_goto_icon_filepath = str(sys_paths.get_barks_reader_goto_icon_file())
        self.action_bar_goto_start_filepath = str(sys_paths.get_barks_reader_goto_start_icon_file())
        self.action_bar_goto_end_filepath = str(sys_paths.get_barks_reader_goto_end_icon_file())

    def add_reader_widget(self, comic_book_reader: ComicBookReader) -> None:
        self.comic_book_reader = comic_book_reader
        self.add_widget(self.comic_book_reader)


KV_FILE = Path(__file__).stem + ".kv"


def get_barks_comic_reader_screen(
    screen_name: str,
    reader_settings: ReaderSettings,
    reader_app_icon_file: str,
    font_manager: FontManager,
    on_comic_is_ready_to_read: Callable[[], None],
    on_close_reader: Callable[[], None],
) -> Screen:
    Builder.load_file(KV_FILE)

    root = ComicBookReaderScreen(reader_settings, reader_app_icon_file, name=screen_name)

    comic_book_reader = ComicBookReader(
        root,
        reader_settings,
        font_manager,
        on_comic_is_ready_to_read,
        on_close_reader,
        root.ids.goto_page_button,
    )
    comic_book_reader.set_action_bar(root.ids.comic_action_bar)

    root.add_reader_widget(comic_book_reader)

    return root
