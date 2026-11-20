"""The two log line formats, which the log configs here and in the sibling repos load by name."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from comic_utils.loguru_setup import (
    LOGGER_SYS_NAME_KEY,
    log_to_console_formatter,
    log_to_file_formatter,
)
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Callable

_STAMP = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}"
_WHERE = r"[\w.]+:log_one_line:\d+"


def log_one_line(formatter: Callable[[object], str], message: str) -> str:
    """Return the line a real loguru sink writes for `message` under `formatter`."""
    lines: list[str] = []
    sink_id = logger.add(lines.append, format=formatter, colorize=False, level="DEBUG")
    try:
        logger.bind(**{LOGGER_SYS_NAME_KEY: "app"}).warning(message)
    finally:
        logger.remove(sink_id)
    [line] = lines
    return line


def test_the_system_name_is_the_key_the_formats_read() -> None:
    assert LOGGER_SYS_NAME_KEY == "sys_name"


def test_a_console_line_puts_where_it_was_logged_at_the_end() -> None:
    line = log_one_line(log_to_console_formatter, "Quack.")
    assert re.fullmatch(rf"{_STAMP} \| WARNING  \| app : Quack\.  \[{_WHERE}\]\n", line), line


def test_a_file_line_puts_where_it_was_logged_before_the_message() -> None:
    line = log_one_line(log_to_file_formatter, "Quack.")
    assert re.fullmatch(rf"{_STAMP} \| WARNING  \| app : {_WHERE} - Quack\.\n", line), line


@pytest.mark.parametrize("formatter", [log_to_console_formatter, log_to_file_formatter])
def test_braces_in_a_message_are_logged_as_written(formatter: Callable[[object], str]) -> None:
    assert "Tricky {} and {name}" in log_one_line(formatter, "Tricky {} and {name}")
