from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, override

from barks_kivy_ui.scrolling import ReaderDropDown
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    NumericProperty,
    StringProperty,
)
from kivy.uix.button import Button
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.display_unit import DisplayUnit, build_document_units
from barks_reader.core.document_chapters import PAGE_IMAGE_EXTENSIONS
from barks_reader.core.document_links import StoryLink, load_story_links
from barks_reader.core.main_layout import MainLayoutMode
from barks_reader.core.reader_formatter import get_action_bar_title
from barks_reader.core.reader_utils import COMIC_PAGE_ASPECT_RATIO

from .action_bar_helpers import (
    ACTION_BAR_SIZE_Y,
    ActionBarVisibility,
    is_action_bar_visible,
    set_action_bar_visibility,
    set_fullscreen_button,
)
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

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_titles import Titles
    from kivy.input import MotionEvent
    from kivy.uix.actionbar import ActionBar
    from kivy.uix.widget import Widget

    from barks_reader.core.reader_settings import ReaderSettings

    from .font_manager import FontManager

DOCUMENT_READER_KV_FILE = Path(__file__).with_suffix(".kv")

STORY_BUTTON_HEIGHT = dp(30)
STORY_DROPDOWN_WIDTH = dp(420)


class GotoStory(Protocol):
    """Select a story with a page of it offered (``MainScreen.goto_title_from_document``)."""

    def __call__(self, title: Titles, page: str, *, keyboard_initiated: bool) -> None: ...


