"""The focus ring names where it landed, so a host's tests can step focus by the log."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from kivy.logger import Logger
from okf_reader.ui import focus_ring
from okf_reader.ui.focus_ring import describe_widget, draw_focus_ring

if TYPE_CHECKING:
    from collections.abc import Iterator


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.fixture
def kivy_log() -> Iterator[list[str]]:
    handler = _Capture()
    level = Logger.level
    Logger.setLevel(logging.DEBUG)
    Logger.addHandler(handler)
    try:
        yield handler.messages
    finally:
        Logger.removeHandler(handler)
        Logger.setLevel(level)


def test_describe_names_the_class_and_text() -> None:
    widget = MagicMock()
    widget.text = "Back"
    assert describe_widget(widget) == 'MagicMock "Back"'


def test_describe_without_text_is_the_class_alone() -> None:
    widget = MagicMock()
    widget.text = ""
    assert describe_widget(widget) == "MagicMock"


def test_describe_cuts_long_text() -> None:
    widget = MagicMock()
    widget.text = "word " * 20
    described = describe_widget(widget)
    assert described.endswith('…"')
    assert len(described) < len(widget.text)


def test_drawing_a_ring_logs_it(kivy_log: list[str]) -> None:
    widget = MagicMock()
    widget.text = "Back"
    with patch.object(focus_ring, "Color"), patch.object(focus_ring, "Line"):
        draw_focus_ring(widget)
    assert 'OKFViewer: Focus ring on MagicMock "Back".' in kivy_log
