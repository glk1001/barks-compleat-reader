"""Every title's notes fit the title panel, on this run's screen and layout.

The panel shows the lines that fit under the title info and silently drops the rest, and
what fits depends on the window: font sizes and line pitches round to whole pixels, and the
info rows differ by title. So a note is measured where it is shown, by walking every story
in the Chronological branch on the remote's Down key and reading what the label logs.

The walk takes minutes and says nothing about any other screen, so the default run skips
it: ``run_gui_tests.sh --notes-fit`` selects it alone, with ``--screen WxH`` and
``--ini main_screen_layout=...`` for the screen and layout, and the overnight ``notes-fit``
stage runs it on each. ``BARKS_GUI_NOTES_FULLSCREEN=1`` walks in fullscreen instead (on a
portrait screen narrower than a page, 2026-11-04, nine notes lose up to three lines).
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics.barks_extra_info import BARKS_EXTRA_INFO
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from barks_gui import nodes, tree
from barks_reader.core import log_markers as markers
from barks_reader.core.filtered_title_lists import FilteredTitleLists
from barks_reader.core.log_markers import pattern
from barks_reader.core.reader_consts_and_types import CHRONO_YEAR_RANGES
from gui_driver import DriverError

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

FULLSCREEN = os.environ.get("BARKS_GUI_NOTES_FULLSCREEN") == "1"
FULLSCREEN_TIMEOUT = 20
LAID_OUT = pattern(markers.TEXT_LAID_OUT)
LINES_AND_SHOWN = re.compile(r"Text laid out: (\d+) lines, (\d+) shown")
CUT = re.compile(pattern(markers.TEXT_CUT_SHORT))
NOTE_TITLES = {title.name for title in BARKS_EXTRA_INFO}
# A story's node is logged by its enum name; anything else ends a year range's stories.
STORY_NAMES = set(Titles.__members__)


def _walk_stories(d: Driver) -> set[str]:
    """Walk down from a just-opened year range through its stories.

    Returns:
        The stories with notes that were visited, each waited on until its label has
        reported its lines.

    """
    seen: set[str] = set()
    while True:
        before = d.match_count(LAID_OUT)
        try:
            d.key_then_wait(d.NODE_SELECTED, "Down")
        except DriverError:  # a Down on the tree's last node logs nothing
            return seen
        name = d.current_node()
        if name not in STORY_NAMES:
            return seen
        if name in NOTE_TITLES:
            d.await_new(LAID_OUT, timeout=15, before=before)
            seen.add(name)


def _enter_fullscreen(d: Driver) -> None:
    with d.expect(pattern(markers.ENTERED_FULLSCREEN, screen="MainScreen"), FULLSCREEN_TIMEOUT):
        d.main_menu_button("fullscreen")
    d.settle()
    if d.in_menu_mode():
        d.key_then_wait(d.MENU_EXITED, "Escape")


@pytest.mark.notes_fit
def test_every_note_shows_all_its_lines(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    if FULLSCREEN:
        _enter_fullscreen(d)

    seen: set[str] = set()
    tree.open_path(d, "Chronological")
    for year_range in CHRONO_YEAR_RANGES:
        d.open_branch(FilteredTitleLists.get_range_str(year_range))
        seen |= _walk_stories(d)

    in_the_tree = {
        info.comic_book_info.title.name
        for info in ALL_FANTA_COMIC_BOOK_INFO.values()
        if info.comic_book_info.title.name in NOTE_TITLES
    }
    assert seen == in_the_tree, f"Notes never reached: {sorted(in_the_tree - seen)}"
    log_lines = d.log_path.read_text("utf-8").splitlines()
    laid_out = [match for line in log_lines if (match := LINES_AND_SHOWN.search(line))]
    assert len(laid_out) >= len(seen), "Fewer layouts logged than notes visited."
    too_long = [match[0] for match in laid_out if int(match[1]) > int(match[2])]
    cut = [line for line in log_lines if CUT.search(line)]
    assert not too_long, "Notes cut short:\n" + "\n".join(cut or too_long)
