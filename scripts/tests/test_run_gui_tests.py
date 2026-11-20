# ruff: noqa: SLF001
"""Tests for the Windows and macOS GUI test runner: its flags, environment and coverage merge."""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import run_gui_tests

if TYPE_CHECKING:
    import argparse
    from collections.abc import Iterator
    from pathlib import Path


class TestMergeCoverage:
    """Each boot's data file is merged into .coverage.gui, as run_gui_tests.sh does."""

    def _merge(self, env: dict[str, str]) -> list[list[str]]:
        with patch.object(run_gui_tests.subprocess, "run") as run:
            run.return_value.returncode = 0
            run_gui_tests.merge_coverage(env)
        return [c.args[0] for c in run.call_args_list]

    def test_the_boots_are_merged(self, tmp_path: Path) -> None:
        (tmp_path / ".coverage.gui.host.123.456").write_bytes(b"")
        (cmd,) = self._merge({"BARKS_PROBE_COVERAGE": str(tmp_path)})
        assert cmd[1:5] == ["-m", "coverage", "combine", "--append"]
        assert f"--data-file={tmp_path / '.coverage.gui'}" in cmd
        assert cmd[-1] == str(tmp_path)

    def test_nothing_without_the_folder(self) -> None:
        assert self._merge({}) == []

    def test_nothing_when_no_boot_measured_any(self, tmp_path: Path) -> None:
        assert self._merge({"BARKS_PROBE_COVERAGE": str(tmp_path)}) == []

    def test_nothing_for_a_built_executable(self, tmp_path: Path) -> None:
        (tmp_path / ".coverage.gui.host.123.456").write_bytes(b"")
        env = {"BARKS_PROBE_COVERAGE": str(tmp_path), "BARKS_PROBE_APP": "reader.exe"}
        assert self._merge(env) == []


def _options(*argv: str) -> argparse.Namespace:
    options, _rest = run_gui_tests._parse(list(argv))
    return options


def _env(tmp_path: Path, *argv: str) -> dict[str, str]:
    return run_gui_tests._run_env(
        _options(*argv), "20261120-010203", tmp_path / "t" / "timings.jsonl"
    )


_USAGE_ERROR = 2
# What a flag may set: none of it comes from the machine's own environment in these tests.
_SET_BY_FLAGS = (
    "BARKS_GUI_INI",
    "KIVY_GL_BACKEND",
    "BARKS_PROBE_APP",
    "BARKS_GUI_KEEP_LOGS",
    "BARKS_GUI_NO_BUDGETS",
    "BARKS_GUI_TIMINGS",
)


@pytest.fixture
def _no_flag_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _SET_BY_FLAGS:
        monkeypatch.setenv(name, "-")
        monkeypatch.delenv(name)


class TestParse:
    def test_what_is_not_the_runner_s_goes_to_pytest(self) -> None:
        options, rest = run_gui_tests._parse(["--quiet", "-k", "history", "--ini", "a=1", "-x"])

        assert rest == ["-k", "history", "-x"]
        assert (options.quiet, options.ini) == (True, ["a=1"])

    def test_no_flag_is_on_unless_given(self) -> None:
        options = _options()

        assert vars(options) == {
            "quiet": False,
            "soak": False,
            "notes_fit": False,
            "calibrate": False,
            "keep_logs": False,
            "app": None,
            "angle": False,
            "ini": [],
        }


