"""Popup presentation for user-facing errors.

Message composition is pure and lives in `core.user_error_messages`; this
module only maps each `ErrorDialogKind` onto a `MessagePopup` layout and its
button wiring. Satisfies `core.user_error_types.UserErrorHandlerPort`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_reader.core.user_error_messages import (
    ErrorDialogKind,
    ErrorPresentation,
    build_error_presentation,
)

from .popup_widgets import open_message_popup

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_reader.core.reader_settings import ReaderSettings
    from barks_reader.core.user_error_types import ErrorInfo, ErrorTypes


class UserErrorHandler:
    def __init__(
        self, reader_settings: ReaderSettings, open_settings_func: Callable[[], None]
    ) -> None:
        self._reader_settings = reader_settings
        self._open_settings = open_settings_func

    def handle_error(
        self,
        error_type: ErrorTypes,
        error_info: ErrorInfo | None,
        on_popup_closed: Callable[[str], None] | None = None,
        popup_title: str = "",
    ) -> None:
        """Show the popup for *error_type* (see `UserErrorHandlerPort`)."""
        presentation = build_error_presentation(
            error_type, error_info, self._reader_settings, popup_title
        )

        if presentation.kind is ErrorDialogKind.GOTO_SETTINGS:
            self._show_settings_error_popup(presentation, on_popup_closed)
        elif presentation.kind is ErrorDialogKind.FATAL_CONFIG:
            self._show_fatal_config_error(presentation, on_popup_closed)
        else:
            self._show_popup_with_close(presentation)

    @staticmethod
    def _show_popup_with_close(presentation: ErrorPresentation) -> None:
        open_message_popup(
            title=presentation.title,
            text=presentation.text,
            ok_text="",  # No OK button
            on_ok=None,
            cancel_text="Close",
            on_cancel=None,
            msg_halign="center",
        )

    def _show_settings_error_popup(
        self,
        presentation: ErrorPresentation,
        on_popup_closed: Callable[[str], None] | None,
    ) -> None:
        """Show a popup for a settings-related error, offering to open settings."""
        assert on_popup_closed

        def _on_goto_settings() -> None:
            self._open_settings()
            on_popup_closed(presentation.close_message)

        open_message_popup(
            title=presentation.title,
            text=presentation.text,
            ok_text="Settings",
            on_ok=_on_goto_settings,
            cancel_text="Cancel",
            on_cancel=lambda: on_popup_closed(presentation.close_message),
        )

    @staticmethod
    def _show_fatal_config_error(
        presentation: ErrorPresentation,
        on_popup_closed: Callable[[str], None] | None,
    ) -> None:
        """Show a non-recoverable error popup that only has a 'Close' button.

        and inform the user they must restart the app after fixing the issue.
        """
        assert on_popup_closed
        open_message_popup(
            title=presentation.title,
            text=presentation.text,
            ok_text="",  # No OK button
            on_ok=None,
            cancel_text="Close",
            on_cancel=lambda: on_popup_closed(presentation.close_message),
        )
