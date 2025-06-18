import logging
from collections import OrderedDict
from pathlib import Path
from threading import Thread
from typing import Callable, List, Dict

from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivy.uix.actionbar import ActionBar, ActionButton
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.image import Image
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
from screeninfo import get_monitors

from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
from comic_book_loader import PageInfo, ComicBookLoader
from file_paths import (
    get_barks_reader_action_bar_background_file,
    get_barks_reader_close_icon_file,
    get_barks_reader_fullscreen_icon_file,
    get_barks_reader_app_icon_file,
    get_barks_reader_next_icon_file,
    get_barks_reader_previous_icon_file,
    get_barks_reader_goto_start_icon_file,
    get_barks_reader_goto_end_icon_file,
    get_barks_reader_fullscreen_exit_icon_file,
    get_barks_reader_action_bar_group_background_file,
    get_barks_reader_goto_icon_file,
)
from reader_consts_and_types import ACTION_BAR_SIZE_Y

GOTO_PAGE_DROPDOWN_FRAC_OF_HEIGHT = 0.97
GOTO_PAGE_BUTTON_HEIGHT = dp(25)
GOTO_PAGE_BUTTON_BODY_COLOR = (0, 1, 1, 1)
GOTO_PAGE_BUTTON_NONBODY_COLOR = (0, 0.5, 0.5, 1)
GOTO_PAGE_BUTTON_CURRENT_PAGE_COLOR = (1, 1, 0, 1)

APP_ACTION_BAR_FULLSCREEN_ICON = get_barks_reader_fullscreen_icon_file()
APP_ACTION_BAR_FULLSCREEN_EXIT_ICON = get_barks_reader_fullscreen_exit_icon_file()


