from __future__ import annotations

import zipfile
from pathlib import Path

from comic_utils.comic_consts import ROMAN_NUMERALS

RAW_ACTION_BAR_SIZE_Y = 45

APP_TITLE = "The Compleat Barks Disney Reader"

LONG_PATH_SETTING = "longpath"
NO_OVERRIDES_SUFFIX = "-no-overrides"
COMIC_PAGE_ONE = ROMAN_NUMERALS[1]
CLOSE_TO_ZERO = 0.001
PanelPath = Path | zipfile.Path

INTRO_NODE_TEXT = "Introduction"
INTRO_COMPLEAT_BARKS_READER_TEXT = "Introduction to the Compleat Barks Reader"
INTRO_DON_AULT_FANTA_INTRO_TEXT = "Don Ault: Fantagraphics Introduction"
THE_STORIES_NODE_TEXT = "The Stories"
CHRONOLOGICAL_NODE_TEXT = "Chronological"
SERIES_NODE_TEXT = "Series"
CATEGORIES_NODE_TEXT = "Categories"
SEARCH_NODE_TEXT = "Search"
APPENDIX_NODE_TEXT = "Appendix"
APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_TEXT = "Don Ault: Life Among the Ducks"
APPENDIX_RICH_TOMASSO_ON_COLORING_BARKS_TEXT = "Rich Tomasso: On Coloring Barks"
APPENDIX_CENSORSHIP_FIXES_NODE_TEXT = "Censorship Fixes and Other Changes"
INDEX_NODE_TEXT = "Index"

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
]
US_YEAR_RANGES = [
    (1951, 1954),
    (1955, 1957),
    (1958, 1961),
]
