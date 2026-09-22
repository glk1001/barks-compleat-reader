"""The log lines that mark the app's user-visible transitions, written in one place.

The app's log is the oracle the GUI path tests wait on (``scripts/gui_driver.py``,
``src/barks-reader/tests/gui/``): a test presses a key and blocks until the line
that transition logs appears. That makes each line's text part of a screen's
contract, and this module is the one place the text is written. The app logs a
marker through ``.format`` (or as-is for the ones with no slots); a test waits on
it through `pattern`, which turns the same template into a regex. Renaming a line
therefore changes both sides or neither, and a marker unit test (``loguru_sink``)
proves the call site still fires it.

Templates use named ``str.format`` fields. A field's value goes into the app's
line verbatim, so a template must not itself contain braces other than its fields.
Stdlib only: this is ``core``, imported by the UI and by tests that must not pull
in Kivy.
"""

from __future__ import annotations

import re
from typing import Final

# ---------------------------------------------------------------- the tree --
NEW_SELECTED_NODE: Final = 'New selected node: "{name}". Previous node: "{previous}".'
NODE_EXPANDED: Final = "Node expanded: '{name}'."
NODE_COLLAPSED: Final = "Node collapsed: '{name}'."
NODE_COLLAPSED_NO_STATE_CHANGE: Final = "Node collapsed but not allowing state change: '{name}'."
GOING_BACK_TO_NODE: Final = 'Going back to previous node "{name}".'
REPOPULATED_NODE: Final = "Repopulated '{name}' with {count} children."
ARTICLE_NODE_PRESSED: Final = "Article node pressed: Reading '{name}'."
UPDATING_BACKGROUND_VIEW_STATE: Final = "Updating background view state to {state}."

# ------------------------------------------------------------------ keys --
# Every key press the window receives, before any handler can consume it. The
# GUI harness counts these against the keys its probe injected: a key from
# elsewhere (the host keyboard, while a visible test window has focus) then
# shows up in the failure report as what it is.
KEY_PRESSED: Final = "Key pressed: {key} ({name})."

# --------------------------------------------- the main screen and its bar --
GO_BACK_SELECTED: Final = "'Go back' menu item selected."
MENU_ENTERED: Final = "Entered menu mode."
MENU_EXITED: Final = "Exited menu mode."
NAV_FOCUS_PREFIX: Final = "Nav focus on"
NAV_FOCUS: Final = f"{NAV_FOCUS_PREFIX} {{widget}}."
DROPDOWN_DISMISSED: Final = "Dropdown dismissed."
ENTERED_BOTTOM_FOCUS: Final = "Entered bottom focus region."
ENTERED_BOTTOM_FOCUS_FOR_SEARCH: Final = "Entered bottom focus region at search screen's request."
ENTERED_BOTTOM_FOCUS_AT_PORTAL: Final = "Entered bottom focus region at the title portal."
EXITED_BOTTOM_FOCUS: Final = "Exited bottom focus region."
ENTERED_TOP_GOTO_ARROW: Final = "Entered top-view goto arrow focus."
TOP_GOTO_ARROW_INACTIVE: Final = "Top-view goto arrow inactive: Up stays on the first node."
GOTO_TITLE: Final = 'Goto title: "{name}", "{filename}".'
QUIT_ASKING: Final = "Quit requested: asking for confirmation."
QUIT_NO_CONFIRMATION: Final = "Quit requested: no confirmation needed."
CLOSING_APP: Final = "Closing app..."
DISPLAY_SETTINGS: Final = "Display settings object."
SETTINGS_CLOSED: Final = "Settings closed."
CONFIG_CHANGE: Final = "Config change: section = '{section}', key = '{key}', value = '{value}'."
ABOUT_BOX_OPENED: Final = "About box opened."
ABOUT_BOX_DISMISSED: Final = "About box dismissed."
WIKI_PAGE_BUTTON_PRESSED: Final = "Wiki page button pressed."
ENTERED_FULLSCREEN: Final = "Entered fullscreen mode on {screen}."
ENTERED_WINDOWED: Final = "Entered windowed mode on {screen}."
# Every window resize event the app receives: the GUI harness compares the last
# one a test leaves against the first, since a shrink after a reader close or a
# fullscreen round trip is a defect whatever the test asserted.
WINDOW_RESIZED: Final = "Main window resize event: width, height = {width},{height}."
MAIN_WINDOW_SHOWN: Final = "Main window shown."  # the first moment a key can reach it

