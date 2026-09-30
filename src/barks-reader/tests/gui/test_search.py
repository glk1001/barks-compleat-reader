"""The search screens: title search and word search, each as a whole round trip."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from barks_gui import expected, nodes, search
from barks_gui.logs import last_field, messages
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
    assert count == expected.title_search_count(TITLE_QUERY), "the count the search facade gives"
    assert count >= TITLE_RESULT_ROW, f"only {count} results for {TITLE_QUERY!r}"
    assert expected.is_title(TITLE_RESULT)
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
    # Return in the box picks the first matching chip
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


# Inside words only: no word starts with it (airline, airliner, airlines).
INSIDE_QUERY = "irline"  # cspell:disable-line


def test_word_search_matches_inside_a_word(boot: AppBoot) -> None:
    """From three letters the box also lists words with the text inside; Return picks the first."""
    d = boot(nodes.WORD_SEARCH)
    search.type_query(d, INSIDE_QUERY)
    words = expected.words_matching(INSIDE_QUERY)
    assert words, f"no word in the index has {INSIDE_QUERY!r} inside it"
    assert not any(w.lower().startswith(INSIDE_QUERY) for w in words), "inside, not at the start"
    count = int(last_field(d, markers.WORD_SEARCH_MATCHED, "count", text=INSIDE_QUERY))
    assert count == len(words), "the count the search facade gives"
    d.key_then_wait(pattern(markers.WORD_SELECTED_CHIP, word=words[0]), "Return")
    assert int(last_field(d, markers.SEARCH_WORD_RESULTS, "count")) >= 1


AND_QUERY = "gold and mine"


def test_a_typed_and_query_lists_stories_with_both_words(boot: AppBoot) -> None:
    """Return runs a typed query: AND is the same story, and a balloon opens its bubbles."""
    found = expected.word_query(AND_QUERY).title_dict
    assert found, f"no story has both words of {AND_QUERY!r}"
    d = boot(nodes.WORD_SEARCH)
    search.run_typed_query(d, AND_QUERY)  # the keyboard is on the first story
    assert int(last_field(d, markers.WORD_QUERY_RUN, "count", text=AND_QUERY)) == len(found)
    assert int(last_field(d, markers.SEARCH_WORD_RESULTS, "count")) == len(found)

    d.move_focus("Right")  # the story's title -> its balloon
    with (
        d.expect(pattern(markers.SHOW_BUBBLES_FOR_SEARCH, text=AND_QUERY)),
        d.expect(markers.BUBBLES_POPUP_OPENED),
    ):
        d.key("Return")
    assert last_field(d, markers.SHOW_BUBBLES_FOR_SEARCH, "title", text=AND_QUERY) in found
    d.key_then_wait(markers.BUBBLES_POPUP_DISMISSED, "Escape")


BAD_QUERY = "(gold"


def test_text_that_does_not_parse_is_searched_as_it_stands(boot: AppBoot) -> None:
    literal = expected.word_query(BAD_QUERY)
    assert literal.used_literal_fallback
    assert literal.title_dict, f"the literal search for {BAD_QUERY!r} finds nothing"
    d = boot(nodes.WORD_SEARCH)
    with d.expect(pattern(markers.WORD_QUERY_FALLBACK, text=BAD_QUERY)):
        search.run_typed_query(d, BAD_QUERY)
    count = int(last_field(d, markers.WORD_QUERY_RUN, "count", text=BAD_QUERY))
    assert count == len(literal.title_dict)


MISSPELT = "scroge"  # cspell:disable-line


def test_a_misspelling_offers_suggestions_and_return_runs_one(boot: AppBoot) -> None:
    """A word in no story brings close spellings; Return on one puts it in and runs again."""
    offered = [s.spelling for s in expected.word_query(MISSPELT).suggestions]
    assert offered, f"no spelling is offered for {MISSPELT!r}"
    fixed = offered[0]
    stories = len(expected.word_query(fixed).title_dict)
    assert stories, f"{fixed!r} is in no story"

    d = boot(nodes.WORD_SEARCH)
    with d.expect(pattern(markers.WORD_SUGGESTIONS, word=MISSPELT)):
        search.run_typed_query(d, MISSPELT)  # nothing found: the keyboard is on a suggestion
    assert int(last_field(d, markers.WORD_QUERY_RUN, "count", text=MISSPELT)) == 0

    with d.expect(d.FOCUS_MOVED):  # the first story the spelling finds
        d.key_then_wait(pattern(markers.WORD_QUERY_RUN, text=fixed), "Return")
    assert int(last_field(d, markers.WORD_QUERY_RUN, "count", text=fixed)) == stories


NO_MATCH_QUERY = "zzzz"
CLEAR_QUERY = "vac"


def test_a_query_with_no_matches_reports_zero_results(boot: AppBoot) -> None:
    d = boot(nodes.TITLE_SEARCH)
    with d.expect(pattern(markers.SEARCH_TITLE_RESULTS, count=0, text=NO_MATCH_QUERY)):
        search.type_query(d, NO_MATCH_QUERY)


def test_the_clear_button_empties_the_search(boot: AppBoot) -> None:
    """Return in the box focuses the first result; from there Left is the clear button.

    Return is the box's own validate; Down, or Right at the text's end, also
    leave it (test_the_box_clear_button_and_results_are_walked_by_keyboard).
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


