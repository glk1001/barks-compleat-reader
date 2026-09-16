"""Fullscreen round trips, in the reader and on the main screen.

Its own module: with no window manager on the nested display, fullscreen resizes
the app window, and no pixel-click test may run in the same boot afterwards.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import nodes

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

FULLSCREEN_TIMEOUT = 20


def test_reader_fullscreen_round_trip(boot: AppBoot) -> None:
    d = boot(nodes.GHOST_OF_THE_GROTTO, cues=nodes.NO_CUES)
    d.open_selected_story()
    before = d.window_geometry()
    with d.expect("Entered fullscreen mode on ComicBookReaderScreen.", FULLSCREEN_TIMEOUT):
        d.press_menu_button("fullscreen")
    with d.expect("Entered windowed mode on ComicBookReaderScreen.", FULLSCREEN_TIMEOUT):
        d.press_menu_button("fullscreen")
    d.settle()
    assert d.window_geometry()[:2] == before[:2], "the window must come back at its old size"
    d.close_reader()


def test_main_screen_fullscreen_round_trip(boot: AppBoot) -> None:
    d = boot(nodes.GHOST_OF_THE_GROTTO)
    before = d.window_geometry()
    with d.expect("Entered fullscreen mode on MainScreen.", FULLSCREEN_TIMEOUT):
        d.main_menu_button("fullscreen")
    with d.expect("Entered windowed mode on MainScreen.", FULLSCREEN_TIMEOUT):
        d.main_menu_button("fullscreen")
    d.settle()
    assert d.window_geometry()[:2] == before[:2]
