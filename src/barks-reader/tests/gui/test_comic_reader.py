"""The comic reader: page edges, the goto buttons, menu mode, and the history it keeps."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from barks_gui import expected, harness, nodes, tree
from barks_gui.logs import fields_of, last_field
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern
from gui_driver import Pick

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

CANNED_EVENTS = 6
TURNS_BEFORE_GOTO_START = 2
BROWSE_RANGE = "1947-1950"
GOTO_PAGE = 12
GOTO_PAGE_BACK = 3
READ = Pick(pages=2, dwell=0.0)
SHOWED_PAGE = pattern(markers.SHOWED_PAGE)


def _open_ghost_of_the_grotto(boot: AppBoot) -> Driver:
    d = boot(nodes.GHOST_OF_THE_GROTTO, cues=nodes.NO_CUES)
    d.open_selected_story()
    d.wait_for(SHOWED_PAGE)
    return d


def _two_up(boot: AppBoot) -> bool:
    """Whether the run booted the reader in double-page mode (the matrix does)."""
    return harness.read_ini_value(boot.scratch / "barks-reader.ini", "double_page_mode") == "1"


def _shows(boot: AppBoot, title: str, page_index: int) -> int:
    """Return the page the reader renders for `page_index`: itself, or two-up its unit's left."""
    return expected.unit_start(title, page_index) if _two_up(boot) else page_index


def test_browse_the_tree_to_a_story_and_read_it(boot: AppBoot) -> None:
    """The Stories > Chronological > a range > a title, opened, read, and closed."""
    d = boot(nodes.THE_STORIES, cues=nodes.NO_CUES)
    tree.collapse_all(d)
    tree.open_path(d, "The Stories", "Chronological", BROWSE_RANGE)
    d.select_node(nodes.GHOST_OF_THE_GROTTO[0])
    assert d.current_node() == nodes.GHOST_OF_THE_GROTTO[0]
    d.open_story(Pick(nodes.GHOST_OF_THE_GROTTO[0], pages=READ.pages, dwell=READ.dwell))
    assert d.current_page() >= 1, "a page must have turned before the reader closed"
    # The walk down the range passed through its titles one node at a time, and
    # the read turned one page at a time from the front.
    path = fields_of(d, markers.NEW_SELECTED_NODE, "name")
    assert path[-1] == nodes.GHOST_OF_THE_GROTTO[0]
    walked = path[path.index(BROWSE_RANGE) + 1 :]
    start, end = (int(y) for y in BROWSE_RANGE.split("-"))
    assert walked == expected.chrono_range_titles(start, end)[: len(walked)], (
        "the titles walked are the range's titles, in the data's order"
    )
    shown = [int(i) for i in fields_of(d, markers.SHOWED_PAGE, "index")]
    if _two_up(boot):
        assert shown == expected.unit_starts(nodes.GHOST_OF_THE_GROTTO_TITLE)[: len(shown)], shown
    else:
        assert shown == list(range(len(shown))), shown


def test_series_story_goto_page_and_double_page(boot: AppBoot) -> None:
    """Series > Donald Duck Adventures > a story: jump to a page, go two-up, close."""
    d = boot(nodes.SERIES, cues=nodes.NO_CUES)
    d.open_branch("Donald Duck Adventures")
    d.select_node(nodes.LOST_IN_THE_ANDES[0])
    d.open_selected_story()
    d.read_pages(READ)

    shows = _shows(boot, nodes.LOST_IN_THE_ANDES_TITLE, GOTO_PAGE)
    with d.expect(pattern(markers.GOTO_PAGE_SELECTED)):  # goto_page waits on the rest itself
        d.goto_page(GOTO_PAGE, shows=shows)
    assert d.current_page() == shows

    # The toggle goes the other way from wherever the run booted (the matrix boots two-up).
    with (
        d.expect(pattern(markers.DOUBLE_PAGE_TOGGLED, mode=not _two_up(boot))),
        d.expect(SHOWED_PAGE),
    ):
        d.press_menu_button("double_page")
    d.close_reader()


def test_reopening_the_goto_dropdown_steps_back_up(boot: AppBoot) -> None:
    """A second goto reopens the (cached) dropdown and can step Up to an earlier page."""
    d = _open_ghost_of_the_grotto(boot)
    title = nodes.GHOST_OF_THE_GROTTO_TITLE
    d.goto_page(GOTO_PAGE, shows=_shows(boot, title, GOTO_PAGE))
    with d.expect(pattern(markers.GOTO_PAGE_SELECTED)):
        d.goto_page(GOTO_PAGE_BACK, shows=_shows(boot, title, GOTO_PAGE_BACK))
    assert d.current_page() == _shows(boot, title, GOTO_PAGE_BACK)
    d.close_reader()


