"""The fun image view under a group node: browse images, its options, its goto buttons.

The view only steps through images it has already shown, so a test first presses
Change Pics on the action bar to give it a second one. Its keyboard focus starts
on the filter (options) button; Down reaches the goto button only while the image
on show comes from a story, and on the two-page spread, with two tiers stacked, a
second Down reaches the lower tier's own.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from barks_gui import expected, nodes
from barks_gui.logs import fields_of, image_exists, last_field
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

# A non-empty title: an image that comes from a story, not a stock one.
A_TITLED_IMAGE = pattern(markers.FUN_VIEW_TITLE_SET, title=re.compile(r'[^"]+'))
ANY_TITLE = pattern(markers.FUN_VIEW_TITLE_SET)
CHANGE_PICS_TRIES = 6


IMAGE_SUFFIXES = {".png", ".jpg"}


def _change_pics(d: Driver) -> None:
    with d.expect(pattern(markers.FUN_IMAGE_LOADED)):
        d.main_menu_button("change_pics")
    assert Path(last_field(d, markers.FUN_IMAGE_LOADED, "filename")).suffix in IMAGE_SUFFIXES


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
    d.key_then_wait(markers.ENTERED_BOTTOM_FOCUS, "Right")
    d.key_then_wait(ANY_TITLE, "Left")  # back to the first image
    d.key_then_wait(ANY_TITLE, "Right")  # forward again
    d.key_then_wait(markers.EXITED_BOTTOM_FOCUS, "Escape")
    # Left showed the image before Change Pics again, Right the changed one again.
    titles = fields_of(d, markers.FUN_VIEW_TITLE_SET, "title")
    first, changed, back, forward = titles[-4:]
    assert back == first
    assert forward == changed


def test_options_menu_opens_and_escape_closes_it(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    d.key_then_wait(markers.ENTERED_BOTTOM_FOCUS, "Right")
    # Up reaches the filter button from either button: Right lands on the goto button
    # when the seeded image is from a story, and that changes as the corpus grows.
    d.move_focus("Up")
    # Opening the menu moves the focus ring into it; only then can it take a key.
    with (
        d.expect(pattern(markers.FUN_OPTIONS_PRESSED, state=True)),
        d.expect(d.FOCUS_MOVED),
    ):
        d.key("Return")
    d.key_then_wait(pattern(markers.FUN_OPTIONS_PRESSED, state=False), "Escape")


def test_goto_button_jumps_to_the_pictured_story(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    _change_pics_until_a_story_image(d)
    d.key_then_wait(markers.ENTERED_BOTTOM_FOCUS, "Right")
    d.move_focus("Down")  # the goto button, active for a story image
    with (
        d.expect(pattern(markers.GOTO_TITLE)),
        d.expect(markers.ENTERED_BOTTOM_FOCUS_AT_PORTAL),
    ):
        d.key("Return")
    # The goto went to the pictured story: its file is the image on show, a
    # real image (a file, or a member of the JPG panels zip), and the tree now
    # selects that title.
    goto_file = Path(last_field(d, markers.GOTO_TITLE, "filename"))
    assert goto_file.name == last_field(d, markers.FUN_IMAGE_LOADED, "filename")
    assert image_exists(goto_file), goto_file
    assert d.current_node() == last_field(d, markers.GOTO_TITLE, "name")
    assert expected.is_title(d.current_node())

    # Go Back comes back to the fun view on the image left, not a fresh one: no new
    # image loads, and the goto's image is still the one on show.
    d.key_then_wait(markers.EXITED_BOTTOM_FOCUS, "Escape")
    images_loaded = d.match_count(pattern(markers.FUN_IMAGE_LOADED))
    with (
        d.expect(pattern(markers.GOING_BACK_TO_NODE, name=nodes.THE_STORIES[0])),
        d.expect(pattern(markers.NODE_IMAGES_KEPT, name=nodes.THE_STORIES[0])),
    ):
        d.go_back()
    d.settle()
    assert d.match_count(pattern(markers.FUN_IMAGE_LOADED)) == images_loaded
    assert goto_file.name == last_field(d, markers.FUN_IMAGE_LOADED, "filename")


def _two_story_tiers(d: Driver) -> bool:
    """Whether the tiers are stacked and each shows an image from a story."""
    if not d.match_count(STACKED):
        return False
    if last_field(d, markers.FUN_VIEW_STACKED, "state") != "True":
        return False
    return (
        last_field(d, markers.FUN_VIEW_TITLE_SET, "title") != ""
        and last_field(d, markers.FUN_VIEW_LOWER_TIER, "title") != ""
    )


STACKED = pattern(markers.FUN_VIEW_STACKED)


def test_on_the_spread_the_lower_tiers_button_goes_to_its_story(boot: AppBoot) -> None:
    """Stacked, Down from the goto button reaches the lower tier's; Enter goes to its story."""
    d = boot(nodes.THE_STORIES, ini={"main_screen_layout": "Two-page spread"})
    for _ in range(CHANGE_PICS_TRIES * 2):
        d.settle()
        if _two_story_tiers(d):
            break
        _change_pics(d)
    else:
        pytest.fail("no stacked pair of story images after Change Pics")
    lower_file = last_field(d, markers.FUN_VIEW_LOWER_TIER, "filename")

    d.key_then_wait(markers.ENTERED_BOTTOM_FOCUS, "Right")
    d.move_focus("Up", "Down", "Down")  # the filter, the goto button, the lower tier's
    with (
        d.expect(pattern(markers.GOTO_TITLE)),
        d.expect(markers.ENTERED_BOTTOM_FOCUS_AT_PORTAL),
    ):
        d.key("Return")
    assert Path(last_field(d, markers.GOTO_TITLE, "filename")).name == lower_file
    assert d.current_node() == last_field(d, markers.GOTO_TITLE, "name")


def test_on_the_spread_a_step_back_to_the_oldest_image_is_given_one_more(boot: AppBoot) -> None:
    """A step back onto the image seeded at boot seeds another behind it.

    So the lower tier never runs dry, and a tap on it never collapses the tiers.
    """
    d = boot(nodes.THE_STORIES, ini={"main_screen_layout": "Two-page spread"})
    seeded = pattern(markers.FUN_VIEW_SEEDED)
    seeded_at_boot = d.match_count(seeded)
    d.key_then_wait(markers.ENTERED_BOTTOM_FOCUS, "Right")
    # Back to the oldest image: the boot's history holds the seed and a few after it.
    for _ in range(CHANGE_PICS_TRIES):
        d.key_then_wait(pattern(markers.FUN_VIEW_TITLE_SET), "Left")
        d.settle()
        if d.match_count(seeded) > seeded_at_boot:
            break
    else:
        pytest.fail("stepping back never reached the oldest image")
    assert d.match_count(seeded) == seeded_at_boot + 1
    seed_file = last_field(d, markers.FUN_VIEW_SEEDED, "filename")
    d.wait_for(pattern(markers.FUN_VIEW_LOWER_TIER, filename=seed_file))
