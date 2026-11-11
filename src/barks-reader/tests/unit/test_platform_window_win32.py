"""The Win32 window backend with its Win32 calls stood in for, on every platform.

``test_platform_window_win32_live.py`` runs the real calls, on Windows only. These
tests are for what the backend does around them, which no platform otherwise ran.
"""

# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING, Self
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
    at = [(60, 40, 716, 539)]

    def fill(_hwnd: int, rect: RECT) -> bool:
        left, top, width, height = at[0]
        rect.left, rect.top, rect.right, rect.bottom = left, top, left + width, top + height
        return True

    def move(_hwnd: int, *args: int) -> bool:
        left, top, width, height, _repaint = args
        at[0] = (left, top, width, height)
        return True

    move_window = MagicMock(side_effect=move)
    backend = _backend(move_window, MagicMock(side_effect=fill))

    with (
        patch.object(win32_module, "Window", MagicMock(fullscreen=False)),
        patch.object(win32_module, "Clock") as clock,
    ):
        backend.move_now(_saved_state())

    move_window.assert_called_once_with(_HWND, 150, 120, 700, 500, True)  # noqa: FBT003
    clock.schedule_once.assert_not_called()


def test_a_window_held_at_the_rectangle_through_the_exit_is_not_moved() -> None:
    """A move then would only block while the window finishes the exit."""
    move_window = MagicMock(return_value=True)
    backend = _backend(move_window, _window_at(150, 120, 700, 500))

    with (
        patch.object(win32_module, "Window", MagicMock(fullscreen=False)),
        patch.object(win32_module, "Clock") as clock,
    ):
        backend.move_now(_saved_state())

    move_window.assert_not_called()
    clock.schedule_once.assert_not_called()


def test_a_window_elsewhere_as_fullscreen_ends_is_logged_before_it_is_moved(
    loguru_sink: list[str],
) -> None:
    """The line splits the wait in a log: before it the exit, after it the move."""
    backend = _backend(MagicMock(return_value=True), _window_at(60, 40, 716, 539))

    with (
        patch.object(win32_module, "Window", MagicMock(fullscreen=False)),
        patch.object(win32_module, "Clock"),
    ):
        backend.move_now(_saved_state())

    wanted = "Window rect (60, 40, 776, 579) as fullscreen ends, not (150, 120, 850, 620)"
    assert any(wanted in s for s in loguru_sink)


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


# --- Holding the saved rectangle through the exit ---


def test_the_saved_rectangle_is_held_on_the_backends_window() -> None:
    backend = _backend(MagicMock(), MagicMock())

    with patch.object(win32_module, "hold_window_rect", return_value=True) as hold:
        backend.hold_windowed_rect(_saved_state())

    hold.assert_called_once_with(_HWND, (150, 120, 700, 500))


def test_letting_go_is_asked_of_the_backends_window() -> None:
    backend = _backend(MagicMock(), MagicMock())

    with patch.object(win32_module, "release_window_rect") as release:
        backend.release_windowed_rect()

    release.assert_called_once_with(_HWND)


def test_with_no_window_handle_nothing_is_held_or_let_go() -> None:
    backend = _backend(MagicMock(), MagicMock())
    backend._hwnd = None

    with (
        patch.object(win32_module, "hold_window_rect") as hold,
        patch.object(win32_module, "release_window_rect") as release,
    ):
        backend.hold_windowed_rect(_saved_state())
        backend.release_windowed_rect()

    hold.assert_not_called()
    release.assert_not_called()


# --- The scheduled restore ---

_SAVED = (150, 120, 700, 500)  # where `_saved_state` puts the window: left, top, width, height
_ELSEWHERE = (60, 40, 716, 539)


