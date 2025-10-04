from __future__ import annotations

from enum import Enum, auto
from textwrap import dedent
from typing import TYPE_CHECKING

from barks_fantagraphics.fanta_comics_info import FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER
from kivy.clock import Clock

from barks_reader.reader_ui_classes import MessagePopup

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_reader.fantagraphics_volumes import (
        TooManyArchiveFilesError,
        WrongFantagraphicsVolumeError,
    )
    from barks_reader.reader_settings import ReaderSettings


class ErrorTypes(Enum):
    FantagraphicsVolumeRootNotSet = auto()
    FantagraphicsVolumeRootNotFound = auto()
    WrongFantagraphicsVolume = auto()
    TooManyArchiveFiles = auto()


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
                    WrongFantagraphicsVolumeError | TooManyArchiveFilesError | None,
                    Callable[[str | None], None],
                    str,
                ],
                None,
            ],
        ] = {
            ErrorTypes.FantagraphicsVolumeRootNotSet: self._handle_fanta_root_not_set,
            ErrorTypes.FantagraphicsVolumeRootNotFound: self._handle_fanta_root_not_found,
            ErrorTypes.WrongFantagraphicsVolume: self._handle_wrong_fanta_volume,
            ErrorTypes.TooManyArchiveFiles: self._handle_too_many_archive_files,
        }

    def handle_error(
        self,
        error_type: ErrorTypes,
        exception: WrongFantagraphicsVolumeError | TooManyArchiveFilesError | None,
        on_popup_closed: Callable[[str | None], None],
        popup_title: str = "",
    ) -> None:
        handler = self._error_handlers.get(error_type)
        if handler:
            handler(exception, on_popup_closed, popup_title)
        else:
            msg = f"No handler configured for error type: {error_type}"
            raise ValueError(msg)

    def _handle_fanta_root_not_set(
        self,
        _exception: Exception | None,
        on_popup_closed: Callable[[str | None], None],
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
            close_message=FANTA_VOLUMES_NOT_SET_FIX_SETTINGS_MSG,
        )

    def _handle_fanta_root_not_found(
        self,
        _exception: Exception | None,
        on_popup_closed: Callable[[str | None], None],
        popup_title: str,
    ) -> None:
        """Handle the case where the Fantagraphics directory is not found."""
        msg = dedent(f"""\
            In the app settings, the Fantagraphics comic zips directory is

                [b]"{self._reader_settings.fantagraphics_volumes_dir}"[/b]

            But this directory could not be found. You need to go to settings
            and enter the correct directory, then restart the app.""")
        title = popup_title if popup_title else "Fantagraphics Directory Not Found"
        self._show_settings_error_popup(
            title=title,
            text=msg,
            on_popup_closed=on_popup_closed,
            close_message=FANTA_VOLUMES_NOT_FOUND_FIX_SETTINGS_MSG,
        )

    def _handle_wrong_fanta_volume(
        self,
        exception: WrongFantagraphicsVolumeError,
        on_popup_closed: Callable[[str | None], None],
        _popup_title: str,
    ) -> None:
        """Handle an unexpected Fantagraphics archive file."""
        # noinspection LongLine
        msg = dedent(f"""\
            There was an unexpected Fantagraphics archive file:

            [size=16sp][b]"{exception.file}".[/b][/size]

            The expected volume number was {exception.expected_volume} not {exception.file_vol}. You need to
            make sure the archives are prefixed with the numbers
            {FIRST_VOLUME_NUMBER:02d} to {LAST_VOLUME_NUMBER:02d} inclusive, then restart the app.""")  # noqa: E501

        self._show_fatal_config_error(
            title="Wrong Fantagraphics Archive File",
            error_msg=msg,
            on_popup_closed=on_popup_closed,
        )

    def _handle_too_many_archive_files(
        self,
        exception: TooManyArchiveFilesError,
        on_popup_closed: Callable[[str | None], None],
        _popup_title: str,
    ) -> None:
        """Handle finding too many Fantagraphics archive files."""
        # noinspection LongLine
        msg = dedent(f"""\
            There were too many Fantagraphics archive files. The
            expected number of files is {exception.num_volumes} not {exception.num_archive_files}. You need to
            make sure the archives are prefixed with the numbers
            {FIRST_VOLUME_NUMBER:02d} to {LAST_VOLUME_NUMBER:02d} inclusive, then restart the app.""")  # noqa: E501

        self._show_fatal_config_error(
            title="Too Many Fantagraphics Archives",
            error_msg=msg,
            on_popup_closed=on_popup_closed,
        )

    def _show_settings_error_popup(
        self,
        title: str,
        text: str,
        on_popup_closed: Callable[[str | None], None],
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
            ok_text="Goto settings",
            ok_func=_on_goto_settings,
            cancel_text="Cancel",
            cancel_func=_on_cancel,
        )

    def _show_fatal_config_error(
        self, title: str, error_msg: str, on_popup_closed: Callable[[str | None], None]
    ) -> None:
        """Show a non-recoverable error popup that only has a 'Close' button.

        and inform the user they must restart the app after fixing the issue.
        """

        def _on_close() -> None:
            popup.dismiss()
            on_popup_closed(WRONG_FANTA_VOLUMES_FIX_AND_RESTART_MSG)

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
        cancel_func: Callable[[], None],
    ) -> MessagePopup:
        """Create and display the MessagePopup."""
        popup = MessagePopup(
            text=text,
            ok_func=ok_func,
            ok_text=ok_text,
            cancel_func=cancel_func,
            cancel_text=cancel_text,
            title=title,
        )
        # Schedule the opening for the next frame to avoid potential graphics issues
        Clock.schedule_once(lambda _dt: popup.open(), 0)

        return popup
