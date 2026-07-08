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

from typing import TYPE_CHECKING

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

    def action_for(self, frontmatter: dict, page_path: Path) -> PageAction | None:
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
        elif page is not None:
            self._viewer.show_page(page)

    def close(self) -> None:
        """Save the reading position and hand control back to the main screen."""
        self.save_session()
        self._on_close_screen()

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
