"""The action bar's dots menu: Settings, How To, and the quit fence."""

from __future__ import annotations

import json
import re
import time
from typing import TYPE_CHECKING

import pytest
from barks_gui import harness, nodes, taps
from barks_gui.logs import last_field
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern
from barks_reader.core.main_layout import MATCH_THE_SCREEN, SINGLE_PAGE, TWO_PAGE_SPREAD
from barks_reader.core.reader_palette import DEFAULT_THEME_NAME, THEME_NAMES
from barks_reader.core.screen_transition import SCREEN_TRANSITION_ENV_VAR

if TYPE_CHECKING:
    from pathlib import Path

    from barks_gui.harness import AppBoot
    from gui_driver import Driver

# The dropdown opens focused on its first entry: Settings, How To, Update Data, About.
HOW_TO_DOWNS = 1
ABOUT_DOWNS = 3
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


SETTINGS_X_FOCUSED = "Nav focus on SettingsCloseButton"


def _close_settings(d: Driver) -> None:
    """Escape lands on the settings' X, as in the readers; Return there closes."""
    d.key_then_wait(SETTINGS_X_FOCUSED, "Escape")
    d.key_then_wait(markers.SETTINGS_CLOSED, "Return")


def test_dots_menu_opens_settings_and_their_close_returns_to_the_menu_button(
    boot: AppBoot,
) -> None:
    """Escape lands on the X, and Return there closes.

    Escape on the X goes back to the list; the close puts the keys back on the Menu
    button that opened the settings.
    """
    d = boot(nodes.THE_STORIES)
    _open_dots_menu(d, downs=0)
    _pick(d, markers.DISPLAY_SETTINGS)
    d.key_then_wait(SETTINGS_X_FOCUSED, "Escape")
    d.key_then_wait(f"{d.FOCUS_MOVED} Setting", "Escape")  # back on the list's item
    d.key_then_wait(SETTINGS_X_FOCUSED, "Escape")
    with d.expect(f'{d.FOCUS_MOVED} ChromeBarButton "Menu"'), d.expect(d.MENU_ENTERED):
        d.key_then_wait(markers.SETTINGS_CLOSED, "Return")


# The settings panel lists its fields in reader_settings._FIELDS order, and its
# keyboard focus starts on the first; this many Downs reach the fun-view title
# toggle. A miscount lands on another field, which the config-change line's key
# then reports.
FUN_VIEW_TITLE_SETTING = "show_fun_view_title_info"
DOWNS_TO_FUN_VIEW_TITLE = 8
FLIPPED = {"0": "1", "1": "0"}


def _toggle_fun_view_title(d: Driver, value: str) -> None:
    """From the tree, open Settings, toggle the fun-view title switch to `value`, close."""
    _open_dots_menu(d, downs=0)
    _pick(d, markers.DISPLAY_SETTINGS)
    d.move_focus(*["Down"] * DOWNS_TO_FUN_VIEW_TITLE)
    d.key_then_wait(
        pattern(markers.CONFIG_CHANGE, key=FUN_VIEW_TITLE_SETTING, value=value), "Return"
    )
    _close_settings(d)


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


# The options settings the harness pins in the ini (barks_gui.harness.INI_DEFAULTS).
LAYOUT_SETTING = "main_screen_layout"
LOG_LEVEL_SETTING = "log_level"


def test_opening_the_settings_leaves_the_options_settings_as_the_ini_had_them(
    boot: AppBoot,
) -> None:
    """Opening and closing the panel changes nothing: an options row reads the ini's value.

    Building the panel once wrote each options setting's default into the ini (the
    layout went back to Match the screen, the log level to INFO, 2026-10-29).
    """
    ini = boot.scratch / "barks-reader.ini"
    d = boot(nodes.THE_STORIES)
    layout = harness.read_ini_value(ini, LAYOUT_SETTING)
    log_level = harness.read_ini_value(ini, LOG_LEVEL_SETTING)
    # An explicit layout: the harness pins a single page, the matrix's spread variant forces
    # the spread.
    assert layout in harness.LAYOUT_MODE_FOR_SETTING

    _open_dots_menu(d, downs=0)
    _pick(d, markers.DISPLAY_SETTINGS)
    _close_settings(d)

    assert harness.read_ini_value(ini, LAYOUT_SETTING) == layout
    assert harness.read_ini_value(ini, LOG_LEVEL_SETTING) == log_level


