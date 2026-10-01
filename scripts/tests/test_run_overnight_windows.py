"""Tests for the Windows overnight runner: its stage table, its choices and its summary.

The stages themselves run real tools on the Windows laptop; what is tested here,
on every platform, is what decides which of them run, what each result is
called, and that summary.txt reads as the Linux run's does.
"""

# ruff: noqa: PLR2004  (small literal counts are the point of these tests)

# cspell:ignore PYTHONIOENCODING

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import run_overnight_windows as rw

if TYPE_CHECKING:
    from collections.abc import Iterator

LINUX_RUNNER = Path(rw.__file__).with_name("run_overnight.sh")


class TestStageTable:
    def test_every_stage_is_documented_in_order(self) -> None:
        listed = re.findall(r"^  ([a-z-]+) ", rw.list_text(), re.MULTILINE)
        assert listed == list(rw.STAGES)

    def test_the_gui_stages_are_stages(self) -> None:
        assert rw.GUI_STAGES.issubset(rw.STAGES)

    def test_every_stage_has_a_method(self) -> None:
        for name in rw.STAGES:
            assert callable(getattr(rw.Run, "stage_" + name.replace("-", "_")))

    def test_update_comes_first(self) -> None:
        # Everything after it tests the code it pulled.
        assert rw.STAGES[0] == "update"

    def test_the_statuses_are_the_linux_runs(self) -> None:
        text = LINUX_RUNNER.read_text(encoding="utf-8")
        assert f"SKIPPED={rw.SKIPPED}" in text
        assert f"WARNED={rw.WARNED}" in text


class TestSelectStages:
    def test_all_by_default(self) -> None:
        assert rw.select_stages([], []) == list(rw.STAGES)

    def test_only_keeps_the_run_order(self) -> None:
        assert rw.select_stages(["soak", "update"], []) == ["update", "soak"]

    def test_skip(self) -> None:
        chosen = rw.select_stages([], ["fetch-build", "built-app"])
        assert chosen == ["update", "pytest", "validate", "gui", "soak"]

    def test_an_unknown_name(self) -> None:
        with pytest.raises(ValueError, match="no stage called nope"):
            rw.select_stages([], ["nope"])

    def test_names_from_an_option(self) -> None:
        assert rw.parse_names("gui,soak,") == ["gui", "soak"]
        assert rw.parse_names("") == []


class TestResultName:
    @pytest.mark.parametrize(
        ("status", "word"),
        [(0, "passed"), (1, "FAILED"), (2, "FAILED"), (3, "skipped"), (4, "WARNED")],
    )
    def test_statuses(self, status: int, word: str) -> None:
        assert rw.result_name(status) == word

    def test_stopped_outranks_the_status(self) -> None:
        assert rw.result_name(0, stopped=True) == "stopped"


class TestSoakSeeds:
    def test_one_seed_from_the_day_of_the_year(self) -> None:
        # The first of the Linux run's three: day * 10 + 1.
        assert rw.soak_seeds({}, dt.date(2026, 2, 1)) == ["321"]

    def test_the_env_overrides(self) -> None:
        env = {"BARKS_OVERNIGHT_SOAK_SEEDS": "7 8"}
        assert rw.soak_seeds(env, dt.date(2026, 1, 1)) == ["7", "8"]

    def test_an_empty_override_is_the_default(self) -> None:
        env = {"BARKS_OVERNIGHT_SOAK_SEEDS": " "}
        assert rw.soak_seeds(env, dt.date(2026, 1, 1)) == ["11"]


class TestSummary:
    def test_the_linux_format(self) -> None:
        results = [
            rw.StageResult("update", "passed", 61),
            rw.StageResult("fetch-build", "FAILED", 5),
            rw.StageResult("validate", "skipped", 0),
        ]
        stamp = "20260930-020000"
        state = "finished in 0h45m"
        text = rw.summary_text(stamp, "abc1234", state, results, f"build/overnight/{stamp}")
        # Line for line what run_overnight.sh's printf '%-14s %-8s %4dm%02ds' writes.
        assert text == (
            "==== overnight run, 20260930-020000 (abc1234): finished in 0h45m ====\n"
            "update         passed      1m01s\n"
            "fetch-build    FAILED      0m05s\n"
            "validate       skipped     0m00s\n"
            "logs: build/overnight/20260930-020000/\n"
        )

    def test_the_linux_runner_writes_the_same_line(self) -> None:
        # If the Linux format moves, this one must move with it.
        text = LINUX_RUNNER.read_text(encoding="utf-8")
        assert "printf '%-14s %-8s %4dm%02ds\\n'" in text
        assert (
            'echo "==== overnight run, ${stamp} ($(git rev-parse --short HEAD)): $1 ===="' in text
        )

    @pytest.mark.parametrize(
        ("secs", "text"), [(0, "0h00m"), (59, "0h00m"), (61 * 60, "1h01m"), (10 * 3600, "10h00m")]
    )
    def test_elapsed(self, secs: int, text: str) -> None:
        assert rw.elapsed(secs) == text


