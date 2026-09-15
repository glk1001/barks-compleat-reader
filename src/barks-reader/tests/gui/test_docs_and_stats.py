"""The statistics screen and the articles that open in the comic reader."""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import nodes

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

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
