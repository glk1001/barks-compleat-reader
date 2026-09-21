"""The comic reader: page edges, the goto buttons, menu mode, and the history it keeps."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from barks_gui import nodes, tree
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


def test_browse_the_tree_to_a_story_and_read_it(boot: AppBoot) -> None:
    """The Stories > Chronological > a range > a title, opened, read, and closed."""
    d = boot(nodes.THE_STORIES, cues=nodes.NO_CUES)
    tree.collapse_all(d)
    tree.open_path(d, "The Stories", "Chronological", BROWSE_RANGE)
    d.select_node(nodes.GHOST_OF_THE_GROTTO[0])
    assert d.current_node() == nodes.GHOST_OF_THE_GROTTO[0]
    d.open_story(Pick(nodes.GHOST_OF_THE_GROTTO[0], pages=READ.pages, dwell=READ.dwell))
    assert d.current_page() >= 1, "a page must have turned before the reader closed"


def test_series_story_goto_page_and_double_page(boot: AppBoot) -> None:
    """Series > Donald Duck Adventures > a story: jump to a page, go two-up, close."""
    d = boot(nodes.SERIES, cues=nodes.NO_CUES)
    d.open_branch("Donald Duck Adventures")
    d.select_node(nodes.LOST_IN_THE_ANDES[0])
    d.open_selected_story()
    d.read_pages(READ)

    with d.expect(pattern(markers.GOTO_PAGE_SELECTED)):  # goto_page waits on the rest itself
        d.goto_page(GOTO_PAGE)
    assert d.current_page() == GOTO_PAGE

    with d.expect(pattern(markers.DOUBLE_PAGE_TOGGLED, mode=True)), d.expect(SHOWED_PAGE):
        d.press_menu_button("double_page")
    d.close_reader()


def test_reopening_the_goto_dropdown_steps_back_up(boot: AppBoot) -> None:
    """A second goto reopens the (cached) dropdown and can step Up to an earlier page."""
    d = _open_ghost_of_the_grotto(boot)
    d.goto_page(GOTO_PAGE)
    with d.expect(pattern(markers.GOTO_PAGE_SELECTED)):
        d.goto_page(GOTO_PAGE_BACK)
    assert d.current_page() == GOTO_PAGE_BACK
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


def test_opening_a_story_records_a_history_event(boot: AppBoot) -> None:
    """The reading history gets one event per open, written as soon as it opens."""
    d = _open_ghost_of_the_grotto(boot)
    d.close_reader()
    history = json.loads((boot.scratch / "barks-reader-history.json").read_text())
    events = history["events"]
    assert len(events) == CANNED_EVENTS + 1
    assert events[-1]["title"] == nodes.GHOST_OF_THE_GROTTO_TITLE
    assert events[-1]["closed_at"], "the close should have been recorded too"
