"""The statistics screen, the documents and the articles.

The documents include the illustrated history's chapters; the articles open in the comic
reader.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from barks_gui import expected, nodes
from barks_gui.logs import fields_of, last_field
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern
from barks_reader.core.main_layout import MainLayoutMode

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from barks_reader.core.document_links import StoryLink
    from gui_driver import Driver

LOADING_IMAGE = pattern(markers.STATISTICS_LOADING_IMAGE)


def test_statistics_tabs_and_the_word_dropdown(boot: AppBoot) -> None:
    """Right/Left move along the tabs and Return loads one; the last tab is a dropdown.

    The tab row is the fixed statistics followed by "Word Statistics", whose Return
    opens a dropdown of word clouds instead of loading an image directly.
    """
    d = boot(nodes.STATISTICS)
    d.key_then_wait(markers.STATISTICS_ENTERED_NAV, "Right")
    d.move_focus("Right")  # second tab
    d.key_then_wait(LOADING_IMAGE, "Return")
    d.move_focus("Left")  # back to the first
    d.key_then_wait(LOADING_IMAGE, "Return")
    d.move_focus("Left")  # wraps to the last tab, Word Statistics
    d.key_then_wait(markers.STATISTICS_ENTERED_DROPDOWN, "Return")
    d.move_focus("Down")
    # The dropdown still eats keys until it has dismissed itself, so wait for that too.
    with (
        d.expect(markers.STATISTICS_EXITED_DROPDOWN),
        d.expect(LOADING_IMAGE),
        d.expect(d.DROPDOWN_DISMISSED),
    ):
        d.key("Return")
    d.key_then_wait(markers.STATISTICS_EXITED_NAV, "Escape")

    # Each load named a real file; the two tabs showed different images and
    # the dropdown pick a word cloud.
    loaded = [Path(p) for p in fields_of(d, markers.STATISTICS_LOADING_IMAGE, "path")]
    assert len(loaded) == STAT_LOADS
    assert all(p.is_file() for p in loaded), loaded
    assert loaded[0] != loaded[1]
    assert loaded[2] == loaded[0], "Left went back to the first tab's image"
    assert "wordcloud" in loaded[3].name


STAT_LOADS = 4  # boot shows the first tab, then the second, the first again, a word cloud
PAGES_FOR_A_TURN = 2
ARTICLE_OPENING_PAGE = 0  # an article has no cue: it opens at its front page


def test_an_article_opens_in_the_comic_reader(boot: AppBoot) -> None:
    """Introduction articles are comics: Return on the node opens the reader."""
    d = boot(nodes.INTRODUCTION)
    d.select_node(nodes.FANTA_INTRO_ARTICLE)
    with (
        d.expect(pattern(markers.ARTICLE_NODE_PRESSED)),
        d.expect(pattern(markers.ALL_IMAGES_LOADED), 30),
    ):
        d.key("Return")
    # The node pressed is the article selected (logged by its Titles name), and
    # an article has no cue, so it opens at its front page.
    assert d.current_node() == nodes.FANTA_INTRO_ARTICLE
    assert re.fullmatch(r"[A-Z0-9_]+", last_field(d, markers.ARTICLE_NODE_PRESSED, "name"))
    assert d.current_page() == ARTICLE_OPENING_PAGE
    d.close_reader()


MAIN_FROM_DOCUMENT = pattern(markers.MAIN_SCREEN_ACTIVE, origin=markers.FROM_DOCUMENT_READER)
MAIN_FROM_NUMBERS = pattern(markers.MAIN_SCREEN_ACTIVE, origin=markers.FROM_BY_THE_NUMBERS)
DOCUMENT_ENTERED = pattern(markers.SCREEN_ENTERED, name="document_reader")
NUMBERS_ENTERED = pattern(markers.SCREEN_ENTERED, name="corpus_stats")
MAIN_ENTERED = pattern(markers.SCREEN_ENTERED, name="main_screen")


def _open_document(d: Driver, name: str) -> None:
    d.select_node(name)
    with (
        d.expect(pattern(markers.DOCUMENT_READER_ACTIVE)),
        d.expect(pattern(markers.DOCUMENT_OPENED)),
        d.expect(pattern(markers.DOCUMENT_PAGE, page=1)),
        d.expect(DOCUMENT_ENTERED),  # the transition has finished before any key is sent
    ):
        d.key("Return")


def _close_document(d: Driver) -> None:
    """Escape opens the document reader's menu on Close; Return presses it."""
    d.key_then_wait(d.MENU_ENTERED, "Escape")
    with d.expect(markers.DOCUMENT_CLOSING), d.expect(MAIN_FROM_DOCUMENT):
        d.key("Return")


