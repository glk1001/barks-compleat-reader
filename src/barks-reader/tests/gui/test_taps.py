"""Taps: the reader driven by pointer presses, as a touchscreen laptop's user drives it.

Every other GUI test presses the remote's keys; these tap, through the app's own
list of what is tappable where (``barks_gui.taps``). A tap is a click, which is
what a touch reaches the app as on Linux (SDL turns a finger into a pointer
press). With the runner's ``--touch`` it is a real touch as well, on a virtual
touchscreen, and each test boots with the virtual keyboard setting on: that is
what makes the app read touchscreens itself, and so what can double a tap or
choose the virtual keyboard for the search box.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_gui import nodes, taps
from barks_gui.logs import fields_of, last_field
from barks_reader.core import log_markers as markers
from barks_reader.core.index_text import indexable_title
from barks_reader.core.log_markers import pattern

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from barks_gui.harness import AppBoot
    from gui_driver import Driver

SHOWED_PAGE = pattern(markers.SHOWED_PAGE)
READER = "ComicBookReaderScreen"
FULLSCREEN_TIMEOUT = 20
# Long enough for a doubled tap's second press to have turned a second page.
NO_DOUBLE_TAP_SECS = 1.5
ANY_FUN_TITLE = pattern(markers.FUN_VIEW_TITLE_SET)
# Every title as the main index writes it, to tell a title's entry from a tag's.
INDEXED_TITLES = frozenset(indexable_title(title) for title in Titles)
DOCUMENT_ENTERED = pattern(markers.SCREEN_ENTERED, name="document_reader")


def _boot(
    boot: AppBoot,
    node: Sequence[str],
    *,
    ini: Mapping[str, str] | None = None,
    cues: Mapping[str, dict[str, int | str] | None] | None = None,
) -> Driver:
    """Boot for a tap test: in touch mode, with the app reading the touchscreen."""
    settings = dict(ini or {})
    if taps.touch_mode():
        settings.setdefault("use_virtual_keyboard", "1")
    return boot(node, ini=settings or None, cues=cues)


def _pages(d: Driver) -> list[int]:
    return [int(i) for i in fields_of(d, markers.SHOWED_PAGE, "index")]


def _open_the_ghost_of_the_grotto(boot: AppBoot) -> Driver:
    d = _boot(boot, nodes.GHOST_OF_THE_GROTTO, cues=nodes.NO_CUES)
    d.open_selected_story()
    d.wait_for(SHOWED_PAGE)
    return d


# ------------------------------------------------------------ the tree --


def test_tapping_tree_nodes_opens_a_branch_and_selects_a_title(boot: AppBoot) -> None:
    """A tap on a branch toggles it, shut and open; a tap on a title selects it.

    Booting expands the whole chain, so both branches start open, and a branch
    keeps its children's state while shut: reopening Chronological shows
    1947-1950 still open.
    """
    d = _boot(boot, nodes.CHRONO_RANGE, cues=nodes.NO_CUES)
    for name in ("Chronological", "1947-1950"):
        taps.tap_then_wait(d, pattern(markers.NODE_COLLAPSED, name=name), text=name)
        taps.tap_then_wait(d, pattern(markers.NODE_EXPANDED, name=name), text=name)
    # A title fully on screen, whichever that is: how many rows show is the screen's.
    _, shown = taps.targets(d)
    title = taps.find(shown, kind="TitleTreeViewNode")
    assert title.whole, f"no title wholly on screen: {title.describe()}"
    with d.expect(pattern(markers.NEW_SELECTED_NODE, name=title.text)):
        taps.tap(d, kind="TitleTreeViewNode", text=title.text)
    assert d.current_node() == title.text


# ------------------------------------------------------ the comic reader --


def test_margin_taps_turn_the_page_once_each(boot: AppBoot) -> None:
    """The right margin turns forward and the left back, one page per tap - never two."""
    d = _open_the_ghost_of_the_grotto(boot)
    first = _pages(d)[-1]
    with d.expect(pattern(markers.RIGHT_MARGIN_PRESSED)), d.expect(SHOWED_PAGE):
        taps.tap(d, kind="ComicBookReader", text="right margin")
    d.expect_no_new(SHOWED_PAGE, NO_DOUBLE_TAP_SECS)
    forward = _pages(d)[-1]
    assert forward > first
    with d.expect(pattern(markers.LEFT_MARGIN_PRESSED)), d.expect(SHOWED_PAGE):
        taps.tap(d, kind="ComicBookReader", text="left margin")
    d.expect_no_new(SHOWED_PAGE, NO_DOUBLE_TAP_SECS)
    assert _pages(d)[-1] == first
    d.close_reader()


def test_a_tap_leaves_keyboard_menu_mode(boot: AppBoot) -> None:
    """Escape puts the reader's bar in menu mode; any tap takes it out again."""
    d = _open_the_ghost_of_the_grotto(boot)
    d.key_then_wait(markers.MENU_ENTERED, "Escape")
    with d.expect(markers.MENU_EXITED), d.expect(SHOWED_PAGE):
        taps.tap(d, kind="ComicBookReader", text="right margin")
    d.close_reader()