class _Clock:
    """Stand in for Kivy's Clock: hold what is scheduled until a test runs it."""

    def __init__(self) -> None:
        self.scheduled: list[tuple[Callable[[float], None], float, MagicMock]] = []

    def schedule_once(self, callback: Callable[[float], None], delay: float = 0) -> MagicMock:
        event = MagicMock()
        self.scheduled.append((callback, delay, event))
        return event

    def run(self, delay: float) -> None:
        """Run the oldest callback scheduled with `delay` that has not been cancelled."""
        for entry in self.scheduled:
            callback, its_delay, event = entry
            if its_delay == delay and not event.cancel.called:
                self.scheduled.remove(entry)
                callback(0)
                return
        msg = f"Nothing is scheduled with a delay of {delay}."
        raise AssertionError(msg)

    def run_frame(self) -> None:
        self.run(0)

    def run_delayed_move(self) -> None:
        self.run(win32_module._RESTORE_GEOMETRY_TIMEOUT_WIN)

    def live(self) -> list[float]:
        return [delay for _, delay, event in self.scheduled if not event.cancel.called]


class _Restore:
    """A scheduled restore to the saved state, on a window a test can move."""

    def __init__(self, window_at: tuple[int, int, int, int], *, fullscreen: bool = False) -> None:
        self.window_at = window_at
        self.move_window = MagicMock(side_effect=self._move)
        self.on_first_resize, self.on_done = MagicMock(), MagicMock()
        self.clock = _Clock()
        self.window = MagicMock(fullscreen=fullscreen)

        def fill(_hwnd: int, rect: RECT) -> bool:
            left, top, width, height = self.window_at
            rect.left, rect.top, rect.right, rect.bottom = left, top, left + width, top + height
            return True

        self.backend = _backend(self.move_window, MagicMock(side_effect=fill))
        self.release = MagicMock()
        self._patches = [
            patch.object(win32_module, "release_window_rect", self.release),
            patch.object(win32_module, "Clock", self.clock),
            patch.object(win32_module, "Window", self.window),
        ]

    def _move(self, _hwnd: int, *rect_and_repaint: int) -> bool:
        self.window_at = (*rect_and_repaint[:4],)
        return True

    def __enter__(self) -> Self:
        for patcher in self._patches:
            patcher.start()
        self.cancel = self.backend.schedule_restore(
            _saved_state(), self.on_first_resize, self.on_done
        )
        return self

    def __exit__(self, *_exc: object) -> None:
        for patcher in self._patches:
            patcher.stop()

    def assert_called_back_once(self) -> None:
        self.on_first_resize.assert_called_once_with()
        self.on_done.assert_called_once_with()

    def assert_not_called_back(self) -> None:
        self.on_first_resize.assert_not_called()
        self.on_done.assert_not_called()


def test_a_window_still_elsewhere_is_moved_when_the_delay_is_up_then_called_back() -> None:
    with _Restore(_ELSEWHERE) as restore:
        restore.clock.run_frame()  # a look: not there yet
        restore.clock.run_frame()  # and another
        restore.move_window.assert_not_called()  # nothing before the delay is up
        restore.assert_not_called_back()

        restore.clock.run_delayed_move()

        restore.move_window.assert_called_once_with(_HWND, *_SAVED, True)  # noqa: FBT003
        restore.assert_not_called_back()  # Kivy has a frame to catch up first
        restore.clock.run_frame()

        restore.assert_called_back_once()
        assert restore.clock.live() == []  # the looking stopped with the move


def test_a_window_already_put_right_is_called_back_without_waiting(
    loguru_sink: list[str],
) -> None:
    """Until then the screen is laid out for fullscreen in a window that is not."""
    with _Restore(_SAVED) as restore:
        restore.assert_called_back_once()  # at once: not even a frame later
        restore.move_window.assert_not_called()
        assert any("finishing the restore without waiting" in s for s in loguru_sink)
        assert restore.clock.live() == [win32_module._RESTORE_GEOMETRY_TIMEOUT_WIN]

        restore.release.assert_not_called()  # the exit may still ask for the wrong place
        restore.clock.run_delayed_move()  # now only a check: the window is still right

        restore.release.assert_called_once_with(_HWND)
        restore.move_window.assert_not_called()
        restore.assert_called_back_once()
        assert restore.clock.live() == []


def test_a_resize_that_leaves_the_window_right_is_called_back_there(
    loguru_sink: list[str],
) -> None:
    """Before the screens lay out for the resize, not a slow frame after it."""
    with _Restore(_ELSEWHERE) as restore:
        on_resize = restore.window.bind.call_args.kwargs["on_resize"]
        restore.window_at = _SAVED

        on_resize(restore.window, 700, 500)

        restore.assert_called_back_once()
        assert any("finishing the restore at the resize" in s for s in loguru_sink)
        restore.window.unbind.assert_called_with(on_resize=on_resize)
        # The frame-by-frame look has stopped; only the delayed move's check is left.
        assert restore.clock.live() == [win32_module._RESTORE_GEOMETRY_TIMEOUT_WIN]


