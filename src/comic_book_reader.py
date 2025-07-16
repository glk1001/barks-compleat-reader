import logging
from collections import OrderedDict
from pathlib import Path
from typing import Callable, List, Dict, Union

from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.event import EventDispatcher
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import NumericProperty, StringProperty
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
from build_comic_images import ComicBookImageBuilder
from comic_book_loader import ComicBookLoader
from comic_book_page_info import PageInfo
from reader_consts_and_types import ACTION_BAR_SIZE_Y
from reader_settings import ReaderSettings
from system_file_paths import SystemFilePaths

GOTO_PAGE_DROPDOWN_FRAC_OF_HEIGHT = 0.97
GOTO_PAGE_BUTTON_HEIGHT = dp(25)
GOTO_PAGE_BUTTON_BODY_COLOR = (0, 1, 1, 1)
GOTO_PAGE_BUTTON_NONBODY_COLOR = (0, 0.5, 0.5, 1)
GOTO_PAGE_BUTTON_CURRENT_PAGE_COLOR = (1, 1, 0, 1)


class ComicPageManager(EventDispatcher):
    """Manages the state and navigation logic for a comic book's pages."""

    current_page_index = NumericProperty(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.page_map: Union[OrderedDict[str, PageInfo], None] = None
        self.index_to_page_map: Dict[int, str] = {}
        self.__first_page_to_read_index = -1

        self.first_page_index = -1
        self.last_page_index = -1

    def get_current_page_index(self) -> int:
        return self.current_page_index

    def reset_current_page_index(self) -> None:
        self.current_page_index = -1

    def get_current_page_str(self) -> str:
        return self.index_to_page_map.get(self.current_page_index, "")

    def set_current_page_index_from_str(self, page_str: str) -> None:
        self.current_page_index = self.page_map[page_str].page_index

    def set_to_first_page_to_read(self) -> None:
        self.current_page_index = self.__first_page_to_read_index

    def goto_start_page(self) -> None:
        if self.get_current_page_index() == self.first_page_index:
            logging.info(
                f"Already on the first page: current index = {self.get_current_page_index()}."
            )
        else:
            logging.info(f"Goto start page: requested index = 0.")
            self.current_page_index = self.first_page_index

    def goto_last_page(self) -> None:
        if self.get_current_page_index() == self.last_page_index:
            logging.info(
                f"Already on the last page: current index = {self.get_current_page_index()}."
            )
        else:
            logging.info(f"Last page: requested index = {self.last_page_index}.")
            self.current_page_index = self.last_page_index

    def next_page(self) -> None:
        if self.get_current_page_index() >= self.last_page_index:
            logging.info(
                f"Already on the last page: current index = {self.get_current_page_index()}."
            )
        else:
            logging.info(f"Next page: requested index = {self.get_current_page_index() + 1}")
            self.current_page_index += 1

    def prev_page(self) -> None:
        if self.get_current_page_index() <= self.first_page_index:
            logging.info(f"Already on the first page: current index = 0.")
        else:
            logging.info(f"Prev page: requested index = {self.get_current_page_index() - 1}")
            self.current_page_index -= 1

    def set_page_map(self, page_map: OrderedDict[str, PageInfo], page_to_first_goto: str):
        self.page_map = page_map
        self.index_to_page_map: Dict[int, str] = {
            page_info.page_index: page_str for page_str, page_info in page_map.items()
        }
        self.__first_page_to_read_index = self.page_map[page_to_first_goto].page_index

        self.first_page_index = next(iter(self.page_map.values())).page_index
        self.last_page_index = next(reversed(self.page_map.values())).page_index

        assert self.first_page_index == 0
        assert (self.last_page_index + 1) == len(self.page_map)

    def get_image_load_order(self) -> List[str]:
        """Determines the optimal order to load images for a smooth user experience."""
        image_load_order = []
        page_to_first_goto = self.index_to_page_map[self.__first_page_to_read_index]

        if self.__first_page_to_read_index == 0:
            image_load_order.extend(self.page_map.keys())
            return image_load_order

        image_load_order.append(page_to_first_goto)
        prev_page = self.index_to_page_map[self.__first_page_to_read_index - 1]
        image_load_order.append(prev_page)

        for page_index in range(self.__first_page_to_read_index + 1, self.last_page_index + 1):
            page = self.index_to_page_map[page_index]
            image_load_order.append(page)

        for page_index in range(self.__first_page_to_read_index - 2, -1, -1):
            page = self.index_to_page_map[page_index]
            image_load_order.append(page)

        return image_load_order


class ComicBookReader(BoxLayout):
    """Main layout for the comic reader."""

    MAX_WINDOW_WIDTH = get_monitors()[0].width
    MAX_WINDOW_HEIGHT = get_monitors()[0].height

    def __init__(
        self,
        reader_settings: ReaderSettings,
        on_comic_is_ready_to_read: Callable[[], None],
        on_close_reader: Callable[[], None],
        goto_page_widget: Widget,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.__reader_settings = reader_settings
        self.__on_comic_is_ready_to_read = on_comic_is_ready_to_read
        self.__on_close_reader = on_close_reader
        self.__goto_page_widget = goto_page_widget

        self.__action_bar = None
        self.__action_bar_fullscreen_icon = (
            self.__reader_settings.sys_file_paths.get_barks_reader_fullscreen_icon_file()
        )
        self.__action_bar_fullscreen_exit_icon = (
            self.__reader_settings.sys_file_paths.get_barks_reader_fullscreen_exit_icon_file()
        )
        self.__current_comic_path = ""

        self.__orientation = "vertical"

        self.__comic_image = Image()
        self.__comic_image.fit_mode = "contain"
        self.__comic_image.mipmap = False
        self.add_widget(self.__comic_image)

        self.__comic_book_loader = ComicBookLoader(
            self.__reader_settings,
            self.first_image_loaded,
            self.all_images_loaded,
            self.load_error,
            self.MAX_WINDOW_WIDTH,
            self.MAX_WINDOW_HEIGHT,
        )

        self.__all_loaded = False
        self.__closed = False
        self.__goto_page_dropdown: Union[DropDown, None] = None

        # Bind property changes to update the display
        self.__page_manager = ComicPageManager()
        self.__page_manager.bind(current_page_index=self.show_page)

        self.__x_mid = -1
        self.__y_top_margin = -1
        self.__fullscreen_left_margin = -1
        self.__fullscreen_right_margin = -1

        Window.bind(on_resize=self.on_window_resize)

    def on_window_resize(self, _window, width, height):
        self.__x_mid = round(width / 2 - self.x)
        self.__y_top_margin = round(height - self.y - (0.09 * height))

        logging.debug(
            f"Comic reader window resize event: x,y = {self.x},{self.y},"
            f" width = {width}, height = {height},"
            f" self.width = {self.width}, self.height = {self.height}."
        )
        logging.debug(
            f"Comic reader window resize event:"
            f" x_mid = {self.__x_mid}, y_top_margin = {self.__y_top_margin}."
        )

        self.__fullscreen_left_margin = round(self.MAX_WINDOW_WIDTH / 4.0)
        self.__fullscreen_right_margin = self.MAX_WINDOW_WIDTH - self.__fullscreen_left_margin
        logging.debug(
            f"Comic reader window resize event:"
            f" fullscreen_left_margin = {self.__fullscreen_left_margin},"
            f" fullscreen_right_margin = {self.__fullscreen_right_margin}."
        )

    @property
    def __current_page_index(self) -> int:
        return self.__page_manager.get_current_page_index()

    @property
    def __current_page_str(self) -> str:
        return self.__page_manager.get_current_page_str()

    @property
    def __page_map(self) -> OrderedDict[str, PageInfo]:
        return self.__page_manager.page_map

    def get_last_read_page(self) -> str:
        return self.__current_page_str

    def set_action_bar(self, action_bar: ActionBar):
        self.__action_bar = action_bar

    def on_touch_down(self, touch):
        logging.debug(
            f"Touch down event: self.x,self.y = {self.x},{self.y},"
            f" touch.x,touch.y = {round(touch.x)},{round(touch.y)},"
            f" width = {round(self.width)}, height = {round(self.height)}."
            f" x_mid = {self.__x_mid}, y_top_margin = {self.__y_top_margin}."
        )

        x_rel = round(touch.x - self.x)
        y_rel = round(touch.y - self.y)

        if self.__is_in_top_margin(x_rel, y_rel):
            logging.debug(f"Top margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            if Window.fullscreen:
                self.__toggle_action_bar()
        elif self.__is_in_left_margin(x_rel, y_rel):
            logging.debug(f"Left margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            self.__prev_page(None)
        elif self.__is_in_right_margin(x_rel, y_rel):
            logging.debug(f"Right margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            self.__next_page(None)
        else:
            logging.debug(
                f"Dead zone: x_rel,y_rel = {x_rel},{y_rel},"
                f" Windows.fullscreen = {Window.fullscreen}."
            )

        return super().on_touch_down(touch)

    def __is_in_top_margin(self, x: int, y: int) -> bool:
        if y <= self.__y_top_margin:
            return False

        if not Window.fullscreen:
            return True

        return self.__fullscreen_left_margin < x <= self.__fullscreen_right_margin

    def __is_in_left_margin(self, x: int, y: int) -> bool:
        return (x < self.__x_mid) and (y <= self.__y_top_margin)

    def __is_in_right_margin(self, x: int, y: int) -> bool:
        return (x >= self.__x_mid) and (y <= self.__y_top_margin)

    def init_data(self):
        self.__comic_book_loader.init_data()

    def read_comic(
        self,
        fanta_info: FantaComicBookInfo,
        comic_book_image_builder: ComicBookImageBuilder,
        page_to_first_goto: str,
        page_map: OrderedDict[str, PageInfo],
    ):
        assert page_to_first_goto in page_map

        self.__all_loaded = False
        self.__page_manager.reset_current_page_index()

        self.__action_bar.action_view.action_previous.title = (
            fanta_info.comic_book_info.get_title_str()
        )

        self.__page_manager.set_page_map(page_map, page_to_first_goto)

        self.__comic_book_loader.set_comic(
            fanta_info,
            comic_book_image_builder,
            self.__page_manager.get_image_load_order(),
            page_map,
        )

        self.__closed = False

    def close_comic_book_reader(self, fullscreen_button: Union[ActionButton, None]):
        if self.__closed:
            return

        self.__comic_book_loader.stop_now()

        if fullscreen_button:
            self.__exit_fullscreen(fullscreen_button)
        self.__comic_book_loader.close_comic()
        self.__on_close_reader()

        self.__page_manager.reset_current_page_index()
        self.__goto_page_dropdown = None
        self.__closed = True

    def first_image_loaded(self):
        self.__page_manager.set_to_first_page_to_read()
        logging.debug(f"First image loaded: current page index = { self.__current_page_index}.")

        self.__on_comic_is_ready_to_read()

    def all_images_loaded(self):
        self.__all_loaded = True
        logging.debug(f"All images loaded: current page index = {self.__current_page_index}.")

    def load_error(self, load_warning_only: bool):
        self.__all_loaded = False
        if not load_warning_only:
            logging.debug(f"There was a comic book load error.")
        self.close_comic_book_reader(None)

    def show_page(self, _instance, _value):
        """Displays the image for the current_page_index."""
        if self.__current_page_index == -1:
            logging.debug(f"Show page not ready: current_page_index = -1.")
            return

        page_str = self.__current_page_str
        logging.debug(
            f"Display image {self.__current_page_index}:"
            f" {self.__comic_book_loader.get_image_info_str(page_str)}."
        )

        self.__wait_for_image_to_load()

        assert 0 <= self.__current_page_index <= self.__page_manager.last_page_index

        try:
            # Kivy Image widget can load from BytesIO
            self.__comic_image.texture = None  # Clear previous texture
            self.__comic_image.source = ""  # Clear previous source
            self.__comic_image.reload()  # Ensure reload if source was same BytesIO object

            image_stream, image_ext = self.__comic_book_loader.get_image_ready_for_reading(
                self.__current_page_index
            )
            self.__comic_image.texture = CoreImage(image_stream, ext=image_ext).texture
        except Exception as e:
            logging.error(f"Error displaying image with index {self.__current_page_index}: {e}")
            # Optionally display a placeholder image or error message

    def goto_start_page(self, _instance):
        self.__page_manager.goto_start_page()

    def goto_last_page(self, _instance):
        self.__page_manager.goto_last_page()

    def __next_page(self, _instance):
        self.__page_manager.next_page()

    def __prev_page(self, _instance):
        self.__page_manager.prev_page()

    def __wait_for_image_to_load(self):
        if self.__all_loaded:
            return

        logging.info(f"Waiting for image with index {self.__current_page_index} to finish loading.")
        while not self.__comic_book_loader.get_load_event(self.__current_page_index).wait(
            timeout=1
        ):
            logging.info(
                f"Still waiting for image with index {self.__current_page_index} to finish loading."
            )
        logging.info(f"Finished waiting for image with index {self.__current_page_index} to load.")

    def toggle_fullscreen(self, button: ActionButton):
        """Toggles fullscreen mode."""
        if Window.fullscreen:
            Window.fullscreen = False
            self.__show_action_bar()
            button.text = "Fullscreen"
            button.icon = self.__action_bar_fullscreen_icon
            logging.info("Exiting fullscreen.")
        else:
            self.__hide_action_bar()
            button.text = "Windowed"
            button.icon = self.__action_bar_fullscreen_exit_icon
            Window.fullscreen = "auto"  # Use 'auto' for best platform behavior
            logging.info("Entering fullscreen.")

    def __hide_action_bar(self):
        self.__action_bar.height = 0
        self.__action_bar.opacity = 0

    def __show_action_bar(self):
        self.__action_bar.height = ACTION_BAR_SIZE_Y
        self.__action_bar.opacity = 1

    def __exit_fullscreen(self, button: ActionButton):
        if not Window.fullscreen:
            return

        Window.fullscreen = False
        self.__show_action_bar()
        button.text = "Fullscreen"
        logging.info("Exiting fullscreen.")

    def __toggle_action_bar(self) -> None:
        """Toggles the visibility of the action bar."""
        logging.debug(
            f"On toggle action bar entry:" f" self.action_bar.height = {self.__action_bar.height}"
        )

        if self.__action_bar.height <= 0.1:
            self.__show_action_bar()
        else:
            self.__hide_action_bar()

        logging.debug(
            f"On toggle action bar exit: self.action_bar.height = {self.__action_bar.height}"
        )

    def goto_page(self, _instance):
        """Goes to user requested page."""

        if not self.__goto_page_dropdown:
            self.__create_goto_page_dropdown()
            assert self.__goto_page_dropdown

        selected_button = None
        # Update button colors to highlight the current page before opening
        for button in self.__goto_page_dropdown.children[0].children:
            page_info = self.__page_map[button.text]
            if page_info.page_index == self.__current_page_index:
                button.background_color = GOTO_PAGE_BUTTON_CURRENT_PAGE_COLOR
                selected_button = button
            else:
                button.background_color = (
                    GOTO_PAGE_BUTTON_BODY_COLOR
                    if page_info.page_type == PageType.BODY
                    else GOTO_PAGE_BUTTON_NONBODY_COLOR
                )

        self.__goto_page_dropdown.open(self.__goto_page_widget)
        if selected_button:
            self.__goto_page_dropdown.scroll_to(selected_button)

    def on_page_selected(self, _instance, page: str):
        self.__page_manager.set_current_page_index_from_str(page)

    def __create_goto_page_dropdown(self):
        max_dropdown_height = round(GOTO_PAGE_DROPDOWN_FRAC_OF_HEIGHT * self.height)

        self.__goto_page_dropdown = DropDown(
            auto_dismiss=True,
            dismiss_on_select=True,
            on_select=self.on_page_selected,
            max_height=max_dropdown_height,
        )

        for page, page_info in self.__page_map.items():
            button = Button(
                text=str(page),
                size_hint_y=None,
                height=GOTO_PAGE_BUTTON_HEIGHT,
                bold=page_info.page_type == PageType.BODY,
            )
            button.bind(on_press=lambda btn: self.__goto_page_dropdown.select(btn.text))
            self.__goto_page_dropdown.add_widget(button)


class ComicBookReaderScreen(BoxLayout, Screen):
    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
    app_icon_filepath = StringProperty()
    action_bar_close_icon_filepath = StringProperty()
    action_bar_fullscreen_filepath = StringProperty()
    action_bar_fullscreen_exit_filepath = StringProperty()
    action_bar_goto_icon_filepath = StringProperty()
    action_bar_goto_start_filepath = StringProperty()
    action_bar_goto_end_filepath = StringProperty()

    def __init__(self, reader_settings: ReaderSettings, **kwargs):
        super().__init__(**kwargs)
        self.comic_book_reader_widget = None

        self.set_action_bar_icons(reader_settings.sys_file_paths)

    def set_action_bar_icons(self, sys_paths: SystemFilePaths):
        self.app_icon_filepath = sys_paths.get_barks_reader_app_icon_file()
        self.action_bar_close_icon_filepath = sys_paths.get_barks_reader_close_icon_file()
        self.action_bar_fullscreen_filepath = sys_paths.get_barks_reader_fullscreen_icon_file()
        self.action_bar_fullscreen_exit_filepath = (
            sys_paths.get_barks_reader_fullscreen_exit_icon_file()
        )
        self.action_bar_goto_icon_filepath = sys_paths.get_barks_reader_goto_icon_file()
        self.action_bar_goto_start_filepath = sys_paths.get_barks_reader_goto_start_icon_file()
        self.action_bar_goto_end_filepath = sys_paths.get_barks_reader_goto_end_icon_file()

    def add_reader_widget(self, comic_book_reader_widget: ComicBookReader):
        self.comic_book_reader_widget = comic_book_reader_widget
        self.add_widget(self.comic_book_reader_widget)


KV_FILE = Path(__file__).stem + ".kv"


def get_barks_comic_reader(
    screen_name: str,
    reader_settings: ReaderSettings,
    on_comic_is_ready_to_read: Callable[[], None],
    on_close_reader: Callable[[], None],
):
    Builder.load_file(KV_FILE)

    root = ComicBookReaderScreen(reader_settings, name=screen_name)

    comic_book_reader_widget = ComicBookReader(
        reader_settings, on_comic_is_ready_to_read, on_close_reader, root.ids.goto_page_button
    )
    comic_book_reader_widget.set_action_bar(root.ids.comic_action_bar)

    root.add_reader_widget(comic_book_reader_widget)

    return root
