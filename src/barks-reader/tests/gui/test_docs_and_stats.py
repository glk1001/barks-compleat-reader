"""The statistics screen and the articles that open in the comic reader."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from barks_gui import nodes

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

TAB_PAUSE = 0.4


def test_statistics_tabs_and_the_word_dropdown(boot: AppBoot) -> None:
    """Right/Left move along the tabs and Return loads one; the last tab is a dropdown.

    The tab row is the fixed statistics followed by "Word Statistics", whose Return
    opens a dropdown of word clouds instead of loading an image directly.
    """
    d = boot(nodes.STATISTICS)
    d.key_then_wait("StatisticsScreen: entered nav focus.", 15, "Right")
    d.key("Right")  # second tab
    d.hold(TAB_PAUSE)
    d.key_then_wait("Statistics: loading image", 15, "Return")
    d.key("Left")  # back to the first
    d.hold(TAB_PAUSE)
    d.key_then_wait("Statistics: loading image", 15, "Return")
    d.key("Left")  # wraps to the last tab, Word Statistics
    d.hold(TAB_PAUSE)
    d.key_then_wait("StatisticsScreen: entered dropdown nav.", 15, "Return")
    d.key("Down")
    d.hold(TAB_PAUSE)
    with d.expect("StatisticsScreen: exited dropdown nav."), d.expect("Statistics: loading image"):
        d.key("Return")
    d.key_then_wait("StatisticsScreen: exited nav focus.", 15, "Escape")


def test_an_article_opens_in_the_comic_reader(boot: AppBoot) -> None:
    """Introduction articles are comics: Return on the node opens the reader."""
    d = boot(nodes.INTRODUCTION)
    d.select_node(nodes.FANTA_INTRO_ARTICLE)
    with d.expect("Article node pressed"), d.expect("All images loaded", 30):
        d.key("Return")
    d.close_reader()


PAGE_PAUSE = 0.4
# Parentheses in a log line must be escaped: wait patterns are regexes.
MAIN_FROM_DOCUMENT = re.escape("Main screen is active (from document reader).")
MAIN_FROM_NUMBERS = re.escape("Main screen is active (from By the Numbers).")
DOCUMENT_ENTERED = "Screen 'document_reader' entered."
NUMBERS_ENTERED = "Screen 'corpus_stats' entered."


def _open_document(d: Driver, name: str) -> None:
    d.select_node(name)
    with (
        d.expect("Document reader screen is active:"),
        d.expect(r"Document reader opened \".*\" with \d+ pages\."),
        d.expect(r"Document page 1/\d+"),
        d.expect(DOCUMENT_ENTERED),  # the transition has finished before any key is sent
    ):
        d.key("Return")


def _close_document(d: Driver) -> None:
    """Escape opens the document reader's menu on Close; Return presses it."""
    d.key_then_wait("Entered menu mode.", 15, "Escape")
    d.hold(PAGE_PAUSE)
    with d.expect("Document reader closing."), d.expect(MAIN_FROM_DOCUMENT):
        d.key("Return")


def test_the_intro_document_opens_and_closes(boot: AppBoot) -> None:
    d = boot(nodes.INTRODUCTION)
    _open_document(d, nodes.INTRO_DOCUMENT)
    _close_document(d)


def test_the_censorship_document_turns_pages(boot: AppBoot) -> None:
    d = boot(nodes.APPENDIX)
    _open_document(d, nodes.CENSORSHIP_DOCUMENT)
    d.key_then_wait(r"Document page 2/\d+", 15, "Right")
    d.key_then_wait(r"Document page 1/\d+", 15, "Left")
    _close_document(d)


def test_by_the_numbers_opens_and_closes_two_ways(boot: AppBoot) -> None:
    """Escape closes the page outright; so does its menu's Close button."""
    d = boot(nodes.INTRODUCTION)
    d.select_node(nodes.BY_THE_NUMBERS)
    with (
        d.expect("By the Numbers screen is active."),
        d.expect("CorpusStats: opened."),
        d.expect(NUMBERS_ENTERED),
    ):
        d.key("Return")
    with d.expect("CorpusStats: closing."), d.expect(MAIN_FROM_NUMBERS):
        d.key("Escape")
    d.wait_for("Screen 'main_screen' entered.")

    with d.expect("CorpusStats: opened."), d.expect(NUMBERS_ENTERED):
        d.key("Return")  # the node is still selected
    d.key_then_wait("Entered menu mode.", 15, "Up")
    d.hold(PAGE_PAUSE)
    with d.expect("CorpusStats: closing."), d.expect(MAIN_FROM_NUMBERS):
        d.key("Return")