def test_a_resize_that_leaves_the_window_elsewhere_is_not_called_back() -> None:
    with _Restore(_ELSEWHERE) as restore:
        on_resize = restore.window.bind.call_args.kwargs["on_resize"]

        on_resize(restore.window, 716, 539)

        restore.assert_not_called_back()


def test_a_resize_after_the_delayed_move_or_a_cancel_calls_nothing() -> None:
    with _Restore(_ELSEWHERE) as restore:
        on_resize = restore.window.bind.call_args.kwargs["on_resize"]
        restore.cancel()
        restore.window.unbind.assert_called_with(on_resize=on_resize)
        restore.window_at = _SAVED

        on_resize(restore.window, 700, 500)  # were it still bound

        restore.assert_not_called_back()


def test_a_clock_that_runs_everything_at_once_still_moves_and_calls_back_once() -> None:
    """As the tests against a real window have it: the delayed move runs before any look."""
    move_window = MagicMock(return_value=True)
    backend = _backend(move_window, _window_at(*_SAVED))
    on_first_resize, on_done = MagicMock(), MagicMock()

    def run_now(callback: Callable[[float], None], _delay: float = 0) -> MagicMock:
        callback(0)
        return MagicMock()

    with (
        patch.object(win32_module, "Window", MagicMock(fullscreen=False)),
        patch.object(win32_module.Clock, "schedule_once", side_effect=run_now),
    ):
        backend.schedule_restore(_saved_state(), on_first_resize, on_done)

    move_window.assert_called_once_with(_HWND, *_SAVED, True)  # noqa: FBT003
    on_first_resize.assert_called_once_with()
    on_done.assert_called_once_with()


def test_a_window_put_right_a_frame_later_is_called_back_then() -> None:
    with _Restore(_ELSEWHERE) as restore:
        restore.clock.run_frame()
        restore.assert_not_called_back()

        restore.window_at = _SAVED
        restore.clock.run_frame()

        restore.assert_called_back_once()


def test_a_window_the_exit_shifts_after_an_early_finish_is_moved_back(
    loguru_sink: list[str],
) -> None:
    with _Restore(_SAVED) as restore:
        restore.window_at = _ELSEWHERE

        restore.clock.run_delayed_move()

        restore.move_window.assert_called_once_with(_HWND, *_SAVED, True)  # noqa: FBT003
        restore.assert_called_back_once()  # not a second time
        assert any("moved after its early restore" in s for s in loguru_sink)


def test_a_window_gone_fullscreen_after_an_early_finish_is_left_alone() -> None:
    """The early finish gave up its cancel, so the delayed move sees to this itself."""
    with _Restore(_SAVED) as restore:
        restore.window.fullscreen = True
        restore.window_at = (0, 0, 2560, 1440)

        restore.clock.run_delayed_move()

        restore.move_window.assert_not_called()


def test_a_window_whose_rectangle_cannot_be_read_waits_for_the_delayed_move(
    loguru_sink: list[str],
) -> None:
    with _Restore(_ELSEWHERE) as restore:
        restore.backend._get_window_rect = MagicMock(side_effect=OSError("no window"))

        restore.clock.run_frame()

        restore.assert_not_called_back()
        assert 0 in restore.clock.live()  # still looking
        assert any("Win32 GetWindowRect failed" in s for s in loguru_sink)


def test_cancelling_before_the_delay_is_up_stops_the_looking_and_the_delayed_move() -> None:
    with _Restore(_ELSEWHERE) as restore:
        restore.clock.run_frame()

        restore.cancel()

        assert restore.clock.live() == []


def test_cancelling_after_the_move_stops_the_callbacks_still_to_come() -> None:
    with _Restore(_ELSEWHERE) as restore:
        restore.clock.run_delayed_move()

        restore.cancel()

        assert restore.clock.live() == []
        restore.assert_not_called_back()
