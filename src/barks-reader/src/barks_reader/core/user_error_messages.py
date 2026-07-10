"""Pure composition of user-facing error dialogs.

`build_error_presentation` turns an (`ErrorTypes`, `ErrorInfo`) pair into an
`ErrorPresentation` — dialog kind, title, text, and close-message — with no
Kivy involvement. The ui presenter (`ui.user_error_handler.UserErrorHandler`)
maps each `ErrorDialogKind` onto a popup layout and button wiring.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from enum import Enum, auto
from textwrap import dedent
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE
from barks_fantagraphics.fanta_comics_info import FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER

from .reader_formatter import escape_kivy_markup
from .user_error_types import ErrorTypes

if TYPE_CHECKING:
    from collections.abc import Callable

    from .reader_settings import ReaderSettings
    from .user_error_types import ErrorInfo


class ErrorDialogKind(Enum):
    """Which popup layout the presenter should use."""

    GOTO_SETTINGS = auto()
    """'Settings' + 'Cancel' buttons; reports ``close_message`` when closed."""

    FATAL_CONFIG = auto()
    """'Close' button only; reports ``close_message`` when closed."""

    NOTICE = auto()
    """'Close' button only, centered text; nothing reported on close."""


@dataclass(frozen=True, slots=True)
class ErrorPresentation:
    """Everything the presenter needs to show one error dialog."""

    kind: ErrorDialogKind
    title: str
    text: str
    close_message: str = ""


FANTA_VOLUMES_NOT_SET_FIX_SETTINGS_MSG = dedent("""\
    ERROR: FANTAGRAPHICS VOLUMES DIRECTORY NOT SET

    You need to add the Fantagraphics

    volumes directory to the app

    settings, then restart the app!""")

FANTA_VOLUMES_NOT_FOUND_FIX_SETTINGS_MSG = dedent("""\
    ERROR: FANTAGRAPHICS VOLUMES NOT FOUND

    You need to check and fix the app

    settings, then restart the app!""")

WRONG_FANTA_VOLUMES_FIX_AND_RESTART_MSG = dedent("""\
    ERROR: WRONG FANTAGRAPHICS VOLUMES

    You need to check the Fantagraphics

    volume directory, rename or remove any

    wrong archives, then restart the app!""")


def build_error_presentation(
    error_type: ErrorTypes,
    error_info: ErrorInfo | None,
    reader_settings: ReaderSettings,
    popup_title: str = "",
) -> ErrorPresentation:
    """Compose the dialog presentation for *error_type*.

    Args:
        error_type: Which kind of error occurred.
        error_info: Structured details for the error message, if any.
        reader_settings: The application settings (source of the configured
            Fantagraphics directory for the not-found message).
        popup_title: Overrides the error's default dialog title when non-empty.

    Returns:
        The composed `ErrorPresentation`.

    Raises:
        ValueError: If *error_type* has no configured message builder.

    """
    builder = _BUILDERS.get(error_type)
    if not builder:
        msg = f"No handler configured for error type: {error_type}"
        raise ValueError(msg)

    return builder(error_info, reader_settings, popup_title)


def _build_fanta_root_not_set(
    _error_info: ErrorInfo | None,
    _reader_settings: ReaderSettings,
    popup_title: str,
) -> ErrorPresentation:
    """Compose the message for the Fantagraphics directory not being set."""
    text = dedent("""\
        Currently, in the app settings, the Fantagraphics comic zips directory has
        not been set. You need to go to settings and enter the zips directory, then
        restart the app.""")

    return ErrorPresentation(
        kind=ErrorDialogKind.GOTO_SETTINGS,
        title=popup_title or "Fantagraphics Directory Not Set",
        text=text,
        close_message=FANTA_VOLUMES_NOT_SET_FIX_SETTINGS_MSG,
    )


def _build_fanta_root_not_found(
    _error_info: ErrorInfo | None,
    reader_settings: ReaderSettings,
    popup_title: str,
) -> ErrorPresentation:
    """Compose the message for a configured Fantagraphics directory that does not exist."""
    fanta_volume_dir = escape_kivy_markup(
        textwrap.fill(str(reader_settings.fantagraphics_volumes_dir), 50)
    )

    text = dedent(f"""\
        In app settings, the Fantagraphics comic zips directory is

            [b]"{fanta_volume_dir}"[/b]

        But this directory could not be found. You need to go to
        settings and enter the correct directory, then restart the
        app.""")

    return ErrorPresentation(
        kind=ErrorDialogKind.GOTO_SETTINGS,
        title=popup_title or "Fantagraphics Directory Not Found",
        text=text,
        close_message=FANTA_VOLUMES_NOT_FOUND_FIX_SETTINGS_MSG,
    )


def _build_duplicate_archive_files(
    error_info: ErrorInfo | None,
    _reader_settings: ReaderSettings,
    popup_title: str,
) -> ErrorPresentation:
    """Compose the message for duplicate Fantagraphics archive files."""
    assert error_info is not None
    assert error_info.duplicate_volumes is not None

    archive_file = escape_kivy_markup(textwrap.fill(str(error_info.file), 50))
    text = dedent(f"""\
        There were duplicate Fantagraphics archive files in the directory:

            [b]"{archive_file}"[/b]

        The duplicate volumes are {", ".join(map(str, error_info.duplicate_volumes))}. You need to
        make sure the archives are prefixed with the numbers
        {FIRST_VOLUME_NUMBER:02d} to {LAST_VOLUME_NUMBER:02d} inclusive, without duplicates, then restart the app.""")  # noqa: E501

    return ErrorPresentation(
        kind=ErrorDialogKind.FATAL_CONFIG,
        title=popup_title or "Wrong Fantagraphics Archive File",
        text=text,
        close_message=WRONG_FANTA_VOLUMES_FIX_AND_RESTART_MSG,
    )


def _build_too_many_archive_files(
    error_info: ErrorInfo | None,
    _reader_settings: ReaderSettings,
    popup_title: str,
) -> ErrorPresentation:
    """Compose the message for too many Fantagraphics archive files."""
    assert error_info is not None

    text = dedent(f"""\
        There were too many Fantagraphics archive files. The
        expected number of files is {error_info.num_volumes} not {error_info.num_archive_files}. You need to
        make sure the archives are prefixed with the numbers
        {FIRST_VOLUME_NUMBER:02d} to {LAST_VOLUME_NUMBER:02d} inclusive, then restart the app.""")  # noqa: E501

    return ErrorPresentation(
        kind=ErrorDialogKind.FATAL_CONFIG,
        title=popup_title or "Too Many Fantagraphics Archives",
        text=text,
        close_message=WRONG_FANTA_VOLUMES_FIX_AND_RESTART_MSG,
    )


def _build_missing_volumes(
    error_info: ErrorInfo | None,
    _reader_settings: ReaderSettings,
    _popup_title: str,
) -> ErrorPresentation:
    """Compose the message for missing Fantagraphics volumes."""
    assert error_info is not None
    assert error_info.missing_volumes is not None

    missing_volumes_str = ", ".join(map(str, error_info.missing_volumes))
    if len(error_info.missing_volumes) == 1:
        title = "Fantagraphics Volume Missing"
        text = (
            f"Fantagraphics volume '{missing_volumes_str}' is missing.\n\n"
            f"You won't be able to read any titles from this volume."
        )
    else:
        title = "Fantagraphics Volumes Missing"
        text = (
            f"Fantagraphics volumes '{missing_volumes_str}' are missing.\n\n"
            f"You won't be able to read any titles from these volumes."
        )

    return ErrorPresentation(kind=ErrorDialogKind.NOTICE, title=title, text=text)


def _build_cannot_show_title(
    error_info: ErrorInfo | None,
    _reader_settings: ReaderSettings,
    _popup_title: str,
) -> ErrorPresentation:
    """Compose the message for a title whose volume is missing."""
    assert error_info is not None
    assert error_info.missing_volumes is not None
    assert len(error_info.missing_volumes) == 1
    assert error_info.title is not None

    title_str = escape_kivy_markup(ENUM_TO_STR_TITLE[error_info.title])
    text = (
        f'Cannot show the title "{title_str}".\n\n'
        f"Fantagraphics volume '{error_info.missing_volumes[0]}' is missing."
    )

    return ErrorPresentation(
        kind=ErrorDialogKind.NOTICE, title="Fantagraphics Volume Missing", text=text
    )


def _build_volume_not_available(
    error_info: ErrorInfo | None,
    _reader_settings: ReaderSettings,
    _popup_title: str,
) -> ErrorPresentation:
    """Compose the message for a title whose volume is unavailable or not found."""
    assert error_info is not None

    if error_info.title is None:
        # 'get_volume_not_available_error_info' produces title=None when the
        # source image has no originating title.
        cannot_show = "Cannot show this title."
    else:
        title_str = escape_kivy_markup(ENUM_TO_STR_TITLE[error_info.title])
        cannot_show = f'Cannot show the title [b]"{title_str}."[/b]'

    if error_info.file_volume == -1:
        title = "Fantagraphics Volume Not Available"
        text = (
            f"{cannot_show}\n\nThe Fantagraphics volume containing this title is not available yet."
        )
    else:
        title = "Fantagraphics Volume Not Found"
        text = (
            f"{cannot_show}\n\n"
            f"This title is in Fantagraphics Volume {error_info.file_volume}"
            f" which could not be found."
        )

    return ErrorPresentation(kind=ErrorDialogKind.NOTICE, title=title, text=text)


_BUILDERS: dict[
    ErrorTypes,
    Callable[[ErrorInfo | None, ReaderSettings, str], ErrorPresentation],
] = {
    ErrorTypes.FantagraphicsVolumeRootNotSet: _build_fanta_root_not_set,
    ErrorTypes.FantagraphicsVolumeRootNotFound: _build_fanta_root_not_found,
    ErrorTypes.DuplicateVolumeArchiveFiles: _build_duplicate_archive_files,
    ErrorTypes.TooManyVolumeArchiveFiles: _build_too_many_archive_files,
    ErrorTypes.MissingArchiveVolumes: _build_missing_volumes,
    ErrorTypes.MissingVolumeCannotShowTitle: _build_cannot_show_title,
    ErrorTypes.ArchiveVolumeNotAvailable: _build_volume_not_available,
}
