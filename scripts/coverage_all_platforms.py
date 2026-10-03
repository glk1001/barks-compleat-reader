#!/usr/bin/env python3
"""Combine one commit's overnight coverage from Linux, Windows and (optionally) macOS.

Each overnight run measures what its own platform runs: the Linux run
(``run_overnight.sh``) the unit suite and the GUI tests, the Windows and macOS
runs (``run_overnight_desktop.py``) the same plus the code only that platform
reaches (``platform_window_win32.py`` and the like). None alone counts all of it.
This fetches each machine's data over ssh, for the newest commit all have
measured (or ``--commit``), and reports each platform and all of them together,
with what each desktop platform adds to Linux and an HTML report. It is a report
only: each machine's own coverage stage already holds its own figure to a floor.

The data must be of one commit's code, since coverage records line numbers: the
source reported against is that commit's, taken from git (``git archive``), not
this checkout's, which may have moved on. Runs of different commits pair when
their ``src/`` trees are the same (coverage measures nothing else), so a commit
that changed only scripts or docs does not keep the machines apart. The machines'
absolute paths are mapped onto it on combine, the Windows ones written with
backslashes.

Usage: coverage_all_platforms.py LINUX_HOST[:REPO] WINDOWS_HOST[:REPO]
                                 [MACOS_HOST[:REPO]] [--commit SHA]
REPO is relative to the remote home: by default this repo's own path for Linux,
``source/repos/barks-compleat-reader`` for Windows and
``Developer/barks-compleat-reader`` for macOS. Each host needs ssh with a key and
a bash shell (Git Bash on Windows). Output: build/coverage-all/SHA/.
"""

# cspell:ignore rcfile

from __future__ import annotations

import argparse
import io
import re
import shutil
import subprocess
import sys
import tarfile
import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

import coverage

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_ROOT = REPO_ROOT / "build" / "coverage-all"


def measured_dirs(pyproject: Path) -> tuple[str, ...]:
    """Return the directories coverage measures: ``[tool.coverage.run] source``."""
    with pyproject.open("rb") as f:
        return tuple(tomllib.load(f)["tool"]["coverage"]["run"]["source"])


# What a run's coverage covers: the packages' code, not the test suites beside it.
MEASURED_DIRS = measured_dirs(REPO_ROOT / "pyproject.toml")
LINUX, WINDOWS, MACOS = "Linux", "Windows", "macOS"
DEFAULT_WINDOWS_REPO = "source/repos/barks-compleat-reader"
DEFAULT_MACOS_REPO = "Developer/barks-compleat-reader"
DATA_FILES = (".coverage.all", ".coverage.unit", ".coverage.gui")
TOP_FILES = 8

# Prints a line per overnight run, newest first: stamp, summary header, data files.
_LIST_RUNS = r"""
cd "$1" || exit 2
for d in $(ls -1r build/overnight 2>/dev/null | grep '^20'); do
    c="build/overnight/$d/coverage"
    printf '%s\t%s\t' "$d" "$(head -1 "build/overnight/$d/summary.txt" 2>/dev/null)"
    for f in .coverage.all .coverage.unit .coverage.gui; do
        [ -f "$c/$f" ] && printf '%s ' "$f"
    done
    echo
done
"""
_HEADER_COMMIT = re.compile(r"\(([0-9a-f]{7,40})\)")


class CoverageAllError(Exception):
    """A step that cannot go on, with why."""


@dataclass(frozen=True)
class Host:
    platform: str  # LINUX, WINDOWS or MACOS
    name: str
    repo: str  # relative to the remote home

    @property
    def repo_dir_name(self) -> str:
        return PurePosixPath(self.repo).name

    @property
    def path_pattern(self) -> str:
        """Return the coverage [paths] pattern its measured files match."""
        if self.platform == WINDOWS:
            return f"*\\{self.repo_dir_name}\\src\\"
        return f"*/{self.repo_dir_name}/src/"