# ---------------------------------------------------------------- popups --
CONFIRM_POPUP_OPENED: Final = 'Confirm popup opened: "{title}".'
CONFIRM_POPUP_CONFIRMED: Final = 'Confirm popup "{title}": confirmed.'
CONFIRM_POPUP_CANCELLED: Final = 'Confirm popup "{title}": cancelled.'
CONFIRM_POPUP_CLOSED: Final = 'Confirm popup "{title}": closed.'

# -------------------------------------------------------- screen switches --
SCREEN_ENTERED: Final = "Screen '{name}' entered."
SCREEN_LEFT: Final = "Screen '{name}' left."
MAIN_SCREEN_ACTIVE: Final = "Main screen is active (from {origin})."
FROM_COMIC_READER: Final = "comic reader"
FROM_DOCUMENT_READER: Final = "document reader"
FROM_BY_THE_NUMBERS: Final = "By the Numbers"
FROM_WIKI_READER: Final = "wiki reader"
SWITCHING_TO_DOCUMENT_READER: Final = 'Switching to document reader for "{title}"...'
DOCUMENT_READER_ACTIVE: Final = 'Document reader screen is active: "{title}".'
SWITCHING_TO_BY_THE_NUMBERS: Final = "Switching to the By the Numbers page..."
BY_THE_NUMBERS_ACTIVE: Final = "By the Numbers screen is active."
WIKI_READER_ACTIVE: Final = "Wiki reader screen is active."

# --------------------------------------------------- the document reader --
DOCUMENT_OPENED: Final = 'Document reader opened "{title}" with {pages} pages.'
DOCUMENT_PAGE: Final = 'Document page {page}/{pages}: "{filename}".'
DOCUMENT_CLOSING: Final = "Document reader closing."
CORPUS_STATS_OPENED: Final = "CorpusStats: opened."
CORPUS_STATS_CLOSING: Final = "CorpusStats: closing."

# ---------------------------------------------------------- the title view --
TITLE_VIEW_ENTERED_NAV: Final = "BottomTitleViewScreen: entered nav focus."
TITLE_VIEW_ENTERED_AT_PORTAL: Final = "BottomTitleViewScreen: entered nav focus at portal."
TITLE_VIEW_EXITED_NAV: Final = "BottomTitleViewScreen: exited nav focus."
TITLE_FADE_STARTED: Final = "Title view fade started: {duration}s."
TITLE_FADE_FINISHED: Final = "Title view fade finished."
USE_OVERRIDES_CHANGED: Final = "Use overrides checkbox changed: use_overrides = {value}."
GOTO_PAGE_CHECKBOX_TOGGLED: Final = "Goto page checkbox toggled: active = {value}."

# -------------------------------------------------------- the comic sources --
# Which source the pages come from, logged once at boot (use_prebuilt_comics).
USING_PREBUILT_ARCHIVES: Final = "Using prebuilt archives. No extra data to initialize."
USING_VOLUME_ARCHIVES: Final = "Using Fantagraphics volume archives. Now loading volume info..."
VOLUMES_LOADED: Final = "Finished loading all volumes in {elapsed}."

