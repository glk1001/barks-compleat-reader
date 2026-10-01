"""The search screens: title search and word search, each as a whole round trip."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from barks_gui import expected, memory, nodes, search
from barks_gui.logs import last_field, messages
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern
from gui_driver import Pick

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

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


SPEAKER_WORD = "money"
SPEAKER = "Scrooge"  # not the first in the list, so the walk down it is tested


def _said_by_focused(speaker: str) -> str:
    return pattern(markers.NAV_FOCUS, widget=f'_SaidByChipButton "Said by: {speaker}"')


def _speaker_item_focused(speaker: str) -> str:
    return pattern(markers.NAV_FOCUS, widget=f'_SaidByItem "{speaker}"')


def test_the_speaker_list_filters_the_word_results_by_keyboard(boot: AppBoot) -> None:
    """Right past a word's + is the speaker chip; Enter lists who says it; Enter picks one."""
    word = expected.words_matching(SPEAKER_WORD)[0]
    everyone = expected.word_stories(word)
    by_speaker = expected.word_stories(word, speaker=SPEAKER)
    assert 0 < by_speaker < everyone, "the filter must narrow the stories, not empty them"
    speakers = expected.speaker_list(word)
    assert speakers.index(SPEAKER) > 0, "the speaker must be down the list, to walk to"

    d = boot(nodes.WORD_SEARCH)
    search.type_query(d, SPEAKER_WORD)
    with d.expect(d.FOCUS_MOVED):  # Return picks the first word and lands on it
        d.key_then_wait(pattern(markers.WORD_SELECTED_CHIP, word=word), "Return")
    assert int(last_field(d, markers.SEARCH_WORD_RESULTS, "count")) == everyone

    d.move_focus("Right", pattern=_focus_on("_PlusButton", "+"))  # the word's +, then the chip
    d.move_focus("Right", pattern=_said_by_focused("anyone"))
    with d.expect(pattern(markers.SPEAKER_LIST_OPENED, count=len(speakers))):
        d.key_then_wait(_speaker_item_focused("anyone"), "Return")  # on the one picked
    for speaker in speakers[: speakers.index(SPEAKER) + 1]:  # most stories first
        d.move_focus("Down", pattern=_speaker_item_focused(speaker))
    with d.expect(pattern(markers.SPEAKER_FILTER_SET, speaker=SPEAKER)):
        d.key_then_wait(_said_by_focused(SPEAKER), "Return")  # applied; back on the chip
    assert int(last_field(d, markers.SEARCH_WORD_RESULTS, "count")) == by_speaker

    d.move_focus("Down", "Down")  # the era row under the chip, then the results


BASKET_QUERY = "gold"


def _focus_on(widget_class: str, text: str) -> str:
    return pattern(markers.NAV_FOCUS, widget=f'{widget_class} "{text}"')


def _basket_runs(d: Driver, text: str, **changed: object) -> int:
    """Return on a basket's + or chip: wait for the change and its run; return its count."""
    marker = (
        markers.WORD_BASKET_MODE
        if "mode" in changed and len(changed) == 1
        else (markers.WORD_BASKET_CHANGED)
    )
    with d.expect(pattern(marker, **changed)):
        d.key_then_wait(pattern(markers.WORD_QUERY_RUN, text=text), "Return")
    return int(last_field(d, markers.WORD_QUERY_RUN, "count", text=text))


