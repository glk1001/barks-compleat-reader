"""Fullscreen round trips, in the reader and on the main screen.

With no window manager on the nested display, fullscreen resizes the app window;
the runner pins the nested screen size so the round trip has a known size to come
back to.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import nodes
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

FULLSCREEN_TIMEOUT = 20
READER = "ComicBookReaderScreen"
MAIN = "MainScreen"


def test_reader_fullscreen_round_trip(boot: AppBoot) -> None:
    d = boot(nodes.GHOST_OF_THE_GROTTO, cues=nodes.NO_CUES)
    d.open_selected_story()
    before = d.window_geometry()
    with d.expect(pattern(markers.ENTERED_FULLSCREEN, screen=READER), FULLSCREEN_TIMEOUT):
        d.press_menu_button("fullscreen")
    with d.expect(pattern(markers.ENTERED_WINDOWED, screen=READER), FULLSCREEN_TIMEOUT):
        d.press_menu_button("fullscreen")
    d.settle()
    assert d.window_geometry()[:2] == before[:2], "the window must come back at its old size"
    d.close_reader()


def test_main_screen_fullscreen_round_trip(boot: AppBoot) -> None:
    d = boot(nodes.GHOST_OF_THE_GROTTO)
    before = d.window_geometry()
    with d.expect(pattern(markers.ENTERED_FULLSCREEN, screen=MAIN), FULLSCREEN_TIMEOUT):
        d.main_menu_button("fullscreen")
    with d.expect(pattern(markers.ENTERED_WINDOWED, screen=MAIN), FULLSCREEN_TIMEOUT):
        d.main_menu_button("fullscreen")
    d.settle()
    assert d.window_geometry()[:2] == before[:2]
