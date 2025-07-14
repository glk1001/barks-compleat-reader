import logging
from collections import OrderedDict
from typing import List, Callable, Tuple, Dict, Union, Generator

from kivy.clock import Clock
from kivy.uix.button import Button

from barks_fantagraphics.barks_tags import (
    TagCategories,
    Tags,
    TagGroups,
    get_tagged_titles,
    get_num_tagged_titles,
    BARKS_TAG_CATEGORIES,
    BARKS_TAG_GROUPS_TITLES,
)
from barks_fantagraphics.barks_titles import (
    Titles,
    BARKS_TITLES,
    US_1_FC_ISSUE_NUM,
    US_2_FC_ISSUE_NUM,
    US_3_FC_ISSUE_NUM,
)
from barks_fantagraphics.fanta_comics_info import (
    FantaComicBookInfo,
    SERIES_CS,
    SERIES_DDA,
    SERIES_USA,
    SERIES_DDS,
    SERIES_USS,
    SERIES_GG,
    SERIES_MISC,
    ALL_LISTS,
)
from filtered_title_lists import FilteredTitleLists
from main_screen import MainScreen
from reader_consts_and_types import (
    INTRO_NODE_TEXT,
    THE_STORIES_NODE_TEXT,
    CHRONOLOGICAL_NODE_TEXT,
    SERIES_NODE_TEXT,
    CATEGORIES_NODE_TEXT,
    SEARCH_NODE_TEXT,
    APPENDIX_NODE_TEXT,
    INDEX_NODE_TEXT,
)
from reader_formatter import (
    get_bold_markup_text,
    get_markup_text_with_num_titles,
    get_markup_text_with_extra,
)
from reader_ui_classes import (
    ReaderTreeView,
    MainTreeViewNode,
    StoryGroupTreeViewNode,
    YearRangeTreeViewNode,
    CsYearRangeTreeViewNode,
    UsYearRangeTreeViewNode,
    TitleSearchBoxTreeViewNode,
    TagSearchBoxTreeViewNode,
    TitleTreeViewNode,
    ButtonTreeViewNode,
    TagStoryGroupTreeViewNode,
    TagGroupStoryGroupTreeViewNode,
)

BUTTON_ON_PRESS_CALLABLE = Callable[[Button], None]


