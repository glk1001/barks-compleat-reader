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
from barks_gui import expected, harness, memory, nodes, taps
from barks_gui.logs import last_field
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


# The wiki's search box has no remote key of its own (Ctrl+F is a desktop key):
# these tap it, as a touch user does, then drive the results with the remote.
SEARCH_QUERY = "grotto"
NO_MATCH_QUERY = "qqqqx"  # cspell:disable-line
SEARCH_CLEARED = pattern(wiki.SEARCH_CLEARED)
PAGE_REGION = pattern(wiki.FOCUS_REGION, name="PAGE")


def _open_wiki_and_search(d: Driver, query: str) -> int:
    """Open the wiki from its node, tap its search box and type `query`; return the hit count."""
    d.select_node(nodes.WIKI_NODE)
    with d.expect(WIKI_ACTIVE, 30), d.expect(SHOWED_PAGE, 30), d.expect(WIKI_ENTERED, 30):
        d.key("Return")
    taps.tap(d, kind="TextInput")
    results = pattern(wiki.SEARCH_RESULTS, text=query)
    # Each keystroke searches; wait only on the full query's results (the index may
    # still be warming for the first ones, which then show a wait note instead).
    d.type_slowly(query, marker=lambda typed: results if typed == query else None)
    return int(last_field(d, wiki.SEARCH_RESULTS, "count", text=query))


def test_wiki_search_opens_hits_from_the_results_and_escape_clears_it(
    wiki_boot: AppBoot,
) -> None:
    """Return opens the top hit; the results take the remote's keys; Escape clears."""
    d = wiki_boot(nodes.INDEXES)
    count = _open_wiki_and_search(d, SEARCH_QUERY)
    assert count >= 2, f"only {count} wiki pages for {SEARCH_QUERY!r}"  # noqa: PLR2004
    d.key_then_wait(SHOWED_PAGE, "Return", timeout=30)  # the box's Return: the top hit
    top_hit = d.last_line(SHOWED_PAGE)

    # The wiki opens with the sidebar focused, and opening a hit leaves it there: the
    # first Down rings the open page's row, the next moves to the second hit.
    d.move_focus("Down", pattern=d.WIKI_FOCUS_MOVED)
    d.move_focus("Down", pattern=d.WIKI_FOCUS_MOVED)
    d.key_then_wait(SHOWED_PAGE, "Return", timeout=30)
    assert d.last_line(SHOWED_PAGE) != top_hit, "Down then Return opens the second hit"

    d.key_then_wait(PAGE_REGION, "Right")
    d.key_then_wait(SEARCH_CLEARED, "Escape")  # Escape unwinds the search before the bar


def test_wiki_search_with_no_match_says_so(wiki_boot: AppBoot) -> None:
    d = wiki_boot(nodes.INDEXES)
    assert _open_wiki_and_search(d, NO_MATCH_QUERY) == 0


SEARCH_FOCUSED = pattern(wiki.SEARCH_FOCUSED)
SEARCH_LEFT = pattern(wiki.SEARCH_LEFT)
MAX_TREE_UPS = 40


def _up_into_the_search_box(d: Driver) -> None:
    """Step Up the sidebar until the focus leaves its top for the search box."""
    for _ in range(MAX_TREE_UPS):
        before = d.match_count(SEARCH_FOCUSED)
        d.key("Up")
        d.settle()
        if d.match_count(SEARCH_FOCUSED) > before:
            return
    msg = f"no search box within {MAX_TREE_UPS} Ups"
    raise AssertionError(msg)


def test_wiki_search_by_remote_alone(wiki_boot: AppBoot) -> None:
    """Up off the tree's top enters the box; Down leaves it for the results; Up returns."""
    d = wiki_boot(nodes.INDEXES)
    d.select_node(nodes.WIKI_NODE)
    with d.expect(WIKI_ACTIVE, 30), d.expect(SHOWED_PAGE, 30), d.expect(WIKI_ENTERED, 30):
        d.key("Return")
    _up_into_the_search_box(d)
    results = pattern(wiki.SEARCH_RESULTS, text=SEARCH_QUERY)
    d.type_slowly(SEARCH_QUERY, marker=lambda typed: results if typed == SEARCH_QUERY else None)
    with d.expect(d.WIKI_FOCUS_MOVED):  # the first result, ringed
        d.key_then_wait(SEARCH_LEFT, "Down")
    d.key_then_wait(SEARCH_FOCUSED, "Up")  # off the first result: back into the box
    d.key_then_wait(SEARCH_LEFT, "Down")
    d.key_then_wait(SHOWED_PAGE, "Return", timeout=30)


def test_wiki_round_trips_leave_no_pages_behind(wiki_boot: AppBoot) -> None:
    """Open the wiki, open a page from the sidebar, go Back, leave: again and again.

    Each page is built afresh, hundreds of labels for a long one; a round that
    kept its pages alive after the wiki was left would show in the census.
    """
    d = wiki_boot(nodes.INDEXES)
    d.select_node(nodes.WIKI_NODE)

    def round_trip() -> None:
        with d.expect(WIKI_ACTIVE, 30), d.expect(SHOWED_PAGE, 30), d.expect(WIKI_ENTERED, 30):
            d.key("Return")
        # The wiki opens with the sidebar focused.
        d.move_focus(*["Down"] * SIDEBAR_STEPS, pattern=d.WIKI_FOCUS_MOVED)
        d.key_then_wait(SHOWED_PAGE, "Return", timeout=30)
        d.key_then_wait(TOP_BAR, "Escape")
        d.key_then_wait(pattern(wiki.BACK_TO), "Return", timeout=30)
        _leave_by_back_at_root(d)

    memory.assert_round_trips_leave_nothing(d, round_trip)
