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
from itertools import takewhile
from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.fanta_comics_info import get_fanta_info
from barks_gui import expected, nodes, search, taps
from barks_gui.logs import fields_of, last_field
from barks_reader.core import log_markers as markers
from barks_reader.core.index_text import indexable_title
from barks_reader.core.log_markers import pattern

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from barks_gui.harness import AppBoot
    from barks_reader.core.tap_targets import TapTarget
    from gui_driver import Driver

SHOWED_PAGE = pattern(markers.SHOWED_PAGE)
READER = "ComicBookReaderScreen"
FULLSCREEN_TIMEOUT = 20
# Long enough for a doubled tap's second press to have turned a second page.
NO_DOUBLE_TAP_SECS = 1.5
ANY_FUN_TITLE = pattern(markers.FUN_VIEW_TITLE_SET)
CHANGE_PICS_TRIES = 6
# Every title the reader can go to, as the main index writes it: to tell a title's
# entry from a tag's. A title with no Fantagraphics volume (Bubbleweight Champ, Beach
# Boy) is indexed too, but tapping it opens the volume-not-available popup instead:
# which entry is first on screen depends on the window, and on a Windows laptop's it
# was one of those.
GOTO_TITLES = frozenset(
    indexable_title(title) for title in Titles if get_fanta_info(title) is not None
)
DOCUMENT_ENTERED = pattern(markers.SCREEN_ENTERED, name="document_reader")
ANY_REVEAL = pattern(markers.TREE_CHILDREN_REVEALED)
# The pinner leaves a drift under half a pixel alone, which a row's rounded top can
# show as one.
ROW_DRIFT_PX = 1
# Long enough for an expansion's scroll correction, a few frames, to have been logged.
NO_REVEAL_SECS = 1.0
# How many of a branch's rows an expansion at the tree's bottom glides into view.
REVEALED_ROWS = 3


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


def _tree_rows(d: Driver) -> list[TapTarget]:
    """Return the tree's rows on screen, top to bottom, cut ones too."""
    _, shown = taps.targets(d)
    return sorted((t for t in shown if t.kind.endswith("TreeViewNode")), key=lambda t: t.top)


def _row_named(rows: list[TapTarget], name: str) -> int:
    return next(i for i, row in enumerate(rows) if row.text == name)


def test_a_branch_tapped_at_the_bottom_glides_up_to_show_its_first_rows(boot: AppBoot) -> None:
    """A branch whose first child would open out of sight glides up to show three.

    The branch is the lowest row wholly on screen: its first child would open under
    the tree's edge, where a cut row shows or, the edge at the branch's very bottom,
    nothing does. It stays on screen itself. Rows always follow a place's, so a place
    as the lowest whole row means the tree goes on below the edge. Places, not Themes:
    the 17 themes fit a 1360 px window, and the lowest row was then Search, a top-level
    node whose opening has nothing to glide to (greg-dell, 2026-10-17).
    """
    d = _boot(boot, nodes.PLACES, cues=nodes.NO_CUES)
    rows = _tree_rows(d)
    places = rows[_row_named(rows, "Places")]
    lowest = next(row for row in reversed(rows) if row.whole)
    assert lowest.left > places.left, f"the places fit the window: {lowest.describe()} is lowest"
    branch = lowest.text

    with d.expect(pattern(markers.TREE_CHILDREN_REVEALED, name=branch)):
        taps.tap(d, text=branch)

    rows = _tree_rows(d)
    i = _row_named(rows, branch)
    assert rows[i].whole, f"{rows[i].describe()} glided off the screen"
    children = list(takewhile(lambda row: row.left > rows[i].left, rows[i + 1 :]))
    assert children, f"no row of {branch} shows"
    cut = [row.describe() for row in children[:REVEALED_ROWS] if not row.whole]
    assert not cut, f"the first rows of {branch} are cut: {cut}"


