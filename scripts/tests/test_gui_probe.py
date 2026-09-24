"""Tests for the Python GUI probe: its paths, its log waits, and its contract with the suite.

The probe's input goes through a platform backend, so what can be tested
everywhere is the part every platform shares: where it looks for the config,
how it reads the app log, and that the lines it writes are the ones the GUI
harness parses. The Windows backend's structures are checked on Windows.
"""

# ruff: noqa: PLR2004  (small literal counts are the point of these tests)

# cspell:ignore glew PYTHONIOENCODING

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import gui_probe
import gui_probe_win32
import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

GUI_TESTS_DIR = Path(__file__).resolve().parents[2] / "src" / "barks-reader" / "tests" / "gui"


@pytest.fixture
def run_dir(tmp_path: Path) -> Iterator[Path]:
    with patch.object(gui_probe, "run_dir", return_value=tmp_path):
        yield tmp_path


class TestEnvRuntime:
    def test_a_quoted_value(self, tmp_path: Path) -> None:
        env = tmp_path / ".env.runtime"
        env.write_text('BARKS_READER_CONFIG_DIR="${HOME}/opt/barks-reader/config"\n')
        value = gui_probe.env_runtime_value("BARKS_READER_CONFIG_DIR", env)
        assert value == "${HOME}/opt/barks-reader/config"

    def test_an_unquoted_value_and_a_missing_one(self, tmp_path: Path) -> None:
        env = tmp_path / ".env.runtime"
        env.write_text("BARKS_READER_DATA_DIR=C:/BarksReader\nOTHER=1\n")
        assert gui_probe.env_runtime_value("BARKS_READER_DATA_DIR", env) == "C:/BarksReader"
        assert gui_probe.env_runtime_value("BARKS_ZIPS_KEY", env) == ""

    def test_a_missing_file_is_no_value(self, tmp_path: Path) -> None:
        assert gui_probe.env_runtime_value("X", tmp_path / "absent") == ""

    def test_home_is_expanded_as_env_runtime_writes_it(self) -> None:
        assert gui_probe.expand_home("${HOME}/opt") == f"{Path.home()}/opt"


