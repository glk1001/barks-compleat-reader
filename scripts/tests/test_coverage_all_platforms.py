"""Tests for coverage_all_platforms.py: picking one commit's runs and mapping both platforms."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import coverage
import coverage_all_platforms as cap
import pytest

if TYPE_CHECKING:
    from pathlib import Path

LINUX = cap.Host("gmk", "Prj/barks-compleat-reader")
WINDOWS = cap.Host("win", "source/repos/barks-compleat-reader")
WIN_FILE = r"C:\Users\me\source\repos\barks-compleat-reader\src\pkg\src\pkg\mod.py"
LINUX_FILE = "/home/me/Prj/barks-compleat-reader/src/pkg/src/pkg/mod.py"


def _run(stamp: str, commit: str) -> cap.Run:
    return cap.Run(stamp, commit, (".coverage.all",))


def _data(path: Path, lines: dict[str, list[int]]) -> Path:
    data = coverage.CoverageData(str(path))
    data.add_lines(lines)
    data.write()
    return path


class TestRuns:
    def test_only_runs_that_measured_coverage_are_listed(self) -> None:
        listing = (
            "20261002-040000\t==== overnight run, 20261002-040000 (aa630aa3): finished ====\t"
            ".coverage.unit .coverage.gui \n"
            "20261001-200218\t==== overnight run, 20261001-200218 (3c1aedd9): finished ====\t\n"
            "20261001-120000\t\t.coverage.all \n"  # still running: no header yet
        )
        assert cap.parse_runs(listing) == [
            cap.Run("20261002-040000", "aa630aa3", (".coverage.unit", ".coverage.gui"))
        ]

    def test_a_runs_own_combination_is_preferred_to_its_parts(self) -> None:
        run = cap.Run("s", "c", (".coverage.all", ".coverage.unit", ".coverage.gui"))
        assert run.inputs() == (".coverage.all",)
        assert cap.Run("s", "c", (".coverage.unit",)).inputs() == (".coverage.unit",)

    def test_the_newest_commit_both_machines_measured(self) -> None:
        linux = [_run("3", "cccccccc"), _run("2", "bbbbbbbb"), _run("1", "aaaaaaaa")]
        windows = [_run("9", "bbbbbbbb"), _run("8", "aaaaaaaa")]
        assert cap.pick_runs(linux, windows, None) == (linux[1], windows[0])

    def test_a_named_commit_by_abbreviation(self) -> None:
        linux = [_run("2", "bbbbbbbb"), _run("1", "aaaaaaaa")]
        windows = [_run("9", "bbbbbbbb"), _run("8", "aaaaaaaa")]
        assert cap.pick_runs(linux, windows, "aaaa") == (linux[1], windows[1])

    def test_no_commit_in_common_names_what_each_machine_has(self) -> None:
        with pytest.raises(cap.CoverageAllError, match=r"Linux: bbbbbbbb; Windows: aaaaaaaa"):
            cap.pick_runs([_run("2", "bbbbbbbb")], [_run("1", "aaaaaaaa")], None)


class TestPaths:
    def test_a_host_without_a_repo_takes_the_default(self) -> None:
        assert cap.parse_host("win", "d/r") == cap.Host("win", "d/r")
        assert cap.parse_host("win:x/y", "d/r") == cap.Host("win", "x/y")

    def test_either_platforms_path_within_the_repo(self) -> None:
        names = (LINUX.repo_dir_name, WINDOWS.repo_dir_name)
        assert cap.repo_relative(WIN_FILE, names) == "src/pkg/src/pkg/mod.py"
        assert cap.repo_relative(LINUX_FILE, names) == "src/pkg/src/pkg/mod.py"
        assert cap.repo_relative("/elsewhere/mod.py", names) is None

    def test_both_machines_data_lands_on_the_commits_source(self, tmp_path: Path) -> None:
        source_root = tmp_path / "source"
        module = source_root / "src" / "pkg" / "src" / "pkg" / "mod.py"
        module.parent.mkdir(parents=True)
        module.write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
        config = tmp_path / "paths.rc"
        config.write_text(cap.paths_config(source_root, LINUX, WINDOWS), encoding="utf-8")
        inputs = [
            _data(tmp_path / "linux.dat", {LINUX_FILE: [1]}),
            _data(tmp_path / "win.dat", {WIN_FILE: [1, 3]}),
        ]
        combined = tmp_path / "all.dat"
        cap._combine(config, combined, inputs)  # noqa: SLF001
        data = cap._read(combined)  # noqa: SLF001
        cap._check_mapped(data, source_root)  # noqa: SLF001
        assert data.measured_files() == {str(module)}
        assert sorted(data.lines(str(module)) or []) == [1, 3]

    def test_a_file_that_maps_nowhere_is_refused(self, tmp_path: Path) -> None:
        data = cap._read(_data(tmp_path / "x.dat", {"/elsewhere/mod.py": [1]}))  # noqa: SLF001
        with pytest.raises(cap.CoverageAllError, match="did not map"):
            cap._check_mapped(data, tmp_path / "source")  # noqa: SLF001

    def test_a_generated_module_git_lacks_comes_from_this_checkout(self, tmp_path: Path) -> None:
        checkout = tmp_path / "checkout"
        generated = checkout / "src" / "pkg" / "src" / "pkg" / "mod.py"
        generated.parent.mkdir(parents=True)
        generated.write_text("v = 1\n", encoding="utf-8")
        source_root = tmp_path / "source"
        inputs = [_data(tmp_path / "win.dat", {WIN_FILE: [1]})]
        names = (LINUX.repo_dir_name, WINDOWS.repo_dir_name)
        with patch.object(cap, "REPO_ROOT", checkout):
            assert cap.fill_untracked(inputs, source_root, names) == ["src/pkg/src/pkg/mod.py"]
            # Once there, it is not copied again.
            assert cap.fill_untracked(inputs, source_root, names) == []
        assert (source_root / "src/pkg/src/pkg/mod.py").read_text(encoding="utf-8") == "v = 1\n"


def test_lines_only_windows_ran(tmp_path: Path) -> None:
    linux = cap._read(_data(tmp_path / "l.dat", {"/s/a.py": [1, 2], "/s/b.py": [1]}))  # noqa: SLF001
    windows = cap._read(_data(tmp_path / "w.dat", {"/s/a.py": [2, 3, 4], "/s/c.py": [5]}))  # noqa: SLF001
    assert cap.lines_only_in(windows, linux) == {"/s/a.py": 2, "/s/c.py": 1}