def test_in_fullscreen_a_top_tap_shows_the_hidden_bar(boot: AppBoot) -> None:
    """Tap Fullscreen, and the bar hides; a top-margin tap brings it back to tap again."""
    d = _open_the_ghost_of_the_grotto(boot)
    taps.tap_then_wait(
        d,
        pattern(markers.ENTERED_FULLSCREEN, screen=READER),
        kv_id="fullscreen_button",
        timeout=FULLSCREEN_TIMEOUT,
    )
    d.settle()
    _, shown = taps.targets(d)
    assert not [t for t in shown if t.id == "fullscreen_button"], "the bar hides in fullscreen"
    try:
        taps.tap_then_wait(
            d, markers.ACTION_BAR_SHOWN_ON_TOP_MARGIN, kind="ComicBookReader", text="top margin"
        )
    except taps.TapOutsideWindowError as exc:
        # No window manager on the nested display: fullscreen draws a screen-sized
        # frame into the windowed-size window, and here the margin is off its edge.
        # Back to windowed (by the bar's key path) first, as the teardown expects.
        with d.expect(pattern(markers.ENTERED_WINDOWED, screen=READER), FULLSCREEN_TIMEOUT):
            d.press_menu_button("fullscreen")
        d.settle()
        d.close_reader()
        pytest.skip(f"fullscreen is not real on this nested screen: {exc}")
    taps.tap_then_wait(
        d,
        pattern(markers.ENTERED_WINDOWED, screen=READER),
        kv_id="fullscreen_button",
        timeout=FULLSCREEN_TIMEOUT,
    )
    d.settle()
    d.close_reader()


# ------------------------------------------------- the fun view, documents --


def test_fun_view_margin_taps_step_through_shown_images(boot: AppBoot) -> None:
    """Change Pics by tap gives the view a second image; its margins step back and on."""
    d = _boot(boot, nodes.THE_STORIES)
    taps.tap_then_wait(d, pattern(markers.FUN_IMAGE_LOADED), kv_id="change_pics_button")
    taps.tap_then_wait(d, ANY_FUN_TITLE, kind="FunImageViewScreen", text="left margin")
    taps.tap_then_wait(d, ANY_FUN_TITLE, kind="FunImageViewScreen", text="right margin")
    titles = fields_of(d, markers.FUN_VIEW_TITLE_SET, "title")
    first, changed, back, forward = titles[-4:]
    assert (back, forward) == (first, changed), titles


def test_document_halves_turn_its_pages(boot: AppBoot) -> None:
    """Tap a document's node to open it; its right half turns on, its left half back."""
    d = _boot(boot, nodes.APPENDIX)
    with (
        d.expect(pattern(markers.DOCUMENT_READER_ACTIVE)),
        d.expect(pattern(markers.DOCUMENT_PAGE, page=1)),
        d.expect(DOCUMENT_ENTERED),
    ):
        taps.tap(d, text=nodes.CENSORSHIP_DOCUMENT)
    taps.tap_then_wait(
        d, pattern(markers.DOCUMENT_PAGE, page=2), kind="DocumentReaderScreen", text="right half"
    )
    taps.tap_then_wait(
        d, pattern(markers.DOCUMENT_PAGE, page=1), kind="DocumentReaderScreen", text="left half"
    )
    assert fields_of(d, markers.DOCUMENT_PAGE, "page") == ["1", "2", "1"]
    with d.expect(markers.DOCUMENT_CLOSING):
        taps.tap(d, text="Close")


# ------------------------------------------------ menus and popups by tap --


def test_the_menu_opens_about_and_its_button_closes_it(boot: AppBoot) -> None:
    d = _boot(boot, nodes.THE_STORIES)
    taps.tap(d, kv_id="menu_button")
    taps.tap_then_wait(d, markers.ABOUT_BOX_OPENED, text="About")
    taps.tap_then_wait(d, markers.ABOUT_BOX_DISMISSED, text="X")


