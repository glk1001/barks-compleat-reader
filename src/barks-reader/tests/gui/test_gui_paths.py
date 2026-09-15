"""GUI path tests: drive the real app through a few of its screens.

Ported from the demo recorder's beats with the camera dwells removed. Every wait
is on a line the app logs, so a test passes on evidence (the comic loaded, the
page turned, the main screen came back) or fails naming the line it never saw.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import reader, tree
from gui_driver import Pick

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

# The chronological range browse walks into, and the story it reads there.
BROWSE_RANGE = "1947-1950"
BROWSE_STORY = "GHOST_OF_THE_GROTTO_THE"

# A story reached through the series tree, and a page index to jump to inside it.
SERIES_STORY = "LOST_IN_THE_ANDES"
SERIES_GOTO_PAGE = 12

# How many letters of the speech-bubble index to step through.
INDEX_LETTERS = 3

# Stories the tests open by name, pinned to "no cue" so each opens at its front
# page with no goto-page row, whatever the canned profile says.
CUES: dict[str, dict[str, int | str] | None] = {
    "The Ghost of the Grotto": None,
    "Lost in the Andes!": None,
}

# Reading a story opens on its front page, so two pages means the front and one turn.
READ = Pick(pages=2, dwell=0.0)


def test_browse_tree_to_a_story_and_read_it(boot: AppBoot) -> None:
    """The Stories > Chronological > a range > a title, opened and read."""
    d = boot(["The Stories", "root"], cues=CUES)
    tree.collapse_all(d)
    tree.open_path(d, "The Stories", "Chronological", BROWSE_RANGE)
    d.select_node(BROWSE_STORY)
    assert d.current_node() == BROWSE_STORY

    d.open_story(Pick(BROWSE_STORY, pages=READ.pages, dwell=READ.dwell))
    assert d.current_page() >= 1, "a page must have turned before the reader closed"


def test_series_story_goto_page_and_double_page(boot: AppBoot) -> None:
    """Series > Donald Duck Adventures > a story: jump to a page, then two-up, then close."""
    d = boot(["Series", "The Stories", "root"], cues=CUES)
    d.select_node("Comics and Stories")
    d.select_node("Donald Duck Adventures")
    d.open_branch("Donald Duck Adventures")
    d.select_node(SERIES_STORY)

    reader.open_selected_story(d)
    d.read_pages(READ)

    d.goto_page(SERIES_GOTO_PAGE)
    assert d.current_page() == SERIES_GOTO_PAGE

    with d.expect("Showed page", 15):
        d.press_menu_button("double_page")
    d.close_reader()


def test_speech_index_steps_through_letters(boot: AppBoot) -> None:
    """Indexes > Speech Bubble Index opens, and each Down repopulates the grid."""
    d = boot(["Speech Bubble Index", "Indexes", "root"])
    d.key("Return")
    d.settle()
    for _ in range(INDEX_LETTERS):
        d.key_then_wait("Populated index page for letter", 15, "Down")
