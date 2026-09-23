"""The Win32 window backend against a real window, on Windows only.

Everything else tests the window manager with this backend stubbed out; these
tests run the backend's own ctypes calls against a plain top-level window the
test makes, so a wrong signature, a wrong struct or a wrong idea of what
``MoveWindow`` does fails here rather than on a user's machine. No Kivy window
is opened (Kivy's ``Window`` and ``Clock`` are stood in for), so the headless CI
leg runs these tests: the ``needs_no_opengl`` marker keeps its UI skip off them.
"""

# ruff: noqa: SLF001
# cspell:ignore CXMINTRACK CYMINTRACK lpfn lpsz OVERLAPPEDWINDOW
# cspell:ignore pytestmark SHOWNOACTIVATE WNDCLASSW wndproc

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from typing import TYPE_CHECKING, Any, ClassVar
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui import platform_window_win32 as win32_module
from barks_reader.ui.platform_window_utils import FullscreenEnum, WindowState
from barks_reader.ui.platform_window_win32 import Win32WindowBackend

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="drives real Win32 windows"),
    pytest.mark.needs_no_opengl,
]

# The backend's lookup takes any visible window of this process whose class name
# starts with "SDL", as Kivy's is.
_CLASS_NAME = "SDL_barks_live_test"
_WS_OVERLAPPEDWINDOW = 0x00CF0000
_SW_SHOWNOACTIVATE = 4
_SM_CXMINTRACK, _SM_CYMINTRACK = 34, 35
# A size no overlapped window can take: Windows holds it at its minimum track size.
_TOO_SMALL = 20

# Where a test puts the window, well inside even a small CI screen.
_RECT_A = (150, 120, 700, 500)  # left, top, width, height
_RECT_B = (60, 40, 500, 400)


def _user32() -> Any:  # noqa: ANN401
    """Return user32 with the signatures these tests call through, 64-bit handles intact."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)  # ty: ignore[unresolved-attribute]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(win32_module._RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.MoveWindow.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.BOOL,
    ]
    return user32


def _window_rect(hwnd: int) -> tuple[int, int, int, int]:
    """Return the window's outer rectangle as (left, top, width, height)."""
    rect = win32_module._RECT()
    assert _user32().GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def _move(hwnd: int, rect: tuple[int, int, int, int]) -> None:
    assert _user32().MoveWindow(hwnd, *rect, True)  # noqa: FBT003


def _run_now(callback: Callable[[float], None], _timeout: float = 0) -> MagicMock:
    """Stand in for ``Clock.schedule_once``: run the callback at once."""
    callback(0)
    return MagicMock()


@pytest.fixture
def live_window() -> Iterator[int]:
    """Make a visible top-level window with an SDL-style class name; destroy it after."""
    user32 = _user32()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # ty: ignore[unresolved-attribute]
    lresult = wintypes.LPARAM
    wndproc_type = ctypes.WINFUNCTYPE(  # ty: ignore[unresolved-attribute]
        lresult, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
    )
    user32.DefWindowProcW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.DefWindowProcW.restype = lresult

    def window_proc(hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    wndproc = wndproc_type(window_proc)  # held until the window is gone

    class WNDCLASSW(ctypes.Structure):
        _fields_: ClassVar[list[tuple[str, Any]]] = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", wndproc_type),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]

    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    hinstance = kernel32.GetModuleHandleW(None)

    window_class = WNDCLASSW()
    window_class.lpfnWndProc = wndproc
    window_class.hInstance = hinstance
    window_class.lpszClassName = _CLASS_NAME
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    user32.RegisterClassW.restype = wintypes.ATOM
    if not user32.RegisterClassW(ctypes.byref(window_class)):
        raise ctypes.WinError(ctypes.get_last_error())  # ty: ignore[unresolved-attribute]

    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]

    hwnd = user32.CreateWindowExW(
        0,
        _CLASS_NAME,
        "Barks live test",
        _WS_OVERLAPPEDWINDOW,
        *_RECT_A,
        None,
        None,
        hinstance,
        None,
    )
    try:
        if not hwnd:
            raise ctypes.WinError(ctypes.get_last_error())  # ty: ignore[unresolved-attribute]
        user32.ShowWindow(hwnd, _SW_SHOWNOACTIVATE)
        yield hwnd
    finally:
        if hwnd:
            user32.DestroyWindow(hwnd)
        user32.UnregisterClassW(_CLASS_NAME, hinstance)
        del wndproc


