"""The Windows build's boot splash: which file takes it down, and deleting it."""

from __future__ import annotations

import tempfile
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from barks_reader.core import boot_splash
from barks_reader.core.boot_splash import boot_splash_file, close_boot_splash

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_PARENT_PID = "4242"
_ENV = "NUITKA_ONEFILE_PARENT"
_SPLASH_NAME = f"onefile_{_PARENT_PID}_splash_feedback.tmp"


@pytest.fixture
def splash_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Give the file an unpacking program with `_PARENT_PID` would be watching.

    Python's temp folder is the only one: TMP and TEMP are unset, as they are off Windows.
    """
    monkeypatch.setenv(_ENV, _PARENT_PID)
    monkeypatch.delenv("TMP", raising=False)
    monkeypatch.delenv("TEMP", raising=False)
    with (
        patch.object(tempfile, "gettempdir", return_value=str(tmp_path)),
        patch.object(boot_splash, "_settled", set()),
    ):
        yield tmp_path / _SPLASH_NAME


class TestBootSplashFile:
    def test_it_is_named_for_the_unpacking_program(self, splash_file: Path) -> None:
        assert boot_splash_file() == splash_file

    @pytest.mark.parametrize("value", ["", "not-a-pid", "-1", "12 34"])
    def test_no_usable_process_id_is_no_splash(
        self, value: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(_ENV, value)
        assert boot_splash_file() is None

    def test_a_process_nothing_unpacked_has_no_splash(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(_ENV, raising=False)
        assert boot_splash_file() is None


class TestCloseBootSplash:
    def test_it_deletes_the_file_and_says_so(
        self, splash_file: Path, loguru_sink: list[str]
    ) -> None:
        splash_file.write_bytes(b"")

        close_boot_splash()

        assert not splash_file.exists()
        assert any("Took down the boot splash." in s for s in loguru_sink)

    def test_a_splash_already_down_is_left_in_silence(
        self, splash_file: Path, loguru_sink: list[str]
    ) -> None:
        splash_file.write_bytes(b"")
        close_boot_splash()
        taken_down = len(loguru_sink)

        close_boot_splash()

        assert not splash_file.exists()
        assert len(loguru_sink) == taken_down

    def test_the_first_look_that_finds_no_file_says_where_it_looked_and_no_later_one(
        self, splash_file: Path, loguru_sink: list[str]
    ) -> None:
        """A splash left up over the reader used to leave nothing in the log to go on."""
        close_boot_splash()
        close_boot_splash()

        lines = [s for s in loguru_sink if "boot splash" in s]
        assert len(lines) == 1
        assert f'No boot splash file to delete in "{splash_file.parent}": ' in lines[0]

    def test_each_unpacking_program_s_missing_file_is_said_once(
        self, splash_file: Path, monkeypatch: pytest.MonkeyPatch, loguru_sink: list[str]
    ) -> None:
        """What is settled is settled for one unpacking program, not for every one after it."""
        close_boot_splash()
        monkeypatch.setenv(_ENV, _PARENT_PID + "1")  # the app, started again

        close_boot_splash()
        close_boot_splash()

        lines = [s for s in loguru_sink if "No boot splash file" in s]
        assert len(lines) == 2  # noqa: PLR2004
        assert splash_file.parent.is_dir()

    @pytest.mark.parametrize("windows_folder", ["TMP", "TEMP"])
    def test_a_file_in_the_temp_folder_windows_chose_is_found_there(
        self,
        splash_file: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        loguru_sink: list[str],
        windows_folder: str,
    ) -> None:
        """The unpacking program asks Windows, which reads TMP first; Python reads TEMP first.

        With the two set to different folders (or TMPDIR set by the shell that started
        the app) the file was looked for in one and made in the other.
        """
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.setenv(windows_folder, str(elsewhere))
        made_by_the_unpacker = elsewhere / _SPLASH_NAME
        made_by_the_unpacker.write_bytes(b"")

        close_boot_splash()

        assert not made_by_the_unpacker.exists()
        assert not splash_file.exists()
        assert any("Took down the boot splash." in s for s in loguru_sink)

    def test_the_folders_looked_in_are_each_named_once(
        self,
        splash_file: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        loguru_sink: list[str],
    ) -> None:
        elsewhere = tmp_path / "elsewhere"
        monkeypatch.setenv("TMP", str(elsewhere))
        monkeypatch.setenv("TEMP", str(splash_file.parent))  # Python's own: not twice

        close_boot_splash()

        (line,) = [s for s in loguru_sink if "No boot splash file" in s]
        assert f'in "{splash_file.parent}", "{elsewhere}": ' in line

    def test_with_no_splash_nothing_is_touched(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(_ENV, raising=False)
        bystander = tmp_path / "onefile__splash_feedback.tmp"
        bystander.write_bytes(b"")

        with patch.object(tempfile, "gettempdir", return_value=str(tmp_path)):
            close_boot_splash()

        assert bystander.exists()

    def test_a_file_that_will_not_go_is_logged_not_raised(
        self, splash_file: Path, loguru_sink: list[str]
    ) -> None:
        splash_file.write_bytes(b"")

        with patch.object(boot_splash.Path, "unlink", side_effect=PermissionError("in use")):
            close_boot_splash()

        assert any("Could not take down the boot splash" in s for s in loguru_sink)
        assert not any("No boot splash file" in s for s in loguru_sink)
