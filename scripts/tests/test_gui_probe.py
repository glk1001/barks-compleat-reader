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
import gui_probe_darwin
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


class TestCoverage:
    def test_the_workspace_app_runs_under_coverage_with_a_data_file_per_boot(
        self, tmp_path: Path
    ) -> None:
        data_dir = tmp_path / "cov"
        argv = gui_probe.under_coverage(["uv", "run", "python", "main.py"], data_dir)
        assert argv == [
            "uv",
            "run",
            "python",
            "-m",
            "coverage",
            "run",
            "--parallel-mode",
            f"--data-file={data_dir / '.coverage.gui'}",
            "main.py",
        ]
        assert data_dir.is_dir()

    def test_every_backend_ends_its_command_in_python_and_main_py(self) -> None:
        """What `under_coverage` relies on: the interpreter, then the script."""
        for backend in (gui_probe_win32.Win32Backend, gui_probe_darwin.DarwinBackend):
            argv = backend.workspace_app_argv(Path("/repo"))
            assert argv[-2] == "python"
            assert Path(argv[-1]).name == "main.py"

    def test_a_build_is_never_run_under_coverage(self, run_dir: Path) -> None:
        backend = MagicMock()
        env = {gui_probe.COVERAGE_ENV_VAR: str(run_dir / "cov"), "BARKS_PROBE_APP": "app.exe"}
        with (
            patch.dict(os.environ, env),
            patch.object(gui_probe, "data_dir", return_value=run_dir),
            patch.object(gui_probe.subprocess, "Popen") as popen,
        ):
            gui_probe.Probe(backend)._launch()  # noqa: SLF001
        assert popen.call_args.args[0] == ["app.exe"]


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
        gui_probe.note_input("tap", "10 20")  # a tap is a press, not a key
        app_log = "\n".join(
            f"2026-09-23 12:00:00.000 | INFO | Key pressed: {code} ({name})."
            for code, name in ((274, "down"), (97, "a"), (98, "b"))
        )
        input_text = gui_probe.input_log().read_text()
        assert stray_key_presses(app_log, input_text) == 0
        assert stray_key_presses(app_log + "\nKey pressed: 13 (enter).", input_text) == 1


class TestCommands:
    def test_a_backend_command_off_windows_and_macos_says_where_to_look(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        if sys.platform in {"win32", "darwin"}:
            pytest.skip("Windows and macOS have a backend")
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


class TestFailedLaunch:
    def test_a_launch_that_cannot_start_restores_the_profile_and_says_why(
        self, run_dir: Path
    ) -> None:
        """Popen raising (no `uv`, a moved build) must not leave the backup unapplied."""
        live = run_dir / "barks-reader.json"
        live.write_text("mine", encoding="utf-8")
        backup = run_dir / "barks-reader.json.bak"
        backend = MagicMock()
        backend.find_window.return_value = None

        def app_rewrites_the_profile(*_args: object, **_kwargs: object) -> None:
            live.write_text("half-written", encoding="utf-8")
            msg = "no such file: uv"
            raise FileNotFoundError(msg)

        with (
            patch.object(gui_probe, "_profile_backups", return_value=[(live, backup)]),
            patch.object(gui_probe.subprocess, "Popen", side_effect=app_rewrites_the_profile),
            pytest.raises(gui_probe.ProbeError, match="the app would not start: no such file"),
        ):
            gui_probe.Probe(backend).start()
        assert live.read_text(encoding="utf-8") == "mine"
        assert not backup.exists()
        assert not (run_dir / "app.pid").exists()


class TestTaps:
    def test_a_tap_clicks_at_the_window_pixel_and_is_logged_as_a_tap(self, run_dir: Path) -> None:
        backend = MagicMock()
        backend.bring_to_front.return_value = True
        backend.client_geometry.return_value = (800, 600, 100, 50)
        (run_dir / "app.pid").write_text("1234")
        with patch.object(gui_probe.time, "sleep"):
            gui_probe.Probe(backend).tap(10, 20)
        backend.click.assert_called_once_with(110, 70)
        [line] = gui_probe.input_log().read_text().splitlines()
        assert line.split(" ", 1)[1] == "tap 10 20"

    def test_a_click_presses_the_same_way_but_is_logged_as_a_click(self, run_dir: Path) -> None:
        backend = MagicMock()
        backend.bring_to_front.return_value = True
        backend.client_geometry.return_value = (800, 600, 100, 50)
        (run_dir / "app.pid").write_text("1234")
        with patch.object(gui_probe.time, "sleep"):
            gui_probe.Probe(backend).click(10, 20)
        backend.move_pointer.assert_called_once_with(110, 70)
        backend.click.assert_called_once_with(110, 70)
        [line] = gui_probe.input_log().read_text().splitlines()
        assert line.split(" ", 1)[1] == "click 10 20"

    def test_a_click_that_waited_for_its_target_says_so_in_the_log(self, run_dir: Path) -> None:
        """The macOS backend waits for the app's window under the point: the log shows it."""
        backend = MagicMock()
        backend.bring_to_front.return_value = True
        backend.client_geometry.return_value = (800, 600, 100, 50)
        (run_dir / "app.pid").write_text("1234")
        clock = iter([100.0, 112.5])
        with (
            patch.object(gui_probe.time, "sleep"),
            patch.object(gui_probe.time, "monotonic", side_effect=lambda: next(clock)),
        ):
            gui_probe.Probe(backend).tap(10, 20)
        lines = [line.split(" ", 1)[1] for line in gui_probe.input_log().read_text().splitlines()]
        assert lines == ["tap 10 20", "wait 12.5s for the app's window under the tap"]

    def test_a_tap_targets_request_is_written_whole(self, run_dir: Path) -> None:
        gui_probe.Probe.tap_targets("5")
        assert (run_dir / "tap-request").read_text(encoding="utf-8") == "5\n"
        assert not list(run_dir.glob("*.tmp"))

    def test_a_memory_census_request_is_written_whole(self, run_dir: Path) -> None:
        gui_probe.Probe.memory_census("3")
        assert (run_dir / "census-request").read_text(encoding="utf-8") == "3\n"
        assert not list(run_dir.glob("*.tmp"))

    def test_the_app_is_told_where_requests_go(self, run_dir: Path) -> None:
        env = gui_probe.app_env({})
        assert env["BARKS_READER_TAP_TARGETS_FILE"] == str(run_dir / "tap-request")
        assert env["BARKS_READER_MEMORY_CENSUS_FILE"] == str(run_dir / "census-request")

    def test_touch_mode_is_refused_here(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BARKS_PROBE_TOUCH", "1")
        backend = MagicMock()
        with pytest.raises(gui_probe.ProbeError, match="Linux only"):
            gui_probe.Probe(backend).start()
        backend.find_window.assert_not_called()


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
            patch.object(gui_probe_win32.Win32Backend, "__init__", return_value=None),
        ):
            gui_probe_win32.Win32Backend().kill_tree(4, max_secs=10)
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
