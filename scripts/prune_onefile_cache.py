#!/usr/bin/env python3
"""Remove the standalone app's old unpack folders, keeping the newest few.

The Linux and Windows builds are Nuitka onefile executables, which unpack themselves
into ``{CACHE_DIR}/BarksReader/{VERSION}`` (``build.sh``'s ``--onefile-tempdir-spec``) and
reuse that folder on the next start. Every build has a new version, so every night's
build left one more folder of about 360 MB, and nothing removed the old ones: 76 of
them, 24 GB, on one overnight machine by 2026-10-28. This keeps the ``--keep`` newest,
by modification time, and removes the rest, except a folder a running process was
started from. The macOS build is an .app bundle, which unpacks nowhere: nothing to do.

Each folder is renamed before it is deleted, so an interrupted delete never leaves a
half-emptied folder under a version's name for that version's next start to trip on;
a folder left with the suffix goes on the next run. On Windows a folder holding a
running executable cannot be renamed, so it is kept, and said so.

The overnight runs' ``tidy`` stage runs it (``run_overnight.sh``,
``run_overnight_desktop.py``).

Usage: prune_onefile_cache.py [--keep N] [--dry-run] [--root DIR]. Exits 1 when a
renamed folder could not be deleted, 0 otherwise (nothing to prune included).
"""

# cspell:ignore LOCALAPPDATA

from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import psutil

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

APP_DIR_NAME = "BarksReader"  # build.sh's --onefile-tempdir-spec
KEEP = 3
DELETING_SUFFIX = ".deleting"
_MB = 1024 * 1024


def unpack_root(
    platform: str = sys.platform,
    environ: Mapping[str, str] = os.environ,
    home: Path | None = None,
) -> Path:
    """Return the folder the app's versions unpack into, as Nuitka's {CACHE_DIR} has it.

    Linux: ``$XDG_CACHE_HOME`` when it is an absolute path, else ``~/.cache``.
    Windows: ``%LOCALAPPDATA%``.
    """
    home = Path.home() if home is None else home
    if platform == "win32":
        local = environ.get("LOCALAPPDATA")
        base = Path(local) if local else home / "AppData" / "Local"
    else:
        xdg = environ.get("XDG_CACHE_HOME", "")
        base = Path(xdg) if xdg.startswith("/") else home / ".cache"
    return base / APP_DIR_NAME


def running_executables() -> set[Path]:
    """Return the executable of every process this user can see."""
    exes: set[Path] = set()
    for proc in psutil.process_iter(["exe"]):
        exe = proc.info.get("exe")
        if exe:
            exes.add(Path(exe))
    return exes


@dataclass
class Plan:
    """What a prune keeps and removes, each newest first."""

    kept: list[Path] = field(default_factory=list)
    in_use: list[Path] = field(default_factory=list)
    remove: list[Path] = field(default_factory=list)


def plan(root: Path, keep: int, executables: Iterable[Path]) -> Plan:
    """Return which of `root`'s folders to keep and which to remove.

    The `keep` newest folders stay, and any older one a running executable lives in;
    a folder an interrupted run left renamed is removed whatever its age.
    """
    exes = list(executables)
    folders = sorted(
        (p for p in root.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    result = Plan()
    versions = [p for p in folders if not p.name.endswith(DELETING_SUFFIX)]
    result.kept = versions[:keep]
    for folder in [*versions[keep:], *(p for p in folders if p.name.endswith(DELETING_SUFFIX))]:
        if any(exe.is_relative_to(folder) for exe in exes):
            result.in_use.append(folder)
        else:
            result.remove.append(folder)
    return result


def folder_size(folder: Path) -> int:
    """Return the bytes the files under `folder` take."""
    total = 0
    for dirpath, _, filenames in os.walk(folder):
        for name in filenames:
            with contextlib.suppress(OSError):
                total += (Path(dirpath) / name).lstat().st_size
    return total


def remove(folder: Path) -> str | None:
    """Rename `folder` aside, then delete it; return why not, or None when it is gone.

    A folder that cannot be renamed is left as it is (on Windows: one in use).
    """
    doomed = folder
    if not folder.name.endswith(DELETING_SUFFIX):
        doomed = folder.with_name(folder.name + DELETING_SUFFIX)
        if doomed.exists():
            shutil.rmtree(doomed)
        try:
            folder.rename(doomed)
        except OSError as e:
            return f"kept, could not move it aside (in use?): {e}"
    shutil.rmtree(doomed)
    return None


def _say(line: str) -> None:
    print(f"prune_onefile_cache: {line}")  # noqa: T201


def prune(root: Path, keep: int, executables: Iterable[Path], dry_run: bool = False) -> int:
    """Prune `root` as `plan` says, reporting each folder; return the exit status."""
    if not root.is_dir():
        _say(f"no {root}: nothing to prune")
        return 0
    todo = plan(root, keep, executables)
    _say(f"{root}: keeping the newest {keep}: {', '.join(p.name for p in todo.kept) or 'none'}")
    for folder in todo.in_use:
        _say(f"  {folder.name}: kept, a running process was started from it")
    status, freed = 0, 0
    for folder in todo.remove:
        size = folder_size(folder)
        if dry_run:
            _say(f"  {folder.name}: would remove ({size / _MB:,.0f} MB)")
            continue
        try:
            why = remove(folder)
        except OSError as e:
            _say(f"  {folder.name}: FAILED to delete: {e}")
            status = 1
            continue
        if why is None:
            freed += size
            _say(f"  {folder.name}: removed ({size / _MB:,.0f} MB)")
        else:
            _say(f"  {folder.name}: {why}")
    if not dry_run:
        _say(f"freed {freed / _MB:,.0f} MB")
    return status


def main(argv: list[str]) -> int:
    """Parse the arguments and prune; return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--keep", type=int, default=KEEP, help=f"default {KEEP}")
    parser.add_argument("--dry-run", action="store_true", help="say what would go; remove none")
    parser.add_argument("--root", type=Path, default=None, help="default: the app's own")
    args = parser.parse_args(argv)
    root = unpack_root() if args.root is None else args.root
    return prune(root, max(args.keep, 0), running_executables(), dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