def test_matching_the_screen_boots_on_the_layout_its_shape_gives(boot: AppBoot) -> None:
    """The layout a new profile has, which the harness's pin hides from every other test.

    The run's screen decides what to expect: the default nested screen is portrait (the
    single page), the 1080p stage's and a desktop's monitor landscape (the spread).
    """
    d = boot(nodes.THE_STORIES, ini={LAYOUT_SETTING: MATCH_THE_SCREEN})
    screen = last_field(d, markers.MAIN_LAYOUT_MODE, "screen")
    width, height = (int(side) for side in screen.split("x"))
    expected = harness.layout_matching_the_screen(width, height)
    if expected is None:
        pytest.skip(f"on a {screen} screen the action bar's height decides the layout")

    assert last_field(d, markers.MAIN_LAYOUT_MODE, "mode") == expected
    assert last_field(d, markers.MAIN_LAYOUT_MODE, "reason") == "boot"


def test_dots_menu_how_to_opens_the_document_reader(boot: AppBoot) -> None:
    d = boot(nodes.THE_STORIES)
    _open_dots_menu(d, downs=HOW_TO_DOWNS)
    with d.expect(DOCUMENT_ENTERED):  # the transition has finished before any key is sent
        _pick(d, pattern(markers.SWITCHING_TO_DOCUMENT_READER))
    # Escape opens the document reader's menu on its only button, Close.
    d.key_then_wait(d.MENU_ENTERED, "Escape")
    d.key_then_wait(pattern(markers.MAIN_SCREEN_ACTIVE), "Return")


def test_dots_menu_about_opens_and_its_close_returns_to_the_menu_button(boot: AppBoot) -> None:
    """Escape lands on the About box's X, and Return there closes it.

    The close puts the keys back on the Menu button, as the settings' does.
    """
    d = boot(nodes.THE_STORIES)
    _open_dots_menu(d, downs=ABOUT_DOWNS)
    _pick(d, markers.ABOUT_BOX_OPENED)
    d.key_then_wait(f'{d.FOCUS_MOVED} Button "X"', "Escape")  # on the box's X first
    with d.expect(f'{d.FOCUS_MOVED} ChromeBarButton "Menu"'), d.expect(d.MENU_ENTERED):
        d.key_then_wait(markers.ABOUT_BOX_DISMISSED, "Return")
    d.key_then_wait(d.MENU_EXITED, "Escape")
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
    _close_settings(d)


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
    _close_settings(d)
    assert harness.read_ini_value(ini, "fanta_dir").strip() == before


# The options and key-capture settings, by their place in the panel (reader_settings order;
# a field added or removed above one moves it, as Double Page Mode's removal did on
# 2026-10-30 and the read cue's arrival on 2026-11-11).
DOWNS_TO_COLOR_THEME = 6
DOWNS_TO_WINDOW_HEIGHT = 11
DOWNS_TO_ALT_ESCAPE = 15
KEY_TAB_CODE = 9


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
    _close_settings(d)
    assert harness.read_ini_value(ini, "color_theme").strip() == THEME_NAMES[picked]


DOWNS_TO_LAYOUT = 1
# The two explicit layouts; the options run Match the screen, Single page, Two-page spread.
EXPLICIT_LAYOUTS = (SINGLE_PAGE, TWO_PAGE_SPREAD)


def _set_layout_from(d: Driver, current: str) -> str:
    """From the tree, set the main screen's layout to the other one; return its name.

    The window takes the new layout's shape, and the screen must take the window's.
    """
    step, picked = ("Down", TWO_PAGE_SPREAD) if current == SINGLE_PAGE else ("Up", SINGLE_PAGE)
    _open_dots_menu(d, downs=0)
    _pick(d, markers.DISPLAY_SETTINGS)
    d.move_focus(*["Down"] * DOWNS_TO_LAYOUT)
    d.key_then_wait(d.FOCUS_MOVED, "Return")  # the options, the current one focused
    d.move_focus(step)
    with d.expect(pattern(markers.WINDOW_RESIZED)):
        d.key_then_wait(
            pattern(markers.SETTING_OPTION_SET, key=LAYOUT_SETTING, value=picked), "Return"
        )
    d.settle()
    _close_settings(d)
    d.settle()
    return picked


_NUMBER = re.compile(r"(\d+)")
_WINDOW_RESIZED_RE = re.compile(pattern(markers.WINDOW_RESIZED, width=_NUMBER, height=_NUMBER))
_LAYOUT_SIZE_RE = re.compile(
    pattern(markers.MAIN_LAYOUT_SIZE, width=_NUMBER, height=_NUMBER, mode="windowed")
)