class TestFetchBuildChoices:
    def test_the_push_run_is_preferred(self) -> None:
        runs = [
            {"databaseId": 2, "event": "pull_request"},
            {"databaseId": 1, "event": "push"},
        ]
        assert rw.pick_build_run(runs) == runs[1]

    def test_else_the_newest(self) -> None:
        runs = [{"databaseId": 2, "event": "workflow_dispatch"}, {"databaseId": 1, "event": "x"}]
        assert rw.pick_build_run(runs) == runs[0]

    def test_no_runs(self) -> None:
        assert rw.pick_build_run([]) is None

    def test_the_windows_job(self) -> None:
        jobs = [{"name": "Build (ubuntu-latest)"}, {"name": "Build (windows-latest)"}]
        assert rw.windows_job(jobs) == jobs[1]
        assert rw.windows_job(jobs[:1]) is None


class TestPrebuiltDir:
    def test_the_ini_setting(self, tmp_path: Path) -> None:
        ini = tmp_path / "barks-reader.ini"
        ini.write_text("[x]\nuse_prebuilt_comics = 0\nprebuilt_dir = D:/Comics\n", encoding="utf-8")
        assert rw.prebuilt_dir(ini) == Path("D:/Comics")

    def test_home_is_expanded(self, tmp_path: Path) -> None:
        ini = tmp_path / "barks-reader.ini"
        ini.write_text("prebuilt_dir = ${HOME}/Comics\n", encoding="utf-8")
        assert rw.prebuilt_dir(ini) == Path(f"{Path.home()}/Comics")

    def test_the_readers_default_without_one(self, tmp_path: Path) -> None:
        expected = Path(f"{Path.home()}/Books/Carl Barks/The Comics/Chronological")
        assert rw.prebuilt_dir(tmp_path / "absent.ini") == expected


class TestChildEnv:
    def test_plain_text_and_utf8(self) -> None:
        env = rw.child_env({"TERM": "xterm", "PATH": "p"}, EXTRA="1")
        assert "TERM" not in env
        assert env["LOGURU_COLORIZE"] == "0"
        assert env["PYTHONUTF8"] == "1"
        assert env["PYTHONIOENCODING"] == "utf-8"
        assert env["PATH"] == "p"
        assert env["EXTRA"] == "1"


# ----------------------------------------------------------------- the run --


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[Path]:
    with (
        patch.object(rw, "REPO_ROOT", tmp_path),
        patch.object(rw, "short_commit", return_value="abc1234"),
        patch.object(rw, "say"),
        # Plenty free, whatever this machine has: the memory tests set their own.
        patch.object(rw, "available_mb", return_value=64 * 1024),
    ):
        yield tmp_path


def _summary(repo: Path) -> str:
    (summary,) = repo.glob("build/overnight/*/summary.txt")
    return summary.read_text(encoding="utf-8")


def _results(repo: Path) -> dict[str, str]:
    lines = _summary(repo).splitlines()[1:-1]
    return {line.split()[0]: line.split()[1] for line in lines}


