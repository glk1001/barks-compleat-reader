"""Kivy's log lines reach the app's loguru log, an exception's traceback included."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from barks_reader.core.kivy_log_handler import LoguruKivyHandler
from loguru import logger

if TYPE_CHECKING:
    import pytest


DENIED = "C:\\Documents and Settings"


def _deny() -> None:
    raise PermissionError(13, "Access is denied", DENIED)


def _kivy_record(msg: str, *, with_exception: bool) -> logging.LogRecord:
    exc_info = None
    if with_exception:
        try:
            _deny()
        except PermissionError:
            exc_info = sys.exc_info()
    return logging.LogRecord(
        "kivy", logging.ERROR, "filechooser.py", 855, msg, None, exc_info, "_generate_file_entries"
    )


def _log_through_a_queued_sink(record: logging.LogRecord) -> list[str]:
    """Emit `record` into a sink queued as the app log's is (``enqueue: True``)."""
    lines: list[str] = []
    handle = logger.add(
        lambda message: lines.append(str(message)),
        format="{extra[sys_name]}: {function}:{line} - {message}\n{exception}",
        enqueue=True,
        catch=True,
    )
    try:
        LoguruKivyHandler(logger, "kivy").emit(record)
        logger.complete()
    finally:
        logger.remove(handle)
    return lines


def test_an_exception_reaches_a_queued_sink_with_its_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Before, the record's bare exc_info could not be pickled for the queue.

    loguru then wrote "Logging error in Loguru Handler" and the traceback to stderr,
    which Kivy shows as warnings, and the line never reached the log.
    """
    record = _kivy_record(f"Unable to open directory <{DENIED}>", with_exception=True)
    lines = _log_through_a_queued_sink(record)
    assert len(lines) == 1
    assert "kivy: _generate_file_entries:855 - Unable to open directory" in lines[0]
    assert "PermissionError: [Errno 13] Access is denied" in lines[0]
    assert "Logging error" not in capsys.readouterr().err


def test_a_plain_line_keeps_its_level_and_braces(capsys: pytest.CaptureFixture[str]) -> None:
    record = _kivy_record("Modules: Start <inspector> with config {}", with_exception=False)
    record.levelno, record.levelname = logging.INFO, "INFO"
    lines = _log_through_a_queued_sink(record)
    assert len(lines) == 1
    assert "_generate_file_entries:855 - Modules: Start <inspector> with config {}" in lines[0]
    assert "Logging error" not in capsys.readouterr().err
