"""The reading history screen, on the canned six-event, three-title history."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from barks_gui import nodes

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

CANNED_EVENTS = 6
CANNED_TITLES = 3
NEWEST_EVENT_ID = "a0000000000000000000000000000006"
BAR_PAUSE = 0.4
CLEAR_TITLE = "Clear Reading History"


def _events(boot: AppBoot) -> list[dict[str, str]]:
    return json.loads((boot.scratch / "barks-reader-history.json").read_text())["events"]


def _enter(boot: AppBoot) -> Driver:
    d = boot(nodes.HISTORY)
    d.wait_for(f"History: built 'journal' view with {CANNED_EVENTS} rows.")
    d.key_then_wait("HistoryScreen: entered nav focus.", 15, "Right")
    return d


def _to_bar(d: Driver) -> None:
    """Up from the first row lands on the bar, on the tab of the view showing."""
    d.key("Up")
    d.hold(BAR_PAUSE)


def test_journal_builds_at_boot_and_the_titles_tab_rebuilds(boot: AppBoot) -> None:
    d = _enter(boot)
    _to_bar(d)
    d.key("Right")  # Journal -> Titles
    d.hold(BAR_PAUSE)
    with (
        d.expect("History: selected 'titles' view."),
        d.expect(f"History: built 'titles' view with {CANNED_TITLES} rows."),
    ):
        d.key("Return")
    d.key("Left")  # back to Journal, already built: mounted from the cache
    d.hold(BAR_PAUSE)
    with d.expect(f"History: mounted cached 'journal' view with {CANNED_EVENTS} rows."):
        d.key("Return")


def test_return_on_a_row_goes_to_its_title(boot: AppBoot) -> None:
    d = _enter(boot)
    with d.expect("Goto title:"), d.expect("Entered bottom focus region at the title portal."):
        d.key("Return")


def test_delete_removes_the_focused_event(boot: AppBoot) -> None:
    """Delete on a journal row removes that event, with no confirmation, and persists."""
    d = _enter(boot)
    d.key_then_wait(f'History: deleted event "{NEWEST_EVENT_ID}".', 15, "Delete")
    d.settle()
    remaining = _events(boot)
    assert len(remaining) == CANNED_EVENTS - 1
    assert all(e["id"] != NEWEST_EVENT_ID for e in remaining)


def test_clear_asks_first_and_then_empties_the_history(boot: AppBoot) -> None:
    d = _enter(boot)
    _to_bar(d)
    for _ in range(2):  # Journal -> Titles -> Clear
        d.key("Right")
        d.hold(BAR_PAUSE)
    d.key_then_wait(f'Confirm popup opened: "{CLEAR_TITLE}".', 15, "Return")
    d.key_then_wait(f'Confirm popup "{CLEAR_TITLE}": cancelled.', 15, "Escape")
    assert len(_events(boot)) == CANNED_EVENTS, "cancel must not clear"
    d.hold(BAR_PAUSE)
    d.key_then_wait(f'Confirm popup opened: "{CLEAR_TITLE}".', 15, "Return")
    with d.expect(f'Confirm popup "{CLEAR_TITLE}": confirmed.'), d.expect("History: cleared."):
        d.key("Return")
    d.settle()
    assert _events(boot) == []
