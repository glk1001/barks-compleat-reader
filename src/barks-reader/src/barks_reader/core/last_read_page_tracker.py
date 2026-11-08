"""Persists 'where the user was reading' across comic-reader sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from . import log_markers
from .reader_consts_and_types import COMIC_BEGIN_PAGE

if TYPE_CHECKING:
    from .comic_book_page_info import ComicLayout
    from .json_settings_manager import SettingsManager
    from .ports import ComicBookReaderPort
    from .saved_page_info import SavedPageInfo


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

    def end(self, comic_book_reader: ComicBookReaderPort) -> SavedPageInfo | None:
        """Persist progress for the current session if saving is enabled, and close it.

        A second ``end()`` without a ``begin()`` saves nothing: the session is closed,
        so a later close path cannot save the old title from whatever page the
        reader shows by then.

        Returns the saved page (with display-page-num normalised to
        ``COMIC_BEGIN_PAGE`` when the user finished the comic), or ``None``
        if saving was disabled or no valid page was read.
        """
        title, layout = self._current_title, self._current_layout
        save_enabled = self._save_enabled
        self._save_enabled = False
        self._current_title = None
        self._current_layout = None

        if not save_enabled:
            return None

        assert title is not None
        assert layout is not None

        last_read_page_str = comic_book_reader.get_last_read_page()
        if not last_read_page_str:
            logger.warning(f'"{title}": There was no valid last read page.')
            return None

        last_read_page = layout.resolve_last_read(
            last_read_page_str,
            comic_book_reader.get_current_display_unit(),
            comic_book_reader.double_page_mode,
        )

        self._json_settings_manager.save_last_read_page(title, last_read_page)
        logger.debug(
            log_markers.LAST_READ_PAGE_SAVED.format(
                title=title, page=last_read_page.display_page_num
            )
        )

        return _from_the_beginning_if_finished(last_read_page)

    def get_last_read_page(self, title_str: str) -> SavedPageInfo | None:
        """Retrieve the persisted last-read page for a title.

        Normalises a finished-comic position back to ``COMIC_BEGIN_PAGE``
        so the next open starts from the cover.
        """
        last_read_page_info = self._json_settings_manager.get_last_read_page(title_str)
        if not last_read_page_info:
            return None

        _from_the_beginning_if_finished(last_read_page_info)
        logger.debug(f'"{title_str}": Last read page "{last_read_page_info}".')
        return last_read_page_info


def _from_the_beginning_if_finished(page: SavedPageInfo) -> SavedPageInfo:
    """Send a page outside the body (a finished comic) back to ``COMIC_BEGIN_PAGE``, in place."""
    if not page.is_inside_body():
        page.display_page_num = COMIC_BEGIN_PAGE
    return page
