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
from unittest.mock import patch

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


class TestFullscreenChange:
    """Into or out of fullscreen, the titled window is missing for about a second."""

    STAND_IN = _window(9, "python", "")  # untitled, screen-sized, the app's process

    def test_an_untitled_window_of_the_app_is_a_fullscreen_change(self) -> None:
        assert gui_probe_darwin.in_fullscreen_change([self.STAND_IN])

    def test_another_apps_untitled_window_is_not(self) -> None:
        assert not gui_probe_darwin.in_fullscreen_change([_window(3, "Finder", "")])
        assert not gui_probe_darwin.in_fullscreen_change([])

    def test_the_lookup_waits_through_the_change_for_the_titled_window(self) -> None:
        titled = _window(5, "python", "The Compleat Barks Disney Reader")
        lists = [[self.STAND_IN], [self.STAND_IN], [titled]]
        with (
            patch.object(gui_probe_darwin, "_declare"),
            patch.object(gui_probe_darwin, "window_list", side_effect=lists),
            patch.object(gui_probe_darwin.time, "sleep"),
        ):
            assert gui_probe_darwin.DarwinBackend().find_window(APP_TITLE) == 5

    def test_a_window_replaced_after_it_was_found_is_found_again(self) -> None:
        """Leaving fullscreen the window found a moment ago goes; its successor is used."""
        old = _window(5, "python", "The Compleat Barks Disney Reader", pid=77)
        new = WindowInfo(
            6, 77, "python", "The Compleat Barks Disney Reader", 0, (838, 1310, 861, 25)
        )
        calls = 0

        def listing(*, only: int | None = None) -> list[WindowInfo]:
            nonlocal calls
            current = [old] if calls == 0 else [new]  # replaced after the lookup
            calls += 1
            return [w for w in current if only is None or w.number == only]

        with (
            patch.object(gui_probe_darwin, "_declare"),
            patch.object(gui_probe_darwin, "window_list", side_effect=listing),
        ):
            backend = gui_probe_darwin.DarwinBackend()
            assert backend.find_window(APP_TITLE) == 5
            assert backend.client_geometry(5) == new.bounds

    def test_with_nothing_of_the_apps_on_screen_the_lookup_answers_at_once(self) -> None:
        """As before a start: no stand-in, so no wait."""
        with (
            patch.object(gui_probe_darwin, "_declare"),
            patch.object(gui_probe_darwin, "window_list", return_value=[]) as listing,
        ):
            assert gui_probe_darwin.DarwinBackend().find_window(APP_TITLE) is None
        listing.assert_called_once()


class TestKeyTarget:
    """Keys go to the app's process alone, never to whatever app is in front."""

    @staticmethod
    def _backend() -> gui_probe_darwin.DarwinBackend:
        with patch.object(gui_probe_darwin, "_declare"):
            return gui_probe_darwin.DarwinBackend()

    def test_no_key_is_sent_before_the_app_was_found_in_front(self) -> None:
        backend = self._backend()
        with (
            patch.object(gui_probe_darwin, "_key") as key,
            pytest.raises(RuntimeError, match="no app process"),
        ):
            backend.send_key("Return")
        key.assert_not_called()

    def test_keys_and_typed_text_go_to_the_apps_process(self) -> None:
        backend = self._backend()
        app = _window(7, "python", "The Compleat Barks Disney Reader", pid=4321)
        with (
            patch.object(gui_probe_darwin, "window_list", return_value=[app]),
            patch.object(gui_probe_darwin, "_key") as key,
        ):
            assert backend.bring_to_front(7)
            backend.send_key("Escape")
            backend.send_char("M")
        assert [c.args for c in key.call_args_list] == [
            (4321, 53),
            (4321, 53),
            (4321, 46),
            (4321, 46),
        ]
        assert key.call_args_list[2].kwargs == {"down": True, "shift": True, "char": "M"}


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
