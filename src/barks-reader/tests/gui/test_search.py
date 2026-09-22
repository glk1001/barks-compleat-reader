"""The search screens: title search and word search, each as a whole round trip."""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import nodes, search
from barks_gui.logs import last_field
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern
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

CUES: dict[str, nodes.Cue] = {TITLE_RESULT_NAME: None, WORD_RESULT_NAME: None}
READ = Pick(pages=2, dwell=0.0)
ALL_IMAGES_LOADED = pattern(markers.ALL_IMAGES_LOADED)


def test_title_search_finds_and_opens_a_story(boot: AppBoot) -> None:
    """Type a title, pick a result, read it, close, and Go Back to the search."""
    d = boot(nodes.TITLE_SEARCH, cues=CUES)
    search.type_query(d, TITLE_QUERY)
    # The full query's result count, as logged, must reach the row about to be picked.
    count = int(last_field(d, markers.SEARCH_TITLE_RESULTS, "count", text=TITLE_QUERY))
    assert count >= TITLE_RESULT_ROW, f"only {count} results for {TITLE_QUERY!r}"
    with d.expect(pattern(markers.SEARCH_SELECTED_TITLE, title=TITLE_RESULT_NAME)):
        search.pick_title_result(d, TITLE_RESULT_ROW, TITLE_RESULT)
    assert d.current_node() == TITLE_RESULT
    d.wait_title_fade()  # the Enter that opens the comic is lost mid-fade

    d.key_then_wait(ALL_IMAGES_LOADED, "Return", timeout=30)
    assert d.current_page() == 0, "no cue, so the story opens at its front page"
    d.read_pages(READ)
    assert d.current_page() >= 1
    d.close_reader()
    d.key_then_wait(markers.EXITED_BOTTOM_FOCUS, "Escape")  # focus back to the tree
    d.go_back_then_wait(pattern(markers.SEARCH_MODE_SET, mode="Title"))


def test_word_search_bubble_opens_the_story_at_its_page(boot: AppBoot) -> None:
    """Type a word, pick its chip, open one story's bubbles, jump in from a bubble."""
    d = boot(nodes.WORD_SEARCH, cues=CUES)
    search.type_query(d, WORD_QUERY)
    # Return in the box picks the first matching chip (the box yields no other key)
    # and lands focus on it; the next Return from there enters the result rows.
    d.key_then_wait(pattern(markers.WORD_SELECTED_CHIP, word=WORD_QUERY), "Return")
    matched = int(last_field(d, markers.WORD_SEARCH_MATCHED, "count", text=WORD_QUERY))
    rows = int(last_field(d, markers.SEARCH_WORD_RESULTS, "count"))
    assert matched >= 1, f"{WORD_QUERY!r} matched no words"
    assert rows >= WORD_RESULT_ROW, f"only {rows} result rows for {WORD_QUERY!r}"

    search.open_word_balloon(d, WORD_RESULT_ROW, WORD_RESULT_NAME)
    search.press_first_bubble(d, WORD_RESULT_NAME)
    d.wait_title_fade()  # the story's title view fades in; a Return mid-fade is lost
    d.key_then_wait(ALL_IMAGES_LOADED, "Return", timeout=30)
    assert d.current_page() > 0, "a bubble opens the story at its own page, not the front"
    d.close_reader()
    d.key_then_wait(markers.EXITED_BOTTOM_FOCUS, "Escape")
    d.go_back_then_wait(pattern(markers.SEARCH_MODE_SET, mode="Word"))


NO_MATCH_QUERY = "zzzz"
CLEAR_QUERY = "vac"


def test_a_query_with_no_matches_reports_zero_results(boot: AppBoot) -> None:
    d = boot(nodes.TITLE_SEARCH)
    with d.expect(pattern(markers.SEARCH_TITLE_RESULTS, count=0, text=NO_MATCH_QUERY)):
        search.type_query(d, NO_MATCH_QUERY)


def test_the_clear_button_empties_the_search(boot: AppBoot) -> None:
    """Return in the box focuses the first result; from there Left is the clear button.

    While the box holds the keyboard the main screen yields every key but Escape
    to it, so Return (the box's own validate) is the only way out by keyboard.
    """
    d = boot(nodes.TITLE_SEARCH)
    search.type_query(d, CLEAR_QUERY)
    d.key_then_wait(d.FOCUS_MOVED, "Return")  # the first result row
    d.move_focus("Left")  # the clear (x) button
    d.key_then_wait(pattern(markers.SEARCH_CLEARED, mode="title"), "Return")


TAG_QUERY = "scrooge"
TAG_OR_MEMBER_SELECTED = (
    f"{pattern(markers.TAG_SELECTED_TAG)}|{pattern(markers.TAG_SELECTED_MEMBER)}"
)


def test_tag_search_by_keyboard_picks_a_tag_then_a_member(boot: AppBoot) -> None:
    """Return in the box lands on the first chip; Return there selects it and shows its members."""
    d = boot(nodes.TAG_SEARCH)
    search.type_query(d, TAG_QUERY)
    d.key_then_wait(d.FOCUS_MOVED, "Return")  # the chips
    d.key_then_wait(TAG_OR_MEMBER_SELECTED, "Return")
    # Whatever Return selected, the tag on offer was one the query matched.
    assert TAG_QUERY in last_field(d, markers.TAG_SELECTED_TAG, "tag").lower()
