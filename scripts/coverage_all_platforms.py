#!/usr/bin/env python3
"""Combine one commit's overnight coverage from a Linux and a Windows machine.

Each overnight run measures what its own platform runs: the Linux run
(``run_overnight.sh``) the unit suite and the GUI tests, the Windows run
(``run_overnight_windows.py``) the same plus the code only Windows reaches
(``platform_window_win32.py`` and the like). Neither alone counts all of it. This
fetches both machines' data over ssh, for the newest commit both have measured
(or ``--commit``), and reports Linux, Windows and the two together, with what
Windows adds and an HTML report. It is a report only: each machine's own coverage
stage already holds its own figure to a floor.

The data must be of one commit, since coverage records line numbers: the source
reported against is that commit's, taken from git (``git archive``), not this
checkout's, which may have moved on. The machines' absolute paths are mapped onto
it on combine, the Windows ones written with backslashes.

Usage: coverage_all_platforms.py LINUX_HOST[:REPO] WINDOWS_HOST[:REPO] [--commit SHA]
REPO is relative to the remote home: by default this repo's own path for Linux,
``source/repos/barks-compleat-reader`` for Windows. Both hosts need ssh with a
key and a bash login shell (Git Bash on Windows). Output: build/coverage-all/SHA/.
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
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import coverage

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_ROOT = REPO_ROOT / "build" / "coverage-all"
DEFAULT_WINDOWS_REPO = "source/repos/barks-compleat-reader"
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
    name: str
    repo: str  # relative to the remote home

    @property
    def repo_dir_name(self) -> str:
        return PurePosixPath(self.repo).name


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


def parse_host(spec: str, default_repo: str) -> Host:
    """Return the host of a `HOST[:REPO]` argument."""
    name, _, repo = spec.partition(":")
    return Host(name, repo or default_repo)


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


def pick_runs(linux: list[Run], windows: list[Run], commit: str | None) -> tuple[Run, Run]:
    """Return the newest Linux run and Windows run of one commit (`commit`, or the newest)."""
    for lin in linux:
        if commit and not same_commit(lin.commit, commit):
            continue
        for win in windows:
            if same_commit(lin.commit, win.commit):
                return lin, win
    lin_commits = ", ".join(dict.fromkeys(r.commit for r in linux)) or "none"
    win_commits = ", ".join(dict.fromkeys(r.commit for r in windows)) or "none"
    wanted = f"commit {commit}" if commit else "a commit"
    msg = (
        f"no {wanted} has coverage from both machines"
        f" (Linux: {lin_commits}; Windows: {win_commits})"
    )
    raise CoverageAllError(msg)


def paths_config(source_root: Path, linux: Host, windows: Host) -> str:
    """Return a coverage config mapping both machines' source paths onto `source_root`."""
    return (
        "[paths]\n"
        "source =\n"
        f"    {source_root}/src/\n"
        f"    */{linux.repo_dir_name}/src/\n"
        f"    *\\{windows.repo_dir_name}\\src\\\n"
    )


def lines_only_in(extra: coverage.CoverageData, base: coverage.CoverageData) -> dict[str, int]:
    """Return, per file, how many lines `extra` ran that `base` did not."""
    added = {}
    for path in extra.measured_files():
        count = len(set(extra.lines(path) or ()) - set(base.lines(path) or ()))
        if count:
            added[path] = count
    return added


def repo_relative(path: str, repo_dir_names: tuple[str, ...]) -> str | None:
    """Return a measured file's path within its repo (`src/...`), from either platform."""
    posix = path.replace("\\", "/")
    for name in repo_dir_names:
        _, found, rest = posix.partition(f"/{name}/src/")
        if found:
            return f"src/{rest}"
    return None


def fill_untracked(
    inputs: list[Path], source_root: Path, repo_dir_names: tuple[str, ...]
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
    unmapped = [f for f in data.measured_files() if not f.startswith(f"{source_root}/")]
    if unmapped:
        msg = f"{len(unmapped)} files did not map onto the commit's source, e.g. {unmapped[0]}"
        raise CoverageAllError(msg)


def main(argv: list[str] | None = None) -> int:
    """Fetch, combine and report; return the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("linux", help="LINUX_HOST[:REPO]")
    parser.add_argument("windows", help="WINDOWS_HOST[:REPO]")
    parser.add_argument("--commit", help="the commit to combine (default: the newest of both)")
    args = parser.parse_args(argv)
    linux = parse_host(args.linux, str(_main_checkout().relative_to(Path.home())))
    windows = parse_host(args.windows, DEFAULT_WINDOWS_REPO)
    try:
        lin_run, win_run = pick_runs(
            parse_runs(_ssh(linux, _LIST_RUNS)), parse_runs(_ssh(windows, _LIST_RUNS)), args.commit
        )
        out = OUT_ROOT / lin_run.commit
        shutil.rmtree(out, ignore_errors=True)
        source_root = out / "source"
        _extract_source(lin_run.commit, source_root)
        config = out / "paths.rc"
        config.write_text(paths_config(source_root, linux, windows), encoding="utf-8")
        lin_inputs = _fetch(linux, lin_run, out / "linux-data")
        win_inputs = _fetch(windows, win_run, out / "windows-data")
        names = (linux.repo_dir_name, windows.repo_dir_name)
        copied = fill_untracked([*lin_inputs, *win_inputs], source_root, names)
        lin_data, win_data, all_data = out / "linux.dat", out / "windows.dat", out / "all.dat"
        _combine(config, lin_data, lin_inputs)
        _combine(config, win_data, win_inputs)
        _combine(config, all_data, [*lin_inputs, *win_inputs])
        _check_mapped(_read(all_data), source_root)
    except CoverageAllError as exc:
        print(f"coverage-all: {exc}", file=sys.stderr)  # noqa: T201
        return 1

    print(f"coverage-all: commit {lin_run.commit}")  # noqa: T201
    if copied:
        print(f"  not in git, this checkout's copy used: {', '.join(copied)}")  # noqa: T201
    print(f"  Linux    {_total(lin_data):>5}%  ({linux.name}, run {lin_run.stamp})")  # noqa: T201
    print(f"  Windows  {_total(win_data):>5}%  ({windows.name}, run {win_run.stamp})")  # noqa: T201
    print(f"  both     {_total(all_data):>5}%")  # noqa: T201
    added = lines_only_in(_read(win_data), _read(lin_data))
    print(f"  lines only Windows ran: {sum(added.values())}")  # noqa: T201
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
