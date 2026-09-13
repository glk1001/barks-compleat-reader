#!/usr/bin/env python3
"""Check that Enter opens the comic right after a search result is clicked.

Regression harness for the bug fixed in `63b4a42`: picking a title-search result
with the *mouse* and pressing Enter during the title view's fade-in used to
activate the panel's eye toggle instead of opening the comic.

Why it needs the GUI
    The window is a random 0-4s animation (the title panel's fade), and the
    decision it corrupts - which widget keyboard focus lands on - only exists in
    a running app. The unit tests in `test_bottom_title_view_screen.py` cover the
    visibility rule directly and are the everyday guard; this script is what
    reproduces the symptom end to end, and it is slow (one app boot per trial).

What it does
    Per trial: boot the app onto Search/Titles via `gui-probe.sh`, type the
    query, click the Nth result, wait `--delay` seconds, press Enter, then read
    the app log for whether a comic was loaded. Each trial uses its own random
    seed, so the fade duration varies from trial to trial.

How to read it
    `opened` is the verdict. `at_portal`/`plain_nav` say which focus path ran:
    a click is *expected* to show `at_portal=False, plain_nav=True`, because a
    mouse-driven goto-title deliberately stays in mouse mode and the Enter then
    enters nav focus lazily. Before the fix, short delays gave `opened=False`;
    after it, every delay opens the comic.

    Exits non-zero if any trial failed to open the comic.

Assumes
    - `scripts/gui-probe.sh doctor` passes, and nothing else is on the display.
    - `scripts/record_demo.py` sits alongside this file: its Driver and its
      search constants (query, result row geometry) are reused verbatim, so the
      two stay in step.
    - Nothing else is driving the app. gui-probe restores the config it backed up
      at start, so a hand-run app overlapping a trial would lose its changes.

Only the standard library is used, so this runs without the workspace venv - the
same as the scripts it drives. It backs up the reader config itself, on top of
gui-probe's own backup, and puts it back on any exit.

Usage:
    scripts/repro_search_enter.py                  # 5 trials, Enter 0.3s after the click
    scripts/repro_search_enter.py --delay 5        # ... after the fade has finished
    scripts/repro_search_enter.py --trials 10
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# The recorder is a sibling script, not an installed module, so the path above has
# to be in place before it can be imported.
import record_demo as rd  # noqa: E402

# The search screen, leaf-to-root, as the app stores it in `last_selected_node`.
SEARCH_NODE = ["Titles", "Search", "root"]
# Seeds are per-trial so each draws its own fade duration; the base only has to be
# stable enough that a run can be repeated.
SEED_BASE = 1000
# How long to let the comic load before giving up on it. A page opens in well under
# a second, so anything this side of it is a failure, not a slow machine.
OPEN_WAIT_SECS = 8

# The tail of the line comic_reader_manager._read_comic_book writes whenever it
# opens a comic, whichever story it is. Matched without the title so that
# re-pointing record_demo's search pick at another story cannot quietly turn this
# check into a no-op.
COMIC_OPENED_MARKER = ' and goto page "'


def say(message: str = "") -> None:
    """Write a progress line to stdout."""
    print(message, flush=True)  # noqa: T201


@dataclass(frozen=True)
class Trial:
    """What one click-then-Enter attempt did."""

    delay: float
    at_portal: bool
    plain_nav: bool
    opened: bool


def probe(*args: str) -> str:
    """Run `gui-probe.sh` with `args` and return its stdout."""
    return subprocess.run(  # noqa: S603  (fixed argv, no shell)
        [str(rd.PROBE), *args], capture_output=True, text=True, check=True
    ).stdout


def run_trial(delay: float, seed: int, config: Path, backup: Path) -> Trial:
    """Boot the app, click a search result, press Enter after `delay`, and report.

    Args:
        delay: Seconds to wait between the click and the Enter - the whole
            experiment. Shorter than the title fade is what used to fail.
        seed: Pins the app's random draws, including the fade's duration.
        config: The reader config to point at the search screen.
        backup: The pristine config to build each trial's copy from.

    Returns:
        What the trial observed.

    """
    settings = json.loads(backup.read_text())
    settings.setdefault("AAA_Settings", {})["last_selected_node"] = list(SEARCH_NODE)
    config.write_text(json.dumps(settings, indent=2))
    os.environ[rd.RANDOM_SEED_ENV_VAR] = str(seed)

    probe("start")
    try:
        driver = rd.Driver()
        log = Path(probe("log").strip())

        driver.hold(0.5)
        driver.key("Return")  # focus the search box
        driver.settle()
        driver.type_slowly(rd.SEARCH_TITLE_QUERY)
        driver.settle()
        driver.hold(0.8)

        row_y = rd.SEARCH_RESULT_TOP_Y + (rd.SEARCH_TITLE_RESULT - 1) * rd.SEARCH_RESULT_ROW_H
        driver.click_then_wait(
            f'Goto title: "{rd.SEARCH_TITLE_PICK.title}"', 15, rd.SEARCH_RESULT_X, row_y
        )

        time.sleep(delay)
        driver.key("Return")
        time.sleep(OPEN_WAIT_SECS)

        text = log.read_text()
        return Trial(
            delay=delay,
            at_portal="entered nav focus at portal" in text,
            plain_nav="BottomTitleViewScreen: entered nav focus." in text,
            opened=COMIC_OPENED_MARKER in text,
        )
    finally:
        probe("stop")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="seconds between the click and the Enter (default: 0.3)",
    )
    parser.add_argument("--trials", type=int, default=5, help="how many trials (default: 5)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the trials and report. Returns a process exit code."""
    args = parse_args(argv)
    config = Path(probe("config").strip())

    with tempfile.TemporaryDirectory(prefix="repro-search-enter-") as tmp:
        backup = Path(tmp) / "barks-reader.json.bak"
        shutil.copy2(config, backup)
        results: list[Trial] = []
        try:
            for i in range(args.trials):
                trial = run_trial(args.delay, SEED_BASE + i, config, backup)
                results.append(trial)
                say(
                    f"  delay={trial.delay:.1f}s  at_portal={trial.at_portal!s:<5}"
                    f" plain_nav={trial.plain_nav!s:<5}  comic opened={trial.opened}"
                )
        finally:
            shutil.copy2(backup, config)
            say(f"restored {config}")

    opened = sum(1 for t in results if t.opened)
    say(f"\nEnter {args.delay:.1f}s after the click: opened {opened}/{len(results)}")
    if opened != len(results):
        say("FAIL: a click-then-Enter did not open the comic.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
