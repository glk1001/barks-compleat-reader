"""The `ViewStates` enum — Kivy-free, shared between core navigation and UI.

The enum identifies every top-level reader view. Domain-driven lookup tables
(article → title, etc.) live alongside `NavigationModel` in
`navigation_model.py`.
"""

from __future__ import annotations

from enum import IntEnum, auto


class ViewStates(IntEnum):
    PRE_INIT = auto()
    INITIAL = auto()
    ON_INTRO_NODE = auto()
    ON_INTRO_COMPLEAT_BARKS_READER_NODE = auto()
    ON_INTRO_DON_AULT_FANTA_INTRO_NODE = auto()
    ON_THE_STORIES_NODE = auto()
    ON_SEARCH_NODE = auto()
    ON_TITLE_SEARCH_NODE = auto()
    ON_TAG_SEARCH_NODE = auto()
    ON_WORD_SEARCH_NODE = auto()
    ON_APPENDIX_NODE = auto()
    ON_APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_NODE = auto()
    ON_APPENDIX_RICH_TOMMASO_ON_COLORING_BARKS_NODE = auto()
    ON_APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_NODE = auto()
    ON_APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_NODE = auto()
    ON_APPENDIX_CENSORSHIP_FIXES_NODE = auto()
    ON_APPENDIX_STATISTICS_NODE = auto()
    ON_INDEX_NODE = auto()
    ON_INDEX_MAIN_NODE = auto()
    ON_INDEX_SPEECH_NODE = auto()
    ON_INDEX_SPEECH_WORDS_NODE = auto()
    ON_INDEX_NAMES_NODE = auto()
    ON_INDEX_LOCATIONS_NODE = auto()
    ON_CHRONO_BY_YEAR_NODE = auto()
    ON_YEAR_RANGE_NODE = auto()
    ON_SERIES_NODE = auto()
    ON_CS_NODE = auto()
    ON_CS_YEAR_RANGE_NODE = auto()
    ON_DD_NODE = auto()
    ON_US_NODE = auto()
    ON_US_YEAR_RANGE_NODE = auto()
    ON_DDS_NODE = auto()
    ON_USS_NODE = auto()
    ON_GG_NODE = auto()
    ON_MISC_NODE = auto()
    ON_CATEGORIES_NODE = auto()
    ON_CATEGORY_NODE = auto()
    ON_TAG_GROUP_NODE = auto()
    ON_TAG_NODE = auto()
    ON_TITLE_NODE = auto()