def test_one_pagers_ignore_double_page(boot: AppBoot) -> None:
    """A one-pager collection is always single-page: the toggle says so and does nothing."""
    d = boot(nodes.ONE_PAGERS)
    d.key_then_wait(pattern(markers.NEW_SELECTED_NODE, name=nodes.YEAR_RANGE_NODE), "Down")
    d.key_then_wait(pattern(markers.NODE_EXPANDED), "Return")
    d.key_then_wait(pattern(markers.NEW_SELECTED_NODE), "Down")  # the range's first one-pager
    d.open_selected_story()
    with d.expect(markers.DOUBLE_PAGE_IGNORED):
        d.press_menu_button("double_page")
    d.expect_no_new(SHOWED_PAGE, 1.0)
    d.close_reader()


def test_left_on_the_first_page_stays_put(boot: AppBoot) -> None:
    d = _open_ghost_of_the_grotto(boot)
    with d.expect(pattern(markers.ALREADY_ON_FIRST_PAGE)):
        d.key("Left")
    d.expect_no_new(SHOWED_PAGE, 1.0)
    d.close_reader()


def test_goto_end_then_right_is_the_last_page(boot: AppBoot) -> None:
    d = _open_ghost_of_the_grotto(boot)
    with d.expect(pattern(markers.GOTO_LAST_PAGE)), d.expect(SHOWED_PAGE):
        d.press_menu_button("goto_end")
    with d.expect(pattern(markers.ALREADY_ON_LAST_PAGE)):
        d.key("Right")
    # The page requested, the page shown and the page Right refused to leave all agree.
    last = int(last_field(d, markers.GOTO_LAST_PAGE, "index"))
    assert d.current_page() == last
    assert int(last_field(d, markers.ALREADY_ON_LAST_PAGE, "index")) == last
    assert last == expected.last_page_index(
        nodes.GHOST_OF_THE_GROTTO_TITLE, two_up=_two_up(boot)
    ), "the last page is the last of the layout the data builds for the story"
    d.close_reader()


def test_goto_start_returns_to_the_opening_page(boot: AppBoot) -> None:
    d = _open_ghost_of_the_grotto(boot)
    first = d.current_page()
    d.read_pages(Pick(pages=TURNS_BEFORE_GOTO_START + 1, dwell=0.0))
    assert d.current_page() != first
    with d.expect(pattern(markers.GOTO_START_PAGE)), d.expect(SHOWED_PAGE):
        d.press_menu_button("goto_start")
    assert d.current_page() == first
    d.close_reader()


def test_escape_opens_the_menu_and_never_closes_the_reader(boot: AppBoot) -> None:
    """Up or Escape enters menu mode; Escape there leaves it; nothing here closes."""
    d = _open_ghost_of_the_grotto(boot)
    d.key_then_wait(markers.MENU_ENTERED, "Up")
    d.key_then_wait(markers.MENU_EXITED, "Escape")
    d.key_then_wait(markers.MENU_ENTERED, "Escape")
    d.expect_no_new(pattern(markers.MAIN_SCREEN_ACTIVE), 2.0)
    d.key_then_wait(markers.MENU_EXITED, "Escape")
    d.close_reader()


def test_closing_a_story_saves_the_page_it_was_on(boot: AppBoot) -> None:
    """The last page read is written to the profile's json on close, keyed by title.

    That cue is what the title view's goto-page row and the reader's opening
    page come from on the next visit (test_title_view).
    """
    d = _open_ghost_of_the_grotto(boot)
    d.read_pages(Pick(pages=TURNS_BEFORE_GOTO_START + 1, dwell=0.0))
    page = d.current_page()
    d.close_reader()
    d.settle()
    settings = json.loads((boot.scratch / "barks-reader.json").read_text())
    cue = settings[nodes.GHOST_OF_THE_GROTTO_TITLE]["last_read_page"]
    assert cue["page_index"] == page


def test_opening_a_story_records_a_history_event(boot: AppBoot) -> None:
    """The reading history gets one event per open, written as soon as it opens."""
    d = _open_ghost_of_the_grotto(boot)
    d.close_reader()
    history = json.loads((boot.scratch / "barks-reader-history.json").read_text())
    events = history["events"]
    assert len(events) == CANNED_EVENTS + 1
    assert events[-1]["title"] == nodes.GHOST_OF_THE_GROTTO_TITLE
    assert events[-1]["closed_at"], "the close should have been recorded too"
    layout = expected.comic_layout(nodes.GHOST_OF_THE_GROTTO_TITLE)
    assert events[-1]["last_body_page"] == layout.last_body_page
