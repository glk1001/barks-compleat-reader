"""The durations the app logs, held to a loose budget: a startup or load regression fails a test.

The app times its own work - the tree build and the setup after it, every view
image, a comic's pages and each page shown, the volumes, the index - and logs
each with an ``{elapsed}`` field ("2.4s" or "12ms"). The benchmarks see only
core functions; these lines see the app as it runs.

A budget is about three times the slowest that duration was seen, and never
under a second. Which "seen": this machine's, when ``run_gui_tests.sh
--calibrate`` has written ``.benchmarks/gui-timings.json`` (gitignored, like
the benchmark baseline beside it); the committed ``BUDGETS`` otherwise, which
came from the desktop that built the suite. A laptop calibrates once and its
budgets fit it.

A busy machine is not a regression: the check is skipped, with a warning that
says so, when the one-minute load average is above what the machine and the
run's own workers account for (a six-process image job once stretched boot
image loads from a fraction of a second to eight). ``BARKS_GUI_NO_BUDGETS=1``
turns the check off for a run, and ``BARKS_GUI_TIMINGS=<file>`` appends each
test's slowest durations to that file as JSON lines, which ``--calibrate``
folds into the baseline.
"""

# cspell:ignore getloadavg gethostname

from __future__ import annotations

import datetime as dt
import json
import os
import re
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from barks_gui.logs import messages
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import capture

if TYPE_CHECKING:
    from collections.abc import Mapping

NO_BUDGETS_ENV_VAR = "BARKS_GUI_NO_BUDGETS"
TIMINGS_FILE_ENV_VAR = "BARKS_GUI_TIMINGS"
# Set by run_gui_tests.sh: how many workers this run has, for the load rule.
WORKERS_ENV_VAR = "BARKS_GUI_WORKER_COUNT"

REPO_ROOT = Path(__file__).resolve().parents[5]
# Written by `run_gui_tests.sh --calibrate`; read whenever it exists.
BASELINE_FILE = REPO_ROOT / ".benchmarks" / "gui-timings.json"
BUDGET_FACTOR = 3.0
MIN_BUDGET_SECS = 1.0
# Floors above the minimum for a kind whose calibration run cannot see its
# worst case: the volumes are read from a warm cache in a run (0.2s), and
# from disk after a reboot.
MIN_BUDGETS: dict[str, float] = {"volumes loaded": 10.0}
# The load one headless worker adds (its Xvfb, the app and its image threads):
# a four-worker run took a quiet 16-core machine to about 12.
PER_WORKER_LOAD = 3.0

# What is timed, by the marker that carries its {elapsed}.
TIMED: dict[str, str] = {
    "tree nodes loaded": markers.TREE_NODES_LOADED,
    "post tree setup": markers.POST_TREE_SETUP,
    "view image loaded": markers.IMAGE_LOADED,
    "title inset image set": markers.TITLE_INSET_IMAGE_SET,
    "volumes loaded": markers.VOLUMES_LOADED,
    "comic images loaded": markers.ALL_IMAGES_LOADED,
    "page shown": markers.SHOWED_PAGE,
    "index built": markers.INDEX_BUILD_COMPLETE,
    "index letter populated": markers.INDEX_LETTER_POPULATED,
}

# Seconds, the committed fallback: calibrated on 2026-09-23 from the slowest of
# each kind across all 62 tests on the desktop that built the suite (headless,
# four workers sharing the machine, otherwise quiet): about three times that,
# and never under a second, since a tenth of a second seen is no evidence a
# tenth is all it may ever take. The slowest seen is noted. A machine with a
# baseline file uses its own numbers instead (`budgets`).
BUDGETS: dict[str, float] = {
    "tree nodes loaded": 2.0,  # 0.5s
    "post tree setup": 3.0,  # 0.7s
    "view image loaded": 8.0,  # 2.7s
    "title inset image set": 6.0,  # 2.0s
    "volumes loaded": 10.0,  # 0.1s warm; a cold cache reads every volume's table
    "comic images loaded": 6.0,  # 2.1s
    "page shown": 3.0,  # 0.9s
    "index built": 1.0,  # 0.01s
    "index letter populated": 1.0,  # 0.2s
}

_ELAPSED_RE = re.compile(r"^(\d+(?:\.\d+)?)(ms|s)$")
_TIMED_RE: dict[str, re.Pattern[str]] = {
    name: re.compile(capture(template, "elapsed")) for name, template in TIMED.items()
}


@dataclass(frozen=True)
class Duration:
    """One timed line: what was timed, how long it took, and the line itself."""

    name: str
    seconds: float
    line: str


def parse_elapsed(text: str) -> float:
    """Return the seconds in an elapsed field the app formatted ("2.4s", "12ms").

    Raises:
        ValueError: If the text is not in either form.

    """
    found = _ELAPSED_RE.fullmatch(text.strip())
    if not found:
        msg = f"not an elapsed time the app formats: {text!r}"
        raise ValueError(msg)
    value, unit = float(found.group(1)), found.group(2)
    return value / 1000 if unit == "ms" else value


