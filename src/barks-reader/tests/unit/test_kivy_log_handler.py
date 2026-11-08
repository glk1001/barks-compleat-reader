"""Kivy's log lines reach the app's loguru log, an exception's traceback included."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from barks_reader.core.kivy_log_handler import LoguruKivyHandler
from loguru import logger

if TYPE_CHECKING:
    import pytest
    from loguru import Record


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


def _log_through_a_queued_sink(record: logging.LogRecord) -> tuple[list[str], str]:
    """Emit `record` into a sink queued as the app log's is (``enqueue: True``).

    Returns:
        The lines the sink got, and how loguru heads a logging error in that sink.
        Only that sink's errors are the handler's: another sink can fail on its own,
        as the default one does when a second pytest run in the process (mutmut's)
        finds the stderr it holds was the first run's, now closed.

    """
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
    return lines, f"Logging error in Loguru Handler #{handle} "


def test_an_exception_reaches_a_queued_sink_with_its_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Before, the record's bare exc_info could not be pickled for the queue.

    loguru then wrote "Logging error in Loguru Handler" and the traceback to stderr,
    which Kivy shows as warnings, and the line never reached the log.
    """
    record = _kivy_record(f"Unable to open directory <{DENIED}>", with_exception=True)
    lines, sink_error = _log_through_a_queued_sink(record)
    assert len(lines) == 1
    assert "kivy: _generate_file_entries:855 - Unable to open directory" in lines[0]
    assert "PermissionError: [Errno 13] Access is denied" in lines[0]
    assert sink_error not in capsys.readouterr().err


def test_a_plain_line_keeps_its_level_and_braces(capsys: pytest.CaptureFixture[str]) -> None:
    record = _kivy_record("Modules: Start <inspector> with config {}", with_exception=False)
    record.levelno, record.levelname = logging.INFO, "INFO"
    lines, sink_error = _log_through_a_queued_sink(record)
    assert len(lines) == 1
    assert "_generate_file_entries:855 - Modules: Start <inspector> with config {}" in lines[0]
    assert sink_error not in capsys.readouterr().err


def _loguru_records_for(record: logging.LogRecord) -> list[Record]:
    """Emit `record` and return the loguru records a plain sink got."""
    records: list[Record] = []
    handle = logger.add(lambda message: records.append(message.record), catch=False)
    try:
        LoguruKivyHandler(logger, "kivy").emit(record)
    finally:
        logger.remove(handle)
    return records


def test_the_loguru_record_says_where_kivy_logged_from() -> None:
    """Every field is Kivy's, not this handler's own file, module and thread."""
    record = _kivy_record("Unable to open directory", with_exception=False)
    record.process, record.thread = 4242, 777

    (loguru_record,) = _loguru_records_for(record)

    assert loguru_record["file"] == "filechooser.py"
    assert loguru_record["function"] == "_generate_file_entries"
    assert loguru_record["line"] == 855  # noqa: PLR2004
    assert loguru_record["module"] == record.module
    assert loguru_record["name"] == "kivy"
    assert loguru_record["process"] == 4242  # noqa: PLR2004
    assert loguru_record["thread"] == 777  # noqa: PLR2004
    assert loguru_record["extra"]["sys_name"] == "kivy"


def test_the_record_keeps_kivy_s_level() -> None:
    (loguru_record,) = _loguru_records_for(_kivy_record("x", with_exception=False))

    assert loguru_record["level"].name == "ERROR"


def test_a_level_loguru_has_no_name_for_is_logged_at_info() -> None:
    """A numeric level with no name in logging ("Level 5") falls back to info."""
    record = _kivy_record("x", with_exception=False)
    record.levelno, record.levelname = 5, "Level 5"

    (loguru_record,) = _loguru_records_for(record)

    assert loguru_record["level"].name == "INFO"
