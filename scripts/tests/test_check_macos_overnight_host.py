"""Tests for check_macos_overnight_host.py: what it makes of each answer, on every platform.

The machine's parts call macOS tools; what is tested here is what each check makes
of their answers, and of the repo's files.
"""

# cspell:ignore sysadminctl

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import check_macos_overnight_host as ch
import check_windows_overnight_host as shared
import gui_probe
import gui_probe_darwin
import pytest
import run_overnight_desktop as rw
from script_test_helpers import write_tree

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


NOT_THIS_PLATFORM = 2  # main()'s exit status off macOS


class TestHooks:
    def test_the_prek_hook(self) -> None:
        assert ch.hooks_check('exec "$PREK" hook-impl --hook-type=pre-push -- "$@"')[0] == "OK"

    def test_another_hook_warns(self) -> None:
        status, text = ch.hooks_check('git lfs pre-push "$@"')
        assert status == "WARN"
        assert "prek install" in text

    def test_no_hook_warns(self) -> None:
        assert ch.hooks_check(None)[0] == "WARN"


class TestScreenLock:
    def test_off(self) -> None:
        out = "2026-10-03 09:36:48.115 sysadminctl[1964:17010] screenLock is off\n"
        assert ch.screen_lock_check(out) == ("OK", "screen lock: off")

    def test_on_warns_naming_the_setting(self) -> None:
        out = "2026-10-03 09:36:48.115 sysadminctl[1964:17010] screenLock delay is 5 seconds\n"
        status, text = ch.screen_lock_check(out)
        assert status == "WARN"
        assert "screenLock delay is 5 seconds" in text

    def test_no_answer(self) -> None:
        assert ch.screen_lock_check("")[0] == "--"


class TestMachine:
    def test_eight_gb_is_enough(self) -> None:
        assert ch.total_memory_check(8 * 1024)[0] == "OK"

    def test_less_warns(self) -> None:
        assert ch.total_memory_check(4 * 1024)[0] == "WARN"

    def test_the_documented_clone_is_ok(self, tmp_path: Path) -> None:
        assert ch.clone_check(tmp_path, expected=tmp_path)[0] == "OK"

    def test_another_clone_warns_naming_the_coverage_report(self, tmp_path: Path) -> None:
        status, text = ch.clone_check(tmp_path / "elsewhere", expected=tmp_path / "Developer")
        assert status == "WARN"
        assert "coverage_all_platforms.py" in text


def test_off_macos_it_says_so() -> None:
    with patch.object(ch.sys, "platform", "linux"):
        assert ch.main() == NOT_THIS_PLATFORM


def _tools(present: set[str]) -> Callable[[str], str | None]:
    return lambda tool: f"/usr/bin/{tool}" if tool in present else None


class TestRun:
    def test_a_tool_s_status_and_everything_it_printed_come_back(self) -> None:
        code = "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"

        status, text = ch._run([sys.executable, "-c", code])  # noqa: SLF001

        assert status == 3  # noqa: PLR2004
        assert text.splitlines() == ["out", "err"]

    def test_a_tool_that_is_not_there_is_a_status_not_an_error(self) -> None:
        status, _ = ch._run(["no-such-tool-on-this-machine"])  # noqa: SLF001

        assert status == 127  # noqa: PLR2004


class TestToolChecks:
    @staticmethod
    def _checks(present: set[str], gh_status: int = 0) -> list[tuple[str, str]]:
        with (
            patch.object(ch.shutil, "which", side_effect=_tools(present)),
            patch.object(ch, "_run", return_value=(gh_status, "")),
        ):
            return ch.tool_checks()

    def test_a_mac_with_every_tool(self) -> None:
        assert self._checks({"git", "gh", "bunx"}) == [
            ("OK", "git"),
            ("OK", "gh logged in"),
            ("OK", "bunx"),
        ]

    def test_only_git_is_needed_for_a_run(self) -> None:
        statuses = [status for status, _ in self._checks(set())]
        assert statuses == ["FAIL", "WARN", "WARN"]

        logged_out = self._checks({"git", "gh", "bunx"}, gh_status=1)[1]
        assert logged_out[0] == "WARN"
        assert logged_out[1].startswith("gh logged out: 'gh auth login'")


