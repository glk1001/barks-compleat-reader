"""A random walk over the remote's six keys, as long as you like, with the invariants watching.

Every scripted test walks one path. This one walks none in particular: a seeded
stream of Escape, Return, Up, Down, Left and Right from a few boot nodes, each
key waited on through the app's own "Key pressed" line, so a main loop that
stops answering is caught at the key that stopped it. What makes the walk a
test is the teardown: the log must stay clean, the reads persisted, the frame
drawn and no key stray, whatever the walk wandered into.

The walk keeps itself alive by never confirming a confirm popup (the quit
confirmation is one), pressing Escape there instead. It is a soak test, off by
default: ``run_gui_tests.sh --soak`` selects it alone, and
``BARKS_GUI_WALK_STEPS`` / ``BARKS_GUI_WALK_SEED`` set its length and seed
(the seed is in the test id, so a failure names the walk that found it).
"""

from __future__ import annotations

import os
import random
import re
import time
from typing import TYPE_CHECKING

import pytest
from barks_gui import nodes
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

REMOTE_KEYS = ("Escape", "Return", "Up", "Down", "Left", "Right")
STEPS = int(os.environ.get("BARKS_GUI_WALK_STEPS", "200"))
SEED = int(os.environ.get("BARKS_GUI_WALK_SEED", "1"))
KEY_TIMEOUT = 15
KEY_PRESSED = pattern(markers.KEY_PRESSED)
CONFIRM_OPENED = pattern(markers.CONFIRM_POPUP_OPENED)
CONFIRM_CLOSED = pattern(markers.CONFIRM_POPUP_CLOSED)
NAV_FOCUS = pattern(markers.NAV_FOCUS)
# The buttons a Return on opens a confirm popup: the bar's Quit, History's Clear.
# The popup opens a moment after the key is logged (a bar button fires its action
# asynchronously), so a walk that looked at once would see no popup, pick a key
# at random, and could confirm it - quitting the app under its own feet.
OPENS_A_CONFIRM = re.compile(
    pattern(
        markers.NAV_FOCUS, widget=re.compile(r'(ChromeBarButton "Quit"|Button "Clear History")')
    )
)
CONFIRM_WAIT_SECS = 3.0
START_NODES = {
    "stories": nodes.THE_STORIES,
    "main-index": nodes.MAIN_INDEX,
    "history": nodes.HISTORY,
    "a-story": nodes.GHOST_OF_THE_GROTTO,
}


def _confirm_popup_open(d: Driver) -> bool:
    return d.match_count(CONFIRM_OPENED) > d.match_count(CONFIRM_CLOSED)


def _focus_opens_a_confirm(d: Driver) -> bool:
    """Whether keyboard focus was last logged on a button that opens a confirm popup."""
    return bool(d.match_count(NAV_FOCUS)) and bool(OPENS_A_CONFIRM.search(d.last_line(NAV_FOCUS)))


def _await_confirm_opened(d: Driver, before: int) -> None:
    """Give a confirm popup a Return may have asked for the time to open (or not).

    Not a failure when none comes: the focus line may be stale, and then the
    Return did something else.
    """
    deadline = time.monotonic() + CONFIRM_WAIT_SECS
    while d.match_count(CONFIRM_OPENED) == before and time.monotonic() < deadline:
        time.sleep(0.1)


@pytest.mark.soak
@pytest.mark.parametrize("start", list(START_NODES), ids=[f"{n}-seed{SEED}" for n in START_NODES])
def test_a_random_walk_leaves_the_app_answering_and_clean(boot: AppBoot, start: str) -> None:
    d = boot(START_NODES[start], cues=nodes.NO_CUES)
    # The walk may end fullscreen or mid-reader; the teardown's other checks still apply.
    boot.expect_boot_size = False
    rng = random.Random(f"{SEED}:{start}")
    for step in range(STEPS):
        key = "Escape" if _confirm_popup_open(d) else rng.choice(REMOTE_KEYS)
        may_confirm = key == "Return" and _focus_opens_a_confirm(d)
        confirms_before = d.match_count(CONFIRM_OPENED)
        try:
            d.key_then_wait(KEY_PRESSED, key, timeout=KEY_TIMEOUT)
        except Exception as exc:
            msg = f"step {step + 1}/{STEPS} ({key}) got no answer from the app: {exc}"
            raise AssertionError(msg) from exc
        if may_confirm:
            _await_confirm_opened(d, confirms_before)
    d.settle()
    assert d.match_count(KEY_PRESSED) >= STEPS