def test_quit_by_tap_asks_first_and_cancel_stays(boot: AppBoot) -> None:
    d = _boot(boot, nodes.THE_STORIES)
    with (
        d.expect(markers.QUIT_ASKING),
        d.expect(pattern(markers.CONFIRM_POPUP_OPENED, title="Quit")),
    ):
        taps.tap(d, kv_id="quit_button")
    taps.tap_then_wait(
        d, pattern(markers.CONFIRM_POPUP_CANCELLED, title="Quit"), kv_id="cancel_button"
    )
    d.expect_no_new(pattern(markers.CLOSING_APP), 2.0)


# ---------------------------------------------------------------- indexes --


def test_main_index_letter_and_item_taps(boot: AppBoot) -> None:
    """Tap a letter to show its titles, then a title to go to it in the tree."""
    d = _boot(boot, nodes.MAIN_INDEX)
    d.wait_for(pattern(markers.INDEX_LETTER_POPULATED, letter="A"))
    taps.tap_then_wait(d, pattern(markers.INDEX_LETTER_POPULATED, letter="B"), text="B")
    # A title's entry, not a tag's (a tag opens its titles instead): a title as
    # the index writes one, wholly on screen.
    _, shown = taps.targets(d)
    item = next(
        (t for t in shown if t.kind == "IndexItemButton" and t.whole and t.text in INDEXED_TITLES),
        None,
    )
    assert item is not None, "no title's entry wholly on screen under 'B'"
    with (
        d.expect(pattern(markers.GOTO_TITLE)),
        d.expect(pattern(markers.NEW_SELECTED_NODE)),
        d.expect(pattern(markers.INDEX_ITEM_PRESSED)),
    ):
        taps.tap(d, kind="IndexItemButton", text=item.text)
    # The item tapped is the one pressed, and under 'B' it is a title starting with B.
    pressed = last_field(d, markers.INDEX_ITEM_PRESSED, "item")
    found = re.search(r"display_text='([^']*)'", pressed)
    assert found, pressed
    assert found[1] == item.text, (found[1], item.text)
    assert found[1].upper().startswith("B")
    assert d.current_node() == last_field(d, markers.GOTO_TITLE, "name")


def test_speech_index_prefix_term_and_bubbles_taps(boot: AppBoot) -> None:
    """Tap a prefix, a term, a title's speech button; the bubbles popup closes by tap."""
    d = _boot(boot, nodes.SPEECH_INDEX)
    d.wait_for(pattern(markers.INDEX_LETTER_POPULATED, letter="A"))
    taps.tap_then_wait(d, pattern(markers.INDEX_LETTER_POPULATED, letter="B"), text="B")
    prefix = taps.tap_then_wait(d, pattern(markers.INDEX_PREFIX_PRESSED), kind="IndexPrefixButton")
    term = taps.tap_then_wait(d, pattern(markers.INDEX_TERM_HANDLED), kind="IndexItemButton")
    handled = last_field(d, markers.INDEX_TERM_HANDLED, "term")
    assert handled == term.text, (handled, term.text)
    assert handled.lower().startswith(prefix.text[0].lower()), (prefix.text, handled)
    with (
        d.expect(pattern(markers.SHOW_BUBBLES_FOR_INDEX_TERMS)),
        d.expect(markers.BUBBLES_POPUP_OPENED),
    ):
        taps.tap(d, kind="TitleShowSpeechButton")
    with d.expect(markers.BUBBLES_POPUP_DISMISSED):
        taps.tap_outside(d, kind="SpeechBubblesPopup")


# ------------------------------------------------------------- the search box --


def test_the_search_box_picks_its_keyboard_by_how_it_was_pressed(boot: AppBoot) -> None:
    """With the virtual keyboard on: a click keeps the system keyboard, a touch shows it."""
    d = _boot(boot, nodes.TITLE_SEARCH, ini={"use_virtual_keyboard": "1"})
    chose = markers.TEXT_INPUT_TOUCHED if taps.touch_mode() else markers.TEXT_INPUT_CLICKED
    taps.tap_then_wait(d, pattern(chose), kv_id="title_search_input")
    d.settle()
    _, shown = taps.targets(d)
    keyboards = [t for t in shown if t.kind == "VKeyboard"]
    if taps.touch_mode():
        assert keyboards, "a touch on the search box shows the virtual keyboard"
    else:
        assert not keyboards, "a click on the search box keeps to the system keyboard"
