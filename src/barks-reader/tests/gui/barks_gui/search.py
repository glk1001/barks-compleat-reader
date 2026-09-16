"""Search-screen moves, including the result rows that can only be clicked.

The rows are clicked rather than keyed: the search box keeps the keyboard, so
Down moves the text cursor instead of the selection, and whether a press reaches
the list at all varies run to run. Clicking is exact on the nested display (no
compositor, no HiDPI scaling), and every click here waits on the log line naming
what it landed on, so a layout change fails the test instead of quietly picking a
different story. The coordinates are screenshot pixels at the pinned window size
(``harness.EXPECTED_WINDOW``); ``require_geometry`` guards every use. The demo
recorder (``scripts/record_demo.py``) carries the same measurements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui.harness import require_geometry
from gui_driver import Driver

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

SEARCH_BOX_PAUSE = 0.6  # after Return focuses the search box, before typing

# Title results: one row per match, top row first.
TITLE_RESULT_X = 450
TITLE_RESULT_TOP_Y = 695  # centre of the first row
TITLE_RESULT_ROW_H = 30

# Word results: every row ends in a speech balloon opening that story's bubbles.
WORD_BALLOON_X = 728
WORD_RESULT_TOP_Y = 697  # centre of the first row
WORD_RESULT_ROW_H = 29
# The first bubble in the popup for the word "airline" in Adventure Down Under.
WORD_BUBBLE_X = 232
WORD_BUBBLE_Y = 843


def type_query(d: Driver, query: str) -> None:
    """Focus the search box from the tree node and type a query into it."""
    d.key("Return")
    d.settle()
    d.hold(SEARCH_BOX_PAUSE)
    d.type_slowly(query)
    d.settle()


def click_title_result(boot: AppBoot, d: Driver, row: int, title_enum: str) -> None:
    """Click title-result `row` (counting from 1) and wait for the goto to that title.

    Returns once the title view's fade has started, so a `wait_title_fade`
    after this waits on the fade the click caused and not on an earlier one
    already finished in the log.
    """
    require_geometry(boot)
    y = TITLE_RESULT_TOP_Y + (row - 1) * TITLE_RESULT_ROW_H
    with d.expect(Driver.FADE_STARTED, 15):
        d.click_then_wait(f'Goto title: "{title_enum}"', 15, TITLE_RESULT_X, y)


def click_word_balloon(boot: AppBoot, d: Driver, row: int, title: str) -> None:
    """Click the balloon on word-result `row` and wait for that story's bubbles popup."""
    require_geometry(boot)
    y = WORD_RESULT_TOP_Y + (row - 1) * WORD_RESULT_ROW_H
    d.click_then_wait(f'Show speech bubbles for: "{title}" and search', 15, WORD_BALLOON_X, y)


def click_first_bubble(boot: AppBoot, d: Driver, title: str) -> None:
    """Click the first bubble in the popup and wait for the goto it triggers.

    The bubble press is logged some 250ms before the story's title view starts
    to fade in, so this also waits for that start (see `click_title_result`).
    """
    require_geometry(boot)
    with d.expect(Driver.FADE_STARTED, 15):
        d.click_then_wait(f'Word search bubble press: "{title}"', 15, WORD_BUBBLE_X, WORD_BUBBLE_Y)