class ComicBookReader(BoxLayout):
    """Main layout for the comic reader."""

    current_page_index = NumericProperty(0)

    MAX_WINDOW_WIDTH = get_monitors()[0].width
    MAX_WINDOW_HEIGHT = get_monitors()[0].height

    def __init__(self, close_reader_func: Callable[[], None], goto_page_widget: Widget, **kwargs):
        super().__init__(**kwargs)

        self.action_bar = None
        self.close_reader_func = close_reader_func
        self.goto_page_widget = goto_page_widget
        self.__action_bar_fullscreen_icon = APP_ACTION_BAR_FULLSCREEN_ICON
        self.__action_bar_fullscreen_exit_icon = APP_ACTION_BAR_FULLSCREEN_EXIT_ICON
        self.current_comic_path = ""

        self.orientation = "vertical"

        self.comic_image = Image()
        self.comic_image.fit_mode = "contain"
        self.comic_image.mipmap = False
        self.add_widget(self.comic_image)

        self.comic_book_loader = ComicBookLoader(
            self.first_image_loaded,
            self.all_images_loaded,
            self.MAX_WINDOW_WIDTH,
            self.MAX_WINDOW_HEIGHT,
        )

        self.image_load_order: List[str] = []
        self.page_to_first_goto = ""
        self.last_page_index = -1
        self.all_loaded = False
        self.page_map: OrderedDict[str, PageInfo] = OrderedDict()
        self.index_to_page_map: Dict[int, str] = {}

        # Bind property changes to update the display
        self.bind(current_page_index=self.show_page)

        self.x_mid = -1
        self.y_top_margin = -1
        self.fullscreen_left_margin = -1
        self.fullscreen_right_margin = -1

        Window.bind(on_resize=self.on_window_resize)

    def on_window_resize(self, _window, width, height):
        self.x_mid = round(width / 2 - self.x)
        self.y_top_margin = round(height - self.y - (0.09 * height))

        logging.debug(
            f"Resize event: x,y = {self.x},{self.y},"
            f" width = {width}, height = {height},"
            f" self.width = {self.width}, self.height = {self.height}."
        )
        logging.debug(f"Resize event: x_mid = {self.x_mid}, y_top_margin = {self.y_top_margin}.")

        self.fullscreen_left_margin = round(self.MAX_WINDOW_WIDTH / 4.0)
        self.fullscreen_right_margin = self.MAX_WINDOW_WIDTH - self.fullscreen_left_margin
        logging.debug(
            f"Resize event: fullscreen_left_margin = {self.fullscreen_left_margin},"
            f" fullscreen_right_margin = {self.fullscreen_right_margin}."
        )

    def get_last_read_page(self) -> str:
        return self.index_to_page_map[self.current_page_index]

    def set_action_bar(self, action_bar: ActionBar):
        self.action_bar = action_bar

    def on_touch_down(self, touch):
        logging.debug(
            f"Touch down event: self.x,self.y = {self.x},{self.y},"
            f" touch.x,touch.y = {round(touch.x)},{round(touch.y)},"
            f" width = {round(self.width)}, height = {round(self.height)}."
            f" x_mid = {self.x_mid}, y_top_margin = {self.y_top_margin}."
        )

        x_rel = round(touch.x - self.x)
        y_rel = round(touch.y - self.y)

        if self.is_in_top_margin(x_rel, y_rel):
            logging.debug(f"Top margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            if Window.fullscreen:
                self.toggle_action_bar()
        elif self.is_in_left_margin(x_rel, y_rel):
            logging.debug(f"Left margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            self.prev_page(None)
        elif self.is_in_right_margin(x_rel, y_rel):
            logging.debug(f"Right margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            self.next_page(None)
        else:
            logging.debug(
                f"Dead zone: x_rel,y_rel = {x_rel},{y_rel},"
                f" Windows.fullscreen = {Window.fullscreen}."
            )

        return super().on_touch_down(touch)

    def is_in_top_margin(self, x: int, y: int) -> bool:
        if y <= self.y_top_margin:
            return False

        if not Window.fullscreen:
            return True

        return self.fullscreen_left_margin < x <= self.fullscreen_right_margin

    def is_in_left_margin(self, x: int, y: int) -> bool:
        return (x < self.x_mid) and (y <= self.y_top_margin)

    def is_in_right_margin(self, x: int, y: int) -> bool:
        return (x >= self.x_mid) and (y <= self.y_top_margin)

    def read_comic(
        self,
        fanta_info: FantaComicBookInfo,
        page_to_first_goto: str,
        page_map: OrderedDict[str, PageInfo],
    ):
        assert page_to_first_goto in page_map

        self.all_loaded = False
        self.current_page_index = -1  # Reset page index

        self.action_bar.action_view.action_previous.title = (
            fanta_info.comic_book_info.get_title_str()
        )
        self.page_to_first_goto = page_to_first_goto
        self.page_map = page_map
        self.index_to_page_map = {self.page_map[page].page_index: page for page in self.page_map}

        self.init_first_and_last_page_index()
        self.init_image_load_order()

        self.comic_book_loader.set_comic(fanta_info, self.image_load_order, self.page_map)

        self.load_current_comic()

    def load_current_comic(self):
        t = Thread(target=self.comic_book_loader.load_comic, args=[])
        t.daemon = True
        t.start()

    def close_comic_book_reader(self, fullscreen_button: ActionButton):
        self.comic_book_loader.stop_now()

        self.exit_fullscreen(fullscreen_button)
        self.comic_book_loader.close_comic()
        self.close_reader_func()

        self.last_page_index = -1

    def init_first_and_last_page_index(self):
        first_page_index = next(iter(self.page_map.values())).page_index

        assert first_page_index == 0
        self.last_page_index = next(reversed(self.page_map.values())).page_index
        assert (self.last_page_index + 1) == len(self.page_map)

    def init_image_load_order(self):
        self.image_load_order.clear()
        page_index_to_first_goto = self.page_map[self.page_to_first_goto].page_index

        if page_index_to_first_goto == 0:
            for page in self.page_map:
                self.image_load_order.append(page)
            return

        self.image_load_order.append(self.page_to_first_goto)
        prev_page = self.index_to_page_map[page_index_to_first_goto - 1]
        self.image_load_order.append(prev_page)

        for page_index in range(page_index_to_first_goto + 1, self.last_page_index + 1):
            page = self.index_to_page_map[page_index]
            self.image_load_order.append(page)

        for page_index in range(page_index_to_first_goto - 2, -1, -1):
            page = self.index_to_page_map[page_index]
            self.image_load_order.append(page)

    def first_image_loaded(self):
        self.current_page_index = self.page_map[self.page_to_first_goto].page_index
        logging.debug(f"First image loaded: current page index = {self.current_page_index}.")

    def all_images_loaded(self):
        self.all_loaded = True
        logging.debug(f"All images loaded: current page index = {self.current_page_index}.")

    def show_page(self, _instance, _value):
        """Displays the image for the current_page_index."""
        if self.current_page_index == -1:
            logging.debug(f"Show page not ready: current_page_index = {self.current_page_index}.")
            return

        logging.debug(
            f"Display image {self.current_page_index}:"
            f' "{self.page_map[self.index_to_page_map[self.current_page_index]].image_filename}".'
        )

        self.wait_for_image_to_load()

        assert 0 <= self.current_page_index <= self.last_page_index

        try:
            # Kivy Image widget can load from BytesIO
            self.comic_image.texture = None  # Clear previous texture
            self.comic_image.source = ""  # Clear previous source
            self.comic_image.reload()  # Ensure reload if source was same BytesIO object

            image_stream, image_ext = self.comic_book_loader.get_image_ready_for_reading(
                self.current_page_index
            )
            self.comic_image.texture = CoreImage(image_stream, ext=image_ext).texture
        except Exception as e:
            logging.error(f"Error displaying image with index {self.current_page_index}: {e}")
            # Optionally display a placeholder image or error message

    def goto_start_page(self, _instance):
        """Goes to the first page."""
        if self.current_page_index == 0:
            logging.info(f"Already on the first page: current index = {self.current_page_index}.")
        else:
            logging.info(f"Goto start page requested: requested index = 0.")
            self.current_page_index = 0

    def goto_last_page(self, _instance):
        """Goes to the last page."""
        if self.current_page_index == self.last_page_index:
            logging.info(f"Already on the last page: current index = {self.current_page_index}.")
        else:
            logging.info(f"Last page requested: requested index = {self.last_page_index}.")
            self.current_page_index = self.last_page_index

    def next_page(self, _instance):
        """Goes to the next page."""
        if self.current_page_index >= self.last_page_index:
            logging.info(f"Already on the last page: current index = {self.current_page_index}.")
        else:
            logging.info(f"Next page requested: requested index = {self.current_page_index + 1}")
            self.current_page_index += 1

    def prev_page(self, _instance):
        """Goes to the previous page."""
        if self.current_page_index == 0:
            logging.info(f"Already on the first page: current index = 0.")
        else:
            logging.info(f"Prev page requested: requested index = {self.current_page_index - 1}")
            self.current_page_index -= 1

        return True

    def goto_page(self, _instance):
        """Goes to user requested page."""

        max_dropdown_height = round(GOTO_PAGE_DROPDOWN_FRAC_OF_HEIGHT * self.height)
        dropdown = DropDown(
            auto_dismiss=True,
            dismiss_on_select=True,
            on_select=self.on_page_selected,
            max_height=max_dropdown_height,
        )

        selected_button = None
        for page, page_info in self.page_map.items():
            page_num_button = Button(
                text=str(page),
                size_hint_y=None,
                height=GOTO_PAGE_BUTTON_HEIGHT,
                bold=page_info.page_type == PageType.BODY,
                background_color=(
                    GOTO_PAGE_BUTTON_BODY_COLOR
                    if page_info.page_type == PageType.BODY
                    else GOTO_PAGE_BUTTON_NONBODY_COLOR
                ),
            )
            page_num_button.bind(on_press=lambda btn: dropdown.select(btn.text))
            dropdown.add_widget(page_num_button)

            if page_info.page_index == self.current_page_index:
                selected_button = page_num_button
                selected_button.background_color = GOTO_PAGE_BUTTON_CURRENT_PAGE_COLOR

        dropdown.open(self.goto_page_widget)
        dropdown.scroll_to(selected_button)

    def on_page_selected(self, _instance, page: str):
        self.current_page_index = self.page_map[page].page_index

    def wait_for_image_to_load(self):
        if self.all_loaded:
            return

        logging.info(f"Waiting for image with index {self.current_page_index} to finish loading.")
        while not self.comic_book_loader.get_load_event(self.current_page_index).wait(timeout=1):
            logging.info(
                f"Still waiting for image with index {self.current_page_index} to finish loading."
            )
        logging.info(f"Finished waiting for image with index {self.current_page_index} to load.")

    def toggle_fullscreen(self, button: ActionButton):
        """Toggles fullscreen mode."""
        if Window.fullscreen:
            Window.fullscreen = False
            self.show_action_bar()
            button.text = "Fullscreen"
            button.icon = self.__action_bar_fullscreen_icon
            logging.info("Exiting fullscreen.")
        else:
            self.hide_action_bar()
            button.text = "Windowed"
            button.icon = self.__action_bar_fullscreen_exit_icon
            Window.fullscreen = "auto"  # Use 'auto' for best platform behavior
            logging.info("Entering fullscreen.")

    def hide_action_bar(self):
        self.action_bar.height = 0
        self.action_bar.opacity = 0

    def show_action_bar(self):
        self.action_bar.height = ACTION_BAR_SIZE_Y
        self.action_bar.opacity = 1

    def exit_fullscreen(self, button: ActionButton):
        if not Window.fullscreen:
            return

        Window.fullscreen = False
        self.show_action_bar()
        button.text = "Fullscreen"
        logging.info("Exiting fullscreen.")

    def toggle_action_bar(self) -> None:
        """Toggles the visibility of the action bar."""
        logging.debug(
            f"On toggle action bar entry:" f" self.action_bar.height = {self.action_bar.height}"
        )

        if self.action_bar.height <= 0.1:
            self.show_action_bar()
        else:
            self.hide_action_bar()

        logging.debug(
            f"On toggle action bar exit: self.action_bar.height = {self.action_bar.height}"
        )


class ComicBookReaderScreen(BoxLayout, Screen):
    APP_ICON_FILE = get_barks_reader_app_icon_file()
    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
    ACTION_BAR_BACKGROUND_PATH = get_barks_reader_action_bar_background_file()
    ACTION_BAR_GROUP_BACKGROUND_PATH = get_barks_reader_action_bar_group_background_file()
    ACTION_BAR_BACKGROUND_COLOR = (0.6, 0.7, 0.2, 1)
    ACTION_BUTTON_BACKGROUND_COLOR = (0.6, 1.0, 0.2, 1)
    ACTION_BAR_CLOSE_ICON = get_barks_reader_close_icon_file()
    ACTION_BAR_FULLSCREEN_ICON = APP_ACTION_BAR_FULLSCREEN_ICON
    ACTION_BAR_FULLSCREEN_EXIT_ICON = APP_ACTION_BAR_FULLSCREEN_EXIT_ICON
    ACTION_BAR_NEXT_ICON = get_barks_reader_next_icon_file()
    ACTION_BAR_PREV_ICON = get_barks_reader_previous_icon_file()
    ACTION_BAR_GOTO_ICON = get_barks_reader_goto_icon_file()
    ACTION_BAR_GOTO_START_ICON = get_barks_reader_goto_start_icon_file()
    ACTION_BAR_GOTO_END_ICON = get_barks_reader_goto_end_icon_file()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.comic_book_reader_widget = None

    def add_reader_widget(self, comic_book_reader_widget: ComicBookReader):
        self.comic_book_reader_widget = comic_book_reader_widget
        self.add_widget(self.comic_book_reader_widget)


KV_FILE = Path(__file__).stem + ".kv"


def get_barks_comic_reader(screen_name: str, close_reader_func: Callable[[], None]):
    Builder.load_file(KV_FILE)

    root = ComicBookReaderScreen(name=screen_name)

    comic_book_reader_widget = ComicBookReader(close_reader_func, root.ids.goto_page_button)
    comic_book_reader_widget.set_action_bar(root.ids.comic_action_bar)

    root.add_reader_widget(comic_book_reader_widget)

    return root
