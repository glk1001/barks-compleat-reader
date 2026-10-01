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
from okf_reader.core.render import BundleDir, ConceptNode, list_children

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
SEARCH_FOCUSED = pattern(wiki.SEARCH_FOCUSED)


def _open_wiki_and_search(d: Driver, query: str) -> int:
    """Open the wiki from its node, tap its search box and type `query`; return the hit count."""
    d.select_node(nodes.WIKI_NODE)
    with d.expect(WIKI_ACTIVE, 30), d.expect(SHOWED_PAGE, 30), d.expect(WIKI_ENTERED, 30):
        d.key("Return")
    # The box takes the keyboard a moment after the tap: a letter typed before
    # then is lost (an overnight 1080p run lost the first letter of its query).
    with d.expect(SEARCH_FOCUSED):
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


KEY_PRESSED = pattern(markers.KEY_PRESSED)
# Up/Down scrolls a link-free stretch without a log line, so a walk to a link is
# bounded by presses, not by a marker.
MAX_LINK_STEPS = 40
# The story page's first paragraph links Donald first, and its first footnote
# marker, [^bib], follows the paragraph's four links.
FIRST_LINK = re.compile(r".*characters/donald-duck\.md")
FIRST_FOOTNOTE = "fn:bib"


def _down_to_link(d: Driver, ref: str | re.Pattern[str]) -> None:
    """Press Down until the page's link highlight lands on `ref`."""
    focused = pattern(wiki.LINK_FOCUS, ref=ref)
    for _ in range(MAX_LINK_STEPS):
        before = d.match_count(focused)
        d.key_then_wait(KEY_PRESSED, "Down")
        if d.match_count(focused) > before:
            return
    msg = f"no link focus on /{focused}/ within {MAX_LINK_STEPS} Downs"
    raise AssertionError(msg)


def _open_story_page(app_boot: AppBoot) -> tuple[Driver, re.Pattern[str]]:
    """Boot on the chip test's story, open its wiki page from the chip; the page has the keys."""
    story_page = _story_page(app_boot, Titles.GHOST_OF_THE_GROTTO_THE)
    d = app_boot(nodes.GHOST_OF_THE_GROTTO, cues=nodes.NO_CUES)
    d.focus_portal()
    d.move_focus(*["Up"] * UPS_TO_WIKI_CHIP)
    with (
        d.expect(pattern(wiki.PAGE_SHOWN, page=story_page), 30),
        d.expect(WIKI_ENTERED, 30),
    ):
        d.key("Return")
    return d, story_page


def test_a_pages_links_are_walked_and_followed_by_remote(wiki_boot: AppBoot) -> None:
    """Down walks to the page's first link, Return follows it, and Back (on the bar) returns."""
    d, story_page = _open_story_page(wiki_boot)
    _down_to_link(d, FIRST_LINK)
    d.key_then_wait(pattern(wiki.PAGE_SHOWN, page=FIRST_LINK, depth=2), "Return", timeout=30)
    d.key_then_wait(TOP_BAR, "Escape")
    d.key_then_wait(pattern(wiki.BACK_TO, page=story_page), "Return", timeout=30)


def test_a_footnote_opens_in_its_popup_and_escape_closes_it(wiki_boot: AppBoot) -> None:
    """Return on a footnote marker shows its note; Escape closes it; the page has the keys again."""
    d, _story_page = _open_story_page(wiki_boot)
    _down_to_link(d, FIRST_FOOTNOTE)
    d.key_then_wait(pattern(wiki.FOOTNOTE_OPENED, ref=FIRST_FOOTNOTE), "Return")
    d.key_then_wait(pattern(wiki.FOOTNOTE_CLOSED), "Escape")
    _down_to_link(d, re.compile(r"fn:.*"))  # the next marker: the page walks on


def _tree_focused(node: str) -> str:
    return pattern(wiki.TREE_FOCUS, node=node)


