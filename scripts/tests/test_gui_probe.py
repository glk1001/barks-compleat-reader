"""Tests for the Python GUI probe: its paths, its log waits, and its contract with the suite.

The probe's input goes through a platform backend, so what can be tested
everywhere is the part every platform shares: where it looks for the config,
how it reads the app log, and that the lines it writes are the ones the GUI
harness parses. The Windows backend's structures are checked on Windows.
"""

# ruff: noqa: PLR2004  (small literal counts are the point of these tests)

# cspell:ignore glew PYTHONIOENCODING

from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import gui_probe
import gui_probe_darwin
import gui_probe_win32
import pytest
from barks_reader.core import data_pack
from script_test_helpers import write_tree

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType

GUI_TESTS_DIR = Path(__file__).resolve().parents[2] / "src" / "barks-reader" / "tests" / "gui"


@pytest.fixture
def run_dir(tmp_path: Path) -> Iterator[Path]:
    with patch.object(gui_probe, "run_dir", return_value=tmp_path):
        yield tmp_path


class TestEnvRuntime:
    def test_a_quoted_value(self, tmp_path: Path) -> None:
        env = tmp_path / ".env.runtime"
        env.write_text(
            'BARKS_READER_CONFIG_DIR="${HOME}/opt/barks-reader/config"\n', encoding="utf-8"
        )
        value = gui_probe.env_runtime_value("BARKS_READER_CONFIG_DIR", env)
        assert value == "${HOME}/opt/barks-reader/config"

    def test_an_unquoted_value_and_a_missing_one(self, tmp_path: Path) -> None:
        env = tmp_path / ".env.runtime"
        env.write_text("BARKS_READER_DATA_DIR=C:/BarksReader\nOTHER=1\n", encoding="utf-8")
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
            "use_png_images = 1\n",
            encoding="utf-8",
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


