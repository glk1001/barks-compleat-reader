"""Tests for the desktop overnight runner: its stage table, its choices and its summary.

The stages themselves run real tools on the Windows laptop and the Mac; what is tested here,
on every platform, is what decides which of them run, what each result is
called, and that summary.txt reads as the Linux run's does.
"""

# ruff: noqa: PLR2004  (small literal counts are the point of these tests)

# cspell:ignore PYTHONIOENCODING caffeinate dimsu pmset taskkill procs

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import gui_probe_win32
import pytest
import run_overnight_desktop as rw

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

    def test_the_build_is_fetched_late_just_before_it_is_used(self) -> None:
        """After the GUI suite, CI's build of a fresh push is done: no stage waits on it."""
        stages = list(rw.STAGES)
        assert stages.index("fetch-build") == stages.index("built-app") - 1
        assert stages.index("fetch-build") > stages.index("gui")

    def test_the_wiki_is_pulled_before_anything_reads_it(self) -> None:
        stages = list(rw.STAGES)
        assert stages.index("wiki-copy") == 1
        assert stages.index("wiki-copy") < stages.index("validate") < stages.index("gui")

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
        assert chosen == ["update", "wiki-copy", "pytest", "validate", "gui", "soak", "coverage"]

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

    def test_stages_started_on_battery_are_named_under_the_table(self) -> None:
        results = [rw.StageResult("pytest", "passed", 61), rw.StageResult("gui", "FAILED", 3000)]
        stamp = "20261004-115956"
        text = rw.summary_text(
            stamp, "1cd7b90", "finished", results, f"build/overnight/{stamp}", ["gui"]
        )
        assert text.splitlines()[3:] == [
            "warning: on battery for gui (a throttled CPU can fail the timing budgets; plug in)",
            "logs: build/overnight/20261004-115956/",
        ]

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

    def test_only_docs_and_markdown_reach_no_build(self) -> None:
        assert rw.reaches_no_build(["docs/plans/x.txt", "README.md", "src/a/notes.md"])
        assert not rw.reaches_no_build(["docs/x.md", "src/a/b.py"])
        assert rw.reaches_no_build([])


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
        # Plugged in, whatever this machine is: the battery tests set their own.
        patch.object(rw, "on_battery", return_value=False),
    ):
        yield tmp_path


def _summary(repo: Path) -> str:
    (summary,) = repo.glob("build/overnight/*/summary.txt")
    return summary.read_text(encoding="utf-8")


def _results(repo: Path) -> dict[str, str]:
    """Return the summary's stage table: the lines between its header and any warning."""
    lines = _summary(repo).splitlines()[1:]
    table = [line for line in lines if not line.startswith(("warning:", "logs:"))]
    return {line.split()[0]: line.split()[1] for line in table}


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

    def test_the_stages_started_on_battery_are_in_the_summary(self, repo: Path) -> None:
        """Unplugged after the first stage: the later ones are named, the first is not."""
        run = rw.Run(["update", "pytest", "gui"], None)
        with (
            patch.object(rw, "on_battery", side_effect=[False, True, True]),
            patch.object(rw.Run, "run_stage", return_value=0),
        ):
            assert run.run() == 0
        assert _results(repo) == {"update": "passed", "pytest": "passed", "gui": "passed"}
        assert "warning: on battery for pytest, gui (" in _summary(repo)

    def test_plugged_in_the_summary_has_no_warning(self, repo: Path) -> None:
        run = rw.Run(["update"], None)
        with patch.object(rw.Run, "run_stage", return_value=0):
            run.run()
        assert "warning:" not in _summary(repo)

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