def test_a_branch_whose_first_row_shows_stays_put_opened_and_shut(boot: AppBoot) -> None:
    """A branch with room under it for a row neither moves to open nor to shut.

    Shutting one was what moved it: Kivy keeps the scroll as a share of the tree's
    height, so a shorter tree shifted every row until the collapse was pinned too.
    """
    d = _boot(boot, nodes.THEMES, cues=nodes.NO_CUES)
    rows = _tree_rows(d)
    themes = _row_named(rows, "Themes")
    # The first theme: its first child opens on the row below, in plain view.
    branch, below = rows[themes + 1], rows[themes + 2]
    assert below.whole, f"no room shows under {branch.describe()}"

    taps.tap_then_wait(d, pattern(markers.NODE_EXPANDED, name=branch.text), text=branch.text)
    d.expect_no_new(ANY_REVEAL, NO_REVEAL_SECS)
    rows = _tree_rows(d)
    opened = rows[_row_named(rows, branch.text)]
    assert abs(opened.top - branch.top) <= ROW_DRIFT_PX, "opening it moved it"

    taps.tap_then_wait(d, pattern(markers.NODE_COLLAPSED, name=branch.text), text=branch.text)
    rows = _tree_rows(d)
    shut = rows[_row_named(rows, branch.text)]
    assert abs(shut.top - branch.top) <= ROW_DRIFT_PX, "shutting it moved it"


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


def test_on_the_spread_a_middle_tap_zooms_a_tier_and_another_brings_the_pair_back(
    boot: AppBoot,
) -> None:
    """The middle third zooms the tier under it, view-only: the history does not move."""
    d = _boot(boot, nodes.THE_STORIES, ini={"main_screen_layout": "Two-page spread"})
    for _ in range(CHANGE_PICS_TRIES):
        d.settle()
        if last_field(d, markers.FUN_VIEW_STACKED, "state") == "True":
            break
        taps.tap_then_wait(d, pattern(markers.FUN_IMAGE_LOADED), kv_id="change_pics_button")
    else:
        pytest.fail("no stacked pair after Change Pics")
    titles_shown = d.match_count(ANY_FUN_TITLE)
    zoom = markers.FUN_VIEW_ZOOM
    taps.tap_then_wait(
        d, pattern(zoom, tier="lower"), kind="FunImageViewScreen", text="lower middle"
    )
    taps.tap_then_wait(d, pattern(zoom, tier="off"), kind="FunImageViewScreen", text="middle")
    taps.tap_then_wait(
        d, pattern(zoom, tier="upper"), kind="FunImageViewScreen", text="upper middle"
    )
    assert d.match_count(ANY_FUN_TITLE) == titles_shown, "a zoom moved the history"


def test_on_the_spread_a_tree_row_beside_the_fun_view_takes_its_tap(boot: AppBoot) -> None:
    """The fun view stands beside the tree on the spread and must not take the tree's taps.

    Only the top row was tappable: the rest lay level with the view's margins, which
    bound a press by its height alone.
    """
    d = _boot(boot, nodes.THE_STORIES, ini={"main_screen_layout": "Two-page spread"})
    taps.tap_then_wait(
        d,
        pattern(markers.NEW_SELECTED_NODE, name="Search"),
        kind="MainTreeViewNode",
        text="Search",
    )
    assert not fields_of(d, markers.LEFT_MARGIN_PRESSED, "x"), "the fun view took the tap"


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


def test_a_menu_opened_by_tap_is_taken_by_the_keys(boot: AppBoot) -> None:
    """The first key lands the ring on the menu's first item; Escape there closes it.

    Before, Escape entered menu mode behind the open menu, and Enter on the Menu
    button there opened it a second time, which Kivy refused.
    """
    d = _boot(boot, nodes.THE_STORIES)
    taps.tap(d, kv_id="menu_button")
    d.settle()
    d.key_then_wait(f'{d.FOCUS_MOVED} Button "Settings"', "Down")
    d.key_then_wait(f'{d.FOCUS_MOVED} Button "How To"', "Down")
    d.key_then_wait(markers.MENU_EXITED, "Escape")  # the menu closes, and menu mode with it
    assert not d.in_menu_mode()


