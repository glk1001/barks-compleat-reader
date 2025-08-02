from __future__ import annotations

from enum import Enum, auto
from textwrap import dedent
from typing import TYPE_CHECKING, Callable

from barks_fantagraphics.fanta_comics_info import FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER
from kivy.clock import Clock

from reader_ui_classes import MessagePopup

if TYPE_CHECKING:
    from fantagraphics_volumes import TooManyArchiveFilesError, WrongFantagraphicsVolumeError
    from reader_settings import ReaderSettings


class ErrorTypes(Enum):
    FantagraphicsVolumeRootNotFound = auto()
    WrongFantagraphicsVolume = auto()
    TooManyArchiveFiles = auto()


NOT_ALL_TITLES_LOADED_SETTINGS_MSG = dedent(
    """
    ERROR: TITLES NOT LOADED

    You need to check and fix the
    app settings, then restart the app!
    """
).strip()

NOT_ALL_TITLES_LOADED_FANTA_VOLUME_MSG = dedent(
    """
    ERROR: TITLES NOT LOADED

    You need to check the Fantagraphics
    volume directory, rename or remove any
    wrong archives, then restart the app!
    """
).strip()


class UserErrorHandler:
    def __init__(self, reader_settings: ReaderSettings, open_settings_func: Callable) -> None:
        self._reader_settings = reader_settings
        self._open_settings = open_settings_func

        self._error_handlers: dict[
            ErrorTypes,
            Callable[
                [
                    WrongFantagraphicsVolumeError | TooManyArchiveFilesError | None,
                    Callable[[str], None],
                ],
                None,
            ],
        ] = {
            ErrorTypes.FantagraphicsVolumeRootNotFound: self._handle_fanta_root_not_found,
            ErrorTypes.WrongFantagraphicsVolume: self._handle_wrong_fanta_volume,
            ErrorTypes.TooManyArchiveFiles: self._handle_too_many_archive_files,
        }

    def handle_error(
        self,
        error_type: ErrorTypes,
        exception: WrongFantagraphicsVolumeError | TooManyArchiveFilesError | None,
        on_popup_closed: Callable[[str | None], None],
    ) -> None:
        handler = self._error_handlers.get(error_type)
        if handler:
            handler(exception, on_popup_closed)
        else:
            msg = f"No handler configured for error type: {error_type}"
            raise ValueError(msg)

    def _handle_fanta_root_not_found(
        self,
        _exception: Exception | None,
        on_popup_closed: Callable[[str | None], None],
    ) -> None:
        """Handle the case where the Fantagraphics directory is not found."""

        def _on_goto_settings() -> None:
            popup.dismiss()
            self._open_settings()
            on_popup_closed(NOT_ALL_TITLES_LOADED_SETTINGS_MSG)

        def _on_cancel() -> None:
            popup.dismiss()
            on_popup_closed(NOT_ALL_TITLES_LOADED_SETTINGS_MSG)

        msg = (
            f"Currently, in the app settings, the Fantagraphics comic zips directory is\n\n"
            f'    [b]"{self._reader_settings.fantagraphics_volumes_dir}"[/b]\n\n'
            "But this directory could not be found. You need to go to settings and enter\n"
            "the correct directory, then restart the app."
        )

        popup = self._show_popup(
            title="Fantagraphics Directory Not Found",
            text=msg,
            ok_text="Goto settings",
            ok_func=_on_goto_settings,
            cancel_text="Cancel",
            cancel_func=_on_cancel,
        )

    def _handle_wrong_fanta_volume(
        self,
        exception: WrongFantagraphicsVolumeError,
        on_popup_closed: Callable[[str | None], None],
    ) -> None:
        """Handle an unexpected Fantagraphics archive file."""
        msg = (
            f"There was a unexpected Fantagraphics archive file:\n\n"
            f'[size=16sp][b]"{exception.file}".[/b][/size]\n\n'
            f"The expected volume number was {exception.expected_volume} not {exception.file_vol}."
            f" You need to make sure the\n"
            f"archives are prefixed with the numbers {FIRST_VOLUME_NUMBER:02d} to"
            f" {LAST_VOLUME_NUMBER:02d} inclusive, then restart\n"
            f"the app."
        )

        self._show_fatal_config_error(
            title="Wrong Fantagraphics Archive File",
            error_msg=msg,
            on_popup_closed=on_popup_closed,
        )

    def _handle_too_many_archive_files(
        self,
        exception: TooManyArchiveFilesError,
        on_popup_closed: Callable[[str | None], None],
    ) -> None:
        """Handle finding too many Fantagraphics archive files."""
        msg = (
            f"There were too many Fantagraphics archive files. The expected number\n"
            f"of files is {exception.num_volumes} not {exception.num_archive_files}."
            f" You need to make sure the archives are prefixed\n"
            f"with the numbers {FIRST_VOLUME_NUMBER:02d} to {LAST_VOLUME_NUMBER:02d} inclusive,"
            f" then restart the app."
        )

        self._show_fatal_config_error(
            title="Too Many Fantagraphics Archives",
            error_msg=msg,
            on_popup_closed=on_popup_closed,
        )

    def _show_fatal_config_error(
        self, title: str, error_msg: str, on_popup_closed: Callable[[str | None], None]
    ) -> None:
        """Show a non-recoverable error popup that only has a 'Close' button.

        and inform the user they must restart the app after fixing the issue.
        """

        def _on_close() -> None:
            popup.dismiss()
            on_popup_closed(NOT_ALL_TITLES_LOADED_FANTA_VOLUME_MSG)

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
