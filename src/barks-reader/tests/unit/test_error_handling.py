"""The fatal-error path: one popup, the error logged without markup, then exit 1."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from barks_reader._version import VERSION
from barks_reader.ui import error_handling, kivy_standalone_error_popup


def test_the_popup_is_shown_with_the_error_then_the_app_exits(loguru_sink: list[str]) -> None:
    with (
        patch.object(kivy_standalone_error_popup, "show_error_popup") as show,
        pytest.raises(SystemExit) as exited,
    ):
        error_handling.handle_app_fail(
            "installer",
            "Installer Error",
            "Could not find [b]the data pack[/b]",
            "some [i]details[/i]",
            "/logs/app.log",
            log_the_error=True,
            background_image_file=Path("/art/error.png"),
        )

    assert exited.value.code == 1
    show.assert_called_once_with(
        title_bar_text="Installer",
        title="Installer Error",
        message="Could not find [b]the data pack[/b]",
        log_path="/logs/app.log",
        severity="error",
        details="some [i]details[/i]",
        show_details=False,
        timeout=0,
        background_image_file=Path("/art/error.png"),
    )
    # The popup renders the markup; the log gets plain text.
    assert "An installer error occurred: Could not find the data pack." in loguru_sink
    assert "some details" in loguru_sink


def test_the_error_need_not_be_logged(loguru_sink: list[str]) -> None:
    with (
        patch.object(kivy_standalone_error_popup, "show_error_popup"),
        pytest.raises(SystemExit),
    ):
        error_handling.handle_app_fail(
            "app",
            "Title",
            "message",
            "details",
            "/log",
            log_the_error=False,
            background_image_file=None,
        )

    assert loguru_sink == []


def test_a_traceback_becomes_the_message_and_the_details() -> None:
    try:
        msg = "boom"
        raise ValueError(msg)  # noqa: TRY301
    except ValueError:
        exc_info = sys.exc_info()

    with patch.object(error_handling, error_handling.handle_app_fail.__name__) as fail:
        error_handling.handle_app_fail_with_traceback(
            "app", "App Error", *exc_info, "/logs/app.log"
        )

    app_type, title, message, details, log_path, log_the_error, background = fail.call_args.args
    assert (app_type, title, log_path) == ("app", "App Error", "/logs/app.log")
    assert message == "ValueError: boom"
    assert details.startswith("Full Traceback:\nTraceback (most recent call last):")
    assert "raise ValueError(msg)" in details
    assert f"  - Version: {VERSION}\n" in details
    assert log_the_error is True
    assert background is None
