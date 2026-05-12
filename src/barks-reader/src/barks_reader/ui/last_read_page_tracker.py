"""Persists 'where the user was reading' across comic-reader sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE

if TYPE_CHECKING:
    from barks_reader.core.comic_book_page_info import ComicLayout
    from barks_reader.core.saved_page_info import SavedPageInfo

    from .comic_book_reader import ComicBookReader
    from .json_settings_manager import SettingsManager


class LastReadPageTracker:
    """Track the active comic's reading position and persist it on close.

    Owns the "is saving enabled / which comic / which layout" state for one
    reading session, so ``ComicReaderManager`` can focus on opening comics.

    A session is bracketed by :meth:`begin` (when a comic is opened) and
    :meth:`end` (when the reader closes). :meth:`get_last_read_page` reads
    the persisted store independent of any active session.
    """

    def __init__(self, json_settings_manager: SettingsManager) -> None:
        self._json_settings_manager = json_settings_manager
        self._save_enabled = False
        self._current_title: str | None = None
        self._current_layout: ComicLayout | None = None

    def begin(self, title: str, layout: ComicLayout, *, save_enabled: bool) -> None:
        """Note the comic being opened; ``end()`` will save its progress."""
        self._current_title = title
        self._current_layout = layout
        self._save_enabled = save_enabled

    def end(self, comic_book_reader: ComicBookReader) -> SavedPageInfo | None:
        """Persist progress for the current session if saving is enabled.

        Returns the saved page (with display-page-num normalised to
        ``COMIC_BEGIN_PAGE`` when the user finished the comic), or ``None``
        if saving was disabled or no valid page was read.
        """
        if not self._save_enabled:
            return None

        assert self._current_title is not None
        assert self._current_layout is not None

        last_read_page_str = comic_book_reader.get_last_read_page()
        if not last_read_page_str:
            logger.warning(f'"{self._current_title}": There was no valid last read page.')
            return None

        last_read_page = self._current_layout.resolve_last_read(
            last_read_page_str,
            comic_book_reader.get_current_display_unit(),
            comic_book_reader.double_page_mode,
        )

        self._json_settings_manager.save_last_read_page(self._current_title, last_read_page)
        logger.debug(
            f'"{self._current_title}": Saved last read page "{last_read_page.display_page_num}".'
        )

        if not last_read_page.is_inside_body():
            last_read_page.display_page_num = COMIC_BEGIN_PAGE

        return last_read_page

    def get_last_read_page(self, title_str: str) -> SavedPageInfo | None:
        """Retrieve the persisted last-read page for a title.

        Normalises a finished-comic position back to ``COMIC_BEGIN_PAGE``
        so the next open starts from the cover.
        """
        last_read_page_info = self._json_settings_manager.get_last_read_page(title_str)
        if not last_read_page_info:
            return None

        if not last_read_page_info.is_inside_body():
            last_read_page_info.display_page_num = COMIC_BEGIN_PAGE

        logger.debug(f'"{title_str}": Last read page "{last_read_page_info}".')
        return last_read_page_info
