#!/usr/bin/env python3
"""Hold each package's unit-suite coverage to its own floor.

The total hides a slide in a small package: ``okf_reader`` could lose ten points while
``barks_reader``, five times its size, kept the total within a point. ``diff-cover``
holds the lines a push changes to 80%, which lets a package at 100% drift down a few
lines at a time. This reads the data a ``pytest --cov`` run left (``.coverage``) and
fails when a package in ``FLOORS``, or the total, is below its floor.

Each floor is one point below what the unit suite reached on 2026-11-21 (the same
here and in CI): a few hard-to-test lines do not fail a push, a real slide does. Raise
a floor when its package has stayed a point or more above it; lower one only with the
reason in the commit.

Run by CI's ``diff-coverage`` job and ``scripts/diff-cover.sh``, after the suite.

Usage: package_coverage.py [--data-file FILE]. Exits 1 below a floor, 0 otherwise.
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

import coverage

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = REPO_ROOT / ".coverage"

# The total's row: every package together, as `coverage report` totals them.
TOTAL = "total"

# Percent of lines and branches, by package (a folder name under a `src/*/src`).
FLOORS: dict[str, float] = {
    "barks_reader": 97.8,
    "barks_fantagraphics": 98.9,
    "barks_build_comic_images": 98.7,
    "comic_utils": 99.0,
    "okf_reader": 99.0,
    TOTAL: 98.2,
}


def measure(data_file: Path, packages: list[str]) -> dict[str, float]:
    """Return each package's coverage, in percent, from a coverage data file.

    Args:
        data_file: The data a ``pytest --cov`` run wrote.
        packages: Package folder names, or `TOTAL` for all the measured code.

    Returns:
        The figure for each name, with what ``pyproject.toml`` omits left out.

    """
    cov = coverage.Coverage(data_file=str(data_file), config_file=str(REPO_ROOT / "pyproject.toml"))
    cov.load()
    return {
        name: cov.report(
            include=None if name == TOTAL else f"*/{name}/*", file=io.StringIO(), precision=1
        )
        for name in packages
    }


def judge(measured: dict[str, float], floors: dict[str, float]) -> tuple[bool, list[str]]:
    """Hold each measured figure to its floor.

    Args:
        measured: Coverage by package, in percent.
        floors: The least each may be.

    Returns:
        Whether all pass, and a line for each package.

    """
    width = max(len(name) for name in floors)
    lines = []
    passed = True
    for name, floor in floors.items():
        got = round(measured[name], 1)
        ok = got >= floor
        passed = passed and ok
        verdict = "ok" if ok else f"FAIL - below its floor, {floor}%"
        lines.append(f"{name:<{width}}  {got:5.1f}%  {verdict}")
    return passed, lines


def main(argv: list[str]) -> int:
    """Parse the arguments, measure, judge, print; return the exit status."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--data-file", type=Path, default=DATA_FILE)
    args = parser.parse_args(argv)
    if not args.data_file.is_file():
        print(f"package coverage: no data at {args.data_file} (run `uv run pytest --cov`)")  # noqa: T201
        return 1
    passed, lines = judge(measure(args.data_file, list(FLOORS)), FLOORS)
    for line in lines:
        print(f"package coverage: {line}")  # noqa: T201
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
