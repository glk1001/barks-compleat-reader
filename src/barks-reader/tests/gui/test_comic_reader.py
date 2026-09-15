"""The comic reader: page edges, the goto buttons, menu mode, and the history it keeps."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from barks_gui import nodes, reader
from gui_driver import Pick

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

CANNED_EVENTS = 6
TURNS_BEFORE_GOTO_START = 2


def _open_ghost_of_the_grotto(boot: AppBoot) -> Driver:
    d = boot(nodes.GHOST_OF_THE_GROTTO, cues=nodes.NO_CUES)
    reader.open_selected_story(d)
    d.wait_for("Showed page")
    return d


def test_left_on_the_first_page_stays_put(boot: AppBoot) -> None:
    d = _open_ghost_of_the_grotto(boot)
    with d.expect("Already on the first page"):
        d.key("Left")
    d.expect_no_new("Showed page", 1.0)
    d.close_reader()


def test_goto_end_then_right_is_the_last_page(boot: AppBoot) -> None:
    d = _open_ghost_of_the_grotto(boot)
    with d.expect("Last page: requested index"), d.expect("Showed page"):
        d.press_menu_button("goto_end")
    with d.expect("Already on the last page"):
        d.key("Right")
    d.close_reader()


def test_goto_start_returns_to_the_opening_page(boot: AppBoot) -> None:
    d = _open_ghost_of_the_grotto(boot)
    first = d.current_page()
    d.read_pages(Pick(pages=TURNS_BEFORE_GOTO_START + 1, dwell=0.0))
    assert d.current_page() != first
    with d.expect("Goto start page: requested index"), d.expect("Showed page"):
        d.press_menu_button("goto_start")
    assert d.current_page() == first
    d.close_reader()


def test_escape_opens_the_menu_and_never_closes_the_reader(boot: AppBoot) -> None:
    """Up or Escape enters menu mode; Escape there leaves it; nothing here closes."""
    d = _open_ghost_of_the_grotto(boot)
    d.key_then_wait("Entered menu mode.", 15, "Up")
    d.key_then_wait("Exited menu mode.", 15, "Escape")
    d.key_then_wait("Entered menu mode.", 15, "Escape")
    d.expect_no_new("Main screen is active", 2.0)
    d.key_then_wait("Exited menu mode.", 15, "Escape")
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
