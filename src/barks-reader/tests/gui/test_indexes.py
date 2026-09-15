"""The index screens: main, speech-bubble (with its prefix bar), and the entity indexes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import nodes

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

PANEL_PAUSE = 0.4  # between a panel move (Right into items, Up to the bar) and the next key
ITEMS_DOWN = 2
INDEX_LETTERS = 3
LETTERS = 26
POPULATED_OR_EMPTY = r"Populated index page for letter '.'(: no items| in )"
EMPTY_LETTER = r"Populated index page for letter '.': no items\."


def test_main_index_builds_and_opens_an_item(boot: AppBoot) -> None:
    """Booting onto Main Index builds it and shows 'A'; Right enters items, Enter presses one."""
    d = boot(nodes.MAIN_INDEX)
    d.wait_for("Index build complete")
    d.wait_for("Populated index page for letter 'A'")
    d.key("Return")  # index nodes hand focus straight into their screen
    d.settle()
    d.key("Right")  # alphabet panel -> items
    d.hold(PANEL_PAUSE)
    for _ in range(ITEMS_DOWN):
        d.key("Down")
        d.hold(PANEL_PAUSE)
    d.key_then_wait("Index item pressed:", 15, "Return")


def test_main_index_letters_repopulate(boot: AppBoot) -> None:
    d = boot(nodes.MAIN_INDEX)
    d.key("Return")
    d.settle()
    d.key_then_wait("Populated index page for letter 'B'", 15, "Down")
    d.key_then_wait("Populated index page for letter 'C'", 15, "Down")


def test_speech_index_letters_repopulate(boot: AppBoot) -> None:
    """Indexes > Speech Bubble Index opens, and each Down repopulates the grid."""
    d = boot(nodes.SPEECH_INDEX)
    d.key("Return")
    d.settle()
    for _ in range(INDEX_LETTERS):
        d.key_then_wait("Populated index page for letter", 15, "Down")


def test_a_letter_with_no_items_says_so(boot: AppBoot) -> None:
    """Walking the alphabet finds a letter with nothing under it, and it is logged as such."""
    d = boot(nodes.MAIN_INDEX)
    d.key("Return")
    d.settle()
    for _ in range(LETTERS):
        d.key_then_wait(POPULATED_OR_EMPTY, 15, "Down")
        if d.match_count(EMPTY_LETTER):
            return
    msg = "every letter of the main index has items"
    raise AssertionError(msg)


def test_speech_index_prefix_bar_and_bubbles(boot: AppBoot) -> None:
    """Right from the letters is the prefix bar; Enter picks a prefix, a term, then bubbles."""
    d = boot(nodes.SPEECH_INDEX)
    d.key("Return")
    d.settle()
    d.key("Right")  # alphabet -> prefix bar
    d.hold(PANEL_PAUSE)
    d.key_then_wait("Pressed prefix button:", 15, "Return")  # selects it, enters the items
    d.hold(PANEL_PAUSE)
    d.key_then_wait("Handling index term:", 15, "Return")  # expands the term's titles
    d.hold(PANEL_PAUSE)
    d.key("Down")  # first title under the term
    d.hold(PANEL_PAUSE)
    d.key("Right")  # its speech button
    d.hold(PANEL_PAUSE)
    d.key_then_wait('Show speech bubbles for: ".*" and index terms', 15, "Return")
    d.key("Escape")  # close the popup
    d.settle()


def test_names_and_locations_indexes_open_items(boot: AppBoot) -> None:
    """The entity indexes share the base index's letters and items."""
    d = boot(nodes.NAMES_INDEX)
    d.key("Return")
    d.settle()
    d.key_then_wait("Populated index page for letter", 15, "Down")
    d.key("Right")
    d.hold(PANEL_PAUSE)
    d.key_then_wait("Index item pressed:", 15, "Return")
    # Over to Locations through the tree. In the items panel Escape only goes back
    # to the letters; the second Escape leaves the index, and Down is the sibling.
    d.key("Escape")
    d.hold(PANEL_PAUSE)
    d.key_then_wait("Exited bottom focus region.", 15, "Escape")
    d.key_then_wait('New selected node: "Locations"', 15, "Down")
    d.key("Return")
    d.settle()
    d.key_then_wait("Populated index page for letter", 15, "Down")