def test_a_menu_opened_by_tap_closes_on_escape(boot: AppBoot) -> None:
    d = _boot(boot, nodes.THE_STORIES)
    taps.tap(d, kv_id="menu_button")
    d.settle()
    d.key_then_wait(markers.DROPDOWN_DISMISSED, "Escape")
    assert not d.in_menu_mode()
    d.key_then_wait(markers.MENU_ENTERED, "Escape")  # the keys are the tree's again


def test_a_word_statistics_list_opened_by_tap_is_taken_by_the_keys(boot: AppBoot) -> None:
    """The first key lands the ring on the list's first row; Escape there closes it."""
    d = _boot(boot, nodes.STATISTICS)
    taps.tap(d, kind="StatMenuButton", text="Word Statistics")
    d.settle()
    with d.expect(markers.STATISTICS_ENTERED_DROPDOWN), d.expect(markers.OPEN_LIST_ADOPTED):
        d.key_then_wait(f'{d.FOCUS_MOVED} Button "Most Frequent"', "Down")
    with d.expect(markers.STATISTICS_EXITED_DROPDOWN):
        d.key_then_wait(d.DROPDOWN_DISMISSED, "Escape")
    d.key_then_wait(f"{d.FOCUS_MOVED} StatMenuButton", "Left")  # the keys stay on the tabs


def test_a_word_statistics_list_opened_by_tap_closes_on_escape(boot: AppBoot) -> None:
    d = _boot(boot, nodes.STATISTICS)
    taps.tap(d, kind="StatMenuButton", text="Word Statistics")
    d.settle()
    d.key_then_wait(d.DROPDOWN_DISMISSED, "Escape")
    d.key_then_wait(markers.MENU_ENTERED, "Escape")  # the keys are the tree's again


