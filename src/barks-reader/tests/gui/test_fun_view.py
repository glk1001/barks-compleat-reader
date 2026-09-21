"""The fun image view under a group node: browse images, its options, its goto arrow.

The view only steps through images it has already shown, so a test first presses
Change Pics on the action bar to give it a second one. Its keyboard focus starts
on the filter (options) button; Down reaches the goto arrow only while the image
on show comes from a story.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from barks_gui import nodes
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

# A non-empty title: an image that comes from a story, not a stock one.
A_TITLED_IMAGE = pattern(markers.FUN_VIEW_TITLE_SET, title=re.compile(r'[^"]+'))
ANY_TITLE = pattern(markers.FUN_VIEW_TITLE_SET)
CHANGE_PICS_TRIES = 6


def _change_pics(d: Driver) -> None:
    with d.expect(pattern(markers.FUN_IMAGE_LOADED)):
        d.main_menu_button("change_pics")


def _change_pics_until_a_story_image(d: Driver) -> None:
    """Change Pics until the fun image on show comes from a story (seeded, so finite)."""
    for _ in range(CHANGE_PICS_TRIES):
        before = d.match_count(A_TITLED_IMAGE)
        _change_pics(d)
        d.settle()
        if d.match_count(A_TITLED_IMAGE) > before:
            return
    msg = f"no story image after {CHANGE_PICS_TRIES} Change Pics"
    raise AssertionError(msg)


def test_left_and_right_step_through_shown_images(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    _change_pics(d)  # a second image in the view's history
    d.key_then_wait(markers.ENTERED_BOTTOM_FOCUS, 15, "Right")
    d.key_then_wait(ANY_TITLE, 15, "Left")  # back to the first image
    d.key_then_wait(ANY_TITLE, 15, "Right")  # forward again
    d.key_then_wait(markers.EXITED_BOTTOM_FOCUS, 15, "Escape")


def test_options_menu_opens_and_escape_closes_it(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    d.key_then_wait(markers.ENTERED_BOTTOM_FOCUS, 15, "Right")
    # Opening the menu moves the focus ring into it; only then can it take a key.
    with (
        d.expect(pattern(markers.FUN_OPTIONS_PRESSED, state=True)),
        d.expect(d.FOCUS_MOVED),
    ):
        d.key("Return")
    d.key_then_wait(pattern(markers.FUN_OPTIONS_PRESSED, state=False), 15, "Escape")


def test_goto_arrow_jumps_to_the_pictured_story(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    _change_pics_until_a_story_image(d)
    d.key_then_wait(markers.ENTERED_BOTTOM_FOCUS, 15, "Right")
    d.move_focus("Down")  # the goto arrow, active for a story image
    with (
        d.expect(pattern(markers.GOTO_TITLE)),
        d.expect(markers.ENTERED_BOTTOM_FOCUS_AT_PORTAL),
    ):
        d.key("Return")
