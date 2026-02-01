from __future__ import annotations

import textwrap
from dataclasses import dataclass
from enum import Enum, auto
from textwrap import dedent
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import BARKS_TITLES
from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
    get_fanta_volume_from_str,
)
from kivy.clock import Clock

from barks_reader.ui.reader_ui_classes import MessagePopup

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_titles import Titles

    from barks_reader.core.random_title_images import ImageInfo
    from barks_reader.core.reader_settings import ReaderSettings


class ErrorTypes(Enum):
    FantagraphicsVolumeRootNotSet = auto()
    FantagraphicsVolumeRootNotFound = auto()
    DuplicateVolumeArchiveFiles = auto()
    TooManyVolumeArchiveFiles = auto()
    MissingArchiveVolumes = auto()
    MissingVolumeCannotShowTitle = auto()
    ArchiveVolumeNotAvailable = auto()


_FANTA_VOLUMES_NOT_SET_FIX_SETTINGS_MSG = dedent("""\
    ERROR: FANTAGRAPHICS VOLUMES DIRECTORY NOT SET

    You need to add the Fantagraphics

    volumes directory to the app

    settings, then restart the app!""")

_FANTA_VOLUMES_NOT_FOUND_FIX_SETTINGS_MSG = dedent("""\
    ERROR: FANTAGRAPHICS VOLUMES NOT FOUND

    You need to check and fix the app

    settings, then restart the app!""")

_WRONG_FANTA_VOLUMES_FIX_AND_RESTART_MSG = dedent("""\
    ERROR: WRONG FANTAGRAPHICS VOLUMES

    You need to check the Fantagraphics

    volume directory, rename or remove any

    wrong archives, then restart the app!""")


@dataclass
class ErrorInfo:
    file: str = ""
    file_volume: int = 0
    expected_volume: int = 0
    num_volumes: int = 0
    num_archive_files: int = 0
    duplicate_volumes: list[int] | None = None
    missing_volumes: list[int] | None = None
    title: Titles | None = None


