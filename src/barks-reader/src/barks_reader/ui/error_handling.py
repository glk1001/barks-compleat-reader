"""The fatal-error path: the error logged, one popup, then exit 1."""

from __future__ import annotations

import os
import sys
import threading
from typing import TYPE_CHECKING, NoReturn

from barks_fantagraphics.speech_markup import escape_markup, unescape_markup
from loguru import logger

from barks_reader.core.crash_report import crash_report

if TYPE_CHECKING:
    from pathlib import Path
    from types import TracebackType


def handle_app_fail_with_traceback(
    app_type: str,
    msg_title: str,
    exc_type: type[BaseException] | None,
    exc_value: BaseException | None,
    exc_traceback: TracebackType | None,
    log_path: str,
    log_the_error: bool = True,
    background_image_file: Path | None = None,
) -> None:
    """Report an uncaught exception: log it, show the error popup, exit 1.

    The popup's widgets can only be built on the main thread. Called on another, this
    logs the error and hands the exception to the main thread (`_fail_on_main_thread`).

    Args:
        app_type: What failed ("app", "installer"), for the popup's bar and the log.
        msg_title: The popup's title.
        exc_type: The exception's type, as ``sys.excepthook`` gets it.
        exc_value: The exception.
        exc_traceback: Its traceback.
        log_path: The log file the popup points to, or "" for none.
        log_the_error: Whether to log the error here.
        background_image_file: Optional art behind the popup.

    """
    # Optional as ``sys.exc_info()`` types them; every caller is handling an exception.
    assert exc_type is not None
    assert exc_value is not None

    # A traceback is text, not markup: its brackets are escaped for the popup's labels,
    # and come back as brackets in the log, the saved file and the clipboard.
    message, details = (
        escape_markup(text) for text in crash_report(exc_type, exc_value, exc_traceback)
    )

    if threading.current_thread() is not threading.main_thread():
        if log_the_error:
            _log_the_error(app_type, message, details)
        _fail_on_main_thread(exc_value)
        return

    handle_app_fail(
        app_type, msg_title, message, details, log_path, log_the_error, background_image_file
    )


def handle_app_fail(
    app_type: str,
    msg_title: str,
    message: str,
    details: str,
    log_path: str,
    log_the_error: bool,
    background_image_file: Path | None,
    show_details: bool = False,
) -> None:
    """Log a fatal error, show it on the error popup, then exit 1. Main thread only.

    The error is logged before the popup is built, so a popup that cannot be shown
    still leaves the error in the log.

    Args:
        app_type: What failed ("app", "installer"), for the popup's bar and the log.
        msg_title: The popup's title.
        message: The error in brief, as Kivy markup.
        details: The rest, as Kivy markup.
        log_path: The log file the popup points to, or "" for none.
        log_the_error: Whether to log the error here.
        background_image_file: Optional art behind the popup.
        show_details: Whether the popup opens with its details showing.

    """
    if log_the_error:
        _log_the_error(app_type, message, details)

    from .kivy_standalone_error_popup import show_error_popup  # noqa: PLC0415

    show_error_popup(
        title_bar_text=app_type.capitalize(),
        title=msg_title,
        message=message,
        log_path=log_path,
        severity="error",
        details=details,
        show_details=show_details,
        timeout=0,
        background_image_file=background_image_file,
    )

    sys.exit(1)


def _log_the_error(app_type: str, message: str, details: str) -> None:
    logger.critical(f"An {app_type} error occurred: {plain_text(message)}.")
    logger.critical(plain_text(details))


def plain_text(markup: str) -> str:
    """Return the error popup's markup as plain text: its tags gone, its escapes undone.

    Args:
        markup: Kivy markup, a bracket that is text escaped (``escape_markup``) as a
            traceback's are.

    Returns:
        The text for the log, the saved report and the clipboard.

    """
    from barks_reader.core.reader_formatter import (  # noqa: PLC0415
        get_text_with_markup_stripped,
    )

    return unescape_markup(get_text_with_markup_stripped(markup))


def _fail_on_main_thread(exc_value: BaseException) -> None:
    """Hand a worker thread's exception to the main thread, or end the process.

    With the Kivy loop running, the exception is raised again from a Clock callback: it
    unwinds the app's run, and the main thread's own hook shows the popup and exits. With
    no loop to raise it in there is no way to show a popup, so the process ends here: a
    ``sys.exit`` on this thread would end only the thread.
    """
    from kivy.base import EventLoop  # noqa: PLC0415
    from kivy.clock import Clock  # noqa: PLC0415

    def raise_it(_dt: float) -> NoReturn:
        raise exc_value

    if EventLoop.status == "started":
        Clock.schedule_once(raise_it, 0)
    else:
        logger.critical("No Kivy loop to show the error in: exiting.")
        _exit_process()


def _exit_process() -> NoReturn:
    os._exit(1)