class TestStartsLight:
    """The driver starts the probe afresh for every key and wait, so it must start fast."""

    def test_it_names_the_data_pack_folder_as_the_app_does(self) -> None:
        assert gui_probe.DATA_PACK_DIR_ENV_VAR == data_pack.DATA_PACK_DIR_ENV_VAR

    def test_importing_it_pulls_in_no_loguru_or_story_catalogue(self) -> None:
        heavy = ("loguru", "barks_fantagraphics", "barks_reader.core.data_pack")
        code = (
            "import sys\n"
            f"sys.path.insert(0, {str(Path(gui_probe.__file__).parent)!r})\n"
            "import gui_probe\n"
            f"print(sorted(m for m in sys.modules if m.startswith({heavy!r})))\n"
        )
        result = subprocess.run(  # noqa: S603  (fixed argv, no shell)
            [sys.executable, "-c", code], capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "[]"


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

    @staticmethod
    def _launch_a_build(run_dir: Path, env: dict[str, str]) -> MagicMock:
        """Launch with `env` and no pack folder named but by it; return the Popen mock."""
        with (
            patch.dict(os.environ, env),
            patch.object(gui_probe, "data_dir", return_value=run_dir),
            patch.object(gui_probe.subprocess, "Popen") as popen,
        ):
            if gui_probe.DATA_PACK_DIR_ENV_VAR not in env:
                os.environ.pop(gui_probe.DATA_PACK_DIR_ENV_VAR, None)
            gui_probe.Probe(MagicMock())._launch()  # noqa: SLF001
        return popen

    def test_a_build_is_never_run_under_coverage(self, run_dir: Path) -> None:
        env = {gui_probe.COVERAGE_ENV_VAR: str(run_dir / "cov"), "BARKS_PROBE_APP": "app.exe"}

        popen = self._launch_a_build(run_dir, env)

        assert popen.call_args.args[0] == ["app.exe"]

    def test_a_build_looks_for_data_packs_only_in_an_empty_folder(self, run_dir: Path) -> None:
        """Beside a build in the repo root sit the published packs; a test once installed them."""
        popen = self._launch_a_build(run_dir, {"BARKS_PROBE_APP": "app.exe"})

        packs = Path(popen.call_args.kwargs["env"][gui_probe.DATA_PACK_DIR_ENV_VAR])
        assert packs == gui_probe.no_data_packs_dir()
        assert packs.is_dir()
        assert not any(packs.iterdir())

    def test_a_build_keeps_a_pack_folder_its_caller_names(self, run_dir: Path) -> None:
        env = {"BARKS_PROBE_APP": "app.exe", gui_probe.DATA_PACK_DIR_ENV_VAR: "/test/packs"}

        popen = self._launch_a_build(run_dir, env)

        assert popen.call_args.kwargs["env"][gui_probe.DATA_PACK_DIR_ENV_VAR] == "/test/packs"

    @pytest.mark.usefixtures("run_dir")
    def test_a_workspace_run_is_not_pointed_at_any_pack_folder(self) -> None:
        """A workspace run never looks for packs unless one is named: nothing to change."""
        with (
            patch.dict(os.environ, {}),
            patch.object(gui_probe.subprocess, "Popen") as popen,
        ):
            os.environ.pop("BARKS_PROBE_APP", None)
            os.environ.pop(gui_probe.DATA_PACK_DIR_ENV_VAR, None)
            os.environ.pop(gui_probe.COVERAGE_ENV_VAR, None)
            gui_probe.Probe(MagicMock())._launch()  # noqa: SLF001
        assert gui_probe.DATA_PACK_DIR_ENV_VAR not in popen.call_args.kwargs["env"]
        assert not gui_probe.no_data_packs_dir().exists()


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
        gui_probe.app_log().write_text("Screen 'main' entered.\n", encoding="utf-8")
        assert gui_probe.wait_for("Screen 'main' entered", timeout=1)

    @pytest.mark.usefixtures("run_dir")
    def test_wait_times_out_without_the_line(self) -> None:
        gui_probe.app_log().write_text("nothing yet\n", encoding="utf-8")
        assert not gui_probe.wait_for("never", timeout=0.1)

    @pytest.mark.usefixtures("run_dir")
    def test_the_wait_command_fails_on_a_timeout(self, capsys: pytest.CaptureFixture[str]) -> None:
        gui_probe.app_log().write_text("", encoding="utf-8")
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
        input_text = gui_probe.input_log().read_text(encoding="utf-8")
        assert stray_key_presses(app_log, input_text) == 0
        assert stray_key_presses(app_log + "\nKey pressed: 13 (enter).", input_text) == 1


def _backend_with_an_app(run_dir: Path, *, in_front: bool = True) -> MagicMock:
    """Stand in for a backend whose app is running, its 800x600 window at 100, 50."""
    backend = MagicMock()
    backend.bring_to_front.return_value = in_front
    backend.client_geometry.return_value = (800, 600, 100, 50)
    (run_dir / "app.pid").write_text("1234", encoding="utf-8")
    return backend


class TestCommands:
    @pytest.mark.skipif(
        sys.platform in {"win32", "darwin"}, reason="Windows and macOS have a backend"
    )
    def test_a_backend_command_off_windows_and_macos_says_where_to_look(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert gui_probe.main(["geometry"]) == 1
        assert "gui-probe.sh" in capsys.readouterr().err

    def test_keys_go_to_the_window_only_once_it_is_in_front(self, run_dir: Path) -> None:
        backend = _backend_with_an_app(run_dir, in_front=False)
        with pytest.raises(gui_probe.ProbeError, match="would not come to the front"):
            gui_probe.Probe(backend).key(["Down"])
        backend.send_key.assert_not_called()

    def test_each_key_is_logged_then_sent(
        self, run_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BARKS_PROBE_KEY_GAP", "0")
        backend = _backend_with_an_app(run_dir)
        gui_probe.Probe(backend).key(["Down", "Return"])
        assert [c.args[0] for c in backend.send_key.call_args_list] == ["Down", "Return"]
        logged = gui_probe.input_log().read_text(encoding="utf-8").splitlines()
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
        backend = _backend_with_an_app(run_dir)
        with patch.object(gui_probe.time, "sleep"):
            gui_probe.Probe(backend).tap(10, 20)
        backend.click.assert_called_once_with(110, 70)
        [line] = gui_probe.input_log().read_text(encoding="utf-8").splitlines()
        assert line.split(" ", 1)[1] == "tap 10 20"

    def test_a_click_presses_the_same_way_but_is_logged_as_a_click(self, run_dir: Path) -> None:
        backend = _backend_with_an_app(run_dir)
        with patch.object(gui_probe.time, "sleep"):
            gui_probe.Probe(backend).click(10, 20)
        backend.move_pointer.assert_called_once_with(110, 70)
        backend.click.assert_called_once_with(110, 70)
        [line] = gui_probe.input_log().read_text(encoding="utf-8").splitlines()
        assert line.split(" ", 1)[1] == "click 10 20"

    def test_a_click_that_waited_for_its_target_says_so_in_the_log(self, run_dir: Path) -> None:
        """The macOS backend waits for the app's window under the point: the log shows it."""
        backend = _backend_with_an_app(run_dir)
        with (
            patch.object(gui_probe.time, "sleep"),
            patch.object(gui_probe.time, "monotonic", side_effect=[100.0, 112.5]),
        ):
            gui_probe.Probe(backend).tap(10, 20)
        lines = [
            line.split(" ", 1)[1]
            for line in gui_probe.input_log().read_text(encoding="utf-8").splitlines()
        ]
        assert lines == ["tap 10 20", "wait 12.5s for the app's window under the tap"]

    def test_a_tap_targets_request_is_written_whole(self, run_dir: Path) -> None:
        gui_probe.Probe.tap_targets("5")
        assert (run_dir / "tap-request").read_text(encoding="utf-8") == "5\n"
        assert not list(run_dir.glob("*.tmp"))

    def test_a_memory_census_request_is_written_whole(self, run_dir: Path) -> None:
        gui_probe.Probe.memory_census("3")
        assert (run_dir / "census-request").read_text(encoding="utf-8") == "3\n"
        assert not list(run_dir.glob("*.tmp"))

    def test_a_frame_request_is_written_whole(self, run_dir: Path) -> None:
        gui_probe.Probe.frame_capture("final")
        assert (run_dir / "frame-request").read_text(encoding="utf-8") == "final\n"
        assert not list(run_dir.glob("*.tmp"))

    def test_the_app_is_told_where_requests_go(self, run_dir: Path) -> None:
        env = gui_probe.app_env({})
        assert env["BARKS_READER_TAP_TARGETS_FILE"] == str(run_dir / "tap-request")
        assert env["BARKS_READER_MEMORY_CENSUS_FILE"] == str(run_dir / "census-request")
        assert env["BARKS_READER_FRAME_CAPTURE_FILE"] == str(run_dir / "frame-request")

    @pytest.mark.usefixtures("run_dir")  # a start that got past the refusal writes there
    def test_touch_mode_is_refused_here(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BARKS_PROBE_TOUCH", "1")
        backend = MagicMock()
        with (
            # And would copy the machine's own profile aside: never from a test.
            patch.object(gui_probe, "_profile_backups", return_value=[]) as backups,
            patch.object(gui_probe.subprocess, "Popen") as popen,
            pytest.raises(gui_probe.ProbeError, match="Linux only"),
        ):
            gui_probe.Probe(backend).start()
        backend.find_window.assert_not_called()
        backups.assert_not_called()
        popen.assert_not_called()


def _app_line(stamp: str, message: str) -> str:
    """Return an app log line as the app's file formatter writes it."""
    return f"2026-10-04 {stamp} | INFO     | app : {message}  [barks_reader.ui.m:f:1]"


_EXITING = _app_line("16:37:22.990", "ComicBookReaderScreen: Exiting fullscreen mode.")
_ENTERED = _app_line("16:37:23.325", "Entered windowed mode on ComicBookReaderScreen.")


class TestWindowModeSettling:
    """Input on macOS waits out a window-mode switch, and a moment after it."""

    @staticmethod
    def _at(stamp: str) -> dt.datetime:
        return dt.datetime.fromisoformat(f"2026-10-04 {stamp}")

    def test_a_switch_started_and_not_ended_is_under_way(self) -> None:
        log = f"{_ENTERED}\n{_EXITING}"
        assert gui_probe.window_mode_settling(log, self._at("16:40:00"), 1.0)

    def test_an_ended_switch_settles_for_a_moment(self) -> None:
        log = f"{_EXITING}\n{_ENTERED}"
        assert gui_probe.window_mode_settling(log, self._at("16:37:23.900"), 1.0)
        assert not gui_probe.window_mode_settling(log, self._at("16:37:24.400"), 1.0)

    def test_a_log_with_no_switch_never_waits(self) -> None:
        log = _app_line("16:37:22.990", "Entering fullscreen mode finished, now closing reader.")
        assert not gui_probe.window_mode_settling(log, self._at("16:37:23"), 1.0)

    def test_entering_fullscreen_counts_as_a_switch_too(self) -> None:
        entering = _app_line("16:37:22.990", "MainScreen: Entering fullscreen mode.")
        assert gui_probe.window_mode_settling(entering, self._at("16:37:30"), 1.0)


class TestHoldForModeSwitch:
    @staticmethod
    def _probe(settle: float) -> gui_probe.Probe:
        backend = MagicMock(spec=["bring_to_front", "send_key", "mode_switch_settle_secs"])
        backend.mode_switch_settle_secs = settle
        backend.bring_to_front.return_value = True
        return gui_probe.Probe(backend)

    @pytest.mark.usefixtures("run_dir")
    def test_a_key_waits_until_the_switch_has_ended_and_says_so(self) -> None:
        gui_probe.app_log().write_text(_EXITING + "\n", encoding="utf-8")
        with (
            patch.object(gui_probe.time, "sleep"),
            patch.object(gui_probe.time, "monotonic", side_effect=[0.0, 0.0, 2.5, 2.5]),
            patch.object(gui_probe, "window_mode_settling", side_effect=[True, False]),
        ):
            self._probe(1.0)._hold_for_mode_switch("key Right")  # noqa: SLF001
        lines = [
            line.split(" ", 1)[1]
            for line in gui_probe.input_log().read_text(encoding="utf-8").splitlines()
        ]
        assert lines == ["wait 2.5s for a window-mode switch before the key Right"]

    @pytest.mark.usefixtures("run_dir")
    def test_a_switch_that_never_ends_holds_input_no_longer_than_the_limit(self) -> None:
        gui_probe.app_log().write_text(_EXITING + "\n", encoding="utf-8")
        with (
            patch.object(gui_probe.time, "sleep"),
            patch.object(gui_probe.time, "monotonic", side_effect=range(0, 100, 3)),
        ):
            self._probe(1.0)._hold_for_mode_switch("tap")  # noqa: SLF001
        assert "for a window-mode switch before the tap" in gui_probe.input_log().read_text(
            encoding="utf-8"
        )

    @pytest.mark.usefixtures("run_dir")
    def test_a_backend_that_does_not_ask_never_waits(self) -> None:
        gui_probe.app_log().write_text(_EXITING + "\n", encoding="utf-8")
        backend = MagicMock(spec=["bring_to_front"])
        with patch.object(gui_probe, "window_mode_settling") as settling:
            gui_probe.Probe(backend)._hold_for_mode_switch("key Up")  # noqa: SLF001
        settling.assert_not_called()
        assert not gui_probe.input_log().exists()

    def test_the_mac_backend_asks(self) -> None:
        assert gui_probe_darwin.DarwinBackend.mode_switch_settle_secs > 0


@pytest.fixture
def backend(run_dir: Path) -> Iterator[MagicMock]:
    """Stand in for the platform under `gui_probe.main`, with an app running in front."""
    fake = _backend_with_an_app(run_dir)
    fake.mode_switch_settle_secs = 0.0
    fake.find_window.return_value = 7
    with patch.object(gui_probe, "_backend", return_value=fake):
        yield fake


@pytest.mark.usefixtures("run_dir")
class TestTheCommandLine:
    """Each command, as the driver sends it: through `main`, over a faked platform."""

    def test_no_command_and_an_unknown_one_print_the_usage(
        self, backend: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert gui_probe.main([]) == 1
        assert gui_probe.main(["no-such-command"]) == 1

        assert capsys.readouterr().out.count(str(gui_probe.__doc__)) == 2
        backend.send_key.assert_not_called()

    def test_log_and_config_print_where_the_files_are(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert gui_probe.main(["log"]) == 0
        assert gui_probe.main(["config"]) == 0

        out = capsys.readouterr().out.splitlines()
        assert out == [str(gui_probe.app_log()), str(gui_probe.config_file())]

    def test_tail_prints_the_last_lines_twenty_unless_told(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        lines = [f"line {n}" for n in range(30)]
        gui_probe.app_log().write_text("\n".join(lines) + "\n", encoding="utf-8")

        assert gui_probe.main(["tail"]) == 0
        assert capsys.readouterr().out.splitlines() == lines[-20:]
        assert gui_probe.main(["tail", "2"]) == 0
        assert capsys.readouterr().out.splitlines() == ["line 28", "line 29"]

    def test_settle_takes_its_quiet_time_and_its_limit(self) -> None:
        with patch.object(gui_probe, "settle") as settle:
            assert gui_probe.main(["settle"]) == 0
            assert gui_probe.main(["settle", "500", "5"]) == 0

        assert [c.args for c in settle.call_args_list] == [(1000, 30), (500, 5.0)]

    def test_geometry_prints_the_window_s_drawable_area(
        self, backend: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert gui_probe.main(["geometry"]) == 0

        assert capsys.readouterr().out == "800x600+100+50\n"
        backend.client_geometry.assert_called_once_with(7)

    def test_resize_gives_the_window_s_drawable_area_the_size_asked(
        self, backend: MagicMock
    ) -> None:
        assert gui_probe.main(["resize", "900", "1100"]) == 0

        backend.resize_client.assert_called_once_with(7, 900, 1100)

    def test_a_backend_that_cannot_resize_says_so_and_fails(
        self, backend: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        backend.resize_client.side_effect = NotImplementedError("resize is not written here")

        assert gui_probe.main(["resize", "900", "1100"]) == 1
        assert "gui-probe: resize is not written here" in capsys.readouterr().err

    def test_a_shot_waits_for_the_app_to_stop_drawing_then_captures_the_window(
        self, backend: MagicMock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = tmp_path / "shot.png"
        with patch.object(gui_probe, "settle") as settle:
            assert gui_probe.main(["shot", str(out)]) == 0

        settle.assert_called_once_with(500, 5)
        backend.capture.assert_called_once_with((800, 600, 100, 50), out)
        assert capsys.readouterr().out == f"{out}\n"

    @pytest.mark.parametrize(
        ("command", "problem", "says"),
        [
            pytest.param("geometry", "no pid", "not started - run 'gui_probe.py start' first"),
            pytest.param("geometry", "no window", "app window (Compleat Barks Disney Reader) not"),
            pytest.param(
                "type", "not in front", "the app window would not come to the front, so input"
            ),
        ],
    )
    def test_a_command_with_no_app_to_reach_says_why(
        self,
        backend: MagicMock,
        capsys: pytest.CaptureFixture[str],
        command: str,
        problem: str,
        says: str,
    ) -> None:
        match problem:
            case "no pid":
                (gui_probe.run_dir() / "app.pid").unlink()
            case "no window":
                backend.find_window.return_value = None
            case _:
                backend.bring_to_front.return_value = False

        assert gui_probe.main([command, "x"]) == 1

        assert f"gui-probe: {says}" in capsys.readouterr().err
        backend.send_char.assert_not_called()

    def test_typing_sends_each_character_and_is_logged_as_one_line(
        self, backend: MagicMock
    ) -> None:
        assert gui_probe.main(["type", "duck"]) == 0

        assert [c.args[0] for c in backend.send_char.call_args_list] == list("duck")
        (line,) = gui_probe.input_log().read_text(encoding="utf-8").splitlines()
        assert line.split(" ", 1)[1] == "type duck"

    @pytest.mark.parametrize(
        ("argv", "method", "args"),
        [
            (["click", "40", "60"], "click", (40, 60)),
            (["tap", "10", "20"], "tap", (10, 20)),
            (["tap-targets", "7"], "tap_targets", ("7",)),
            (["memory-census", "8"], "memory_census", ("8",)),
            (["frame-capture", "9"], "frame_capture", ("9",)),
            (["key", "Down", "Return"], "key", (["Down", "Return"],)),
            (["start", "100,50"], "start", ()),
        ],
    )
    @pytest.mark.usefixtures("backend")
    def test_each_command_reaches_its_own_move(
        self, argv: list[str], method: str, args: tuple[object, ...]
    ) -> None:
        with patch.object(gui_probe.Probe, method) as move:
            assert gui_probe.main(argv) == 0

        move.assert_called_once_with(*args)

    def test_the_x_server_command_is_kept_and_says_there_is_none(
        self, backend: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        backend.process_alive.return_value = True
        assert gui_probe.main(["stop-xserver"]) == 1
        assert "the app is still running - stop it first" in capsys.readouterr().err

        backend.process_alive.return_value = False
        assert gui_probe.main(["stop-xserver"]) == 0
        assert capsys.readouterr().out == "gui-probe: no X server on this platform\n"

    def test_doctor_lists_every_check_and_fails_on_a_fail(
        self, backend: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        backend.doctor_checks.return_value = [("OK", "a screen")]
        with patch.object(gui_probe, "repo_checks", return_value=[("WARN", "no profile")]):
            assert gui_probe.main(["doctor"]) == 0
        assert capsys.readouterr().out == "  OK   a screen\n  WARN no profile\n\ndoctor: ready.\n"

        with patch.object(gui_probe, "repo_checks", return_value=[("FAIL", "uv not on PATH")]):
            assert gui_probe.main(["doctor"]) == 1
        assert "doctor: NOT ready - fix the FAIL items above." in capsys.readouterr().out

    @pytest.mark.parametrize(
        ("platform", "module", "name"),
        [
            ("win32", gui_probe_win32, "Win32Backend"),
            ("darwin", gui_probe_darwin, "DarwinBackend"),
        ],
    )
    def test_each_platform_gets_its_own_backend(
        self, platform: str, module: ModuleType, name: str
    ) -> None:
        with patch.object(gui_probe.sys, "platform", platform), patch.object(module, name) as made:
            assert gui_probe._backend() is made.return_value  # noqa: SLF001


class TestStartAndStop:
    @pytest.fixture
    def profile(self, run_dir: Path) -> Iterator[tuple[Path, Path]]:
        """Make a live profile file; yield it and where a start backs it up."""
        live, backup = run_dir / "barks-reader.json", run_dir / "barks-reader.json.bak"
        live.write_text("the user's", encoding="utf-8")
        with patch.object(gui_probe, "_profile_backups", return_value=[(live, backup)]):
            yield live, backup

    @staticmethod
    def _start(backend: MagicMock, log_text: str, *, ready: bool = True) -> None:
        """Start with the launch faked: the app has logged `log_text` by the time it is ready."""

        def launch(_probe: gui_probe.Probe) -> None:
            gui_probe.app_log().write_text(log_text, encoding="utf-8")
            (gui_probe.run_dir() / "app.pid").write_text("1234", encoding="utf-8")

        backend.process_alive.return_value = False
        with (
            patch.object(gui_probe.Probe, "_launch", launch),
            patch.object(gui_probe, "wait_for", return_value=ready),
            patch.object(gui_probe, "settle"),
            patch.object(gui_probe.time, "sleep"),
        ):
            gui_probe.Probe(backend).start()

    @pytest.fixture
    def fresh(self, run_dir: Path, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        """Make a backend with no app running and no window of the app's on screen yet."""
        # No backend asked for, whatever the machine running the tests asks of its own app.
        monkeypatch.delenv("KIVY_GL_BACKEND", raising=False)
        fake = MagicMock()
        fake.client_geometry.return_value = (800, 600, 100, 50)
        fake.find_window.side_effect = [None, None, 7]  # the refusal's look, then two waits
        (run_dir / "frame-old.png").write_bytes(b"png")
        (run_dir / "tap-request").write_text("stale", encoding="utf-8")
        return fake

    def test_a_start_clears_the_last_run_backs_up_the_profile_and_parks_the_pointer(
        self,
        fresh: MagicMock,
        run_dir: Path,
        profile: tuple[Path, Path],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._start(fresh, "GL: Backend used <sdl2>\n")

        _live, backup = profile
        assert backup.read_text(encoding="utf-8") == "the user's"
        assert not (run_dir / "frame-old.png").exists()
        assert not (run_dir / "tap-request").exists()
        assert gui_probe.input_log().read_text(encoding="utf-8") == ""
        fresh.bring_to_front.assert_called_once_with(7)
        fresh.move_pointer.assert_called_once_with(105, 350)  # far left, mid-height
        assert f"ready (graphics backend: sdl2). Log: {gui_probe.app_log()}" in (
            capsys.readouterr().out
        )

    def test_a_throwaway_profile_is_not_backed_up(
        self, fresh: MagicMock, profile: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BARKS_PROBE_NO_RESTORE", "1")

        self._start(fresh, "")

        assert not profile[1].exists()

    @pytest.mark.parametrize(
        ("fails", "says"),
        [
            pytest.param("ready", "app never became ready; see ", id="never ready"),
            pytest.param("gl", "not the 'angle_sdl2' asked for", id="the wrong graphics"),
            pytest.param("window", "logged its ready line but no Compleat Barks", id="no window"),
            pytest.param("front", "would not come to the front (is the screen", id="not in front"),
        ],
    )
    def test_a_start_that_fails_stops_the_app_and_restores_the_profile(
        self,
        fresh: MagicMock,
        profile: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
        fails: str,
        says: str,
    ) -> None:
        live, backup = profile
        log_text = ""
        match fails:
            case "gl":
                monkeypatch.setenv("KIVY_GL_BACKEND", "angle_sdl2")
                log_text = "GL: Backend used <sdl2>\n"
            case "window":
                fresh.find_window.side_effect = None
                fresh.find_window.return_value = None
                monkeypatch.setattr(gui_probe, "WINDOW_WAIT_SECS", 0.0)
            case "front":
                fresh.bring_to_front.return_value = False

        def app_rewrites_the_profile(*_args: object, **_kwargs: object) -> None:
            live.write_text("the app's", encoding="utf-8")

        fresh.kill_tree.side_effect = app_rewrites_the_profile
        with pytest.raises(gui_probe.ProbeError, match=re.escape(says)):
            self._start(fresh, log_text, ready=fails != "ready")

        fresh.kill_tree.assert_called_once_with(1234, max_secs=10)
        assert live.read_text(encoding="utf-8") == "the user's"
        assert not backup.exists()
        assert not (gui_probe.run_dir() / "app.pid").exists()

    @pytest.mark.parametrize(
        ("running", "window", "says"),
        [
            (True, None, "already running (stop it first)"),
            (False, 7, "window is already open - close it first, or keys would go to it"),
        ],
    )
    def test_a_start_is_refused_while_an_app_or_its_window_is_there(
        self, run_dir: Path, running: bool, window: int | None, says: str
    ) -> None:
        fake = _backend_with_an_app(run_dir)
        fake.process_alive.return_value = running
        fake.find_window.return_value = window

        with (
            patch.object(gui_probe.Probe, "_launch") as launch,
            pytest.raises(gui_probe.ProbeError, match=re.escape(says)),
        ):
            gui_probe.Probe(fake).start()

        launch.assert_not_called()

    def test_a_stop_ends_the_app_and_puts_the_profile_back(
        self, backend: MagicMock, profile: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        live, backup = profile
        backup.write_text("the user's", encoding="utf-8")
        live.write_text("the app's", encoding="utf-8")

        assert gui_probe.main(["stop"]) == 0

        backend.kill_tree.assert_called_once_with(1234, max_secs=10)
        assert live.read_text(encoding="utf-8") == "the user's"
        assert not backup.exists()
        assert capsys.readouterr().out == f"gui-probe: restored {live}\ngui-probe: stopped\n"

    def test_a_stop_with_nothing_started_only_says_so(
        self, run_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake = MagicMock()
        with patch.object(gui_probe, "_profile_backups", return_value=[]):
            gui_probe.Probe(fake).stop()

        fake.kill_tree.assert_not_called()
        assert not any(run_dir.iterdir())
        assert capsys.readouterr().out == "gui-probe: stopped\n"


@pytest.mark.usefixtures("run_dir")
class TestSettle:
    """The app has stopped drawing once its log has stopped growing."""

    @staticmethod
    def _settle(growth: list[str], quiet_ms: int = 500) -> int:
        """Settle while the log grows by each of `growth` in turn; return the polls slept."""
        pending = list(growth)

        def app_keeps_drawing(_secs: float) -> None:
            if pending:
                with gui_probe.app_log().open("a", encoding="utf-8") as log:
                    log.write(pending.pop(0))

        with patch.object(gui_probe.time, "sleep", side_effect=app_keeps_drawing) as sleep:
            gui_probe.settle(quiet_ms, max_secs=30)
        return sleep.call_count

    def test_it_returns_once_the_log_has_been_still_for_the_quiet_time(self) -> None:
        gui_probe.app_log().write_text("booting\n", encoding="utf-8")

        # Two polls see it grow; two more, 250 ms each, see it still.
        assert self._settle(["drew a page\n", "drew another\n"]) == 4

    def test_a_log_that_is_not_there_is_a_still_one(self) -> None:
        assert self._settle([]) == 2

    def test_a_log_that_never_stops_growing_is_given_up_on_at_the_limit(self) -> None:
        with (
            patch.object(gui_probe.time, "monotonic", side_effect=[0.0, 1.0, 2.0, 31.0]),
            patch.object(gui_probe.time, "sleep") as sleep,
            patch.object(gui_probe, "app_log") as app_log,
        ):
            app_log.return_value.stat.side_effect = [MagicMock(st_size=n) for n in (10, 20)]
            gui_probe.settle(500, max_secs=30)

        assert sleep.call_count == 2


class TestRepoChecks:
    """The doctor's checks that are the same on every platform."""

    @staticmethod
    def _checks(repo: Path, *, uv: str | None = "/usr/bin/uv") -> list[tuple[str, str]]:
        with (
            patch.object(gui_probe, "REPO_ROOT", repo),
            patch.object(gui_probe, "config_dir", return_value=repo / "config"),
            patch.object(gui_probe.shutil, "which", return_value=uv),
            patch.object(gui_probe, "dir_setting_checks", return_value=[("OK", "its folders")]),
        ):
            return gui_probe.repo_checks()

    def test_a_machine_with_everything(self, tmp_path: Path) -> None:
        env = "BARKS_ZIPS_KEY=k\nBARKS_READER_CONFIG_DIR=c\nBARKS_READER_DATA_DIR=d\n"
        ini = tmp_path / "config" / "barks-reader.ini"
        write_tree(tmp_path, {".env.runtime": env, ".venv/bin/python": "", str(ini): "[ui]\n"})

        assert self._checks(tmp_path) == [
            ("OK", "uv"),
            ("OK", ".env.runtime"),
            ("OK", "BARKS_ZIPS_KEY"),
            ("OK", "BARKS_READER_CONFIG_DIR"),
            ("OK", "BARKS_READER_DATA_DIR"),
            ("OK", ".venv"),
            ("OK", str(ini)),
            ("OK", "its folders"),
        ]

    def test_a_fresh_clone_fails_on_each_thing_it_lacks(self, tmp_path: Path) -> None:
        checks = self._checks(tmp_path, uv=None)

        assert [status for status, _ in checks] == ["FAIL", "FAIL", "FAIL", "WARN"]
        assert checks[0] == ("FAIL", "uv not on PATH")
        assert checks[1][1].startswith(".env.runtime - gitignored (it holds BARKS_ZIPS_KEY)")
        assert checks[2] == ("FAIL", ".venv - run 'uv sync'")
        assert "the GUI suite skips every test" in checks[3][1]

    def test_a_variable_missing_from_env_runtime_is_named(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {".env.runtime": "BARKS_ZIPS_KEY=k\nBARKS_READER_DATA_DIR=\n"})

        failed = [text for status, text in self._checks(tmp_path) if status == "FAIL"]

        assert "BARKS_READER_CONFIG_DIR not set in .env.runtime" in failed
        assert "BARKS_READER_DATA_DIR not set in .env.runtime" in failed
        assert not any("BARKS_ZIPS_KEY" in text for text in failed)
