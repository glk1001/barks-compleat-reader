"""Tests for the probe's Windows backend, with Windows' own calls faked: run everywhere.

Only the structure-size test needs Windows itself.
"""

# ruff: noqa: PLR2004  (small literal counts are the point of these tests)

from __future__ import annotations

import ctypes
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import gui_probe_win32
import pytest
from check_gui_keys import REMOTE_KEYS

# The remote's six keys, and Delete, the one desktop key a test is waived to press.
KEYS_THE_SUITE_SENDS = (*sorted(REMOTE_KEYS), "Delete")


def _backend() -> gui_probe_win32.Win32Backend:
    """Make the backend off Windows too: constructing it declares Windows' own calls."""
    with patch.object(gui_probe_win32.Win32Backend, "__init__", return_value=None):
        return gui_probe_win32.Win32Backend()


class TestWin32Keys:
    def test_every_key_the_suite_sends_has_a_windows_key(self) -> None:
        """The remote's six keys, and Delete, the one desktop key a test is waived to press."""
        for name in KEYS_THE_SUITE_SENDS:
            assert name in gui_probe_win32.VIRTUAL_KEYS

    def test_the_arrows_are_extended_keys(self) -> None:
        # Without the flag SDL reads them as the numeric keypad's arrows.
        for name in ("Up", "Down", "Left", "Right", "Delete"):
            assert gui_probe_win32.VIRTUAL_KEYS[name][1]
        assert not gui_probe_win32.VIRTUAL_KEYS["Return"][1]

    def test_bringing_the_app_forward_sends_no_input(self) -> None:
        """No key to take the foreground: it would land in whatever window had it."""
        user32 = MagicMock()
        user32.GetForegroundWindow.side_effect = [111, 111, 222]  # someone else's, then ours
        user32.GetWindowThreadProcessId.return_value = 7
        user32.IsIconic.return_value = False
        kernel32 = MagicMock()
        kernel32.GetCurrentThreadId.return_value = 3
        with (
            patch.object(gui_probe_win32, "_user32", user32),
            patch.object(gui_probe_win32, "_kernel32", kernel32),
            patch.object(gui_probe_win32, "_send") as send,
        ):
            assert _backend().bring_to_front(222)
        send.assert_not_called()
        user32.SetForegroundWindow.assert_called_once_with(222)
        # Joined the foreground thread's input for the switch, and left it after.
        assert [c.args for c in user32.AttachThreadInput.call_args_list] == [
            (3, 7, True),
            (3, 7, False),
        ]

    def test_a_browser_tab_named_for_the_app_is_not_its_window(self) -> None:
        """Only SDL's window counts: a titled browser tab would take the app's keys."""
        windows = {  # hwnd: (class, title)
            1: ("MozillaWindowClass", "The Compleat Barks Disney Reader — Mozilla Firefox"),
            2: ("SDL_app", "The Compleat Barks Disney Reader"),
        }
        user32 = MagicMock()
        user32.IsWindowVisible.return_value = True
        user32.EnumWindows.side_effect = lambda visit, _lparam: all(visit(h, 0) for h in windows)
        user32.GetClassNameW.side_effect = lambda h, buf, _n: setattr(buf, "value", windows[h][0])
        user32.GetWindowTextLengthW.side_effect = lambda h: len(windows[h][1])
        user32.GetWindowTextW.side_effect = lambda h, buf, _n: setattr(buf, "value", windows[h][1])
        with (
            patch.object(gui_probe_win32, "_user32", user32),
            patch.object(gui_probe_win32, "_ENUM_WINDOWS_PROC", lambda f: f),
        ):
            backend = _backend()
            assert backend.find_window("Compleat Barks Disney Reader") == 2
            del windows[2]
            assert backend.find_window("Compleat Barks Disney Reader") is None

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows' own structure sizes")
    def test_input_is_the_size_send_input_expects(self) -> None:
        # SendInput refuses every event when cbSize is not sizeof(INPUT): 40 on 64-bit, 28 on 32.
        expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        assert ctypes.sizeof(gui_probe_win32._INPUT) == expected  # noqa: SLF001


