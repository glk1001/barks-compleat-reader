"""The Win32 window backend with its Win32 calls stood in for, on every platform.

``test_platform_window_win32_live.py`` runs the real calls, on Windows only. These
tests are for what the backend does around them, which no platform otherwise ran.
"""

# ruff: noqa: SLF001

from __future__ import annotations

from contextlib import ExitStack
from typing import TYPE_CHECKING, Self
from unittest.mock import MagicMock, patch

from barks_reader.core.window_state import WindowState
from barks_reader.ui import platform_window_win32 as win32_module
from barks_reader.ui.platform_window_win32 import Win32WindowBackend
from unit_helpers import run_last_scheduled

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

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


def _rect_filler(rectangles: Iterator[tuple[int, int, int, int]]) -> Callable[[int, RECT], bool]:
    """Return a GetWindowRect stand-in reporting each rectangle (left, top, size) in turn."""

    def fill(_hwnd: int, rect: RECT) -> bool:
        left, top, width, height = next(rectangles)
        rect.left, rect.top, rect.right, rect.bottom = left, top, left + width, top + height
        return True

    return fill


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


class _MoveNow:
    """A `move_now` on a window that takes the move only from a given attempt on."""

    def __init__(self, *, lands_on_attempt: int | None) -> None:
        self.window_at: tuple[int, ...] = _ELSEWHERE
        self.attempts = 0
        self.lands_on_attempt = lands_on_attempt
        self.clock = _Clock()
        self.window = MagicMock(fullscreen=False)

        def move(_hwnd: int, *rect_and_repaint: int) -> bool:
            self.attempts += 1
            if self.lands_on_attempt is not None and self.attempts >= self.lands_on_attempt:
                self.window_at = (*rect_and_repaint[:4],)
            return True

        def fill(_hwnd: int, rect: RECT) -> bool:
            left, top, width, height = self.window_at
            rect.left, rect.top, rect.right, rect.bottom = left, top, left + width, top + height
            return True

        self.backend = _backend(MagicMock(side_effect=move), MagicMock(side_effect=fill))

    def run(self) -> None:
        """Call `move_now`, then run each frame's attempt until none is scheduled."""
        with (
            patch.object(win32_module, "Window", self.window),
            patch.object(win32_module, "Clock", self.clock),
        ):
            self.backend.move_now(_saved_state())
            while self.clock.live():
                self.clock.run_frame()


def test_a_window_that_never_takes_the_move_is_tried_a_few_frames_and_left() -> None:
    """Not every frame for good: the scheduled restore settles what this could not."""
    move_now = _MoveNow(lands_on_attempt=None)

    move_now.run()

    assert move_now.attempts == win32_module._MOVE_NOW_ATTEMPTS


def test_a_move_that_holds_on_a_later_frame_stops_there_and_tells_the_restore() -> None:
    """The first move straight after the exit is lost; the next frame's holds."""
    move_now = _MoveNow(lands_on_attempt=2)
    restore = MagicMock()
    move_now.backend._restore = restore

    move_now.run()

    assert move_now.attempts == 2  # noqa: PLR2004
    assert move_now.window_at == _SAVED
    restore.look_now.assert_called_once_with()


def test_a_window_gone_fullscreen_again_is_not_moved_on_the_next_frame() -> None:
    move_now = _MoveNow(lands_on_attempt=None)
    with (
        patch.object(win32_module, "Window", move_now.window),
        patch.object(win32_module, "Clock", move_now.clock),
    ):
        move_now.backend.move_now(_saved_state())
        move_now.window.fullscreen = "auto"
        move_now.clock.run_frame()

    assert move_now.attempts == 1
    assert move_now.clock.live() == []


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


