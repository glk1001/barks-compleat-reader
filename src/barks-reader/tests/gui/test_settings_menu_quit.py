"""The action bar's dots menu: Settings, How To, and the quit fence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import nodes
from gui_driver import DROPDOWN_DISMISS_PAUSE

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

DROPDOWN_PAUSE = 0.5  # after the dropdown opens, before moving in it
# The dropdown opens focused on its first entry: Settings, How To, About.
HOW_TO_DOWNS = 1
ABOUT_DOWNS = 2
QUIT_TITLE = "Quit"


def _let_the_dropdown_go(d: Driver) -> None:
    """Wait for the dots menu to finish dismissing after a pick, or it eats the next Escape."""
    d.settle()
    d.hold(DROPDOWN_DISMISS_PAUSE)


def test_dots_menu_opens_settings(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    d.main_menu_button("menu")
    d.hold(DROPDOWN_PAUSE)
    d.key_then_wait("Display settings object.", 15, "Return")
    _let_the_dropdown_go(d)
    d.key_then_wait("Settings closed.", 15, "Escape")


def test_dots_menu_how_to_opens_the_document_reader(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    d.main_menu_button("menu")
    d.hold(DROPDOWN_PAUSE)
    for _ in range(HOW_TO_DOWNS):
        d.key("Down")
        d.hold(DROPDOWN_PAUSE)
    d.key_then_wait("Switching to document reader for", 15, "Return")
    _let_the_dropdown_go(d)
    # Escape opens the document reader's menu on its only button, Close.
    d.key("Escape")
    d.hold(DROPDOWN_PAUSE)
    d.key_then_wait("Main screen is active", 15, "Return")


def test_dots_menu_about_opens_and_escape_dismisses(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    d.main_menu_button("menu")
    d.hold(DROPDOWN_PAUSE)
    for _ in range(ABOUT_DOWNS):
        d.key("Down")
        d.hold(DROPDOWN_PAUSE)
    d.key_then_wait("About box opened.", 15, "Return")
    _let_the_dropdown_go(d)
    d.key("Escape")  # the box auto-dismisses; nothing is logged for that
    d.settle()
    d.key_then_wait("New selected node", 15, "Down")  # and the tree answers again


def test_quit_asks_first_and_escape_stays(boot: AppBoot) -> None:
    """The fence: with confirm_quit on, Quit opens a popup and Escape keeps the app up."""
    d = boot(nodes.GHOST_OF_THE_GROTTO)
    with (
        d.expect("Quit requested: asking for confirmation."),
        d.expect(f'Confirm popup opened: "{QUIT_TITLE}".'),
    ):
        d.main_menu_button("quit")
    d.key_then_wait(f'Confirm popup "{QUIT_TITLE}": cancelled.', 15, "Escape")
    d.expect_no_new("Closing app", 2.0)
    d.key_then_wait("New selected node", 15, "Down")  # still alive and answering


def test_quit_confirmed_closes_the_app(boot: AppBoot) -> None:
    d = boot(nodes.GHOST_OF_THE_GROTTO)
    with d.expect(f'Confirm popup opened: "{QUIT_TITLE}".'):
        d.main_menu_button("quit")
    with d.expect(f'Confirm popup "{QUIT_TITLE}": confirmed.'), d.expect("Closing app"):
        d.key("Return")