def _pages_opened(d: Driver, title: str) -> int:
    """Return the page count `title` opened with, after checking every page shown agreed."""
    assert last_field(d, markers.DOCUMENT_OPENED, "title") == title
    pages = int(last_field(d, markers.DOCUMENT_OPENED, "pages"))
    assert pages >= 1
    assert set(fields_of(d, markers.DOCUMENT_PAGE, "pages")) == {str(pages)}
    return pages


def test_the_intro_document_opens_and_closes(boot: AppBoot) -> None:
    d = boot(nodes.INTRODUCTION)
    _open_document(d, nodes.INTRO_DOCUMENT)
    pages = _pages_opened(d, nodes.INTRO_DOCUMENT)
    assert pages == expected.document_page_count(expected.intro_document_dir())
    assert fields_of(d, markers.DOCUMENT_PAGE, "page") == ["1"]
    _close_document(d)


def test_the_censorship_document_turns_pages(boot: AppBoot) -> None:
    """Right turns a page, or on the two-page spread a pair (pages 1 and 2, then 3 and 4)."""
    d = boot(nodes.APPENDIX)
    _open_document(d, nodes.CENSORSHIP_DOCUMENT)
    paired = last_field(d, markers.MAIN_LAYOUT_MODE, "mode") == MainLayoutMode.SPREAD.value
    turned_to = 3 if paired else 2
    d.key_then_wait(pattern(markers.DOCUMENT_PAGE, page=turned_to), "Right")
    d.key_then_wait(pattern(markers.DOCUMENT_PAGE, page=1), "Left")
    pages = _pages_opened(d, nodes.CENSORSHIP_DOCUMENT)
    assert pages == expected.document_page_count(expected.censorship_document_dir())
    assert pages >= PAGES_FOR_A_TURN + (1 if paired else 0)
    assert fields_of(d, markers.DOCUMENT_PAGE, "page") == ["1", str(turned_to), "1"]
    if paired:
        assert fields_of(d, markers.DOCUMENT_RIGHT_PAGE, "page") == ["2", "4", "2"]
    _close_document(d)


def test_by_the_numbers_opens_and_closes_two_ways(boot: AppBoot) -> None:
    """Escape lands on the bar's Close and Return closes, as in the readers; so does Left."""
    d = boot(nodes.INTRODUCTION)
    d.select_node(nodes.BY_THE_NUMBERS)
    with (
        d.expect(markers.BY_THE_NUMBERS_ACTIVE),
        d.expect(markers.CORPUS_STATS_OPENED),
        d.expect(NUMBERS_ENTERED),
    ):
        d.key("Return")
    # MAIN_FROM_NUMBERS is logged as the transition starts; the main screen's
    # entered line, once it ends. That line is already in the log from boot, so
    # only a NEW one counts - the plain wait_for would return at once.
    d.key_then_wait(d.MENU_ENTERED, "Escape")
    with (
        d.expect(markers.CORPUS_STATS_CLOSING),
        d.expect(MAIN_FROM_NUMBERS),
        d.expect(MAIN_ENTERED),
    ):
        d.key("Return")

    with d.expect(markers.CORPUS_STATS_OPENED), d.expect(NUMBERS_ENTERED):
        d.key("Return")  # the node is still selected
    with d.expect(markers.CORPUS_STATS_CLOSING), d.expect(MAIN_FROM_NUMBERS):
        d.key("Left")


# --- the illustrated history: chapters, and their figures' stories -----------------------
#
# The chapters move as the history grows, so every name, page and story here is read from
# the data (`expected.illustrated_history_chapters`, `expected.first_linked_page`), and a
# machine without them skips.

GOTO_STORY = pattern(markers.DOCUMENT_GOTO_STORY)


def _linked_page(d: Driver, *, several: bool) -> expected.LinkedPage:
    """Return the first chapter page with one story link (or several), else skip.

    As the booted app shows pages: on the two-page spread in pairs from the first,
    with Go to Story offering both pages' links, so the page is the pair's first.
    """
    if not expected.illustrated_history_chapters():
        pytest.skip(f"no illustrated-history chapters here: {expected.illustrated_history_dir()}")
    paired = last_field(d, markers.MAIN_LAYOUT_MODE, "mode") == MainLayoutMode.SPREAD.value
    linked = expected.first_linked_page(several=several, paired=paired)
    if linked is None:
        pytest.skip(f"no chapter page links {'several stories' if several else 'one story'}")
    return linked


