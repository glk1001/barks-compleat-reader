"""Tests for the macOS backend of the GUI probe.

The key tables and the window picking are plain Python and run everywhere; the
calls into the window server and the process handling run on macOS only.
"""

# ruff: noqa: PLR2004  (key codes and pixel counts are the point of these tests)

# cspell:ignore pids frontmost unshifted pgrep

from __future__ import annotations

import string
import subprocess
import sys
import time
from pathlib import Path

import gui_probe
import gui_probe_darwin
import gui_probe_win32
import pytest
from gui_probe_darwin import WindowInfo, frontmost_normal_window, is_app_window, pick_app_window

APP_TITLE = "Compleat Barks Disney Reader"
REPO_ROOT = Path(__file__).resolve().parents[2]

_on_macos = pytest.mark.skipif(sys.platform != "darwin", reason="calls the macOS window server")


def _window(number: int, owner: str, title: str, layer: int = 0, pid: int = 100) -> WindowInfo:
    return WindowInfo(
        number=number,
        owner_pid=pid,
        owner_name=owner,
        title=title,
        layer=layer,
        bounds=(874, 1365, 843, 25),
    )


class TestKeys:
    def test_every_key_the_suite_sends_has_a_mac_key(self) -> None:
        """The remote's six keys, and Delete, the one desktop key a test is waived to press."""
        for name in ("Escape", "Return", "Up", "Down", "Left", "Right", "Delete"):
            assert name in gui_probe_darwin.VIRTUAL_KEYS

    def test_it_knows_every_key_name_the_windows_probe_knows(self) -> None:
        assert set(gui_probe_darwin.VIRTUAL_KEYS) == set(gui_probe_win32.VIRTUAL_KEYS)

    def test_delete_is_forward_delete_not_the_macs_backspace(self) -> None:
        assert gui_probe_darwin.VIRTUAL_KEYS["Delete"] == 117
        assert gui_probe_darwin.VIRTUAL_KEYS["BackSpace"] == 51

    def test_every_printable_ascii_character_has_a_key(self) -> None:
        printable = set(string.ascii_letters + string.digits + string.punctuation + " ")
        assert printable <= set(gui_probe_darwin.CHAR_KEYS)

    def test_a_shifted_character_shares_its_key_with_the_unshifted_one(self) -> None:
        keys = gui_probe_darwin.CHAR_KEYS
        assert keys["a"] == (0, False)
        assert keys["A"] == (0, True)
        assert keys["1"] == (18, False)
        assert keys["!"] == (18, True)
        assert keys["/"] == (44, False)
        assert keys["?"] == (44, True)
        assert keys[" "] == (49, False)


class TestWindowPicking:
    def test_the_apps_window_is_a_python_window_with_its_title(self) -> None:
        assert is_app_window(_window(1, "python", "The Compleat Barks Disney Reader"), APP_TITLE)

    def test_a_built_app_owns_its_window_too(self) -> None:
        window = _window(1, "barks-reader-macos-x64", "The Compleat Barks Disney Reader")
        assert is_app_window(window, APP_TITLE)

    def test_a_terminal_titled_for_the_app_is_not_its_window(self) -> None:
        """A terminal tab or an editor naming the app would take the keys meant for it."""
        terminal = _window(1, "Terminal", "Compleat Barks Disney Reader - claude - 180x52")
        assert not is_app_window(terminal, APP_TITLE)

    def test_a_window_above_the_normal_layer_is_not_its_window(self) -> None:
        assert not is_app_window(_window(1, "python", APP_TITLE, layer=25), APP_TITLE)

    def test_the_frontmost_of_the_apps_windows_is_picked(self) -> None:
        windows = [
            _window(1, "Terminal", "Compleat Barks Disney Reader"),
            _window(2, "python", "The Compleat Barks Disney Reader"),
            _window(3, "python", "The Compleat Barks Disney Reader"),
        ]
        picked = pick_app_window(windows, APP_TITLE)
        assert picked is not None
        assert picked.number == 2
        assert pick_app_window(windows[:1], APP_TITLE) is None

    def test_the_menu_bar_is_not_the_frontmost_window(self) -> None:
        windows = [
            _window(1, "Window Server", "Menubar", layer=24),
            _window(2, "Control Centre", "Clock", layer=25),
            _window(3, "python", "The Compleat Barks Disney Reader", pid=7),
            _window(4, "Terminal", "zsh"),
        ]
        front = frontmost_normal_window(windows)
        assert front is not None
        assert front.owner_pid == 7


class TestLaunch:
    def test_the_workspace_app_runs_through_the_soft_gl_wrapper(self) -> None:
        argv = gui_probe_darwin.DarwinBackend.workspace_app_argv(REPO_ROOT)
        assert argv[0] == "bash"
        assert Path(argv[1]) == REPO_ROOT / "scripts" / "macos" / "with-soft-gl.sh"
        assert Path(argv[1]).is_file()
        assert argv[2:] == ["python", str(REPO_ROOT / "main.py")]

    def test_the_app_gets_a_session_of_its_own(self) -> None:
        """So the probe's Ctrl+C never reaches it, and one signal ends uv and Python together."""
        assert gui_probe_darwin.DarwinBackend.start_new_session
        assert gui_probe_darwin.DarwinBackend.creation_flags == 0

    def test_the_probe_picks_this_backend_on_macos(self) -> None:
        if sys.platform != "darwin":
            pytest.skip("macOS picks it")
        assert isinstance(gui_probe._backend(), gui_probe_darwin.DarwinBackend)  # noqa: SLF001


@_on_macos
class TestLive:
    def test_the_window_list_has_windows_and_names_their_owners(self) -> None:
        windows = gui_probe_darwin.window_list()
        assert windows
        assert all(w.owner_pid > 0 and w.owner_name for w in windows)

    def test_a_running_process_is_alive_and_a_finished_one_is_not(self) -> None:
        process = subprocess.Popen(["sleep", "30"], start_new_session=True)  # noqa: S607
        backend = gui_probe_darwin.DarwinBackend()
        try:
            assert backend.process_alive(process.pid)
        finally:
            process.kill()
            process.wait()
        assert not backend.process_alive(process.pid)

    def test_killing_the_tree_ends_the_whole_process_group(self) -> None:
        # A shell with a child, as uv runs Python: both must go.
        process = subprocess.Popen(
            ["/bin/sh", "-c", "sleep 30 & wait"],
            start_new_session=True,
        )
        backend = gui_probe_darwin.DarwinBackend()
        time.sleep(0.3)
        child = subprocess.run(  # noqa: S603
            ["pgrep", "-P", str(process.pid)],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        ).stdout.split()
        assert child
        backend.kill_tree(process.pid, max_secs=5)
        assert not backend.process_alive(process.pid)
        assert not backend.process_alive(int(child[0]))
