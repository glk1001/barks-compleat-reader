"""The tree and the main screen's action bar, driven from the keyboard."""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import nodes
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

DOWNS_INTO_THE_RANGE = 3
# From go_back, three Lefts pass the fullscreen and icon buttons and wrap to
# quit; three Rights wrap back. If either wrap failed, Return would land on
# collapse (harmless) or quit (which only asks, since the profile pins
# confirm_quit) - and the go-back line would never be logged.
WRAP_STEPS = 3
ANY_NODE_SELECTED = pattern(markers.NEW_SELECTED_NODE)


def test_collapse_and_expand_a_top_level_node(boot: AppBoot) -> None:
    """Left shuts an open node; Return opens it again."""
    d = boot(nodes.THE_STORIES)
    d.key_then_wait(pattern(markers.NODE_COLLAPSED, name="The Stories"), 15, "Left")
    d.key_then_wait(pattern(markers.NODE_EXPANDED, name="The Stories"), 15, "Return")


def test_left_on_a_title_selects_its_parent(boot: AppBoot) -> None:
    """Down walks into a range's titles; Left on a title climbs back to the range."""
    d = boot(nodes.CHRONO_RANGE)
    for _ in range(DOWNS_INTO_THE_RANGE):
        d.key_then_wait(ANY_NODE_SELECTED, 15, "Down")
    assert d.current_node() != nodes.CHRONO_RANGE[0]
    d.key_then_wait(pattern(markers.NEW_SELECTED_NODE, name=nodes.CHRONO_RANGE[0]), 15, "Left")


def test_series_covers_expands_into_year_ranges(boot: AppBoot) -> None:
    """The Covers series lists year ranges, not titles."""
    d = boot(nodes.SERIES)
    d.select_node("Covers")
    d.key_then_wait(pattern(markers.NODE_EXPANDED, name="Covers"), 15, "Return")
    d.key_then_wait(pattern(markers.NEW_SELECTED_NODE, name=nodes.YEAR_RANGE_NODE), 15, "Down")


def test_menu_mode_wraps_both_ways(boot: AppBoot) -> None:
    """The action-bar menu opens on Go Back and wraps at both ends."""
    d = boot(nodes.GHOST_OF_THE_GROTTO)
    d.key_then_wait(d.MENU_ENTERED, 15, "Escape")
    d.move_focus(*["Left"] * WRAP_STEPS, *["Right"] * WRAP_STEPS)
    d.key_then_wait(markers.GO_BACK_SELECTED, 15, "Return")


def test_go_back_returns_to_the_previous_node(boot: AppBoot) -> None:
    """Escape then Return is Go Back, which selects the node before this one again."""
    d = boot(nodes.GHOST_OF_THE_GROTTO)
    d.key_then_wait(ANY_NODE_SELECTED, 15, "Down")
    assert d.current_node() != nodes.GHOST_OF_THE_GROTTO[0]
    with d.expect(pattern(markers.GOING_BACK_TO_NODE, name=nodes.GHOST_OF_THE_GROTTO[0])):
        d.go_back()
    d.wait_for(pattern(markers.NEW_SELECTED_NODE, name=nodes.GHOST_OF_THE_GROTTO[0]))


def test_collapse_button_shuts_the_whole_tree(boot: AppBoot) -> None:
    """The Collapse button on the action bar closes every open node."""
    d = boot(nodes.GHOST_OF_THE_GROTTO)
    collapsed = "|".join(
        pattern(marker, name="The Stories")
        for marker in (markers.NODE_COLLAPSED, markers.NODE_COLLAPSED_NO_STATE_CHANGE)
    )
    with d.expect(collapsed):
        d.main_menu_button("collapse")


CHANGE_PICS_TRIES = 6
# Up on the first node logs one line or the other, depending on the top image.
ARROW_FOCUSED = markers.ENTERED_TOP_GOTO_ARROW
UP_OUTCOME = f"{pattern(ARROW_FOCUSED)}|{pattern(markers.TOP_GOTO_ARROW_INACTIVE)}"


def test_up_on_the_first_node_reaches_the_top_goto_arrow(boot: AppBoot) -> None:
    """Up from the first tree node enters the top view's goto arrow, once it has a story.

    The arrow is live only while the top image comes from a story; Change Pics
    draws new images (seeded, so the draw is finite) until it does.
    """
    d = boot(nodes.INTRODUCTION)
    for _ in range(CHANGE_PICS_TRIES):
        before = d.match_count(ARROW_FOCUSED)
        d.key_then_wait(UP_OUTCOME, 15, "Up")
        if d.match_count(ARROW_FOCUSED) > before:
            break
        d.main_menu_button("change_pics")
        d.settle()
    else:
        msg = f"the top image never came from a story after {CHANGE_PICS_TRIES} Change Pics"
        raise AssertionError(msg)
    with (
        d.expect(pattern(markers.GOTO_TITLE)),
        d.expect(markers.ENTERED_BOTTOM_FOCUS_AT_PORTAL),
    ):
        d.key("Return")
