"""The Win32 window backend with its Win32 calls stood in for, on every platform.

``test_platform_window_win32_live.py`` runs the real calls, on Windows only. These
tests are for what the backend does around them, which no platform otherwise ran.
"""

# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from barks_reader.ui import platform_window_win32 as win32_module
from barks_reader.ui.platform_window_utils import WindowState
from barks_reader.ui.platform_window_win32 import Win32WindowBackend

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_reader.core.win32_window import RECT

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


def _window_at(left: int, top: int, width: int, height: int) -> MagicMock:
    """Return a GetWindowRect stand-in that reports the window at the rectangle given."""

    def fill(_hwnd: int, rect: RECT) -> bool:
        rect.left, rect.top, rect.right, rect.bottom = left, top, left + width, top + height
        return True

    return MagicMock(side_effect=fill)


def test_a_move_now_that_holds_tries_no_more() -> None:
    move_window = MagicMock(return_value=True)
    backend = _backend(move_window, _window_at(150, 120, 700, 500))

    with (
        patch.object(win32_module, "Window", MagicMock(fullscreen=False)),
        patch.object(win32_module, "Clock") as clock,
    ):
        backend.move_now(_saved_state())

    move_window.assert_called_once_with(_HWND, 150, 120, 700, 500, True)  # noqa: FBT003
    clock.schedule_once.assert_not_called()


def test_a_move_now_left_where_it_was_tries_again_next_frame() -> None:
    backend = _backend(MagicMock(return_value=True), _window_at(60, 40, 716, 539))

    with (
        patch.object(win32_module, "Window", MagicMock(fullscreen=False)),
        patch.object(win32_module, "Clock") as clock,
    ):
        backend.move_now(_saved_state())

    clock.schedule_once.assert_called_once()


def test_a_restore_left_at_the_wrong_size_recovers_through_kivy_and_moves_again(
    loguru_sink: list[str],
) -> None:
    move_window = MagicMock(return_value=True)
    backend = _backend(move_window, _window_at(150, 120, 136, 45))
    window = MagicMock(fullscreen=False)

    with (
        patch.object(win32_module, "Window", window),
        patch.object(win32_module, "Clock") as clock,
    ):
        backend._set_window_rect(150, 120, 700, 500)
        assert (window.size, window.left, window.top) == ((700, 500), 150, 120)
        retry = clock.schedule_once.call_args.args[0]
        retry(0)

    assert move_window.call_count == 2  # noqa: PLR2004
    assert any("MoveWindow no-op detected" in line for line in loguru_sink)
    assert any(line.startswith("Win32 retry:") for line in loguru_sink)


def test_a_restore_at_the_size_asked_for_needs_no_recovery() -> None:
    move_window = MagicMock(return_value=True)
    backend = _backend(move_window, _window_at(150, 120, 700, 500))

    with patch.object(win32_module, "Clock") as clock:
        backend._set_window_rect(150, 120, 700, 500)

    move_window.assert_called_once()
    clock.schedule_once.assert_not_called()


# --- Binding to the window ---


def test_a_window_that_cannot_be_found_leaves_the_backend_unavailable(
    loguru_sink: list[str],
) -> None:
    with patch.object(win32_module, "find_app_hwnd", return_value=None):
        backend = Win32WindowBackend()

    assert backend.is_available() is False
    assert any("Could not get Win32 handle" in line for line in loguru_sink)


def test_a_lookup_that_raises_leaves_the_backend_unavailable(loguru_sink: list[str]) -> None:
    with patch.object(win32_module, "find_app_hwnd", side_effect=OSError("no user32")):
        backend = Win32WindowBackend()

    assert backend.is_available() is False
    assert any("Could not initialize Win32 handles: no user32" in line for line in loguru_sink)


def test_a_window_handle_given_is_the_one_bound_and_the_lookup_is_not_run() -> None:
    with (
        patch.object(win32_module, "find_app_hwnd") as find,
        patch.object(win32_module, "Win32Window") as window_class,
    ):
        backend = Win32WindowBackend(_HWND)

    find.assert_not_called()
    window_class.assert_called_once_with(_HWND)
    window = window_class.return_value
    assert backend.is_available() is True
    assert backend._move_window is window.move_window
    assert backend._get_window_rect is window.get_window_rect
    assert backend._get_client_rect is window.get_client_rect


# --- Saving the window's rectangle ---


def test_the_saved_state_is_the_windows_own_rectangle() -> None:
    backend = _backend(MagicMock(), _window_at(150, 120, 700, 500))
    backend._get_client_rect = _window_at(0, 0, 700, 500)
    state = WindowState()

    backend.save_state(state)

    assert (state.pos, state.size) == ((150, 120), (700, 500))


def test_a_save_that_raises_takes_the_state_from_kivy(loguru_sink: list[str]) -> None:
    backend = _backend(MagicMock(), MagicMock(side_effect=OSError("bad handle")))
    state = MagicMock(spec=WindowState)

    backend.save_state(state)

    state.save_state_now.assert_called_once_with()
    assert any("Win32 save state failed" in line for line in loguru_sink)


# --- The scheduled restore ---


def _schedule_restore(
    backend: Win32WindowBackend, clock: MagicMock
) -> tuple[MagicMock, MagicMock, Callable[[], None]]:
    """Schedule a restore to the saved state; return its two callbacks and its cancel."""
    on_first_resize, on_done = MagicMock(), MagicMock()
    cancel = backend.schedule_restore(_saved_state(), on_first_resize, on_done)
    clock.schedule_once.assert_called_once()
    assert clock.schedule_once.call_args.args[1] == win32_module._RESTORE_GEOMETRY_TIMEOUT_WIN
    return on_first_resize, on_done, cancel


def test_a_scheduled_restore_moves_the_window_then_calls_back_a_frame_later() -> None:
    move_window = MagicMock(return_value=True)
    backend = _backend(move_window, _window_at(150, 120, 700, 500))

    with patch.object(win32_module, "Clock") as clock, patch.object(win32_module, "Window"):
        on_first_resize, on_done, _ = _schedule_restore(backend, clock)
        restore = clock.schedule_once.call_args.args[0]

        move_window.assert_not_called()  # nothing before the delay is up
        restore(0)

        move_window.assert_called_once_with(_HWND, 150, 120, 700, 500, True)  # noqa: FBT003
        on_first_resize.assert_not_called()  # Kivy has a frame to catch up first
        sync_and_finish, delay = clock.schedule_once.call_args.args
        assert delay == 0
        sync_and_finish(0)

    on_first_resize.assert_called_once_with()
    on_done.assert_called_once_with()


def test_cancelling_before_the_delay_is_up_stops_the_delayed_move() -> None:
    backend = _backend(MagicMock(), MagicMock())

    with patch.object(win32_module, "Clock") as clock:
        delayed_move = clock.schedule_once.return_value
        _, _, cancel = _schedule_restore(backend, clock)
        cancel()

    delayed_move.cancel.assert_called_once_with()


def test_cancelling_after_the_move_stops_the_callbacks_still_to_come() -> None:
    backend = _backend(MagicMock(return_value=True), _window_at(150, 120, 700, 500))
    delayed_move, callbacks_step = MagicMock(), MagicMock()

    with patch.object(win32_module, "Clock") as clock:
        clock.schedule_once.side_effect = [delayed_move, callbacks_step]
        _, _, cancel = _schedule_restore(backend, clock)
        clock.schedule_once.call_args.args[0](0)
        cancel()

    callbacks_step.cancel.assert_called_once_with()
    delayed_move.cancel.assert_not_called()
