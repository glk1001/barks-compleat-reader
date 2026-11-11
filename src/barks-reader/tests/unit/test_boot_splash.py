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


@pytest.fixture
def splash_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Give the file an unpacking program with `_PARENT_PID` would be watching."""
    monkeypatch.setenv(_ENV, _PARENT_PID)
    with patch.object(tempfile, "gettempdir", return_value=str(tmp_path)):
        yield tmp_path / f"onefile_{_PARENT_PID}_splash_feedback.tmp"


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
        close_boot_splash()

        assert not splash_file.exists()
        assert not any("boot splash" in s for s in loguru_sink)

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
