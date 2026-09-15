"""The action bar's dots menu: Settings, How To, and the quit fence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import nodes

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

DROPDOWN_PAUSE = 0.5  # after the dropdown opens, before moving in it
# The dropdown opens focused on its first entry: Settings, How To, About.
HOW_TO_DOWNS = 1


def test_dots_menu_opens_settings(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    d.main_menu_button("menu")
    d.hold(DROPDOWN_PAUSE)
    d.key_then_wait("Display settings object.", 15, "Return")
    d.key("Escape")  # closes the settings panel (silent today; M2 adds the marker)
    d.settle()


def test_dots_menu_how_to_opens_the_document_reader(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    d.main_menu_button("menu")
    d.hold(DROPDOWN_PAUSE)
    for _ in range(HOW_TO_DOWNS):
        d.key("Down")
        d.hold(DROPDOWN_PAUSE)
    d.key_then_wait("Switching to document reader for", 15, "Return")
    d.settle()
    # Escape opens the document reader's menu on its only button, Close.
    d.key("Escape")
    d.hold(DROPDOWN_PAUSE)
    d.key_then_wait("Main screen is active", 15, "Return")
