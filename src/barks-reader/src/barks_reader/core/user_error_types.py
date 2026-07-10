"""Kivy-free user-facing error contracts: error kinds, payloads, and the handler port.

The presentation side (popup composition and display) lives in
`ui.user_error_handler`; `core` modules report errors through the
`UserErrorHandlerPort` protocol defined here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Protocol

from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    get_fanta_volume_from_str,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_titles import Titles

    from .image_selector import ImageInfo


class TitleNotInFantaInfoError(Exception):
    """Exception raised for title not in Fanta info."""

    def __init__(self, title_str: str) -> None:
        super().__init__(f'Title "{title_str}" not in Fanta info.')


class ErrorTypes(Enum):
    FantagraphicsVolumeRootNotSet = auto()
    FantagraphicsVolumeRootNotFound = auto()
    DuplicateVolumeArchiveFiles = auto()
    TooManyVolumeArchiveFiles = auto()
    MissingArchiveVolumes = auto()
    MissingVolumeCannotShowTitle = auto()
    ArchiveVolumeNotAvailable = auto()


@dataclass(frozen=True, slots=True)
class ErrorInfo:
    file: str = ""
    file_volume: int = 0
    expected_volume: int = 0
    num_volumes: int = 0
    num_archive_files: int = 0
    duplicate_volumes: list[int] | None = None
    missing_volumes: list[int] | None = None
    title: Titles | None = None


class UserErrorHandlerPort(Protocol):
    """Present a user-facing error (production shows a Kivy popup)."""

    def handle_error(
        self,
        error_type: ErrorTypes,
        error_info: ErrorInfo | None,
        on_popup_closed: Callable[[str], None] | None = None,
        popup_title: str = "",
    ) -> None:
        """Present the error described by *error_type* and *error_info*.

        Args:
            error_type: Which kind of error occurred.
            error_info: Structured details for the error message, if any.
            on_popup_closed: Called with a close-message when the popup closes.
            popup_title: Overrides the handler's default popup title.

        """
        ...


def get_volume_not_available_error_info(image_info: ImageInfo) -> ErrorInfo:
    fanta_volume = (
        -1
        if image_info.from_title is None or image_info.from_title not in ALL_FANTA_COMIC_BOOK_INFO
        else (
            get_fanta_volume_from_str(
                ALL_FANTA_COMIC_BOOK_INFO[image_info.from_title].fantagraphics_volume
            )
        )
    )
    return ErrorInfo(file_volume=fanta_volume, title=image_info.from_title)