@dataclass(frozen=True)
class Run:
    stamp: str
    commit: str
    data_files: tuple[str, ...]

    def inputs(self) -> tuple[str, ...]:
        """Return the data files to combine: the run's own combination when it made one."""
        if ".coverage.all" in self.data_files:
            return (".coverage.all",)
        return self.data_files


def parse_host(platform: str, spec: str, default_repo: str) -> Host:
    """Return the host of a `HOST[:REPO]` argument."""
    name, _, repo = spec.partition(":")
    return Host(platform, name, repo or default_repo)


def parse_runs(listing: str) -> list[Run]:
    """Return the runs in a `_LIST_RUNS` listing that measured coverage, newest first."""
    runs = []
    for line in listing.splitlines():
        stamp, _, rest = line.partition("\t")
        header, _, files = rest.partition("\t")
        found = _HEADER_COMMIT.search(header)
        data_files = tuple(f for f in files.split() if f in DATA_FILES)
        if found and data_files:
            runs.append(Run(stamp, found[1], data_files))
    return runs


def same_commit(a: str, b: str) -> bool:
    """Return whether two abbreviations name one commit."""
    return a.startswith(b) or b.startswith(a)


def same_source(src_tree: Callable[[str], str | None]) -> Callable[[str, str], bool]:
    """Return a test of whether two commits measured the same code.

    The same commit, or two whose measured code is one (`src_tree` gives a
    commit's, or None when git does not have it): a commit that changed only
    scripts, docs or tests measured the same lines.
    """

    def same(a: str, b: str) -> bool:
        if same_commit(a, b):
            return True
        tree = src_tree(a)
        return tree is not None and tree == src_tree(b)

    return same


@cache
def git_src_tree(commit: str) -> str | None:
    """Return what identifies a commit's measured code, or None when git here lacks the commit.

    The ids of its MEASURED_DIRS trees, joined ("-" for one the commit has not
    got): not ``src/`` whole, which holds the test suites too, so a commit that
    only added tests (a whole day's coverage work, 2026-10-03) kept the machines'
    runs of one code from pairing.
    """
    git = ["git", "-C", str(REPO_ROOT), "rev-parse", "--verify", "--quiet"]
    if not _git_out([*git, f"{commit}^{{commit}}"]):
        return None
    return " ".join(_git_out([*git, f"{commit}:{d}"]) or "-" for d in MEASURED_DIRS)


def _git_out(argv: list[str]) -> str:
    done = subprocess.run(argv, capture_output=True, text=True, check=False)  # noqa: S603
    return done.stdout.strip()


def pick_runs(
    runs: Mapping[str, Sequence[Run]],
    commit: str | None,
    same: Callable[[str, str], bool] = same_commit,
) -> dict[str, Run]:
    """Return each platform's newest run of one commit (`commit`, or the newest all have).

    `runs` is each platform's runs, newest first; the first platform's order picks
    the commit. `same` says whether another platform's run measured that commit's
    code: by default only a run of that very commit does.
    """
    first, *others = runs
    for run in runs[first]:
        if commit and not same_commit(run.commit, commit):
            continue
        picked = {first: run}
        for platform in others:
            match = next((r for r in runs[platform] if same(run.commit, r.commit)), None)
            if match is None:
                break
            picked[platform] = match
        else:
            return picked
    has = "; ".join(
        f"{platform}: {', '.join(dict.fromkeys(r.commit for r in platform_runs)) or 'none'}"
        for platform, platform_runs in runs.items()
    )
    wanted = f"commit {commit}" if commit else "a commit"
    msg = f"no {wanted} has coverage from every machine ({has})"
    raise CoverageAllError(msg)


def paths_config(source_root: Path, hosts: Sequence[Host]) -> str:
    """Return a coverage config mapping every machine's source paths onto `source_root`."""
    patterns = dict.fromkeys(host.path_pattern for host in hosts)
    lines = ["[paths]", "source =", f"    {source_root}/src/", *(f"    {p}" for p in patterns)]
    return "\n".join(lines) + "\n"


