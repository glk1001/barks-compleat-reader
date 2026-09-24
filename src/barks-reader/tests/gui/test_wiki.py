"""The Carl Barks Wiki: opened from its node and from a story's chip, browsed, left.

Skipped when the profile points at no live wiki bundle. With the live bundle
off the app reads the copy under its Reader Files folder, which the harness
cannot see from the ini, so the tests run and fail if it is missing (the wiki
node is then absent) - a data gap to fix, not a reason to test less. The
wiki viewer logs through Kivy's logger, so its lines carry a ``kivy:`` prefix in
the app log; the patterns below are substrings of them.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_gui import expected, harness, nodes
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
# The wiki bundle the app reads when the live one is off: its copy under Reader Files.
BUNDLED_WIKI_SUBDIR = Path("Reader Files") / "Carl Barks Wiki"
SIDEBAR_STEPS = 2
# On the top bar Escape lands on Back; the goto-title button is this far right
# (the bar runs Back, contrast, goto-title, quit).
BAR_RIGHTS_TO_GOTO = 2
# Up from the read portal is the wiki chip when the title view shows no goto-page
# row (no cue) and no overrides row. The chip test's story has no optional
# override (special_overrides_handler lists the four that do), so that holds
# whatever the profile's use_prebuilt_comics: pinning prebuilt comics instead
# made the test need a prebuilt comics directory it never reads from.
UPS_TO_WIKI_CHIP = 1
# What the app writes for an unset wiki directory (reader_settings
# UNSET_WIKI_BUNDLE_DIR_MARKER); the key is never empty in an app-written ini.
UNSET_WIKI_DIR = "<Carl Barks Wiki Not Set>"


def _expand_path(value: str) -> Path:
    """Return an ini path as the app reads it: environment variables (``${HOME}``) and ``~``."""
    return Path(os.path.expandvars(value)).expanduser()


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
        if not (_expand_path(wiki_dir) / "index.md").is_file():
            pytest.skip(f"the profile's wiki directory is not a bundle: {wiki_dir}")
    return boot


def _wiki_bundle(app_boot: AppBoot) -> Path:
    """Return the bundle the app reads for this boot: the live one, or the copy in Reader Files."""
    ini = app_boot.scratch / "barks-reader.ini"
    if harness.read_ini_value(ini, "use_live_wiki_bundle").strip() != "0":
        return _expand_path(harness.read_ini_value(ini, "wiki_bundle_dir").strip())
    data_dir = harness.app_data_dir()
    assert data_dir is not None, "no app data directory to find the bundled wiki in"
    return data_dir / BUNDLED_WIKI_SUBDIR


def _story_page(app_boot: AppBoot, title: Titles) -> re.Pattern[str]:
    """Return a regex for the page `title`'s chip opens, from the wiki join the app uses."""
    page = expected.wiki_page(_wiki_bundle(app_boot), title)
    assert page is not None, f"the wiki bundle has no page for {title.name}"
    return re.compile(rf".*{re.escape(page.name)}")


def _leave_by_back_at_root(d: Driver) -> None:
    """Escape lifts focus to the top bar on Back; Back at the root exits the wiki."""
    d.key_then_wait(TOP_BAR, "Escape")
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
    story_page = _story_page(wiki_boot, Titles.GHOST_OF_THE_GROTTO_THE)
    d = wiki_boot(nodes.GHOST_OF_THE_GROTTO, cues=nodes.NO_CUES)
    d.focus_portal()
    d.move_focus(*["Up"] * UPS_TO_WIKI_CHIP)
    with (
        d.expect(markers.WIKI_PAGE_BUTTON_PRESSED),
        d.expect(WIKI_ACTIVE, 30),
        d.expect(pattern(wiki.PAGE_SHOWN, page=story_page), 30),
        d.expect(WIKI_ENTERED, 30),
    ):
        d.key("Return")

    d.key_then_wait(SIDEBAR, "Left")
    d.move_focus(*["Down"] * SIDEBAR_STEPS, pattern=d.WIKI_FOCUS_MOVED)
    d.key_then_wait(SHOWED_PAGE, "Return", timeout=30)  # the story picked out of the sidebar
    assert not story_page.search(d.last_line(SHOWED_PAGE)), "the sidebar pick must be another page"

    d.key_then_wait(TOP_BAR, "Escape")
    d.key_then_wait(pattern(wiki.BACK_TO, page=story_page), "Return", timeout=30)

    d.key_then_wait(TOP_BAR, "Escape")
    d.move_focus(*["Right"] * BAR_RIGHTS_TO_GOTO, pattern=d.WIKI_FOCUS_MOVED)
    with (
        d.expect(pattern(markers.WIKI_GOTO_TITLE, name=re.compile(r"[A-Z_]+"))),
        d.expect(MAIN_FROM_WIKI),
        d.expect(pattern(markers.NEW_SELECTED_NODE, name=nodes.GHOST_OF_THE_GROTTO[0])),
    ):
        d.key("Return")