# ------------------------------------------------------- what a read persists --
# One per read that saves progress (articles do not): the harness checks the
# profile's last-read cue and reading history against these at every teardown.
LAST_READ_PAGE_SAVED: Final = '"{title}": Saved last read page "{page}".'
HISTORY_OPEN_RECORDED: Final = 'History: Recorded open of "{title}".'
HISTORY_CLOSE_RECORDED: Final = 'History: Recorded close of "{title}".'

# --------------------------------------------------------- the comic reader --
ALL_IMAGES_LOADED: Final = "All images loaded in {elapsed}: current page index = {index}."
SHOWED_PAGE: Final = "Showed page {index} in {elapsed}."
ALREADY_ON_FIRST_PAGE: Final = "Already on the first page: current index = {index}."
ALREADY_ON_LAST_PAGE: Final = "Already on the last page: current index = {index}."
GOTO_START_PAGE: Final = "Goto start page: requested index = {index}."
GOTO_LAST_PAGE: Final = "Last page: requested index = {index}."
DOUBLE_PAGE_TOGGLED: Final = "Double page mode toggled: {mode}."
DOUBLE_PAGE_IGNORED: Final = "Double page toggle ignored: single-page collection."
GOTO_PAGE_DROPDOWN_OPENED: Final = "Goto page dropdown opened."
GOTO_PAGE_SELECTED: Final = 'Goto page selected: "{page}".'

# ------------------------------------------------------------ the fun view --
FUN_OPTIONS_PRESSED: Final = "Fun view options button pressed. New state is '{state}'."
FUN_VIEW_TITLE_SET: Final = 'Set fun view title to "{title}".'
FUN_IMAGE_LOADED: Final = 'Set last loaded fun image file "{filename} and title: "{title}".'

# --------------------------------------------------------------- history --
HISTORY_ENTERED_NAV: Final = "HistoryScreen: entered nav focus."
HISTORY_SELECTED_VIEW: Final = "History: selected '{view}' view."
HISTORY_BUILT_VIEW: Final = "History: built '{view}' view with {rows} rows."
HISTORY_MOUNTED_CACHED_VIEW: Final = "History: mounted cached '{view}' view with {rows} rows."
HISTORY_DELETED_EVENT: Final = 'History: deleted event "{event_id}".'
HISTORY_DELETED_TITLE: Final = 'History: deleted title "{title}".'
HISTORY_CLEARED: Final = "History: cleared."

# --------------------------------------------------------------- indexes --
INDEX_ENTERED_NAV: Final = "IndexScreen: entered nav focus."
INDEX_BUILD_COMPLETE: Final = "Index build complete (in {elapsed})."
INDEX_LETTER_POPULATED: Final = "Populated index page for letter '{letter}' in {elapsed}."
INDEX_LETTER_EMPTY: Final = "Populated index page for letter '{letter}': no items."
INDEX_ITEM_PRESSED: Final = "Index item pressed: {item}"
INDEX_TERM_HANDLED: Final = 'Handling index term: "{term}".'
INDEX_PREFIX_PRESSED: Final = "Pressed prefix button: '{prefix}."
SHOW_BUBBLES_FOR_INDEX_TERMS: Final = (
    'Show speech bubbles for: "{title}" and index terms "{terms}".'
)
TITLE_FROM_BUBBLE_BROWSER: Final = 'Handling title from speech bubble browser: "{title}" - {page}.'
BUBBLES_POPUP_OPENED: Final = "Speech bubbles popup opened."
BUBBLES_POPUP_DISMISSED: Final = "Speech bubbles popup dismissed."

