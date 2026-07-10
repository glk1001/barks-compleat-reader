"""Popup presentation for user-facing errors.

Message composition is pure and lives in `core.user_error_messages`; this
module only maps each `ErrorDialogKind` onto a `MessagePopup` layout and its
button wiring. Satisfies `core.user_error_types.UserErrorHandlerPort`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.clock import Clock

from barks_reader.core.user_error_messages import (
    ErrorDialogKind,
    ErrorPresentation,
    build_error_presentation,
)

from .popup_widgets import MessagePopup

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

    def _show_popup_with_close(self, presentation: ErrorPresentation) -> None:
        def _on_close() -> None:
            popup.dismiss()

        popup = self._show_popup(
            title=presentation.title,
            text=presentation.text,
            msg_halign="center",
            ok_text="",  # No OK button
            ok_func=None,
            cancel_text="Close",
            cancel_func=_on_close,
        )

    def _show_settings_error_popup(
        self,
        presentation: ErrorPresentation,
        on_popup_closed: Callable[[str], None] | None,
    ) -> None:
        """Show a popup for a settings-related error, offering to open settings."""

        def _on_goto_settings() -> None:
            popup.dismiss()
            self._open_settings()
            assert on_popup_closed
            on_popup_closed(presentation.close_message)

        def _on_cancel() -> None:
            popup.dismiss()
            assert on_popup_closed
            on_popup_closed(presentation.close_message)

        popup = self._show_popup(
            title=presentation.title,
            text=presentation.text,
            ok_text="Settings",
            ok_func=_on_goto_settings,
            cancel_text="Cancel",
            cancel_func=_on_cancel,
        )

    def _show_fatal_config_error(
        self,
        presentation: ErrorPresentation,
        on_popup_closed: Callable[[str], None] | None,
    ) -> None:
        """Show a non-recoverable error popup that only has a 'Close' button.

        and inform the user they must restart the app after fixing the issue.
        """

        def _on_close() -> None:
            popup.dismiss()
            assert on_popup_closed
            on_popup_closed(presentation.close_message)

        popup = self._show_popup(
            title=presentation.title,
            text=presentation.text,
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
