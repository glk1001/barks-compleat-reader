"""The index screens: main, speech-bubble (with its prefix bar), and the entity indexes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import nodes
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

ITEMS_DOWN = 2
INDEX_LETTERS = 3
LETTERS = 26
EMPTY_LETTER = pattern(markers.INDEX_LETTER_EMPTY)
POPULATED_OR_EMPTY = f"{pattern(markers.INDEX_LETTER_POPULATED)}|{EMPTY_LETTER}"
ITEM_PRESSED = pattern(markers.INDEX_ITEM_PRESSED)


def _letter(letter: str) -> str:
    return pattern(markers.INDEX_LETTER_POPULATED, letter=letter)


def test_main_index_builds_and_opens_an_item(boot: AppBoot) -> None:
    """Booting onto Main Index builds it and shows 'A'; Right enters items, Enter presses one."""
    d = boot(nodes.MAIN_INDEX)
    d.wait_for(pattern(markers.INDEX_BUILD_COMPLETE))
    d.wait_for(_letter("A"))
    d.key("Return")  # index nodes hand focus straight into their screen
    d.settle()
    d.move_focus("Right")  # alphabet panel -> items
    d.move_focus(*["Down"] * ITEMS_DOWN)
    d.key_then_wait(ITEM_PRESSED, "Return")


def test_main_index_letters_repopulate(boot: AppBoot) -> None:
    d = boot(nodes.MAIN_INDEX)
    d.key("Return")
    d.settle()
    d.key_then_wait(_letter("B"), "Down")
    d.key_then_wait(_letter("C"), "Down")


def test_speech_index_letters_repopulate(boot: AppBoot) -> None:
    """Indexes > Speech Bubble Index opens, and each Down repopulates the grid."""
    d = boot(nodes.SPEECH_INDEX)
    d.key("Return")
    d.settle()
    for _ in range(INDEX_LETTERS):
        d.key_then_wait(POPULATED_OR_EMPTY, "Down")


def test_a_letter_with_no_items_says_so(boot: AppBoot) -> None:
    """Walking the alphabet finds a letter with nothing under it, and it is logged as such."""
    d = boot(nodes.MAIN_INDEX)
    d.key("Return")
    d.settle()
    for _ in range(LETTERS):
        d.key_then_wait(POPULATED_OR_EMPTY, "Down")
        if d.match_count(EMPTY_LETTER):
            return
    msg = "every letter of the main index has items"
    raise AssertionError(msg)


def test_speech_index_prefix_bar_and_bubbles(boot: AppBoot) -> None:
    """Right from the letters is the prefix bar; Enter picks a prefix, a term, then bubbles."""
    d = boot(nodes.SPEECH_INDEX)
    d.key("Return")
    d.settle()
    d.move_focus("Right")  # alphabet -> prefix bar
    # Return selects the prefix and, a frame later, lands focus in its items.
    with d.expect(pattern(markers.INDEX_PREFIX_PRESSED)), d.expect(d.FOCUS_MOVED):
        d.key("Return")
    # Return expands the term's titles and re-lands focus once they are in.
    with d.expect(pattern(markers.INDEX_TERM_HANDLED)), d.expect(d.FOCUS_MOVED):
        d.key("Return")
    d.move_focus("Down")  # first title under the term
    d.move_focus("Right")  # its speech button
    d.key_then_wait(pattern(markers.SHOW_BUBBLES_FOR_INDEX_TERMS), "Return")
    d.key("Escape")  # close the popup
    d.settle()


def test_names_and_locations_indexes_open_items(boot: AppBoot) -> None:
    """The entity indexes share the base index's letters and items."""
    d = boot(nodes.NAMES_INDEX)
    d.key("Return")
    d.settle()
    d.key_then_wait(POPULATED_OR_EMPTY, "Down")
    d.move_focus("Right")
    d.key_then_wait(ITEM_PRESSED, "Return")
    # Over to Locations through the tree. In the items panel Escape only goes back
    # to the letters; the second Escape leaves the index, and Down is the sibling.
    d.move_focus("Escape")
    d.key_then_wait(markers.EXITED_BOTTOM_FOCUS, "Escape")
    d.key_then_wait(pattern(markers.NEW_SELECTED_NODE, name="Locations"), "Down")
    d.key("Return")
    d.settle()
    d.key_then_wait(POPULATED_OR_EMPTY, "Down")
