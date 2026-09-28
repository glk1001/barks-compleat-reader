"""Which buttons each kind of error popup gets, and what they do."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core.user_error_messages import ErrorDialogKind, ErrorPresentation
from barks_reader.core.user_error_types import ErrorTypes
from barks_reader.ui import user_error_handler as handler_module
from barks_reader.ui.user_error_handler import UserErrorHandler

if TYPE_CHECKING:
    from collections.abc import Mapping


def _shown(kind: ErrorDialogKind) -> tuple[Mapping[str, Any], MagicMock, MagicMock]:
    """Show an error of `kind`; return the popup's arguments, open-settings and on-closed."""
    presentation = ErrorPresentation(kind=kind, title="T", text="x", close_message="closed msg")
    open_settings, on_closed = MagicMock(), MagicMock()
    with (
        patch.object(handler_module, "build_error_presentation", return_value=presentation),
        patch.object(handler_module, "open_message_popup") as opened,
    ):
        UserErrorHandler(MagicMock(), open_settings).handle_error(
            ErrorTypes.MissingArchiveVolumes, None, on_closed
        )
    return opened.call_args.kwargs, open_settings, on_closed


def test_a_notice_has_close_only_and_nothing_to_call() -> None:
    kwargs, _, on_closed = _shown(ErrorDialogKind.NOTICE)
    assert (kwargs["ok_text"], kwargs["cancel_text"]) == ("", "Close")
    assert kwargs["on_cancel"] is None
    on_closed.assert_not_called()


def test_a_settings_error_offers_settings_or_cancel() -> None:
    kwargs, open_settings, on_closed = _shown(ErrorDialogKind.GOTO_SETTINGS)
    assert (kwargs["ok_text"], kwargs["cancel_text"]) == ("Settings", "Cancel")
    kwargs["on_ok"]()
    open_settings.assert_called_once()
    on_closed.assert_called_once_with("closed msg")
    kwargs["on_cancel"]()
    assert on_closed.call_count == 2  # noqa: PLR2004
    open_settings.assert_called_once()


@pytest.mark.parametrize("kind", [ErrorDialogKind.FATAL_CONFIG])
def test_a_fatal_error_closes_and_reports_it(kind: ErrorDialogKind) -> None:
    kwargs, open_settings, on_closed = _shown(kind)
    assert (kwargs["ok_text"], kwargs["cancel_text"]) == ("", "Close")
    kwargs["on_cancel"]()
    on_closed.assert_called_once_with("closed msg")
    open_settings.assert_not_called()
