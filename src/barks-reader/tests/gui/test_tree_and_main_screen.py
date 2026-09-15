"""The tree and the main screen's action bar, driven from the keyboard."""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import nodes
from gui_driver import MENU_OPEN_PAUSE, MENU_STEP_PAUSE

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

DOWNS_INTO_THE_RANGE = 3
# From go_back, three Lefts pass the fullscreen and icon buttons and wrap to
# quit; three Rights wrap back. If either wrap failed, Return would land on
# collapse (harmless) or quit (which only asks, since the profile pins
# confirm_quit) - and the go-back line would never be logged.
WRAP_STEPS = 3


def test_collapse_and_expand_a_top_level_node(boot: AppBoot) -> None:
    """Left shuts an open node; Return opens it again."""
    d = boot(nodes.THE_STORIES)
    d.key_then_wait("Node collapsed: 'The Stories'", 15, "Left")
    d.key_then_wait("Node expanded: 'The Stories'", 15, "Return")


def test_left_on_a_title_selects_its_parent(boot: AppBoot) -> None:
    """Down walks into a range's titles; Left on a title climbs back to the range."""
    d = boot(nodes.CHRONO_RANGE)
    for _ in range(DOWNS_INTO_THE_RANGE):
        d.key_then_wait("New selected node", 15, "Down")
    assert d.current_node() != nodes.CHRONO_RANGE[0]
    d.key_then_wait(f'New selected node: "{nodes.CHRONO_RANGE[0]}"', 15, "Left")


def test_series_covers_expands_into_year_ranges(boot: AppBoot) -> None:
    """The Covers series lists year ranges, not titles."""
    d = boot(nodes.SERIES)
    d.select_node("Covers")
    d.key_then_wait("Node expanded: 'Covers'", 15, "Return")
    d.key_then_wait(r'New selected node: "19\d\d-19\d\d"', 15, "Down")


def test_menu_mode_wraps_both_ways(boot: AppBoot) -> None:
    """The action-bar menu opens on Go Back and wraps at both ends."""
    d = boot(nodes.GHOST_OF_THE_GROTTO)
    d.key_then_wait("Entered menu mode.", 15, "Escape")
    d.hold(MENU_OPEN_PAUSE)
    for step in ("Left", "Right"):
        for _ in range(WRAP_STEPS):
            d.key(step)
            d.hold(MENU_STEP_PAUSE)
    d.key_then_wait("'Go back' menu item selected.", 15, "Return")


def test_go_back_returns_to_the_previous_node(boot: AppBoot) -> None:
    """Escape then Return is Go Back, which selects the node before this one again."""
    d = boot(nodes.GHOST_OF_THE_GROTTO)
    d.key_then_wait("New selected node", 15, "Down")
    assert d.current_node() != nodes.GHOST_OF_THE_GROTTO[0]
    with d.expect(f'Going back to previous node "{nodes.GHOST_OF_THE_GROTTO[0]}"'):
        d.go_back()
    d.wait_for(f'New selected node: "{nodes.GHOST_OF_THE_GROTTO[0]}"')


def test_collapse_button_shuts_the_whole_tree(boot: AppBoot) -> None:
    """The Collapse button on the action bar closes every open node."""
    d = boot(nodes.GHOST_OF_THE_GROTTO)
    with d.expect(r"Node collapsed( but not allowing state change)?: 'The Stories'"):
        d.main_menu_button("collapse")
