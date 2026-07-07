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

    from barks_reader.core.image_selector import ImageSelector
    from barks_reader.core.reader_settings import ReaderSettings

    from .font_manager import FontManager

# The Barks screens' action-bar title green (MainScreen.ACTION_BAR_TITLE_COLOR).
_ACTION_BAR_TITLE_COLOR = (0.0, 1.0, 0.0, 1.0)


class _GotoTitleActionProvider:
    """Offer "Goto Title" on wiki story pages (an okf_reader PageActionProvider).

    A page qualifies when the story-page gate maps it to a canonical title with
    a Fantagraphics entry — every such title has a place in the main tree.
    Running the action hands the title to ``goto_title`` (the wiki screen's
    close-and-navigate handler).
    """

    def __init__(self, goto_title: Callable[[Titles], None]) -> None:
        self._goto_title = goto_title

    def action_for(self, frontmatter: dict, page_path: Path) -> PageAction | None:
        """Return the "Goto Title" action for a story page, else None."""
        title_enum = story_page_title(frontmatter, page_path)
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
        session_state_path: Path,
        on_goto_title: Callable[[Titles], None],
        on_close_screen: Callable[[], None],
        **kwargs: str,
    ) -> None:
        super().__init__(**kwargs)

        self._reader_settings = reader_settings
        self._font_manager = font_manager
        self._image_selector = image_selector
        self._session_state_path = session_state_path
        self._on_goto_title = on_goto_title
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

    def _goto_title(self, title: Titles) -> None:
        # Land the user on the main screen with the title selected in the tree
        # and shown in the bottom title view — the reading controls live there.
        self.close()
        self._on_goto_title(title)

    def _build_viewer(self, bundle: Path) -> None:
        logger.info(f'Building wiki viewer for bundle "{bundle}".')
        if self._viewer is not None:
            self._viewer.save_session()  # the outgoing bundle's position survives
            self.remove_widget(self._viewer)
        self._viewer = OKFViewer(
            bundle,
            image_provider=BarksPanelsImageProvider(self._reader_settings, self._image_selector),
            table_rewriter=BarksTableRewriter(),
            action_provider=_GotoTitleActionProvider(self._goto_title),
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
    image_selector: ImageSelector,
    session_state_path: Path,
    on_goto_title: Callable[[Titles], None],
    on_close_screen: Callable[[], None],
) -> WikiReaderScreen:
    """Build the wiki reader screen (no kv file — the viewer renders itself)."""
    return WikiReaderScreen(
        reader_settings,
        font_manager,
        image_selector,
        session_state_path,
        on_goto_title,
        on_close_screen,
        name=screen_name,
    )
