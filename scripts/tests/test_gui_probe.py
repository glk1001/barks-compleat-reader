"""Tests for the Python GUI probe: its paths, its log waits, and its contract with the suite.

The probe's input goes through a platform backend, so what can be tested
everywhere is the part every platform shares: where it looks for the config,
how it reads the app log, and that the lines it writes are the ones the GUI
harness parses. The Windows backend's structures are checked on Windows.
"""

# ruff: noqa: PLR2004  (small literal counts are the point of these tests)

from __future__ import annotations

import ctypes
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

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows' own structure sizes")
    def test_input_is_the_size_send_input_expects(self) -> None:
        # SendInput refuses every event when cbSize is not sizeof(INPUT): 40 on 64-bit, 28 on 32.
        expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        assert ctypes.sizeof(gui_probe_win32._INPUT) == expected  # noqa: SLF001
