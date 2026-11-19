"""The Reading node: stories left mid-way, random picks, the playlists and this month's."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from barks_gui import nodes
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern
from barks_reader.core.this_month import MonthDate, get_month_node_text, get_stories_in_month

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

RANDOM_PICKS = 5
CANNED_LEFT_MID_WAY = 3
PLAYLIST = "The Bravery Stories"
PLAYLIST_INTRO_NODE = "<playlist-intro>"
ANY_NODE_SELECTED = pattern(markers.NEW_SELECTED_NODE)


def _repopulated(name: str) -> str:
    return pattern(markers.REPOPULATED_NODE, name=name, count=RANDOM_PICKS)


def test_surprise_me_redraws_on_every_expand(boot: AppBoot) -> None:
    d = boot(nodes.READING)
    d.open_branch("Choose for me")
    with d.expect(_repopulated("Surprise me")):
        d.open_branch("Surprise me")
    d.key_then_wait(pattern(markers.NODE_COLLAPSED, name="Surprise me"), "Left")
    with d.expect(_repopulated("Surprise me")):
        d.key("Return")


def test_continue_reading_lists_the_stories_left_mid_way_newest_first(boot: AppBoot) -> None:
    """The canned history's three titles each stopped inside the story at their latest read."""
    d = boot(nodes.READING)
    with (
        d.expect(
            pattern(markers.REPOPULATED_NODE, name="Continue reading", count=CANNED_LEFT_MID_WAY)
        ),
        # Every row has the half dot: The Ghost of the Grotto too, finished in an earlier read.
        d.expect(
            pattern(
                markers.POPULATED_READ_MARKS,
                name="Continue reading",
                finished=0,
                part_read=CANNED_LEFT_MID_WAY,
                unread=0,
            )
        ),
    ):
        d.open_branch("Continue reading")
    d.key_then_wait(ANY_NODE_SELECTED, "Down")
    assert d.current_node() == nodes.GHOST_OF_THE_GROTTO[0], "the newest read comes first"


def test_not_yet_read_redraws_on_every_expand(boot: AppBoot) -> None:
    d = boot(nodes.READING)
    d.open_branch("Choose for me")
    with (
        d.expect(_repopulated("From not yet read")),
        # No row it offers has a dot: neither a finished story nor one left mid-way.
        d.expect(
            pattern(
                markers.POPULATED_READ_MARKS,
                name="From not yet read",
                finished=0,
                part_read=0,
                unread=RANDOM_PICKS,
            )
        ),
    ):
        d.open_branch("From not yet read")
    d.key_then_wait(pattern(markers.NODE_COLLAPSED, name="From not yet read"), "Left")
    with d.expect(_repopulated("From not yet read")):
        d.key("Return")


def test_a_playlist_lists_its_stories_after_an_intro(boot: AppBoot) -> None:
    d = boot(nodes.READING)
    d.open_branch("Playlists")
    with d.expect(pattern(markers.UPDATING_BACKGROUND_VIEW_STATE, state="ON_PLAYLIST_NODE")):
        d.open_branch(PLAYLIST)
    d.key_then_wait(ANY_NODE_SELECTED, "Down")
    assert d.current_node() != PLAYLIST_INTRO_NODE, "Down must skip the intro paragraph"


def test_this_month_lists_the_stories_submitted_in_it(boot: AppBoot) -> None:
    """The node is named for today's month, and its first group opens onto title rows."""
    month = datetime.now().astimezone().month
    submitted = get_stories_in_month(MonthDate.SUBMITTED, month)
    d = boot(nodes.READING)
    with d.expect(pattern(markers.UPDATING_BACKGROUND_VIEW_STATE, state="ON_THIS_MONTH_NODE")):
        d.open_branch(get_month_node_text(month))
    d.key_then_wait(ANY_NODE_SELECTED, "Down")  # the Submitted group
    d.key_then_wait(pattern(markers.NODE_EXPANDED), "Return")
    d.key_then_wait(ANY_NODE_SELECTED, "Down")  # its first story, or a line above it skipped
    assert d.current_node() in {info.title.name for info in submitted}


def test_this_month_lists_the_stories_on_sale_in_it(boot: AppBoot) -> None:
    """The second group opens onto the stories whose issue carries today's month."""
    month = datetime.now().astimezone().month
    on_sale = get_stories_in_month(MonthDate.ON_SALE, month)
    d = boot(nodes.READING)
    d.open_branch(get_month_node_text(month))
    d.key_then_wait(ANY_NODE_SELECTED, "Down")  # the Submitted group, closed
    d.key_then_wait(ANY_NODE_SELECTED, "Down")  # the On sale group
    d.key_then_wait(pattern(markers.NODE_EXPANDED), "Return")
    d.settle()
    d.key_then_wait(ANY_NODE_SELECTED, "Down")
    assert d.current_node() in {info.title.name for info in on_sale}


def test_a_character_pick_opens_a_story(boot: AppBoot) -> None:
    d = boot(nodes.READING)
    d.open_branch("Choose for me")
    d.select_node("With Scrooge")
    d.key_then_wait(_repopulated("With Scrooge"), "Return")
    d.key_then_wait(ANY_NODE_SELECTED, "Down")  # the first of the five
    d.open_selected_story()
    d.close_reader()
