"""Ports for the comic-book reader widget and its host screen.

`core.comic_reader_manager` and `core.last_read_page_tracker` drive the reader
through these narrow surfaces; the production implementations are the Kivy
`ComicBookReader` widget and `ComicBookReaderScreen` in `ui.comic_book_reader`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections import OrderedDict

    from barks_build_comic_images.build_comic_images import ComicBookImageBuilder
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo

    from barks_reader.core.comic_book_page_info import PageInfo
    from barks_reader.core.display_unit import DisplayUnit


class ComicBookReaderPort(Protocol):
    """The comic-reading widget: load a comic and report the reading position."""

    @property
    def double_page_mode(self) -> bool:
        """Whether the reader is currently showing two-page spreads."""
        ...

    def init_data(self) -> None:
        """Initialize the reader's comic book data."""
        ...

    def read_comic(
        self,
        fanta_info: FantaComicBookInfo,
        use_fantagraphics_overrides: bool,
        comic_book_image_builder: ComicBookImageBuilder,
        page_to_first_goto: str,
        page_map: OrderedDict[str, PageInfo],
    ) -> None:
        """Load *fanta_info*'s comic and start reading at *page_to_first_goto*."""
        ...

    def get_last_read_page(self) -> str:
        """Return the display page number the user last read."""
        ...

    def get_current_display_unit(self) -> DisplayUnit | None:
        """Return the current display unit (for double page mode awareness)."""
        ...


class ComicBookReaderScreenPort(Protocol):
    """The screen hosting the reader widget: fullscreen policy and close flow."""

    can_benefit_from_fullscreen: bool

    @property
    def comic_book_reader(self) -> ComicBookReaderPort:
        """The hosted comic-reading widget."""
        ...

    def close_comic_book_reader(self) -> None:
        """Close the comic reader and return to the previous screen."""
        ...
