"""Fullscreen round trips, in the reader and on the main screen.

With no window manager on the nested display, fullscreen resizes the app window;
the runner pins the nested screen size so the round trip has a known size to come
back to.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import harness, nodes
from barks_gui.logs import last_field
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

FULLSCREEN_TIMEOUT = 20
READER = "ComicBookReaderScreen"
MAIN = "MainScreen"
SHOWED_PAGE = pattern(markers.SHOWED_PAGE)
# Pages turned before going two-up, to land on a spread rather than the title page
# and the full-page splash that open the story, which show alone even two-up.
PAGES_TO_A_SPREAD = 6
# Fullscreen on and off this often on the one spread, as a soak walk did when the
# spread was seen to stand half off the screen until the reader went windowed.
SPREAD_ROUND_TRIPS = 6


def _booted_two_up(boot: AppBoot) -> bool:
    """Whether the run booted the reader in double-page mode (the matrix does)."""
    return harness.read_ini_value(boot.scratch / "barks-reader.ini", "double_page_mode") == "1"


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


def test_a_spread_stays_centred_through_fullscreen_switches(boot: AppBoot) -> None:
    """Two-up on a spread, fullscreen on and off again and again on that page.

    The teardown's centring check (``assert_page_centred``) judges every placement
    the reader logs: a spread once stood half off the screen after such switches,
    until the reader went windowed, and nothing else the suite checked showed it.
    """
    d = boot(nodes.GHOST_OF_THE_GROTTO, cues=nodes.NO_CUES)
    d.open_selected_story()
    for _ in range(PAGES_TO_A_SPREAD):
        d.key_then_wait(SHOWED_PAGE, "Right")
    # Two-up, unless the run booted two-up already (the matrix does): there the
    # toggle would turn it off.
    if not _booted_two_up(boot):
        with d.expect(pattern(markers.DOUBLE_PAGE_TOGGLED, mode=True)), d.expect(SHOWED_PAGE):
            d.press_menu_button("double_page")
    d.settle()
    width = int(last_field(d, markers.PAGE_PLACED, "width"))
    height = int(last_field(d, markers.PAGE_PLACED, "height"))
    assert width > height, f"a {width}x{height} page: two-up should show a spread here"
    for _ in range(SPREAD_ROUND_TRIPS):
        with d.expect(pattern(markers.ENTERED_FULLSCREEN, screen=READER), FULLSCREEN_TIMEOUT):
            d.press_menu_button("fullscreen")
        d.settle()
        with d.expect(pattern(markers.ENTERED_WINDOWED, screen=READER), FULLSCREEN_TIMEOUT):
            d.press_menu_button("fullscreen")
        d.settle()
    d.close_reader()
