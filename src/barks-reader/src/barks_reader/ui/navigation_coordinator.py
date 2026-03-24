"""NavigationCoordinator: single entry-point for all title navigation and content-opening flows.

Extracted from MainScreen to eliminate the God Object pattern where MainScreen defined ~10 private
callback methods that mediated between TreeViewManager, ViewStateManager, and ComicReaderManager.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from barks_fantagraphics.barks_tags import BARKS_TAGGED_PAGES, TagGroups, Tags
from barks_fantagraphics.barks_titles import (
    BARKS_TITLE_DICT,
    BARKS_TITLES,
    NON_COMIC_TITLES,
    ComicBookInfo,
    Titles,
)
from barks_fantagraphics.comics_database import TitleNotFoundError
from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    SERIES_EXTRAS,
    FantaComicBookInfo,
    get_fanta_info,
)
from loguru import logger

from barks_reader.core.image_selector import ImageInfo
from barks_reader.core.reader_consts_and_types import CHRONO_YEAR_RANGES, COMIC_BEGIN_PAGE
from barks_reader.core.reader_tree_view_utils import find_tree_view_title_node
from barks_reader.ui.user_error_handler import ErrorInfo, ErrorTypes, TitleNotInFantaInfoError
from barks_reader.ui.view_states import ViewStates

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from barks_fantagraphics.comic_book import ComicBook
    from barks_fantagraphics.comics_database import ComicsDatabase
    from comic_utils.comic_consts import PanelPath

    from barks_reader.core.reader_settings import ReaderSettings
    from barks_reader.core.special_overrides_handler import SpecialFantaOverrides
    from barks_reader.ui.bottom_title_view_screen import BottomTitleViewScreen
    from barks_reader.ui.comic_reader_manager import ComicReaderManager
    from barks_reader.ui.json_settings_manager import SavedPageInfo
    from barks_reader.ui.reader_screens import ScreenSwitchers
    from barks_reader.ui.reader_ui_classes import BaseTreeViewNode, ButtonTreeViewNode
    from barks_reader.ui.tree_view_manager import TreeViewManager
    from barks_reader.ui.tree_view_screen import TreeViewScreen
    from barks_reader.ui.user_error_handler import UserErrorHandler
    from barks_reader.ui.view_state_manager import ViewStateManager


@dataclass(frozen=True, slots=True)
class TitleTarget:
    """Immutable description of a title navigation target.

    Replaces the diverse callback signatures that MainScreen previously passed
    to TreeViewManager and other components.
    """

    fanta_info: FantaComicBookInfo
    title_image_file: PanelPath | None = None
    tag: Tags | TagGroups | None = None
    page_to_goto: str = ""


class NavigationCoordinator:
    """Single entry-point for all flows that navigate to a title or open content.

    Owns the wiring between ViewStateManager, TreeViewManager, ComicReaderManager,
    and the screen widgets. MainScreen delegates to this instead of defining ~10
    private callback methods.
    """

    def __init__(
        self,
        reader_settings: ReaderSettings,
        comics_database: ComicsDatabase,
        view_state_manager: ViewStateManager,
        comic_reader_manager: ComicReaderManager,
        bottom_title_view_screen: BottomTitleViewScreen,
        tree_view_screen: TreeViewScreen,
        screen_switchers: ScreenSwitchers,
        special_fanta_overrides: SpecialFantaOverrides,
        user_error_handler: UserErrorHandler,
        on_active_changed: Callable[[bool], None],
    ) -> None:
        self._reader_settings = reader_settings
        self._comics_database = comics_database
        self._view_state_manager = view_state_manager
        self._comic_reader_manager = comic_reader_manager
        self._bottom_title_view_screen = bottom_title_view_screen
        self._tree_view_screen = tree_view_screen
        self._screen_switchers = screen_switchers
        self._special_fanta_overrides = special_fanta_overrides
        self._user_error_handler = user_error_handler
        self._on_active_changed = on_active_changed

        self._tree_view_manager: TreeViewManager | None = None
        self._year_range_nodes: dict[tuple[int, int], ButtonTreeViewNode] = {}
        self._current_fanta_info: FantaComicBookInfo | None = None
        self._read_comic_view_state: ViewStates | None = None
        self._doc_reader_close_view_state: ViewStates | None = None

    def set_tree_view_manager(self, tree_view_manager: TreeViewManager) -> None:
        """Set the TreeViewManager (deferred to break circular dependency)."""
        self._tree_view_manager = tree_view_manager

    def set_year_range_nodes(
        self, year_range_nodes: dict[tuple[int, int], ButtonTreeViewNode]
    ) -> None:
        """Set year-range nodes (deferred — populated after tree build)."""
        self._year_range_nodes = year_range_nodes

    # === State queries ===

    @property
    def current_fanta_info(self) -> FantaComicBookInfo | None:
        """The currently selected title, if any."""
        return self._current_fanta_info

    # === Primary path: tree-view title selection ===

    def select_title(self, target: TitleTarget) -> None:
        """Handle 'user picked a title from the tree view'.

        Sets the title on ViewStateManager, updates view state to ON_TITLE_NODE,
        configures goto-page checkbox, and handles tag-page navigation if a tag
        is provided.
        """
        self._current_fanta_info = target.fanta_info
        self._set_title(target.title_image_file)
        self._view_state_manager.update_view_for_node_with_title(ViewStates.ON_TITLE_NODE)

        if target.tag is not None:
            self._set_tag_goto_page_checkbox(
                target.tag,
                self._current_fanta_info.comic_book_info.get_title_str(),
            )

    # === Navigation paths ===

    def navigate_to_chrono_title(self, image_info: ImageInfo) -> None:
        """Navigate to a title's chronological position from a background image.

        Resolves the year-range node, opens the tree to the correct position,
        then updates the title view.
        """
        assert image_info.from_title is not None

        logger.debug(f'Goto title: "{image_info.from_title.name}", "{image_info.filename}".')
        title_fanta_info = self._get_fanta_info(image_info.from_title)

        title_year_range = self._get_year_range_from_info(title_fanta_info)
        if title_year_range is None:
            msg = f"No year range found for {title_fanta_info.comic_book_info.get_title_str()}."
            raise RuntimeError(msg)
        year_node = self._year_range_nodes.get(title_year_range)
        if not year_node:
            msg = f"No year node found for range '{title_year_range}'."
            raise RuntimeError(msg)

        year_node.ensure_populated()
        logger.debug(f"For range {title_year_range}, year node has {len(year_node.nodes)} nodes.")

        assert self._tree_view_manager is not None

        # Save the currently selected node so Back can return to it.
        back_node = self._tree_view_screen.get_selected_node()

        self._tree_view_manager.deselect_and_close_open_nodes()

        # Restore the back node after deselect_and_close_open_nodes resets selection tracking.
        if back_node is not None:
            self._tree_view_screen.ids.reader_tree_view.set_back_node(back_node)

        self._tree_view_manager.open_all_parent_nodes(year_node)
        title_node = cast(
            "BaseTreeViewNode",
            find_tree_view_title_node(year_node.nodes, image_info.from_title),
        )
        self._tree_view_manager.goto_node(title_node, scroll_to=True)

        self._title_row_selected(title_fanta_info, image_info.filename)

    def navigate_to_title_with_page(self, image_info: ImageInfo, page_to_goto: str) -> None:
        """Navigate to a title and set a specific page (from index screens).

        Delegates to navigate_to_chrono_title, then sets the goto-page checkbox.
        """
        if image_info.from_title in NON_COMIC_TITLES:
            self.read_article(image_info.from_title, ViewStates.ON_INDEX_NODE)
            return

        self.navigate_to_chrono_title(image_info)

        if page_to_goto:
            logger.debug(f"Setting page to goto: {page_to_goto}.")
            self._bottom_title_view_screen.set_goto_page_state(page_to_goto, active=True)

    def navigate_to_search_result(self, title_str: str) -> bool:
        """Navigate to a title from search results.

        Args:
            title_str: The display title string from the search screen.

        Returns:
            False if the title was not found in the title dictionary.

        """
        title_str = ComicBookInfo.get_title_str_from_display_title(title_str)
        if title_str not in BARKS_TITLE_DICT:
            logger.debug(f'Search goto title: not found: "{title_str}".')
            return False
        title = BARKS_TITLE_DICT[title_str]
        image_info = ImageInfo(from_title=title, filename=None)
        self.navigate_to_chrono_title(image_info)
        return True

    def update_title(self, title_str: str) -> bool:
        """Update the current title from a tree view text label.

        Args:
            title_str: The display title string from the tree view.

        Returns:
            False if the title is not configured or is in the EXTRAS series.

        """
        logger.debug(f'Update title: "{title_str}".')
        assert title_str != ""

        title_str = ComicBookInfo.get_title_str_from_display_title(title_str)

        if title_str not in ALL_FANTA_COMIC_BOOK_INFO:
            logger.debug(f'Update title: Not configured yet: "{title_str}".')
            return False

        next_fanta_info = ALL_FANTA_COMIC_BOOK_INFO[title_str]
        if next_fanta_info.series_name == SERIES_EXTRAS:
            logger.debug(f'Title is in EXTRA series: "{title_str}".')
            return False

        self._current_fanta_info = next_fanta_info
        self._set_title()

        return True

    # === Content-opening paths ===

    def read_comic(self) -> bool:
        """Open the currently selected title in the comic reader.

        Returns:
            True if the comic was successfully opened, False on error.

        """
        try:
            comic_book = self._get_comic_book()
        except TitleNotFoundError as e:
            logger.error(e)
            error_info = ErrorInfo(file_volume=-1, title=BARKS_TITLE_DICT[e.title])
            self._user_error_handler.handle_error(ErrorTypes.ArchiveVolumeNotAvailable, error_info)
            return False

        self._on_active_changed(False)  # noqa: FBT003
        self._read_comic_view_state = None

        assert self._current_fanta_info is not None
        self._comic_reader_manager.read_barks_comic_book(
            self._current_fanta_info,
            comic_book,
            self._get_page_to_first_goto(),
            self._bottom_title_view_screen.use_overrides_active,
        )
        return True

    def read_article(self, article_title: Titles, return_view_state: ViewStates) -> None:
        """Open a non-comic article in the comic reader."""
        self._on_active_changed(False)  # noqa: FBT003
        self._read_comic_view_state = return_view_state

        page_to_first_goto = "1"
        self._comic_reader_manager.read_article_as_comic_book(article_title, page_to_first_goto)

    def open_document(
        self, doc_dir: Path, title: str, return_view_state: ViewStates | None = None
    ) -> None:
        """Open a document in the document reader."""
        self._on_active_changed(False)  # noqa: FBT003
        self._doc_reader_close_view_state = return_view_state
        self._screen_switchers.switch_to_document_reader(doc_dir, title)

    # === Return paths ===

    def on_comic_closed(self) -> None:
        """Handle return from comic reader. Restores view state, saves last-read page."""
        if self._read_comic_view_state is not None:
            self._view_state_manager.update_view_for_node(self._read_comic_view_state)
            self._read_comic_view_state = None

        if not self._current_fanta_info:
            return

        last_read_page = self._comic_reader_manager.comic_closed()
        self._set_goto_page_checkbox(last_read_page)

    def on_document_closed(self) -> None:
        """Handle return from document reader. Restores view state."""
        if self._doc_reader_close_view_state is not None:
            self._view_state_manager.update_view_for_node(self._doc_reader_close_view_state)
            self._doc_reader_close_view_state = None

    # === Internal helpers ===

    def _title_row_selected(
        self,
        new_fanta_info: FantaComicBookInfo,
        title_image_file: PanelPath | None,
    ) -> None:
        self._current_fanta_info = new_fanta_info
        self._set_title(title_image_file)
        self._view_state_manager.set_view_state(
            ViewStates.ON_TITLE_NODE,
            title_str=self._current_fanta_info.comic_book_info.get_title_str(),
        )

    def _set_title(self, title_image_file: PanelPath | None = None) -> None:
        assert self._current_fanta_info is not None
        self._view_state_manager.set_title(self._current_fanta_info, title_image_file)
        self._set_goto_page_checkbox()
        self._set_use_overrides_checkbox()

    def _set_tag_goto_page_checkbox(self, tag: Tags | TagGroups, title_str: str) -> None:
        logger.debug(f'Setting tag goto page for ({tag.value}, "{title_str}").')

        if type(tag) is Tags:
            title = BARKS_TITLE_DICT[ComicBookInfo.get_title_str_from_display_title(title_str)]
            if (tag, title) not in BARKS_TAGGED_PAGES:
                logger.debug(f'No pages for ({tag.value}, "{title_str}").')
            else:
                page_to_goto = BARKS_TAGGED_PAGES[(tag, title)][0]
                logger.debug(f"Setting page to goto: {page_to_goto}.")
                self._bottom_title_view_screen.set_goto_page_state(page_to_goto, active=True)

    def _set_goto_page_checkbox(self, last_read_page: SavedPageInfo | None = None) -> None:
        if not last_read_page:
            assert self._current_fanta_info is not None
            title_str = self._current_fanta_info.comic_book_info.get_title_str()
            last_read_page = self._comic_reader_manager.get_last_read_page(title_str)

        if not last_read_page or (last_read_page.display_page_num == COMIC_BEGIN_PAGE):
            self._bottom_title_view_screen.set_goto_page_state(active=False)
        else:
            self._bottom_title_view_screen.set_goto_page_state(
                last_read_page.display_page_num, active=True
            )

    def _set_use_overrides_checkbox(self) -> None:
        assert self._current_fanta_info is not None
        title = self._current_fanta_info.comic_book_info.title
        if (
            self._reader_settings.use_prebuilt_archives
            or not self._special_fanta_overrides.is_title_where_overrides_are_optional(title)
        ):
            self._bottom_title_view_screen.set_overrides_state(active=True)
            return

        self._bottom_title_view_screen.set_overrides_state(
            description=self._special_fanta_overrides.get_description(title),
            active=self._special_fanta_overrides.get_overrides_setting(title),
        )

    def _get_comic_book(self) -> ComicBook:
        assert self._current_fanta_info is not None
        title_str = self._current_fanta_info.comic_book_info.get_title_str()

        overrides_intro_inset_file = self._special_fanta_overrides.get_inset_file(
            self._current_fanta_info.comic_book_info.title,
            self._bottom_title_view_screen.use_overrides_active,
        )

        return self._comics_database.get_comic_book(title_str, overrides_intro_inset_file)

    def _get_page_to_first_goto(self) -> str:
        if not self._bottom_title_view_screen.goto_page_active:
            return COMIC_BEGIN_PAGE

        return self._bottom_title_view_screen.goto_page_num

    @staticmethod
    def _get_year_range_from_info(fanta_info: FantaComicBookInfo) -> tuple[int, int] | None:
        sub_year = fanta_info.comic_book_info.submitted_year
        return next(
            (r for r in CHRONO_YEAR_RANGES if r[0] <= sub_year <= r[1]),
            None,
        )

    @staticmethod
    def _get_fanta_info(title: Titles) -> FantaComicBookInfo:
        fanta_info = get_fanta_info(title)
        if fanta_info is None:
            raise TitleNotInFantaInfoError(BARKS_TITLES[title])

        return fanta_info
