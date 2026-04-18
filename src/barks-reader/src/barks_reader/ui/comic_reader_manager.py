from typing import TYPE_CHECKING

from barks_build_comic_images.build_comic_images import ComicBookImageBuilder
from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles
from barks_fantagraphics.comic_book import ComicBook
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO, FantaComicBookInfo
from comic_utils.get_panel_bytes import get_decrypted_bytes  # ty: ignore[unresolved-import]
from kivy.clock import Clock
from loguru import logger

from barks_reader.core.comic_book_page_info import ComicLayout, ComicLayoutBuilder
from barks_reader.core.fantagraphics_volumes import MissingVolumeError
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE
from barks_reader.core.reader_settings import ReaderSettings
from barks_reader.core.saved_page_info import SavedPageInfo

from .comic_book_reader import ComicBookReaderScreen
from .json_settings_manager import SettingsManager
from .tree_view_screen import TreeViewScreen
from .user_error_handler import ErrorInfo, ErrorTypes, UserErrorHandler

if TYPE_CHECKING:
    from .comic_book_reader import ComicBookReader


class ComicReaderManager:
    """Manages the logic for reading comics, including state management and image building."""

    def __init__(
        self,
        comics_database: ComicsDatabase,
        reader_settings: ReaderSettings,
        json_settings_manager: SettingsManager,
        layout_builder: ComicLayoutBuilder,
        tree_view_screen: TreeViewScreen,
        user_error_handler: UserErrorHandler,
    ) -> None:
        """Initialize the ComicReaderManager.

        Args:
            comics_database: The database of comics.
            reader_settings: The application settings.
            json_settings_manager: Manager for JSON-based settings (last read pages).
            layout_builder: Builds a ``ComicLayout`` for each comic to be read.
            tree_view_screen: The tree view screen controller.
            user_error_handler: Handler for user-facing errors.

        """
        self._comics_database = comics_database
        self._reader_settings = reader_settings
        self._tree_view_screen = tree_view_screen
        self._user_error_handler = user_error_handler

        self.all_fanta_titles = ALL_FANTA_COMIC_BOOK_INFO
        self._json_settings_manager = json_settings_manager
        self._layout_builder = layout_builder
        self._layout: ComicLayout | None = None

        self._comic_book_reader_screen: ComicBookReaderScreen | None = None
        self._comic_book_reader: ComicBookReader | None = None
        self._fanta_info: FantaComicBookInfo | None = None
        self._save_last_page = True

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
        self._save_last_page = False

        article_title_str = BARKS_TITLES[article_title]
        self._fanta_info = self.all_fanta_titles[article_title_str]
        article_as_comic = self._comics_database.get_comic_book(article_title_str)

        assert self._comic_book_reader_screen
        self._comic_book_reader_screen.can_benefit_from_fullscreen = False
        try:
            self._read_comic_book(article_as_comic, page_to_first_goto)
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
        self._save_last_page = True
        self._fanta_info = fanta_info

        self._read_comic_book(comic, page_to_first_goto, use_overrides_active=use_overrides_active)

    def _read_comic_book(
        self,
        comic: ComicBook,
        page_to_first_goto: str,
        use_overrides_active: bool = True,
    ) -> None:
        assert page_to_first_goto
        assert self._comic_book_reader
        assert self._fanta_info
        assert self._fanta_info.comic_book_info

        self._layout = self._layout_builder.build(comic)

        get_decrypted_func = None
        if self._reader_settings.file_paths.barks_panels_are_encrypted:
            get_decrypted_func = get_decrypted_bytes

        comic_book_image_builder = ComicBookImageBuilder(
            comic,
            self._reader_settings.sys_file_paths.get_empty_page_file(),
            get_inset_decrypted_bytes=get_decrypted_func,
        )
        comic_book_image_builder.set_required_dim(
            self._layout_builder.get_required_dimensions(comic)
        )

        logger.debug(
            f'Load "{self._fanta_info.comic_book_info.get_title_str()}"'
            f' and goto page "{page_to_first_goto}".',
        )

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
        """Handle actions when a comic is closed, such as saving the last read page.

        Returns:
            The SavedPageInfo of the last read page, or None if saving was disabled
            or no page was read.

        """
        if not self._save_last_page:
            return None

        assert self._fanta_info
        assert self._fanta_info.comic_book_info

        title_str = self._fanta_info.comic_book_info.get_title_str()
        last_read_page = self._get_last_read_page_from_comic()

        if not last_read_page:
            logger.warning(f'"{title_str}": There was no valid last read page.')
        else:
            self._json_settings_manager.save_last_read_page(title_str, last_read_page)
            logger.debug(
                f'"{title_str}": Saved last read page "{last_read_page.display_page_num}".',
            )

            if not last_read_page.is_inside_body():
                last_read_page.display_page_num = COMIC_BEGIN_PAGE

        return last_read_page

    def get_last_read_page(self, title_str: str) -> SavedPageInfo | None:
        """Retrieve the last read page for a given title.

        If the comic was previously finished (last read page was the end), this resets
        it to the beginning.

        Args:
            title_str: The title of the comic.

        """
        last_read_page_info = self._json_settings_manager.get_last_read_page(title_str)
        if not last_read_page_info:
            return None

        if not last_read_page_info.is_inside_body():
            # The comic has been read. Go back to the first page.
            last_read_page_info.display_page_num = COMIC_BEGIN_PAGE

        logger.debug(f'"{title_str}": Last read page "{last_read_page_info}".')

        return last_read_page_info

    def _get_last_read_page_from_comic(self) -> SavedPageInfo | None:
        assert self._comic_book_reader
        assert self._layout

        last_read_page_str = self._comic_book_reader.get_last_read_page()
        if not last_read_page_str:
            return None

        return self._layout.resolve_last_read(
            last_read_page_str,
            self._comic_book_reader.get_current_display_unit(),
            self._comic_book_reader.double_page_mode,
        )