# ---------------------------------------------------------------- search --
SEARCH_MODE_SET: Final = "SearchScreen mode set to '{mode}'."
SEARCH_ENTERED_NAV: Final = "SearchScreen: entered nav focus."
SEARCH_EXITED_NAV: Final = "SearchScreen: exited nav focus."
SEARCH_BOX_FOCUS: Final = "SearchScreen: {mode} search box {state}."
SEARCH_SELECTED_TITLE: Final = 'Search: selected "{title}".'
SEARCH_TITLE_RESULTS: Final = "Search results: {count} titles for '{text}'."
SEARCH_TAG_RESULTS: Final = "Search results: {count} tags for '{text}'."
SEARCH_WORD_RESULTS: Final = "Search results: {count} word rows."
WORD_SEARCH_MATCHED: Final = 'Word search: "{text}" matched {count} words.'
SEARCH_CLEARED: Final = "Search cleared: {mode}."
TAG_SELECTED_TAG: Final = 'Tag search: selected tag "{tag}".'
TAG_SELECTED_MEMBER: Final = 'Tag search: selected member "{member}".'
WORD_SELECTED_CHIP: Final = 'Word search: selected chip "{word}".'
SHOW_BUBBLES_FOR_SEARCH: Final = 'Show speech bubbles for: "{title}" and search "{text}".'
WORD_BUBBLE_PRESS: Final = 'Word search bubble press: "{title}" page {page}.'

# ------------------------------------------------------------ statistics --
STATISTICS_LOADING_IMAGE: Final = 'Statistics: loading image "{path}".'
STATISTICS_ENTERED_NAV: Final = "StatisticsScreen: entered nav focus."
STATISTICS_EXITED_NAV: Final = "StatisticsScreen: exited nav focus."
STATISTICS_ENTERED_DROPDOWN: Final = "StatisticsScreen: entered dropdown nav."
STATISTICS_EXITED_DROPDOWN: Final = "StatisticsScreen: exited dropdown nav."

# ------------------------------------------------------------------ wiki --
WIKI_GOTO_TITLE: Final = 'Wiki goto title: "{name}".'


_FIELD_RE = re.compile(r"\{(\w+)\}")


def pattern(template: str, **fields: object) -> str:
    r"""Turn a marker template into a regex that matches the line the app logs.

    Literal text is escaped. A field given here is escaped too, unless it is a
    compiled regex, whose pattern is spliced in as written; a field left out
    matches anything. So ``pattern(SHOWED_PAGE, index=3)`` matches "Showed page 3
    in 12ms." but not "Showed page 34 in 12ms.", and ``pattern(NEW_SELECTED_NODE,
    name=re.compile(r"19\\d\\d-19\\d\\d"))`` matches any year-range node.

    Args:
        template: A marker from this module.
        **fields: Values for some or all of its fields.

    Returns:
        A regex for ``re.search`` (or ``grep -E``) over the app log.

    Raises:
        KeyError: If a field named here is not in the template.

    """
    names = set(_FIELD_RE.findall(template))
    unknown = set(fields) - names
    if unknown:
        msg = f"{sorted(unknown)} not in template {template!r}"
        raise KeyError(msg)

    # split() alternates literal text and field name, starting with a literal.
    out: list[str] = []
    for i, part in enumerate(_FIELD_RE.split(template)):
        if i % 2 == 0:
            out.append(re.escape(part))
        elif part not in fields:
            out.append(".*")
        else:
            value = fields[part]
            out.append(value.pattern if isinstance(value, re.Pattern) else re.escape(str(value)))
    return "".join(out)


def capture(template: str, field: str, **fields: object) -> str:
    """Turn a marker template into a regex that captures one of its fields.

    Like `pattern`, with `field` becoming the named group ``(?P<field>.*)``, so a
    test can read a value the app logged: ``re.search(capture(SHOWED_PAGE,
    "index"), line)["index"]``. The other fields match as `pattern` matches them.

    Args:
        template: A marker from this module.
        field: The field to capture.
        **fields: Values for some of the other fields.

    Returns:
        A regex for ``re.search`` over one log line.

    Raises:
        KeyError: If `field` (or a field named here) is not in the template.

    """
    if field not in set(_FIELD_RE.findall(template)):
        msg = f"{field!r} not in template {template!r}"
        raise KeyError(msg)
    return pattern(template, **fields, **{field: re.compile(f"(?P<{field}>.*)")})
