from __future__ import annotations

from enum import IntEnum, auto

from barks_fantagraphics.barks_tags import (
    BARKS_TAG_CATEGORIES_DICT,
    TagGroups,
    Tags,
    is_tag_enum,
    is_tag_group_enum,
)
from barks_fantagraphics.barks_titles import NON_COMIC_TITLES, Titles
from barks_fantagraphics.fanta_comics_info import (
    SERIES_CS,
    SERIES_DDA,
    SERIES_DDS,
    SERIES_GG,
    SERIES_MISC,
    SERIES_USA,
    SERIES_USS,
)

from barks_reader.reader_consts_and_types import (
    APPENDIX_CENSORSHIP_FIXES_NODE_TEXT,
    APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_TEXT,
    APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_TEXT,
    APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_TEXT,
    APPENDIX_NODE_TEXT,
    APPENDIX_RICH_TOMASSO_ON_COLORING_BARKS_TEXT,
    CATEGORIES_NODE_TEXT,
    CHRONOLOGICAL_NODE_TEXT,
    INDEX_MAIN_TEXT,
    INDEX_NODE_TEXT,
    INDEX_SPEECH_TEXT,
    INTRO_COMPLEAT_BARKS_READER_TEXT,
    INTRO_DON_AULT_FANTA_INTRO_TEXT,
    INTRO_NODE_TEXT,
    SEARCH_NODE_TEXT,
    SERIES_NODE_TEXT,
    THE_STORIES_NODE_TEXT,
)
from barks_reader.reader_formatter import get_clean_text_without_extra
from barks_reader.reader_ui_classes import (
    ButtonTreeViewNode,
    CsYearRangeTreeViewNode,
    TagSearchBoxTreeViewNode,
    TitleSearchBoxTreeViewNode,
    UsYearRangeTreeViewNode,
    YearRangeTreeViewNode,
)


class ViewStates(IntEnum):
    PRE_INIT = auto()
    INITIAL = auto()
    ON_INTRO_NODE = auto()
    ON_INTRO_COMPLEAT_BARKS_READER_NODE = auto()
    ON_INTRO_DON_AULT_FANTA_INTRO_NODE = auto()
    ON_THE_STORIES_NODE = auto()
    ON_SEARCH_NODE = auto()
    ON_APPENDIX_NODE = auto()
    ON_APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_NODE = auto()
    ON_APPENDIX_RICH_TOMASSO_ON_COLORING_BARKS_NODE = auto()
    ON_APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_NODE = auto()
    ON_APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_NODE = auto()
    ON_APPENDIX_CENSORSHIP_FIXES_NODE = auto()
    ON_INDEX_NODE = auto()
    ON_INDEX_MAIN_NODE = auto()
    ON_INDEX_SPEECH_NODE = auto()
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
    ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET = auto()
    ON_TITLE_SEARCH_BOX_NODE = auto()
    ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET = auto()
    ON_TAG_SEARCH_BOX_NODE = auto()


_NODE_TYPE_TO_VIEW_STATE_MAP: dict[type, tuple[ViewStates, str]] = {
    CsYearRangeTreeViewNode: (ViewStates.ON_CS_YEAR_RANGE_NODE, "cs_year_range"),
    UsYearRangeTreeViewNode: (ViewStates.ON_US_YEAR_RANGE_NODE, "us_year_range"),
    YearRangeTreeViewNode: (ViewStates.ON_YEAR_RANGE_NODE, "year_range"),
}