# A query whose one chip is a tag group: selected as typed, its members listed under it.
GROUP_QUERY = "africa"
GROUP = "Africa"
GROUP_MEMBERS = ("Algeria", "Arabian Peninsula")
# A query whose third chip is a group; Return on it selects its first member.
MULTI_QUERY = "south"
MULTI_GROUP = "South America"
MULTI_GROUP_STEPS = 2
MULTI_FIRST_MEMBER = "Andes"


def _chip_focused(text: str) -> str:
    return pattern(markers.NAV_FOCUS, widget=f'_TagChipButton "{text}"')


# Only inside names: Africa, Central Africa, South Africa - none typed whole, so no chip
# is picked as it is typed.
INSIDE_TAG_QUERY = "frica"  # cspell:disable-line


def test_tag_chips_match_inside_a_name_and_show_counts(boot: AppBoot) -> None:
    """From three letters a tag is found inside its name; its chip's count is what it lists."""
    d = boot(nodes.TAG_SEARCH)
    search.type_query(d, INSIDE_TAG_QUERY)
    matches = expected.tags_matching(INSIDE_TAG_QUERY)
    assert matches, f"no tag has {INSIDE_TAG_QUERY!r} inside its name"
    assert not any(m.exact for m in matches)
    count = int(last_field(d, markers.SEARCH_TAG_RESULTS, "count", text=INSIDE_TAG_QUERY))
    assert count == len(matches)
    # "fr" alone finds only France and picks it; the whole text must pick nothing.
    log = messages(d.log_path.read_text(encoding="utf-8", errors="replace"))
    after_results = log[log.rindex(f"tags for '{INSIDE_TAG_QUERY}'") :]
    assert not re.search(pattern(markers.TAG_SELECTED_TAG), after_results), "none picked as typed"

    first = matches[0]
    d.key_then_wait(_chip_focused(first.label), "Return")  # the box's Return: the first chip
    with d.expect(pattern(markers.TAG_TITLES_LISTED, tag=first.label, count=first.title_count)):
        d.key_then_wait(pattern(markers.TAG_SELECTED_TAG, tag=first.label), "Return")


def test_a_tag_groups_members_are_walked_and_picked_by_keyboard(boot: AppBoot) -> None:
    """Down walks from the group into its members; Return picks one; Left comes back to it."""
    d = boot(nodes.TAG_SEARCH)
    with d.expect(pattern(markers.TAG_SELECTED_TAG, tag=GROUP)):  # the only chip: picked as typed
        search.type_query(d, GROUP_QUERY)
    d.key_then_wait(_chip_focused(GROUP), "Return")
    for member in GROUP_MEMBERS:
        d.key_then_wait(_chip_focused(member), "Down")
    picked = GROUP_MEMBERS[-1]
    with d.expect(pattern(markers.TAG_SELECTED_MEMBER, member=picked)):
        d.key_then_wait(d.FOCUS_MOVED, "Return")  # the member's titles, focused
    d.key_then_wait(_chip_focused(picked), "Left")  # back to the picked member, not the top
    for chip in (*reversed(GROUP_MEMBERS[:-1]), GROUP):
        d.key_then_wait(_chip_focused(chip), "Up")
    d.key_then_wait(search.SEARCH_BOX_FOCUSED, "Up")  # off the top chip: back in the box


def test_return_on_a_group_opens_its_members_and_again_closes_them(boot: AppBoot) -> None:
    d = boot(nodes.TAG_SEARCH)
    search.type_query(d, MULTI_QUERY)
    d.key_then_wait(d.FOCUS_MOVED, "Return")  # the first chip
    d.move_focus(*["Down"] * MULTI_GROUP_STEPS)
    with (
        d.expect(pattern(markers.TAG_SELECTED_TAG, tag=MULTI_GROUP)),
        d.expect(pattern(markers.TAG_SELECTED_MEMBER, member=MULTI_FIRST_MEMBER)),
    ):
        d.key_then_wait(_chip_focused(MULTI_FIRST_MEMBER), "Return")
    d.key_then_wait(_chip_focused(MULTI_GROUP), "Up")
    # Return on the open group folds it: its own titles, the focus left on it.
    d.key_then_wait(_chip_focused(MULTI_GROUP), "Return")
    d.key_then_wait(d.FOCUS_MOVED, "Right")  # the group's titles
    d.key_then_wait(d.FOCUS_MOVED, "Down")
    d.key_then_wait(d.FOCUS_MOVED, "Up")
    d.key_then_wait(_chip_focused(MULTI_GROUP), "Left")  # back to the selected chip


def test_the_box_clear_button_and_results_are_walked_by_keyboard(boot: AppBoot) -> None:
    """Down, or Right at the text's end, leaves the box; the results reach the clear button."""
    d = boot(nodes.TITLE_SEARCH)
    search.type_query(d, CLEAR_QUERY)
    d.key_then_wait(d.FOCUS_MOVED, "Down")  # the first result row
    d.key_then_wait(d.FOCUS_MOVED, "Left")  # no chips in title search: the clear button
    d.key_then_wait(d.FOCUS_MOVED, "Right")  # back to the results
    d.key_then_wait(d.FOCUS_MOVED, "Left")
    d.key_then_wait(search.SEARCH_BOX_FOCUSED, "Left")  # from the clear button, the box
    d.key_then_wait(d.FOCUS_MOVED, "Right")  # the cursor is at the end: the results
    d.key_then_wait(markers.SEARCH_EXITED_NAV, "Escape")
