from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import StringProperty  # ty: ignore[unresolved-import]

from barks_reader.core.reader_formatter import get_action_bar_title
from barks_reader.core.reader_utils import COMIC_PAGE_ASPECT_RATIO
from barks_reader.ui.reader_keyboard_nav import (
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_UP,
    ActionBarNavMixin,
)
from barks_reader.ui.reader_screens import ReaderScreen
from barks_reader.ui.reader_ui_classes import ACTION_BAR_SIZE_Y

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.input import MotionEvent

    from barks_reader.ui.font_manager import FontManager

DOCUMENT_READER_KV_FILE = Path(__file__).with_suffix(".kv")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


class DocumentReaderScreen(ReaderScreen, ActionBarNavMixin):
    ACTION_BAR_TITLE_COLOR = (0.0, 1.0, 0.0, 1.0)
    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
    ASPECT_RATIO = COMIC_PAGE_ASPECT_RATIO
    action_bar_title = StringProperty()
    app_icon_filepath = StringProperty()
    page_source = StringProperty()

    def __init__(
        self,
        font_manager: FontManager,
        on_close_screen: Callable[[], None],
        **kwargs: str,
    ) -> None:
        super().__init__(**kwargs)

        self._font_manager = font_manager
        self._on_close_screen = on_close_screen
        self._page_paths: list[Path] = []
        self._current_page_index = 0

        self._setup_action_bar_nav([self.ids.close_button])

    def open_document(self, doc_dir: Path, title: str) -> None:
        self.action_bar_title = get_action_bar_title(self._font_manager, title)

        self._page_paths = sorted(
            p for p in doc_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
        )
        self._current_page_index = 0
        self._update_page_source()

        Window.bind(on_key_down=self._on_key_down)

    def _update_page_source(self) -> None:
        if self._page_paths:
            self.page_source = str(self._page_paths[self._current_page_index])
        else:
            self.page_source = ""

    def next_page(self) -> None:
        if self._current_page_index < len(self._page_paths) - 1:
            self._current_page_index += 1
            self._update_page_source()

    def prev_page(self) -> None:
        if self._current_page_index > 0:
            self._current_page_index -= 1
            self._update_page_source()

    def on_touch_down(self, touch: MotionEvent) -> bool:
        self._clear_menu_on_touch()

        # Let action bar buttons handle their own touches first.
        if self.ids.doc_action_bar.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        if self.ids.doc_page.collide_point(*touch.pos):
            mid_x = self.ids.doc_page.center_x
            if touch.x < mid_x:
                self.prev_page()
            else:
                self.next_page()
            return True

        return super().on_touch_down(touch)

    def _on_key_down(
        self, _window: object, key: int, _scancode: int, _codepoint: str, _modifier: list
    ) -> bool:
        if self._menu_mode:
            return self._handle_menu_key(key)
        if key == KEY_LEFT:
            self.prev_page()
        elif key == KEY_RIGHT:
            self.next_page()
        elif key in (KEY_ESCAPE, KEY_UP):
            self._enter_menu_mode()
        else:
            return False
        return True

    def close(self) -> None:
        if self._menu_mode:
            self._exit_menu_mode()
        Window.unbind(on_key_down=self._on_key_down)
        self._on_close_screen()


def get_document_reader_screen(
    screen_name: str,
    font_manager: FontManager,
    on_close_screen: Callable[[], None],
) -> DocumentReaderScreen:
    Builder.load_file(str(DOCUMENT_READER_KV_FILE))

    return DocumentReaderScreen(
        font_manager,
        on_close_screen,
        name=screen_name,
    )
