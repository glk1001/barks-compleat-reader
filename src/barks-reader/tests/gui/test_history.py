"""The reading history screen, on the canned six-event, three-title history."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from barks_gui import nodes
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

CANNED_EVENTS = 6
CANNED_TITLES = 3
NEWEST_EVENT_ID = "a0000000000000000000000000000006"
CLEAR_TITLE = "Clear Reading History"


def _events(boot: AppBoot) -> list[dict[str, str]]:
    return json.loads((boot.scratch / "barks-reader-history.json").read_text())["events"]


def _enter(boot: AppBoot) -> Driver:
    d = boot(nodes.HISTORY)
    d.wait_for(pattern(markers.HISTORY_BUILT_VIEW, view="journal", rows=CANNED_EVENTS))
    d.key_then_wait(markers.HISTORY_ENTERED_NAV, 15, "Right")
    return d


def _to_bar(d: Driver) -> None:
    """Up from the first row lands on the bar, on the tab of the view showing."""
    d.move_focus("Up")


def test_journal_builds_at_boot_and_the_titles_tab_rebuilds(boot: AppBoot) -> None:
    d = _enter(boot)
    _to_bar(d)
    d.move_focus("Right")  # Journal -> Titles
    with (
        d.expect(pattern(markers.HISTORY_SELECTED_VIEW, view="titles")),
        d.expect(pattern(markers.HISTORY_BUILT_VIEW, view="titles", rows=CANNED_TITLES)),
    ):
        d.key("Return")
    d.move_focus("Left")  # back to Journal, already built: mounted from the cache
    with d.expect(pattern(markers.HISTORY_MOUNTED_CACHED_VIEW, view="journal", rows=CANNED_EVENTS)):
        d.key("Return")


def test_return_on_a_row_goes_to_its_title(boot: AppBoot) -> None:
    d = _enter(boot)
    with (
        d.expect(pattern(markers.GOTO_TITLE)),
        d.expect(markers.ENTERED_BOTTOM_FOCUS_AT_PORTAL),
    ):
        d.key("Return")


def test_delete_removes_the_focused_event(boot: AppBoot) -> None:
    """Delete on a journal row removes that event, with no confirmation, and persists."""
    d = _enter(boot)
    d.key_then_wait(pattern(markers.HISTORY_DELETED_EVENT, event_id=NEWEST_EVENT_ID), 15, "Delete")
    d.settle()
    remaining = _events(boot)
    assert len(remaining) == CANNED_EVENTS - 1
    assert all(e["id"] != NEWEST_EVENT_ID for e in remaining)


def test_clear_asks_first_and_then_empties_the_history(boot: AppBoot) -> None:
    d = _enter(boot)
    _to_bar(d)
    d.move_focus("Right", "Right")  # Journal -> Titles -> Clear
    d.key_then_wait(pattern(markers.CONFIRM_POPUP_OPENED, title=CLEAR_TITLE), 15, "Return")
    # The popup owns the keys until it has closed, so wait for that too.
    with (
        d.expect(pattern(markers.CONFIRM_POPUP_CANCELLED, title=CLEAR_TITLE)),
        d.expect(pattern(markers.CONFIRM_POPUP_CLOSED, title=CLEAR_TITLE)),
    ):
        d.key("Escape")
    assert len(_events(boot)) == CANNED_EVENTS, "cancel must not clear"
    d.key_then_wait(pattern(markers.CONFIRM_POPUP_OPENED, title=CLEAR_TITLE), 15, "Return")
    with (
        d.expect(pattern(markers.CONFIRM_POPUP_CONFIRMED, title=CLEAR_TITLE)),
        d.expect(markers.HISTORY_CLEARED),
    ):
        d.key("Return")
    d.settle()
    assert _events(boot) == []