class DocumentReaderScreen(ReaderScreen, ReaderCloseMixin, DropdownNavMixin, ActionBarNavMixin):
    """A folder of page images, turned by tap or arrow key.

    A page may name the stories its figures come from (``core.document_links``). "Go to
    Story" then closes the document and selects the story with the figure's page offered: at
    once for one story, from a list for several. The button is greyed on a page with none.

    Each document's last page is kept until the app quits, so one opened to resume (an
    illustrated-history chapter, from its node or from Go Back after a story) comes back at
    the page it was left on.

    On the two-page spread the pages show two at a time, paired from the first (a
    document has no cover: ``core.display_unit.build_document_units``), in a box twice a
    page wide with the bar over it, and Go to Story offers both pages' stories; a turn
    moves a pair. An odd last page sits alone in the middle of the box, as the comic
    reader's does.

    The bar's Fullscreen works as the comic reader's: fullscreen hides the bar, and the
    pages take its room; a tap on the top margin, or Escape, brings it back. A document
    never goes fullscreen on its own (the comic reader's setting does not reach it), and
    closing returns the window to the mode the document opened in, waiting for the
    screen to be laid out for it (``ReaderCloseMixin``, the comic reader's too).
    """

    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
    ASPECT_RATIO = COMIC_PAGE_ASPECT_RATIO
    GREYED_BUTTON_OPACITY = 0.4
    action_bar_title = StringProperty()
    app_icon_filepath = StringProperty()
    is_fullscreen = BooleanProperty(defaultvalue=False)
    # The main screen's layout ("single" or "spread"); the app sets it, the kv file
    # widens the page box to the pair for the spread (`pages_across`).
    layout_mode = StringProperty(MainLayoutMode.SINGLE.value)
    pages_across = NumericProperty(1)
    page_source = StringProperty()
    right_page_source = StringProperty()
    has_story_links = BooleanProperty(defaultvalue=False)

    def __init__(
        self,
        reader_settings: ReaderSettings,
        font_manager: FontManager,
        window_manager: WindowManager,
        on_close_screen: Callable[[], None],
        on_goto_story: GotoStory,
        **kwargs: str,
    ) -> None:
        super().__init__(**kwargs)

        self._font_manager = font_manager
        self._on_close_screen = on_close_screen
        self._on_goto_story = on_goto_story

        # The window-mode engine is shared with the main and comic screens (one geometry
        # store); this controller carries this screen's completion callbacks.
        self._mode = WindowModeController(
            DocumentReaderScreen.__name__,
            window_manager,
            WindowModeCallbacks(
                on_windowed_first_resize=self._set_hints_for_windowed_mode,
                on_finished_windowed=self._on_finished_goto_windowed_mode,
                on_finished_fullscreen=self._on_finished_goto_fullscreen_mode,
            ),
        )
        sys_file_paths = reader_settings.sys_file_paths
        self._fullscreen_icon = str(sys_file_paths.get_barks_reader_fullscreen_icon_file())
        self._fullscreen_exit_icon = str(
            sys_file_paths.get_barks_reader_fullscreen_exit_icon_file()
        )
        self._was_fullscreen_on_entry = False
        self._is_closing = False
        # What runs once the screen has gone (`close`), e.g. Go to Story's navigation.
        self._after_close: Callable[[], None] | None = None
        self._doc_dir: Path | None = None
        self._page_paths: list[Path] = []
        self._units: list[DisplayUnit] = []
        self._unit_idx_for_index: dict[int, int] = {}
        self._current_page_index = 0
        self._last_page_indexes: dict[Path, int] = {}
        self._story_links: list[StoryLink] = []
        self._story_dropdown: ReaderDropDown | None = None
        self._story_buttons: list[Button] = []
        self._story_picked_by_keyboard = False

        # Close stays the default, so Escape then Enter still closes the document.
        self._setup_action_bar_nav(
            [self.ids.fullscreen_button, self.ids.goto_story_button, self.ids.close_button],
            default_focus_idx=2,
        )
        self._setup_dropdown_nav()

    @property
    @override
    def drag_region(self) -> Widget | None:
        # The bar is the page's width, centred: it takes the window-drag hit test over.
        return self.ids.doc_action_bar.drag_region

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
            p for p in doc_dir.iterdir() if p.suffix.lower() in PAGE_IMAGE_EXTENSIONS
        )
        self._units, self._unit_idx_for_index = build_document_units(len(self._page_paths))
        last_index = self._last_page_indexes.get(doc_dir, 0) if resume else 0
        self._current_page_index = max(0, min(last_index, len(self._page_paths) - 1))
        logger.info(log_markers.DOCUMENT_OPENED.format(title=title, pages=len(self._page_paths)))
        self._update_page_source()

        # The mode the window is in, to come back to on close; a document never goes
        # fullscreen on its own.
        self._was_fullscreen_on_entry = bool(WindowManager.is_fullscreen_now())
        self.is_fullscreen = self._was_fullscreen_on_entry
        self._update_widget_states()

        Window.bind(on_key_down=self._on_key_down)

    def on_layout_mode(self, _instance: Widget, _mode: str) -> None:
        """Show the current page as the new layout shows it: alone, or with its pair.

        A closed reader has no pages (`close`), so a change under it shows nothing.
        """
        if self._page_paths:
            self._update_page_source()

    def _current_unit(self) -> DisplayUnit:
        """Return what the current page shows: itself alone, or its pair on the spread."""
        if self.layout_mode == MainLayoutMode.SPREAD.value:
            return self._units[self._unit_idx_for_index[self._current_page_index]]
        return DisplayUnit(self._current_page_index, None)

    def _update_page_source(self) -> None:
        if not self._page_paths:
            self.page_source = ""
            self.right_page_source = ""
            self._story_links = []
            self.has_story_links = False
            return

        unit = self._current_unit()
        self._current_page_index = unit.left_page_index
        page = self._page_paths[unit.left_page_index]
        right_page = (
            None if unit.right_page_index is None else self._page_paths[unit.right_page_index]
        )
        self.page_source = str(page)
        self.right_page_source = "" if right_page is None else str(right_page)
        self._story_links = load_story_links(page)
        if right_page is not None:
            self._story_links += load_story_links(right_page)
        if self._doc_dir is not None:
            self._last_page_indexes[self._doc_dir] = self._current_page_index
        pages = len(self._page_paths)
        logger.debug(
            log_markers.DOCUMENT_PAGE.format(
                page=unit.left_page_index + 1, pages=pages, filename=page.name
            )
        )
        if unit.right_page_index is not None and right_page is not None:
            logger.debug(
                log_markers.DOCUMENT_RIGHT_PAGE.format(
                    page=unit.right_page_index + 1, pages=pages, filename=right_page.name
                )
            )
        self.has_story_links = bool(self._story_links)

    def next_page(self) -> None:
        unit = self._current_unit()
        last_shown = (
            unit.left_page_index if unit.right_page_index is None else unit.right_page_index
        )
        if last_shown < len(self._page_paths) - 1:
            self._current_page_index = last_shown + 1
            self._update_page_source()

    def prev_page(self) -> None:
        # The page before the unit's first; on the spread its unit shows (its pair).
        if self._current_page_index > 0:
            self._current_page_index -= 1
            self._update_page_source()

    def tap_target_regions(self) -> dict[str, Rect]:
        """Return the page box's two halves, back and forward, for a GUI test to tap."""
        page = self.ids.doc_page
        half = page.width / 2
        return {
            "left half": window_rect(page, page.x, page.y, half, page.height),
            "right half": window_rect(page, page.x + half, page.y, page.width - half, page.height),
        }

    def on_touch_down(self, touch: MotionEvent) -> bool:
        if self._is_closing:
            return True  # as for keys (_on_key_down): nothing left to act on
        self._clear_menu_on_touch()

        # Let action bar buttons handle their own touches first.
        if self.ids.doc_action_bar.collide_point(*touch.pos):
            return bool(super().on_touch_down(touch))

        # A hidden bar (fullscreen) comes back on a tap along the top, where it was.
        if self._is_action_bar_hidden() and self._is_touch_in_top_margin(touch):
            logger.debug(log_markers.ACTION_BAR_SHOWN_ON_TOP_MARGIN)
            self._show_action_bar()
            return True

        if self.ids.doc_page.collide_point(*touch.pos):
            mid_x = self.ids.doc_page.center_x
            if touch.x < mid_x:
                self.prev_page()
            else:
                self.next_page()
            return True

        return bool(super().on_touch_down(touch))

    def _is_touch_in_top_margin(self, touch: MotionEvent) -> bool:
        return touch.y > self.top - self.ACTION_BAR_HEIGHT

    def _on_key_down(
        self, _window: object, key: int, _scancode: int, _codepoint: str, _modifier: list[str]
    ) -> bool:
        if self._is_closing:
            # Leaving fullscreen on the way out takes a moment, with the document already
            # closed: a page turn or bar action now has nothing to act on.
            return True
        return self._handle_reader_key(key)

    # --- The window mode and the bar ---

    def toggle_screen_mode(self) -> None:
        """Switch the window to the other mode, from the bar's Fullscreen button."""
        self._mode.toggle()

    def _on_finished_goto_windowed_mode(self) -> None:
        self.is_fullscreen = False
        self._update_widget_states()
        logger.info(log_markers.ENTERED_WINDOWED.format(screen=DocumentReaderScreen.__name__))
        log_window_geometry("DocumentReaderScreen windowed")
        if self._is_closing:
            logger.debug("Entering windowed mode finished, now closing the document reader.")
            self._finish_closing_once_laid_out()

    def _on_finished_goto_fullscreen_mode(self) -> None:
        self.is_fullscreen = self._is_fullscreen_now_after_goto()
        self._update_widget_states()
        logger.info(log_markers.ENTERED_FULLSCREEN.format(screen=DocumentReaderScreen.__name__))
        log_window_geometry("DocumentReaderScreen fullscreen")
        if self._is_closing:
            logger.debug("Entering fullscreen mode finished, now closing the document reader.")
            self._finish_closing_once_laid_out()

    def _update_widget_states(self) -> None:
        visibility = (
            ActionBarVisibility.HIDDEN if self.is_fullscreen else ActionBarVisibility.VISIBLE
        )
        set_action_bar_visibility(self.ids.doc_action_bar, visibility)
        set_fullscreen_button(
            self.ids.fullscreen_button,
            is_fullscreen=self.is_fullscreen,
            fullscreen_icon=self._fullscreen_icon,
            fullscreen_exit_icon=self._fullscreen_exit_icon,
        )

    @override
    def _reader_action_bar(self) -> ActionBar:
        return self.ids.doc_action_bar

    @override
    def _is_action_bar_hidden(self) -> bool:
        return not is_action_bar_visible(self.ids.doc_action_bar)

    @override
    def _on_action_bar_shown_for_menu(self) -> None:
        self._show_action_bar()

    @override
    def _on_action_bar_hidden_after_menu(self) -> None:
        if self.is_fullscreen:
            self._hide_action_bar()

    def _reading_next_page(self) -> None:
        self.next_page()

    def _reading_prev_page(self) -> None:
        self.prev_page()

    # --- Go to Story ---

    def open_goto_story_from_bar(self) -> None:
        """Go to the page's story, or list its stories, from the bar button (a mouse press).

        A list opens as the keyboard opens it, with the arrow keys live in it, so Left and
        Right do not turn pages under it (as the comic reader's Goto Page).
        """
        self._open_list_from_bar(
            self.ids.goto_story_button, partial(self._open_goto_story, keyboard_initiated=False)
        )

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
        # A selection has read the flag by now; a list left without one must not
        # leave it set for the next pick by mouse.
        self._story_picked_by_keyboard = False
        self._on_dropdown_dismissed(instance)

    def _goto_story(self, link: StoryLink, *, keyboard_initiated: bool) -> None:
        logger.info(log_markers.DOCUMENT_GOTO_STORY.format(name=link.title.name, page=link.page))
        # Once the document has gone: a close from a changed window mode waits for the
        # window to come back, and the main screen's navigation must come after it.
        self.close(
            then=lambda: self._on_goto_story(
                link.title, link.page, keyboard_initiated=keyboard_initiated
            )
        )

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

    def close(self, then: Callable[[], None] | None = None) -> None:
        """Close the document, returning the window to the mode it was opened in.

        Args:
            then: Called once the screen has gone: at once, or after the window mode
                change a close from a changed mode waits for.

        """
        if self._is_closing:
            return
        logger.debug(log_markers.DOCUMENT_CLOSING)
        if self._menu_mode:
            self._exit_menu_mode()
        # No pages: a layout change under a closed reader laid the document out again
        # and moved its resume page (2026-10-30). The resume pages stay (`open_document`).
        self._page_paths = []

        self._after_close = then
        if bool(WindowManager.is_fullscreen_now()) == self._was_fullscreen_on_entry:
            self._finish_closing()
            return
        # The window changed mode under the document: back to the mode it opened in,
        # and the screen leaves once laid out for it (the mode's finish callback). The
        # keys stay bound till then, for `_on_key_down` to swallow.
        self._is_closing = True
        if self._was_fullscreen_on_entry:
            self._mode.goto_fullscreen()
        else:
            self._mode.goto_windowed()

    @override
    def _finish_closing(self) -> None:
        Window.unbind(on_key_down=self._on_key_down)
        self._is_closing = False
        self._on_close_screen()
        after_close, self._after_close = self._after_close, None
        if after_close is not None:
            after_close()


def get_document_reader_screen(
    screen_name: str,
    reader_settings: ReaderSettings,
    font_manager: FontManager,
    window_manager: WindowManager,
    on_close_screen: Callable[[], None],
    on_goto_story: GotoStory,
) -> DocumentReaderScreen:
    Builder.load_file(str(DOCUMENT_READER_KV_FILE))

    return DocumentReaderScreen(
        reader_settings,
        font_manager,
        window_manager,
        on_close_screen,
        on_goto_story,
        name=screen_name,
    )
