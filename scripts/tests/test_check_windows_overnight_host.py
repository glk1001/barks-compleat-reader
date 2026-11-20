"""Tests for the Windows overnight host check: how it reads and judges what it finds.

What it asks Windows (the registry, powercfg, tasklist) runs only there; what
is tested here, on every platform, is the parsing and the verdicts.
"""

# cspell:ignore tasklist RTCWAKE schtasks

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import patch

import check_windows_overnight_host as ch
import gui_probe_win32
import pytest
import run_overnight_desktop as rw
from script_test_helpers import write_tree

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

POWERCFG = """Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)
  Subgroup GUID: 7516b95f-f776-4464-8c53-06167f40cc99  (Display)
    Power Setting GUID: 3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e  (Turn off display after)
      Possible Settings units: Seconds
    Current AC Power Setting Index: 0x00002a30
    Current DC Power Setting Index: 0x000000f0
"""


class TestAcIndex:
    def test_the_ac_value_not_the_dc_one(self) -> None:
        assert ch.ac_index(POWERCFG) == 10800  # noqa: PLR2004

    def test_no_setting(self) -> None:
        assert ch.ac_index("The system cannot find the path specified.") is None


class TestIdleCheck:
    @pytest.mark.parametrize("secs", [0, ch.MIN_IDLE_SECS, 10800])
    def test_never_or_longer_than_a_run(self, secs: int) -> None:
        assert ch.idle_check("sleep", secs)[0] == "OK"

    def test_shorter_than_a_run_warns(self) -> None:
        status, text = ch.idle_check("the non-sensor presence timeout", 240)
        assert status == "WARN"
        assert "after 4 min" in text

    def test_no_such_setting(self) -> None:
        assert ch.idle_check("sleep", None)[0] == "--"


class TestSignInCheck:
    def test_never(self) -> None:
        assert ch.sign_in_check(ch.SIGN_IN_NEVER)[0] == "OK"

    @pytest.mark.parametrize("delay", [900, 0, None])
    def test_anything_else_fails(self, delay: int | None) -> None:
        assert ch.sign_in_check(delay)[0] == "FAIL"


class TestScreenSaverCheck:
    def test_none(self) -> None:
        assert ch.screen_saver_check("", "")[0] == "OK"

    def test_with_a_password(self) -> None:
        assert ch.screen_saver_check("C:\\Windows\\system32\\Mystify.scr", "1")[0] == "FAIL"

    def test_without_one(self) -> None:
        assert ch.screen_saver_check("C:\\Windows\\system32\\Mystify.scr", "0")[0] == "OK"


class TestPresenceLockChecks:
    def test_glance_fails_whatever_its_case(self) -> None:
        (check,) = ch.presence_lock_checks({"explorer.exe", "GLANCE.EXE"})
        assert check[0] == "FAIL"
        assert "Walk Away Lock" in check[1]

    def test_none_running(self) -> None:
        assert ch.presence_lock_checks({"explorer.exe"}) == [
            ("OK", "no webcam presence-lock app running")
        ]


class TestWikiCopyChecks:
    @staticmethod
    def _wiki(tmp_path: Path, text: bytes) -> Path:
        wiki = tmp_path / ch.WIKI_SUBPATH
        wiki.mkdir(parents=True)
        (wiki / "index.md").write_bytes(text)
        return tmp_path

    def test_an_lf_copy(self, tmp_path: Path) -> None:
        assert ch.wiki_copy_checks(self._wiki(tmp_path, b"# Wiki\n\ntext\n"))[0][0] == "OK"

    def test_a_crlf_copy_warns(self, tmp_path: Path) -> None:
        (check,) = ch.wiki_copy_checks(self._wiki(tmp_path, b"# Wiki\r\n\r\ntext\r\n"))
        assert check[0] == "WARN"
        assert "CRLF" in check[1]

    def test_no_copy_fails(self, tmp_path: Path) -> None:
        assert ch.wiki_copy_checks(tmp_path)[0][0] == "FAIL"

    def test_no_data_dir_fails(self) -> None:
        assert ch.wiki_copy_checks(None)[0][0] == "FAIL"


