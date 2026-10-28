"""Tests for the pruning of the standalone app's unpack folders."""

# cspell:ignore LOCALAPPDATA libpython

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import prune_onefile_cache as poc

if TYPE_CHECKING:
    import pytest


def _versions(root: Path, *names: str) -> list[Path]:
    """Make one unpack folder per name, newest first, a day apart."""
    folders = []
    for age, name in enumerate(names):
        folder = root / name
        (folder / "lib").mkdir(parents=True)
        (folder / "barks-reader-linux").write_bytes(b"x" * 1000)
        (folder / "lib" / "libpython.so").write_bytes(b"y" * 500)
        stamp = 1_800_000_000 - age * 86_400
        os.utime(folder, (stamp, stamp))
        folders.append(folder)
    return folders


def _left(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir())


class TestUnpackRoot:
    def test_linux_uses_the_cache_folder_under_home(self, tmp_path: Path) -> None:
        assert poc.unpack_root("linux", {}, tmp_path) == tmp_path / ".cache" / "BarksReader"

    def test_an_absolute_xdg_cache_home_wins(self, tmp_path: Path) -> None:
        environ = {"XDG_CACHE_HOME": "/var/cache/greg"}
        assert poc.unpack_root("linux", environ, tmp_path) == Path("/var/cache/greg/BarksReader")

    def test_a_relative_xdg_cache_home_is_ignored_as_nuitka_ignores_it(
        self, tmp_path: Path
    ) -> None:
        environ = {"XDG_CACHE_HOME": "cache"}
        assert poc.unpack_root("linux", environ, tmp_path) == tmp_path / ".cache" / "BarksReader"

    def test_windows_uses_local_app_data(self, tmp_path: Path) -> None:
        environ = {"LOCALAPPDATA": str(tmp_path / "Local")}
        assert poc.unpack_root("win32", environ, tmp_path) == tmp_path / "Local" / "BarksReader"


class TestPrune:
    def test_the_newest_three_stay_and_the_rest_go(self, tmp_path: Path) -> None:
        _versions(tmp_path, "1.0.0.605", "1.0.0.604", "1.0.0.603", "1.0.0.602", "1.0.0.601")
        assert poc.prune(tmp_path, 3, []) == 0
        assert _left(tmp_path) == ["1.0.0.603", "1.0.0.604", "1.0.0.605"]

    def test_age_is_by_modification_time_not_by_name(self, tmp_path: Path) -> None:
        # Newest first: an old 0.0.0 build started again yesterday still stays.
        _versions(tmp_path, "0.0.0.231", "1.0.0.9", "1.0.0.10")
        assert poc.prune(tmp_path, 1, []) == 0
        assert _left(tmp_path) == ["0.0.0.231"]

    def test_an_old_folder_a_process_runs_from_stays(self, tmp_path: Path) -> None:
        folders = _versions(tmp_path, "1.0.0.603", "1.0.0.602", "1.0.0.601")
        running = [folders[2] / "barks-reader-linux"]
        assert poc.prune(tmp_path, 1, running) == 0
        assert _left(tmp_path) == ["1.0.0.601", "1.0.0.603"]

    def test_a_folder_an_interrupted_run_left_aside_goes(self, tmp_path: Path) -> None:
        _versions(tmp_path, "1.0.0.603.deleting", "1.0.0.602")
        assert poc.prune(tmp_path, 3, []) == 0
        assert _left(tmp_path) == ["1.0.0.602"]

    def test_a_dry_run_removes_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _versions(tmp_path, "1.0.0.602", "1.0.0.601")
        assert poc.prune(tmp_path, 1, [], dry_run=True) == 0
        assert _left(tmp_path) == ["1.0.0.601", "1.0.0.602"]
        assert "1.0.0.601: would remove" in capsys.readouterr().out

    def test_no_unpack_folder_is_nothing_to_prune(self, tmp_path: Path) -> None:
        assert poc.prune(tmp_path / "BarksReader", 3, []) == 0

    def test_a_folder_that_cannot_be_moved_aside_is_kept_without_failing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _versions(tmp_path, "1.0.0.602", "1.0.0.601")

        def refuse(_self: Path, _target: Path) -> Path:
            msg = "in use"
            raise PermissionError(msg)

        monkeypatch.setattr(Path, "rename", refuse)
        assert poc.prune(tmp_path, 1, []) == 0
        assert _left(tmp_path) == ["1.0.0.601", "1.0.0.602"]

    def test_a_delete_that_fails_fails_the_prune(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _versions(tmp_path, "1.0.0.602", "1.0.0.601")

        def fail(_path: Path) -> None:
            msg = "read-only file system"
            raise OSError(msg)

        monkeypatch.setattr(poc.shutil, "rmtree", fail)
        assert poc.prune(tmp_path, 1, []) == 1

    def test_the_freed_size_is_reported(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _versions(tmp_path, "1.0.0.602", "1.0.0.601")
        poc.prune(tmp_path, 1, [])
        out = capsys.readouterr().out
        assert "1.0.0.601: removed" in out
        assert "freed 0 MB" in out
