from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, override

from barks_kivy_ui.scrolling import ReaderDropDown
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, StringProperty  # ty: ignore[unresolved-import]
from kivy.uix.button import Button
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.document_chapters import PAGE_IMAGE_EXTENSIONS
from barks_reader.core.document_links import StoryLink, load_story_links
from barks_reader.core.reader_formatter import get_action_bar_title
from barks_reader.core.reader_utils import COMIC_PAGE_ASPECT_RATIO

from .action_bar_helpers import ACTION_BAR_SIZE_Y
from .reader_keyboard_nav import ActionBarNavMixin, DropdownNavMixin, open_dropdown
from .reader_screens import ReaderScreen
from .tap_targets import Rect, window_rect

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_titles import Titles
    from kivy.input import MotionEvent
    from kivy.uix.widget import Widget

    from .font_manager import FontManager

DOCUMENT_READER_KV_FILE = Path(__file__).with_suffix(".kv")

IMAGE_EXTENSIONS = PAGE_IMAGE_EXTENSIONS

STORY_BUTTON_HEIGHT = dp(30)
STORY_DROPDOWN_WIDTH = dp(420)


class GotoStory(Protocol):
    """Select a story with a page of it offered (``MainScreen.goto_title_from_document``)."""

    def __call__(self, title: Titles, page: str, *, keyboard_initiated: bool) -> None: ...


