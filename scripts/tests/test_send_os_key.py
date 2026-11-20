"""Tests for send_os_key.py: which window gets the key, and what a failure says.

The key itself goes through the OS, which the build smoke test exercises on every
CI leg; here each platform's calls are faked, so every branch runs everywhere.
"""

# cspell:ignore xdotool onlyvisible windowfocus IMAGENAME tasklist pids

from __future__ import annotations

import subprocess
from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call, patch

import gui_probe_win32
import pytest
import send_os_key

if TYPE_CHECKING:
    from collections.abc import Generator

XDOTOOL = "/usr/bin/xdotool"
ESCAPE_CODE = 53
APP_PID = 4242


@contextmanager
def _on(platform: str) -> Generator[None]:
    """Have the script take this machine for one running `platform`."""
    with patch.object(send_os_key.sys, "platform", platform):
        yield


def _found(stdout: str) -> MagicMock:
    return MagicMock(stdout=stdout)


class TestLinux:
    @staticmethod
    def _press(pids: list[int], searches: list[MagicMock]) -> tuple[int, MagicMock]:
        """Press Escape for `pids`, each search answering in turn; return status and run."""
        argv = ["Escape", "--pids", *map(str, pids)]
        with (
            _on("linux"),
            patch.object(send_os_key.shutil, "which", return_value=XDOTOOL),
            patch.object(send_os_key.subprocess, "run", side_effect=[*searches, None, None]) as run,
        ):
            return send_os_key.main(argv), run

    def test_the_first_process_with_a_window_is_focused_then_the_key_is_pressed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The onefile bootstrap has no window: the program it unpacked has."""
        status, run = self._press([10, 11, 12], [_found(""), _found("777\n778\n")])

        assert status == 0
        assert [c.args[0] for c in run.call_args_list] == [
            [XDOTOOL, "search", "--onlyvisible", "--pid", "10"],
            [XDOTOOL, "search", "--onlyvisible", "--pid", "11"],
            [XDOTOOL, "windowfocus", "--sync", "777"],
            [XDOTOOL, "key", "Escape"],
        ]
        assert run.call_args_list[-1].kwargs == {"check": True}
        assert capsys.readouterr().out == "send_os_key: pressed Escape\n"

    def test_with_no_window_found_the_key_is_still_pressed(self) -> None:
        """The display holds nothing else, so the key reaches the program anyway."""
        status, run = self._press([10], [_found("")])

        assert status == 0
        assert run.call_args_list[-1].args[0] == [XDOTOOL, "key", "Escape"]
        assert not any("windowfocus" in c.args[0] for c in run.call_args_list)

    def test_without_xdotool_it_says_so(self, capsys: pytest.CaptureFixture[str]) -> None:
        with _on("linux"), patch.object(send_os_key.shutil, "which", return_value=None):
            assert send_os_key.main(["Escape"]) == 1

        assert capsys.readouterr().err == "send_os_key: xdotool is not installed\n"

    def test_a_key_xdotool_could_not_press_fails_it(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        refused = subprocess.CalledProcessError(1, [XDOTOOL, "key", "Escape"])
        with (
            _on("linux"),
            patch.object(send_os_key.shutil, "which", return_value=XDOTOOL),
            patch.object(send_os_key.subprocess, "run", side_effect=refused),
        ):
            assert send_os_key.main(["Escape"]) == 1

        assert "returned non-zero exit status 1" in capsys.readouterr().err


class TestWindows:
    def test_the_processes_running_an_image_are_read_from_the_task_list(self) -> None:
        listing = (
            '"app.exe","4242","Console","1","52,340 K"\n"app.exe","4250","Console","1","9 K"\n'
        )
        with patch.object(send_os_key.subprocess, "run", return_value=_found(listing)) as run:
            assert send_os_key._windows_pids("app.exe") == [4242, 4250]  # noqa: SLF001

        assert run.call_args.args[0][-1] == "IMAGENAME eq app.exe"

    def test_a_task_list_that_names_no_task_gives_none(self) -> None:
        nothing = "INFO: No tasks are running which match the specified criteria.\n"
        with patch.object(send_os_key.subprocess, "run", return_value=_found(nothing)):
            assert send_os_key._windows_pids("app.exe") == []  # noqa: SLF001

    @staticmethod
    def _press(
        *, pids: list[int], window: int | None = 99, in_front: bool = True
    ) -> tuple[int, MagicMock, MagicMock]:
        backend = MagicMock()
        backend.bring_to_front.return_value = in_front
        with (
            _on("win32"),
            patch.object(gui_probe_win32, "Win32Backend", return_value=backend),
            patch.object(gui_probe_win32, "find_window_of_processes", return_value=window) as find,
            patch.object(send_os_key, "_windows_pids", return_value=pids),
        ):
            return send_os_key.main(["Escape", "--image", "app.exe"]), backend, find

    def test_the_key_goes_to_the_window_of_the_image_s_processes(self) -> None:
        status, backend, find = self._press(pids=[APP_PID, 4250])

        assert status == 0
        find.assert_called_once_with({APP_PID, 4250})
        assert backend.mock_calls == [call.bring_to_front(99), call.send_key("Escape")]

    @pytest.mark.parametrize(
        ("answers", "says"),
        [
            pytest.param({"pids": []}, "no process is running app.exe", id="no process"),
            pytest.param(
                {"pids": [APP_PID], "window": None},
                f"no visible window belongs to app.exe (processes [{APP_PID}])",
                id="no window",
            ),
            pytest.param(
                {"pids": [APP_PID], "in_front": False},
                "the window would not come to the front, so the key would go elsewhere",
                id="not in front",
            ),
        ],
    )
    def test_no_key_is_sent_where_it_could_go_elsewhere(
        self, capsys: pytest.CaptureFixture[str], answers: dict, says: str
    ) -> None:
        status, backend, _ = self._press(**answers)

        assert status == 1
        backend.send_key.assert_not_called()
        assert capsys.readouterr().err == f"send_os_key: {says}\n"

    def test_the_image_is_needed(self, capsys: pytest.CaptureFixture[str]) -> None:
        with _on("win32"), pytest.raises(SystemExit):
            send_os_key.main(["Escape", "--pids", "1"])

        assert "--image is needed on Windows" in capsys.readouterr().err


class TestMacos:
    def test_each_process_gets_the_key_down_then_up_and_every_event_is_released(self) -> None:
        quartz, core = MagicMock(), MagicMock()
        quartz.CGEventCreateKeyboardEvent.side_effect = ["e1", "e2", "e3", "e4"]
        with (
            _on("darwin"),
            patch.object(send_os_key.ctypes, "CDLL", side_effect=[quartz, core]),
            patch.object(send_os_key.ctypes.util, "find_library"),
            patch.object(send_os_key.time, "sleep"),
        ):
            assert send_os_key.main(["Escape", "--pids", "10", "11"]) == 0

        assert quartz.CGEventCreateKeyboardEvent.call_args_list == [
            call(None, ESCAPE_CODE, True),  # noqa: FBT003
            call(None, ESCAPE_CODE, False),  # noqa: FBT003
            call(None, ESCAPE_CODE, True),  # noqa: FBT003
            call(None, ESCAPE_CODE, False),  # noqa: FBT003
        ]
        assert quartz.CGEventPostToPid.call_args_list == [
            call(10, "e1"),
            call(10, "e2"),
            call(11, "e3"),
            call(11, "e4"),
        ]
        assert [c.args[0] for c in core.CFRelease.call_args_list] == ["e1", "e2", "e3", "e4"]

    def test_the_processes_are_needed(self, capsys: pytest.CaptureFixture[str]) -> None:
        with _on("darwin"), pytest.raises(SystemExit):
            send_os_key.main(["Escape"])

        assert "--pids is needed on macOS" in capsys.readouterr().err


def test_only_the_keys_the_smoke_test_presses_are_taken() -> None:
    with pytest.raises(SystemExit):
        send_os_key.main(["Tab"])
