"""The action bar's dots menu: Settings, How To, and the quit fence."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

from barks_gui import harness, nodes
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
    d.key_then_wait(markers.SETTINGS_CLOSED, "Escape")


# The settings panel lists its fields in reader_settings._FIELDS order, and its
# keyboard focus starts on the first; this many Downs reach the fun-view title
# toggle. A miscount lands on another field, which the config-change line's key
# then reports.
FUN_VIEW_TITLE_SETTING = "show_fun_view_title_info"
DOWNS_TO_FUN_VIEW_TITLE = 6
FLIPPED = {"0": "1", "1": "0"}


def _toggle_fun_view_title(d: Driver, value: str) -> None:
    """From the tree, open Settings, toggle the fun-view title switch to `value`, close."""
    _open_dots_menu(d, downs=0)
    _pick(d, markers.DISPLAY_SETTINGS)
    d.move_focus(*["Down"] * DOWNS_TO_FUN_VIEW_TITLE)
    d.key_then_wait(
        pattern(markers.CONFIG_CHANGE, key=FUN_VIEW_TITLE_SETTING, value=value), "Return"
    )
    d.key_then_wait(markers.SETTINGS_CLOSED, "Escape")


def test_a_settings_toggle_round_trips_through_the_ini(boot: AppBoot) -> None:
    """Return on a switch flips it and the ini has the new value at once; back again restores it."""
    ini = boot.scratch / "barks-reader.ini"
    d = boot(nodes.THE_STORIES)
    original = harness.read_ini_value(ini, FUN_VIEW_TITLE_SETTING).strip()
    assert original in FLIPPED, f"unexpected ini value {original!r}"

    _toggle_fun_view_title(d, FLIPPED[original])
    assert harness.read_ini_value(ini, FUN_VIEW_TITLE_SETTING).strip() == FLIPPED[original]
    _toggle_fun_view_title(d, original)
    assert harness.read_ini_value(ini, FUN_VIEW_TITLE_SETTING).strip() == original


def test_dots_menu_how_to_opens_the_document_reader(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    _open_dots_menu(d, downs=HOW_TO_DOWNS)
    with d.expect(DOCUMENT_ENTERED):  # the transition has finished before any key is sent
        _pick(d, pattern(markers.SWITCHING_TO_DOCUMENT_READER))
    # Escape opens the document reader's menu on its only button, Close.
    d.key_then_wait(d.MENU_ENTERED, "Escape")
    d.key_then_wait(pattern(markers.MAIN_SCREEN_ACTIVE), "Return")


def test_dots_menu_about_opens_and_escape_dismisses(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    _open_dots_menu(d, downs=ABOUT_DOWNS)
    _pick(d, markers.ABOUT_BOX_OPENED)
    d.key_then_wait(markers.ABOUT_BOX_DISMISSED, "Escape")
    d.key_then_wait(ANY_NODE_SELECTED, "Down")  # and the tree answers again


def test_quit_asks_first_and_escape_stays(boot: AppBoot) -> None:
    """The fence: with confirm_quit on, Quit opens a popup and Escape keeps the app up."""
    d = boot(nodes.GHOST_OF_THE_GROTTO)
    with (
        d.expect(markers.QUIT_ASKING),
        d.expect(pattern(markers.CONFIRM_POPUP_OPENED, title=QUIT_TITLE)),
    ):
        d.main_menu_button("quit")
    d.key_then_wait(pattern(markers.CONFIRM_POPUP_CANCELLED, title=QUIT_TITLE), "Escape")
    d.expect_no_new(pattern(markers.CLOSING_APP), 2.0)
    d.key_then_wait(ANY_NODE_SELECTED, "Down")  # still alive and answering


SAVE_TIMEOUT = 10.0


def _saved_node(boot: AppBoot) -> list[str]:
    settings = json.loads((boot.scratch / "barks-reader.json").read_text(encoding="utf-8"))
    return settings["AAA_Settings"]["last_selected_node"]


def _wait_for_saved_node(boot: AppBoot, want: str) -> None:
    """Poll the profile's json until the app has saved `want` as the selected node.

    The save follows the "Closing app" line as the app shuts down; there is no
    later line to wait on, so this is the one wait in the suite on a file.
    """
    deadline = time.monotonic() + SAVE_TIMEOUT
    while time.monotonic() < deadline:
        saved = _saved_node(boot)
        if saved and saved[0] == want:
            return
        time.sleep(0.25)
    msg = f"the app never saved {want!r} as its selected node; the json has {_saved_node(boot)}"
    raise AssertionError(msg)


def test_quit_confirmed_closes_the_app_and_saves_the_selected_node(boot: AppBoot) -> None:
    """A confirmed quit closes the app, which writes the node it was on for the next start."""
    d = boot(nodes.GHOST_OF_THE_GROTTO)
    d.key_then_wait(ANY_NODE_SELECTED, "Down")  # so the saved node differs from the booted one
    moved_to = d.current_node()
    assert moved_to != nodes.GHOST_OF_THE_GROTTO[0]
    assert _saved_node(boot)[0] == nodes.GHOST_OF_THE_GROTTO[0], "the boot node is what is saved"

    with d.expect(pattern(markers.CONFIRM_POPUP_OPENED, title=QUIT_TITLE)):
        d.main_menu_button("quit")
    with (
        d.expect(pattern(markers.CONFIRM_POPUP_CONFIRMED, title=QUIT_TITLE)),
        d.expect(pattern(markers.CLOSING_APP)),
    ):
        d.key("Return")
    _wait_for_saved_node(boot, moved_to)