def test_a_second_move_that_fails_is_logged_and_goes_no_further(loguru_sink: list[str]) -> None:
    """The one Win32 call made from a Clock callback: an error there would stop the app."""
    move_window = MagicMock(side_effect=[True, OSError("the window has gone")])
    backend = _backend(move_window, _window_at(150, 120, 136, 45))

    with (
        patch.object(win32_module, "Window", MagicMock(fullscreen=False)),
        patch.object(win32_module, "Clock") as clock,
    ):
        backend._set_window_rect(150, 120, 700, 500)
        retry = clock.schedule_once.call_args.args[0]
        retry(0)

    assert "Win32 MoveWindow retry failed: the window has gone" in loguru_sink
    assert not any(line.startswith("Win32 retry:") for line in loguru_sink)


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


# --- Setting the window's size exactly ---


def test_under_the_custom_titlebar_the_window_is_sized_as_its_drawable_area() -> None:
    """The client area fills the window: a size plus the style's frame came back too big."""
    move_window = MagicMock()
    rectangles = iter([(150, 120, 1058, 1130), (150, 120, 719, 1130)])
    backend = _backend(move_window, MagicMock(side_effect=_rect_filler(rectangles)))
    backend._get_client_rect = _window_at(0, 0, 1058, 1130)

    with patch.object(win32_module, "Window", MagicMock()) as window:
        backend.set_size(719, 1130)

    move_window.assert_called_once_with(_HWND, 150, 120, 719, 1130, True)  # noqa: FBT003
    assert window.size != (719, 1130)  # not through Kivy as well


def test_a_window_with_the_desktops_frame_is_sized_to_hold_the_drawable_area() -> None:
    move_window = MagicMock()
    rectangles = iter([(150, 120, 716, 539), (150, 120, 816, 639)])
    backend = _backend(move_window, MagicMock(side_effect=_rect_filler(rectangles)))
    backend._get_client_rect = _window_at(0, 0, 700, 500)  # a frame of 16x39

    with patch.object(win32_module, "Window", MagicMock()):
        backend.set_size(800, 600)

    move_window.assert_called_once_with(_HWND, 150, 120, 816, 639, True)  # noqa: FBT003


def test_a_size_the_window_did_not_take_is_set_through_kivy(loguru_sink: list[str]) -> None:
    backend = _backend(MagicMock(), _window_at(150, 120, 1058, 1130))  # left as it was
    backend._get_client_rect = _window_at(0, 0, 1058, 1130)

    with patch.object(win32_module, "Window", MagicMock()) as window:
        backend.set_size(719, 1130)

    assert window.size == (719, 1130)
    assert any("not the (719, 1130) asked for" in line for line in loguru_sink)


def test_a_sizing_that_raises_is_logged_and_set_through_kivy(loguru_sink: list[str]) -> None:
    """Raised from a Clock callback, it would stop the app."""
    backend = _backend(MagicMock(), MagicMock(side_effect=OSError("access violation")))

    with patch.object(win32_module, "Window", MagicMock()) as window:
        backend.set_size(719, 1130)

    assert window.size == (719, 1130)
    assert any("access violation" in line for line in loguru_sink)


def test_with_no_window_handle_the_size_is_set_through_kivy() -> None:
    move_window = MagicMock()
    backend = _backend(move_window, MagicMock())
    backend._hwnd = None

    with patch.object(win32_module, "Window", MagicMock()) as window:
        backend.set_size(719, 1130)

    assert window.size == (719, 1130)
    move_window.assert_not_called()


# --- The minimum, held by the caption guard ---


def test_the_minimum_is_held_by_the_windows_guard_and_a_raise_is_sized_again() -> None:
    backend = _backend(MagicMock(), MagicMock())

    with patch.object(win32_module, "set_window_client_minimum", return_value=True) as hold:
        assert backend.set_minimum_size(633, 1000) is True

    hold.assert_called_once_with(_HWND, 633, 1000)


def test_with_no_guard_the_minimum_of_sdl_stands_and_a_raise_is_not_sized_again() -> None:
    """Windows would hold the window to SDL's minimum, and refuse the exact size."""
    backend = _backend(MagicMock(), MagicMock())

    with patch.object(win32_module, "set_window_client_minimum", return_value=False):
        assert backend.set_minimum_size(633, 1000) is False