@pytest.mark.usefixtures("_no_flag_variables")
class TestRunEnv:
    """Each flag reaches the suite and the app as the variable they read."""

    def test_a_plain_run_sets_one_worker_and_the_stamp_and_nothing_a_flag_sets(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        env = _env(tmp_path)

        assert env["BARKS_GUI_WORKER_COUNT"] == "1"
        assert env["BARKS_GUI_RUN_STAMP"] == "20261120-010203"
        assert env["PYTHONUNBUFFERED"] == "1"  # cspell:ignore PYTHONUNBUFFERED
        assert env["PATH"] == os.environ["PATH"]  # the rest is the caller's
        assert [name for name in _SET_BY_FLAGS if name in env] == []
        assert capsys.readouterr().out == ""
        assert not (tmp_path / "t").exists()

    def test_the_settings_are_joined_in_the_order_given(self, tmp_path: Path) -> None:
        env = _env(tmp_path, "--ini", "goto_page=1", "--ini", "color_theme=dark")

        assert env["BARKS_GUI_INI"] == "goto_page=1;color_theme=dark"

    def test_angle_is_the_backend_kivy_reads(self, tmp_path: Path) -> None:
        assert _env(tmp_path, "--angle")["KIVY_GL_BACKEND"] == "angle_sdl2"

    def test_a_built_executable_is_given_by_its_whole_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        env = _env(tmp_path, "--app", "reader.exe")

        assert env["BARKS_PROBE_APP"] == str((tmp_path / "reader.exe").resolve())

    def test_keep_logs(self, tmp_path: Path) -> None:
        assert _env(tmp_path, "--keep-logs")["BARKS_GUI_KEEP_LOGS"] == "1"

    def test_a_calibration_turns_the_budgets_off_and_records_the_timings(
        self, tmp_path: Path
    ) -> None:
        env = _env(tmp_path, "--calibrate")

        assert env["BARKS_GUI_NO_BUDGETS"] == "1"
        assert env["BARKS_GUI_TIMINGS"] == str(tmp_path / "t" / "timings.jsonl")
        assert (tmp_path / "t").is_dir()  # made now: the tests append to a file in it

    @pytest.mark.parametrize(
        ("flag", "says"),
        [
            (["--ini", "a=1"], "settings for this run: a=1"),
            (["--angle"], "drawing through ANGLE"),
            (["--keep-logs"], "keeping every test's artifacts"),
            (["--calibrate"], "calibrating the timing budgets"),
        ],
    )
    def test_each_flag_that_changes_the_run_says_so(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], flag: list[str], says: str
    ) -> None:
        _env(tmp_path, *flag)

        assert f"run_gui_tests: {says}" in capsys.readouterr().out


class TestIsSummary:
    @pytest.mark.parametrize(
        "line",
        [
            "FAILED src/barks-reader/tests/gui/test_history.py::test_delete - AssertionError",
            "ERROR src/barks-reader/tests/gui/test_wiki.py::test_search",
            "E   AssertionError: the canned history moved",
            "===== 3 failed, 183 passed in 600.00s =====",
            "186 passed in 605.31s (0:10:05)",
            "1 skipped, 2 error in 3.00s",
        ],
    )
    def test_quiet_keeps_failures_and_the_totals(self, line: str) -> None:
        assert run_gui_tests._is_summary(line)

    @pytest.mark.parametrize(
        "line",
        [
            "src/barks-reader/tests/gui/test_history.py ....",
            "    d.key_then_wait(marker, 'Return')",
            "",
        ],
    )
    def test_and_drops_the_rest(self, line: str) -> None:
        assert not run_gui_tests._is_summary(line)