class TestRun:
    def test_a_failing_stage_does_not_stop_the_others(self, repo: Path) -> None:
        statuses = {"pytest": 1, "validate": rw.SKIPPED}
        run = rw.Run(["update", "pytest", "validate"], None)
        with patch.object(
            rw.Run, "run_stage", side_effect=lambda name, _log: statuses.get(name, 0)
        ):
            assert run.run() == 1
        assert _results(repo) == {"update": "passed", "pytest": "FAILED", "validate": "skipped"}
        assert "finished in" in _summary(repo).splitlines()[0]

    def test_a_failed_update_stops_the_run(self, repo: Path) -> None:
        run = rw.Run(["update", "pytest"], None)
        stage = MagicMock(return_value=1)
        with patch.object(rw.Run, "run_stage", stage):
            assert run.run() == 1
        assert [c.args[0] for c in stage.call_args_list] == ["update"]
        assert _results(repo) == {"update": "FAILED"}
        assert "stopped after a failed update" in _summary(repo)

    def test_skips_and_warnings_pass_the_run(self, repo: Path) -> None:
        statuses = {"gui": rw.WARNED, "validate": rw.SKIPPED}
        run = rw.Run(["gui", "validate"], None)
        with patch.object(rw.Run, "run_stage", side_effect=lambda name, _log: statuses[name]):
            assert run.run() == 0
        assert _results(repo) == {"gui": "WARNED", "validate": "skipped"}

    def test_a_crashing_stage_is_its_failure_alone(self, repo: Path) -> None:
        def stage(name: str, _log: rw.StageLog) -> int:
            if name == "pytest":
                msg = "boom"
                raise OSError(msg)
            return 0

        run = rw.Run(["pytest", "validate"], None)
        with patch.object(rw.Run, "run_stage", side_effect=stage):
            assert run.run() == 1
        assert _results(repo) == {"pytest": "FAILED", "validate": "passed"}
        (log,) = repo.glob("build/overnight/*/pytest.log")
        assert "OSError: boom" in log.read_text(encoding="utf-8")

    def test_ctrl_c_stops_the_run(self, repo: Path) -> None:
        run = rw.Run(["pytest", "validate"], None)
        with patch.object(rw.Run, "run_stage", side_effect=KeyboardInterrupt):
            assert run.run() == 130
        assert _results(repo) == {"pytest": "stopped"}
        assert "stopped during pytest" in _summary(repo)

    def test_the_gui_stages_fail_when_the_machine_cannot_take_input(self, repo: Path) -> None:
        run = rw.Run(["gui", "soak"], None)
        run.gui_ready = False
        with patch.object(rw.Run, "stage_gui") as gui, patch.object(rw.Run, "stage_soak") as soak:
            assert run.run() == 1
        gui.assert_not_called()
        soak.assert_not_called()
        assert _results(repo) == {"gui": "FAILED", "soak": "FAILED"}
        (log,) = repo.glob("build/overnight/*/gui.log")
        assert "gui-doctor.log" in log.read_text(encoding="utf-8")

    @pytest.mark.usefixtures("repo")
    def test_doctor_is_asked_once(self) -> None:
        run = rw.Run(["gui", "soak"], None)
        with (
            patch.object(rw.StageLog, "run", return_value=0) as ran,
            patch.object(rw.Run, "stage_gui", return_value=0),
            patch.object(rw.Run, "stage_soak", return_value=0),
        ):
            assert run.run() == 0
        assert ran.call_count == 1
        assert ran.call_args.args[0][-1] == "doctor"
        assert run.gui_ready is True

    def test_built_app_skips_without_an_executable(self, repo: Path) -> None:
        run = rw.Run(["built-app"], None)
        run.no_exe_why = "fetch-build did not fetch the executable"
        run.gui_ready = True
        assert run.run() == 0
        assert _results(repo) == {"built-app": "skipped"}
        (log,) = repo.glob("build/overnight/*/built-app.log")
        assert "fetch-build did not fetch" in log.read_text(encoding="utf-8")

    def test_fetch_build_skips_with_app(self, repo: Path) -> None:
        exe = repo / "reader.exe"
        run = rw.Run(["fetch-build"], exe)
        assert run.run() == 0
        assert _results(repo) == {"fetch-build": "skipped"}
        assert run.exe == exe

    def test_validate_skips_without_the_prebuilt_comics(self, repo: Path) -> None:
        run = rw.Run(["validate"], None)
        with patch.object(rw, "prebuilt_dir", return_value=repo / "absent"):
            assert run.run() == 0
        assert _results(repo) == {"validate": "skipped"}


class TestMemory:
    @pytest.mark.parametrize(
        ("value", "expected"), [("8000", 8000), ("", 6144), ("lots", 6144), (None, 6144)]
    )
    def test_env_mb(self, value: str | None, expected: int) -> None:
        env = {} if value is None else {"X": value}
        assert rw.env_mb(env, "X", 6144) == expected

    def test_enough_free_memory(self) -> None:
        assert rw.free_memory_problem(8000, 6144) is None
        assert rw.free_memory_problem(6144, 6144) is None

    def test_too_little_says_how_much(self) -> None:
        problem = rw.free_memory_problem(3000, 6144)
        assert problem is not None
        assert "3,000 MB" in problem
        assert "6,144 MB" in problem

    def test_process_tree_mb_of_no_process(self) -> None:
        assert rw.process_tree_mb(2**31 - 1) is None

    def test_biggest_apps_are_sorted_and_counted(self) -> None:
        apps = rw.biggest_apps(3)
        assert len(apps) <= 3
        assert [size for _, size in apps] == sorted((size for _, size in apps), reverse=True)


