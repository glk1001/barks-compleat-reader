from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

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
from kivy.clock import Clock
from kivy.uix.treeview import TreeViewNode
from loguru import logger

from barks_reader.background_views import BackgroundViews, ViewStates
from barks_reader.reader_consts_and_types import (
    APPENDIX_CENSORSHIP_FIXES_NODE_TEXT,
    APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_TEXT,
    APPENDIX_NODE_TEXT,
    APPENDIX_RICH_TOMASSO_ON_COLORING_BARKS_TEXT,
    CATEGORIES_NODE_TEXT,
    CHRONOLOGICAL_NODE_TEXT,
    INDEX_NODE_TEXT,
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
    TitleTreeViewNode,
    UsYearRangeTreeViewNode,
    YearRangeTreeViewNode,
)

if TYPE_CHECKING:
    from kivy.uix.button import Button
    from kivy.uix.spinner import Spinner

    from barks_reader.reader_ui_classes import ReaderTreeView
    from barks_reader.tree_view_screen import TreeViewScreen
    from barks_reader.view_state_manager import ViewStateManager


UpdateTitleCallable = Callable[[str], bool]
ReadArticleCallable = Callable[[Titles, ViewStates], None]
ReadIntroCompleatBarksReaderCallable = Callable[[], None]
ScrollToNodeCallable = Callable[[TreeViewNode], None]
SetTagGotoPageCheckboxCallable = Callable[[Tags | TagGroups, str], None]


NODE_TYPE_TO_VIEW_STATE_MAP: dict[type, tuple[ViewStates, str]] = {
    YearRangeTreeViewNode: (ViewStates.ON_YEAR_RANGE_NODE, "year_range"),
    CsYearRangeTreeViewNode: (ViewStates.ON_CS_YEAR_RANGE_NODE, "cs_year_range"),
    UsYearRangeTreeViewNode: (ViewStates.ON_US_YEAR_RANGE_NODE, "us_year_range"),
}

# fmt: off
NODE_TEXT_TO_VIEW_STATE_MAP: dict[str, ViewStates] = {
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
    APPENDIX_CENSORSHIP_FIXES_NODE_TEXT: ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE,
    INDEX_NODE_TEXT: ViewStates.ON_INDEX_NODE,
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
    "N/A" + ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET.name: ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET,  # noqa: E501
    "N/A" + ViewStates.ON_TITLE_SEARCH_BOX_NODE.name: ViewStates.ON_TITLE_SEARCH_BOX_NODE,
    "N/A" + ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET.name: ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET,  # noqa: E501
    "N/A" + ViewStates.ON_TAG_SEARCH_BOX_NODE.name: ViewStates.ON_TAG_SEARCH_BOX_NODE,
}
assert sorted(NODE_TEXT_TO_VIEW_STATE_MAP.values()) == sorted(ViewStates)

ARTICLE_VIEW_STATE_TO_TITLE_MAP = {
    ViewStates.ON_APPENDIX_RICH_TOMASSO_ON_COLORING_BARKS_NODE: Titles.RICH_TOMASSO___ON_COLORING_BARKS,  # noqa: E501
    ViewStates.ON_INTRO_DON_AULT_FANTA_INTRO_NODE: Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION,
    ViewStates.ON_APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_NODE: Titles.DON_AULT___LIFE_AMONG_THE_DUCKS,
    ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE: Titles.CENSORSHIP_FIXES_AND_OTHER_CHANGES,
}
# fmt: on
assert sorted(ARTICLE_VIEW_STATE_TO_TITLE_MAP.values()) == sorted(NON_COMIC_TITLES)