def test_two_words_are_combined_by_keyboard(boot: AppBoot) -> None:
    """A word's + picks it; two picked search the same story; the ALL chip flips to ANY."""
    first, second = expected.words_matching(BASKET_QUERY)[:2]
    both, either = f'"{first}" "{second}"', f'"{first}" | "{second}"'
    d = boot(nodes.WORD_SEARCH)
    search.type_query(d, BASKET_QUERY)
    with d.expect(d.FOCUS_MOVED):  # Return picks the first word and lands on it
        d.key_then_wait(pattern(markers.WORD_SELECTED_CHIP, word=first), "Return")

    d.move_focus("Right", pattern=_focus_on("_PlusButton", "+"))
    count = _basket_runs(d, f'"{first}"', count=1)
    assert count == len(expected.word_query(f'"{first}"').title_dict)

    d.move_focus("Down", pattern=_focus_on("_PlusButton", "+"))  # the second word's +
    count_all = _basket_runs(d, both, count=2, mode="ALL")
    assert count_all == len(expected.word_query(both).title_dict)

    d.move_focus("Up", "Up", pattern=d.FOCUS_MOVED)  # the first word's +, then the basket row
    count_any = _basket_runs(d, either, mode="ANY")
    assert count_any == len(expected.word_query(either).title_dict)
    assert count_any >= count_all


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
    d.key_then_wait(d.FOCUS_MOVED, "Right")  # the group's + (it picks tags to combine)
    d.key_then_wait(d.FOCUS_MOVED, "Right")  # the era row, above the group's titles
    d.key_then_wait(d.FOCUS_MOVED, "Down")  # the titles
    d.key_then_wait(d.FOCUS_MOVED, "Up")  # the era row again
    d.key_then_wait(_chip_focused(MULTI_GROUP), "Left")  # back to the selected chip


COMBINE_QUERY = "gyro"


def _combined(d: Driver, **fields: object) -> int:
    """Return on a tag's + or chip, or in the box: wait for the stories; return their count."""
    d.key_then_wait(pattern(markers.TAG_COMBINED_RESULTS, **fields), "Return")
    return int(last_field(d, markers.TAG_COMBINED_RESULTS, "count"))


def test_tags_are_combined_and_excluded_by_keyboard(boot: AppBoot) -> None:
    """A tag's + picks it; two picked list the stories both tag; a picked tag steps to 'not'."""
    first, second = (m.label for m in expected.tags_matching(COMBINE_QUERY)[:2])
    d = boot(nodes.TAG_SEARCH)
    search.type_query(d, COMBINE_QUERY)
    d.key_then_wait(d.FOCUS_MOVED, "Return")  # the first chip

    d.move_focus("Right", pattern=_focus_on("_PlusButton", "+"))
    with d.expect(pattern(markers.TAG_BASKET_CHANGED, count=1)):
        assert _combined(d, tags=first) == expected.tag_selection_count((first,))

    d.move_focus("Down", pattern=_focus_on("_PlusButton", "+"))  # the second tag's +
    both = f"{first} + {second}"
    with d.expect(pattern(markers.TAG_BASKET_CHANGED, count=2, mode="ALL")):
        count = _combined(d, tags=both)
    assert count == expected.tag_selection_count((first, second))

    d.move_focus("Up", "Up")  # the first tag's +, then the picked-tags row (on ALL)
    d.move_focus("Right", pattern=_focus_on("_BasketChipButton", first))
    d.move_focus("Right", pattern=_focus_on("_BasketChipButton", second))
    count = _combined(d, tags=f"{first} -{second}")  # the second, left out
    assert count == expected.tag_selection_count((first,), (second,))


ERA_TAG_QUERY = "gyro"  # Gyro Gearloose, typed whole: picked as typed
ERA = (1951, 1954)
ERA_LABEL = "1951-54"
ERA_STEPS = 3  # All years, 1942-46, 1947-50, then 1951-54


def test_the_era_filter_narrows_tag_results(boot: AppBoot) -> None:
    """Right from a tag is the era row; Enter on an era lists only that tag's stories then."""
    tag = expected.tags_matching(ERA_TAG_QUERY)[0].label
    everyone = expected.tag_stories_in_years(tag)
    in_era = expected.tag_stories_in_years(tag, ERA)
    assert 0 < in_era < everyone, "the era must narrow the stories, not empty them"

    d = boot(nodes.TAG_SEARCH)
    with d.expect(pattern(markers.TAG_TITLES_LISTED, tag=tag, count=everyone)):
        search.type_query(d, ERA_TAG_QUERY)
    d.key_then_wait(_chip_focused(tag), "Return")
    d.move_focus("Right", pattern=_focus_on("_PlusButton", "+"))
    d.move_focus("Right", pattern=_focus_on("_EraChipButton", "All years"))
    d.move_focus(*["Right"] * ERA_STEPS)
    with d.expect(pattern(markers.ERA_FILTER_SET, era=ERA_LABEL)):
        d.key_then_wait(pattern(markers.TAG_TITLES_LISTED, tag=tag, count=in_era), "Return")
    d.move_focus("Down")  # the tag's stories in the era


