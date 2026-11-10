"""The fatal-error path: one popup, the error logged without markup, then exit 1."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import kivy.base
import kivy.clock
import pytest
from barks_reader._version import VERSION
from barks_reader.ui import error_handling, kivy_standalone_error_popup

if TYPE_CHECKING:
    from types import TracebackType


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


_SUBSCRIPT_LINE = '_ = pages["key"][i]'
type _ExcInfo = tuple[type[BaseException], BaseException, TracebackType | None]


def _raise_from_a_line_with_subscripts() -> None:
    pages: dict[str, list[int]] = {"key": []}
    i = 0
    _ = pages["key"][i]


def _exc_info_with_subscripts() -> _ExcInfo:
    try:
        _raise_from_a_line_with_subscripts()
    except IndexError as e:
        return type(e), e, e.__traceback__
    raise AssertionError  # pragma: no cover


def test_plain_text_keeps_a_bracket_that_was_text() -> None:
    line = "got items[i] & one of ['a', 'b']"
    markup = f"[b]Error:[/b] {error_handling.escape_markup(line)}"
    assert error_handling.plain_text(markup) == f"Error: {line}"


def test_a_tracebacks_brackets_reach_the_popup_escaped_and_the_log_whole(
    loguru_sink: list[str],
) -> None:
    with (
        patch.object(kivy_standalone_error_popup, "show_error_popup") as show,
        pytest.raises(SystemExit),
    ):
        error_handling.handle_app_fail_with_traceback(
            "app", "App Error", *_exc_info_with_subscripts(), "/logs/app.log"
        )

    details = show.call_args.kwargs["details"]
    assert "[" not in details  # nothing for the popup's labels to read as a tag
    assert _SUBSCRIPT_LINE in error_handling.plain_text(details)
    assert any(_SUBSCRIPT_LINE in line for line in loguru_sink)


def test_the_error_is_logged_even_when_the_popup_cannot_be_shown(
    loguru_sink: list[str],
) -> None:
    with (
        patch.object(
            kivy_standalone_error_popup, "show_error_popup", side_effect=TypeError("no window")
        ),
        pytest.raises(TypeError),
    ):
        error_handling.handle_app_fail(
            "app",
            "Title",
            "message",
            "details",
            "/log",
            log_the_error=True,
            background_image_file=None,
        )

    assert "An app error occurred: message." in loguru_sink
    assert "details" in loguru_sink


def _fail_on_a_worker_thread(exc_info: _ExcInfo) -> None:
    worker = threading.Thread(
        target=error_handling.handle_app_fail_with_traceback,
        args=("app", "App Error", *exc_info, "/logs/app.log"),
    )
    worker.start()
    worker.join()


def test_a_worker_threads_error_is_logged_and_raised_again_on_the_main_thread(
    loguru_sink: list[str],
) -> None:
    exc_info = _exc_info_with_subscripts()
    with (
        patch.object(kivy_standalone_error_popup, "show_error_popup") as show,
        patch.object(kivy.base.EventLoop, "status", "started"),
        patch.object(kivy.clock.Clock, "schedule_once") as schedule,
        patch.object(error_handling, "_exit_process") as exit_process,
    ):
        _fail_on_a_worker_thread(exc_info)

    show.assert_not_called()  # no widgets off the main thread
    exit_process.assert_not_called()
    assert "An app error occurred: IndexError: list index out of range." in loguru_sink
    assert any(_SUBSCRIPT_LINE in line for line in loguru_sink)
    raise_it = schedule.call_args.args[0]
    with pytest.raises(IndexError) as raised:
        raise_it(0.0)
    assert raised.value is exc_info[1]


def test_a_worker_threads_error_with_no_kivy_loop_ends_the_process(
    loguru_sink: list[str],
) -> None:
    with (
        patch.object(kivy_standalone_error_popup, "show_error_popup") as show,
        patch.object(kivy.base.EventLoop, "status", "idle"),
        patch.object(kivy.clock.Clock, "schedule_once") as schedule,
        patch.object(error_handling, "_exit_process") as exit_process,
    ):
        _fail_on_a_worker_thread(_exc_info_with_subscripts())

    show.assert_not_called()
    schedule.assert_not_called()
    exit_process.assert_called_once_with()
    assert "An app error occurred: IndexError: list index out of range." in loguru_sink
    assert "No Kivy loop to show the error in: exiting." in loguru_sink