@pytest.fixture
def kivy_window() -> Iterator[MagicMock]:
    """Stand in for Kivy's Window (a windowed one) and run the Clock's callbacks at once."""
    window = MagicMock(fullscreen=False)
    with (
        patch.object(win32_module, "Window", window),
        patch.object(win32_module.Clock, "schedule_once", side_effect=_run_now),
    ):
        yield window


def test_the_lookup_finds_an_sdl_window_of_this_process(live_window: int) -> None:
    found = Win32WindowBackend._find_hwnd_by_enum_windows()
    assert found

    user32 = _user32()
    class_name = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(found, class_name, 256)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(found, ctypes.byref(pid))
    assert class_name.value.startswith("SDL")
    assert pid.value == os.getpid()
    if win32_module.Window is None:
        # No Kivy window in this process (the CI leg's no_provider): ours is the only one.
        assert found == live_window


def test_a_backend_bound_to_the_window_is_available(live_window: int) -> None:
    assert Win32WindowBackend(hwnd=live_window).is_available()


@pytest.mark.usefixtures("kivy_window")
def test_set_window_rect_moves_and_resizes_the_window(
    live_window: int, loguru_sink: list[str]
) -> None:
    Win32WindowBackend(hwnd=live_window)._set_window_rect(*_RECT_B)

    assert _window_rect(live_window) == _RECT_B
    assert not any("no-op detected" in line for line in loguru_sink)


def test_a_size_below_the_minimum_takes_the_recovery_path(
    live_window: int, kivy_window: MagicMock, loguru_sink: list[str]
) -> None:
    """The documented bug: a window held at its minimum, where MoveWindow cannot shrink it."""
    left, top = _RECT_B[:2]
    Win32WindowBackend(hwnd=live_window)._set_window_rect(left, top, _TOO_SMALL, _TOO_SMALL)

    user32 = _user32()
    _, _, width, height = _window_rect(live_window)
    assert width >= user32.GetSystemMetrics(_SM_CXMINTRACK) > _TOO_SMALL
    assert height >= user32.GetSystemMetrics(_SM_CYMINTRACK) > _TOO_SMALL
    assert any("no-op detected" in line for line in loguru_sink)
    assert kivy_window.size == (_TOO_SMALL, _TOO_SMALL)  # recovered through SDL, then retried
    assert any(line.startswith("Win32 retry:") for line in loguru_sink)


@pytest.mark.usefixtures("kivy_window")
def test_save_state_reads_the_real_rectangle(live_window: int) -> None:
    _move(live_window, _RECT_B)
    state = WindowState()

    Win32WindowBackend(hwnd=live_window).save_state(state)

    assert state.screen == FullscreenEnum.WINDOWED
    assert state.pos == _RECT_B[:2]
    assert state.size == _RECT_B[2:]


@pytest.mark.usefixtures("kivy_window")
def test_a_scheduled_restore_puts_the_window_back_and_finishes(live_window: int) -> None:
    backend = Win32WindowBackend(hwnd=live_window)
    state = WindowState()
    backend.save_state(state)  # at _RECT_A, where the fixture made it
    _move(live_window, _RECT_B)
    on_first_resize, on_done = MagicMock(), MagicMock()

    backend.schedule_restore(state, on_first_resize, on_done)

    assert _window_rect(live_window) == _RECT_A
    on_first_resize.assert_called_once_with()
    on_done.assert_called_once_with()
