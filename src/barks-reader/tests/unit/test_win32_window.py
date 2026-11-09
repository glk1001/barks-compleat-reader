"""The Win32 window lookup's matching, on any OS, through a stand-in ``user32``.

``test_platform_window_win32_live.py`` runs the real calls on Windows; this pins
which window the lookup takes, and that a 64-bit handle comes back whole.
"""

# ruff: noqa: N802, SLF001

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
