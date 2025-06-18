# You might need 'pip install rarfile' and the 'unrar' executable for .cbr support
# import rarfile
import io
import logging
import os
import threading
import zipfile
from pathlib import Path
from threading import Thread

from PIL import Image as PilImage, ImageOps
from kivy.app import App
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.properties import NumericProperty, StringProperty
from kivy.uix.actionbar import ActionBar, ActionView, ActionPrevious, ActionButton
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from screeninfo import get_monitors

DEFAULT_ASPECT_RATIO = 1.5
DEFAULT_WINDOW_HEIGHT = 1000
DEFAULT_WINDOW_WIDTH = int(round(DEFAULT_WINDOW_HEIGHT / DEFAULT_ASPECT_RATIO))
DEFAULT_LEFT_POS = 400
DEFAULT_TOP_POS = 50

ACTION_BAR_SIZE_HINT_Y = 0.05


class ComicReader(BoxLayout):
    """Main layout for the comic reader."""

    current_page_index = NumericProperty(0)
    current_comic_path = StringProperty("")

    MAX_WINDOW_WIDTH = get_monitors()[0].width
    MAX_WINDOW_HEIGHT = get_monitors()[0].height

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.action_bar = None

        self.orientation = "vertical"

        self.comic_image = Image()
        self.comic_image.fit_mode = "contain"
        self.comic_image.mipmap = False
        self.add_widget(self.comic_image)

        self.popup = None

        self.images = []
        self.image_names = []
        self.image_loaded_events = []
        self.first_page_index = -1
        self.last_page_index = -1
        self.all_loaded = False

        # Bind property changes to update the display
        self.bind(current_page_index=self.show_page)

        self.x_mid = -1
        self.y_top_margin = -1

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

        if y_rel > self.y_top_margin:
            logging.debug(f"Top margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            if Window.fullscreen:
                self.toggle_action_bar()
        elif x_rel < self.x_mid:
            logging.debug(f"Left margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            self.prev_page(None)
        elif x_rel >= self.x_mid:
            logging.debug(f"Right margin pressed: x_rel,y_rel = {x_rel},{y_rel}.")
            self.next_page(None)
        else:
            logging.error("Middle touch - should not happen.")

        return super().on_touch_down(touch)

    def open_file_chooser(self):
        """Opens a file chooser popup to select a comic file."""
        filechooser = FileChooserListView(
            filters=["*.cbz", "*.zip", "*.cbr", "*.rar"],  # Add more extensions if needed
            path=os.path.expanduser(
                "/home/greg/Books/Carl Barks/The Comics/Chronological Years/1945"
            ),
        )
        filechooser.bind(on_submit=self.selected_file)

        self.popup = Popup(title="Select Comic File", content=filechooser, size_hint=(0.9, 0.9))
        self.popup.open()

    def selected_file(self, instance, selection, touch):
        """Called when a file is selected in the file chooser."""
        if selection:
            self.current_comic_path = selection[0]
            self.load_current_comic_path()
            self.popup.dismiss()

    def load_current_comic_path(self):
        self.all_loaded = False

        self.load_image_names()
        self.init_load_events()

        t = Thread(target=self.load_comic, args=[self.current_comic_path])
        t.daemon = True
        t.start()

    def init_load_events(self):
        self.image_loaded_events = []
        for name in self.image_names:
            self.image_loaded_events.append(threading.Event())

    def load_image_names(self):
        if not self.current_comic_path.lower().endswith((".cbz", ".zip")):
            raise Exception("Expected '.cbz' or '.zip' file.")

        try:
            with zipfile.ZipFile(self.current_comic_path, "r") as archive:
                # Get image file names, sorted alphabetically
                self.image_names = sorted(
                    [f for f in archive.namelist() if f.lower().endswith((".png", ".jpg"))]
                )

            self.first_page_index = 0
            self.last_page_index = len(self.image_names) - 1

        except FileNotFoundError:
            logging.error(f'Comic file not found: "{self.current_comic_path}".')
            # Optionally show an error message to the user
        except zipfile.BadZipFile:
            logging.error(f'Bad zip file: "{self.current_comic_path}".')
            # Optionally show an error message to the user
        # except rarfile.BadRarFile:
        #      Logger.error(f"Bad rar file: {self.current_comic_path}")
        #      # Optionally show an error message to the user
        except Exception as e:
            logging.error(f'Error loading comic "{self.current_comic_path}": {e}')
            # Optionally show a generic error message

    def load_comic(self, comic_path):
        """Loads images from the comic archive."""
        self.images = []  # Clear previous images
        self.current_page_index = -1  # Reset page index

        try:
            with zipfile.ZipFile(comic_path, "r") as archive:
                first_loaded = False
                for i, name in enumerate(self.image_names):
                    with archive.open(name) as file:
                        ext = Path(name).suffix
                        self.images.append(self.get_image_data(file, ext))
                    self.image_loaded_events[i].set()
                    if not first_loaded:
                        first_loaded = True
                        Clock.schedule_once(self.first_image_loaded, 0)

            self.all_loaded = True
            logging.info(f"Loaded {len(self.images)} images from {comic_path}.")

            # Add .cbr support if rarfile is installed
            # elif comic_path.lower().endswith(('.cbr', '.rar')):
            #     with rarfile.RarFile(comic_path, 'r') as archive:
            #         image_names = sorted([
            #             f for f in archive.namelist()
            #             if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))
            #         ])
            #         for name in image_names:
            #             with archive.open(name) as file:
            #                 img_data = io.BytesIO(file.read())
            #                 self.images.append(img_data)
            #     Logger.info(f"Loaded {len(self.images)} images from {comic_path}")

        except FileNotFoundError:
            logging.error(f'Comic file not found: "{comic_path}".')
            # Optionally show an error message to the user
        except zipfile.BadZipFile:
            logging.error(f'Bad zip file: "{comic_path}".')
            # Optionally show an error message to the user
        # except rarfile.BadRarFile:
        #      Logger.error(f"Bad rar file: {comic_path}")
        #      # Optionally show an error message to the user
        except Exception as e:
            logging.error(f'Error loading comic "{comic_path}": {e}')
            # Optionally show a generic error message

    def first_image_loaded(self, _dt):
        self.current_page_index = 0
        logging.debug(f"First image loaded: current page index = {self.current_page_index}.")

    def get_image_data(self, file: zipfile.ZipExtFile, ext: str) -> io.BytesIO:
        assert ext in [".png", ".jpg"]
        image_format = "jpeg" if ext == "jpeg" else "png"
        img_data = PilImage.open(io.BytesIO(file.read()))
        img_data = ImageOps.contain(
            img_data,
            (self.MAX_WINDOW_HEIGHT, self.MAX_WINDOW_WIDTH),
            PilImage.Resampling.LANCZOS,
        )
        data = io.BytesIO()
        img_data.save(data, format=image_format)

        return data

    def show_page(self, _instance, _value):
        """Displays the image for the current_page_index."""
        if self.current_page_index == -1:
            return

        logging.debug(
            f"Display image {self.current_page_index}:"
            f' "{self.image_names[self.current_page_index]}".'
        )

        self.wait_for_image_to_load()

        assert self.images
        assert self.first_page_index <= self.current_page_index <= self.last_page_index

        try:
            # Kivy Image widget can load from BytesIO
            self.comic_image.texture = None  # Clear previous texture
            self.comic_image.source = ""  # Clear previous source
            self.comic_image.reload()  # Ensure reload if source was same BytesIO object

            # Reset stream position before loading
            self.images[self.current_page_index].seek(0)
            self.comic_image.texture = CoreImage(
                self.images[self.current_page_index], ext="jpeg"
            ).texture
        except Exception as e:
            logging.error(f"Error displaying image with index {self.current_page_index}: {e}")
            # Optionally display a placeholder image or error message

    def next_page(self, _instance):
        """Goes to the next page."""
        if self.current_page_index >= self.last_page_index:
            logging.info(f"Already on the last page: current index = {self.current_page_index}.")
        else:
            logging.info(f"Next page requested: requested index = {self.current_page_index + 1}")
            self.current_page_index += 1

    def prev_page(self, _instance):
        """Goes to the previous page."""
        if self.current_page_index == self.first_page_index:
            logging.info(f"Already on the first page: current index = {self.current_page_index}.")
        else:
            logging.info(f"Prev page requested: requested index = {self.current_page_index - 1}")
            self.current_page_index -= 1

    def wait_for_image_to_load(self):
        if self.all_loaded:
            return

        logging.info(f"Waiting for image with index {self.current_page_index} to finish loading.")
        while not self.image_loaded_events[self.current_page_index].wait(timeout=1):
            logging.info(
                f"Still waiting for image with index {self.current_page_index} to finish loading."
            )
        logging.info(f"Finished waiting for image with index {self.current_page_index} to load.")

    def toggle_fullscreen(self, button: ActionButton):
        """Toggles fullscreen mode."""
        if Window.fullscreen:
            Window.fullscreen = False
            self.action_bar.size_hint_y = 0.1
            button.text = "Fullscreen"
            logging.info("Exiting fullscreen.")
        else:
            self.action_bar.size_hint_y = 0.0
            button.text = "Windowed"
            Window.fullscreen = "auto"  # Use 'auto' for best platform behavior
            logging.info("Entering fullscreen.")

    def toggle_action_bar(self) -> None:
        """Toggles the visibility of the action bar."""
        logging.debug(
            f"On toggle action bar entry:"
            f" self.action_bar.size_hint_y = {self.action_bar.size_hint_y}"
        )

        if self.action_bar.size_hint_y < 0.01:
            self.action_bar.size_hint_y = ACTION_BAR_SIZE_HINT_Y
        else:
            self.action_bar.size_hint_y = 0.0

        logging.debug(
            f"On toggle action bar exit:"
            f" self.action_bar.size_hint_y = {self.action_bar.size_hint_y}"
        )


class ComicReaderApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        Window.size = (DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        Window.left = DEFAULT_LEFT_POS
        Window.top = DEFAULT_TOP_POS

        self.root = None
        self.title = "Barks Comic Reader"
        self.comic_reader_widget = ComicReader()

    def build(self):
        # Create the main layout with ActionBar at the top
        root = BoxLayout(orientation="vertical")

        # Create the ActionBar
        title = "The Lost Crown of Genghis Kahn!"
        action_bar = ActionBar(size_hint_y=ACTION_BAR_SIZE_HINT_Y)
        action_view = ActionView()
        action_view.add_widget(ActionPrevious(title=title, with_previous=False))

        # Add buttons to the ActionView
        open_button = ActionButton(text="Open Comic")
        open_button.bind(
            on_press=lambda x: self.comic_reader_widget.open_file_chooser()
        )  # Bind to root widget method
        action_view.add_widget(open_button)

        fullscreen_button = ActionButton(text="Fullscreen")
        fullscreen_button.bind(
            on_press=lambda button: self.comic_reader_widget.toggle_fullscreen(button)
        )  # Bind to root widget method
        action_view.add_widget(fullscreen_button)

        quit_button = ActionButton(text="Close")
        quit_button.bind(on_press=lambda x: self.stop())  # Bind to App stop method
        action_view.add_widget(quit_button)

        action_bar.add_widget(action_view)

        root.add_widget(action_bar)

        self.comic_reader_widget.set_action_bar(action_bar)
        root.add_widget(self.comic_reader_widget)

        # Set the root widget and return it
        self.root = root
        return root


def setup_logging(log_level) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        level=log_level,
    )
    # TODO: Hack to stop third-party modules screwing with our logging.
    # Must be a better way.
    logging.root.setLevel(log_level)


if __name__ == "__main__":
    setup_logging(logging.DEBUG)

    ComicReaderApp().run()
