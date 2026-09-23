"""The main window's settled geometry is logged as WINDOW_GEOMETRY."""

from __future__ import annotations

import re
from unittest.mock import patch

from barks_reader.core import log_markers
from barks_reader.ui import platform_window_utils
from barks_reader.ui.platform_window_utils import log_window_geometry


def test_the_line_carries_the_reason_size_and_position(loguru_sink: list[str]) -> None:
    """Any run's log shows a window that shrank or moved, not only a GUI-harness run."""
    with patch.object(platform_window_utils, "Window") as window:
        window.size = (782, 1225)
        window.left, window.top = 40, 60

        log_window_geometry("MainScreen windowed")

    assert "Main window geometry (MainScreen windowed): 782x1225+40+60." in loguru_sink


def test_the_line_matches_its_pattern(loguru_sink: list[str]) -> None:
    """The GUI harness reads the line back through the marker's own pattern."""
    with patch.object(platform_window_utils, "Window") as window:
        window.size = (800, 600)
        window.left, window.top = 0, 0

        log_window_geometry("boot")

    assert re.search(log_markers.pattern(log_markers.WINDOW_GEOMETRY), "\n".join(loguru_sink))