class TestAppMemoryWatch:
    @staticmethod
    def _watch(tmp_path: Path, cap_mb: int = 3000) -> tuple[rw.AppMemoryWatch, MagicMock]:
        (tmp_path / "app.pid").write_text("4242\n", encoding="utf-8")
        log = MagicMock(spec=rw.StageLog)
        return rw.AppMemoryWatch(log, cap_mb, tmp_path / "app.pid", 0.01), log

    def test_under_the_cap_is_only_noted(self, tmp_path: Path) -> None:
        watch, log = self._watch(tmp_path)
        with (
            patch.object(rw, "process_tree_mb", return_value=1200),
            patch.object(rw, "kill_tree") as kill,
        ):
            watch.check()
        kill.assert_not_called()
        log.line.assert_not_called()
        assert watch.peak_mb == 1200
        assert watch.breaches == []

    def test_over_the_cap_stops_the_app_once(self, tmp_path: Path) -> None:
        watch, log = self._watch(tmp_path)
        with (
            patch.object(rw, "process_tree_mb", return_value=4400),
            patch.object(rw, "kill_tree") as kill,
        ):
            watch.check()
            watch.check()  # the same app, already stopped: not again
        kill.assert_called_once_with(4242)
        assert watch.breaches == [4400]
        assert "4,400 MB" in log.line.call_args.args[0]
        assert "over the cap 1 time(s)" in watch.finish()

    def test_no_app_is_nothing(self, tmp_path: Path) -> None:
        log = MagicMock(spec=rw.StageLog)
        watch = rw.AppMemoryWatch(log, 3000, tmp_path / "absent.pid", 0.01)
        watch.check()
        assert watch.peak_mb == 0
        assert watch.finish() == "memory: the app's peak was 0 MB (cap 3,000 MB)"

    def test_it_watches_in_its_own_thread(self, tmp_path: Path) -> None:
        watch, _ = self._watch(tmp_path)
        with (
            patch.object(rw, "process_tree_mb", return_value=800),
            patch.object(rw, "kill_tree"),
        ):
            watch.start()
            for _ in range(200):
                if watch.peak_mb:
                    break
                rw.time.sleep(0.01)
            line = watch.finish()
        assert not watch.is_alive()
        assert "800 MB" in line


class TestGuiStageMemory:
    def test_a_gui_stage_does_not_start_short_of_memory(self, repo: Path) -> None:
        run = rw.Run(["gui"], None)
        run.gui_ready = True
        with (
            patch.object(rw, "available_mb", return_value=2000),
            patch.object(rw, "biggest_apps", return_value=[("firefox.exe", 1700)]),
            patch.object(rw.Run, "stage_gui") as gui,
        ):
            assert run.run() == 1
        gui.assert_not_called()
        (log,) = repo.glob("build/overnight/*/gui.log")
        text = log.read_text(encoding="utf-8")
        assert "2,000 MB" in text
        assert "firefox.exe" in text

    @pytest.mark.usefixtures("repo")
    def test_a_breach_fails_a_suite_that_passed(self) -> None:
        run = rw.Run(["gui"], None)
        log = MagicMock(spec=rw.StageLog)
        log.run.return_value = 0

        def breach(watch: rw.AppMemoryWatch) -> None:
            watch.breaches.append(4400)

        with patch.object(rw.AppMemoryWatch, "start", breach):
            assert run.gui_tests(log) == 1
        assert "over the cap" in log.line.call_args.args[0]

    @pytest.mark.usefixtures("repo")
    def test_a_clean_suite_passes(self) -> None:
        run = rw.Run(["gui"], None)
        log = MagicMock(spec=rw.StageLog)
        log.run.return_value = 0
        with patch.object(rw.AppMemoryWatch, "start"):
            assert run.gui_tests(log) == 0
        assert "peak" in log.line.call_args.args[0]


class TestMain:
    def test_an_unknown_stage(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert rw.main(["--only", "nope"]) == 2
        assert "no stage called nope" in capsys.readouterr().err

    def test_a_missing_app(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        assert rw.main(["--app", str(tmp_path / "absent.exe")]) == 2
        assert "not an executable" in capsys.readouterr().err

    def test_list(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert rw.main(["--list"]) == 0
        assert "fetch-build" in capsys.readouterr().out
