"""What the OKF reader's tests share: Kivy's log, as a host that routes it would see it."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from kivy.logger import Logger

if TYPE_CHECKING:
    from collections.abc import Iterator


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.messages: list[str] = []
        self.levels: list[tuple[int, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())
        self.levels.append((record.levelno, record.getMessage()))


@pytest.fixture
def _kivy_capture() -> Iterator[_Capture]:
    handler = _Capture()
    level = Logger.level
    Logger.setLevel(logging.DEBUG)
    Logger.addHandler(handler)
    try:
        yield handler
    finally:
        Logger.removeHandler(handler)
        Logger.setLevel(level)


@pytest.fixture
def kivy_log(_kivy_capture: _Capture) -> list[str]:
    """Collect every message Kivy's logger emits during the test, DEBUG and up."""
    return _kivy_capture.messages


@pytest.fixture
def kivy_log_levels(_kivy_capture: _Capture) -> list[tuple[int, str]]:
    """Collect the same messages, each with the level it was logged at."""
    return _kivy_capture.levels
