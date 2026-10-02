"""Tests for check_macos_overnight_host.py: what it makes of each answer, on every platform.

The machine's parts call macOS tools; what is tested here is what each check makes
of their answers, and of the repo's files.
"""

# cspell:ignore sysadminctl

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import check_macos_overnight_host as ch
import check_windows_overnight_host as shared
import run_overnight_desktop as rw

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

NOT_THIS_PLATFORM = 2  # main()'s exit status off macOS


class TestCpiDb:
    def test_the_database_is_ok(self, tmp_path: Path) -> None:
        db = tmp_path / "cpi.db"
        db.write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
        assert ch.cpi_db_check(db)[0] == "OK"

    def test_the_lfs_pointer_fails_saying_how_to_fetch_it(self, tmp_path: Path) -> None:
        db = tmp_path / "cpi.db"
        db.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:ab\nsize 65073152\n")
        status, text = ch.cpi_db_check(db)
        assert status == "FAIL"
        assert "git lfs pull" in text

    def test_no_file_fails(self, tmp_path: Path) -> None:
        assert ch.cpi_db_check(tmp_path / "cpi.db")[0] == "FAIL"


class TestHooks:
    def test_the_prek_hook(self) -> None:
        assert ch.hooks_check('exec "$PREK" hook-impl --hook-type=pre-push -- "$@"')[0] == "OK"

    def test_the_lfs_hook_alone_warns(self) -> None:
        """`git lfs install` claims the pre-push slot; prek must be installed after it."""
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


def test_the_free_memory_minimum_follows_the_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    """The shared check judges free memory by the runner's machine-sized minimum, not 6 GB."""
    monkeypatch.delenv("BARKS_OVERNIGHT_MIN_FREE_MB", raising=False)
    with (
        patch.object(rw, "available_mb", return_value=3000),
        patch.object(rw, "machine_memory_defaults", return_value=(2048, 3072)),
    ):
        status, text = shared.memory_check()
    assert status == "OK"
    assert "needs 2,048" in text
