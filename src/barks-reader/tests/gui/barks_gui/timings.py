"""The durations the app logs, held to a loose budget: a startup or load regression fails a test.

The app times its own work - the tree build and the setup after it, every view
image, a comic's pages and each page shown, the volumes, the index - and logs
each with an ``{elapsed}`` field ("2.4s" or "12ms"). The benchmarks see only
core functions; these lines see the app as it runs. Each budget is about three
times the slowest that duration was seen in a calibration pass, so a regression
trips it and ordinary variance does not.

A busy machine is not a regression: when the one-minute load average exceeds
the core count at teardown the check is skipped, with a warning that says so
(a six-process image job once stretched boot image loads from a fraction of a
second to eight). ``BARKS_GUI_NO_BUDGETS=1`` turns the check off for a run, and
``BARKS_GUI_TIMINGS=<file>`` appends each test's slowest durations to that file
as JSON lines, which is how the budgets are calibrated.
"""

# cspell:ignore getloadavg

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from barks_gui.logs import messages
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import capture

if TYPE_CHECKING:
    from pathlib import Path

NO_BUDGETS_ENV_VAR = "BARKS_GUI_NO_BUDGETS"
TIMINGS_FILE_ENV_VAR = "BARKS_GUI_TIMINGS"

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

# Seconds. Calibrated on 2026-09-23 from the slowest of each kind across all 62
# tests (headless, four workers sharing the machine, otherwise quiet): about
# three times that, and never under a second, since a tenth of a second seen
# is no evidence a tenth is all it may ever take. The slowest seen is noted.
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


def budget_problems(app_log: str) -> list[str]:
    """Return one line per timed line that took longer than its budget."""
    return [
        f"{d.name} took {d.seconds:g}s, over its {BUDGETS[d.name]:g}s budget: {d.line}"
        for d in durations(app_log)
        if d.seconds > BUDGETS[d.name]
    ]


def machine_is_busy() -> str | None:
    """Return why the budgets should not be trusted right now, or None when they can be.

    The one-minute load average against the core count: above it, the app was
    competing for the CPU and its durations say nothing about the app.
    """
    try:
        load = os.getloadavg()[0]
    except OSError:
        return None
    cores = os.cpu_count() or 1
    if load > cores:
        return f"the load average is {load:.0f} on {cores} cores"
    return None


def record_slowest(path: Path, nodeid: str, worst: dict[str, float]) -> None:
    """Append one JSON line with a test's slowest durations, for calibrating the budgets."""
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"test": nodeid, "slowest": worst}) + "\n")