def _last_size(d: Driver, regex: re.Pattern[str]) -> tuple[int, int]:
    """Return the width and height of the last line of `regex` the app logged."""
    found = regex.findall(d.log_path.read_text(encoding="utf-8", errors="replace"))
    assert found, f"the app has not logged /{regex.pattern}/"
    width, height = found[-1]
    return int(width), int(height)


def _assert_the_screen_fills_the_window(d: Driver, layout: str) -> None:
    window = _last_size(d, _WINDOW_RESIZED_RE)
    screen = _last_size(d, _LAYOUT_SIZE_RE)
    assert screen == window, (
        f"on {layout!r} the main screen is laid out {screen[0]}x{screen[1]}"
        f" in a {window[0]}x{window[1]} window"
    )


# The transition that showed the defect: it moves the two screens themselves, so the main
# screen is still laid out in the window when the comic's fullscreen resizes it. The
# app's other pick, at random, is often one that draws the screens through a shader.
A_TRANSITION_THAT_MOVES_ITS_SCREENS = "CardTransition"
READER_FULLSCREEN = pattern(markers.ENTERED_FULLSCREEN, screen="ComicBookReaderScreen")
READER_WINDOWED = pattern(markers.ENTERED_WINDOWED, screen="ComicBookReaderScreen")
FULLSCREEN_TIMEOUT = 20


