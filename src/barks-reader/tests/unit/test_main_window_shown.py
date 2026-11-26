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
    geometry.when_settled.side_effect = lambda callback: callback()  # nothing pending
    with (
        patch.object(barks_reader_app, "_log_screen_settings") as log_settings,
        patch.object(barks_reader_app, "log_window_geometry") as log_geometry,
    ):
        _show_main_window(window, geometry)
    assert parent.mock_calls[:2] == [call.geometry.set_window_ready(), call.window.show()]
    assert log_markers.MAIN_WINDOW_SHOWN in loguru_sink
    log_geometry.assert_called_once_with("boot")
    log_settings.assert_called_once()


def test_the_boot_size_waits_for_the_window_to_settle(loguru_sink: list[str]) -> None:
    """A window still to be corrected to its shape is logged at the size it settles at."""
    parent = MagicMock()
    with (
        patch.object(barks_reader_app, "_log_screen_settings") as log_settings,
        patch.object(barks_reader_app, "log_window_geometry") as log_geometry,
    ):
        _show_main_window(parent.window, parent.geometry)
        assert log_markers.MAIN_WINDOW_SHOWN in loguru_sink  # the probe's boot is not held up
        log_geometry.assert_not_called()

        (settled,) = parent.geometry.when_settled.call_args.args
        settled()
    log_geometry.assert_called_once_with("boot")
    log_settings.assert_called_once()


def test_the_boot_splash_comes_down_once_the_window_is_up() -> None:
    parent = MagicMock()
    with (
        patch.object(barks_reader_app, "_log_screen_settings"),
        patch.object(barks_reader_app, "log_window_geometry"),
        patch.object(barks_reader_app, "close_boot_splash", parent.close_boot_splash),
    ):
        _show_main_window(parent.window, parent.geometry)
    assert parent.mock_calls[1:3] == [call.window.show(), call.close_boot_splash()]
