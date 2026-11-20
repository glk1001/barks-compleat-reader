"""Markers, limits and short key sequences that more than one GUI test file needs.

What is here was written once per test file before: the dots menu's order above all,
which two files each counted for themselves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern
from gui_driver import Pick

if TYPE_CHECKING:
    from gui_driver import Driver

ANY_NODE_SELECTED = pattern(markers.NEW_SELECTED_NODE)
SHOWED_PAGE = pattern(markers.SHOWED_PAGE)
DOCUMENT_ENTERED = pattern(markers.SCREEN_ENTERED, name="document_reader")
MAIN_FROM_DOCUMENT = pattern(markers.MAIN_SCREEN_ACTIVE, origin=markers.FROM_DOCUMENT_READER)

# Seconds for the window to go fullscreen or come back: the desktop animates it.
FULLSCREEN_TIMEOUT = 20
# Presses of "change pictures" allowed before a new one must have come: a pick may repeat.
CHANGE_PICS_TRIES = 6
# A short read: the page a story opens on and one turn, with no rest on either.
READ = Pick(pages=2, dwell=0.0)

# The dots menu opens focused on its first entry: Settings, How To, Update Data, About.
HOW_TO_DOWNS = 1
UPDATE_DATA_DOWNS = 2
ABOUT_DOWNS = 3


def open_dots_menu(d: Driver, downs: int) -> None:
    """Open the dots menu, which lands focus on its first entry, and step down `downs`."""
    d.main_menu_button_then_wait("menu", d.FOCUS_MOVED)
    d.move_focus(*["Down"] * downs)


def open_selected_story_to_its_first_page(d: Driver) -> Driver:
    """Open the story the tree is on and wait for the reader to show a page."""
    d.open_selected_story()
    d.wait_for(SHOWED_PAGE)
    return d


def open_document(d: Driver, name: str) -> None:
    """Select the document's node and open it, waiting for its first page to be up."""
    d.select_node(name)
    with (
        d.expect(pattern(markers.DOCUMENT_READER_ACTIVE)),
        d.expect(pattern(markers.DOCUMENT_OPENED)),
        d.expect(pattern(markers.DOCUMENT_PAGE, page=1)),
        d.expect(DOCUMENT_ENTERED),  # the transition has finished before any key is sent
    ):
        d.key("Return")