def _open_chapter_at(d: Driver, linked: expected.LinkedPage) -> None:
    """Open the history, then the page's chapter, and turn to the page."""
    d.open_branch(nodes.ILLUSTRATED_HISTORY)
    _open_document(d, linked.chapter.title)
    for page in linked.turns:
        d.key_then_wait(pattern(markers.DOCUMENT_PAGE, page=page), "Right")


def _focus_go_to_story(d: Driver) -> None:
    """Escape opens the bar on Close, its default; Go to Story is the button before it."""
    d.key_then_wait(d.MENU_ENTERED, "Escape")
    d.move_focus("Left")


def _went_to(d: Driver, link: StoryLink) -> None:
    """Check the jump named `link`'s story and page, and selected the story."""
    assert last_field(d, markers.DOCUMENT_GOTO_STORY, "name") == link.title.name
    assert last_field(d, markers.DOCUMENT_GOTO_STORY, "page") == link.page
    assert d.current_node() == link.title.name


def test_the_history_node_lists_the_chapters_on_disk(boot: AppBoot) -> None:
    """Under Introduction, the history's children are its chapter folders, in order."""
    chapters = expected.illustrated_history_chapters()
    if not chapters:
        pytest.skip(f"no illustrated-history chapters here: {expected.illustrated_history_dir()}")
    d = boot(nodes.INTRODUCTION)
    d.open_branch(nodes.ILLUSTRATED_HISTORY)
    for chapter in chapters:
        d.key_then_wait(pattern(markers.NEW_SELECTED_NODE, name=chapter.title), "Down")
    # Nothing follows them: the next node down is the Introduction's next one.
    d.key_then_wait(pattern(markers.NEW_SELECTED_NODE, name=nodes.BY_THE_NUMBERS), "Down")


def test_go_to_story_then_go_back_returns_to_the_page(boot: AppBoot) -> None:
    """A page's one story is gone to at once; Go Back reopens the chapter at that page."""
    d = boot(nodes.INTRODUCTION)
    linked = _linked_page(d, several=False)
    (link,) = linked.links
    _open_chapter_at(d, linked)
    _focus_go_to_story(d)
    with (
        d.expect(GOTO_STORY),
        d.expect(markers.DOCUMENT_CLOSING),
        d.expect(MAIN_FROM_DOCUMENT),
        d.expect(pattern(markers.GOTO_PAGE_OFFERED, page=link.page)),
        d.expect(pattern(markers.NEW_SELECTED_NODE, name=link.title.name)),
    ):
        d.key("Return")
    _went_to(d, link)

    # A keyboard jump leaves the keys on the title view; Escape hands them back to the tree.
    d.key_then_wait(markers.EXITED_BOTTOM_FOCUS, "Escape")
    # Back closes the story's branch and puts the tree at the chapter's node, as a fresh
    # open leaves it, so closing the chapter lands there and not on the story.
    with (
        d.expect(pattern(markers.GOING_BACK_TO_NODE, name=linked.chapter.title)),
        d.expect(pattern(markers.NODE_COLLAPSED_NO_STATE_CHANGE, name="The Stories")),
        d.expect(pattern(markers.DOCUMENT_OPENED, title=linked.chapter.title)),
        d.expect(pattern(markers.DOCUMENT_PAGE, page=linked.page)),
        d.expect(DOCUMENT_ENTERED),
    ):
        d.go_back()
    assert fields_of(d, markers.DOCUMENT_PAGE, "page")[-1] == str(linked.page)

    # The bar comes back on Go to Story, the button pressed last: Close is the next one.
    d.key_then_wait(d.MENU_ENTERED, "Escape")
    d.move_focus("Right")
    with d.expect(markers.DOCUMENT_CLOSING), d.expect(MAIN_FROM_DOCUMENT):
        d.key("Return")


def test_several_stories_on_a_page_are_picked_from_a_list(boot: AppBoot) -> None:
    """Go to Story on a page with several stories lists them; Down then Return picks the second."""
    d = boot(nodes.INTRODUCTION)
    linked = _linked_page(d, several=True)
    second = linked.links[1]
    _open_chapter_at(d, linked)
    _focus_go_to_story(d)
    d.key_then_wait(d.FOCUS_MOVED, "Return")  # the list opens, its first story focused
    d.move_focus("Down")
    with (
        d.expect(GOTO_STORY),
        d.expect(d.DROPDOWN_DISMISSED),
        d.expect(MAIN_FROM_DOCUMENT),
        d.expect(pattern(markers.NEW_SELECTED_NODE, name=second.title.name)),
    ):
        d.key("Return")
    _went_to(d, second)