def durations(app_log: str) -> list[Duration]:
    """Return every timed line in the log, in order.

    Read from the messages, without each line's trailing location: an elapsed
    field at the end of a message ("...in 0.3s.") would otherwise run on into
    the module path and parse as nothing.
    """
    found: list[Duration] = []
    for line in messages(app_log).splitlines():
        for name, regex in _TIMED_RE.items():
            match = regex.search(line)
            if match is None:
                continue
            try:
                seconds = parse_elapsed(match["elapsed"])
            except ValueError:
                continue
            found.append(Duration(name, seconds, line.strip()))
            break
    return found


def slowest(found: list[Duration]) -> dict[str, float]:
    """Return the longest duration seen for each name that was seen at all."""
    worst: dict[str, float] = {}
    for d in found:
        worst[d.name] = max(worst.get(d.name, 0.0), d.seconds)
    return worst


def budget_problems(app_log: str, budgets: Mapping[str, float]) -> list[str]:
    """Return one line per timed line that took longer than its budget."""
    return [
        f"{d.name} took {d.seconds:g}s, over its {budgets[d.name]:g}s budget: {d.line}"
        for d in durations(app_log)
        if d.seconds > budgets[d.name]
    ]


@dataclass(frozen=True)
class Baseline:
    """What a calibration run wrote: when and where, and the slowest of each kind."""

    calibrated: str
    host: str
    workers: int
    slowest: dict[str, float]


def fold(jsonl: Path) -> dict[str, float]:
    """Return the slowest of each kind across every test recorded in the JSON lines file."""
    worst: dict[str, float] = {}
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        for name, seconds in json.loads(line)["slowest"].items():
            worst[name] = max(worst.get(name, 0.0), float(seconds))
    return worst


def write_baseline(path: Path, slowest: Mapping[str, float], workers: int) -> Baseline:
    """Write this machine's baseline, dated and named, and return it."""
    baseline = Baseline(
        calibrated=dt.datetime.now(tz=dt.UTC).date().isoformat(),
        host=socket.gethostname(),
        workers=workers,
        slowest=dict(sorted(slowest.items())),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(baseline.__dict__, indent=2) + "\n", encoding="utf-8")
    return baseline


def read_baseline(path: Path) -> Baseline | None:
    """Return the baseline at `path`, or None when there is none (or it is unreadable)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Baseline(
            calibrated=str(data["calibrated"]),
            host=str(data["host"]),
            workers=int(data["workers"]),
            slowest={str(k): float(v) for k, v in data["slowest"].items()},
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def budgets(baseline_file: Path = BASELINE_FILE) -> tuple[dict[str, float], str]:
    """Return the budgets in force and where they came from.

    This machine's baseline when it has one - BUDGET_FACTOR times the slowest
    each kind was seen, never under MIN_BUDGET_SECS (or the kind's own floor in
    MIN_BUDGETS), with the committed budget for a kind the baseline never saw -
    and the committed budgets otherwise.
    """
    baseline = read_baseline(baseline_file)
    if baseline is None:
        return dict(BUDGETS), "the committed budgets"
    in_force = dict(BUDGETS)
    for name, seconds in baseline.slowest.items():
        if name in in_force:
            floor = MIN_BUDGETS.get(name, MIN_BUDGET_SECS)
            in_force[name] = round(max(BUDGET_FACTOR * seconds, floor), 3)
    source = (
        f"budgets calibrated on {baseline.host} on {baseline.calibrated}"
        f" with {baseline.workers} worker(s), from {baseline_file}"
    )
    return in_force, source


def machine_is_busy(workers: int | None = None) -> str | None:
    """Return why the budgets should not be trusted right now, or None when they can be.

    The one-minute load average against what the machine and this run account
    for: the core count plus PER_WORKER_LOAD for each of the run's workers.
    Above that, something else was competing for the CPU and the app's
    durations say nothing about the app.

    Args:
        workers: The run's worker count; the runner's environment variable, or
            one, when not given.

    """
    try:
        load = os.getloadavg()[0]
    except OSError:
        return None
    if workers is None:
        workers = int(os.environ.get(WORKERS_ENV_VAR, "1") or 1)
    cores = os.cpu_count() or 1
    allowed = cores + PER_WORKER_LOAD * workers
    if load > allowed:
        return (
            f"the load average is {load:.0f}, over the {allowed:g} that {cores} cores"
            f" and {workers} worker(s) account for"
        )
    return None


def record_slowest(path: Path, nodeid: str, worst: dict[str, float]) -> None:
    """Append one JSON line with a test's slowest durations, for calibrating the budgets."""
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"test": nodeid, "slowest": worst}) + "\n")


def main(argv: list[str]) -> int:
    """Fold a recording run into this machine's baseline.

    Usage: ``calibrate <timings.jsonl> <workers>``.
    """
    if len(argv) != 3 or argv[0] != "calibrate":  # noqa: PLR2004
        print("usage: python -m barks_gui.timings calibrate <timings.jsonl> <workers>")  # noqa: T201
        return 2
    jsonl, workers = Path(argv[1]), int(argv[2])
    baseline = write_baseline(BASELINE_FILE, fold(jsonl), workers)
    in_force, _ = budgets()
    print(f"timing budgets calibrated on {baseline.host}, written to {BASELINE_FILE}:")  # noqa: T201
    for name in TIMED:
        seen = baseline.slowest.get(name)
        shown = f"{seen:g}s seen" if seen is not None else "not seen, committed budget"
        print(f"  {name:24s} {in_force[name]:5g}s  ({shown})")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