def test_a_layout_changed_after_a_comic_read_fullscreen_fills_its_window(
    boot: AppBoot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A comic opened fullscreen and closed, then the other layout: the screen fits the window.

    The comic's fullscreen fixed the main screen's size under it, and its exit left
    that behind: the layout's new window then held a screen still laid out for the
    old one, half of it out of sight (seen on Windows, 2026-11-11). And back again:
    the screen must follow the window each time. The window itself need not come
    back at its boot size: a change of layout keeps its height where the screen has
    the room, and on a screen too narrow for the spread it cannot.
    """
    boot.expect_boot_size = False
    monkeypatch.setenv(SCREEN_TRANSITION_ENV_VAR, A_TRANSITION_THAT_MOVES_ITS_SCREENS)
    ini = boot.scratch / "barks-reader.ini"
    d = boot(
        nodes.GHOST_OF_THE_GROTTO, cues=nodes.NO_CUES, ini={"goto_fullscreen_on_comic_read": "1"}
    )
    layout = harness.read_ini_value(ini, LAYOUT_SETTING)
    assert layout in EXPLICIT_LAYOUTS, f"the run's layout is {layout!r}"

    with d.expect(READER_FULLSCREEN, FULLSCREEN_TIMEOUT):
        d.open_selected_story()
    d.settle()
    with d.expect(READER_WINDOWED, FULLSCREEN_TIMEOUT):
        d.close_reader()
    d.settle()
    # The close puts the keys back on the title's Read button: Escape gives the tree them.
    d.key_then_wait(d.EXITED_BOTTOM_FOCUS, "Escape")

    other = _set_layout_from(d, layout)
    _assert_the_screen_fills_the_window(d, other)
    assert _set_layout_from(d, other) == layout
    _assert_the_screen_fills_the_window(d, layout)


VIRTUAL_KEYBOARD_SETTING = "use_virtual_keyboard"
DOWNS_TO_VIRTUAL_KEYBOARD = 16
# The search box logs how it was pressed only while the on-screen keyboard is allowed.
BOX_PRESSED = f"{pattern(markers.TEXT_INPUT_CLICKED)}|{pattern(markers.TEXT_INPUT_TOUCHED)}"


def _set_virtual_keyboard(d: Driver, value: str) -> None:
    """From the tree, open Settings, flip the virtual keyboard switch to `value`, close."""
    _open_dots_menu(d, downs=0)
    _pick(d, markers.DISPLAY_SETTINGS)
    d.move_focus(*["Down"] * DOWNS_TO_VIRTUAL_KEYBOARD)
    d.key_then_wait(
        pattern(markers.CONFIG_CHANGE, key=VIRTUAL_KEYBOARD_SETTING, value=value), "Return"
    )
    _close_settings(d)


def test_the_virtual_keyboard_turned_on_in_the_settings_works_without_a_restart(
    boot: AppBoot,
) -> None:
    """The search box picks its keyboard by how it is pressed as soon as the switch is on."""
    d = boot(nodes.TITLE_SEARCH, ini={VIRTUAL_KEYBOARD_SETTING: "0"})
    _set_virtual_keyboard(d, "1")
    taps.tap_then_wait(d, BOX_PRESSED, kv_id="title_search_input")
    if taps.touch_mode():
        d.settle()
        _, shown = taps.targets(d)
        assert [t for t in shown if t.kind == "VKeyboard"], "a touch shows the keyboard"


def test_the_virtual_keyboard_turned_off_in_the_settings_stops_without_a_restart(
    boot: AppBoot,
) -> None:
    """Off, the search box takes a press as any other box, and no keyboard is on show."""
    d = boot(nodes.TITLE_SEARCH, ini={VIRTUAL_KEYBOARD_SETTING: "1"})
    _set_virtual_keyboard(d, "0")
    taps.tap(d, kv_id="title_search_input")
    d.expect_no_new(BOX_PRESSED)
    _, shown = taps.targets(d)
    assert not [t for t in shown if t.kind == "VKeyboard"], "turned off, no keyboard shows"


def test_a_number_setting_opens_its_entry_box_and_escape_leaves_it_unchanged(
    boot: AppBoot,
) -> None:
    """Return opens the number's box on the shared frame; Escape closes it, the ini as it was.

    Escape is the frame's even while the box has the keyboard: had it gone to the box,
    the next Escape would close the popup and the settings' X would never be focused.
    """
    ini = boot.scratch / "barks-reader.ini"
    d = boot(nodes.THE_STORIES)
    before = harness.read_ini_value(ini, "main_window_height")
    _open_dots_menu(d, downs=0)
    _pick(d, markers.DISPLAY_SETTINGS)
    d.move_focus(*["Down"] * DOWNS_TO_WINDOW_HEIGHT)
    opened = pattern(markers.SETTING_NUMBER_OPENED, key="main_window_height")
    d.key_then_wait(opened, "Return")
    d.key("Escape")
    _close_settings(d)
    assert harness.read_ini_value(ini, "main_window_height") == before


def test_the_settings_list_stops_at_its_top(boot: AppBoot) -> None:
    """The panel opens on its first item; Up there stays, as the app's lists do."""
    d = boot(nodes.THE_STORIES)
    _open_dots_menu(d, downs=0)
    _pick(d, markers.DISPLAY_SETTINGS)
    d.key("Up")
    d.expect_no_new(d.FOCUS_MOVED)
    _close_settings(d)


def test_a_captured_alternate_escape_key_then_acts_as_escape(boot: AppBoot) -> None:
    """Escape cancels the capture; Tab is captured, and then Tab closes the settings.

    The remote's own keys are not captured: Left focuses Clear and Return clears the key.
    """
    ini = boot.scratch / "barks-reader.ini"
    d = boot(nodes.THE_STORIES)
    _open_dots_menu(d, downs=0)
    _pick(d, markers.DISPLAY_SETTINGS)
    d.move_focus(*["Down"] * DOWNS_TO_ALT_ESCAPE)
    capture_opened = pattern(markers.ALT_ESCAPE_CAPTURE_OPENED)
    d.key_then_wait(capture_opened, "Return")
    d.key_then_wait(markers.ALT_ESCAPE_CAPTURE_CANCELLED, "Escape")
    d.key_then_wait(capture_opened, "Return")
    d.key_then_wait(
        pattern(markers.ALT_ESCAPE_CAPTURED, keycode=KEY_TAB_CODE),
        "Tab",  # desktop key: the key captured; the remote's six each have work of their own
    )
    d.key_then_wait(SETTINGS_X_FOCUSED, "Tab")  # desktop key: the new Escape, just captured
    d.key_then_wait(markers.SETTINGS_CLOSED, "Return")
    assert harness.read_ini_value(ini, "alt_escape_key").strip() == str(KEY_TAB_CODE)

    _open_dots_menu(d, downs=0)
    _pick(d, markers.DISPLAY_SETTINGS)
    d.move_focus(*["Down"] * DOWNS_TO_ALT_ESCAPE)
    d.key_then_wait(capture_opened, "Return")
    d.move_focus("Left")  # Cancel is focused to start; Clear is a Left away
    d.key_then_wait(markers.ALT_ESCAPE_CLEARED, "Return")
    assert harness.read_ini_value(ini, "alt_escape_key").strip() == "0"


MAX_CHOOSER_STEPS = 8


def _chooser_tree(boot: AppBoot, tmp_path: Path) -> Path:
    """Make root/{alpha,beta,library}, library the real archives; return the library."""
    real = harness.expand_path(
        harness.read_ini_value(boot.scratch / "barks-reader.ini", "fanta_dir")
    )
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
    _close_settings(d)
    assert harness.read_ini_value(boot.scratch / "barks-reader.ini", "fanta_dir").strip() == str(
        library
    )
