from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles
from barks_fantagraphics.comic_book import ComicBook
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO, FantaComicBookInfo
from kivy.clock import Clock
from loguru import logger

from barks_reader.core.comic_book_page_info import ComicLayout, ComicLayoutBuilder
from barks_reader.core.fantagraphics_volumes import MissingVolumeError
from barks_reader.core.reader_settings import ReaderSettings
from barks_reader.core.reader_setup import prepare_comic_for_reading
from barks_reader.core.saved_page_info import SavedPageInfo

from .comic_book_reader import ComicBookReaderScreen
from .last_read_page_tracker import LastReadPageTracker
from .tree_view_screen import TreeViewScreen
from .user_error_handler import ErrorInfo, ErrorTypes, UserErrorHandler

if TYPE_CHECKING:
    from .comic_book_reader import ComicBookReader


class ComicReaderManager:
    """Coordinate opening comics in the reader screen.

    Owns the "open a comic" flow (title/article lookup, building reader
    inputs, missing-volume error handling, screen-state passthroughs).
    Last-read-page persistence is delegated to ``LastReadPageTracker``.
    """

    def __init__(
        self,
        comics_database: ComicsDatabase,
        reader_settings: ReaderSettings,
        last_read_page_tracker: LastReadPageTracker,
        layout_builder: ComicLayoutBuilder,
        tree_view_screen: TreeViewScreen,
        user_error_handler: UserErrorHandler,
    ) -> None:
        """Initialize the ComicReaderManager.

        Args:
            comics_database: The database of comics.
            reader_settings: The application settings.
            last_read_page_tracker: Tracks and persists reading progress.
            layout_builder: Builds a ``ComicLayout`` for each comic to be read.
            tree_view_screen: The tree view screen controller.
            user_error_handler: Handler for user-facing errors.

        """
        self._comics_database = comics_database
        self._reader_settings = reader_settings
        self._tree_view_screen = tree_view_screen
        self._user_error_handler = user_error_handler

        self.all_fanta_titles = ALL_FANTA_COMIC_BOOK_INFO
        self._last_read_page_tracker = last_read_page_tracker
        self._layout_builder = layout_builder
        self._layout: ComicLayout | None = None

        self._comic_book_reader_screen: ComicBookReaderScreen | None = None
        self._comic_book_reader: ComicBookReader | None = None
        self._fanta_info: FantaComicBookInfo | None = None

    def set_comic_book_reader_screen(self, comic_book_reader_screen: ComicBookReaderScreen) -> None:
        """Set the comic book reader screen instance."""
        self._comic_book_reader_screen = comic_book_reader_screen
        assert self._comic_book_reader_screen is not None
        self._comic_book_reader = self._comic_book_reader_screen.comic_book_reader

    def init_comic_book_data(self) -> None:
        """Initialize the comic book reader data."""
        assert self._comic_book_reader
        self._comic_book_reader.init_data()

    def clear_window_state(self) -> None:
        """Clear the saved window state (position/size) of the reader screen."""
        assert self._comic_book_reader_screen
        self._comic_book_reader_screen.clear_window_state()

    def save_window_state_now(self) -> None:
        """Immediately save the current window state of the reader screen."""
        assert self._comic_book_reader_screen
        self._comic_book_reader_screen.save_window_state_now()

    def read_article_as_comic_book(self, article_title: Titles, page_to_first_goto: str) -> None:
        """Open an article (non-comic content) in the comic reader.

        Articles are treated as comics but do not save their "last read page" state.

        Args:
            article_title: The enum title of the article.
            page_to_first_goto: The page ID to navigate to initially.

        """
        article_title_str = BARKS_TITLES[article_title]
        self._fanta_info = self.all_fanta_titles[article_title_str]
        article_as_comic = self._comics_database.get_comic_book(article_title_str)

        assert self._comic_book_reader_screen
        self._comic_book_reader_screen.can_benefit_from_fullscreen = False
        try:
            self._read_comic_book(article_as_comic, page_to_first_goto, save_last_page=False)
        finally:
            self._comic_book_reader_screen.can_benefit_from_fullscreen = True

    def read_barks_comic_book(
        self,
        fanta_info: FantaComicBookInfo,
        comic: ComicBook,
        page_to_first_goto: str,
        use_overrides_active: bool,
    ) -> None:
        """Open a Barks comic book in the reader.

        Args:
            fanta_info: Metadata about the Fantagraphics volume/comic.
            comic: The ComicBook object to read.
            page_to_first_goto: The page ID to navigate to initially.
            use_overrides_active: Whether to apply censorship overrides.

        """
        self._fanta_info = fanta_info
        self._read_comic_book(
            comic,
            page_to_first_goto,
            save_last_page=True,
            use_overrides_active=use_overrides_active,
        )

    def _read_comic_book(
        self,
        comic: ComicBook,
        page_to_first_goto: str,
        *,
        save_last_page: bool,
        use_overrides_active: bool = True,
    ) -> None:
        assert page_to_first_goto
        assert self._comic_book_reader
        assert self._fanta_info
        assert self._fanta_info.comic_book_info

        self._layout, comic_book_image_builder = prepare_comic_for_reading(
            comic, self._reader_settings, self._layout_builder
        )

        title_str = self._fanta_info.comic_book_info.get_title_str()
        self._last_read_page_tracker.begin(title_str, self._layout, save_enabled=save_last_page)

        logger.debug(f'Load "{title_str}" and goto page "{page_to_first_goto}".')

        try:
            self._comic_book_reader.read_comic(
                self._fanta_info,
                use_overrides_active,
                comic_book_image_builder,
                page_to_first_goto,
                self._layout.page_map,
            )
        except MissingVolumeError as e:
            logger.error(e)
            error_info = ErrorInfo(missing_volumes=[e.missing_vol], title=e.title)
            self._user_error_handler.handle_error(
                ErrorTypes.MissingVolumeCannotShowTitle, error_info
            )
            assert self._comic_book_reader_screen is not None
            Clock.schedule_once(
                lambda _dt: self._comic_book_reader_screen.close_comic_book_reader(),  # ty:ignore[unresolved-attribute]
                1,
            )

    def comic_closed(self) -> SavedPageInfo | None:
        """Persist the last-read page when the reader closes."""
        assert self._comic_book_reader
        return self._last_read_page_tracker.end(self._comic_book_reader)

    def get_last_read_page(self, title_str: str) -> SavedPageInfo | None:
        """Retrieve the persisted last-read page for a title."""
        return self._last_read_page_tracker.get_last_read_page(title_str)
