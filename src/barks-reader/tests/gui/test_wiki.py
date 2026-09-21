"""The Carl Barks Wiki: opened from its node and from a story's chip, browsed, left.

Skipped when the profile points at no live wiki bundle. With the live bundle
off the app reads the copy under its Reader Files folder, which the harness
cannot see from the ini, so the tests run and fail if it is missing (the wiki
node is then absent) - a data gap to fix, not a reason to test less. The
wiki viewer logs through Kivy's logger, so its lines carry a ``kivy:`` prefix in
the app log; the patterns below are substrings of them.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from barks_gui import harness, nodes
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern
from okf_reader.core import log_markers as wiki

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

WIKI_ACTIVE = markers.WIKI_READER_ACTIVE
WIKI_ENTERED = pattern(markers.SCREEN_ENTERED, name="wiki_reader")  # the transition has finished
MAIN_FROM_WIKI = pattern(markers.MAIN_SCREEN_ACTIVE, origin=markers.FROM_WIKI_READER)
SHOWED_PAGE = pattern(wiki.PAGE_SHOWN)
TOP_BAR = pattern(wiki.FOCUS_REGION, name="TOP_BAR")
SIDEBAR = pattern(wiki.FOCUS_REGION, name="SIDEBAR")
ANDES_PAGE = re.compile(r".*lost-in-the-andes\.md")
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
    with d.expect(wiki.BACK_EXIT), d.expect(MAIN_FROM_WIKI):
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
    d.move_focus(*["Up"] * UPS_TO_WIKI_CHIP)
    with (
        d.expect(markers.WIKI_PAGE_BUTTON_PRESSED),
        d.expect(WIKI_ACTIVE, 30),
        d.expect(pattern(wiki.PAGE_SHOWN, page=ANDES_PAGE), 30),
        d.expect(WIKI_ENTERED, 30),
    ):
        d.key("Return")

    d.key_then_wait(SIDEBAR, 15, "Left")
    d.move_focus(*["Down"] * SIDEBAR_STEPS, pattern=d.WIKI_FOCUS_MOVED)
    d.key_then_wait(SHOWED_PAGE, 30, "Return")  # the story picked out of the sidebar
    assert d.match_count(SHOWED_PAGE) >= TWO_PAGES

    d.key_then_wait(TOP_BAR, 15, "Escape")
    d.key_then_wait(pattern(wiki.BACK_TO, page=ANDES_PAGE), 30, "Return")

    d.key_then_wait(TOP_BAR, 15, "Escape")
    d.move_focus(*["Right"] * BAR_RIGHTS_TO_GOTO, pattern=d.WIKI_FOCUS_MOVED)
    with (
        d.expect(pattern(markers.WIKI_GOTO_TITLE, name=re.compile(r"[A-Z_]+"))),
        d.expect(MAIN_FROM_WIKI),
        d.expect(pattern(markers.NEW_SELECTED_NODE, name=nodes.LOST_IN_THE_ANDES[0])),
    ):
        d.key("Return")