class TestRepoChecks:
    def test_the_pre_push_hook_is_read_from_the_git_folder_a_worktree_shares(
        self, tmp_path: Path
    ) -> None:
        write_tree(tmp_path, {".git/hooks/pre-push": "exec prek hook-impl --hook-type=pre-push\n"})
        with (
            patch.object(ch, "REPO_ROOT", tmp_path),
            patch.object(ch, "_run", return_value=(0, ".git\n")) as run,
        ):
            hook = ch._pre_push_hook()  # noqa: SLF001

        assert hook == "exec prek hook-impl --hook-type=pre-push\n"
        assert run.call_args.args[0][-2:] == ["rev-parse", "--git-common-dir"]

    @pytest.mark.parametrize("git", [(128, "fatal: not a git repository\n"), (0, ".git\n")])
    def test_no_repository_or_no_hook_is_no_hook(
        self, tmp_path: Path, git: tuple[int, str]
    ) -> None:
        with patch.object(ch, "REPO_ROOT", tmp_path), patch.object(ch, "_run", return_value=git):
            assert ch._pre_push_hook() is None  # noqa: SLF001

    def test_the_repo_s_checks_are_its_files_its_hook_and_where_it_is(self) -> None:
        with (
            patch.object(shared, "repo_file_checks", return_value=[("OK", "files")]),
            patch.object(ch, "_pre_push_hook", return_value="a hook") as hook,
            patch.object(ch, "hooks_check", return_value=("OK", "hook")) as judged,
            patch.object(ch, "clone_check", return_value=("OK", "clone")) as clone,
        ):
            assert ch.repo_checks() == [("OK", "files"), ("OK", "hook"), ("OK", "clone")]

        judged.assert_called_once_with(hook.return_value)
        clone.assert_called_once_with(ch.REPO_ROOT)


class TestMachineChecks:
    def test_the_mac_s_version_memory_and_screen_lock(self) -> None:
        answers = {"sw_vers": (0, "12.7.6\n"), "sysadminctl": (0, "screenLock is off\n")}
        with (
            patch.object(ch, "_run", side_effect=lambda argv: answers[argv[0]]),
            patch.object(rw.psutil, "virtual_memory", return_value=MagicMock(total=8 * 1024**3)),
            patch.object(ch, "total_memory_check", return_value=("OK", "8 GB")) as total,
            patch.object(shared, "memory_check", return_value=("OK", "free")),
            patch.object(ch, "screen_lock_check", return_value=("OK", "no lock")) as lock,
        ):
            checks = ch.machine_checks()

        assert checks == [("OK", "macOS 12.7.6"), ("OK", "8 GB"), ("OK", "free"), ("OK", "no lock")]
        total.assert_called_once_with(8 * 1024)
        lock.assert_called_once_with("screenLock is off\n")


class TestTheWholeCheck:
    def test_the_probe_s_doctor_checks_come_first(self) -> None:
        with (
            patch.object(gui_probe_darwin, "DarwinBackend") as backend,
            patch.object(gui_probe, "repo_checks", return_value=[("OK", "uv")]),
        ):
            backend.return_value.doctor_checks.return_value = [("OK", "a screen")]
            assert ch.gui_checks() == [("OK", "a screen"), ("OK", "uv")]

    @staticmethod
    def _main(machine: list[tuple[str, str]]) -> int:
        with (
            patch.object(ch.sys, "platform", "darwin"),
            patch.object(ch, "gui_checks", return_value=[("OK", "a screen")]),
            patch.object(ch, "tool_checks", return_value=[("WARN", "no gh")]),
            patch.object(ch, "repo_checks", return_value=[]),
            patch.object(shared, "data_checks", return_value=[]),
            patch.object(ch, "machine_checks", return_value=machine),
        ):
            return ch.main()

    def test_warnings_alone_leave_the_mac_ready(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert self._main([("OK", "macOS 12.7.6")]) == 0

        out = capsys.readouterr().out
        assert "\nTools\n  WARN no gh\n" in out
        assert out.endswith("\ncheck_macos_overnight_host: ready.\n")

    def test_one_fail_and_it_is_not_ready(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert self._main([("FAIL", "the screen locks")]) == 1

        assert capsys.readouterr().out.endswith("NOT ready - fix the FAIL items above.\n")
