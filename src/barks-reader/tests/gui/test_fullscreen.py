"""Fullscreen round trips, in the reader and on the main screen.

With no window manager on the nested display, fullscreen resizes the app window;
the runner pins the nested screen size so the round trip has a known size to come
back to.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest
from barks_gui import harness, nodes
from barks_gui.logs import last_field, last_size
from barks_gui.steps import (
    FULLSCREEN_TIMEOUT,
    MAIN_FROM_DOCUMENT,
    SHOWED_PAGE,
    open_document,
)
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

READER = "ComicBookReaderScreen"
DOCUMENT_READER = "DocumentReaderScreen"
MAIN = "MainScreen"
# Pages turned before going two-up, to land on a spread rather than the title page
# and the full-page splash that open the story, which show alone even two-up.
PAGES_TO_A_SPREAD = 6
# Fullscreen on and off this often on the one spread, as a soak walk did when the
# spread was seen to stand half off the screen until the reader went windowed.
SPREAD_ROUND_TRIPS = 6


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


def test_document_reader_fullscreen_round_trip(boot: AppBoot) -> None:
    """The document reader's bar has the comic reader's Fullscreen; the bar hides in it."""
    d = boot(nodes.APPENDIX)
    open_document(d, nodes.CENSORSHIP_DOCUMENT)
    before = d.window_geometry()
    with d.expect(pattern(markers.ENTERED_FULLSCREEN, screen=DOCUMENT_READER), FULLSCREEN_TIMEOUT):
        d.press_document_menu_button("fullscreen")
    # The bar is hidden now; Escape brings it back for the menu, as in the comic reader.
    with d.expect(pattern(markers.ENTERED_WINDOWED, screen=DOCUMENT_READER), FULLSCREEN_TIMEOUT):
        d.press_document_menu_button("fullscreen")
    d.settle()
    assert d.window_geometry()[:2] == before[:2], "the window must come back at its old size"
    with d.expect(markers.DOCUMENT_CLOSING), d.expect(MAIN_FROM_DOCUMENT):
        d.press_document_menu_button("close")


def test_a_document_closed_from_fullscreen_comes_back_windowed(boot: AppBoot) -> None:
    """A document opened windowed and closed in fullscreen leaves the window as it found it."""
    d = boot(nodes.APPENDIX)
    open_document(d, nodes.CENSORSHIP_DOCUMENT)
    before = d.window_geometry()
    with d.expect(pattern(markers.ENTERED_FULLSCREEN, screen=DOCUMENT_READER), FULLSCREEN_TIMEOUT):
        d.press_document_menu_button("fullscreen")
    with (
        d.expect(markers.DOCUMENT_CLOSING),
        d.expect(pattern(markers.ENTERED_WINDOWED, screen=DOCUMENT_READER), FULLSCREEN_TIMEOUT),
        d.expect(MAIN_FROM_DOCUMENT, FULLSCREEN_TIMEOUT),
    ):
        d.press_document_menu_button("close")
    d.settle()
    assert d.window_geometry()[:2] == before[:2]


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
    if not harness.booted_two_up(boot.scratch):
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


def test_closing_from_a_window_falls_out_at_the_full_screen_size(boot: AppBoot) -> None:
    """Opened full screen, gone windowed on a spread, closed: the reader fills the screen.

    Closing goes back to the window mode the reader was opened in, full screen here,
    and its fall-out animation draws the reader as it stands when it starts. Started
    before the reader had been laid out for the full screen, it fell out with the
    spread at the window's size, pinned to the screen's left edge (a soak on the Mac
    guest, 2026-10-03, seen there; no check judged it, as the reader was closing).
    """
    d = boot(nodes.GHOST_OF_THE_GROTTO, cues=nodes.NO_CUES)
    with d.expect(pattern(markers.ENTERED_FULLSCREEN, screen=MAIN), FULLSCREEN_TIMEOUT):
        d.main_menu_button("fullscreen")
    d.settle()
    d.open_selected_story()
    for _ in range(PAGES_TO_A_SPREAD):
        d.key_then_wait(SHOWED_PAGE, "Right")
    if not harness.booted_two_up(boot.scratch):
        with d.expect(pattern(markers.DOUBLE_PAGE_TOGGLED, mode=True)), d.expect(SHOWED_PAGE):
            d.press_menu_button("double_page")
    with d.expect(pattern(markers.ENTERED_WINDOWED, screen=READER), FULLSCREEN_TIMEOUT):
        d.press_menu_button("fullscreen")
    d.settle()

    d.close_reader()

    size = [int(last_field(d, markers.READER_CLOSING, f)) for f in ("width", "height")]
    window = [int(last_field(d, markers.READER_CLOSING, f)) for f in ("win_width", "win_height")]
    assert all(abs(a - b) <= 2 for a, b in zip(size, window, strict=True)), (  # noqa: PLR2004
        f"the reader fell out at {size[0]}x{size[1]} in a {window[0]}x{window[1]} window"
    )
    # Windowed again, as booted: the teardown holds the window to its boot size. The
    # closed reader leaves the keyboard on the title view, below the tree.
    d.key_then_wait(markers.EXITED_BOTTOM_FOCUS, "Escape")
    with d.expect(pattern(markers.ENTERED_WINDOWED, screen=MAIN), FULLSCREEN_TIMEOUT):
        d.main_menu_button("fullscreen")
    d.settle()


# How much shorter the test makes the window, in pixels: no more than half the way to
# its minimum height, and with less room than the least, the test has nothing to show.
RESIZE_SHORTER = 120
LEAST_RESIZE_SHORTER = 20
RESIZE_TOO_WIDE = (260, 90, 180)  # one after another, as a drag sends them
# A corrected size may be a pixel or two off where a display scales the window's units.
RESIZE_TOLERANCE = 2


@pytest.mark.skipif(sys.platform == "darwin", reason="the macOS probe cannot resize a window yet")
def test_a_window_resized_out_of_shape_takes_its_layout_s_shape_again(boot: AppBoot) -> None:
    """Resized from outside, as by a corner, the window keeps the height and fits the width.

    Shorter and too wide, it must come back narrower, at the height it was given; and
    given its first height again, at its first width. A correction that grew the
    window (Windows' frame, 2026-11-17) or doubled it (a Retina Mac's points,
    2026-10-14) fails one or the other.
    """
    d = boot(nodes.GHOST_OF_THE_GROTTO)
    width, height = d.window_geometry()[:2]
    room = (height - last_size(d, markers.WINDOW_MINIMUM_SET)[1]) // 2
    if room < LEAST_RESIZE_SHORTER:
        pytest.skip(f"a window {height} high is at its minimum height on this screen")
    shorter = height - min(RESIZE_SHORTER, room)

    with d.expect(pattern(markers.WINDOW_ASPECT_CORRECTED)):
        for extra in RESIZE_TOO_WIDE:
            d.resize_window(width + extra, shorter)
    d.settle()
    fitted_width, fitted_height = d.window_geometry()[:2]
    assert abs(fitted_height - shorter) <= RESIZE_TOLERANCE, (
        f"resized to a height of {shorter}, the window settled {fitted_width}x{fitted_height}"
    )
    assert fitted_width < width, (
        f"a {width}x{height} window made {height - shorter} shorter"
        f" settled {fitted_width} wide, no narrower"
    )

    with d.expect(pattern(markers.WINDOW_ASPECT_CORRECTED)):
        d.resize_window(fitted_width + RESIZE_TOO_WIDE[0], height)
    d.settle()
    back = d.window_geometry()[:2]
    assert all(
        abs(now - was) <= RESIZE_TOLERANCE for now, was in zip(back, (width, height), strict=True)
    ), (
        f"given its height of {height} again, the {width}x{height} window"
        f" settled {back[0]}x{back[1]}"
    )
