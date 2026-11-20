"""Tests for coverage_all_platforms.py: picking one commit's runs and mapping every platform."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import coverage
import coverage_all_platforms as cap
import pytest
from script_test_helpers import git, write_tree

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

LINUX = cap.Host(cap.LINUX, "gmk", "Prj/barks-compleat-reader")
WINDOWS = cap.Host(cap.WINDOWS, "win", "source/repos/barks-compleat-reader")
MACOS = cap.Host(cap.MACOS, "mac", "Developer/barks-compleat-reader")
WIN_FILE = r"C:\Users\me\source\repos\barks-compleat-reader\src\pkg\src\pkg\mod.py"
LINUX_FILE = "/home/me/Prj/barks-compleat-reader/src/pkg/src/pkg/mod.py"
MAC_FILE = "/Users/me/Developer/barks-compleat-reader/src/pkg/src/pkg/mod.py"
NAMES = ("barks-compleat-reader",)


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

    def test_a_run_still_going_or_stopped_is_passed_over(self) -> None:
        """Its data is only the stages so far: the unit suite, without the GUI tests."""
        listing = (
            "20261007-160548\t==== overnight run, 20261007-160548 (f5985a31):"
            " 9 of 18 stages done ====\t.coverage.unit \n"
            "20261007-120000\t==== overnight run, 20261007-120000 (f5985a31):"
            " stopped during gui, 1h02m in ====\t.coverage.unit \n"
            "20261007-091407\t==== overnight run, 20261007-091407 (f5985a31):"
            " finished in 3h12m ====\t.coverage.all \n"
        )
        assert cap.parse_runs(listing) == [
            cap.Run("20261007-091407", "f5985a31", (".coverage.all",))
        ]

    def test_a_runs_own_combination_is_preferred_to_its_parts(self) -> None:
        run = cap.Run("s", "c", (".coverage.all", ".coverage.unit", ".coverage.gui"))
        assert run.inputs() == (".coverage.all",)
        assert cap.Run("s", "c", (".coverage.unit",)).inputs() == (".coverage.unit",)

    def test_the_newest_commit_both_machines_measured(self) -> None:
        linux = [_run("3", "cccccccc"), _run("2", "bbbbbbbb"), _run("1", "aaaaaaaa")]
        windows = [_run("9", "bbbbbbbb"), _run("8", "aaaaaaaa")]
        picked = cap.pick_runs({cap.LINUX: linux, cap.WINDOWS: windows}, None)
        assert picked == {cap.LINUX: linux[1], cap.WINDOWS: windows[0]}

    def test_the_newest_commit_all_three_measured(self) -> None:
        """A commit the Mac has not run yet is passed over for one every machine ran."""
        linux = [_run("3", "cccccccc"), _run("2", "bbbbbbbb")]
        windows = [_run("9", "cccccccc"), _run("8", "bbbbbbbb")]
        macos = [_run("5", "bbbbbbbb")]
        picked = cap.pick_runs({cap.LINUX: linux, cap.WINDOWS: windows, cap.MACOS: macos}, None)
        assert picked == {cap.LINUX: linux[1], cap.WINDOWS: windows[1], cap.MACOS: macos[0]}

    def test_a_named_commit_by_abbreviation(self) -> None:
        linux = [_run("2", "bbbbbbbb"), _run("1", "aaaaaaaa")]
        windows = [_run("9", "bbbbbbbb"), _run("8", "aaaaaaaa")]
        picked = cap.pick_runs({cap.LINUX: linux, cap.WINDOWS: windows}, "aaaa")
        assert picked == {cap.LINUX: linux[1], cap.WINDOWS: windows[1]}

    def test_runs_of_commits_with_the_same_source_pair(self) -> None:
        """A commit that changed only scripts or docs keeps the code the others measured."""
        trees = {"cccccccc": "tree1", "bbbbbbbb": "tree1", "aaaaaaaa": "tree0"}
        same = cap.same_source(trees.get)
        linux = [_run("3", "cccccccc")]
        windows = [_run("9", "bbbbbbbb"), _run("8", "aaaaaaaa")]
        picked = cap.pick_runs({cap.LINUX: linux, cap.WINDOWS: windows}, None, same)
        assert picked == {cap.LINUX: linux[0], cap.WINDOWS: windows[0]}

    def test_a_commit_git_does_not_have_pairs_only_with_itself(self) -> None:
        same = cap.same_source({"aaaaaaaa": "tree0"}.get)
        assert same("aaaaaaaa", "aaaa")
        assert not same("ffffffff", "eeeeeeee")  # neither known: no tree to compare
        assert not same("aaaaaaaa", "ffffffff")

    @pytest.mark.usefixtures("no_outer_git")
    def test_the_src_tree_follows_src_alone(self, tmp_path: Path) -> None:
        """A real repository: docs- and tests-only commits keep it, a code commit changes it."""

        def commit(path: str, text: str) -> str:
            write_tree(tmp_path, {path: text})
            git(tmp_path, "add", "-A")
            git(tmp_path, "commit", "-qm", path)
            return git(tmp_path, "rev-parse", "HEAD")

        git(tmp_path, "init", "-q")
        first = commit("src/pkg/src/a.py", "a = 1\n")
        docs = commit("docs/notes.md", "notes\n")
        tests = commit("src/pkg/tests/test_a.py", "def test_a(): ...\n")
        code = commit("src/pkg/src/a.py", "a = 2\n")
        cap.git_src_tree.cache_clear()
        try:
            with (
                patch.object(cap, "REPO_ROOT", tmp_path),
                patch.object(cap, "MEASURED_DIRS", ("src/pkg/src", "src/other/src")),
            ):
                assert cap.git_src_tree(first) == cap.git_src_tree(docs)
                assert cap.git_src_tree(tests) == cap.git_src_tree(first)
                assert cap.git_src_tree(code) != cap.git_src_tree(first)
                assert cap.git_src_tree("0" * 40) is None
        finally:
            cap.git_src_tree.cache_clear()

    def test_the_measured_dirs_are_coverages_own(self) -> None:
        assert cap.measured_dirs(cap.REPO_ROOT / "pyproject.toml") == cap.MEASURED_DIRS
        assert "src/barks-reader/src/barks_reader" in cap.MEASURED_DIRS
        assert not any("/tests" in d for d in cap.MEASURED_DIRS)

    def test_no_commit_in_common_names_what_each_machine_has(self) -> None:
        runs = {
            cap.LINUX: [_run("2", "bbbbbbbb")],
            cap.WINDOWS: [_run("1", "aaaaaaaa")],
            cap.MACOS: [],
        }
        match = r"Linux: bbbbbbbb; Windows: aaaaaaaa; macOS: none"
        with pytest.raises(cap.CoverageAllError, match=match):
            cap.pick_runs(runs, None)


class TestPaths:
    def test_a_host_without_a_repo_takes_the_default(self) -> None:
        assert cap.parse_host(cap.WINDOWS, "win", "d/r") == cap.Host(cap.WINDOWS, "win", "d/r")
        assert cap.parse_host(cap.MACOS, "mac:x/y", "d/r") == cap.Host(cap.MACOS, "mac", "x/y")

    def test_each_platforms_path_within_the_repo(self) -> None:
        for path in (WIN_FILE, LINUX_FILE, MAC_FILE):
            assert cap.repo_relative(path, NAMES) == "src/pkg/src/pkg/mod.py"
        assert cap.repo_relative("/elsewhere/mod.py", NAMES) is None

    def test_one_pattern_serves_the_machines_that_share_one(self, tmp_path: Path) -> None:
        config = cap.paths_config(tmp_path, [LINUX, WINDOWS, MACOS])
        assert config.splitlines()[2:] == [
            f"    {tmp_path}/src/",
            "    */barks-compleat-reader/src/",
            "    *\\barks-compleat-reader\\src\\",
        ]

    def test_every_machines_data_lands_on_the_commits_source(self, tmp_path: Path) -> None:
        source_root = tmp_path / "source"
        module = source_root / "src" / "pkg" / "src" / "pkg" / "mod.py"
        module.parent.mkdir(parents=True)
        module.write_text("a = 1\nb = 2\nc = 3\nd = 4\n", encoding="utf-8")
        config = tmp_path / "paths.rc"
        config.write_text(cap.paths_config(source_root, [LINUX, WINDOWS, MACOS]), encoding="utf-8")
        inputs = [
            _data(tmp_path / "linux.dat", {LINUX_FILE: [1]}),
            _data(tmp_path / "win.dat", {WIN_FILE: [1, 3]}),
            _data(tmp_path / "mac.dat", {MAC_FILE: [4]}),
        ]
        combined = tmp_path / "all.dat"
        cap._combine(config, combined, inputs)  # noqa: SLF001
        data = cap._read(combined)  # noqa: SLF001
        cap._check_mapped(data, source_root)  # noqa: SLF001
        assert data.measured_files() == {str(module)}
        assert sorted(data.lines(str(module)) or []) == [1, 3, 4]

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
        with patch.object(cap, "REPO_ROOT", checkout):
            assert cap.fill_untracked(inputs, source_root, NAMES) == ["src/pkg/src/pkg/mod.py"]
            # Once there, it is not copied again.
            assert cap.fill_untracked(inputs, source_root, NAMES) == []
        assert (source_root / "src/pkg/src/pkg/mod.py").read_text(encoding="utf-8") == "v = 1\n"


class TestHosts:
    def test_the_mac_is_optional(self) -> None:
        with patch.object(cap, "_main_checkout", return_value=cap.Path.home() / "repo"):
            hosts, commit = cap._hosts(["gmk", "win"])  # noqa: SLF001
            assert [h.platform for h in hosts] == [cap.LINUX, cap.WINDOWS]
            assert commit is None
            hosts, _ = cap._hosts(["gmk", "win", "mac", "--commit", "abc1234"])  # noqa: SLF001
        assert [h.platform for h in hosts] == [cap.LINUX, cap.WINDOWS, cap.MACOS]
        assert hosts[2] == cap.Host(cap.MACOS, "mac", cap.DEFAULT_MACOS_REPO)


def test_lines_only_windows_ran(tmp_path: Path) -> None:
    linux = cap._read(_data(tmp_path / "l.dat", {"/s/a.py": [1, 2], "/s/b.py": [1]}))  # noqa: SLF001
    windows = cap._read(_data(tmp_path / "w.dat", {"/s/a.py": [2, 3, 4], "/s/c.py": [5]}))  # noqa: SLF001
    assert cap.lines_only_in(windows, linux) == {"/s/a.py": 2, "/s/c.py": 1}


class TestRemoteSteps:
    """What goes to ssh and scp, and what a refusal says: the machines are not called."""

    def test_the_listing_script_runs_in_the_host_s_repo(self) -> None:
        done = MagicMock(returncode=0, stdout="a listing\n")
        with patch.object(cap.subprocess, "run", return_value=done) as run:
            assert cap._ssh(LINUX, "ls build") == "a listing\n"  # noqa: SLF001

        assert run.call_args.args[0][-5:] == ["gmk", "bash", "-s", "--", LINUX.repo]
        assert run.call_args.kwargs["input"] == "ls build"

    def test_a_host_that_cannot_be_reached_is_named(self) -> None:
        done = MagicMock(returncode=255, stderr="ssh: connect to host gmk: timed out\n")
        with (
            patch.object(cap.subprocess, "run", return_value=done),
            pytest.raises(cap.CoverageAllError, match=r"^gmk: listing the overnight runs failed"),
        ):
            cap._ssh(LINUX, "ls build")  # noqa: SLF001

    def test_a_run_s_parts_are_copied_from_its_coverage_folder(self, tmp_path: Path) -> None:
        run = cap.Run("20261002-040000", "aa630aa3", (".coverage.unit", ".coverage.gui"))
        with patch.object(cap.subprocess, "run", return_value=MagicMock(returncode=0)) as scp:
            fetched = cap._fetch(WINDOWS, run, tmp_path / "win-data")  # noqa: SLF001

        assert fetched == [tmp_path / "win-data" / name for name in run.data_files]
        assert (tmp_path / "win-data").is_dir()
        folder = f"win:{WINDOWS.repo}/build/overnight/20261002-040000/coverage"
        assert [c.args[0][-2] for c in scp.call_args_list] == [
            f"{folder}/.coverage.unit",
            f"{folder}/.coverage.gui",
        ]

    def test_a_copy_that_fails_names_the_file(self, tmp_path: Path) -> None:
        refused = MagicMock(returncode=1, stderr="scp: No such file or directory\n")
        with (
            patch.object(cap.subprocess, "run", return_value=refused),
            pytest.raises(cap.CoverageAllError, match=r"coverage/\.coverage\.all failed: scp: No"),
        ):
            cap._fetch(LINUX, _run("20261002-040000", "aa630aa3"), tmp_path / "data")  # noqa: SLF001


MODULE = "src/pkg/src/pkg/mod.py"


@pytest.fixture
def checkout(tmp_path: Path, no_outer_git: None) -> Iterator[tuple[Path, str]]:  # noqa: ARG001
    """Make a throwaway repository with one module committed; yield it and the commit."""
    repo = tmp_path / "barks-compleat-reader"
    repo.mkdir()
    git(repo, "init", "-q")
    write_tree(repo, {MODULE: "a = 1\nb = 2\nc = 3\nd = 4\n", "docs/notes.md": "notes\n"})
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "the module")
    commit = git(repo, "rev-parse", "--short=8", "HEAD")
    cap.git_src_tree.cache_clear()
    with (
        patch.object(cap, "REPO_ROOT", repo),
        patch.object(cap, "OUT_ROOT", tmp_path / "coverage-all"),
        patch.object(cap, "MEASURED_DIRS", ("src/pkg/src",)),
    ):
        yield repo, commit
    cap.git_src_tree.cache_clear()


class TestLocalSteps:
    def test_a_commit_s_src_tree_is_written_out_and_nothing_else(
        self, checkout: tuple[Path, str], tmp_path: Path
    ) -> None:
        _, commit = checkout

        cap._extract_source(commit, tmp_path / "source")  # noqa: SLF001

        written = tmp_path / "source" / MODULE
        assert written.read_text(encoding="utf-8") == "a = 1\nb = 2\nc = 3\nd = 4\n"
        assert not (tmp_path / "source" / "docs").exists()

    @pytest.mark.usefixtures("checkout")
    def test_a_commit_git_does_not_have_says_to_fetch(self, tmp_path: Path) -> None:
        with pytest.raises(cap.CoverageAllError, match=r"no commit 0123abcd here .*`git fetch`"):
            cap._extract_source("0123abcd", tmp_path / "source")  # noqa: SLF001

    def test_the_main_checkout_is_where_the_git_folder_is(self, checkout: tuple[Path, str]) -> None:
        repo, _ = checkout

        assert cap._main_checkout().resolve() == repo.resolve()  # noqa: SLF001


class TestMain:
    """The whole run on one throwaway commit, with only ssh and scp stood in for."""

    @staticmethod
    def _listing(commit: str) -> str:
        header = f"==== overnight run, 20261002-040000 ({commit}): finished ===="
        return f"20261002-040000\t{header}\t.coverage.all \n"

    @staticmethod
    def _main(listing: str, lines: dict[str, dict[str, list[int]]]) -> int:
        """Run for a Linux and a Windows machine whose runs measured `lines`, by platform."""

        def fetch(host: cap.Host, _run: cap.Run, dest: Path) -> list[Path]:
            dest.mkdir(parents=True)
            return [_data(dest / ".coverage.all", lines[host.platform])]

        with (
            patch.object(cap, "_main_checkout", return_value=cap.Path.home() / "Prj" / "reader"),
            patch.object(cap, "_ssh", return_value=listing),
            patch.object(cap, "_fetch", side_effect=fetch),
        ):
            return cap.main(["gmk:Prj/barks-compleat-reader", "win"])

    def test_each_machine_s_lines_are_combined_and_reported(
        self, checkout: tuple[Path, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _, commit = checkout
        lines = {cap.LINUX: {LINUX_FILE: [1, 2]}, cap.WINDOWS: {WIN_FILE: [2, 3]}}

        assert self._main(self._listing(commit), lines) == 0

        out = capsys.readouterr().out.splitlines()
        assert out[0] == f"coverage-all: commit {commit}"
        totals = {line.split()[0]: line.split()[1] for line in out[1:4]}
        assert totals == {"Linux": "50.0%", "Windows": "50.0%", "all": "75.0%"}
        assert f"(gmk, run 20261002-040000, {commit})" in out[1]
        assert "  lines only Windows ran: 1" in out
        assert out[-2].split() == ["1", str(cap.Path(MODULE))]
        report = tmp_path / "coverage-all" / commit / "html" / "index.html"
        assert out[-1] == f"  report: {report}"
        assert report.is_file()

    def test_a_machine_with_no_run_of_the_commit_fails_it_and_says_what_each_has(
        self, checkout: tuple[Path, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        _, commit = checkout

        with (
            patch.object(cap, "_main_checkout", return_value=cap.Path.home() / "Prj" / "reader"),
            patch.object(cap, "_ssh", side_effect=[self._listing(commit), ""]),
        ):
            assert cap.main(["gmk", "win"]) == 1

        err = capsys.readouterr().err
        assert err.startswith("coverage-all: no a commit has coverage from every machine")
        assert f"Linux: {commit}; Windows: none" in err