SCOPE_TAG_QUERY = "gyro"  # Gyro Gearloose, typed whole: listed as typed
SCOPE_WORD_QUERY = "gold"


def test_a_word_search_is_restricted_to_a_tag(boot: AppBoot) -> None:
    """The tag listed in the tag search is offered to the word search: 'Only in: <tag>'."""
    tag = expected.tags_matching(SCOPE_TAG_QUERY)[0].label
    word = expected.words_matching(SCOPE_WORD_QUERY)[0]
    everywhere = expected.word_stories(word)
    in_tag = expected.word_stories_in_tag(word, tag)
    assert 0 < in_tag < everywhere, "the tag must narrow the stories, not empty them"

    d = boot(nodes.TAG_SEARCH)
    with d.expect(pattern(markers.TAG_TITLES_LISTED, tag=tag)):
        search.type_query(d, SCOPE_TAG_QUERY)
    d.key_then_wait(markers.EXITED_BOTTOM_FOCUS, "Escape")  # from the box to the tree
    d.key_then_wait(pattern(markers.NEW_SELECTED_NODE, name="Words"), "Down")
    with d.expect(pattern(markers.SEARCH_MODE_SET, mode="Word")):  # Return opens it
        search.type_query(d, SCOPE_WORD_QUERY)
    with d.expect(d.FOCUS_MOVED):  # Return picks the first word and lands on it
        d.key_then_wait(pattern(markers.WORD_SELECTED_CHIP, word=word), "Return")
    assert int(last_field(d, markers.SEARCH_WORD_RESULTS, "count")) == everywhere

    d.move_focus("Right", pattern=_focus_on("_PlusButton", "+"))
    d.move_focus("Right", pattern=_said_by_focused("anyone"))
    d.move_focus("Down", pattern=_focus_on("_EraChipButton", "All years"))
    d.move_focus("Down", pattern=_focus_on("_ScopeChipButton", "Everywhere"))
    d.move_focus("Right", pattern=_focus_on("_ScopeChipButton", f"Only in: {tag}"))
    with d.expect(pattern(markers.WORD_TAG_FILTER_SET, tags=tag)):
        d.key_then_wait(pattern(markers.SEARCH_WORD_RESULTS, count=in_tag), "Return")


def test_typed_tags_are_combined_on_return(boot: AppBoot) -> None:
    """Tags typed with + , | or - make one chip; Return combines them and lists their stories."""
    first, second = (m.label for m in expected.tags_matching(COMBINE_QUERY)[:2])
    typed = f"{first.lower()} -{second.lower()}"
    d = boot(nodes.TAG_SEARCH)
    search.type_query(d, typed)
    with d.expect(d.FOCUS_MOVED):  # on the first story they list
        count = _combined(d, tags=f"{first} -{second}")
    assert count == expected.tag_selection_count((first,), (second,))


def test_typed_tags_with_a_year_range_list_only_those_years(boot: AppBoot) -> None:
    """A typed year: range joins the typed tags as a chip; the stories are only those years'."""
    tag = expected.tags_matching(ERA_TAG_QUERY)[0].label
    first, last = ERA
    typed = f"{tag.lower()} year:{first}-{last % 100}"
    d = boot(nodes.TAG_SEARCH)
    search.type_query(d, typed)
    with d.expect(pattern(markers.TAG_BASKET_CHANGED, count=2)):  # the tag and the years
        count = _combined(d, tags=f"{tag} year:{first}-{last % 100}")
    assert count == expected.tag_stories_in_years(tag, ERA)