class TreeViewManager:
    """Manage all interactions and events related to the TreeView."""

    # Seems wrong result for 'SetTagGotoPageCheckboxCallable' inspection.
    # noinspection PyTypeHints
    def __init__(
        self,
        background_views: BackgroundViews,
        view_state_manager: ViewStateManager,
        tree_view_screen: TreeViewScreen,
        update_title_func: UpdateTitleCallable,
        read_article_func: ReadArticleCallable,
        read_intro_compleat_barks_reader_func: ReadIntroCompleatBarksReaderCallable,
        set_tag_goto_page_checkbox_func: SetTagGotoPageCheckboxCallable,
    ) -> None:
        self._background_views = background_views
        self._view_state_manager = view_state_manager
        self._tree_view_screen = tree_view_screen

        self._tree_view_screen.ids.reader_tree_view.bind(on_node_expand=self.on_node_expanded)

        self._update_title_func = update_title_func
        self._read_article_func = read_article_func
        self._read_intro_compleat_barks_reader_func = read_intro_compleat_barks_reader_func
        self._set_tag_goto_page_checkbox_func = set_tag_goto_page_checkbox_func

        assert self._update_title_func
        assert self._read_article_func
        assert self._set_tag_goto_page_checkbox_func

    def goto_node(self, node: TreeViewNode, scroll_to: bool = False) -> None:
        def show_node(n: TreeViewNode) -> None:
            self._tree_view_screen.select_node(n)
            if scroll_to:
                self.scroll_to_node(n)

        Clock.schedule_once(lambda _dt, item=node: show_node(item), 0)

    def scroll_to_node(self, node: TreeViewNode) -> None:
        Clock.schedule_once(lambda _dt: self._tree_view_screen.scroll_to_node(node), 0)

    def on_node_expanded(self, _tree: ReaderTreeView, node: ButtonTreeViewNode) -> None:
        if isinstance(node, TitleTreeViewNode):
            return

        logger.info(f'Node expanded: "{node.text}" ({type(node)}).')

        new_view_state, view_state_params = self._get_view_state_from_node(node)

        if new_view_state is None:
            msg = f"No view state mapping found for node: {node.text} ({type(node)})"
            raise RuntimeError(msg)

        logger.info(f'Updating backgrounds views for expanded node: "{new_view_state.name}".')
        self._view_state_manager.update_background_views(new_view_state, **view_state_params)

        self.scroll_to_node(node.nodes[0] if node.nodes else node)

    def on_intro_compleat_barks_reader_pressed(self, _button: Button) -> None:
        self._read_intro_compleat_barks_reader_func()

    def on_article_node_pressed(self, node: ButtonTreeViewNode) -> None:
        """Consolidate handling of all simple article nodes."""
        view_state = self._get_view_state_for_node_text(node.text)

        if view_state not in ARTICLE_VIEW_STATE_TO_TITLE_MAP:
            msg = f"No article mapping found for node: {node.text}"
            raise RuntimeError(msg)

        article_title = ARTICLE_VIEW_STATE_TO_TITLE_MAP[view_state]
        logger.info(f"Article node pressed: Reading '{article_title.name}'.")
        self._read_article_func(article_title, view_state)

    @staticmethod
    def _get_view_state_for_node_text(node_text: str) -> ViewStates | None:
        clean_text = get_clean_text_without_extra(node_text)
        return NODE_TEXT_TO_VIEW_STATE_MAP.get(clean_text)

    def on_title_search_box_pressed(self, instance: TitleSearchBoxTreeViewNode) -> None:
        logger.debug(f"Title search box pressed: {instance}.")

        if not instance.get_current_title():
            logger.debug("Have not got title search box text yet.")
            self._view_state_manager.update_view_for_node(
                ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET
            )
        elif self._background_views.get_view_state() != ViewStates.ON_TITLE_SEARCH_BOX_NODE:
            logger.debug(
                f"Forcing title search box change:"
                f" view state = {self._background_views.get_view_state()},"
                f' title search box text = "{instance.get_current_title()}",'
                f' title spinner text = "{instance.ids.title_spinner.text}"',
            )
            self.on_title_search_box_title_changed(
                instance.ids.title_spinner,
                instance.ids.title_spinner.text,
            )

    def on_title_search_box_title_changed(self, _spinner: Spinner, title_str: str) -> None:
        logger.debug(f'Title search box title changed: "{title_str}".')

        if not title_str:
            self._view_state_manager.update_view_for_node(
                ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET
            )
        elif self._update_title_func(title_str):
            self._view_state_manager.update_view_for_node_with_title(
                ViewStates.ON_TITLE_SEARCH_BOX_NODE
            )
        else:
            self._view_state_manager.update_view_for_node(
                ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET
            )

    def on_tag_search_box_pressed(self, instance: TagSearchBoxTreeViewNode) -> None:
        logger.debug(f"Tag search box pressed: {instance}.")

        if not instance.get_current_tag_str():
            logger.debug("Have not got tag search box text yet.")
            self._view_state_manager.update_view_for_node(
                ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET
            )
        elif self._background_views.get_view_state() != ViewStates.ON_TAG_SEARCH_BOX_NODE:
            logger.debug(
                f"Forcing tag search box change:"
                f" view state = {self._background_views.get_view_state()},"
                f' tag search box text = "{instance.get_current_tag_str()}",'
                f' tag title spinner text = "{instance.ids.tag_title_spinner.text}"',
            )
            self.on_tag_search_box_title_changed(instance, instance.ids.tag_title_spinner.text)

    def on_tag_search_box_text_changed(self, instance: TagSearchBoxTreeViewNode, text: str) -> None:
        logger.debug(f'Tag search box text changed: text: "{text}".')

        if not instance.get_current_title():
            self._view_state_manager.update_view_for_node(
                ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET
            )

    def on_tag_search_box_tag_changed(
        self,
        instance: TagSearchBoxTreeViewNode,
        tag_str: str,
    ) -> None:
        logger.debug(f'Tag search box tag changed: "{tag_str}".')

        if not tag_str:
            return

        if not instance.get_current_title():
            self._view_state_manager.update_view_for_node(
                ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET
            )

    def on_tag_search_box_title_changed(
        self,
        instance: TagSearchBoxTreeViewNode,
        title_str: str,
    ) -> None:
        logger.debug(
            f'Tag search box title changed: "{title_str}".'
            f' Tag: "{instance.get_current_tag().value}".',
        )

        if not title_str:
            self._view_state_manager.update_view_for_node(
                ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET
            )
        elif self._update_title_func(title_str):
            self._view_state_manager.update_view_for_node_with_title(
                ViewStates.ON_TAG_SEARCH_BOX_NODE
            )
            self._set_tag_goto_page_checkbox_func(instance.get_current_tag(), title_str)
        else:
            self._view_state_manager.update_view_for_node(
                ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET
            )

    @staticmethod
    def _get_view_state_from_node(
        node: ButtonTreeViewNode,
    ) -> tuple[ViewStates | None, dict[str, str | TagGroups | Tags]]:
        """Determine the view state and parameters from a tree view node."""
        node_type = type(node)
        view_state_params: dict[str, str | TagGroups | Tags] = {}
        new_view_state: ViewStates | None = None
        clean_node_text = get_clean_text_without_extra(node.text)

        if node_type in NODE_TYPE_TO_VIEW_STATE_MAP:
            new_view_state, param_name = NODE_TYPE_TO_VIEW_STATE_MAP[node_type]
            view_state_params[param_name] = node.text
        elif clean_node_text in NODE_TEXT_TO_VIEW_STATE_MAP:
            new_view_state = NODE_TEXT_TO_VIEW_STATE_MAP[clean_node_text]
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