def _rect_filler(left: int, top: int, right: int, bottom: int) -> object:
    """Stand in for a call that fills in the rectangle it is passed by reference."""

    def fill(_window: int, by_ref: Any) -> bool:  # noqa: ANN401 (a ctypes reference)
        rect = by_ref._obj  # noqa: SLF001 (the structure ctypes.byref wraps)
        rect.left, rect.top, rect.right, rect.bottom = left, top, right, bottom
        return True

    return fill


class TestWin32Resize:
    def test_the_frame_is_added_to_the_size_asked_for_the_drawable_area(self) -> None:
        """SetWindowPos sizes the whole window: 16 and 39 here are its frame's share."""
        user32 = MagicMock()
        user32.GetClientRect.side_effect = _rect_filler(0, 0, 782, 1224)
        user32.GetWindowRect.side_effect = _rect_filler(100, 50, 100 + 798, 50 + 1263)
        with patch.object(gui_probe_win32, "_user32", user32):
            _backend().resize_client(222, 900, 1100)

        # The size alone (0x16): not moved, not raised, not made the active window.
        user32.SetWindowPos.assert_called_once_with(222, None, 0, 0, 916, 1139, 0x16)

    def test_a_window_that_has_gone_is_an_error(self) -> None:
        user32 = MagicMock()
        user32.GetClientRect.return_value = 0
        with (
            patch.object(gui_probe_win32, "_user32", user32),
            pytest.raises(RuntimeError, match="the app window has gone"),
        ):
            _backend().resize_client(222, 900, 1100)
        user32.SetWindowPos.assert_not_called()

    def test_a_refused_resize_is_an_error(self) -> None:
        user32 = MagicMock()
        user32.GetClientRect.side_effect = _rect_filler(0, 0, 782, 1224)
        user32.GetWindowRect.side_effect = _rect_filler(0, 0, 782, 1224)
        user32.SetWindowPos.return_value = 0
        with (
            patch.object(gui_probe_win32, "_user32", user32),
            pytest.raises(RuntimeError, match="not resized to 900x1100"),
        ):
            _backend().resize_client(222, 900, 1100)


class TestWin32Close:
    """The app is asked to close before it is ended, so coverage can save its data."""

    def test_the_process_tree_takes_children_and_grandchildren_only(self) -> None:
        parents = {10: 1, 11: 10, 12: 11, 20: 1, 21: 20}
        assert gui_probe_win32.descendants(10, parents) == {10, 11, 12}
        assert gui_probe_win32.descendants(99, parents) == {99}

    @staticmethod
    def _kill(*, window: int | None, exits: bool) -> tuple[MagicMock, MagicMock, MagicMock]:
        user32 = MagicMock()
        user32.PostMessageW.return_value = 1
        kernel32 = MagicMock()
        kernel32.OpenProcess.return_value = 555
        kernel32.WaitForSingleObject.return_value = 0 if exits else 0x102  # WAIT_TIMEOUT
        with (
            patch.object(gui_probe_win32, "_user32", user32),
            patch.object(gui_probe_win32, "_kernel32", kernel32),
            patch.object(gui_probe_win32, "_process_parents", return_value={7: 4}),
            patch.object(gui_probe_win32, "find_window_of_processes", return_value=window) as find,
            patch.object(gui_probe_win32.subprocess, "run") as run,
        ):
            _backend().kill_tree(4, max_secs=10)
        find.assert_called_once_with({4, 7})  # uv and the python under it
        return user32, kernel32, run

    def test_an_app_that_closes_is_not_killed(self) -> None:
        user32, kernel32, run = self._kill(window=42, exits=True)
        user32.PostMessageW.assert_called_once_with(42, 0x0010, 0, 0)  # WM_CLOSE
        run.assert_not_called()
        kernel32.CloseHandle.assert_called_once_with(555)

    def test_an_app_that_will_not_close_is_killed(self, capsys: pytest.CaptureFixture[str]) -> None:
        _, _, run = self._kill(window=42, exits=False)
        assert run.call_args.args[0][-1] == "/F"
        assert "ending it by force" in capsys.readouterr().out

    def test_an_app_with_no_window_is_killed(self) -> None:
        user32, _, run = self._kill(window=None, exits=True)
        user32.PostMessageW.assert_not_called()
        assert run.call_args.args[0][-1] == "/F"
