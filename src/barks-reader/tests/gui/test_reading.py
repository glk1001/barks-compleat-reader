"""The Reading node: stories left mid-way, random picks, the playlists and this month's."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pytest
from barks_gui import harness, nodes
from barks_gui.steps import ANY_NODE_SELECTED
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern
from barks_reader.core.this_month import MonthDate, get_month_node_text, get_stories_in_month

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

RANDOM_PICKS = 5
CANNED_LEFT_MID_WAY = 3
PLAYLIST = "The Bravery Stories"
PLAYLIST_INTRO_NODE = "<playlist-intro>"
ONLY_UNREAD_ROW = "Only stories not yet read"
# The tick row heads 'Choose for me': from any node under it, fewer Ups than this.
MAX_UPS_TO_THE_TICK = 12


def _repopulated(name: str) -> str:
    return pattern(markers.REPOPULATED_NODE, name=name, count=RANDOM_PICKS)


def _boot_in_one_month(boot: AppBoot) -> tuple[Driver, int]:
    """Boot onto Reading; return the driver and the month the app named its node for.

    The app reads today's month as it builds the tree. A boot that ran over midnight on
    a month's last day could have read either month: that one run in thousands is
    skipped, not failed on a node the test guessed wrong.
    """
    before = datetime.now().astimezone().month
    d = boot(nodes.READING)
    if datetime.now().astimezone().month != before:
        pytest.skip("the month changed while the app booted")
    return d, before


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


def _only_unread_picks(name: str) -> str:
    """Return the read-marks line of a node whose rows are made with no dot among them."""
    return pattern(
        markers.POPULATED_READ_MARKS,
        name=name,
        finished=0,
        part_read=0,
        unread=RANDOM_PICKS,
    )


def _only_unread_setting(boot: AppBoot) -> str:
    return harness.read_ini_value(boot.scratch / "barks-reader.ini", "choose_only_unread").strip()


def test_the_only_unread_tick_keeps_a_node_s_picks_to_stories_not_yet_read(
    boot: AppBoot,
) -> None:
    """Return on the tick row turns it on, and off again; a node opened between has no dots."""
    d = boot(nodes.READING)
    d.open_branch("Choose for me")
    d.select_node(ONLY_UNREAD_ROW)
    d.key_then_wait(pattern(markers.CHOOSE_ONLY_UNREAD_SET, value=True), "Return")
    assert _only_unread_setting(boot) == "1"

    # A decade's node, not only 'Surprise me': the tick is every node's.
    with d.expect(_repopulated("From the 1950s")), d.expect(_only_unread_picks("From the 1950s")):
        d.open_branch("From the 1950s")
    d.key_then_wait(pattern(markers.NODE_COLLAPSED, name="From the 1950s"), "Left")

    for _ in range(MAX_UPS_TO_THE_TICK):
        d.key_then_wait(ANY_NODE_SELECTED, "Up")
        if d.current_node() == ONLY_UNREAD_ROW:
            break
    else:
        pytest.fail(f"{MAX_UPS_TO_THE_TICK} Ups did not reach the tick row: {d.current_node()}")
    d.key_then_wait(pattern(markers.CHOOSE_ONLY_UNREAD_SET, value=False), "Return")
    assert _only_unread_setting(boot) == "0"


def test_the_only_unread_tick_is_kept_from_the_last_run(boot: AppBoot) -> None:
    """Booted with the tick on, the nodes keep to the unread before the row is touched."""
    d = boot(nodes.READING, ini={"choose_only_unread": "1"})
    d.open_branch("Choose for me")
    with d.expect(_repopulated("Surprise me")), d.expect(_only_unread_picks("Surprise me")):
        d.open_branch("Surprise me")


def test_a_playlist_lists_its_stories_after_an_intro(boot: AppBoot) -> None:
    d = boot(nodes.READING)
    d.open_branch("Playlists")
    with d.expect(pattern(markers.UPDATING_BACKGROUND_VIEW_STATE, state="ON_PLAYLIST_NODE")):
        d.open_branch(PLAYLIST)
    d.key_then_wait(ANY_NODE_SELECTED, "Down")
    assert d.current_node() != PLAYLIST_INTRO_NODE, "Down must skip the intro paragraph"


def test_this_month_lists_the_stories_submitted_in_it(boot: AppBoot) -> None:
    """The node is named for today's month, and its first group opens onto title rows."""
    d, month = _boot_in_one_month(boot)
    submitted = get_stories_in_month(MonthDate.SUBMITTED, month)
    with d.expect(pattern(markers.UPDATING_BACKGROUND_VIEW_STATE, state="ON_THIS_MONTH_NODE")):
        d.open_branch(get_month_node_text(month))
    d.key_then_wait(ANY_NODE_SELECTED, "Down")  # the Submitted group
    d.key_then_wait(pattern(markers.NODE_EXPANDED), "Return")
    d.key_then_wait(ANY_NODE_SELECTED, "Down")  # its first story, or a line above it skipped
    assert d.current_node() in {info.title.name for info in submitted}


def test_this_month_lists_the_stories_on_sale_in_it(boot: AppBoot) -> None:
    """The second group opens onto the stories whose issue carries today's month."""
    d, month = _boot_in_one_month(boot)
    on_sale = get_stories_in_month(MonthDate.ON_SALE, month)
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