def test_the_tree_opens_steps_in_and_out_and_closes_by_remote(wiki_boot: AppBoot) -> None:
    """Right opens a section, steps into it, and on a page opens it; Left steps out and closes.

    The expectations come from the bundle, through the viewer's own listing
    (the order its index pages give), not from names written here.
    """
    d = wiki_boot(nodes.INDEXES)
    d.select_node(nodes.WIKI_NODE)
    with d.expect(WIKI_ACTIVE, 30), d.expect(SHOWED_PAGE, 30), d.expect(WIKI_ENTERED, 30):
        d.key("Return")
    d.move_focus(*["Down"] * SIDEBAR_STEPS, pattern=d.WIKI_FOCUS_MOVED)
    section_name = last_field(d, wiki.TREE_FOCUS, "node")
    sections = [c for c in list_children(_wiki_bundle(wiki_boot)) if isinstance(c, BundleDir)]
    section = next((c for c in sections if (c.title or c.name) == section_name), None)
    assert section is not None, f"{section_name!r} is not a section of the bundle"
    children = list_children(section.path)
    first_page = next(i for i, c in enumerate(children) if isinstance(c, ConceptNode))

    def child_name(child: BundleDir | ConceptNode) -> str:
        return child.title or child.name if isinstance(child, BundleDir) else child.title

    d.key_then_wait(pattern(wiki.TREE_BRANCH_OPENED, node=section_name), "Right")
    d.key_then_wait(_tree_focused(child_name(children[0])), "Right")  # into its first child
    d.key_then_wait(_tree_focused(section_name), "Left")  # back out to the section
    d.key_then_wait(pattern(wiki.TREE_BRANCH_CLOSED, node=section_name), "Left")

    d.key_then_wait(pattern(wiki.TREE_BRANCH_OPENED, node=section_name), "Right")
    d.key_then_wait(_tree_focused(child_name(children[0])), "Right")
    for child in children[1 : first_page + 1]:
        d.key_then_wait(_tree_focused(child_name(child)), "Down")
    page = children[first_page].path.relative_to(_wiki_bundle(wiki_boot)).as_posix()
    with d.expect(pattern(wiki.FOCUS_REGION, name="PAGE")):
        d.key_then_wait(pattern(wiki.PAGE_SHOWN, page=page), "Right", timeout=30)


# The bar's buttons as the focus ring names them: Contrast is an icon toggle (a
# text one standalone), the home icon a plain Button.
CONTRAST_RINGED = pattern(wiki.FOCUS_RING, widget=re.compile(r"\w*ToggleButton.*"))
HOME_RINGED = pattern(wiki.FOCUS_RING, widget="Button")


def _open_wiki_from_its_node(d: Driver) -> None:
    d.select_node(nodes.WIKI_NODE)
    with d.expect(WIKI_ACTIVE, 30), d.expect(SHOWED_PAGE, 30), d.expect(WIKI_ENTERED, 30):
        d.key("Return")


def test_the_top_bar_is_walked_and_contrast_toggled_by_remote(wiki_boot: AppBoot) -> None:
    """Escape lifts to the bar on Back; Right reaches Contrast; Return toggles; Down drops out."""
    d = wiki_boot(nodes.INDEXES)
    _open_wiki_from_its_node(d)
    for state in ("on", "off"):
        d.key_then_wait(TOP_BAR, "Escape")  # the ring starts on Back
        d.key_then_wait(CONTRAST_RINGED, "Right")
        with d.expect(SIDEBAR):  # the focus goes back where it came from, then the toggle
            d.key_then_wait(pattern(wiki.CONTRAST, state=state), "Return")
    d.key_then_wait(TOP_BAR, "Escape")
    d.key_then_wait(HOME_RINGED, "Left")
    d.key_then_wait(d.WIKI_FOCUS_MOVED, "Left")  # wraps to the last button, Quit
    d.key_then_wait(SIDEBAR, "Down")  # out of the bar, nothing pressed


BIBLIOGRAPHY = pattern(wiki.PAGE_SHOWN, page=re.compile(r".*reference/data/bibliography\.md"))
# What the bibliography page may add to the app's widgets, its table scrolled into
# view: the page's own blocks and a screen of row Labels. Built whole, its ~940-row
# table alone was over 940 Labels (okf_reader's LAZY_TABLE_MIN_ROWS).
LONG_TABLE_WIDGET_LIMIT = 400
# Down presses that scroll the page well into its table (a link-free stretch: each
# press scrolls a step).
LONG_TABLE_SCROLL_STEPS = 40


def test_a_long_tables_rows_are_built_only_near_the_view(wiki_boot: AppBoot) -> None:
    """The bibliography's table, scrolled through, holds a screen of rows, not all of them.

    Kivy frees a widget only on a full garbage collection, so a page that built every
    row of a thousand-row table left them all as garbage each time it was left: on
    Windows a soak walk paging the bibliography passed 6 GB.
    """
    d = wiki_boot(nodes.INDEXES)
    _open_wiki_and_search(d, "bibliography")
    before = memory.census(d)
    d.key_then_wait(BIBLIOGRAPHY, "Return", timeout=30)  # the top hit
    d.key_then_wait(PAGE_REGION, "Right")
    for _ in range(LONG_TABLE_SCROLL_STEPS):
        d.key_then_wait(KEY_PRESSED, "Down")
    after = memory.census(d)
    added = after.widgets - before.widgets
    assert added < LONG_TABLE_WIDGET_LIMIT, (
        f"the bibliography page added {added} widgets (limit {LONG_TABLE_WIDGET_LIMIT})"
    )
