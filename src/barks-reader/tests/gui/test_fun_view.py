"""The fun image view under a group node: browse images, its options, its goto arrow.

The view only steps through images it has already shown, so a test first presses
Change Pics on the action bar to give it a second one. Its keyboard focus starts
on the filter (options) button; Down reaches the goto arrow only while the image
on show comes from a story.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import nodes

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

A_TITLED_IMAGE = r'Set fun view title to "[^"]+"'
CHANGE_PICS_TRIES = 6


def _change_pics(d: Driver) -> None:
    with d.expect("Set last loaded fun image file"):
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
    d.key_then_wait("Entered bottom focus region.", 15, "Right")
    d.key_then_wait("Set fun view title to", 15, "Left")  # back to the first image
    d.key_then_wait("Set fun view title to", 15, "Right")  # forward again
    d.key_then_wait("Exited bottom focus region.", 15, "Escape")


def test_options_menu_opens_and_escape_closes_it(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    d.key_then_wait("Entered bottom focus region.", 15, "Right")
    # Opening the menu moves the focus ring into it; only then can it take a key.
    with (
        d.expect("Fun view options button pressed. New state is 'True'"),
        d.expect(d.FOCUS_MOVED),
    ):
        d.key("Return")
    d.key_then_wait("Fun view options button pressed. New state is 'False'", 15, "Escape")


def test_goto_arrow_jumps_to_the_pictured_story(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    _change_pics_until_a_story_image(d)
    d.key_then_wait("Entered bottom focus region.", 15, "Right")
    d.move_focus("Down")  # the goto arrow, active for a story image
    with d.expect("Goto title:"), d.expect("Entered bottom focus region at the title portal."):
        d.key("Return")