class DocumentReaderScreen(ReaderScreen, DropdownNavMixin, ActionBarNavMixin):
    """A folder of page images, turned by tap or arrow key.

    A page may name the stories its figures come from (``core.document_links``). "Go to
    Story" then closes the document and selects the story with the figure's page offered: at
    once for one story, from a list for several. The button is greyed on a page with none.

    Each document's last page is kept until the app quits, so one opened to resume (an
    illustrated-history chapter, from its node or from Go Back after a story) comes back at
    the page it was left on.
    """

    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
    ASPECT_RATIO = COMIC_PAGE_ASPECT_RATIO
    GREYED_BUTTON_OPACITY = 0.4
    action_bar_title = StringProperty()
    app_icon_filepath = StringProperty()
    page_source = StringProperty()
    has_story_links = BooleanProperty(defaultvalue=False)

    def __init__(
        self,
        font_manager: FontManager,
        on_close_screen: Callable[[], None],
        on_goto_story: GotoStory,
        **kwargs: str,
    ) -> None:
        super().__init__(**kwargs)

        self._font_manager = font_manager
        self._on_close_screen = on_close_screen
        self._on_goto_story = on_goto_story
        self._doc_dir: Path | None = None
        self._page_paths: list[Path] = []
        self._current_page_index = 0
        self._last_page_indexes: dict[Path, int] = {}
        self._story_links: list[StoryLink] = []
        self._story_dropdown: ReaderDropDown | None = None
        self._story_buttons: list[Button] = []
        self._story_picked_by_keyboard = False

        # Close stays the default, so Up then Enter still closes the document.
        self._setup_action_bar_nav(
            [self.ids.goto_story_button, self.ids.close_button], default_focus_idx=1
        )
        self._setup_dropdown_nav()

    def open_document(self, doc_dir: Path, title: str, *, resume: bool = False) -> None:
        """Open a folder of page images at its first page, or with `resume` at its last one.

        Args:
            doc_dir: The folder of page images.
            title: The title shown in the action bar.
            resume: Open at the page the document was last left on in this session.

        """
        self.action_bar_title = get_action_bar_title(self._font_manager, title)

        self._doc_dir = doc_dir
        self._page_paths = sorted(
            p for p in doc_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
        )
        last_index = self._last_page_indexes.get(doc_dir, 0) if resume else 0
        self._current_page_index = max(0, min(last_index, len(self._page_paths) - 1))
        logger.info(log_markers.DOCUMENT_OPENED.format(title=title, pages=len(self._page_paths)))
        self._update_page_source()

        Window.bind(on_key_down=self._on_key_down)

    def _update_page_source(self) -> None:
        if self._page_paths:
            page = self._page_paths[self._current_page_index]
            self.page_source = str(page)
            self._story_links = load_story_links(page)
            if self._doc_dir is not None:
                self._last_page_indexes[self._doc_dir] = self._current_page_index
            logger.debug(
                log_markers.DOCUMENT_PAGE.format(
                    page=self._current_page_index + 1,
                    pages=len(self._page_paths),
                    filename=page.name,
                )
            )
        else:
            self.page_source = ""
            self._story_links = []
        self.has_story_links = bool(self._story_links)

    def next_page(self) -> None:
        if self._current_page_index < len(self._page_paths) - 1:
            self._current_page_index += 1
            self._update_page_source()

    def prev_page(self) -> None:
        if self._current_page_index > 0:
            self._current_page_index -= 1
            self._update_page_source()

    def tap_target_regions(self) -> dict[str, Rect]:
        """Return the page's two halves, back and forward, for a GUI test to tap."""
        page = self.ids.doc_page
        half = page.width / 2
        return {
            "left half": window_rect(page, page.x, page.y, half, page.height),
            "right half": window_rect(page, page.x + half, page.y, page.width - half, page.height),
        }

    def on_touch_down(self, touch: MotionEvent) -> bool:
        self._clear_menu_on_touch()

        # Let action bar buttons handle their own touches first.
        if self.ids.doc_action_bar.collide_point(*touch.pos):
            return bool(super().on_touch_down(touch))

        if self.ids.doc_page.collide_point(*touch.pos):
            mid_x = self.ids.doc_page.center_x
            if touch.x < mid_x:
                self.prev_page()
            else:
                self.next_page()
            return True

        return bool(super().on_touch_down(touch))

    def _on_key_down(
        self, _window: object, key: int, _scancode: int, _codepoint: str, _modifier: list[str]
    ) -> bool:
        return self._handle_reader_key(key)

    def _reading_next_page(self) -> None:
        self.next_page()

    def _reading_prev_page(self) -> None:
        self.prev_page()

    # --- Go to Story ---

    def open_goto_story_from_bar(self) -> None:
        """Go to the page's story, or list its stories, from the bar button (a mouse press).

        A list opens as the keyboard opens it, in menu mode with the arrow keys live in it,
        so Left and Right do not turn pages under it (as the comic reader's Goto Page).
        """
        goto_idx = self._menu_buttons.index(self.ids.goto_story_button)
        entered_menu = not self._menu_mode
        if entered_menu:
            self._last_used_btn_idx = goto_idx
            self._enter_menu_mode()
        self._focused_btn_idx = goto_idx
        self._open_goto_story(keyboard_initiated=False)
        if entered_menu and self._menu_mode and not self._dropdown_nav_mode:
            self._exit_menu_mode()

    @override
    def _activate_focused_button(self) -> None:
        if self._menu_buttons[self._focused_btn_idx] is self.ids.goto_story_button:
            self._last_used_btn_idx = self._focused_btn_idx
            self._open_goto_story(keyboard_initiated=True)
        else:
            super()._activate_focused_button()

    def _open_goto_story(self, *, keyboard_initiated: bool) -> None:
        """Go to the only story on the page, or open the list of them; none does nothing."""
        if not self._story_links:
            return
        if len(self._story_links) == 1:
            self._goto_story(self._story_links[0], keyboard_initiated=keyboard_initiated)
            return
        self._clear_menu_focus()
        if not self._open_story_dropdown():
            self._update_menu_focus()
            return
        self._enter_dropdown_nav(initial_idx=0)

    def _open_story_dropdown(self) -> bool:
        dropdown = ReaderDropDown(
            auto_dismiss=True,
            dismiss_on_select=True,
            auto_width=False,
            width=STORY_DROPDOWN_WIDTH,
        )
        self._story_buttons = []
        for index, link in enumerate(self._story_links):
            button = Button(
                text=link.label, size_hint_y=None, height=STORY_BUTTON_HEIGHT, halign="left"
            )
            button.bind(on_press=lambda _btn, i=index: dropdown.select(i))
            dropdown.add_widget(button)
            self._story_buttons.append(button)
        dropdown.bind(on_select=self._on_story_selected, on_dismiss=self._on_story_list_dismissed)
        if not open_dropdown(dropdown, self.ids.goto_story_button):
            return False
        self._story_dropdown = dropdown
        return True

    def _on_story_selected(self, _dropdown: Widget, index: int) -> None:
        keyboard_initiated = self._story_picked_by_keyboard
        self._story_picked_by_keyboard = False
        link = self._story_links[index]
        # The list dismisses itself after this; leave the screen once it has.
        Clock.schedule_once(
            lambda _dt: self._goto_story(link, keyboard_initiated=keyboard_initiated), 0
        )

    def _on_story_list_dismissed(self, instance: Widget) -> None:
        self._story_dropdown = None
        self._on_dropdown_dismissed(instance)

    def _goto_story(self, link: StoryLink, *, keyboard_initiated: bool) -> None:
        logger.info(log_markers.DOCUMENT_GOTO_STORY.format(name=link.title.name, page=link.page))
        self.close()
        self._on_goto_story(link.title, link.page, keyboard_initiated=keyboard_initiated)

    @override
    def _activate_dropdown_item(self) -> None:
        self._story_picked_by_keyboard = True
        super()._activate_dropdown_item()

    @override
    def _get_dropdown_buttons(self) -> list[Button]:
        return self._story_buttons

    @override
    def _dismiss_dropdown(self) -> None:
        if self._story_dropdown is not None:
            self._story_dropdown.dismiss()

    def close(self) -> None:
        logger.debug(log_markers.DOCUMENT_CLOSING)
        if self._menu_mode:
            self._exit_menu_mode()
        Window.unbind(on_key_down=self._on_key_down)
        self._on_close_screen()


def get_document_reader_screen(
    screen_name: str,
    font_manager: FontManager,
    on_close_screen: Callable[[], None],
    on_goto_story: GotoStory,
) -> DocumentReaderScreen:
    Builder.load_file(str(DOCUMENT_READER_KV_FILE))

    return DocumentReaderScreen(
        font_manager,
        on_close_screen,
        on_goto_story,
        name=screen_name,
    )