class TestConfigDir:
    def test_an_exported_variable_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BARKS_READER_CONFIG_DIR", "/scratch/config")
        with patch.object(gui_probe, "env_runtime_value", return_value="/elsewhere"):
            assert gui_probe.config_dir() == Path("/scratch/config")

    def test_then_env_runtime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BARKS_READER_CONFIG_DIR", raising=False)
        with patch.object(gui_probe, "env_runtime_value", return_value="${HOME}/cfg"):
            assert gui_probe.config_dir() == Path.home() / "cfg"

    def test_the_run_directory_is_named_after_the_display(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BARKS_PROBE_DISPLAY", ":5")
        assert gui_probe.run_dir().name == "barks-gui-probe-5"


class TestDoctor:
    def test_a_directory_is_warned_about_only_while_its_switch_is_on(self, tmp_path: Path) -> None:
        ini = tmp_path / "barks-reader.ini"
        ini.write_text(
            "[Barks Reader]\n"
            f"fanta_dir = {tmp_path}\n"
            "prebuilt_dir = /nowhere/prebuilt\n"
            "use_prebuilt_comics = 0\n"
            "png_barks_panels_dir = /nowhere/pngs\n"
            "use_png_images = 1\n"
        )
        found = gui_probe.dir_setting_checks(ini)
        checks = {text.split()[0]: status for status, text in found}
        assert checks == {"fanta_dir": "OK", "prebuilt_dir": "--", "png_barks_panels_dir": "WARN"}


class TestTailOutput:
    def test_tail_prints_characters_a_windows_code_page_cannot_encode(self, tmp_path: Path) -> None:
        """The app log's box drawing crashed `tail` under Windows' cp1252 console."""
        run = tmp_path / "barks-gui-probe-97"
        run.mkdir()
        (run / "app.log").write_text("\u2514\u2500 a tree line\n", encoding="utf-8")
        # The probe's run folder is under the temp dir, which these variables set.
        env = dict(
            os.environ,
            BARKS_PROBE_DISPLAY=":97",
            PYTHONIOENCODING="cp1252",
            TMPDIR=str(tmp_path),
            TEMP=str(tmp_path),
            TMP=str(tmp_path),
        )
        result = subprocess.run(  # noqa: S603
            [sys.executable, gui_probe.__file__, "tail", "5"],
            capture_output=True,
            env=env,
            check=False,
        )
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        # Lines, not raw bytes: the console ends them with \r\n on Windows.
        assert result.stdout.decode("utf-8").splitlines() == ["\u2514\u2500 a tree line"]


class TestAppEnv:
    def test_the_app_log_is_plain_text_even_under_a_terminal(self) -> None:
        """Git Bash sets TERM, and loguru on Windows then colours even a file."""
        env = gui_probe.app_env({"TERM": "xterm", "PATH": "p"})
        assert env["LOGURU_COLORIZE"] == "0"
        assert env["PATH"] == "p"


class TestGlBackend:
    LOG = "2026-09-23 | INFO | kivy: kivy:print_gl_version:51 - GL: Backend used <glew>\n"

    def test_a_run_that_asked_for_angle_but_got_opengl_is_refused(self) -> None:
        problem = gui_probe.gl_backend_problem("angle_sdl2", self.LOG)
        assert problem is not None
        assert "'glew'" in problem
        assert "'angle_sdl2'" in problem

    def test_the_backend_asked_for_passes(self) -> None:
        log = self.LOG.replace("glew", "angle_sdl2")
        assert gui_probe.gl_backend_problem("angle_sdl2", log) is None

    def test_nothing_asked_for_or_nothing_logged_passes(self) -> None:
        assert gui_probe.gl_backend_problem(None, self.LOG) is None
        assert gui_probe.gl_backend_problem("angle_sdl2", "no backend line yet") is None


class TestLogWaits:
    def test_a_pattern_is_matched_per_line_as_grep_does(self) -> None:
        text = "first line\nMain window shown.\nlast"
        assert gui_probe.log_has(r"^Main window shown\.$", text)
        assert not gui_probe.log_has(r"^shown", text)

    @pytest.mark.usefixtures("run_dir")
    def test_wait_sees_a_line_already_there(self) -> None:
        gui_probe.app_log().write_text("Screen 'main' entered.\n")
        assert gui_probe.wait_for("Screen 'main' entered", timeout=1)

    @pytest.mark.usefixtures("run_dir")
    def test_wait_times_out_without_the_line(self) -> None:
        gui_probe.app_log().write_text("nothing yet\n")
        assert not gui_probe.wait_for("never", timeout=0.1)

    @pytest.mark.usefixtures("run_dir")
    def test_the_wait_command_fails_on_a_timeout(self, capsys: pytest.CaptureFixture[str]) -> None:
        gui_probe.app_log().write_text("")
        assert gui_probe.main(["wait", "never", "0.1"]) == 1
        assert "timed out" in capsys.readouterr().err


class TestInputLog:
    @pytest.mark.usefixtures("run_dir")
    def test_the_harness_counts_what_the_probe_logs(self) -> None:
        """The stray-key check reads this log: a key and a typed string must count as sent."""
        sys.path.insert(0, str(GUI_TESTS_DIR))
        try:
            from barks_gui.harness import stray_key_presses  # noqa: PLC0415
        finally:
            sys.path.remove(str(GUI_TESTS_DIR))
        gui_probe.note_input("key", "Down")
        gui_probe.note_input("type", "ab")
        app_log = "\n".join(
            f"2026-09-23 12:00:00.000 | INFO | Key pressed: {code} ({name})."
            for code, name in ((274, "down"), (97, "a"), (98, "b"))
        )
        input_text = gui_probe.input_log().read_text()
        assert stray_key_presses(app_log, input_text) == 0
        assert stray_key_presses(app_log + "\nKey pressed: 13 (enter).", input_text) == 1


class TestCommands:
    def test_a_backend_command_off_windows_says_where_to_look(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        if sys.platform == "win32":
            pytest.skip("Windows has the backend")
        assert gui_probe.main(["geometry"]) == 1
        assert "gui-probe.sh" in capsys.readouterr().err

    def test_keys_go_to_the_window_only_once_it_is_in_front(self, run_dir: Path) -> None:
        backend = MagicMock()
        backend.bring_to_front.return_value = False
        (run_dir / "app.pid").write_text("1234")
        with pytest.raises(gui_probe.ProbeError, match="would not come to the front"):
            gui_probe.Probe(backend).key(["Down"])
        backend.send_key.assert_not_called()

    def test_each_key_is_logged_then_sent(
        self, run_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BARKS_PROBE_KEY_GAP", "0")
        backend = MagicMock()
        backend.bring_to_front.return_value = True
        (run_dir / "app.pid").write_text("1234")
        gui_probe.Probe(backend).key(["Down", "Return"])
        assert [c.args[0] for c in backend.send_key.call_args_list] == ["Down", "Return"]
        logged = gui_probe.input_log().read_text().splitlines()
        assert [line.split(" ", 1)[1] for line in logged] == ["key Down", "key Return"]


class TestWin32Keys:
    def test_every_key_the_suite_sends_has_a_windows_key(self) -> None:
        """The remote's six keys, and Delete, the one desktop key a test is waived to press."""
        for name in ("Escape", "Return", "Up", "Down", "Left", "Right", "Delete"):
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
            patch.object(gui_probe_win32.Win32Backend, "__init__", return_value=None),
        ):
            assert gui_probe_win32.Win32Backend().bring_to_front(222)
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
            patch.object(gui_probe_win32.Win32Backend, "__init__", return_value=None),
        ):
            backend = gui_probe_win32.Win32Backend()
            assert backend.find_window("Compleat Barks Disney Reader") == 2
            del windows[2]
            assert backend.find_window("Compleat Barks Disney Reader") is None

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows' own structure sizes")
    def test_input_is_the_size_send_input_expects(self) -> None:
        # SendInput refuses every event when cbSize is not sizeof(INPUT): 40 on 64-bit, 28 on 32.
        expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        assert ctypes.sizeof(gui_probe_win32._INPUT) == expected  # noqa: SLF001
