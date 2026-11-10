"""The Win32 window backend with its Win32 calls stood in for, on every platform.

``test_platform_window_win32_live.py`` runs the real calls, on Windows only. These
tests are for what the backend does around them, which no platform otherwise ran.
"""

# ruff: noqa: SLF001

from __future__ import annotations

from unittest.mock import MagicMock, patch

from barks_reader.ui import platform_window_win32 as win32_module
from barks_reader.ui.platform_window_utils import WindowState
from barks_reader.ui.platform_window_win32 import Win32WindowBackend

_HWND = 0x1234


def _backend(move_window: MagicMock, get_window_rect: MagicMock) -> Win32WindowBackend:
    """Return a backend bound to no real window, its Win32 calls the ones given."""
    with patch.object(win32_module, "find_app_hwnd", return_value=None):
        backend = Win32WindowBackend()
    backend._hwnd = _HWND
    backend._move_window = move_window
    backend._get_window_rect = get_window_rect
    return backend


def _saved_state() -> WindowState:
    state = WindowState()
    state.pos = (150, 120)
    state.size = (700, 500)
    return state


def test_a_move_now_that_raises_is_logged_and_goes_no_further(loguru_sink: list[str]) -> None:
    """Raised into the fullscreen exit, it left the restore unscheduled and its count up."""
    move_window = MagicMock(side_effect=OSError("access violation"))
    backend = _backend(move_window, MagicMock())

    with (
        patch.object(win32_module, "Window", MagicMock(fullscreen=False)),
        patch.object(win32_module, "Clock") as clock,
    ):
        backend.move_now(_saved_state())

    move_window.assert_called_once_with(_HWND, 150, 120, 700, 500, True)  # noqa: FBT003
    clock.schedule_once.assert_not_called()
    assert any("access violation" in line for line in loguru_sink)


def test_a_move_now_with_no_window_handle_calls_nothing() -> None:
    move_window = MagicMock()
    backend = _backend(move_window, MagicMock())
    backend._hwnd = None

    backend.move_now(_saved_state())

    move_window.assert_not_called()
