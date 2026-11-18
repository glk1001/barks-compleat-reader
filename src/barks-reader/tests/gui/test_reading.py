"""The Reading node: the stories left mid-way, random picks that redraw, and the playlists."""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import nodes
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern

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
    with d.expect(
        pattern(markers.REPOPULATED_NODE, name="Continue reading", count=CANNED_LEFT_MID_WAY)
    ):
        d.open_branch("Continue reading")
    d.key_then_wait(ANY_NODE_SELECTED, "Down")
    assert d.current_node() == nodes.GHOST_OF_THE_GROTTO[0], "the newest read comes first"


def test_not_yet_read_redraws_on_every_expand(boot: AppBoot) -> None:
    d = boot(nodes.READING)
    d.open_branch("Choose for me")
    with d.expect(_repopulated("Not yet read")):
        d.open_branch("Not yet read")
    d.key_then_wait(pattern(markers.NODE_COLLAPSED, name="Not yet read"), "Left")
    with d.expect(_repopulated("Not yet read")):
        d.key("Return")


def test_a_playlist_lists_its_stories_after_an_intro(boot: AppBoot) -> None:
    d = boot(nodes.READING)
    d.open_branch("Playlists")
    with d.expect(pattern(markers.UPDATING_BACKGROUND_VIEW_STATE, state="ON_PLAYLIST_NODE")):
        d.open_branch(PLAYLIST)
    d.key_then_wait(ANY_NODE_SELECTED, "Down")
    assert d.current_node() != PLAYLIST_INTRO_NODE, "Down must skip the intro paragraph"


def test_a_character_pick_opens_a_story(boot: AppBoot) -> None:
    d = boot(nodes.READING)
    d.open_branch("Choose for me")
    d.select_node("With Scrooge")
    d.key_then_wait(_repopulated("With Scrooge"), "Return")
    d.key_then_wait(ANY_NODE_SELECTED, "Down")  # the first of the five
    d.open_selected_story()
    d.close_reader()
