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
START_NODES = {
    "stories": nodes.THE_STORIES,
    "main-index": nodes.MAIN_INDEX,
    "history": nodes.HISTORY,
    "a-story": nodes.GHOST_OF_THE_GROTTO,
}


def _confirm_popup_open(d: Driver) -> bool:
    return d.match_count(CONFIRM_OPENED) > d.match_count(CONFIRM_CLOSED)


@pytest.mark.soak
@pytest.mark.parametrize("start", list(START_NODES), ids=[f"{n}-seed{SEED}" for n in START_NODES])
def test_a_random_walk_leaves_the_app_answering_and_clean(boot: AppBoot, start: str) -> None:
    d = boot(START_NODES[start], cues=nodes.NO_CUES)
    # The walk may end fullscreen or mid-reader; the teardown's other checks still apply.
    boot.expect_boot_size = False
    rng = random.Random(f"{SEED}:{start}")
    for step in range(STEPS):
        key = "Escape" if _confirm_popup_open(d) else rng.choice(REMOTE_KEYS)
        try:
            d.key_then_wait(KEY_PRESSED, key, timeout=KEY_TIMEOUT)
        except Exception as exc:
            msg = f"step {step + 1}/{STEPS} ({key}) got no answer from the app: {exc}"
            raise AssertionError(msg) from exc
    d.settle()
    assert d.match_count(KEY_PRESSED) >= STEPS
