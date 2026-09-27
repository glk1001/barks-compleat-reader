#!/usr/bin/env python3
"""Hold the overnight run's combined coverage to a floor that follows the best it reached.

``pyproject.toml``'s ``fail_under`` (40) is sized for CI, whose unit suite skips the
tests that need the data pack, so it guards nothing near the real figure. The
overnight run's coverage stage combines the unit suite with the GUI tests (about
87% on 2026-09-27) and passes the total here: it fails when the total is more than
the tolerance below the best recorded in ``.benchmarks/coverage.json``
(machine-local, gitignored), and records a new best. The tolerance absorbs the
soak's random walks, which reach a little more or less each night.

Usage: coverage_floor.py TOTAL [--tolerance POINTS] [--record FILE]. Exits 1 below
the floor, 0 otherwise.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORD_FILE = REPO_ROOT / ".benchmarks" / "coverage.json"
TOLERANCE = 1.0


def read_best(record_file: Path) -> float | None:
    """Return the best combined total recorded, or None before the first."""
    try:
        return float(json.loads(record_file.read_text())["combined"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def judge(total: float, record_file: Path, tolerance: float = TOLERANCE) -> tuple[bool, str]:
    """Hold `total` to the floor, recording it when it is a new best.

    Args:
        total: Tonight's combined coverage, in percent.
        record_file: Where the best is kept.
        tolerance: Points below the best still accepted.

    Returns:
        Whether it passes, and the line to print.

    """
    best = read_best(record_file)
    if best is not None and total < best - tolerance:
        return False, f"FAIL - combined {total}% is more than {tolerance} below its best, {best}%"
    if best is not None and total <= best:
        return True, f"within {tolerance} of its best, {best}%"
    record_file.parent.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.now(tz=dt.UTC).date().isoformat()
    record_file.write_text(json.dumps({"combined": total, "date": today}, indent=2) + "\n")
    was = f" (was {best}%)" if best is not None else ""
    return True, f"new best, recorded: {total}%{was}"


def main(argv: list[str]) -> int:
    """Parse the arguments, judge, print; return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("total", type=float)
    parser.add_argument("--tolerance", type=float, default=TOLERANCE)
    parser.add_argument("--record", type=Path, default=RECORD_FILE)
    args = parser.parse_args(argv)
    passed, line = judge(args.total, args.record, args.tolerance)
    print(f"coverage: {line}")  # noqa: T201
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
