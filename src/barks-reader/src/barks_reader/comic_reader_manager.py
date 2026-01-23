from typing import TYPE_CHECKING

from barks_build_comic_images.build_comic_images import ComicBookImageBuilder
from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles
from barks_fantagraphics.comic_book import ComicBook
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO, FantaComicBookInfo

# noinspection PyUnresolvedReferences
from comic_utils.get_panel_bytes import get_decrypted_bytes  # ty: ignore[unresolved-import]
from loguru import logger

from barks_reader.comic_book_reader import ComicBookReaderScreen
from barks_reader.core.comic_book_page_info import ComicBookPageInfo, ComicBookPageInfoManager
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE
from barks_reader.core.reader_settings import ReaderSettings
from barks_reader.json_settings_manager import SavedPageInfo, SettingsManager
from barks_reader.tree_view_screen import TreeViewScreen
from barks_reader.user_error_handler import UserErrorHandler

if TYPE_CHECKING:
    from barks_reader.comic_book_reader import ComicBookReader


class ComicReaderManager:
    def __init__(
        self,
        comics_database: ComicsDatabase,
        reader_settings: ReaderSettings,
        json_settings_manager: SettingsManager,
        tree_view_screen: TreeViewScreen,
        user_error_handler: UserErrorHandler,
    ) -> None:
        self._comics_database = comics_database
        self._reader_settings = reader_settings
        self._tree_view_screen = tree_view_screen
        self._user_error_handler = user_error_handler

        self.all_fanta_titles = ALL_FANTA_COMIC_BOOK_INFO
        self._json_settings_manager = json_settings_manager
        self._comic_page_info_mgr = ComicBookPageInfoManager(
            self._comics_database,
            self._reader_settings,
        )
        self._comic_page_info: ComicBookPageInfo | None = None

        self._comic_book_reader_screen: ComicBookReaderScreen | None = None
        self._comic_book_reader: ComicBookReader | None = None
        self._fanta_info: FantaComicBookInfo | None = None
        self._save_last_page = True

    def set_comic_book_reader_screen(self, comic_book_reader_screen: ComicBookReaderScreen) -> None:
        self._comic_book_reader_screen = comic_book_reader_screen
        self._comic_book_reader = self._comic_book_reader_screen.comic_book_reader

    def init_comic_book_data(self) -> None:
        assert self._comic_book_reader
        self._comic_book_reader.init_data()

    def clear_window_state(self) -> None:
        assert self._comic_book_reader_screen
        self._comic_book_reader_screen.clear_window_state()

    def save_window_state_now(self) -> None:
        assert self._comic_book_reader_screen
        self._comic_book_reader_screen.save_window_state_now()

    def read_article_as_comic_book(self, article_title: Titles, page_to_first_goto: str) -> None:
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

        self._comic_page_info = self._comic_page_info_mgr.get_comic_page_info(comic)
        assert self._comic_page_info

        comic_book_image_builder = ComicBookImageBuilder(
            comic,
            self._reader_settings.sys_file_paths.get_empty_page_file(),
            get_inset_decrypted_bytes=get_decrypted_bytes
            if self._reader_settings.file_paths.barks_panels_are_encrypted
            else None,
        )
        comic_book_image_builder.set_required_dim(self._comic_page_info.required_dim)

        logger.debug(
            f'Load "{self._fanta_info.comic_book_info.get_title_str()}"'
            f' and goto page "{page_to_first_goto}".',
        )

        self._comic_book_reader.read_comic(
            self._fanta_info,
            use_overrides_active,
            comic_book_image_builder,
            page_to_first_goto,
            self._comic_page_info.page_map,
        )

    def comic_closed(self) -> SavedPageInfo | None:
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

            if not self._is_inside_body_pages(last_read_page):
                last_read_page.display_page_num = COMIC_BEGIN_PAGE

        return last_read_page

    def get_last_read_page(self, title_str: str) -> SavedPageInfo | None:
        last_read_page_info = self._json_settings_manager.get_last_read_page(title_str)
        if not last_read_page_info:
            return None

        if not self._is_inside_body_pages(last_read_page_info):
            # The comic has been read. Go back to the first page.
            last_read_page_info.display_page_num = COMIC_BEGIN_PAGE

        logger.debug(f'"{title_str}": Last read page "{last_read_page_info}".')

        return last_read_page_info

    @staticmethod
    def _is_inside_body_pages(page_info: SavedPageInfo) -> bool:
        return (page_info.page_type == PageType.BODY) and (
            page_info.display_page_num != page_info.last_body_page
        )

    def _get_last_read_page_from_comic(self) -> SavedPageInfo | None:
        assert self._comic_book_reader
        assert self._comic_page_info

        last_read_page_str = self._comic_book_reader.get_last_read_page()
        if not last_read_page_str:
            return None

        last_read_page = self._comic_page_info.page_map[last_read_page_str]

        return SavedPageInfo(
            last_read_page.page_index,
            last_read_page.display_page_num,
            last_read_page.page_type,
            self._comic_page_info.last_body_page,
        )