class UserErrorHandler:
    def __init__(
        self, reader_settings: ReaderSettings, open_settings_func: Callable[[], None]
    ) -> None:
        self._reader_settings = reader_settings
        self._open_settings = open_settings_func

        self._error_handlers: dict[
            ErrorTypes,
            Callable[
                [
                    ErrorInfo | None,
                    Callable[[str | None], None],
                    str,
                ],
                None,
            ],
        ] = {
            ErrorTypes.FantagraphicsVolumeRootNotSet: self._handle_fanta_root_not_set,
            ErrorTypes.FantagraphicsVolumeRootNotFound: self._handle_fanta_root_not_found,
            ErrorTypes.DuplicateVolumeArchiveFiles: self._handle_duplicate_archive_files,
            ErrorTypes.TooManyVolumeArchiveFiles: self._handle_too_many_archive_files,
            ErrorTypes.MissingArchiveVolumes: self._handle_missing_volumes,
            ErrorTypes.MissingVolumeCannotShowTitle: self._handle_cannot_show_title,
            ErrorTypes.ArchiveVolumeNotAvailable: self._handle_volume_not_available,
        }

    def handle_error(
        self,
        error_type: ErrorTypes,
        error_info: ErrorInfo | None,
        on_popup_closed: Callable[[str], None] | None = None,
        popup_title: str = "",
    ) -> None:
        handler = self._error_handlers.get(error_type)
        if handler:
            handler(error_info, on_popup_closed, popup_title)
        else:
            msg = f"No handler configured for error type: {error_type}"
            raise ValueError(msg)

    def _handle_fanta_root_not_set(
        self,
        _error_info: ErrorInfo | None,
        on_popup_closed: Callable[[str], None],
        popup_title: str,
    ) -> None:
        """Handle the case where the Fantagraphics directory has not been set."""
        msg = dedent("""\
            Currently, in the app settings, the Fantagraphics comic zips directory has
            not been set. You need to go to settings and enter the zips directory, then
            restart the app.""")

        title = popup_title if popup_title else "Fantagraphics Directory Not Set"

        self._show_settings_error_popup(
            title=title,
            text=msg,
            on_popup_closed=on_popup_closed,
            close_message=_FANTA_VOLUMES_NOT_SET_FIX_SETTINGS_MSG,
        )

    def _handle_fanta_root_not_found(
        self,
        _error_info: ErrorInfo | None,
        on_popup_closed: Callable[[str], None],
        popup_title: str,
    ) -> None:
        """Handle the case where the Fantagraphics directory is not found."""
        fanta_volume_dir = textwrap.fill(str(self._reader_settings.fantagraphics_volumes_dir), 50)

        msg = dedent(f"""\
            In app settings, the Fantagraphics comic zips directory is

                [b]"{fanta_volume_dir}"[/b]

            But this directory could not be found. You need to go to
            settings and enter the correct directory, then restart the
            app.""")

        title = popup_title if popup_title else "Fantagraphics Directory Not Found"

        self._show_settings_error_popup(
            title=title,
            text=msg,
            on_popup_closed=on_popup_closed,
            close_message=_FANTA_VOLUMES_NOT_FOUND_FIX_SETTINGS_MSG,
        )

    def _handle_duplicate_archive_files(
        self,
        error_info: ErrorInfo | None,
        on_popup_closed: Callable[[str], None],
        popup_title: str,
    ) -> None:
        """Handle duplicate Fantagraphics archive files."""
        assert error_info is not None

        archive_file = textwrap.fill(str(error_info.file), 50)
        assert error_info.duplicate_volumes is not None
        # noinspection LongLine
        msg = dedent(f"""\
            There were duplicate Fantagraphics archive files in the directory:

                [b]"{archive_file}"[/b]

            The duplicate volumes are {", ".join(map(str, error_info.duplicate_volumes))}. You need to
            make sure the archives are prefixed with the numbers
            {FIRST_VOLUME_NUMBER:02d} to {LAST_VOLUME_NUMBER:02d} inclusive, without duplicates, then restart the app.""")  # noqa: E501

        title = popup_title if popup_title else "Wrong Fantagraphics Archive File"

        self._show_fatal_config_error(
            title=title,
            error_msg=msg,
            on_popup_closed=on_popup_closed,
        )

    def _handle_too_many_archive_files(
        self,
        error_info: ErrorInfo | None,
        on_popup_closed: Callable[[str], None],
        popup_title: str,
    ) -> None:
        """Handle finding too many Fantagraphics archive files."""
        assert error_info is not None

        # noinspection LongLine
        msg = dedent(f"""\
            There were too many Fantagraphics archive files. The
            expected number of files is {error_info.num_volumes} not {error_info.num_archive_files}. You need to
            make sure the archives are prefixed with the numbers
            {FIRST_VOLUME_NUMBER:02d} to {LAST_VOLUME_NUMBER:02d} inclusive, then restart the app.""")  # noqa: E501

        title = popup_title if popup_title else "Too Many Fantagraphics Archives"

        self._show_fatal_config_error(
            title=title,
            error_msg=msg,
            on_popup_closed=on_popup_closed,
        )

    def _handle_missing_volumes(
        self,
        error_info: ErrorInfo | None,
        _on_popup_closed: Callable[[str], None] | None = None,
        _popup_title: str = "",
    ) -> None:
        """Handle Fantagraphics volumes missing."""
        assert error_info is not None
        assert error_info.missing_volumes is not None

        missing_volumes_str = ", ".join(map(str, error_info.missing_volumes))
        if len(error_info.missing_volumes) == 1:
            title = "Fantagraphics Volume Missing"
            msg = (
                f"Fantagraphics volume '{missing_volumes_str}' is missing.\n\n"
                f"You won't be able to read any titles from this volume."
            )
        else:
            title = "Fantagraphics Volumes Missing"
            msg = (
                f"Fantagraphics volumes '{missing_volumes_str}' are missing.\n\n"
                f"You won't be able to read any titles from these volumes."
            )

        self._show_popup_with_close(title=title, text=msg)

    def _handle_cannot_show_title(
        self,
        error_info: ErrorInfo | None,
        _on_popup_closed: Callable[[str], None] | None = None,
        _popup_title: str = "",
    ) -> None:
        """Handle cannot show title because volume is missing."""
        assert error_info is not None
        assert error_info.missing_volumes is not None
        assert len(error_info.missing_volumes) == 1
        assert error_info.title is not None

        title = "Fantagraphics Volume Missing"
        msg = (
            f'Cannot show the title "{BARKS_TITLES[error_info.title]}".\n\n'
            f"Fantagraphics volume '{error_info.missing_volumes[0]}' is missing."
        )

        self._show_popup_with_close(title=title, text=msg)

    def _handle_volume_not_available(
        self,
        error_info: ErrorInfo | None,
        _on_popup_closed: Callable[[str], None] | None = None,
        _popup_title: str = "",
    ) -> None:
        """Handle Fantagraphics volume not available."""
        assert error_info is not None
        assert error_info.title is not None

        cannot_show = f'Cannot show the title [b]"{BARKS_TITLES[error_info.title]}."[/b]'

        if error_info.file_volume == -1:
            title = "Fantagraphics Volume Not Available"
            msg = (
                f"{cannot_show}\n\nThe Fantagraphics volume containing this"
                f" title is not available yet."
            )
        else:
            title = "Fantagraphics Volume Not Found"
            msg = (
                f"{cannot_show}\n\n"
                f"This title is in Fantagraphics Volume {error_info.file_volume}"
                f" which could not be found."
            )

        self._show_popup_with_close(title=title, text=msg)

    def _show_popup_with_close(self, title: str, text: str) -> None:
        def _on_close() -> None:
            popup.dismiss()

        popup = self._show_popup(
            title=title,
            text=text,
            msg_halign="center",
            ok_text="",  # No OK button
            ok_func=None,
            cancel_text="Close",
            cancel_func=_on_close,
        )

    def _show_settings_error_popup(
        self,
        title: str,
        text: str,
        on_popup_closed: Callable[[str], None],
        close_message: str,
    ) -> None:
        """Show a popup for a settings-related error, offering to open settings."""

        def _on_goto_settings() -> None:
            popup.dismiss()
            self._open_settings()
            on_popup_closed(close_message)

        def _on_cancel() -> None:
            popup.dismiss()
            on_popup_closed(close_message)

        popup = self._show_popup(
            title=title,
            text=text,
            ok_text="Settings",
            ok_func=_on_goto_settings,
            cancel_text="Cancel",
            cancel_func=_on_cancel,
        )

    def _show_fatal_config_error(
        self, title: str, error_msg: str, on_popup_closed: Callable[[str], None]
    ) -> None:
        """Show a non-recoverable error popup that only has a 'Close' button.

        and inform the user they must restart the app after fixing the issue.
        """

        def _on_close() -> None:
            popup.dismiss()
            on_popup_closed(_WRONG_FANTA_VOLUMES_FIX_AND_RESTART_MSG)

        popup = self._show_popup(
            title=title,
            text=error_msg,
            ok_text="",  # No OK button
            ok_func=None,
            cancel_text="Close",
            cancel_func=_on_close,
        )

    @staticmethod
    def _show_popup(
        title: str,
        text: str,
        ok_text: str,
        ok_func: Callable[[], None] | None,
        cancel_text: str,
        cancel_func: Callable[[], None] | None,
        msg_halign: str = "justify",
    ) -> MessagePopup:
        """Create and display the MessagePopup."""
        popup = MessagePopup(
            text=text,
            ok_func=ok_func,
            ok_text=ok_text,
            cancel_func=cancel_func,
            cancel_text=cancel_text,
            title=title,
            msg_halign=msg_halign,
        )
        # Schedule the opening for the next frame to avoid potential graphics issues
        Clock.schedule_once(lambda _dt: popup.open(), 0)

        return popup


def get_volume_not_available_error_info(image_info: ImageInfo) -> ErrorInfo:
    # noinspection PyTypeChecker
    fanta_volume = (
        -1
        if image_info.from_title not in ALL_FANTA_COMIC_BOOK_INFO
        else (
            get_fanta_volume_from_str(
                ALL_FANTA_COMIC_BOOK_INFO[image_info.from_title].fantagraphics_volume
            )
        )
    )
    return ErrorInfo(file_volume=fanta_volume, title=image_info.from_title)