def test_the_box_clear_button_and_results_are_walked_by_keyboard(boot: AppBoot) -> None:
    """Down leaves the box for the results, Right at the text's end for the clear button."""
    d = boot(nodes.TITLE_SEARCH)
    search.type_query(d, CLEAR_QUERY)
    d.key_then_wait(d.FOCUS_MOVED, "Down")  # the first result row
    d.key_then_wait(d.FOCUS_MOVED, "Left")  # no chips in title search: the clear button
    d.key_then_wait(d.FOCUS_MOVED, "Right")  # back to the results
    d.key_then_wait(d.FOCUS_MOVED, "Left")
    d.key_then_wait(search.SEARCH_BOX_FOCUSED, "Left")  # from the clear button, the box
    d.key_then_wait(CLEAR_FOCUSED, "Right")  # the cursor is at the end: the clear button
    d.key_then_wait(d.FOCUS_MOVED, "Right")  # and on to the results
    d.key_then_wait(markers.SEARCH_EXITED_NAV, "Escape")


CLEAR_FOCUSED = pattern(markers.NAV_FOCUS, widget=re.compile(r"SearchClearButton.*"))
CLEAR_WORD_QUERY = "gold"


def test_the_clear_button_is_reached_by_keyboard_with_chips_listed(boot: AppBoot) -> None:
    """Back in the box, Right at the text's end is the clear button: it clears words and era."""
    d = boot(nodes.WORD_SEARCH)
    search.type_query(d, CLEAR_WORD_QUERY)
    d.key_then_wait(d.FOCUS_MOVED, "Return")  # the first word
    d.move_focus("Right", pattern=_focus_on("_PlusButton", "+"))
    d.key_then_wait(pattern(markers.WORD_BASKET_CHANGED, count=1), "Return")
    d.move_focus("Right", pattern=_said_by_focused("anyone"))
    d.move_focus("Down", pattern=_focus_on("_EraChipButton", "All years"))
    d.move_focus("Right")
    d.key_then_wait(pattern(markers.ERA_FILTER_SET, era="1942-46"), "Return")

    d.move_focus("Up", pattern=_said_by_focused("anyone"))
    d.key_then_wait(search.SEARCH_BOX_FOCUSED, "Up")
    d.key_then_wait(CLEAR_FOCUSED, "Right")
    with (
        d.expect(pattern(markers.ERA_FILTER_SET, era="All years")),
        d.expect(search.SEARCH_BOX_FOCUSED),
    ):
        d.key_then_wait(pattern(markers.SEARCH_CLEARED, mode="word"), "Return")


# ----------------------------------------------------------------- memory --

LEAK_ROUNDS_QUERY = {"Word": "gold", "Tag": "gyro"}
PICKED = {"Word": markers.WORD_BASKET_CHANGED, "Tag": markers.TAG_BASKET_CHANGED}


@pytest.mark.parametrize(("mode", "node"), [("Word", nodes.WORD_SEARCH), ("Tag", nodes.TAG_SEARCH)])
def test_search_round_trips_leave_no_chips_behind(
    boot: AppBoot, mode: str, node: list[str]
) -> None:
    """Fill the list, pick two with their +, clear: again and again, and no chip is kept.

    All by the remote's keys: back up to the box, Right to the clear button, Return.
    """
    d = boot(node)
    d.key_then_wait(search.SEARCH_BOX_FOCUSED, "Return")
    query = LEAK_ROUNDS_QUERY[mode]

    def round_trip() -> None:
        d.type_slowly(query, marker=search.results_line)
        d.key_then_wait(d.FOCUS_MOVED, "Return")  # the first word or tag
        d.move_focus("Right", pattern=_focus_on("_PlusButton", "+"))
        d.key_then_wait(pattern(PICKED[mode], count=1), "Return")
        d.move_focus("Down", pattern=_focus_on("_PlusButton", "+"))
        d.key_then_wait(pattern(PICKED[mode], count=2), "Return")
        d.move_focus("Up", "Up")  # the first row's +, then the picked row
        d.key_then_wait(search.SEARCH_BOX_FOCUSED, "Up")
        d.key_then_wait(CLEAR_FOCUSED, "Right")
        d.key_then_wait(pattern(markers.SEARCH_CLEARED, mode=mode.lower()), "Return")

    memory.assert_round_trips_leave_nothing(d, round_trip)