def test_quit_by_tap_asks_first_and_cancel_stays(boot: AppBoot) -> None:
    d = _boot(boot, nodes.THE_STORIES)
    with (
        d.expect(markers.QUIT_ASKING),
        d.expect(pattern(markers.CONFIRM_POPUP_OPENED, title="Quit")),
    ):
        taps.tap(d, kv_id="quit_button")
    taps.tap_then_wait(
        d, pattern(markers.CONFIRM_POPUP_CANCELLED, title="Quit"), kind="Button", text="Stay"
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
        (t for t in shown if t.kind == "IndexItemButton" and t.whole and t.text in GOTO_TITLES),
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


# ------------------------------------------------------------ the search chips --

SAID_BY_QUERY = "money"
SAID_BY_SPEAKER = "Scrooge"  # its stored name is its shown name, and not first in the list


def test_a_tapped_word_stays_marked_and_its_speaker_list_is_picked_by_tap(boot: AppBoot) -> None:
    """A word tapped stays marked as the one picked; its Said by list opens and picks by tap."""
    words = expected.words_matching(SAID_BY_QUERY)
    word = words[0]
    speakers = expected.speaker_list(word)
    assert speakers.index(SAID_BY_SPEAKER) > 0
    d = _boot(boot, nodes.WORD_SEARCH)
    search.type_query(d, SAID_BY_QUERY)
    # Out of the box: in touch mode its on-screen keyboard covers the lower rows.
    d.key_then_wait(d.FOCUS_MOVED, "Down")
    d.settle()

    taps.tap_then_wait(
        d, pattern(markers.WORD_SELECTED_CHIP, word=word), kind="_SearchResultButton", text=word
    )
    d.settle()  # past the press's lapse, which once painted over the mark
    _, shown = taps.targets(d)
    marked = {t.text for t in shown if t.kind == "_SearchResultButton" and t.selected}
    assert marked == {word}, f"the tapped word alone is marked, not {sorted(marked)}"

    taps.tap_then_wait(
        d,
        pattern(markers.SPEAKER_LIST_OPENED, count=len(speakers)),
        kind="_SaidByChipButton",
        text="Said by: anyone",
    )
    d.settle()
    taps.tap_then_wait(
        d,
        pattern(markers.SPEAKER_FILTER_SET, speaker=SAID_BY_SPEAKER),
        kind="_SaidByItem",
        text=SAID_BY_SPEAKER,
    )
    d.settle()
    _, shown = taps.targets(d)
    taps.find(shown, kind="_SaidByChipButton", text=f"Said by: {SAID_BY_SPEAKER}")
    assert not [t for t in shown if t.kind == "_SaidByItem"], "the list closes on a pick"


NESTING_GROUP = "chemistry"
SUBGROUP = "chemical names"


def test_a_speaker_list_opened_by_tap_is_taken_by_the_keys(boot: AppBoot) -> None:
    """The first key lands the ring on the speaker picked now; Escape there closes the list."""
    words = expected.words_matching(SAID_BY_QUERY)
    word = words[0]
    speakers = expected.speaker_list(word)
    d = _boot(boot, nodes.WORD_SEARCH)
    search.type_query(d, SAID_BY_QUERY)
    d.key_then_wait(d.FOCUS_MOVED, "Down")  # out of the box
    d.settle()
    taps.tap_then_wait(
        d, pattern(markers.WORD_SELECTED_CHIP, word=word), kind="_SearchResultButton", text=word
    )
    d.settle()
    taps.tap_then_wait(
        d,
        pattern(markers.SPEAKER_LIST_OPENED, count=len(speakers)),
        kind="_SaidByChipButton",
        text="Said by: anyone",
    )
    d.settle()
    with d.expect(markers.OPEN_LIST_ADOPTED):
        d.key_then_wait(f'{d.FOCUS_MOVED} _SaidByItem "anyone"', "Down")
    d.key_then_wait(f'{d.FOCUS_MOVED} _SaidByItem "(?!anyone")', "Down")  # the first speaker
    with d.expect(d.DROPDOWN_DISMISSED):
        d.key_then_wait(f'{d.FOCUS_MOVED} _SaidByChipButton "Said by: anyone"', "Escape")


def test_an_open_tag_group_closes_and_opens_by_tap(boot: AppBoot) -> None:
    """A tap on the open group closes it, another opens it; a subgroup opens in place."""
    members = expected.group_members(NESTING_GROUP)
    d = _boot(boot, nodes.TAG_SEARCH)
    with d.expect(pattern(markers.TAG_SELECTED_TAG, tag=NESTING_GROUP)):  # picked as typed
        search.type_query(d, NESTING_GROUP)
    d.key_then_wait(d.FOCUS_MOVED, "Down")  # out of the box
    d.settle()

    taps.tap_then_wait(
        d,
        pattern(markers.TAG_GROUP_CLOSED, group=NESTING_GROUP),
        kind="_TagChipButton",
        text=NESTING_GROUP,
    )
    d.settle()
    _, shown = taps.targets(d)
    assert not {t.text for t in shown if t.kind == "_TagChipButton"} & set(members)
    taps.tap_then_wait(
        d,
        pattern(markers.TAG_SELECTED_TAG, tag=NESTING_GROUP),
        kind="_TagChipButton",
        text=NESTING_GROUP,
    )
    d.settle()
    taps.tap_then_wait(
        d,
        pattern(markers.TAG_GROUP_OPENED, group=SUBGROUP),
        kind="_TagChipButton",
        text=SUBGROUP,
    )
    d.settle()
    _, shown = taps.targets(d)
    taps.find(shown, kind="_TagChipButton", text=expected.group_members(SUBGROUP)[0])


CHIP_WORD_QUERY = "gold"


def test_search_chips_are_picked_by_tap(boot: AppBoot) -> None:
    """A word's +, the picked-words chips and an era chip each act on a tap, by what they show."""
    d = _boot(boot, nodes.WORD_SEARCH)
    search.type_query(d, CHIP_WORD_QUERY)
    # Out of the box: in touch mode its on-screen keyboard covers the lower rows.
    d.key_then_wait(d.FOCUS_MOVED, "Down")
    d.settle()

    # Every word's + shows the same "+": which word it picked is read back from the line.
    taps.tap_then_wait(
        d, pattern(markers.WORD_BASKET_CHANGED, count=1), kind="_PlusButton", text="+"
    )
    word = last_field(d, markers.WORD_BASKET_CHANGED, "words")
    assert word in expected.words_matching(CHIP_WORD_QUERY)
    taps.tap_then_wait(
        d, pattern(markers.WORD_BASKET_MODE, mode="ANY"), kind="_BasketChipButton", text="ALL"
    )
    taps.tap_then_wait(
        d, pattern(markers.ERA_FILTER_SET, era="1951-54"), kind="_EraChipButton", text="1951-54"
    )
    taps.tap_then_wait(
        d,
        pattern(markers.WORD_BASKET_CHANGED, count=0),
        kind="_BasketChipButton",
        text=f"{word} \u00d7",  # as listed: spaces run together
    )


def test_the_keyboard_focus_follows_a_tap_in_the_index(boot: AppBoot) -> None:
    """A letter tapped takes the keyboard focus: the next Down goes on from it."""
    d = _boot(boot, nodes.MAIN_INDEX)
    d.key_then_wait(markers.INDEX_ENTERED_NAV, "Return")  # the ring sits on "A"
    taps.tap_then_wait(d, pattern(markers.INDEX_LETTER_POPULATED, letter="C"), text="C")
    d.settle()
    d.key_then_wait(pattern(markers.INDEX_LETTER_POPULATED, letter="D"), "Down")


def test_an_item_tapped_with_the_keys_active_is_pressed_once(boot: AppBoot) -> None:
    """A title's entry tapped while the ring is in the index goes to the title, pressed once.

    The keys press the tapped item again on the focus's behalf; the second press must
    let itself by rather than take the focus a second time.
    """
    d = _boot(boot, nodes.MAIN_INDEX)
    d.key_then_wait(markers.INDEX_ENTERED_NAV, "Return")  # the ring sits on "A"
    taps.tap_then_wait(d, pattern(markers.INDEX_LETTER_POPULATED, letter="B"), text="B")
    d.settle()
    _, shown = taps.targets(d)
    item = next(
        (t for t in shown if t.kind == "IndexItemButton" and t.whole and t.text in GOTO_TITLES),
        None,
    )
    assert item is not None, "no title's entry wholly on screen under 'B'"
    # The tree selects the title only once its animated expand ends, a second or more after
    # the goto, so wait for that rather than a settle.
    with (
        d.expect(pattern(markers.GOTO_TITLE)),
        d.expect(pattern(markers.NEW_SELECTED_NODE)),
        d.expect(pattern(markers.INDEX_ITEM_PRESSED)),
    ):
        taps.tap(d, kind="IndexItemButton", text=item.text)
    d.settle()
    pressed = fields_of(d, markers.INDEX_ITEM_PRESSED, "item")
    assert len(pressed) == 1, pressed
    assert f"display_text='{item.text}'" in pressed[0], (pressed[0], item.text)
    assert d.current_node() == last_field(d, markers.GOTO_TITLE, "name")


def test_the_keyboard_focus_follows_a_tap_on_a_tag_chip(boot: AppBoot) -> None:
    """A member chip tapped takes the keyboard focus: the next Down goes on from it."""
    members = expected.group_members(NESTING_GROUP)
    d = _boot(boot, nodes.TAG_SEARCH)
    with d.expect(pattern(markers.TAG_SELECTED_TAG, tag=NESTING_GROUP)):
        search.type_query(d, NESTING_GROUP)
    d.key_then_wait(d.FOCUS_MOVED, "Down")  # out of the box, onto the group chip
    taps.tap_then_wait(
        d,
        pattern(markers.TAG_SELECTED_MEMBER, member=members[0]),
        kind="_TagChipButton",
        text=members[0],
    )
    d.settle()
    d.key_then_wait(f'{d.FOCUS_MOVED} _TagChipButton "{members[1]}"', "Down")
