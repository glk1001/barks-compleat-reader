from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE
from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    get_fanta_volume_from_str,
)
from loguru import logger

from .comic_book_page_info import slice_comic_layout
from .fantagraphics_volumes import MissingVolumeError
from .reader_setup import prepare_comic_for_reading
from .user_error_types import ErrorInfo, ErrorTypes

if TYPE_CHECKING:
    from collections.abc import Sequence

    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.comic_book import ComicBook
    from barks_fantagraphics.comics_database import ComicsDatabase
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo

    from .comic_book_page_info import ComicLayout, ComicLayoutBuilder
    from .last_read_page_tracker import LastReadPageTracker
    from .ports import CancelHandle, ComicBookReaderPort, ComicBookReaderScreenPort, Scheduler
    from .reader_settings import ReaderSettings
    from .reading_history import ReadingHistoryTracker
    from .saved_page_info import SavedPageInfo
    from .user_error_types import UserErrorHandlerPort

_CLOSE_READER_ON_ERROR_DELAY_SECS = 1


@dataclass(frozen=True, slots=True)
class _PendingTracking:
    """What the trackers are to begin with, once the comic being opened has drawn."""

    title_str: str
    layout: ComicLayout
    save_last_page: bool
    history_title_str: str


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
        reading_history_tracker: ReadingHistoryTracker,
        layout_builder: ComicLayoutBuilder,
        user_error_handler: UserErrorHandlerPort,
        scheduler: Scheduler,
    ) -> None:
        """Initialize the ComicReaderManager.

        Args:
            comics_database: The database of comics.
            reader_settings: The application settings.
            last_read_page_tracker: Tracks and persists reading progress.
            reading_history_tracker: Records reading sessions to the history log.
            layout_builder: Builds a ``ComicLayout`` for each comic to be read.
            user_error_handler: Handler for user-facing errors.
            scheduler: Marshals delayed callbacks onto the UI thread.

        """
        self._comics_database = comics_database
        self._reader_settings = reader_settings
        self._user_error_handler = user_error_handler
        self._scheduler = scheduler

        self.all_fanta_titles = ALL_FANTA_COMIC_BOOK_INFO
        self._last_read_page_tracker = last_read_page_tracker
        self._reading_history_tracker = reading_history_tracker
        self._layout_builder = layout_builder
        self._layout: ComicLayout | None = None

        self._comic_book_reader_screen: ComicBookReaderScreenPort | None = None
        self._comic_book_reader: ComicBookReaderPort | None = None
        self._fanta_info: FantaComicBookInfo | None = None
        # The close an unreadable-comic error deferred, until it fires or no longer applies.
        self._pending_error_close: CancelHandle | None = None
        # The trackers' inputs for the comic now opening, until its first page draws.
        self._pending_tracking: _PendingTracking | None = None
        # Whether the comic now in the reader opened, and so has trackers to end.
        self._tracking = False

    def set_comic_book_reader_screen(
        self, comic_book_reader_screen: ComicBookReaderScreenPort
    ) -> None:
        """Set the comic book reader screen instance."""
        self._cancel_pending_error_close()
        self._comic_book_reader_screen = comic_book_reader_screen
        assert self._comic_book_reader_screen is not None
        self._comic_book_reader = self._comic_book_reader_screen.comic_book_reader

    def init_comic_book_data(self) -> None:
        """Initialize the comic book reader data."""
        assert self._comic_book_reader
        self._comic_book_reader.init_data()

    def read_article_as_comic_book(self, article_title: Titles, page_to_first_goto: str) -> None:
        """Open an article (non-comic content) in the comic reader.

        Articles are treated as comics but do not save their "last read page" state.

        Args:
            article_title: The enum title of the article.
            page_to_first_goto: The page ID to navigate to initially.

        """
        article_title_str = ENUM_TO_STR_TITLE[article_title]
        self._fanta_info = self.all_fanta_titles[article_title]
        article_as_comic = self._comics_database.get_comic_book(article_title_str)

        # Set for the read, not restored after it: the screen reads the flag when it
        # is shown, which the reader defers until page one has drawn, well after this
        # returns. Restored on the way out, every article still opened fullscreen.
        assert self._comic_book_reader_screen
        self._comic_book_reader_screen.can_benefit_from_fullscreen = False
        self._read_comic_book(article_as_comic, page_to_first_goto, save_last_page=False)

    def read_barks_comic_book(
        self,
        fanta_info: FantaComicBookInfo,
        comic: ComicBook,
        page_to_first_goto: str,
        use_overrides_active: bool,
        history_title_str: str | None = None,
        collection_page_range: tuple[int, int] | None = None,
        tagged_pages: Sequence[str] = (),
    ) -> None:
        """Open a Barks comic book in the reader.

        Args:
            fanta_info: Metadata about the Fantagraphics volume/comic.
            comic: The ComicBook object to read.
            page_to_first_goto: The page ID to navigate to initially.
            use_overrides_active: Whether to apply censorship overrides.
            history_title_str: Title to record in the reading history when it
                differs from the comic's own title (e.g. a one-pager read via
                the "All One-Pagers" collection).
            collection_page_range: For the large single-page-only collections
                ("All One-Pagers"/"All Covers"), the inclusive 1-based page range
                of the member's year-range group. Only that slice is opened, so
                the loader holds ~40-55 pages instead of the whole collection.
            tagged_pages: The pages a tag marks in the comic, when it was opened
                through the tag: the goto-page list shows them in their own colour.

        """
        self._fanta_info = fanta_info
        assert self._comic_book_reader_screen
        self._comic_book_reader_screen.can_benefit_from_fullscreen = True
        self._read_comic_book(
            comic,
            page_to_first_goto,
            save_last_page=True,
            use_overrides_active=use_overrides_active,
            history_title_str=history_title_str,
            collection_page_range=collection_page_range,
            tagged_pages=tagged_pages,
        )

    def _read_comic_book(
        self,
        comic: ComicBook,
        page_to_first_goto: str,
        *,
        save_last_page: bool,
        use_overrides_active: bool = True,
        history_title_str: str | None = None,
        collection_page_range: tuple[int, int] | None = None,
        tagged_pages: Sequence[str] = (),
    ) -> None:
        assert page_to_first_goto
        assert self._comic_book_reader
        assert self._fanta_info
        assert self._fanta_info.comic_book_info

        self._layout, comic_book_image_builder = prepare_comic_for_reading(
            comic, self._reader_settings, self._layout_builder
        )
        if collection_page_range is not None:
            # Open only the member's year-range group, not the whole collection.
            self._layout = slice_comic_layout(self._layout, *collection_page_range)

        title_str = self._fanta_info.comic_book_info.get_title_str()
        logger.debug(f'Load "{title_str}" and goto page "{page_to_first_goto}".')

        # Only a comic that opened is tracked: a failed open has no page to save, and
        # is not a read for the history. The reader says when page one has drawn; a
        # load that fails before then, on the loader thread included, never says so.
        self._pending_tracking = _PendingTracking(
            title_str, self._layout, save_last_page, history_title_str or title_str
        )
        try:
            self._comic_book_reader.read_comic(
                self._fanta_info,
                use_overrides_active,
                comic_book_image_builder,
                page_to_first_goto,
                self._layout,
                tagged_pages=tagged_pages,
                on_comic_opened=self._begin_tracking,
            )
        except MissingVolumeError as e:
            logger.error(e)
            self._report_unreadable(
                ErrorTypes.MissingVolumeCannotShowTitle,
                ErrorInfo(missing_volumes=[e.missing_vol], title=e.title),
            )
            return
        except FileNotFoundError as e:
            # Prebuilt archives: the title's own comic file is absent.
            logger.error(e)
            self._report_unreadable(
                ErrorTypes.ArchiveVolumeNotAvailable,
                ErrorInfo(
                    file_volume=get_fanta_volume_from_str(self._fanta_info.fantagraphics_volume),
                    title=self._fanta_info.comic_book_info.title,
                ),
            )
            return

    def _begin_tracking(self) -> None:
        """Begin the trackers for the comic whose first page has just drawn."""
        pending = self._pending_tracking
        assert pending is not None
        self._pending_tracking = None
        self._last_read_page_tracker.begin(
            pending.title_str, pending.layout, save_enabled=pending.save_last_page
        )
        if pending.save_last_page:
            # `save_last_page` is only False for articles, which aren't history-worthy.
            self._reading_history_tracker.begin(pending.history_title_str)
        self._tracking = True

    def _report_unreadable(self, error_type: ErrorTypes, error_info: ErrorInfo) -> None:
        """Show the user why the comic cannot be read, then close the reader after a delay."""
        self._pending_tracking = None
        self._user_error_handler.handle_error(error_type, error_info)
        assert self._comic_book_reader_screen is not None
        reader_screen = self._comic_book_reader_screen
        self._pending_error_close = self._scheduler.schedule_once(
            reader_screen.close_comic_book_reader, _CLOSE_READER_ON_ERROR_DELAY_SECS
        )

    def _cancel_pending_error_close(self) -> None:
        """Drop a deferred error close: the reader it was for is closed or gone."""
        if self._pending_error_close is not None:
            self._pending_error_close.cancel()
            self._pending_error_close = None

    def comic_closed(self) -> SavedPageInfo | None:
        """Persist the last-read page when the reader closes.

        A close still pending from an unreadable-comic error is cancelled here, so the
        user closing the reader first, then opening another title within the delay,
        does not have the stale close shut the new comic. A comic that never opened
        has nothing to persist.
        """
        self._cancel_pending_error_close()
        self._pending_tracking = None
        if not self._tracking:
            return None
        self._tracking = False
        assert self._comic_book_reader
        last_read_page = self._last_read_page_tracker.end(self._comic_book_reader)
        self._reading_history_tracker.end(last_read_page)
        return last_read_page

    def get_last_read_page(self, title_str: str) -> SavedPageInfo | None:
        """Retrieve the persisted last-read page for a title."""
        return self._last_read_page_tracker.get_last_read_page(title_str)
