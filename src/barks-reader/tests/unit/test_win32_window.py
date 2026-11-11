"""The Win32 window lookup's matching, on any OS, through a stand-in ``user32``.

``test_platform_window_win32_live.py`` runs the real calls on Windows; this pins
which window the lookup takes, and that a 64-bit handle comes back whole.
"""

# ruff: noqa: N802, SLF001
# cspell:ignore NOMOVE NOSIZE WINDOWPOS NCPAINT
# cspell:ignore WINDOWPOSCHANGING NCACTIVATE NCUAHDRAWCAPTION NCUAHDRAWFRAME

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import win32_window

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

OUR_PID = os.getpid()
OTHER_PID = OUR_PID + 1
HIGH_HWND = 0x1_0000_0010  # above 2**31: an untyped call cannot carry it


class FakeUser32:
    """The lookup's ``user32`` calls over a table of windows: hwnd -> (visible, pid, class)."""

    def __init__(
        self, windows: dict[int, tuple[bool, int, str]], active: int | None = None
    ) -> None:
        self.windows = windows
        self.active = active
        self.visited: list[int | None] = []

    def GetActiveWindow(self) -> int | None:
        return self.active

    def IsWindowVisible(self, hwnd: int) -> bool:
        return self.windows[hwnd][0]

    def GetWindowThreadProcessId(self, hwnd: int, pid_ref: Any) -> int:  # noqa: ANN401
        pid_ref._obj.value = self.windows[hwnd][1]
        return 1

    def GetClassNameW(self, hwnd: int, buffer: Any, _length: int) -> int:  # noqa: ANN401
        buffer.value = self.windows[hwnd][2]
        return len(buffer.value)

    def EnumWindows(self, callback: Callable[[int | None, int], bool], _lparam: int) -> bool:
        for hwnd in [None, *self.windows]:
            self.visited.append(hwnd)
            if not callback(hwnd, 0):
                return False
        return True


@pytest.fixture
def use_user32() -> Iterator[Callable[[FakeUser32], FakeUser32]]:
    """Stand a `FakeUser32` in for the typed ``user32``, and a pass-through callback type."""
    with patch.object(ctypes, "WINFUNCTYPE", create=True, new=lambda *_types: lambda f: f):

        def install(fake: FakeUser32) -> FakeUser32:
            patcher = patch.object(win32_window, "_typed_user32", return_value=fake)
            patcher.start()
            patchers.append(patcher)
            return fake

        patchers: list[Any] = []
        yield install
        for patcher in patchers:
            patcher.stop()


class TestFindHwndByEnumWindows:
    def test_the_visible_sdl_window_of_this_process_is_found(
        self, use_user32: Callable[[FakeUser32], FakeUser32]
    ) -> None:
        fake = use_user32(FakeUser32({10: (True, OUR_PID, "SDL_app"), 20: (True, OUR_PID, "SDL")}))

        assert win32_window.find_hwnd_by_enum_windows() == 10  # noqa: PLR2004
        assert fake.visited == [None, 10]  # the enumeration stops at it

    @pytest.mark.parametrize(
        "window",
        [
            (False, OUR_PID, "SDL_app"),  # hidden
            (True, OTHER_PID, "SDL_app"),  # another process
            (True, OUR_PID, "ConsoleWindowClass"),  # not SDL's
        ],
    )
    def test_any_other_window_is_passed_over(
        self, use_user32: Callable[[FakeUser32], FakeUser32], window: tuple[bool, int, str]
    ) -> None:
        use_user32(FakeUser32({10: window, 20: (True, OUR_PID, "SDL_app")}))

        assert win32_window.find_hwnd_by_enum_windows() == 20  # noqa: PLR2004

    def test_no_window_gives_zero(self, use_user32: Callable[[FakeUser32], FakeUser32]) -> None:
        use_user32(FakeUser32({10: (True, OTHER_PID, "SDL_app")}))

        assert win32_window.find_hwnd_by_enum_windows() == 0

    def test_a_64_bit_handle_comes_back_whole(
        self, use_user32: Callable[[FakeUser32], FakeUser32]
    ) -> None:
        use_user32(FakeUser32({HIGH_HWND: (True, OUR_PID, "SDL_app")}))

        assert win32_window.find_hwnd_by_enum_windows() == HIGH_HWND


