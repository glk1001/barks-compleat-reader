"""Emit hand-authored Python LOC per day, split by workspace package.

Walks the git history of the current repository, and for the last commit of each
calendar day counts newlines across every tracked ``*.py`` blob, bucketed into one
band per workspace package plus ``tests`` and ``scripts`` (root scripts + ``main.py``).

Two classes of file are treated as *not* hand-authored and excluded from every band:

* **Generated data modules** — see :data:`GENERATED`.
* **Scratch directories** — ``experiments/`` and ``scraps/``.

The result is printed to stdout as JSON: ``{"cats": [...], "series": [[date, c0, c1, ...], ...]}``
where each row is one calendar day and ``ci`` is the LOC in category ``cats[i]``. Days
with no commit carry the previous day's values forward. This is the data the sibling
``loc-growth.html`` chart embeds; refresh it by re-running this script (see README).

Run via git-calling subprocesses and prints to stdout by design, hence the file-level noqa.
"""

# ruff: noqa: INP001, S603, S607, DTZ011, T201

from __future__ import annotations

import json
import subprocess
from collections import OrderedDict
from datetime import date, timedelta

# Machine-generated data modules (mostly data literals), excluded from authored LOC.
GENERATED: set[str] = {"barks_bibliography.py", "barks_covers.py"}

# Workspace package directory (under ``src/<dir>/src``) -> importable package name.
PKG_DIR_TO_NAME: dict[str, str] = {
    "barks-reader": "barks_reader",
    "barks-fantagraphics": "barks_fantagraphics",
    "barks-kivy-ui": "barks_kivy_ui",
    "okf-reader": "okf_reader",
    "barks-build-comic-images": "barks_build_comic_images",
    "comic-utils": "comic_utils",
}

# Category order = stacking / column order (bottom -> top in the chart).
CATS: list[str] = [
    "barks_fantagraphics",
    "barks_reader",
    "barks_kivy_ui",
    "okf_reader",
    "comic_utils",
    "barks_build_comic_images",
    "scripts",
    "tests",
]
_CAT_IDX: dict[str, int] = {c: i for i, c in enumerate(CATS)}

# A ``src/<pkg>/src`` path has at least this many "/"-separated parts.
_MIN_PKG_PATH_PARTS = 3
# A ``git cat-file --batch`` header line is ``<sha> <type> <size>``.
_BATCH_HEADER_FIELDS = 3


def categorize(path: str) -> str | None:
    """Return the category a repo-relative ``.py`` path belongs to, or None to exclude it.

    Args:
        path: A repo-relative path ending in ``.py``.

    Returns:
        A category name from :data:`CATS`, or None if the file is generated or scratch.

    """
    if path.startswith(("experiments/", "scraps/")) or "/scraps/" in path:
        return None
    if path.rsplit("/", 1)[-1] in GENERATED:
        return None
    if "/tests/" in path or path.startswith("tests/"):
        return "tests"
    parts = path.split("/")
    if len(parts) >= _MIN_PKG_PATH_PARTS and parts[0] == "src" and parts[2] == "src":
        return PKG_DIR_TO_NAME.get(parts[1], "scripts")
    return "scripts"  # main.py, scripts/*.py


def _run(args: list[str]) -> str:
    """Run a git command and return its stdout as text."""
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def last_commit_per_day(since: str) -> OrderedDict[str, str]:
    """Map each ``YYYY-MM-DD`` to the SHA of its last (latest) commit since ``since``.

    Args:
        since: A git ``--since`` expression (e.g. an ISO date).

    Returns:
        Ordered mapping of day -> commit SHA, oldest day first.

    """
    out = _run(
        ["git", "log", f"--since={since}", "--date=short", "--pretty=format:%H %ad", "--reverse"]
    )
    per_day: OrderedDict[str, str] = OrderedDict()
    for line in out.splitlines():
        sha, day = line.split()
        per_day[day] = sha  # reverse log => last assignment wins = latest commit that day
    return per_day


def loc_by_cat_at_commit(sha: str) -> list[int]:
    """Return authored Python LOC per category at the given commit.

    Args:
        sha: The commit to inspect.

    Returns:
        A list of newline counts aligned to :data:`CATS`.

    """
    tree = _run(["git", "ls-tree", "-r", "--name-only", sha])
    paths = [p for p in tree.splitlines() if p.endswith(".py")]
    counts = [0] * len(CATS)
    if not paths:
        return counts
    spec = "".join(f"{sha}:{p}\n" for p in paths).encode()
    data = subprocess.run(
        ["git", "cat-file", "--batch"], input=spec, capture_output=True, check=True
    ).stdout
    i, length, path_idx = 0, len(data), 0
    while i < length:
        newline = data.index(b"\n", i)
        parts = data[i:newline].split(b" ")
        i = newline + 1
        if len(parts) != _BATCH_HEADER_FIELDS or parts[1] != b"blob":
            break  # unexpected object; stop rather than miscount
        size = int(parts[2])
        cat = categorize(paths[path_idx])
        if cat is not None:
            counts[_CAT_IDX[cat]] += data.count(b"\n", i, i + size)
        i += size + 1  # skip blob content + its trailing newline
        path_idx += 1
    return counts


def build_series(days: int = 366) -> dict[str, object]:
    """Build the per-day, per-category LOC series for the last ``days`` days.

    Args:
        days: How many days back from today to include.

    Returns:
        ``{"cats": CATS, "series": [[date, *counts], ...]}``.

    """
    since = (date.today() - timedelta(days=days)).isoformat()
    per_day = last_commit_per_day(since)
    days_sorted = sorted(per_day)
    at_day = {d: loc_by_cat_at_commit(sha) for d, sha in per_day.items()}

    start = date.fromisoformat(days_sorted[0])
    end = date.today()
    series: list[list[object]] = []
    last = [0] * len(CATS)
    day = start
    while day <= end:
        key = day.isoformat()
        if key in at_day:
            last = at_day[key]
        series.append([key, *last])
        day += timedelta(days=1)
    return {"cats": CATS, "series": series}


def main() -> None:
    """Print the LOC series as compact JSON to stdout."""
    print(json.dumps(build_series(), separators=(",", ":")))


if __name__ == "__main__":
    main()
