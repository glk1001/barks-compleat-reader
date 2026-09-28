"""The action bar's dots menu: Settings, How To, and the quit fence."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from barks_gui import harness, nodes
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern
from barks_reader.core.reader_palette import DEFAULT_THEME_NAME, THEME_NAMES

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


FOLDER_CHOOSER_CLOSED = pattern(markers.FOLDER_CHOOSER_CLOSED)


def test_a_folder_setting_opens_its_chooser_and_escape_closes_it(boot: AppBoot) -> None:
    """The first setting is the library folder; Return opens its chooser, Escape closes it."""
    d = boot(nodes.THE_STORIES)
    _open_dots_menu(d, downs=0)
    _pick(d, markers.DISPLAY_SETTINGS)
    d.key_then_wait(pattern(markers.FOLDER_CHOOSER_OPENED), "Return")
    d.key_then_wait(FOLDER_CHOOSER_CLOSED, "Escape")
    d.key_then_wait(markers.SETTINGS_CLOSED, "Escape")


def test_enter_in_a_folder_chooser_keeps_the_path_it_shows(boot: AppBoot) -> None:
    """Enter selects the path in the box - on opening, the setting's own - and closes."""
    ini = boot.scratch / "barks-reader.ini"
    d = boot(nodes.THE_STORIES)
    before = harness.read_ini_value(ini, "fanta_dir").strip()
    _open_dots_menu(d, downs=0)
    _pick(d, markers.DISPLAY_SETTINGS)
    d.key_then_wait(pattern(markers.FOLDER_CHOOSER_OPENED), "Return")
    with d.expect(FOLDER_CHOOSER_CLOSED):
        d.key_then_wait(pattern(markers.FOLDER_CHOOSER_SELECTED), "Return")
    d.key_then_wait(markers.SETTINGS_CLOSED, "Escape")
    assert harness.read_ini_value(ini, "fanta_dir").strip() == before


# The options and key-capture settings, by their place in the panel (reader_settings order).
DOWNS_TO_COLOR_THEME = 4
DOWNS_TO_ALT_ESCAPE = 13
KEY_LEFT_CODE = 276


def test_an_options_setting_takes_a_new_value_by_keyboard(boot: AppBoot) -> None:
    """Return opens the theme's options on the current one; a step and Return picks its neighbour.

    Down, unless the current theme is the last (the matrix's four-color-theme):
    below the last option is the list's Cancel button.
    """
    ini = boot.scratch / "barks-reader.ini"
    d = boot(nodes.THE_STORIES)
    before = harness.read_ini_value(ini, "color_theme").strip() or DEFAULT_THEME_NAME
    index = THEME_NAMES.index(before)
    step, picked = ("Up", index - 1) if index == len(THEME_NAMES) - 1 else ("Down", index + 1)
    _open_dots_menu(d, downs=0)
    _pick(d, markers.DISPLAY_SETTINGS)
    d.move_focus(*["Down"] * DOWNS_TO_COLOR_THEME)
    d.key_then_wait(d.FOCUS_MOVED, "Return")  # the options, the current one focused
    d.move_focus(step)
    set_to = pattern(markers.SETTING_OPTION_SET, key="color_theme", value=THEME_NAMES[picked])
    d.key_then_wait(set_to, "Return")
    d.key_then_wait(markers.SETTINGS_CLOSED, "Escape")
    assert harness.read_ini_value(ini, "color_theme").strip() == THEME_NAMES[picked]


def test_a_captured_alternate_escape_key_then_acts_as_escape(boot: AppBoot) -> None:
    """Escape cancels the capture; Left is captured, and then Left closes the settings."""
    ini = boot.scratch / "barks-reader.ini"
    d = boot(nodes.THE_STORIES)
    _open_dots_menu(d, downs=0)
    _pick(d, markers.DISPLAY_SETTINGS)
    d.move_focus(*["Down"] * DOWNS_TO_ALT_ESCAPE)
    capture_opened = pattern(markers.ALT_ESCAPE_CAPTURE_OPENED)
    d.key_then_wait(capture_opened, "Return")
    d.key_then_wait(markers.ALT_ESCAPE_CAPTURE_CANCELLED, "Escape")
    d.key_then_wait(capture_opened, "Return")
    d.key_then_wait(pattern(markers.ALT_ESCAPE_CAPTURED, keycode=KEY_LEFT_CODE), "Left")
    d.key_then_wait(markers.SETTINGS_CLOSED, "Left")  # the new Escape
    assert harness.read_ini_value(ini, "alt_escape_key").strip() == str(KEY_LEFT_CODE)


MAX_CHOOSER_STEPS = 8


def _chooser_tree(boot: AppBoot, tmp_path: Path) -> Path:
    """Make root/{alpha,beta,library}, library the real archives; return the library."""
    real = Path(
        os.path.expandvars(harness.read_ini_value(boot.scratch / "barks-reader.ini", "fanta_dir"))
    ).expanduser()
    if not real.is_dir():
        pytest.skip(f"no Fantagraphics library at {real}")
    root = tmp_path / "root"
    for name in ("alpha", "beta"):
        (root / name).mkdir(parents=True)
    library = root / "library"
    library.mkdir()
    for archive in real.iterdir():
        (library / archive.name).symlink_to(archive)
    return library


def _at(folder: Path) -> str:
    return pattern(markers.FOLDER_CHOOSER_AT, path=str(folder))


def test_a_folder_chooser_is_browsed_by_remote(boot: AppBoot, tmp_path: Path) -> None:
    """Up/Down move through the folders, Right opens one, Left goes up, Return keeps one."""
    library = _chooser_tree(boot, tmp_path)
    root = library.parent
    d = boot(nodes.THE_STORIES, ini={"fanta_dir": str(library), "use_prebuilt_comics": "0"})
    _open_dots_menu(d, downs=0)
    _pick(d, markers.DISPLAY_SETTINGS)
    d.key_then_wait(pattern(markers.FOLDER_CHOOSER_OPENED), "Return")
    d.settle()  # the chooser highlights the setting's own folder once its list is in
    d.key_then_wait(_at(root / "beta"), "Up")  # the list runs ../, alpha, beta, library
    d.key_then_wait(pattern(markers.FOLDER_CHOOSER_IN, path=str(root / "beta")), "Right")
    d.key_then_wait(pattern(markers.FOLDER_CHOOSER_IN, path=str(root)), "Left")
    for _ in range(MAX_CHOOSER_STEPS):
        d.key_then_wait(pattern(markers.FOLDER_CHOOSER_AT), "Down")
        if str(library) in d.last_line(pattern(markers.FOLDER_CHOOSER_AT)):
            break
    with d.expect(FOLDER_CHOOSER_CLOSED):
        d.key_then_wait(pattern(markers.FOLDER_CHOOSER_SELECTED, path=str(library)), "Return")
    d.key_then_wait(markers.SETTINGS_CLOSED, "Escape")
    assert harness.read_ini_value(boot.scratch / "barks-reader.ini", "fanta_dir").strip() == str(
        library
    )