class TestWikiCopy:
    @staticmethod
    def _stage(repo: Path, *, pulled: bool, status: int, wiki: bool = True) -> MagicMock:
        """Run wiki-copy with the pull and check_wiki_copy.py faked; return the pull."""
        wiki_repo = repo / "barks-wiki"
        if wiki:
            wiki_repo.mkdir()
        run = rw.Run(["wiki-copy"], None)
        with (
            patch.object(rw, "WIKI_REPO", wiki_repo),
            patch.object(rw.pull_sibling, "pull", return_value=(pulled, "wiki-copy: said")) as pull,
            patch.object(rw.StageLog, "run", return_value=status),
        ):
            run.run()
        return pull

    def test_pulled_and_current_passes(self, repo: Path) -> None:
        pull = self._stage(repo, pulled=True, status=0)
        assert pull.call_args.kwargs == {"stage": "wiki-copy"}
        assert _results(repo) == {"wiki-copy": "passed"}
        (log,) = repo.glob("build/overnight/*/wiki-copy.log")
        assert "wiki-copy: said" in log.read_text(encoding="utf-8")

    def test_a_stale_copy_warns(self, repo: Path) -> None:
        self._stage(repo, pulled=True, status=rw.WIKI_COPY_STALE)
        assert _results(repo) == {"wiki-copy": "WARNED"}

    def test_a_wiki_that_could_not_be_pulled_warns_though_the_copy_matches_it(
        self, repo: Path
    ) -> None:
        """Current against a checkout days old is no news: the Windows laptop's, 2026-10-09."""
        self._stage(repo, pulled=False, status=0)
        assert _results(repo) == {"wiki-copy": "WARNED"}

    def test_a_broken_join_fails(self, repo: Path) -> None:
        self._stage(repo, pulled=False, status=1)
        assert _results(repo) == {"wiki-copy": "FAILED"}

    def test_skipped_without_barks_wiki(self, repo: Path) -> None:
        pull = self._stage(repo, pulled=True, status=0, wiki=False)
        pull.assert_not_called()
        assert _results(repo) == {"wiki-copy": "skipped"}

    def test_the_stale_status_matches_check_wiki_copy(self) -> None:
        source = (Path(rw.__file__).parent / "check_wiki_copy.py").read_text(encoding="utf-8")
        assert f"STALE_EXIT = {rw.WIKI_COPY_STALE}" in source


def _ci(
    builds: dict[str, int], changed: dict[str, str], *, pushed: bool = True, gh_ok: bool = True
) -> object:
    """Fake git and gh for fetch-build: HEAD c3, then c2 and c1 before it.

    builds: the commits CI built, and their run ids; changed: each earlier commit's
    files changed since, up to c3.
    """

    def capture(argv: list[str]) -> tuple[int, str]:
        match argv:
            case ["git", "rev-parse", "HEAD"]:
                return 0, "c3\n"
            case ["git", "rev-list", *_]:
                return 0, "c2\nc1\n"
            case ["git", "diff", *_, earlier, "c3"]:
                return 0, changed[earlier]
            case ["git", "branch", *_]:
                return 0, "  origin/main\n" if pushed else ""
            case ["gh", "run", "list", *rest]:
                commit = rest[rest.index("--commit") + 1]
                runs = [{"databaseId": builds[commit], "event": "push"}] if commit in builds else []
                return (0, json.dumps(runs)) if gh_ok else (1, "")
        raise AssertionError(argv)

    return capture


