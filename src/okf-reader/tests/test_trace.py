"""The viewer's trace lines, as a host that routes Kivy's log would see them."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from kivy.logger import Logger
from okf_reader.ui import trace

if TYPE_CHECKING:
    from collections.abc import Iterator

BUNDLE = Path("/bundle")


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.fixture
def kivy_log() -> Iterator[list[str]]:
    """Collect every message Kivy's logger emits during the test, DEBUG and up."""
    handler = _Capture()
    level = Logger.level
    Logger.setLevel(logging.DEBUG)
    Logger.addHandler(handler)
    try:
        yield handler.messages
    finally:
        Logger.removeHandler(handler)
        Logger.setLevel(level)


def test_page_shown_names_the_page_relative_to_the_bundle(kivy_log: list[str]) -> None:
    trace.page_shown(BUNDLE, BUNDLE / "concept" / "stories" / "the-firebug.md", 3)
    assert "OKFViewer: Showed page 'concept/stories/the-firebug.md' (history depth 3)." in kivy_log


def test_a_page_outside_the_bundle_falls_back_to_its_name(kivy_log: list[str]) -> None:
    trace.page_shown(BUNDLE, Path("/elsewhere/orphan.md"), 1)
    assert "OKFViewer: Showed page 'orphan.md' (history depth 1)." in kivy_log


def test_the_navigation_markers(kivy_log: list[str]) -> None:
    trace.focus_region("SIDEBAR")
    trace.focus_ring('ActionButton "Back"')
    trace.tree_focus("The Firebug")
    trace.back_to(BUNDLE, BUNDLE / "index.md")
    trace.back_exit()
    trace.tree_settled("The Firebug", 2)
    trace.page_action("Read comic")
    assert kivy_log == [
        "OKFViewer: Focus region SIDEBAR.",
        'OKFViewer: Focus ring on ActionButton "Back".',
        "OKFViewer: Sidebar focus on tree node 'The Firebug'.",
        "OKFViewer: Back to 'index.md'.",
        "OKFViewer: Back at history root; exiting.",
        "OKFViewer: Tree settled on 'The Firebug' after 2 frames.",
        "OKFViewer: Page action 'Read comic'.",
    ]
