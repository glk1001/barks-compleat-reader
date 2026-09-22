"""The main window is shown after its sizing is done, and the log says so (MAIN_WINDOW_SHOWN)."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

from barks_reader.core import log_markers
from barks_reader.ui import barks_reader_app
from barks_reader.ui.barks_reader_app import _show_main_window


def test_the_window_is_shown_after_its_geometry_is_ready_and_then_logged(
    loguru_sink: list[str],
) -> None:
    """The GUI probe boots on this line: a key sent before the window shows is lost."""
    parent = MagicMock()
    window, geometry = parent.window, parent.geometry
    with patch.object(barks_reader_app, "_log_screen_settings") as log_settings:
        _show_main_window(window, geometry)
    assert parent.mock_calls[:2] == [call.geometry.set_window_ready(), call.window.show()]
    assert log_markers.MAIN_WINDOW_SHOWN in loguru_sink
    log_settings.assert_called_once()
