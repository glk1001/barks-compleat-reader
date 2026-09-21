"""The action bar's dots menu: Settings, How To, and the quit fence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import nodes
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot
    from gui_driver import Driver

# The dropdown opens focused on its first entry: Settings, How To, About.
HOW_TO_DOWNS = 1
ABOUT_DOWNS = 2
QUIT_TITLE = "Quit"
DOCUMENT_ENTERED = pattern(markers.SCREEN_ENTERED, name="document_reader")
ANY_NODE_SELECTED = pattern(markers.NEW_SELECTED_NODE)


def _open_dots_menu(d: Driver, downs: int) -> None:
    """Open the dots menu, which lands focus on its first entry, and step down `downs`."""
    d.main_menu_button_then_wait("menu", d.FOCUS_MOVED)
    d.move_focus(*["Down"] * downs)


def _pick(d: Driver, marker: str) -> None:
    """Return on the focused entry, waiting for what it opens and for the dropdown to go.

    Until the dropdown has dismissed itself it still owns the window's keys and
    would eat the next Escape.
    """
    with d.expect(marker), d.expect(d.DROPDOWN_DISMISSED):
        d.key("Return")


def test_dots_menu_opens_settings(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    _open_dots_menu(d, downs=0)
    _pick(d, markers.DISPLAY_SETTINGS)
    d.key_then_wait(markers.SETTINGS_CLOSED, 15, "Escape")


def test_dots_menu_how_to_opens_the_document_reader(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    _open_dots_menu(d, downs=HOW_TO_DOWNS)
    with d.expect(DOCUMENT_ENTERED):  # the transition has finished before any key is sent
        _pick(d, pattern(markers.SWITCHING_TO_DOCUMENT_READER))
    # Escape opens the document reader's menu on its only button, Close.
    d.key_then_wait(d.MENU_ENTERED, 15, "Escape")
    d.key_then_wait(pattern(markers.MAIN_SCREEN_ACTIVE), 15, "Return")


def test_dots_menu_about_opens_and_escape_dismisses(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    _open_dots_menu(d, downs=ABOUT_DOWNS)
    _pick(d, markers.ABOUT_BOX_OPENED)
    d.key("Escape")  # the box auto-dismisses; nothing is logged for that
    d.settle()
    d.key_then_wait(ANY_NODE_SELECTED, 15, "Down")  # and the tree answers again


def test_quit_asks_first_and_escape_stays(boot: AppBoot) -> None:
    """The fence: with confirm_quit on, Quit opens a popup and Escape keeps the app up."""
    d = boot(nodes.GHOST_OF_THE_GROTTO)
    with (
        d.expect(markers.QUIT_ASKING),
        d.expect(pattern(markers.CONFIRM_POPUP_OPENED, title=QUIT_TITLE)),
    ):
        d.main_menu_button("quit")
    d.key_then_wait(pattern(markers.CONFIRM_POPUP_CANCELLED, title=QUIT_TITLE), 15, "Escape")
    d.expect_no_new(pattern(markers.CLOSING_APP), 2.0)
    d.key_then_wait(ANY_NODE_SELECTED, 15, "Down")  # still alive and answering


def test_quit_confirmed_closes_the_app(boot: AppBoot) -> None:
    d = boot(nodes.GHOST_OF_THE_GROTTO)
    with d.expect(pattern(markers.CONFIRM_POPUP_OPENED, title=QUIT_TITLE)):
        d.main_menu_button("quit")
    with (
        d.expect(pattern(markers.CONFIRM_POPUP_CONFIRMED, title=QUIT_TITLE)),
        d.expect(pattern(markers.CLOSING_APP)),
    ):
        d.key("Return")