class TestRunPytest:
    """Against a real child: the log is written as the lines come, whatever is printed."""

    _STATUS = 3
    _CHILD = f"print('a.py ....'); print('FAILED a.py::test_b - boom'); raise SystemExit({_STATUS})"

    def _run(self, tmp_path: Path, *, quiet: bool) -> tuple[int, str]:
        log = tmp_path / "run" / "pytest.log"
        # The child takes pytest's flags as arguments it never reads.
        status = run_gui_tests._run_pytest(
            [sys.executable, "-c", self._CHILD], dict(os.environ), quiet=quiet, log=log
        )
        return status, log.read_text(encoding="utf-8")

    def test_the_status_is_the_child_s_and_the_log_has_every_line(self, tmp_path: Path) -> None:
        status, logged = self._run(tmp_path, quiet=False)

        assert status == self._STATUS
        assert logged == "a.py ....\nFAILED a.py::test_b - boom\n"

    def test_a_full_run_prints_every_line_and_asks_pytest_for_durations(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._run(tmp_path, quiet=False)

        out = capsys.readouterr().out
        assert out.splitlines()[0].endswith("-v --durations=0")
        assert out.splitlines()[1:] == ["a.py ....", "FAILED a.py::test_b - boom"]

    def test_a_quiet_run_prints_only_the_failure_but_logs_it_all(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _status, logged = self._run(tmp_path, quiet=True)

        out = capsys.readouterr().out
        assert out.splitlines()[0].endswith("-q --tb=short")
        assert out.splitlines()[1:] == ["FAILED a.py::test_b - boom"]
        assert "a.py ...." in logged


@pytest.mark.usefixtures("_no_flag_variables")
class TestMain:
    @pytest.fixture
    def run(self, tmp_path: Path) -> Iterator[SimpleNamespace]:
        """Fake main's children: the doctor, pytest, the merge and the calibration."""
        with (
            patch.object(run_gui_tests, "REPO_ROOT", tmp_path),
            patch.object(run_gui_tests.subprocess, "run") as child,
            patch.object(run_gui_tests, "_run_pytest", return_value=0) as run_pytest,
            patch.object(run_gui_tests, "merge_coverage") as merge,
        ):
            child.return_value.returncode = 0
            yield SimpleNamespace(child=child, pytest=run_pytest, merge=merge)

    @staticmethod
    def _selected(run: SimpleNamespace) -> str:
        cmd = run.pytest.call_args.args[0]
        return cmd[cmd.index("-m", 2) + 1]  # past "python -m pytest"

    def test_a_passing_run_exits_0_having_merged_the_coverage(self, run: SimpleNamespace) -> None:
        assert run_gui_tests.main(["-k", "history"]) == 0

        cmd = run.pytest.call_args.args[0]
        assert cmd[:4] == [sys.executable, "-m", "pytest", run_gui_tests.GUI_TESTS]
        assert cmd[-2:] == ["-k", "history"]
        assert run.pytest.call_args.kwargs["quiet"] is False
        run.merge.assert_called_once()
        assert run.child.call_count == 1  # the doctor alone: nothing was calibrated

    @pytest.mark.parametrize(
        ("flags", "marker"),
        [
            ([], "not soak and not notes_fit"),
            (["--soak"], "soak"),
            (["--notes-fit"], "notes_fit"),
        ],
    )
    def test_the_walks_are_run_only_when_asked_for(
        self, run: SimpleNamespace, flags: list[str], marker: str
    ) -> None:
        run_gui_tests.main(flags)

        assert self._selected(run) == marker

    def test_a_failing_run_exits_with_pytest_s_status_and_says_where_to_look(
        self, run: SimpleNamespace, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run.pytest.return_value = 1

        assert run_gui_tests.main(["--quiet"]) == 1

        assert run.pytest.call_args.kwargs["quiet"] is True
        assert "pytest's output and the artifacts are in" in capsys.readouterr().out
        run.merge.assert_called_once()  # what did run was still measured

    def test_a_machine_that_is_not_ready_runs_nothing(
        self, run: SimpleNamespace, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run.child.return_value.returncode = 1
        run.child.return_value.stdout = "FAIL: no display"

        assert run_gui_tests.main([]) == 1

        run.pytest.assert_not_called()
        err = capsys.readouterr().err
        assert "FAIL: no display" in err
        assert "this machine is not ready" in err

    def test_an_app_that_is_not_a_file_is_refused_before_anything_runs(
        self, run: SimpleNamespace, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert run_gui_tests.main(["--app", str(tmp_path / "absent.exe")]) == _USAGE_ERROR

        run.child.assert_not_called()
        assert "not an executable" in capsys.readouterr().err

    def test_a_calibration_that_passed_records_its_budgets(self, run: SimpleNamespace) -> None:
        failed = 4
        run.child.side_effect = [MagicMock(returncode=0), MagicMock(returncode=failed)]

        assert run_gui_tests.main(["--calibrate"]) == failed  # the calibration's own status

        calibrate = run.child.call_args_list[1]
        assert calibrate.args[0][1:4] == ["-m", "barks_gui.timings", "calibrate"]
        assert calibrate.args[0][-1] == "1"  # one worker
        assert str(run_gui_tests.PROBE.parent) in calibrate.kwargs["env"]["PYTHONPATH"]

    def test_a_calibration_that_failed_records_nothing(self, run: SimpleNamespace) -> None:
        """A stuck app's durations would set the baseline wrong."""
        run.pytest.return_value = 1

        assert run_gui_tests.main(["--calibrate"]) == 1

        assert run.child.call_count == 1
