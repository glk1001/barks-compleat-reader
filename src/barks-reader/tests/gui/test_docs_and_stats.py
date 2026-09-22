"""The statistics screen and the articles that open in the comic reader."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from barks_gui import nodes
from barks_gui.logs import fields_of, last_field
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
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
    _pages_opened(d, nodes.INTRO_DOCUMENT)
    assert fields_of(d, markers.DOCUMENT_PAGE, "page") == ["1"]
    _close_document(d)


def test_the_censorship_document_turns_pages(boot: AppBoot) -> None:
    d = boot(nodes.APPENDIX)
    _open_document(d, nodes.CENSORSHIP_DOCUMENT)
    d.key_then_wait(pattern(markers.DOCUMENT_PAGE, page=2), "Right")
    d.key_then_wait(pattern(markers.DOCUMENT_PAGE, page=1), "Left")
    assert _pages_opened(d, nodes.CENSORSHIP_DOCUMENT) >= PAGES_FOR_A_TURN
    assert fields_of(d, markers.DOCUMENT_PAGE, "page") == ["1", "2", "1"]
    _close_document(d)


def test_by_the_numbers_opens_and_closes_two_ways(boot: AppBoot) -> None:
    """Escape closes the page outright; so does its menu's Close button."""
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
    with (
        d.expect(markers.CORPUS_STATS_CLOSING),
        d.expect(MAIN_FROM_NUMBERS),
        d.expect(MAIN_ENTERED),
    ):
        d.key("Escape")

    with d.expect(markers.CORPUS_STATS_OPENED), d.expect(NUMBERS_ENTERED):
        d.key("Return")  # the node is still selected
    d.key_then_wait(d.MENU_ENTERED, "Up")
    with d.expect(markers.CORPUS_STATS_CLOSING), d.expect(MAIN_FROM_NUMBERS):
        d.key("Return")