def test_with_no_window_handle_no_minimum_is_held() -> None:
    backend = _backend(MagicMock(), MagicMock())
    backend._hwnd = None

    with patch.object(win32_module, "set_window_client_minimum") as hold:
        assert backend.set_minimum_size(633, 1000) is False

    hold.assert_not_called()


# --- Moving the window, its size kept ---


def test_a_move_keeps_the_windows_size() -> None:
    """Moved through Kivy, the window grew by its frame on each (2026-11-27)."""
    move_window = MagicMock()
    rectangles = iter([(644, 100, 633, 1000), (644, 40, 633, 1000)])
    backend = _backend(move_window, MagicMock(side_effect=_rect_filler(rectangles)))

    with patch.object(win32_module, "Window", MagicMock(left=644, top=100)) as window:
        backend.move_to(644, 40)

    move_window.assert_called_once_with(_HWND, 644, 40, 633, 1000, True)  # noqa: FBT003
    assert (window.left, window.top) == (644, 100)  # not through Kivy as well


def test_a_move_the_window_did_not_take_is_made_through_kivy(loguru_sink: list[str]) -> None:
    backend = _backend(MagicMock(), _window_at(644, 100, 633, 1000))  # left where it was

    with patch.object(win32_module, "Window", MagicMock()) as window:
        backend.move_to(644, 40)

    assert (window.left, window.top) == (644, 40)
    assert any("not the (644, 40, 1277, 1040) asked for" in line for line in loguru_sink)


def test_a_move_that_changed_the_windows_size_is_made_through_kivy(
    loguru_sink: list[str],
) -> None:
    """Where it was asked to be, but the frame bigger: not the move that was asked for."""
    rectangles = iter([(644, 100, 633, 1000), (644, 40, 649, 1039)])
    backend = _backend(MagicMock(), MagicMock(side_effect=_rect_filler(rectangles)))

    with patch.object(win32_module, "Window", MagicMock()) as window:
        backend.move_to(644, 40)

    assert (window.left, window.top) == (644, 40)
    assert any("was put at (644, 40, 1293, 1079)" in line for line in loguru_sink)


def test_a_move_that_raises_is_logged_and_made_through_kivy(loguru_sink: list[str]) -> None:
    move_window = MagicMock(side_effect=OSError("access violation"))
    backend = _backend(move_window, _window_at(644, 100, 633, 1000))

    with patch.object(win32_module, "Window", MagicMock()) as window:
        backend.move_to(644, 40)

    assert (window.left, window.top) == (644, 40)
    assert any("access violation" in line for line in loguru_sink)


def test_a_window_whose_rectangle_cannot_be_read_is_moved_through_kivy() -> None:
    move_window = MagicMock()
    backend = _backend(move_window, MagicMock())
    backend._hwnd = None

    with patch.object(win32_module, "Window", MagicMock()) as window:
        backend.move_to(644, 40)

    assert (window.left, window.top) == (644, 40)
    move_window.assert_not_called()


# --- Saving the window's rectangle ---


def test_the_saved_state_is_the_windows_own_rectangle() -> None:
    backend = _backend(MagicMock(), _window_at(150, 120, 700, 500))
    backend._get_client_rect = _window_at(0, 0, 700, 500)
    state = WindowState()

    backend.save_state(state)

    assert (state.pos, state.size) == ((150, 120), (700, 500))


def test_a_save_that_raises_takes_the_state_from_kivy(loguru_sink: list[str]) -> None:
    backend = _backend(MagicMock(), MagicMock(side_effect=OSError("bad handle")))
    state = WindowState()
    kivy_window = MagicMock(system_size=[800, 600], left=10, top=20)

    with patch.object(win32_module, "Window", kivy_window):
        backend.save_state(state)

    assert (state.size, state.pos) == ((800, 600), (10, 20))
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


