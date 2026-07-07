"""The Carl Barks Wiki screen: the OKF viewer embedded as a top-level app screen.

Hosts an ``okf_reader`` ``OKFViewer`` the way scripts/read_okf.py hosts it
standalone: the Barks knowledge comes from ``barks_reader.core.wiki_integration``
(backgrounds, tables, the story-page gate) plus the app's own fonts and icons
here. The viewer is built lazily on first open — the bundle path is a user
setting and may be absent — and its top bar's corner button closes the screen
(``TopBarSpec.on_close``) instead of quitting the app. Read Comic switches to
the app's comic reader screen via the supplied ``read_title`` callback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE
from barks_fantagraphics.comic_book_info import is_one_pager_located
from loguru import logger
from okf_reader.core.actions import PageAction
from okf_reader.core.top_bar import TopBarSpec
from okf_reader.ui.viewer import OKFViewer

from barks_reader.core.reader_consts_and_types import RAW_ACTION_BAR_SIZE_Y
from barks_reader.core.reader_formatter import get_action_bar_title
from barks_reader.core.wiki_integration import (
    WIKI_TITLE,
    BarksPanelsImageProvider,
    BarksTableRewriter,
    story_page_title,
)

from .reader_screens import ReaderScreen

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.comics_database import ComicsDatabase

    from barks_reader.core.image_selector import ImageSelector
    from barks_reader.core.reader_settings import ReaderSettings

    from .font_manager import FontManager

# The Barks screens' action-bar title green (MainScreen.ACTION_BAR_TITLE_COLOR).
_ACTION_BAR_TITLE_COLOR = (0.0, 1.0, 0.0, 1.0)


class _ReadComicActionProvider:
    """Offer "Read Comic" on wiki story pages (an okf_reader PageActionProvider).

    A page qualifies when the story-page gate maps it to a canonical title and
    the comics database can serve it (or it is a located one-pager, read via
    the "All One-Pagers" collection). Running the action hands the title to the
    app's ``read_title`` callback, which switches to the comic reader screen.
    """

    def __init__(
        self, comics_database: ComicsDatabase, read_title: Callable[[Titles], bool]
    ) -> None:
        self._comics_database = comics_database
        self._read_title = read_title

    def action_for(self, frontmatter: dict, page_path: Path) -> PageAction | None:
        """Return the "Read Comic" action for a readable story page, else None."""
        title_enum = story_page_title(frontmatter, page_path)
        if title_enum is None:
            return None
        found, _close = self._comics_database.is_story_title(ENUM_TO_STR_TITLE[title_enum])
        if not (found or is_one_pager_located(title_enum)):
            return None
        return PageAction("Read Comic", lambda: self._run_read_title(title_enum))

    def _run_read_title(self, title: Titles) -> None:
        # PageAction.run is () -> None; a failed open already reports via the
        # app's error handler, so the bool result has nothing to add here.
        self._read_title(title)


class WikiReaderScreen(ReaderScreen):
    """Top-level screen wrapping the OKF viewer on the configured wiki bundle."""

    def __init__(
        self,
        reader_settings: ReaderSettings,
        font_manager: FontManager,
        comics_database: ComicsDatabase,
        image_selector: ImageSelector,
        session_state_path: Path,
        read_title: Callable[[Titles], bool],
        on_close_screen: Callable[[], None],
        **kwargs: str,
    ) -> None:
        super().__init__(**kwargs)

        self._reader_settings = reader_settings
        self._font_manager = font_manager
        self._comics_database = comics_database
        self._image_selector = image_selector
        self._session_state_path = session_state_path
        self._read_title = read_title
        self._on_close_screen = on_close_screen

        self._viewer: OKFViewer | None = None
        self._bundle: Path | None = None

    def open_wiki(self, bundle: Path) -> None:
        """Show the wiki, building the viewer on first open (or on a bundle change).

        Lazy so an unconfigured or missing bundle costs the app nothing at
        startup; a changed bundle-path setting swaps the viewer for a fresh one.
        """
        if self._viewer is None or bundle != self._bundle:
            self._build_viewer(bundle)

    def close(self) -> None:
        """Save the reading position and hand control back to the main screen."""
        if self._viewer is not None:
            self._viewer.save_session()
        self._on_close_screen()

    def _build_viewer(self, bundle: Path) -> None:
        logger.info(f'Building wiki viewer for bundle "{bundle}".')
        if self._viewer is not None:
            self._viewer.save_session()  # the outgoing bundle's position survives
            self.remove_widget(self._viewer)
        self._viewer = OKFViewer(
            bundle,
            image_provider=BarksPanelsImageProvider(self._reader_settings, self._image_selector),
            table_rewriter=BarksTableRewriter(),
            action_provider=_ReadComicActionProvider(self._comics_database, self._read_title),
            top_bar=self._top_bar_spec(),
            state_path=self._session_state_path,
        )
        self._bundle = bundle
        self.add_widget(self._viewer)

    def _top_bar_spec(self) -> TopBarSpec:
        """Dress the viewer's bar like the Barks screens' action bars.

        The same pieces the standalone launcher uses, but ``on_close`` leaves
        this screen instead of stopping the app. The title markup bakes in the
        current font size (the bar is built lazily at first open, when the
        window height is settled).
        """
        sys_paths = self._reader_settings.sys_file_paths
        return TopBarSpec(
            title_markup=get_action_bar_title(self._font_manager, WIKI_TITLE),
            title_color=_ACTION_BAR_TITLE_COLOR,
            icon_path=sys_paths.get_barks_reader_app_window_icon_path(),
            back_icon_path=sys_paths.get_barks_reader_go_back_icon_file(),
            close_icon_path=sys_paths.get_barks_reader_close_icon_file(),
            height=RAW_ACTION_BAR_SIZE_Y,
            on_close=self.close,
        )


def get_wiki_reader_screen(
    screen_name: str,
    reader_settings: ReaderSettings,
    font_manager: FontManager,
    comics_database: ComicsDatabase,
    image_selector: ImageSelector,
    session_state_path: Path,
    read_title: Callable[[Titles], bool],
    on_close_screen: Callable[[], None],
) -> WikiReaderScreen:
    """Build the wiki reader screen (no kv file — the viewer renders itself)."""
    return WikiReaderScreen(
        reader_settings,
        font_manager,
        comics_database,
        image_selector,
        session_state_path,
        read_title,
        on_close_screen,
        name=screen_name,
    )
