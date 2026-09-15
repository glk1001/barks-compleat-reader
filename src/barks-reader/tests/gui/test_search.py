"""The search screens: title search and word search, each as a whole round trip."""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import nodes, search
from gui_driver import Pick

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

TITLE_QUERY = "vacation"
TITLE_RESULT_ROW = 2
TITLE_RESULT = "VACATION_TIME"
TITLE_RESULT_NAME = "Vacation Time"

WORD_QUERY = "airline"
WORD_RESULT_ROW = 1
WORD_RESULT_NAME = "Adventure Down Under"

# The title view fades in over a random 0-4s and logs nothing when it finishes; a
# result picked with the mouse hands focus to the portal only once the panel is
# up, so the Enter that opens the comic has to wait it out. M2 adds the marker.
TITLE_FADE_SECS = 4.5

CUES: dict[str, nodes.Cue] = {TITLE_RESULT_NAME: None, WORD_RESULT_NAME: None}
READ = Pick(pages=2, dwell=0.0)


def test_title_search_finds_and_opens_a_story(boot: AppBoot) -> None:
    """Type a title, click a result, read it, close, and Go Back to the search."""
    d = boot(nodes.TITLE_SEARCH, cues=CUES)
    search.type_query(d, TITLE_QUERY)
    with d.expect(f'Search: selected "{TITLE_RESULT_NAME}"'):
        search.click_title_result(boot, d, TITLE_RESULT_ROW, TITLE_RESULT)
    d.hold(TITLE_FADE_SECS)

    d.key_then_wait("All images loaded", 30, "Return")
    d.read_pages(READ)
    d.close_reader()
    d.key("Escape")  # hand focus back from the bottom region to the tree
    d.settle()
    d.go_back_then_wait("SearchScreen mode set to 'Title'", 15)


def test_word_search_bubble_opens_the_story_at_its_page(boot: AppBoot) -> None:
    """Type a word, pick its chip, open one story's bubbles, jump in from a bubble."""
    d = boot(nodes.WORD_SEARCH, cues=CUES)
    search.type_query(d, WORD_QUERY)
    d.key("Down")  # the first matching word chip
    d.settle()
    d.key_then_wait(f'Word search: selected chip "{WORD_QUERY}"', 15, "Return")

    search.click_word_balloon(boot, d, WORD_RESULT_ROW, WORD_RESULT_NAME)
    search.click_first_bubble(boot, d, WORD_RESULT_NAME)
    d.settle()
    d.key_then_wait("All images loaded", 30, "Return")
    assert d.current_page() > 0, "a bubble opens the story at its own page, not the front"
    d.close_reader()
    d.key("Escape")
    d.settle()
    d.go_back_then_wait("SearchScreen mode set to 'Word'", 15)