# fmt: off
# noinspection LongLine
_NODE_TEXT_TO_VIEW_STATE_MAP: dict[str, ViewStates] = {
    "N/A" + ViewStates.PRE_INIT.name: ViewStates.PRE_INIT,
    "N/A" + ViewStates.INITIAL.name: ViewStates.INITIAL,
    INTRO_NODE_TEXT: ViewStates.ON_INTRO_NODE,
    INTRO_COMPLEAT_BARKS_READER_TEXT: ViewStates.ON_INTRO_COMPLEAT_BARKS_READER_NODE,
    INTRO_DON_AULT_FANTA_INTRO_TEXT: ViewStates.ON_INTRO_DON_AULT_FANTA_INTRO_NODE,
    THE_STORIES_NODE_TEXT: ViewStates.ON_THE_STORIES_NODE,
    SEARCH_NODE_TEXT: ViewStates.ON_SEARCH_NODE,
    APPENDIX_NODE_TEXT: ViewStates.ON_APPENDIX_NODE,
    APPENDIX_RICH_TOMASSO_ON_COLORING_BARKS_TEXT: ViewStates.ON_APPENDIX_RICH_TOMASSO_ON_COLORING_BARKS_NODE,  # noqa: E501
    APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_TEXT: ViewStates.ON_APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_NODE,
    APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_TEXT: ViewStates.ON_APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_NODE,  # noqa: E501
    APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_TEXT: ViewStates.ON_APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_NODE,  # noqa: E501
    APPENDIX_CENSORSHIP_FIXES_NODE_TEXT: ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE,
    INDEX_NODE_TEXT: ViewStates.ON_INDEX_NODE,
    INDEX_MAIN_TEXT: ViewStates.ON_INDEX_MAIN_NODE,
    INDEX_SPEECH_TEXT: ViewStates.ON_INDEX_SPEECH_NODE,
    CHRONOLOGICAL_NODE_TEXT: ViewStates.ON_CHRONO_BY_YEAR_NODE,
    "N/A" + ViewStates.ON_YEAR_RANGE_NODE.name: ViewStates.ON_YEAR_RANGE_NODE,
    SERIES_NODE_TEXT: ViewStates.ON_SERIES_NODE,
    SERIES_CS: ViewStates.ON_CS_NODE,
    "N/A" + ViewStates.ON_CS_YEAR_RANGE_NODE.name: ViewStates.ON_CS_YEAR_RANGE_NODE,
    SERIES_DDA: ViewStates.ON_DD_NODE,
    SERIES_USA: ViewStates.ON_US_NODE,
    "N/A" + ViewStates.ON_US_YEAR_RANGE_NODE.name: ViewStates.ON_US_YEAR_RANGE_NODE,
    SERIES_DDS: ViewStates.ON_DDS_NODE,
    SERIES_USS: ViewStates.ON_USS_NODE,
    SERIES_GG: ViewStates.ON_GG_NODE,
    SERIES_MISC: ViewStates.ON_MISC_NODE,
    CATEGORIES_NODE_TEXT: ViewStates.ON_CATEGORIES_NODE,
    "N/A" + ViewStates.ON_CATEGORY_NODE.name: ViewStates.ON_CATEGORY_NODE,
    "N/A" + ViewStates.ON_TAG_GROUP_NODE.name: ViewStates.ON_TAG_GROUP_NODE,
    "N/A" + ViewStates.ON_TAG_NODE.name: ViewStates.ON_TAG_NODE,
    "N/A" + ViewStates.ON_TITLE_NODE.name: ViewStates.ON_TITLE_NODE,
    "N/A"
    + ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET.name: ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET,  # noqa: E501
    "N/A" + ViewStates.ON_TITLE_SEARCH_BOX_NODE.name: ViewStates.ON_TITLE_SEARCH_BOX_NODE,
    "N/A"
    + ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET.name: ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET,  # noqa: E501
    "N/A" + ViewStates.ON_TAG_SEARCH_BOX_NODE.name: ViewStates.ON_TAG_SEARCH_BOX_NODE,
}
# fmt: on
assert sorted(_NODE_TEXT_TO_VIEW_STATE_MAP.values()) == sorted(ViewStates)

# fmt: off
# noinspection LongLine
_ARTICLE_VIEW_STATE_TO_TITLE_MAP = {
    ViewStates.ON_APPENDIX_RICH_TOMASSO_ON_COLORING_BARKS_NODE: Titles.RICH_TOMASSO___ON_COLORING_BARKS,  # noqa: E501
    ViewStates.ON_INTRO_DON_AULT_FANTA_INTRO_NODE: Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION,
    ViewStates.ON_APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_NODE: Titles.DON_AULT___LIFE_AMONG_THE_DUCKS,
    ViewStates.ON_APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_NODE: Titles.MAGGIE_THOMPSON___COMICS_READERS_FIND_COMIC_BOOK_GOLD,  # noqa: E501
    ViewStates.ON_APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_NODE: Titles.GEORGE_LUCAS___AN_APPRECIATION,
    ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE: Titles.CENSORSHIP_FIXES_AND_OTHER_CHANGES,
}
# fmt: on
assert sorted(_ARTICLE_VIEW_STATE_TO_TITLE_MAP.values()) == sorted(NON_COMIC_TITLES)


def get_view_state_and_article_title_from_node(
    node: ButtonTreeViewNode,
) -> tuple[ViewStates, Titles]:
    view_state = _get_view_state_from_node_text(node.text)

    if view_state not in _ARTICLE_VIEW_STATE_TO_TITLE_MAP:
        msg = f"No article mapping found for node: {node.text}"
        raise RuntimeError(msg)

    return view_state, _ARTICLE_VIEW_STATE_TO_TITLE_MAP[view_state]


def _get_view_state_from_node_text(node_text: str) -> ViewStates | None:
    clean_text = get_clean_text_without_extra(node_text)
    return _NODE_TEXT_TO_VIEW_STATE_MAP.get(clean_text)


def get_view_state_from_node(
    node: ButtonTreeViewNode,
) -> tuple[ViewStates | None, dict[str, str | TagGroups | Tags]]:
    """Determine the view state and parameters from a tree view node."""
    view_state_params: dict[str, str | TagGroups | Tags] = {}
    new_view_state: ViewStates | None = None
    clean_node_text = get_clean_text_without_extra(node.text)

    for node_type, (state, param_name) in _NODE_TYPE_TO_VIEW_STATE_MAP.items():
        if isinstance(node, node_type):
            # noinspection PyUnresolvedReferences
            return state, {param_name: node.text}

    if isinstance(node, TitleSearchBoxTreeViewNode):
        new_view_state = ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET
    elif isinstance(node, TagSearchBoxTreeViewNode):
        new_view_state = ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET
    elif clean_node_text in _NODE_TEXT_TO_VIEW_STATE_MAP:
        new_view_state = _NODE_TEXT_TO_VIEW_STATE_MAP[clean_node_text]
    elif clean_node_text in BARKS_TAG_CATEGORIES_DICT:
        new_view_state = ViewStates.ON_CATEGORY_NODE
        view_state_params["category"] = clean_node_text
    elif is_tag_group_enum(clean_node_text):
        new_view_state = ViewStates.ON_TAG_GROUP_NODE
        view_state_params["tag_group"] = TagGroups(clean_node_text)
    elif is_tag_enum(clean_node_text):
        new_view_state = ViewStates.ON_TAG_NODE
        view_state_params["tag"] = Tags(clean_node_text)

    return new_view_state, view_state_params
