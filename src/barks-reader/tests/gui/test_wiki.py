"""The Carl Barks Wiki: opened from its node and from a story's chip, browsed, left.

Skipped when the profile points at no live wiki bundle. With the live bundle
off the app reads the copy under its Reader Files folder, which the harness
cannot see from the ini, so the tests run and fail if it is missing (the wiki
node is then absent) - a data gap to fix, not a reason to test less. The
wiki viewer logs
through Kivy's logger, so its lines carry a ``kivy:`` prefix in the app log;
the patterns below are substrings of them.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from barks_gui import harness, nodes

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

WIKI_ACTIVE = "Wiki reader screen is active."
WIKI_ENTERED = "Screen 'wiki_reader' entered."  # the transition has finished
# Parentheses in a log line must be escaped: wait patterns are regexes.
MAIN_FROM_WIKI = re.escape("Main screen is active (from wiki reader).")
SHOWED_PAGE = "OKFViewer: Showed page"
TOP_BAR = "OKFViewer: Focus region TOP_BAR."
BAR_PAUSE = 0.5
SIDEBAR_STEPS = 2
# On the top bar Escape lands on Back; the goto-title button is this far right
# (the bar runs Back, contrast, goto-title, quit).
BAR_RIGHTS_TO_GOTO = 2
# Up from the read portal, with no cue and prebuilt comics (no goto-page row,
# no overrides row), is the wiki chip. The chip test pins use_prebuilt_comics
# for that: Lost in the Andes has an optional override, and with the volumes
# in use the overrides row would sit between the portal and the chip.
UPS_TO_WIKI_CHIP = 1
PREBUILT_COMICS = {"use_prebuilt_comics": "1"}
# What the app writes for an unset wiki directory (reader_settings
# UNSET_WIKI_BUNDLE_DIR_MARKER); the key is never empty in an app-written ini.
UNSET_WIKI_DIR = "<Carl Barks Wiki Not Set>"
TWO_PAGES = 2


@pytest.fixture
def wiki_boot(boot: AppBoot) -> AppBoot:
    """Return the boot, or skip when the profile's live wiki setting points at no bundle."""
    ini = boot.scratch / "barks-reader.ini"
    if harness.read_ini_value(ini, "use_live_wiki_bundle").strip() != "0":
        # The app accepts the marker, a bundle root (its index.md is the gate),
        # or, when not set, anything at all - the latter two are checked below.
        wiki_dir = harness.read_ini_value(ini, "wiki_bundle_dir").strip()
        if wiki_dir in {"", UNSET_WIKI_DIR}:
            pytest.skip("no live wiki bundle configured in the profile")
        if not (Path(wiki_dir).expanduser() / "index.md").is_file():
            pytest.skip(f"the profile's wiki directory is not a bundle: {wiki_dir}")
    return boot


def _leave_by_back_at_root(d: Driver) -> None:
    """Escape lifts focus to the top bar on Back; Back at the root exits the wiki."""
    d.key_then_wait(TOP_BAR, 15, "Escape")
    with d.expect("OKFViewer: Back at history root; exiting."), d.expect(MAIN_FROM_WIKI):
        d.key("Return")


def test_wiki_opens_from_its_node_and_back_leaves_it(wiki_boot: AppBoot) -> None:
    """Open the wiki from its node, then leave it with Back at the history root.

    The node resumes wherever the wiki was last left (a session file in the
    profile) and opens the home page when there is none, as in a fresh scratch
    profile; either way a page shows, and that is what is asserted.
    """
    d = wiki_boot(nodes.INDEXES)
    d.select_node(nodes.WIKI_NODE)
    with d.expect(WIKI_ACTIVE, 30), d.expect(SHOWED_PAGE, 30), d.expect(WIKI_ENTERED, 30):
        d.key("Return")
    _leave_by_back_at_root(d)


def test_wiki_from_a_story_chip_sidebar_back_and_goto_title(wiki_boot: AppBoot) -> None:
    """A story's wiki chip opens its page; the sidebar walks to another; Back; goto title."""
    d = wiki_boot(nodes.LOST_IN_THE_ANDES, cues=nodes.NO_CUES, ini=PREBUILT_COMICS)
    d.focus_portal()
    for _ in range(UPS_TO_WIKI_CHIP):
        d.key("Up")
        d.hold(BAR_PAUSE)
    with (
        d.expect("Wiki page button pressed."),
        d.expect(WIKI_ACTIVE, 30),
        d.expect(f"{SHOWED_PAGE} '.*lost-in-the-andes.md'", 30),
        d.expect(WIKI_ENTERED, 30),
    ):
        d.key("Return")

    d.key_then_wait("OKFViewer: Focus region SIDEBAR.", 15, "Left")
    for _ in range(SIDEBAR_STEPS):
        d.key("Down")
        d.hold(BAR_PAUSE)
    d.key_then_wait(SHOWED_PAGE, 30, "Return")  # the story picked out of the sidebar
    assert d.match_count(SHOWED_PAGE) >= TWO_PAGES

    d.key_then_wait(TOP_BAR, 15, "Escape")
    d.key_then_wait("OKFViewer: Back to '.*lost-in-the-andes.md'", 30, "Return")

    d.key_then_wait(TOP_BAR, 15, "Escape")
    for _ in range(BAR_RIGHTS_TO_GOTO):
        d.key("Right")
        d.hold(BAR_PAUSE)
    with (
        d.expect(r'Wiki goto title: "[A-Z_]+"'),
        d.expect(MAIN_FROM_WIKI),
        d.expect(f'New selected node: "{nodes.LOST_IN_THE_ANDES[0]}"'),
    ):
        d.key("Return")
