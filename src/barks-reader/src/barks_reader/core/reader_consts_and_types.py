from __future__ import annotations

RAW_ACTION_BAR_SIZE_Y = 45

# Shared action-bar look, used by the kv bars (ui/action_bar.kv) and passed to
# the okf viewer's TopBarSpec (core/wiki_integration.py) so all four bars match.
ACTION_BAR_BG_COLOR = (0.12, 0.12, 0.12, 1)  # standard ActionBar background color
ACTION_BAR_SEPARATOR_COLOR = (0.3, 0.3, 0.3, 1)
ACTION_BAR_TITLE_COLOR = (0.0, 1.0, 0.0, 1.0)
RAW_ACTION_BAR_ICON_WIDTH = 70  # dp, the icon-container width
# Width of the separator fencing the Quit button off from the working buttons:
# the 1dp line sits centered, leaving ~8dp of dead space on each side.
RAW_QUIT_FENCE_WIDTH = 17  # dp

APP_TITLE = "The Compleat Barks Disney Reader"
FANTAGRAPHICS_BARKS_LIBRARY = "Fantagraphics Complete Carl Barks Disney Library"

LONG_PATH_SETTING = "longpath"
OPTIONS_SETTING = "options"
ALT_ESCAPE_KEY_SETTING = "altescapekey"
NO_OVERRIDES_SUFFIX = "-no-overrides"
COMIC_BEGIN_PAGE = "0"
FIRST_BODY_PAGE = "1"
CLOSE_TO_ZERO = 0.001

# fmt: off
INTRO_NODE_TEXT = "Introduction"
INTRO_COMPLEAT_BARKS_READER_TEXT = "The Compleat Barks Disney Reader"
INTRO_DON_AULT_FANTA_INTRO_TEXT = "Don Ault: Fantagraphics Introduction"
THE_STORIES_NODE_TEXT = "The Stories"
CHRONOLOGICAL_NODE_TEXT = "Chronological"
SERIES_NODE_TEXT = "Series"
CATEGORIES_NODE_TEXT = "Categories"
SEARCH_NODE_TEXT = "Search"
TITLE_SEARCH_NODE_TEXT = "Titles"
TAG_SEARCH_NODE_TEXT = "Tags"
WORD_SEARCH_NODE_TEXT = "Words"
APPENDIX_NODE_TEXT = "Appendix"
APPENDIX_RICH_TOMMASO_ON_COLORING_BARKS_TEXT = "Rich Tommaso: On Coloring Barks"
APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_TEXT = "Don Ault: Life Among the Ducks"
APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_TEXT = "Maggie Thompson: Comics Readers Find..."  # noqa: E501
APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_TEXT = "George Lucas: An Appreciation"
APPENDIX_CENSORSHIP_FIXES_NODE_TEXT = "Censorship Fixes and Other Changes"
APPENDIX_STATISTICS_NODE_TEXT = "Statistics"
INDEX_NODE_TEXT = "Indexes"
INDEX_MAIN_TEXT = "Main Index"
INDEX_SPEECH_TEXT = "Speech Bubble Index"
INDEX_SPEECH_WORDS_TEXT = "Words"
INDEX_NAMES_TEXT = "Names"
INDEX_LOCATIONS_TEXT = "Locations"
INDEX_WIKI_TEXT = "Carl Barks Wiki"
# fmt: on

CHRONO_YEAR_RANGES = [
    (1942, 1946),
    (1947, 1950),
    (1951, 1954),
    (1955, 1957),
    (1958, 1961),
    (1962, 1971),
]
CS_YEAR_RANGES = [
    (1942, 1946),
    (1947, 1950),
    (1951, 1954),
    (1955, 1957),
    (1958, 1961),
    (1962, 1966),
]
US_YEAR_RANGES = [
    (1951, 1954),
    (1955, 1957),
    (1958, 1961),
    (1962, 1966),
]