class TestFindAppHwnd:
    def test_the_active_window_is_taken_first(
        self, use_user32: Callable[[FakeUser32], FakeUser32]
    ) -> None:
        fake = use_user32(FakeUser32({10: (True, OUR_PID, "SDL_app")}, active=HIGH_HWND))

        assert win32_window.find_app_hwnd() == HIGH_HWND
        assert fake.visited == []

    def test_with_no_active_window_the_windows_are_enumerated(
        self, use_user32: Callable[[FakeUser32], FakeUser32]
    ) -> None:
        use_user32(FakeUser32({10: (True, OUR_PID, "SDL_app")}, active=None))

        assert win32_window.find_app_hwnd() == 10  # noqa: PLR2004


@pytest.fixture
def fresh_user32() -> Iterator[MagicMock]:
    """Stand in for ``ctypes.WinDLL`` (Windows only), returning the library it loads."""
    library = MagicMock()
    with patch.object(ctypes, "WinDLL", create=True, return_value=library) as win_dll:
        yield library
    win_dll.assert_called_with("user32", use_last_error=True)


class TestTyping:
    """Each call carries a handle as ``HWND``, so a 64-bit one goes in and out whole."""

    def test_the_lookups_calls_are_typed(self, fresh_user32: MagicMock) -> None:
        user32 = win32_window._typed_user32()

        assert user32 is fresh_user32
        typing = {
            "GetActiveWindow": ([], wintypes.HWND),
            "IsWindowVisible": ([wintypes.HWND], wintypes.BOOL),
            "GetWindowThreadProcessId": (
                [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)],
                wintypes.DWORD,
            ),
            "GetClassNameW": ([wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
            "EnumWindows": ([ctypes.c_void_p, wintypes.LPARAM], wintypes.BOOL),
        }
        for call, (argtypes, restype) in typing.items():
            assert getattr(user32, call).argtypes == argtypes, call
            assert getattr(user32, call).restype is restype, call

    def test_the_windows_calls_are_typed(self, fresh_user32: MagicMock) -> None:
        window = win32_window.Win32Window(HIGH_HWND)

        assert window.hwnd == HIGH_HWND
        assert window.move_window is fresh_user32.MoveWindow
        for call in (window.move_window, window.get_window_rect, window.get_client_rect):
            assert call.argtypes[0] is wintypes.HWND
            assert call.restype is wintypes.BOOL
        assert window.get_window_rect.argtypes[1] is ctypes.POINTER(win32_window.RECT)
        assert window.get_client_rect.argtypes[1] is ctypes.POINTER(win32_window.RECT)


OTHER_MESSAGE = 0x0401
NEXT_PROC = 0x7FF0_0000_1000


class TestGuardedFrameMessage:
    def test_an_activation_is_passed_on_with_no_repaint_of_the_frame(self) -> None:
        passed_on = win32_window.guarded_frame_message(win32_window.WM_NCACTIVATE, 0)
        assert passed_on == win32_window.NO_FRAME_REPAINT

    @pytest.mark.parametrize(
        "msg", [win32_window.WM_NCUAHDRAWCAPTION, win32_window.WM_NCUAHDRAWFRAME]
    )
    def test_the_themes_caption_drawing_is_answered_here(self, msg: int) -> None:
        assert win32_window.guarded_frame_message(msg, 5) is None

    def test_every_other_message_goes_on_as_it_came(self) -> None:
        assert win32_window.guarded_frame_message(OTHER_MESSAGE, 5) == 5  # noqa: PLR2004


@pytest.fixture
def guard_user32() -> Iterator[MagicMock]:
    """Stand in for the ``user32`` a guard loads, on any OS; its window takes the guard."""
    user32 = MagicMock()
    user32.SetWindowLongPtrW.return_value = NEXT_PROC
    with (
        patch.object(ctypes, "WinDLL", create=True, return_value=user32),
        patch.object(ctypes, "WINFUNCTYPE", create=True, new=lambda *_types: lambda f: f),
        patch.object(ctypes, "cast", return_value=MagicMock(value=1)),
        patch.object(win32_window, "_caption_guards", []),
    ):
        yield user32


class TestCaptionGuard:
    def test_the_guard_goes_before_the_windows_own_procedure(
        self, guard_user32: MagicMock, loguru_sink: list[str]
    ) -> None:
        assert win32_window.guard_against_native_caption(HIGH_HWND)

        (hwnd, index, _proc), _ = guard_user32.SetWindowLongPtrW.call_args
        assert (hwnd, index) == (HIGH_HWND, -4)
        assert len(win32_window._caption_guards) == 1  # held: the window calls it
        assert any("Guarding window 0x100000010" in s for s in loguru_sink)

    def test_an_activation_reaches_the_window_with_no_repaint(
        self, guard_user32: MagicMock
    ) -> None:
        win32_window.guard_against_native_caption(HIGH_HWND)
        (guard,) = win32_window._caption_guards
        guard_user32.CallWindowProcW.return_value = 1

        result = guard._on_message(HIGH_HWND, win32_window.WM_NCACTIVATE, 0, 0)

        assert result == 1
        guard_user32.CallWindowProcW.assert_called_once_with(
            NEXT_PROC, HIGH_HWND, win32_window.WM_NCACTIVATE, 0, win32_window.NO_FRAME_REPAINT
        )

    def test_the_themes_caption_drawing_never_reaches_the_window(
        self, guard_user32: MagicMock
    ) -> None:
        win32_window.guard_against_native_caption(HIGH_HWND)
        (guard,) = win32_window._caption_guards

        assert guard._on_message(HIGH_HWND, win32_window.WM_NCUAHDRAWCAPTION, 1, 2) == 0
        guard_user32.CallWindowProcW.assert_not_called()

    def test_another_message_reaches_the_window_unchanged(self, guard_user32: MagicMock) -> None:
        win32_window.guard_against_native_caption(HIGH_HWND)
        (guard,) = win32_window._caption_guards

        guard._on_message(HIGH_HWND, OTHER_MESSAGE, 1, 2)

        guard_user32.CallWindowProcW.assert_called_once_with(
            NEXT_PROC, HIGH_HWND, OTHER_MESSAGE, 1, 2
        )

    def test_a_window_that_refuses_the_guard_is_left_and_it_says_so(
        self, guard_user32: MagicMock, loguru_sink: list[str]
    ) -> None:
        guard_user32.SetWindowLongPtrW.return_value = None

        assert not win32_window.guard_against_native_caption(HIGH_HWND)

        assert win32_window._caption_guards == []
        assert any("Could not guard the window" in s for s in loguru_sink)


HELD = (150, 120, 700, 500)  # left, top, width, height
ASKED = (142, 89, 716, 539)  # where SDL's fullscreen exit asks for: a frame too big


def _window_pos(flags: int = 0) -> win32_window.WINDOWPOS:
    window_pos = win32_window.WINDOWPOS()
    window_pos.x, window_pos.y, window_pos.cx, window_pos.cy = ASKED
    window_pos.flags = flags
    return window_pos


def _rect_of(window_pos: win32_window.WINDOWPOS) -> tuple[int, int, int, int]:
    return window_pos.x, window_pos.y, window_pos.cx, window_pos.cy


class TestPutAtHeldRect:
    def test_a_move_and_resize_goes_to_the_held_rectangle(self) -> None:
        window_pos = _window_pos()
        win32_window.put_at_held_rect(window_pos, HELD)
        assert _rect_of(window_pos) == HELD

    def test_a_move_that_keeps_the_size_keeps_it(self) -> None:
        window_pos = _window_pos(win32_window.SWP_NOSIZE)
        win32_window.put_at_held_rect(window_pos, HELD)
        assert _rect_of(window_pos) == (*HELD[:2], *ASKED[2:])

    def test_a_resize_that_keeps_the_position_keeps_it(self) -> None:
        window_pos = _window_pos(win32_window.SWP_NOMOVE)
        win32_window.put_at_held_rect(window_pos, HELD)
        assert _rect_of(window_pos) == (*ASKED[:2], *HELD[2:])


class TestHeldRect:
    """A guard holding its window at a rectangle, through moves the app does not make."""

    @staticmethod
    def _changing(guard: win32_window.CaptionGuard) -> tuple[int, int, int, int]:
        """Send the guard a move to `ASKED`; return where the window is then to go."""
        window_pos = _window_pos()
        guard._on_message(
            HIGH_HWND, win32_window.WM_WINDOWPOSCHANGING, 0, ctypes.addressof(window_pos)
        )
        return _rect_of(window_pos)

    @pytest.fixture
    def guard(self, guard_user32: MagicMock) -> win32_window.CaptionGuard:
        assert guard_user32 is not None
        win32_window.guard_against_native_caption(HIGH_HWND)
        (guard,) = win32_window._caption_guards
        return guard

    def test_with_nothing_held_the_window_goes_where_it_is_sent(
        self, guard: win32_window.CaptionGuard
    ) -> None:
        assert self._changing(guard) == ASKED

    def test_a_held_window_goes_to_its_rectangle_and_the_move_still_goes_on(
        self, guard: win32_window.CaptionGuard, guard_user32: MagicMock
    ) -> None:
        assert win32_window.hold_window_rect(HIGH_HWND, HELD)

        assert self._changing(guard) == HELD
        guard_user32.CallWindowProcW.assert_called_once()  # the window is still told

    def test_letting_go_logs_the_frame_messages_the_held_window_had(
        self, guard: win32_window.CaptionGuard, loguru_sink: list[str]
    ) -> None:
        """What a log has to say whether the desktop painted its caption during an exit."""
        guard._on_message(HIGH_HWND, 0x0085, 0, 0)  # before the hold: not kept
        win32_window.hold_window_rect(HIGH_HWND, HELD)
        guard._on_message(HIGH_HWND, 0x0085, 0, 0)
        guard._on_message(HIGH_HWND, OTHER_MESSAGE, 0, 0)
        guard._on_message(HIGH_HWND, win32_window.WM_NCUAHDRAWCAPTION, 0, 0)

        win32_window.release_window_rect(HIGH_HWND)
        win32_window.release_window_rect(HIGH_HWND)  # nothing new: no second line

        lines = [s for s in loguru_sink if "Frame messages while the window was held" in s]
        assert len(lines) == 1
        assert "WM_NCPAINT, +" in lines[0]
        assert lines[0].count("WM_NCPAINT") == 1
        assert "WM_NCUAHDRAWCAPTION." in lines[0]

    def test_once_let_go_the_window_goes_where_it_is_sent(
        self, guard: win32_window.CaptionGuard
    ) -> None:
        win32_window.hold_window_rect(HIGH_HWND, HELD)
        win32_window.release_window_rect(HIGH_HWND)

        assert self._changing(guard) == ASKED

    def test_a_rectangle_nobody_let_go_is_dropped_in_a_couple_of_seconds(
        self, guard: win32_window.CaptionGuard
    ) -> None:
        """A forgotten hold would pin the window where it was for good."""
        with patch.object(win32_window.time, "monotonic", return_value=100.0):
            win32_window.hold_window_rect(HIGH_HWND, HELD)
        with patch.object(win32_window.time, "monotonic", return_value=103.0):
            assert self._changing(guard) == ASKED
        assert self._changing(guard) == ASKED  # and it stays dropped

    @pytest.mark.usefixtures("guard")
    def test_a_window_with_no_guard_holds_nothing(self) -> None:
        assert not win32_window.hold_window_rect(HIGH_HWND + 1, HELD)
        win32_window.release_window_rect(HIGH_HWND + 1)  # and letting go is safe