def lines_only_in(extra: coverage.CoverageData, base: coverage.CoverageData) -> dict[str, int]:
    """Return, per file, how many lines `extra` ran that `base` did not."""
    added = {}
    for path in extra.measured_files():
        count = len(set(extra.lines(path) or ()) - set(base.lines(path) or ()))
        if count:
            added[path] = count
    return added


def repo_relative(path: str, repo_dir_names: Sequence[str]) -> str | None:
    """Return a measured file's path within its repo (`src/...`), from any platform."""
    posix = path.replace("\\", "/")
    for name in repo_dir_names:
        _, found, rest = posix.partition(f"/{name}/src/")
        if found:
            return f"src/{rest}"
    return None


def fill_untracked(
    inputs: list[Path], source_root: Path, repo_dir_names: Sequence[str]
) -> list[str]:
    """Copy into `source_root` this checkout's copy of each measured file git does not hold.

    The generated modules (``_version.py``, ``get_panel_bytes.py``) are gitignored,
    so no commit has them, and coverage maps a path only onto a file that exists.
    Return the files copied.
    """
    copied = []
    for data_file in inputs:
        for path in _read(data_file).measured_files():
            rel = repo_relative(path, repo_dir_names)
            if rel is None or (source_root / rel).exists() or not (REPO_ROOT / rel).is_file():
                continue
            (source_root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO_ROOT / rel, source_root / rel)
            copied.append(rel)
    return copied


