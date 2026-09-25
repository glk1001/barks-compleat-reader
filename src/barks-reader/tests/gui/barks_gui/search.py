"""Search-screen moves: typing a query, and picking results from the keyboard.

Return in the search box hands the keyboard to the first result row (or the
first chip, in tag and word mode); Down walks the rows and Right on a word row
moves to its speech balloon. Every move waits on the focus line the app logs
for it, and every pick on the line naming what it landed on, so a layout change
fails the test instead of quietly picking a different story. Nothing here
clicks: the rows were once reached by pixel, which tied the suite to one window
size and broke whenever the screen was rearranged.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern

if TYPE_CHECKING:
    from gui_driver import Driver

# The box takes the keyboard a moment after Return asks for it, and logs when it has.
SEARCH_BOX_FOCUSED = pattern(markers.SEARCH_BOX_FOCUS, mode=re.compile(r"\w+"), state="focused")


def _results_line(typed: str) -> str | None:
    """Return the line the app logs for `typed` in any search mode; None for one character.

    Title and tag search do nothing on a single character, and the word search
    logs on every one, so the first keystroke is the only one typed on the clock.
    """
    if len(typed) <= 1:
        return None
    return "|".join(
        pattern(marker, text=typed)
        for marker in (
            markers.SEARCH_TITLE_RESULTS,
            markers.SEARCH_TAG_RESULTS,
            markers.WORD_SEARCH_MATCHED,
        )
    )


def type_query(d: Driver, query: str) -> None:
    """Focus the search box from the tree node and type a query, a keystroke at a time.

    Each keystroke after the first waits on the results line it produces.
    """
    d.key_then_wait(SEARCH_BOX_FOCUSED, "Return")
    d.type_slowly(query, marker=_results_line)


def _focus_result_row(d: Driver, row: int) -> None:
    """Leave the box for the first result row and step Down to `row` (counting from 1)."""
    d.key_then_wait(d.FOCUS_MOVED, "Return")
    d.move_focus(*["Down"] * (row - 1))


def pick_title_result(d: Driver, row: int, title_enum: str) -> None:
    """Return on title-result `row` and wait for the goto to that title.

    A result picked from the keyboard hands focus to the title's read portal, so
    this also waits for that; a `wait_title_fade` after it then lets the Enter
    that opens the comic go out once the panel has faded in.
    """
    _focus_result_row(d, row)
    with (
        d.expect(pattern(markers.GOTO_TITLE, name=title_enum)),
        d.expect(d.ENTERED_AT_PORTAL),
    ):
        d.key("Return")


def open_word_balloon(d: Driver, row: int, title: str) -> None:
    """Return on the balloon of word-result `row` and wait for that story's bubbles popup.

    Returns once the popup has drawn its focus on the first bubble, so a Return
    straight after presses it.
    """
    _focus_result_row(d, row)
    d.move_focus("Right")  # the row's title -> its balloon
    with (
        d.expect(pattern(markers.SHOW_BUBBLES_FOR_SEARCH, title=title)),
        d.expect(markers.BUBBLES_POPUP_OPENED),
        d.expect(d.FOCUS_MOVED),
    ):
        d.key("Return")


def press_first_bubble(d: Driver, title: str) -> None:
    """Return on the bubble the popup opened focused on, and wait for the goto it triggers.

    The bubble press is logged some 250ms before the story's title view starts
    to fade in, so this also waits for that start: a `wait_title_fade` after it
    then waits on this fade and not on an earlier one already finished.
    """
    with (
        d.expect(pattern(markers.WORD_BUBBLE_PRESS, title=title)),
        d.expect(markers.BUBBLES_POPUP_DISMISSED),
        d.expect(d.FADE_STARTED),
    ):
        d.key("Return")