class TestFetchBuild:
    @staticmethod
    def _fetch(repo: Path, capture: object) -> tuple[MagicMock, str]:
        """Run fetch-build on Windows with git and gh faked; return the download and log."""
        run = rw.Run(["fetch-build"], None)
        with (
            patch.object(rw, "ON_WINDOWS", True),  # noqa: FBT003
            patch.object(rw.StageLog, "capture", side_effect=capture),
            patch.object(rw.Run, "_await_windows_job", return_value={}),
            patch.object(rw.Run, "_download", return_value=0) as download,
        ):
            run.run()
        (log,) = repo.glob("build/overnight/*/fetch-build.log")
        return download, log.read_text(encoding="utf-8")

    def test_this_commits_build(self, repo: Path) -> None:
        download, _ = self._fetch(repo, _ci({"c3": 30, "c2": 20}, {}))
        assert download.call_args.args[-1] == "30"
        assert _results(repo) == {"fetch-build": "passed"}

    def test_an_earlier_build_when_only_docs_changed_since(self, repo: Path) -> None:
        changed = {"c2": "docs/a.md\n", "c1": "docs/a.md\nREADME.md\n"}
        download, log = self._fetch(repo, _ci({"c1": 10}, changed))
        assert download.call_args.args[-1] == "10"
        assert "only docs changed since" in log
        assert _results(repo) == {"fetch-build": "passed"}

    def test_skipped_when_more_than_docs_changed_since_the_last_build(self, repo: Path) -> None:
        """[skip ci] on a code change: there is no build of this code to test."""
        changed = {"c2": "src/a.py\n"}
        download, log = self._fetch(repo, _ci({"c2": 20}, changed))
        download.assert_not_called()
        assert "changes more than docs since c2" in log
        assert _results(repo) == {"fetch-build": "skipped"}

    def test_a_commit_not_pushed_fails(self, repo: Path) -> None:
        _, log = self._fetch(repo, _ci({"c2": 20}, {"c2": "src/a.py\n"}, pushed=False))
        assert "c3 is not pushed" in log
        assert _results(repo) == {"fetch-build": "FAILED"}

    def test_no_build_in_the_commits_before_fails(self, repo: Path) -> None:
        changed = {"c2": "docs/a.md\n", "c1": "docs/a.md\n"}
        _, log = self._fetch(repo, _ci({}, changed))
        assert "20 commits before it" in log
        assert _results(repo) == {"fetch-build": "FAILED"}

    def test_gh_failing_fails(self, repo: Path) -> None:
        _, log = self._fetch(repo, _ci({"c3": 30}, {}, gh_ok=False))
        assert "gh run list failed" in log
        assert _results(repo) == {"fetch-build": "FAILED"}


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


def _log() -> MagicMock:
    log = MagicMock(spec=rw.StageLog)
    log.run.return_value = 0
    log.capture.return_value = (0, "84.2\n")
    return log