def test_going_fullscreen_quiets_the_windows_frame_then_ends_the_quiet() -> None:
    backend = _backend(MagicMock(), MagicMock())
    seconds = win32_module._FULLSCREEN_ENTRY_QUIET_SECONDS

    with (
        patch.object(win32_module, "quiet_window_frame", return_value=7) as quiet,
        patch.object(win32_module, "end_window_frame_quiet") as end_quiet,
        patch.object(win32_module, "Clock") as clock,
    ):
        backend.quiet_frame_for_fullscreen()

        quiet.assert_called_once_with(_HWND, seconds)
        end_quiet.assert_not_called()
        (callback, delay), _ = clock.schedule_once.call_args
        assert delay == seconds
        callback(0)
        end_quiet.assert_called_once_with(_HWND, 7)  # this quiet, not one begun since


def test_a_window_with_no_guard_or_no_handle_schedules_no_end_of_quiet() -> None:
    backend = _backend(MagicMock(), MagicMock())

    with (
        patch.object(win32_module, "quiet_window_frame", return_value=0) as quiet,
        patch.object(win32_module, "Clock") as clock,
    ):
        backend.quiet_frame_for_fullscreen()
        backend._hwnd = None
        backend.quiet_frame_for_fullscreen()

    quiet.assert_called_once()
    clock.schedule_once.assert_not_called()


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
        with ExitStack() as patches:
            for patcher in self._patches:
                patches.enter_context(patcher)
            self.cancel = self.backend.schedule_restore(
                _saved_state(), self.on_first_resize, self.on_done
            )
            # Kept only now: a schedule_restore that raises has undone its patches.
            self._undo = patches.pop_all()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._undo.close()

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


def test_a_restore_finished_a_second_time_calls_back_only_once() -> None:
    """Nothing asks twice today; the guard is what keeps a later caller from laying out twice."""
    with _Restore(_SAVED) as restore:
        restore.assert_called_back_once()

        scheduled = restore.backend._restore
        assert scheduled is not None
        scheduled._finish()

        restore.assert_called_back_once()


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


def test_a_restore_that_finished_early_leaves_a_window_gone_fullscreen_since_alone() -> None:
    """Out of fullscreen and straight back in, before the first exit's delayed move.

    The move let go of the window all the same, which ended the quiet the new entry
    had just begun, and the caption could flash.
    """
    with _Restore(_SAVED) as restore:
        restore.assert_called_back_once()
        restore.window.fullscreen = "auto"
        restore.window_at = (0, 0, 2560, 1440)

        restore.clock.run_delayed_move()

        restore.release.assert_not_called()
        restore.move_window.assert_not_called()


def test_a_delayed_move_run_as_it_is_scheduled_still_lets_go_of_the_window() -> None:
    """A clock that runs a callback at once: the restore is the backend's newest by then.

    The live Windows tests run the clock so, and the move, asking whether its restore
    was still the newest before the backend had been given it, held on to the window.
    """
    release = MagicMock()
    backend = _backend(MagicMock(return_value=True), _window_at(*_SAVED))
    clock = MagicMock()
    clock.schedule_once.side_effect = lambda callback, _delay=0: callback(0)

    with (
        patch.object(win32_module, "release_window_rect", release),
        patch.object(win32_module, "Clock", clock),
        patch.object(win32_module, "Window", MagicMock(fullscreen=False)),
    ):
        backend.schedule_restore(_saved_state(), MagicMock(), MagicMock())

    release.assert_called_once_with(_HWND)


def test_a_restore_that_finished_early_leaves_a_newer_restores_window_alone() -> None:
    """Out, in and out again: the second exit holds the window, and has its own restore."""
    with _Restore(_SAVED) as restore:
        restore.assert_called_back_once()
        restore.window_at = _ELSEWHERE  # the second exit, on its way
        restore.backend.schedule_restore(_saved_state(), MagicMock(), MagicMock())

        restore.clock.run_delayed_move()  # the first restore's: the oldest

        restore.release.assert_not_called()  # the held rectangle is the second exit's
        restore.move_window.assert_not_called()

        restore.clock.run_delayed_move()  # the second's own

        restore.release.assert_called_once_with(_HWND)
        restore.move_window.assert_called_once_with(_HWND, *_SAVED, True)  # noqa: FBT003


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


