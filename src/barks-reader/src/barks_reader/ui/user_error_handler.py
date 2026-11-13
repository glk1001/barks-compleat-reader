"""Popup presentation for user-facing errors.

Message composition is pure and lives in `core.user_error_messages`; this
module only maps each `ErrorDialogKind` onto a message popup's buttons and
their wiring. Satisfies `core.user_error_types.UserErrorHandlerPort`.
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


def _nobody_to_tell(_close_message: str) -> None:
    """Stand in for a caller that did not ask to hear of the popup closing."""


class UserErrorHandler:
    """Show the popup for each kind of user-facing error."""

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
            self._show_popup_with_close(presentation, centred=True)

    @staticmethod
    def _show_popup_with_close(
        presentation: ErrorPresentation,
        on_close: Callable[[], None] | None = None,
        *,
        centred: bool = False,
    ) -> None:
        """Show a popup whose only button is 'Close'."""
        open_message_popup(
            title=presentation.title,
            text=presentation.text,
            ok_text="",  # No OK button
            on_ok=None,
            cancel_text="Close",
            on_cancel=on_close,
            centred=centred,
        )

    def _show_settings_error_popup(
        self,
        presentation: ErrorPresentation,
        on_popup_closed: Callable[[str], None] | None,
    ) -> None:
        """Show a popup for a settings-related error, offering to open settings."""
        on_popup_closed = on_popup_closed or _nobody_to_tell

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
        on_popup_closed = on_popup_closed or _nobody_to_tell
        UserErrorHandler._show_popup_with_close(
            presentation, lambda: on_popup_closed(presentation.close_message)
        )