def _main_checkout() -> Path:
    """Return the repo's main checkout, which a worktree's path is not."""
    common = subprocess.run(  # noqa: S603
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return Path(common).parent


def _ssh(host: Host, script: str) -> str:
    result = subprocess.run(  # noqa: S603
        ["ssh", "-o", "BatchMode=yes", host.name, "bash", "-s", "--", host.repo],  # noqa: S607
        input=script,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = f"{host.name}: listing the overnight runs failed: {result.stderr.strip()}"
        raise CoverageAllError(msg)
    return result.stdout


def _fetch(host: Host, run: Run, dest: Path) -> list[Path]:
    dest.mkdir(parents=True)
    fetched = []
    for name in run.inputs():
        remote = f"{host.name}:{host.repo}/build/overnight/{run.stamp}/coverage/{name}"
        target = dest / name
        result = subprocess.run(  # noqa: S603
            ["scp", "-q", "-o", "BatchMode=yes", remote, str(target)],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            msg = f"copying {remote} failed: {result.stderr.strip()}"
            raise CoverageAllError(msg)
        fetched.append(target)
    return fetched


def _extract_source(commit: str, dest: Path) -> None:
    """Write the commit's `src/` tree under `dest`, from git."""
    archive = subprocess.run(  # noqa: S603
        ["git", "-C", str(REPO_ROOT), "archive", "--format=tar", commit, "src"],  # noqa: S607
        capture_output=True,
        check=False,
    )
    if archive.returncode != 0:
        msg = (
            f"git has no commit {commit} here ({archive.stderr.decode().strip()});"
            " `git fetch` first"
        )
        raise CoverageAllError(msg)
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(dest, filter="data")


def _combine(config: Path, out: Path, inputs: list[Path]) -> None:
    subprocess.run(  # noqa: S603
        [
            *(sys.executable, "-m", "coverage", "combine", "--keep", "--quiet"),
            *(f"--rcfile={config}", f"--data-file={out}", *map(str, inputs)),
        ],
        check=True,
    )


def _total(data: Path) -> str:
    # From the repo root, so pyproject.toml's report settings (omit, ...) apply.
    return subprocess.run(  # noqa: S603
        [
            *(sys.executable, "-m", "coverage", "report", "--format=total", "--precision=1"),
            *("--fail-under=0", f"--data-file={data}"),
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    ).stdout.strip()


def _read(data: Path) -> coverage.CoverageData:
    read = coverage.CoverageData(str(data))
    read.read()
    return read


def _check_mapped(data: coverage.CoverageData, source_root: Path) -> None:
    unmapped = [f for f in data.measured_files() if not Path(f).is_relative_to(source_root)]
    if unmapped:
        msg = f"{len(unmapped)} files did not map onto the commit's source, e.g. {unmapped[0]}"
        raise CoverageAllError(msg)


def _hosts(argv: list[str] | None) -> tuple[list[Host], str | None]:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("linux", help="LINUX_HOST[:REPO]")
    parser.add_argument("windows", help="WINDOWS_HOST[:REPO]")
    parser.add_argument("macos", nargs="?", help="MACOS_HOST[:REPO] (optional)")
    parser.add_argument("--commit", help="the commit to combine (default: the newest of all)")
    args = parser.parse_args(argv)
    hosts = [
        parse_host(LINUX, args.linux, str(_main_checkout().relative_to(Path.home()))),
        parse_host(WINDOWS, args.windows, DEFAULT_WINDOWS_REPO),
    ]
    if args.macos:
        hosts.append(parse_host(MACOS, args.macos, DEFAULT_MACOS_REPO))
    return hosts, args.commit


def main(argv: list[str] | None = None) -> int:
    """Fetch, combine and report; return the exit code."""
    hosts, commit = _hosts(argv)
    try:
        listed = {h.platform: parse_runs(_ssh(h, _LIST_RUNS)) for h in hosts}
        runs = pick_runs(listed, commit, same_source(git_src_tree))
        out = OUT_ROOT / runs[LINUX].commit
        shutil.rmtree(out, ignore_errors=True)
        source_root = out / "source"
        _extract_source(runs[LINUX].commit, source_root)
        config = out / "paths.rc"
        config.write_text(paths_config(source_root, hosts), encoding="utf-8")
        inputs = {
            h.platform: _fetch(h, runs[h.platform], out / f"{h.platform}-data") for h in hosts
        }
        every_input = [path for paths in inputs.values() for path in paths]
        names = list(dict.fromkeys(h.repo_dir_name for h in hosts))
        copied = fill_untracked(every_input, source_root, names)
        data = {h.platform: out / f"{h.platform}.dat" for h in hosts}
        for host in hosts:
            _combine(config, data[host.platform], inputs[host.platform])
        all_data = out / "all.dat"
        _combine(config, all_data, every_input)
        _check_mapped(_read(all_data), source_root)
    except CoverageAllError as exc:
        print(f"coverage-all: {exc}", file=sys.stderr)  # noqa: T201
        return 1

    print(f"coverage-all: commit {runs[LINUX].commit}")  # noqa: T201
    others = {r.commit for r in runs.values()} - {runs[LINUX].commit}
    if others:
        print(f"  with {', '.join(sorted(others))}: the same src/, so the same lines")  # noqa: T201
    if copied:
        print(f"  not in git, this checkout's copy used: {', '.join(copied)}")  # noqa: T201
    for host in hosts:
        total = _total(data[host.platform])
        run = runs[host.platform]
        where = f"({host.name}, run {run.stamp}, {run.commit})"
        print(f"  {host.platform:<8} {total:>5}%  {where}")  # noqa: T201
    print(f"  {'all':<8} {_total(all_data):>5}%")  # noqa: T201
    linux_data = _read(data[LINUX])
    for host in hosts[1:]:
        added = lines_only_in(_read(data[host.platform]), linux_data)
        print(f"  lines only {host.platform} ran: {sum(added.values())}")  # noqa: T201
        for path, count in sorted(added.items(), key=lambda item: -item[1])[:TOP_FILES]:
            print(f"    {count:>5}  {Path(path).relative_to(source_root)}")  # noqa: T201
    html = out / "html"
    subprocess.run(  # noqa: S603
        [
            *(sys.executable, "-m", "coverage", "html", "--quiet", "--fail-under=0"),
            *(f"--data-file={all_data}", "-d", str(html)),
        ],
        check=True,
        cwd=REPO_ROOT,
    )
    print(f"  report: {html / 'index.html'}")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