@pytest.mark.usefixtures("repo")
class TestCoverage:
    """The pytest and gui stages measure; the coverage stage combines, reports and judges."""

    def test_the_unit_suite_runs_under_coverage(self) -> None:
        run = rw.Run(["pytest"], None)
        log = _log()
        assert run.stage_pytest(log) == 0
        argv, env = log.run.call_args.args
        assert "--cov" in argv
        assert env["COVERAGE_FILE"] == str(run.cov_dir / ".coverage.unit")

    def test_the_gui_stage_gives_the_probe_a_coverage_folder(self) -> None:
        run = rw.Run(["gui"], None)
        with patch.object(rw.Run, "gui_tests", return_value=0) as gui_tests:
            assert run.stage_gui(_log()) == 0
        assert gui_tests.call_args.kwargs == {"BARKS_PROBE_COVERAGE": str(run.cov_dir)}
        assert run.cov_dir.is_dir()

    def test_nothing_measured_is_skipped(self) -> None:
        run = rw.Run(["coverage"], None)
        log = _log()
        assert run.stage_coverage(log) == rw.SKIPPED
        log.run.assert_not_called()

    def _measured(self, *parts: str) -> rw.Run:
        run = rw.Run(["coverage"], None)
        run.cov_dir.mkdir()
        for part in parts:
            (run.cov_dir / part).write_bytes(b"")
        return run

    def test_each_part_and_the_combined_figure_are_reported(self) -> None:
        run = self._measured(".coverage.unit", ".coverage.gui")
        log = _log()
        assert run.stage_coverage(log) == 0
        lines = [c.args[0] for c in log.line.call_args_list]
        assert "coverage: unit suite  84.2%" in lines
        assert "coverage: GUI tests   84.2%" in lines
        assert "coverage: combined    84.2%" in lines
        combine = log.run.call_args_list[0].args[0]
        assert combine[2:4] == ["coverage", "combine"]
        assert combine[-2:] == [
            str(run.cov_dir / ".coverage.unit"),
            str(run.cov_dir / ".coverage.gui"),
        ]

    def test_a_night_without_both_stages_passing_is_not_judged(self) -> None:
        run = self._measured(".coverage.unit")
        run.results = [rw.StageResult("pytest", "passed", 1), rw.StageResult("gui", "FAILED", 1)]
        log = _log()
        assert run.stage_coverage(log) == 0
        assert "not judged" in log.line.call_args.args[0]
        assert not any("coverage_floor.py" in " ".join(c.args[0]) for c in log.run.call_args_list)

    def test_a_night_both_passed_is_held_to_the_floor(self) -> None:
        run = self._measured(".coverage.unit", ".coverage.gui")
        run.results = [rw.StageResult("pytest", "passed", 1), rw.StageResult("gui", "passed", 1)]
        log = _log()
        log.run.side_effect = [0, 0, 1]  # combine, html, the floor: below it
        assert run.stage_coverage(log) == 1
        floor = log.run.call_args.args[0]
        assert floor[-4:] == [str(rw.SCRIPTS / "coverage_floor.py"), "84.2", "--tolerance", "1.0"]


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

    def test_linux_is_sent_to_its_own_runner(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(rw, "ON_WINDOWS", False), patch.object(rw, "ON_MACOS", False):  # noqa: FBT003
            assert rw.main([]) == 2
        assert "on Linux use run_overnight.sh" in capsys.readouterr().err


class TestGlBackend:
    """Where Windows has no OpenGL driver, every stage draws through ANGLE."""

    def test_gdi_generic_draws_through_angle(self) -> None:
        assert rw.gl_backend_for({}, rw.SOFTWARE_OPENGL) == rw.ANGLE_BACKEND

    @pytest.mark.parametrize(
        ("env", "renderer"),
        [
            ({"KIVY_GL_BACKEND": "sdl2"}, rw.SOFTWARE_OPENGL),  # the caller chose
            ({}, "NVIDIA GeForce RTX 3060/PCIe/SSE2"),  # a real driver
            ({}, None),  # unread: over ssh, say
        ],
    )
    def test_otherwise_kivy_chooses(self, env: dict[str, str], renderer: str | None) -> None:
        assert rw.gl_backend_for(env, renderer) is None

    @pytest.fixture
    def no_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Set, then removed: the test's own setting is undone with the rest.
        monkeypatch.setenv("KIVY_GL_BACKEND", "-")
        monkeypatch.delenv("KIVY_GL_BACKEND")

    @pytest.mark.usefixtures("no_backend")
    def test_the_run_sets_it_for_every_stage_and_says_so(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with (
            patch.object(rw, "ON_WINDOWS", True),  # noqa: FBT003
            patch.object(gui_probe_win32, "opengl_renderer", return_value=rw.SOFTWARE_OPENGL),
        ):
            rw.choose_gl_backend()
        assert rw.os.environ["KIVY_GL_BACKEND"] == rw.ANGLE_BACKEND
        assert rw.child_env(rw.os.environ)["KIVY_GL_BACKEND"] == rw.ANGLE_BACKEND
        assert "drawing through ANGLE" in capsys.readouterr().out

    @pytest.mark.usefixtures("no_backend")
    def test_a_real_driver_is_named_and_left_alone(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with (
            patch.object(rw, "ON_WINDOWS", True),  # noqa: FBT003
            patch.object(gui_probe_win32, "opengl_renderer", return_value="Intel(R) UHD"),
        ):
            rw.choose_gl_backend()
        assert "KIVY_GL_BACKEND" not in rw.os.environ
        assert "OpenGL: Intel(R) UHD" in capsys.readouterr().out

    def test_off_windows_nothing_is_asked(self) -> None:
        with (
            patch.object(rw, "ON_WINDOWS", False),  # noqa: FBT003
            patch.object(gui_probe_win32, "opengl_renderer") as asked,
        ):
            rw.choose_gl_backend()
        asked.assert_not_called()

    @pytest.mark.skipif(rw.ON_WINDOWS, reason="on Windows it reads the real OpenGL")
    def test_the_probe_reads_nothing_off_windows(self) -> None:
        assert gui_probe_win32.opengl_renderer() is None


# ------------------------------------------------------------------ macOS --


class TestMachineMemory:
    @pytest.mark.parametrize(
        ("total_mb", "expected"),
        [
            (16384, (6144, 6144)),  # the Windows laptop: the 6 GB defaults
            (8192, (4096, 6144)),
            (4096, (2048, 3072)),  # the macOS guest: half free to start, three quarters cap
        ],
    )
    def test_the_defaults_fit_the_machine(self, total_mb: int, expected: tuple[int, int]) -> None:
        assert rw.memory_defaults(total_mb) == expected


class TestMacOS:
    @pytest.mark.parametrize(
        ("pmset", "on_battery"),
        [
            ("Now drawing from 'AC Power'\n", False),  # what the macOS guest says
            ("Now drawing from 'Battery Power'\n -InternalBattery-0\t87%; discharging", True),
            ("", False),
        ],
    )
    def test_the_power_source(self, pmset: str, on_battery: bool) -> None:
        assert rw.pmset_on_battery(pmset) is on_battery

    def test_caffeinate_holds_sleep_off_for_this_process(self) -> None:
        with (
            patch.object(rw, "ON_WINDOWS", False),  # noqa: FBT003
            patch.object(rw.subprocess, "Popen") as popen,
        ):
            with rw.kept_awake():
                popen.return_value.terminate.assert_not_called()
            popen.return_value.terminate.assert_called_once()
        assert popen.call_args.args[0] == ["caffeinate", "-dimsu", "-w", str(rw.os.getpid())]

    def test_no_caffeinate_warns_and_runs_on(self) -> None:
        with (
            patch.object(rw, "ON_WINDOWS", False),  # noqa: FBT003
            patch.object(rw.subprocess, "Popen", side_effect=OSError("no caffeinate")),
            patch.object(rw, "say") as say,
            rw.kept_awake(),
        ):
            pass
        assert "could not hold off sleep" in say.call_args.args[0]

    def test_a_process_tree_is_ended_without_taskkill(self) -> None:
        script = (
            "import subprocess, sys, time;"
            " subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']);"
            " time.sleep(60)"
        )
        parent = rw.subprocess.Popen([rw.sys.executable, "-c", script])
        try:
            children: list[rw.psutil.Process] = []
            deadline = rw.time.monotonic() + 10
            while not children and rw.time.monotonic() < deadline:
                children = rw.psutil.Process(parent.pid).children()
            assert children, "the parent never started its child"
            with patch.object(rw, "ON_WINDOWS", False):  # noqa: FBT003
                rw.kill_tree(parent.pid)
            assert parent.wait(10) != 0
            _, alive = rw.psutil.wait_procs(children, timeout=10)
            assert not alive, f"left running: {alive}"
        finally:
            if parent.poll() is None:
                parent.kill()

    def test_the_suite_runs_through_the_soft_gl_wrapper_on_macos(self) -> None:
        with patch.object(rw, "ON_MACOS", True):  # noqa: FBT003
            assert rw.venv_command("pytest", "-q") == [
                "bash",
                str(rw.SOFT_GL_WRAPPER),
                "pytest",
                "-q",
            ]
        assert rw.SOFT_GL_WRAPPER.is_file()
        with patch.object(rw, "ON_MACOS", False):  # noqa: FBT003
            assert rw.venv_command("pytest", "-q") == ["uv", "run", "pytest", "-q"]

    def test_fetch_build_fetches_nothing_on_macos(self, repo: Path) -> None:
        run = rw.Run(["fetch-build", "built-app"], None)
        run.gui_ready = True
        with patch.object(rw, "ON_WINDOWS", False):  # noqa: FBT003
            assert run.run() == 0
        assert _results(repo) == {"fetch-build": "skipped", "built-app": "skipped"}
        (log,) = repo.glob("build/overnight/*/fetch-build.log")
        assert "with-soft-gl.sh" in log.read_text(encoding="utf-8")
