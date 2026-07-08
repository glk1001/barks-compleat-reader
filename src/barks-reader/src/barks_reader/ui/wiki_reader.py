"""The Carl Barks Wiki screen: the OKF viewer embedded as a top-level app screen.

Hosts an ``okf_reader`` ``OKFViewer`` the way scripts/read_okf.py hosts it
standalone: the Barks knowledge comes from ``barks_reader.core.wiki_integration``
(backgrounds, tables, the story-page gate) plus the app's own fonts and icons
here. The viewer is built lazily on first open — the bundle path is a user
setting and may be absent — and its top bar's corner button closes the screen
(``TopBarSpec.on_close``) instead of quitting the app. A story page's
"Goto Title" action closes the wiki and hands the title to the supplied
``goto_title`` callback — the index screens' ``on_goto_title`` behavior:
select the title in the main tree and set the bottom title view.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kivy.core.window import Window
from loguru import logger
from okf_reader.core.actions import PageAction
from okf_reader.ui.viewer import OKFViewer

from barks_reader.core.wiki_integration import (
    BarksPanelsImageProvider,
    BarksTableRewriter,
    tree_navigable_title,
    wiki_session_path,
    wiki_top_bar_spec,
)

from .reader_keyboard_nav import KEY_ESCAPE, KEY_F, KEY_LEFT, is_escape_key
from .reader_screens import ReaderScreen

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from barks_fantagraphics.barks_titles import Titles

    from barks_reader.core.image_selector import ImageSelector
    from barks_reader.core.reader_settings import ReaderSettings

    from .font_manager import FontManager


class _GotoTitleActionProvider:
    """Offer "Goto Title" on wiki story pages (an okf_reader PageActionProvider).

    A page qualifies when the gate maps it to a canonical title with a place in
    the main tree (`tree_navigable_title` — Extras articles are excluded; they
    have no chronological position to navigate to). Running the action hands
    the title to ``goto_title`` (the wiki screen's close-and-navigate handler).
    """

    def __init__(self, goto_title: Callable[[Titles], None]) -> None:
        self._goto_title = goto_title

    def action_for(self, frontmatter: dict[str, Any], page_path: Path) -> PageAction | None:
        """Return the "Goto Title" action for a navigable story page, else None."""
        title_enum = tree_navigable_title(frontmatter, page_path)
        if title_enum is None:
            return None
        return PageAction("Goto Title", lambda: self._goto_title(title_enum))


class WikiReaderScreen(ReaderScreen):
    """Top-level screen wrapping the OKF viewer on the configured wiki bundle."""

    def __init__(
        self,
        reader_settings: ReaderSettings,
        font_manager: FontManager,
        image_selector: ImageSelector,
        app_data_dir: Path,
        on_goto_title: Callable[[Titles], None],
        on_close_screen: Callable[[], None],
        **kwargs: str,
    ) -> None:
        super().__init__(**kwargs)

        self._reader_settings = reader_settings
        self._font_manager = font_manager
        self._image_selector = image_selector
        self._app_data_dir = app_data_dir
        self._on_goto_title = on_goto_title
        self._on_close_screen = on_close_screen

        self._viewer: OKFViewer | None = None
        self._bundle: Path | None = None

    def open_wiki(self, bundle: Path, page: Path | None = None) -> None:
        """Show the wiki, building the viewer on first open (or on a bundle change).

        Lazy so an unconfigured or missing bundle costs the app nothing at
        startup; a changed bundle-path setting swaps the viewer for a fresh one.

        Args:
            bundle: The wiki OKF bundle directory.
            page: A bundle page to land on; None keeps/restores the current page.

        """
        if self._viewer is None or bundle != self._bundle:
            self._build_viewer(bundle, start_page=page)
        else:
            # Re-root the history at the landing page so Back from it exits the
            # reader (via on_exit) rather than walking a previous visit's trail.
            self._viewer.reset_to(page)
        # Route the window's back keys here while this screen is up; unbind on close.
        # Unbind first so a re-open without an intervening close can't double-bind.
        Window.unbind(on_key_down=self._on_key_down)
        Window.bind(on_key_down=self._on_key_down)

    def close(self) -> None:
        """Save the reading position and hand control back to the main screen.

        The single exit funnel: the corner Quit button, "Goto Title", and Back at
        the history root all route here, so unbinding the keyboard here covers
        every way out.
        """
        Window.unbind(on_key_down=self._on_key_down)
        self.save_session()
        self._on_close_screen()

    def _on_key_down(
        self, _window: object, key: int, _scancode: int, _codepoint: str, modifiers: list[str]
    ) -> bool:
        """Route Ctrl+F to search and Escape/Alt+Left to the viewer's Back, consuming the key.

        Escape honors the user-configured alternate Escape via ``is_escape_key``,
        and backs out of an active search before navigating. Consuming (returning
        True) keeps the key from leaking to the main screen's handler. At the
        history root Back exits the reader (the viewer's on_exit).
        """
        if self._viewer is None:
            return False
        if key == KEY_F and "ctrl" in modifiers:
            self._viewer.focus_search()
            return True
        # While the search field owns the keyboard, keystrokes must reach it: only
        # a real Escape acts (backing out of the search). The user-configurable
        # alternate Escape is often an ordinary letter (e.g. "r") and must still
        # type into the field, and Alt+Left must not be stolen mid-typing.
        if self._viewer.search_focused:
            if key == KEY_ESCAPE:
                self._viewer.escape_search()
                return True
            return False
        return self._handle_nav_key(key, modifiers)

    def _handle_nav_key(self, key: int, modifiers: list[str]) -> bool:
        """Handle a back-navigation key when the search field is not focused."""
        assert self._viewer is not None
        if is_escape_key(key):
            if self._viewer.escape_search():
                return True
            self._viewer.go_back()
            return True
        if key == KEY_LEFT and "alt" in modifiers:
            self._viewer.go_back()
            return True
        return False

    def save_session(self) -> None:
        """Persist the reading position (a no-op before the first open).

        Besides `close`, the app calls this from its stop hook, so quitting
        while the wiki screen is open doesn't lose the resume point.
        """
        if self._viewer is not None:
            self._viewer.save_session()

    def _goto_title(self, title: Titles) -> None:
        # Land the user on the main screen with the title selected in the tree
        # and shown in the bottom title view — the reading controls live there.
        self.close()
        self._on_goto_title(title)

    def _build_viewer(self, bundle: Path, start_page: Path | None = None) -> None:
        logger.info(f'Building wiki viewer for bundle "{bundle}".')
        if self._viewer is not None:
            self._viewer.save_session()  # the outgoing bundle's position survives
            self.remove_widget(self._viewer)
        # The shared bar builder; on_close leaves this screen instead of
        # stopping the app. The title markup bakes in the current font size
        # (built lazily at first open, when the window height is settled).
        self._viewer = OKFViewer(
            bundle,
            start_page=start_page,
            image_provider=BarksPanelsImageProvider(self._reader_settings, self._image_selector),
            table_rewriter=BarksTableRewriter(),
            action_provider=_GotoTitleActionProvider(self._goto_title),
            top_bar=wiki_top_bar_spec(
                self._font_manager, self._reader_settings.sys_file_paths, on_close=self.close
            ),
            state_path=wiki_session_path(self._app_data_dir, bundle),
            on_exit=self.close,
        )
        self._bundle = bundle
        self.add_widget(self._viewer)


def get_wiki_reader_screen(
    screen_name: str,
    reader_settings: ReaderSettings,
    font_manager: FontManager,
    image_selector: ImageSelector,
    app_data_dir: Path,
    on_goto_title: Callable[[Titles], None],
    on_close_screen: Callable[[], None],
) -> WikiReaderScreen:
    """Build the wiki reader screen (no kv file — the viewer renders itself)."""
    return WikiReaderScreen(
        reader_settings,
        font_manager,
        image_selector,
        app_data_dir,
        on_goto_title,
        on_close_screen,
        name=screen_name,
    )