class TestOpenglCheck:
    def test_a_real_driver_is_named(self) -> None:
        assert ch.opengl_check("Intel(R) UHD Graphics", {}) == (
            "OK",
            "OpenGL: Intel(R) UHD Graphics",
        )

    def test_no_driver_says_the_runner_draws_through_angle(self) -> None:
        status, text = ch.opengl_check("GDI Generic", {})
        assert status == "OK"
        assert "draws through ANGLE" in text
        assert "--angle" in text

    def test_a_backend_already_set_is_what_draws(self) -> None:
        assert ch.opengl_check("GDI Generic", {"KIVY_GL_BACKEND": "angle_sdl2"}) == (
            "OK",
            "KIVY_GL_BACKEND=angle_sdl2: Kivy draws through it",
        )

    def test_unread_over_ssh_says_where_to_run_it(self) -> None:
        status, text = ch.opengl_check(None, {})
        assert status == "WARN"
        assert "on the desktop" in text


class TestMain:
    def test_windows_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ch.sys, "platform", "linux")
        assert ch.main() == 2  # noqa: PLR2004


class TestMemoryCheck:
    """Free memory judged as a GUI stage will judge it; the macOS check uses this one too."""

    @pytest.fixture(autouse=True)
    def _no_minimum_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BARKS_OVERNIGHT_MIN_FREE_MB", "-")
        monkeypatch.delenv("BARKS_OVERNIGHT_MIN_FREE_MB")

    def test_the_minimum_follows_the_machine(self) -> None:
        """Judged by the runner's machine-sized minimum, not a fixed 6 GB."""
        with (
            patch.object(rw, "available_mb", return_value=3000),
            patch.object(rw, "machine_memory_defaults", return_value=(2048, 3072)),
        ):
            status, text = ch.memory_check()

        assert status == "OK"
        assert "needs 2,048" in text

    def test_too_little_warns_naming_what_holds_the_most(self) -> None:
        """Only a warning: tonight's free memory may differ from now's."""
        with (
            patch.object(rw, "available_mb", return_value=1000),
            patch.object(rw, "machine_memory_defaults", return_value=(2048, 3072)),
            patch.object(rw, "biggest_apps", return_value=[("firefox", 4096), ("code", 1500)]),
        ):
            status, text = ch.memory_check()

        assert status == "WARN"
        assert text.endswith(": firefox 4,096 MB, code 1,500 MB")

    def test_a_minimum_set_for_the_run_is_the_one_used(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BARKS_OVERNIGHT_MIN_FREE_MB", "500")
        with (
            patch.object(rw, "available_mb", return_value=1000),
            patch.object(rw, "machine_memory_defaults", return_value=(2048, 3072)),
        ):
            status, text = ch.memory_check()

        assert status == "OK"
        assert "needs 500" in text


class TestRun:
    def test_a_tool_s_status_and_everything_it_printed_come_back(self) -> None:
        code = "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"

        status, text = ch._run([sys.executable, "-c", code])  # noqa: SLF001

        assert status == 3  # noqa: PLR2004
        assert text.splitlines() == ["out", "err"]

    def test_a_tool_that_is_not_there_is_a_status_not_an_error(self) -> None:
        status, text = ch._run(["no-such-tool-on-this-machine"])  # noqa: SLF001

        assert status == 127  # noqa: PLR2004
        assert text  # the system's own words for it, which differ by platform


class TestRegistryValues:
    def test_off_windows_there_is_no_registry_to_read(self) -> None:
        with patch.object(ch.sys, "platform", "linux"):
            assert ch._registry(r"Control Panel\Desktop", "DelayLockInterval") is None  # noqa: SLF001

    @pytest.mark.parametrize(("value", "number"), [("0", 0), (300, 300), ("", None), (None, None)])
    def test_a_value_is_a_number_or_nothing(self, value: object, number: int | None) -> None:
        assert ch._as_int(value) == number  # noqa: SLF001


def _tools(present: set[str]) -> Callable[[str], str | None]:
    return lambda tool: f"/usr/bin/{tool}" if tool in present else None


class TestToolChecks:
    @staticmethod
    def _checks(present: set[str], gh_status: int = 0) -> list[tuple[str, str]]:
        with (
            patch.object(ch.shutil, "which", side_effect=_tools(present)),
            patch.object(ch, "_run", return_value=(gh_status, "")) as run,
        ):
            checks = ch.tool_checks()
        if "gh" in present:
            run.assert_called_once_with(["gh", "auth", "status"])
        else:
            run.assert_not_called()
        return checks

    def test_a_machine_with_every_tool(self) -> None:
        assert self._checks({"git", "gh", "bunx"}) == [
            ("OK", "git"),
            ("OK", "gh"),
            ("OK", "gh logged in"),
            ("OK", "bunx"),
        ]

    def test_fetch_build_needs_gh_logged_in_and_the_hooks_want_bunx(self) -> None:
        assert self._checks({"git", "gh"}, gh_status=1)[2:] == [
            ("FAIL", "gh: run 'gh auth login'"),
            ("WARN", "no bunx: the cspell commit hook fails (docs/setup.md, Windows: bunx.cmd)"),
        ]

    def test_a_tool_not_on_the_path_fails_and_says_where_it_comes_from(self) -> None:
        assert self._checks(set())[:2] == [
            ("FAIL", "git not on PATH (Git for Windows)"),
            ("FAIL", "gh not on PATH (winget install GitHub.cli, for fetch-build)"),
        ]


class TestRepoFileChecks:
    def test_a_fresh_clone_lacks_the_generated_modules_and_a_calibration(
        self, tmp_path: Path
    ) -> None:
        with patch.object(ch, "REPO_ROOT", tmp_path):
            checks = ch.repo_file_checks()

        assert [status for status, _ in checks] == ["FAIL", "FAIL", "WARN"]
        assert checks[0][1].endswith("_version.py missing - run 'bash scripts/build.sh'")
        assert "--calibrate" in checks[2][1]

    def test_a_set_up_clone_has_them_all(self, tmp_path: Path) -> None:
        files = {module: "" for module, _ in ch.GENERATED_MODULES}
        write_tree(tmp_path, {**files, ".benchmarks/gui-timings.json": "{}"})
        with patch.object(ch, "REPO_ROOT", tmp_path):
            checks = ch.repo_file_checks()

        assert [status for status, _ in checks] == ["OK", "OK", "OK"]


class TestDataChecks:
    @staticmethod
    def _checks(barks_root: Path, prebuilt: Path) -> list[tuple[str, str]]:
        with (
            patch.object(ch, "BARKS_ROOT", barks_root),
            patch.object(ch.gui_probe, "config_dir", return_value=barks_root / "config"),
            patch.object(ch.gui_probe, "data_dir", return_value=barks_root / "data"),
            patch.object(ch, "_prebuilt_dir", return_value=prebuilt) as read,
            patch.object(ch, "wiki_copy_checks", return_value=[("OK", "the wiki copy")]) as wiki,
        ):
            checks = ch.data_checks()
        read.assert_called_once_with(barks_root / "config" / "barks-reader.ini")
        wiki.assert_called_once_with(barks_root / "data")
        return checks

    def test_the_reader_files_and_the_prebuilt_comics_are_there(self, tmp_path: Path) -> None:
        reader_files = tmp_path / "Compleat Barks Disney Reader" / "Reader Files"
        reader_files.mkdir(parents=True)
        (tmp_path / "prebuilt").mkdir()

        assert self._checks(tmp_path, tmp_path / "prebuilt") == [
            ("OK", f"{reader_files}"),
            ("OK", f"prebuilt comics: {tmp_path / 'prebuilt'}"),
            ("OK", "the wiki copy"),
        ]

    def test_no_reader_files_fails_and_no_prebuilt_comics_only_warns(self, tmp_path: Path) -> None:
        missing, prebuilt, _ = self._checks(tmp_path, tmp_path / "prebuilt")

        assert missing[0] == "FAIL"
        assert "pytest needs it" in missing[1]
        assert prebuilt == (
            "WARN",
            f"no prebuilt comics at {tmp_path / 'prebuilt'}: the validate stage skips itself",
        )

    def test_the_prebuilt_folder_is_read_as_the_runner_reads_it(self, tmp_path: Path) -> None:
        with patch.object(rw, "prebuilt_dir", return_value=tmp_path) as read:
            assert ch._prebuilt_dir(tmp_path / "barks-reader.ini") == tmp_path  # noqa: SLF001

        read.assert_called_once_with(tmp_path / "barks-reader.ini")


class TestMachineChecks:
    """What the checks ask Windows, and what each answer becomes."""

    AC_FIVE_MINUTES = "    Current AC Power Setting Index: 0x0000012c\n"
    AC_NEVER = "    Current AC Power Setting Index: 0x00000000\n"

    def _checks(
        self, *, registry: Mapping[str, object], wake: str, task_status: int
    ) -> list[tuple[str, str]]:
        def run(argv: list[str]) -> tuple[int, str]:
            match argv:
                case ["powercfg", *_, "RTCWAKE"]:
                    return 0, wake
                case ["powercfg", *_]:
                    return 0, self.AC_NEVER
                case ["tasklist", *_]:
                    return 0, '"explorer.exe","4","Console","1","9 K"\n'
                case ["schtasks", *_]:
                    return task_status, ""
            raise AssertionError(argv)

        def read_registry(_path: str, name: str, **_kw: object) -> object | None:
            return registry.get(name)

        with (
            patch.object(ch, "_registry", side_effect=read_registry),
            patch.object(ch, "_run", side_effect=run),
            patch.object(ch, "memory_check", return_value=("OK", "memory")),
            patch.object(ch, "opengl_check", return_value=("OK", "OpenGL")) as opengl,
            patch.object(gui_probe_win32, "opengl_renderer", return_value="a renderer"),
            patch.object(ch, "presence_lock_checks", return_value=[("OK", "presence")]) as presence,
        ):
            checks = ch.machine_checks()
        assert opengl.call_args.args[0] == "a renderer"
        presence.assert_called_once_with({"explorer.exe"})
        return checks

    def test_a_machine_set_up_for_the_night(self) -> None:
        never = str(ch.SIGN_IN_NEVER)
        registry = {"AllowDevelopmentWithoutDevLicense": 1, "DelayLockInterval": never}

        checks = self._checks(registry=registry, wake=self.AC_NEVER[:-2] + "1\n", task_status=0)

        assert [status for status, _ in checks if status != "OK"] == []
        assert ("OK", "Developer Mode") in checks
        assert ("OK", "wake timers allowed on AC") in checks
        assert ("OK", f"the '{ch.TASK_NAME}' task is registered") in checks
        assert len(checks) == 2 + 3 + len(ch.IDLE_SETTINGS) + 3

    def test_what_is_not_set_up_is_named(self) -> None:
        checks = self._checks(registry={}, wake=self.AC_NEVER, task_status=1)

        problems = [text for status, text in checks if status != "OK"]
        assert any(text.startswith("Developer Mode off") for text in problems)
        assert "wake timers off on AC: the task cannot wake the machine at night" in problems
        assert any(text.startswith(f"no '{ch.TASK_NAME}' task") for text in problems)


class TestTheWholeCheck:
    def test_the_probe_s_doctor_checks_come_first(self) -> None:
        with (
            patch.object(gui_probe_win32, "Win32Backend") as backend,
            patch.object(ch.gui_probe, "repo_checks", return_value=[("OK", "uv")]),
        ):
            backend.return_value.doctor_checks.return_value = [("OK", "a screen")]
            assert ch.gui_checks() == [("OK", "a screen"), ("OK", "uv")]

    @staticmethod
    def _main(machine: list[tuple[str, str]]) -> int:
        with (
            patch.object(ch.sys, "platform", "win32"),
            patch.object(ch, "gui_checks", return_value=[("OK", "a screen")]),
            patch.object(ch, "tool_checks", return_value=[("WARN", "no bunx")]),
            patch.object(ch, "repo_file_checks", return_value=[]),
            patch.object(ch, "data_checks", return_value=[]),
            patch.object(ch, "machine_checks", return_value=machine),
        ):
            return ch.main()

    def test_warnings_alone_leave_the_machine_ready(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert self._main([("OK", "memory")]) == 0

        out = capsys.readouterr().out
        assert "\nThe GUI probe (doctor)\n  OK   a screen\n\nTools\n  WARN no bunx\n" in out
        assert out.endswith("\ncheck_windows_overnight_host: ready.\n")

    def test_one_fail_and_it_is_not_ready(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert self._main([("FAIL", "Developer Mode off")]) == 1

        assert capsys.readouterr().out.endswith("NOT ready - fix the FAIL items above.\n")