def test_a_move_as_fullscreen_ends_finishes_a_restore_already_waiting(
    loguru_sink: list[str],
) -> None:
    """The restore starts before the move: a move with no resize still finishes it at once."""
    with _Restore(_ELSEWHERE) as restore:
        restore.assert_not_called_back()

        restore.backend.move_now(_saved_state())

        restore.assert_called_back_once()
        assert any("finishing the restore without waiting" in s for s in loguru_sink)
        assert restore.clock.live() == [win32_module._RESTORE_GEOMETRY_TIMEOUT_WIN]


def test_a_move_after_the_restore_finished_at_the_resize_calls_back_no_more() -> None:
    """The exit's resize comes inside the move, and finishes the restore first."""
    with _Restore(_ELSEWHERE) as restore:
        on_resize = restore.window.bind.call_args.kwargs["on_resize"]
        restore.window_at = _SAVED
        on_resize(restore.window, 700, 500)

        restore.backend.move_now(_saved_state())

        restore.assert_called_back_once()


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


# --- The fallbacks no Linux run reached ---


def test_a_window_with_no_guard_to_hold_it_is_said_so(loguru_sink: list[str]) -> None:
    backend = _backend(MagicMock(), MagicMock())

    with patch.object(win32_module, "hold_window_rect", return_value=False):
        backend.hold_windowed_rect(_saved_state())

    assert "Win32: The window has no guard to hold it through the exit." in loguru_sink
    assert not any("Holding the window" in line for line in loguru_sink)


def test_with_no_window_handle_the_rectangle_is_not_read_and_nothing_is_moved() -> None:
    move_window, get_window_rect = MagicMock(), MagicMock()
    backend = _backend(move_window, get_window_rect)
    backend._hwnd = None

    assert backend._window_rect() is None
    assert backend._is_window_at(_ELSEWHERE) is False
    with patch.object(win32_module, "Clock") as clock:
        backend._set_window_rect(*_SAVED)

    get_window_rect.assert_not_called()
    move_window.assert_not_called()
    clock.schedule_once.assert_not_called()


def test_a_restore_s_move_that_raises_is_logged_not_raised(loguru_sink: list[str]) -> None:
    """Raised from a Clock callback, it would take the app down mid fullscreen exit."""
    backend = _backend(MagicMock(side_effect=OSError("access violation")), MagicMock())

    with patch.object(win32_module, "Clock") as clock:
        backend._set_window_rect(*_SAVED)

    assert "Win32 MoveWindow failed: access violation" in loguru_sink
    clock.schedule_once.assert_not_called()  # no recovery from a move that never happened


class _WindowThatWillNotResize:
    """Kivy's Window, refusing the size the recovery sets."""

    fullscreen = False

    @property
    def size(self) -> tuple[int, int]:
        return (136, 45)

    @size.setter
    def size(self, _size: tuple[int, int]) -> None:
        msg = "no GL context"
        raise RuntimeError(msg)


def test_a_recovery_kivy_refuses_is_logged_and_the_move_still_tried_again(
    loguru_sink: list[str],
) -> None:
    move_window = MagicMock(return_value=True)
    backend = _backend(move_window, _window_at(150, 120, 136, 45))

    with (
        patch.object(win32_module, "Window", _WindowThatWillNotResize()),
        patch.object(win32_module, "Clock") as clock,
    ):
        backend._set_window_rect(*_SAVED)
        run_last_scheduled(clock.schedule_once)

    assert "Window.size recovery failed: no GL context" in loguru_sink
    assert move_window.call_count == 2  # noqa: PLR2004


def test_a_window_gone_by_the_next_frame_is_not_moved_again(loguru_sink: list[str]) -> None:
    move_window = MagicMock(return_value=True)
    backend = _backend(move_window, _window_at(150, 120, 136, 45))

    with (
        patch.object(win32_module, "Window", MagicMock(fullscreen=False)),
        patch.object(win32_module, "Clock") as clock,
    ):
        backend._set_window_rect(*_SAVED)
        backend._hwnd = None  # the app is closing
        run_last_scheduled(clock.schedule_once)

    move_window.assert_called_once()
    assert not any(line.startswith("Win32 retry:") for line in loguru_sink)