class ReaderTreeBuilder:
    def __init__(
        self,
        main_screen: MainScreen,
    ):
        self.__main_screen = main_screen
        self.__events = self.__main_screen.reader_tree_events
        self.chrono_year_range_nodes: Dict[Tuple[int, int], ButtonTreeViewNode] = {}

        self.__all_series_pressed_funcs: OrderedDict[str, BUTTON_ON_PRESS_CALLABLE] = OrderedDict(
            [
                (SERIES_CS, self.__main_screen.cs_pressed),
                (SERIES_DDA, self.__main_screen.dd_pressed),
                (SERIES_USA, self.__main_screen.us_pressed),
                (SERIES_DDS, self.__main_screen.dds_pressed),
                (SERIES_USS, self.__main_screen.uss_pressed),
                (SERIES_GG, self.__main_screen.gg_pressed),
                (SERIES_MISC, self.__main_screen.misc_pressed),
            ]
        )

    def build_main_screen_tree(self):
        """Sets up and kicks off the entire asynchronous tree build process."""
        tree: ReaderTreeView = self.__main_screen.ids.reader_tree_view

        self.__main_screen.loading_data_popup.ids.loading_data_progress_bar.min = 0
        # Approximate total number of nodes to load:
        self.__main_screen.loading_data_popup.ids.loading_data_progress_bar.max = (
            len(self.__main_screen.title_lists[ALL_LISTS])  # chronological titles
            + len(self.__main_screen.title_lists[ALL_LISTS])  # series titles
            + get_num_tagged_titles()  # category titles
        )
        self.__main_screen.loading_data_popup.progress_bar_value = 0

        tree.bind(on_node_expand=self.__main_screen.on_node_expanded)

        logging.debug("Building simple nodes...")
        self.__add_intro_node(tree)
        the_stories_node = self.__add_the_stories_node(tree)
        self.__add_search_node(tree)
        self.__add_appendix_node(tree)
        self.__add_index_node(tree)

        logging.debug("Starting asynchronous build of story nodes...")
        # This is the single entry point for the entire asynchronous build.
        master_generator = self.__add_story_nodes_gen(tree, the_stories_node)
        self.__run_generator(master_generator, on_finish=self.__finished_all_nodes)

        tree.bind(minimum_height=tree.setter("height"))

    def __inc_progress_bar(self):
        self.__main_screen.loading_data_popup.progress_bar_value += 1

    # --- Master Generator ---

    def __add_story_nodes_gen(
        self, tree: ReaderTreeView, parent_node: ButtonTreeViewNode
    ) -> Generator:
        """
        A master generator that orchestrates the entire story node build process.
        It yields control to sub-generators for each major section.
        """
        # 1. Build Chronological nodes section
        logging.debug("Start building chronological nodes...")
        chrono_node = self.__create_and_add_simple_node(
            tree,
            CHRONOLOGICAL_NODE_TEXT,
            self.__main_screen.on_chrono_pressed,
            True,
            StoryGroupTreeViewNode,
            parent_node,
        )
        yield from self.__add_chrono_year_range_nodes_gen(tree, chrono_node)
        yield  # Yield once after the whole section is done for good measure.

        # 2. Build Series nodes section
        logging.debug("Start building series nodes...")
        series_node = self.__create_and_add_simple_node(
            tree,
            SERIES_NODE_TEXT,
            self.__main_screen.on_series_pressed,
            True,
            StoryGroupTreeViewNode,
            parent_node,
        )
        yield from self.__add_series_nodes_gen(tree, series_node)
        yield

        # 3. Build Categories nodes section
        logging.debug("Start building category nodes...")
        category_node = self.__create_and_add_simple_node(
            tree,
            CATEGORIES_NODE_TEXT,
            self.__main_screen.on_categories_pressed,
            True,
            StoryGroupTreeViewNode,
            parent_node,
        )
        yield from self.__add_categories_nodes_gen(tree, category_node)
        yield

    # --- Generator Chain Implementation ---

    def __add_chrono_year_range_nodes_gen(
        self, tree: ReaderTreeView, parent_node: ButtonTreeViewNode
    ) -> Generator:
        """Generator to add all chronological year range nodes."""
        year_ranges = self.__main_screen.filtered_title_lists.chrono_year_ranges
        yield from self.__add_year_range_nodes_gen(
            year_ranges, self.__add_chrono_year_range_node_and_child_nodes_gen, tree, parent_node
        )

    def __add_series_nodes_gen(
        self, tree: ReaderTreeView, parent_node: ButtonTreeViewNode
    ) -> Generator:
        """Generator to add all series nodes."""
        for series_name, on_pressed in self.__all_series_pressed_funcs.items():
            logging.debug(f'Adding series node "{series_name}".')
            yield from self.__add_series_node_gen(tree, series_name, on_pressed, parent_node)
            yield

    def __add_categories_nodes_gen(
        self, tree: ReaderTreeView, parent_node: ButtonTreeViewNode
    ) -> Generator:
        """Generator to add all category and tag nodes."""
        for category in TagCategories:
            logging.debug(f'Adding category "{category}".')
            new_node = self.__create_and_add_simple_node(
                tree,
                category.value,
                self.__main_screen.on_category_pressed,
                True,
                StoryGroupTreeViewNode,
                parent_node,
            )
            yield from self.__add_category_node_gen(tree, category, new_node)
            yield

    @staticmethod
    def __add_year_range_nodes_gen(
        year_ranges: List[Tuple[int, int]],
        add_nodes_func_gen: Callable[
            [ReaderTreeView, Tuple[int, int], ButtonTreeViewNode], Generator
        ],
        tree: ReaderTreeView,
        parent_node: ButtonTreeViewNode,
    ) -> Generator:
        """A generic generator to add nodes for a list of year ranges."""
        for year_range in year_ranges:
            yield from add_nodes_func_gen(tree, year_range, parent_node)
            yield

    def __add_chrono_year_range_node_and_child_nodes_gen(
        self, tree: ReaderTreeView, year_range: Tuple[int, int], parent_node: ButtonTreeViewNode
    ) -> Generator:
        new_node, year_range_titles = self.__add_chrono_year_range_node(
            tree, year_range, parent_node
        )
        yield from self.__add_fanta_info_story_nodes_gen(tree, year_range_titles, new_node)
        self.chrono_year_range_nodes[year_range] = new_node

    def __add_category_node_gen(
        self, tree: ReaderTreeView, category: TagCategories, parent_node: ButtonTreeViewNode
    ) -> Generator:
        for tag_or_group in BARKS_TAG_CATEGORIES[category]:
            if isinstance(tag_or_group, Tags):
                yield from self.__add_tag_node_gen(tree, tag_or_group, parent_node)
            elif isinstance(tag_or_group, TagGroups):
                titles = BARKS_TAG_GROUPS_TITLES[tag_or_group]
                tag_group_node = self.__add_tag_group_node(tree, tag_or_group, titles, parent_node)
                yield from self.__add_title_nodes_gen(tree, titles, tag_group_node)

    def __add_tag_node_gen(
        self, tree: ReaderTreeView, tag: Tags, parent_node: ButtonTreeViewNode
    ) -> Generator:
        titles = get_tagged_titles(tag)
        new_node = TagStoryGroupTreeViewNode(
            tag, text=get_markup_text_with_num_titles(tag.value, len(titles))
        )
        yield from self.__add_title_nodes_gen(tree, titles, new_node)
        tree.add_node(new_node, parent=parent_node)

    def __add_title_nodes_gen(
        self, tree: ReaderTreeView, titles: List[Titles], parent_node: ButtonTreeViewNode
    ) -> Generator:
        for title in titles:
            # TODO: Very roundabout way to get fanta info
            title_str = BARKS_TITLES[title]
            if title_str in self.__main_screen.all_fanta_titles:
                title_info = self.__main_screen.all_fanta_titles[title_str]
                node = TitleTreeViewNode.create_from_fanta_info(
                    title_info, self.__main_screen.on_title_row_button_pressed
                )
                tree.add_node(node, parent=parent_node)
            self.__inc_progress_bar()
            yield

    def __add_series_node_gen(
        self,
        tree: ReaderTreeView,
        series_name: str,
        on_pressed: BUTTON_ON_PRESS_CALLABLE,
        parent_node: ButtonTreeViewNode,
    ) -> Generator:
        if series_name == SERIES_CS:
            yield from self.__add_cs_node_gen(tree, on_pressed, parent_node)
        elif series_name == SERIES_USA:
            yield from self.__add_us_node_gen(tree, on_pressed, parent_node)
        else:
            yield from self.__add_simple_series_node_gen(tree, series_name, on_pressed, parent_node)

    def __add_simple_series_node_gen(
        self,
        tree: ReaderTreeView,
        series_name: str,
        on_pressed: BUTTON_ON_PRESS_CALLABLE,
        parent_node: ButtonTreeViewNode,
    ) -> Generator:
        title_list = self.__main_screen.title_lists[series_name]
        series_text = get_markup_text_with_num_titles(series_name, len(title_list))
        new_node = StoryGroupTreeViewNode(text=series_text)
        new_node.bind(on_press=on_pressed)
        tree.add_node(new_node, parent=parent_node)
        yield from self.__add_fanta_info_story_nodes_gen(tree, title_list, new_node)

    def __add_cs_node_gen(
        self,
        tree: ReaderTreeView,
        on_pressed: BUTTON_ON_PRESS_CALLABLE,
        parent_node: ButtonTreeViewNode,
    ) -> Generator:
        yield from self.__add_splittable_series_node_gen(
            SERIES_CS,
            self.__main_screen.filtered_title_lists.cs_year_ranges,
            self.__add_cs_year_range_node_gen,
            tree,
            on_pressed,
            parent_node,
        )

    def __add_cs_year_range_node_gen(
        self, tree: ReaderTreeView, year_range: Tuple[int, int], parent_node: ButtonTreeViewNode
    ) -> Generator:
        new_node, year_range_titles = self.__create_and_add_year_range_node(
            tree,
            year_range,
            self.__main_screen.on_cs_year_range_pressed,
            FilteredTitleLists.get_cs_range_str_from_str,
            self.__get_cs_year_range_extra_text,
            CsYearRangeTreeViewNode,
            parent_node,
        )
        yield from self.__add_fanta_info_story_nodes_gen(tree, year_range_titles, new_node)

    def __add_us_node_gen(
        self,
        tree: ReaderTreeView,
        on_pressed: BUTTON_ON_PRESS_CALLABLE,
        parent_node: ButtonTreeViewNode,
    ) -> Generator:
        yield from self.__add_splittable_series_node_gen(
            SERIES_USA,
            self.__main_screen.filtered_title_lists.us_year_ranges,
            self.__add_us_year_range_node_gen,
            tree,
            on_pressed,
            parent_node,
        )

    def __add_us_year_range_node_gen(
        self, tree: ReaderTreeView, year_range: Tuple[int, int], parent_node: ButtonTreeViewNode
    ) -> Generator:
        new_node, year_range_titles = self.__create_and_add_year_range_node(
            tree,
            year_range,
            self.__main_screen.on_us_year_range_pressed,
            FilteredTitleLists.get_us_range_str_from_str,
            self.__get_us_year_range_extra_text,
            UsYearRangeTreeViewNode,
            parent_node,
        )
        yield from self.__add_fanta_info_story_nodes_gen(tree, year_range_titles, new_node)

    def __add_splittable_series_node_gen(
        self,
        series_name: str,
        series_year_ranges: List[Tuple[int, int]],
        add_node_func_gen: Callable[
            [ReaderTreeView, Tuple[int, int], StoryGroupTreeViewNode], Generator
        ],
        tree: ReaderTreeView,
        on_pressed: BUTTON_ON_PRESS_CALLABLE,
        parent_node: ButtonTreeViewNode,
    ) -> Generator:
        title_list = self.__main_screen.title_lists[series_name]
        series_text = get_markup_text_with_num_titles(series_name, len(title_list))
        series_node = StoryGroupTreeViewNode(text=series_text)
        series_node.bind(on_press=on_pressed)

        yield from self.__add_year_range_nodes_gen(
            series_year_ranges,
            add_node_func_gen,
            tree,
            series_node,
        )
        tree.add_node(series_node, parent=parent_node)

    def __add_fanta_info_story_nodes_gen(
        self,
        tree: ReaderTreeView,
        title_info_list: List[FantaComicBookInfo],
        parent_node: ButtonTreeViewNode,
    ) -> Generator:
        for title_info in title_info_list:
            node = TitleTreeViewNode.create_from_fanta_info(
                title_info, self.__main_screen.on_title_row_button_pressed
            )
            tree.add_node(node, parent=parent_node)
            self.__inc_progress_bar()
            yield

    # --- Synchronous Helper Methods ---

    def __add_intro_node(self, tree: ReaderTreeView):
        self.__create_and_add_simple_node(
            tree, INTRO_NODE_TEXT, self.__main_screen.on_intro_pressed
        )

    def __add_the_stories_node(self, tree: ReaderTreeView) -> MainTreeViewNode:
        return self.__create_and_add_simple_node(
            tree, THE_STORIES_NODE_TEXT, self.__main_screen.on_the_stories_pressed
        )

    def __add_search_node(self, tree: ReaderTreeView):
        search_node = self.__create_and_add_simple_node(
            tree, SEARCH_NODE_TEXT, self.__main_screen.on_search_pressed
        )
        self.__create_and_add_title_search_box_node(tree, search_node)
        self.__create_and_add_tag_search_box_node(tree, search_node)

    def __add_appendix_node(self, tree: ReaderTreeView):
        self.__create_and_add_simple_node(
            tree, APPENDIX_NODE_TEXT, self.__main_screen.on_appendix_pressed
        )

    def __add_index_node(self, tree: ReaderTreeView):
        self.__create_and_add_simple_node(
            tree, INDEX_NODE_TEXT, self.__main_screen.on_index_pressed
        )

    def __add_chrono_year_range_node(
        self, tree: ReaderTreeView, year_range: Tuple[int, int], parent_node: ButtonTreeViewNode
    ) -> Tuple[ButtonTreeViewNode, List[FantaComicBookInfo]]:
        return self.__create_and_add_year_range_node(
            tree,
            year_range,
            self.__main_screen.on_year_range_pressed,
            lambda x: x,
            lambda title_list: str(len(title_list)),
            YearRangeTreeViewNode,
            parent_node,
        )

    @staticmethod
    def __add_tag_group_node(
        tree: ReaderTreeView,
        tag_group: TagGroups,
        titles: List[Titles],
        parent_node: ButtonTreeViewNode,
    ):
        node = TagGroupStoryGroupTreeViewNode(
            tag_group, text=get_markup_text_with_num_titles(tag_group.value, len(titles))
        )
        return tree.add_node(node, parent=parent_node)

    @staticmethod
    def __get_cs_year_range_extra_text(title_list: List[FantaComicBookInfo]) -> str:
        first_issue = min(
            title_list, key=lambda x: x.comic_book_info.issue_number
        ).comic_book_info.issue_number
        last_issue = max(
            title_list, key=lambda x: x.comic_book_info.issue_number
        ).comic_book_info.issue_number
        return f"WDCS {first_issue}-{last_issue}"

    @staticmethod
    def __get_us_year_range_extra_text(title_list: List[FantaComicBookInfo]) -> str:
        def get_us_issue_number(fanta_info: FantaComicBookInfo) -> int:
            num = fanta_info.comic_book_info.issue_number
            if num == US_1_FC_ISSUE_NUM:
                return 1
            if num == US_2_FC_ISSUE_NUM:
                return 2
            if num == US_3_FC_ISSUE_NUM:
                return 3
            return num

        first_issue = get_us_issue_number(min(title_list, key=lambda x: get_us_issue_number(x)))
        last_issue = get_us_issue_number(max(title_list, key=lambda x: get_us_issue_number(x)))
        return f"US {first_issue}-{last_issue}"

    @staticmethod
    def __create_and_add_simple_node(
        tree: ReaderTreeView,
        text: str,
        on_press_handler: BUTTON_ON_PRESS_CALLABLE,
        is_bold: bool = False,
        node_class: type = MainTreeViewNode,
        parent_node: ButtonTreeViewNode = None,
    ) -> Union[MainTreeViewNode, StoryGroupTreeViewNode]:
        node_text = get_bold_markup_text(text) if is_bold else text
        new_node = node_class(text=node_text)
        new_node.bind(on_press=on_press_handler)
        return tree.add_node(new_node, parent=parent_node)

    def __create_and_add_title_search_box_node(
        self, tree: ReaderTreeView, parent_node: ButtonTreeViewNode
    ):
        new_node = TitleSearchBoxTreeViewNode(self.__main_screen.title_search)
        new_node.bind(on_title_search_box_pressed=self.__main_screen.on_title_search_box_pressed)
        new_node.bind(
            on_title_search_box_title_changed=self.__main_screen.on_title_search_box_title_changed
        )
        return tree.add_node(new_node, parent=parent_node)

    def __create_and_add_tag_search_box_node(
        self, tree: ReaderTreeView, parent_node: ButtonTreeViewNode
    ):
        new_node = TagSearchBoxTreeViewNode(self.__main_screen.title_search)
        new_node.bind(on_tag_search_box_pressed=self.__main_screen.on_tag_search_box_pressed)
        new_node.bind(
            on_tag_search_box_text_changed=self.__main_screen.on_tag_search_box_text_changed
        )
        new_node.bind(
            on_tag_search_box_tag_changed=self.__main_screen.on_tag_search_box_tag_changed
        )
        new_node.bind(
            on_tag_search_box_title_changed=self.__main_screen.on_tag_search_box_title_changed
        )
        return tree.add_node(new_node, parent=parent_node)

    def __create_and_add_year_range_node(
        self,
        tree: ReaderTreeView,
        year_range: Tuple[int, int],
        on_press_handler: BUTTON_ON_PRESS_CALLABLE,
        get_title_key_func: Callable[[str], str],
        get_year_range_extra_text_func: Callable[[List[FantaComicBookInfo]], str],
        node_class: type,
        parent_node: ButtonTreeViewNode,
    ) -> Tuple[ButtonTreeViewNode, List[FantaComicBookInfo]]:
        year_range_str = FilteredTitleLists.get_range_str(year_range)
        year_range_key = get_title_key_func(year_range_str)
        year_range_titles = self.__main_screen.title_lists[year_range_key]
        year_range_extra_text = get_year_range_extra_text_func(year_range_titles)
        year_range_text = get_markup_text_with_extra(year_range_str, year_range_extra_text)
        new_node = node_class(text=year_range_text)
        new_node.bind(on_press=on_press_handler)
        new_node = tree.add_node(new_node, parent=parent_node)
        return new_node, year_range_titles

    @staticmethod
    def __run_generator(gen: Generator, on_finish: Callable = None):
        """
        Schedules a generator to run one step at a time on the Kivy clock.
        An optional on_finish callback can be provided.
        """

        def _next_step(*_):
            try:
                next(gen)
                Clock.schedule_once(_next_step, 0)
            except StopIteration:
                if on_finish:
                    on_finish()

        Clock.schedule_once(_next_step, 0)

    def __finished_all_nodes(self) -> None:
        logging.debug(
            f"Finished loading all nodes:"
            f" {self.__main_screen.loading_data_popup.progress_bar_value}"
            f" titles processed."
        )
        self.__main_screen.reader_tree_events.finished_building()
