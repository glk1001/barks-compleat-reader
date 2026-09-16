"""The action bar's dots menu: Settings, How To, and the quit fence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import nodes

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

# The dropdown opens focused on its first entry: Settings, How To, About.
HOW_TO_DOWNS = 1
ABOUT_DOWNS = 2
QUIT_TITLE = "Quit"
DOCUMENT_ENTERED = "Screen 'document_reader' entered."


def _open_dots_menu(d: Driver, downs: int) -> None:
    """Open the dots menu, which lands focus on its first entry, and step down `downs`."""
    d.main_menu_button_then_wait("menu", d.FOCUS_MOVED)
    d.move_focus(*["Down"] * downs)


def _pick(d: Driver, pattern: str) -> None:
    """Return on the focused entry, waiting for what it opens and for the dropdown to go.

    Until the dropdown has dismissed itself it still owns the window's keys and
    would eat the next Escape.
    """
    with d.expect(pattern), d.expect(d.DROPDOWN_DISMISSED):
        d.key("Return")


def test_dots_menu_opens_settings(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    _open_dots_menu(d, downs=0)
    _pick(d, "Display settings object.")
    d.key_then_wait("Settings closed.", 15, "Escape")


def test_dots_menu_how_to_opens_the_document_reader(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    _open_dots_menu(d, downs=HOW_TO_DOWNS)
    with d.expect(DOCUMENT_ENTERED):  # the transition has finished before any key is sent
        _pick(d, "Switching to document reader for")
    # Escape opens the document reader's menu on its only button, Close.
    d.key_then_wait(d.MENU_ENTERED, 15, "Escape")
    d.key_then_wait("Main screen is active", 15, "Return")


def test_dots_menu_about_opens_and_escape_dismisses(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    _open_dots_menu(d, downs=ABOUT_DOWNS)
    _pick(d, "About box opened.")
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
