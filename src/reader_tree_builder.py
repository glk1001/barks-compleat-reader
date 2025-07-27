import logging
from collections import OrderedDict
from datetime import datetime
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
    BARKS_TAG_GROUPS,
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
    APPENDIX_CENSORSHIP_FIXES_NODE_TEXT,
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
from timing import Timing

BUTTON_ON_PRESS_CALLABLE = Callable[[Button], None]


class _CompletionCounter:
    """
    A simple counter to track the completion of multiple asynchronous tasks.
    It triggers a callback when all tasks are finished.
    """

    def __init__(self, on_all_finished: Callable = None):
        self._count = 0
        self._on_all_finished = on_all_finished

    def start_task(self):
        """Register a new task."""
        self._count += 1

    def finish_task(self):
        """Mark a task as complete and trigger the final callback if it's the last one."""
        self._count -= 1
        if self._count == 0:
            if self._on_all_finished:
                self._on_all_finished()


class ReaderTreeBuilder:
    # Process nodes in batches to reduce scheduling overhead and improve performance.
    # A larger batch size is faster but makes the UI less responsive during the build.
    BUILD_BATCH_SIZE = 5

    def __init__(self, main_screen: MainScreen):
        self._main_screen = main_screen
        self._events = self._main_screen.reader_tree_events
        self._tree_build_timing = None
        self.chrono_year_range_nodes: Dict[Tuple[int, int], ButtonTreeViewNode] = {}

        self._all_series_pressed_funcs: OrderedDict[str, BUTTON_ON_PRESS_CALLABLE] = OrderedDict(
            [
                (SERIES_CS, self._main_screen.cs_pressed),
                (SERIES_DDA, self._main_screen.dd_pressed),
                (SERIES_USA, self._main_screen.us_pressed),
                (SERIES_DDS, self._main_screen.dds_pressed),
                (SERIES_USS, self._main_screen.uss_pressed),
                (SERIES_GG, self._main_screen.gg_pressed),
                (SERIES_MISC, self._main_screen.misc_pressed),
            ]
        )

    def build_main_screen_tree(self):
        """Sets up and kicks off the entire asynchronous tree build process."""
        tree: ReaderTreeView = self._main_screen.ids.reader_tree_view

        self._main_screen.loading_data_popup.ids.loading_data_progress_bar.min = 0
        # Approximate total number of nodes to load:
        self._main_screen.loading_data_popup.ids.loading_data_progress_bar.max = (
            len(self._main_screen.title_lists[ALL_LISTS])  # chronological titles
            + len(self._main_screen.title_lists[ALL_LISTS])  # series titles
            + get_num_tagged_titles()  # category titles
        )
        logging.debug(
            f"Progress bar max"
            f" = {self._main_screen.loading_data_popup.ids.loading_data_progress_bar.max}."
        )
        self._main_screen.loading_data_popup.progress_bar_value = 0

        tree.bind(on_node_expand=self._main_screen.on_node_expanded)

        logging.debug("Building simple nodes...")
        self._add_intro_node(tree)
        the_stories_node = self._add_the_stories_node(tree)
        self._add_search_node(tree)
        self._add_appendix_node(tree)
        self._add_index_node(tree)

        logging.debug("Starting asynchronous build of all story nodes...")
        # This is the single entry point for the entire asynchronous build.
        self._build_story_nodes_concurrently(tree, the_stories_node)

        tree.bind(minimum_height=tree.setter("height"))

    def _inc_progress_bar(self):
        self._main_screen.loading_data_popup.progress_bar_value += 1

    def _build_story_nodes_concurrently(
        self, tree: ReaderTreeView, parent_node: ButtonTreeViewNode
    ):
        """
        Dispatches all heavy build tasks to run concurrently on the Kivy
        scheduler and uses a counter to detect when all tasks are complete.
        """
        self._tree_build_timing = Timing(datetime.now())

        # Create ONE counter for all concurrent tasks, passing the final callback.
        concurrent_task_counter = _CompletionCounter(on_all_finished=self._finished_all_nodes)

        # 1. Create main parent nodes synchronously
        chrono_node = self._create_and_add_simple_node(
            tree,
            CHRONOLOGICAL_NODE_TEXT,
            self._main_screen.on_chrono_pressed,
            True,
            StoryGroupTreeViewNode,
            parent_node,
        )
        series_node = self._create_and_add_simple_node(
            tree,
            SERIES_NODE_TEXT,
            self._main_screen.on_series_pressed,
            True,
            StoryGroupTreeViewNode,
            parent_node,
        )
        categories_node = self._create_and_add_simple_node(
            tree,
            CATEGORIES_NODE_TEXT,
            self._main_screen.on_categories_pressed,
            True,
            StoryGroupTreeViewNode,
            parent_node,
        )

        # 2. Dispatch the Chronological build task
        logging.debug("Dispatching the Chronological node build tasks...")
        concurrent_task_counter.start_task()
        chrono_gen = self._add_chrono_year_range_nodes_gen(tree, chrono_node)
        self._run_generator(chrono_gen, on_finish=concurrent_task_counter.finish_task)

        # 3. Handle Series nodes: create parents synchronously, populate children concurrently
        logging.debug(
            "Creating Series parent nodes to preserve order and dispatching population tasks..."
        )
        for series_name, on_pressed in self._all_series_pressed_funcs.items():
            # To guarantee correct series order, synchronously create the parent node
            # for the series' child titles.
            title_list = self._main_screen.title_lists[series_name]
            series_text = get_markup_text_with_num_titles(series_name, len(title_list))
            new_series_node = StoryGroupTreeViewNode(text=series_text)
            new_series_node.bind(on_press=on_pressed)
            tree.add_node(new_series_node, parent=series_node)

            # Dispatch a concurrent task to populate this new node's children.
            concurrent_task_counter.start_task()
            gen = self._populate_series_node_gen(tree, series_name, new_series_node)
            self._run_generator(gen, on_finish=concurrent_task_counter.finish_task)

        # 4. Dispatch all the Category build tasks to run concurrently
        logging.debug("Dispatching all the Category nodes build tasks...")
        for category in TagCategories:
            concurrent_task_counter.start_task()

            # We need a small wrapper generator to create the sub-parent node.
            def category_gen_wrapper(cat_to_build):
                new_node = self._create_and_add_simple_node(
                    tree,
                    cat_to_build.value,
                    self._main_screen.on_category_pressed,
                    True,
                    StoryGroupTreeViewNode,
                    categories_node,
                )
                yield from self._add_category_node_gen(tree, cat_to_build, new_node)

            gen = category_gen_wrapper(category)
            self._run_generator(gen, on_finish=concurrent_task_counter.finish_task)

    # --- Population Generators ---

    def _populate_series_node_gen(
        self, tree: ReaderTreeView, series_name: str, parent_node: ButtonTreeViewNode
    ) -> Generator[None, None, None]:
        """Populates the children of a pre-existing series node."""
        if series_name == SERIES_CS:
            yield from self._populate_cs_node_gen(tree, parent_node)
        elif series_name == SERIES_USA:
            yield from self._populate_us_node_gen(tree, parent_node)
        else:
            yield from self._populate_simple_series_node_gen(series_name, tree, parent_node)

    def _populate_simple_series_node_gen(
        self, series_name: str, tree: ReaderTreeView, parent_node: ButtonTreeViewNode
    ) -> Generator[None, None, None]:
        """Populates a simple series node with its title list."""
        title_list = self._main_screen.title_lists[series_name]
        yield from self._add_fanta_info_story_nodes_gen(tree, title_list, parent_node)

    def _populate_cs_node_gen(
        self, tree: ReaderTreeView, parent_node: ButtonTreeViewNode
    ) -> Generator[None, None, None]:
        """Populates a CS series node with its year-range children."""
        yield from self._populate_splittable_series_node_gen(
            tree,
            parent_node,
            self._main_screen.filtered_title_lists.cs_year_ranges,
            self._add_cs_year_range_node_gen,
        )

    def _populate_us_node_gen(
        self, tree: ReaderTreeView, parent_node: ButtonTreeViewNode
    ) -> Generator[None, None, None]:
        """Populates a US series node with its year-range children."""
        yield from self._populate_splittable_series_node_gen(
            tree,
            parent_node,
            self._main_screen.filtered_title_lists.us_year_ranges,
            self._add_us_year_range_node_gen,
        )

    @staticmethod
    def _populate_splittable_series_node_gen(
        tree: ReaderTreeView,
        parent_node: ButtonTreeViewNode,
        year_ranges: List[Tuple[int, int]],
        add_year_range_node_gen_func: Callable[..., Generator[None, None, None]],
    ) -> Generator[None, None, None]:
        """Populates a series node that is split by year ranges."""
        for year_range in year_ranges:
            yield from add_year_range_node_gen_func(tree, year_range, parent_node)

    # --- Child Node Creation Generators ---

    def _add_chrono_year_range_nodes_gen(
        self, tree: ReaderTreeView, parent_node: ButtonTreeViewNode
    ) -> Generator[None, None, None]:
        """Generator to add all chronological year range nodes."""
        year_ranges = self._main_screen.filtered_title_lists.chrono_year_ranges
        for year_range in year_ranges:
            yield from self._add_chrono_year_range_node_and_child_nodes_gen(
                tree, year_range, parent_node
            )

    def _add_chrono_year_range_node_and_child_nodes_gen(
        self, tree: ReaderTreeView, year_range: Tuple[int, int], parent_node: ButtonTreeViewNode
    ) -> Generator[None, None, None]:
        new_node, year_range_titles = self._add_chrono_year_range_node(
            tree, year_range, parent_node
        )
        yield from self._add_fanta_info_story_nodes_gen(tree, year_range_titles, new_node)
        self.chrono_year_range_nodes[year_range] = new_node

    def _add_category_node_gen(
        self, tree: ReaderTreeView, category: TagCategories, parent_node: ButtonTreeViewNode
    ) -> Generator[None, None, None]:
        for tag_or_group in BARKS_TAG_CATEGORIES[category]:
            if isinstance(tag_or_group, Tags):
                yield from self._add_tag_node_gen(tree, tag_or_group, parent_node)
            elif isinstance(tag_or_group, TagGroups):
                logging.debug(
                    f'Got tag group: "{tag_or_group.name}".'
                    f' Adding tag group node under parent "{parent_node.text}".'
                )
                yield from self._add_tag_group_node_gen(tree, tag_or_group, parent_node)

    def _add_tag_group_node_gen(
        self,
        tree: ReaderTreeView,
        tag_group: TagGroups,
        parent_node: ButtonTreeViewNode,
    ) -> Generator[None, None, None]:
        new_node = TagGroupStoryGroupTreeViewNode(
            tag_group, text=get_bold_markup_text(tag_group.value)
        )

        for tag in BARKS_TAG_GROUPS[tag_group]:
            yield from self._add_tag_node_gen(tree, tag, new_node)

        tree.add_node(new_node, parent=parent_node)

    def _add_tag_node_gen(
        self, tree: ReaderTreeView, tag: Tags, parent_node: ButtonTreeViewNode
    ) -> Generator[None, None, None]:
        titles = get_tagged_titles(tag)
        new_node = TagStoryGroupTreeViewNode(
            tag, text=get_markup_text_with_num_titles(tag.value, len(titles))
        )
        yield from self._add_title_nodes_gen(tree, titles, new_node)
        tree.add_node(new_node, parent=parent_node)

    def _add_title_nodes_gen(
        self, tree: ReaderTreeView, titles: List[Titles], parent_node: ButtonTreeViewNode
    ) -> Generator[None, None, None]:
        for i, title in enumerate(titles):
            # TODO: Very roundabout way to get fanta info
            title_str = BARKS_TITLES[title]
            if title_str in self._main_screen.all_fanta_titles:
                title_info = self._main_screen.all_fanta_titles[title_str]
                node = TitleTreeViewNode.create_from_fanta_info(
                    title_info, self._main_screen.on_title_row_button_pressed
                )
                tree.add_node(node, parent=parent_node)

            self._inc_progress_bar()

            if (i + 1) % self.BUILD_BATCH_SIZE == 0:
                yield

    def _add_cs_year_range_node_gen(
        self, tree: ReaderTreeView, year_range: Tuple[int, int], parent_node: ButtonTreeViewNode
    ) -> Generator[None, None, None]:
        new_node, year_range_titles = self._create_and_add_year_range_node(
            tree,
            year_range,
            self._main_screen.on_cs_year_range_pressed,
            FilteredTitleLists.get_cs_range_str_from_str,
            self._get_cs_year_range_extra_text,
            CsYearRangeTreeViewNode,
            parent_node,
        )
        yield from self._add_fanta_info_story_nodes_gen(tree, year_range_titles, new_node)

    def _add_us_year_range_node_gen(
        self, tree: ReaderTreeView, year_range: Tuple[int, int], parent_node: ButtonTreeViewNode
    ) -> Generator[None, None, None]:
        new_node, year_range_titles = self._create_and_add_year_range_node(
            tree,
            year_range,
            self._main_screen.on_us_year_range_pressed,
            FilteredTitleLists.get_us_range_str_from_str,
            self._get_us_year_range_extra_text,
            UsYearRangeTreeViewNode,
            parent_node,
        )
        yield from self._add_fanta_info_story_nodes_gen(tree, year_range_titles, new_node)

    def _add_fanta_info_story_nodes_gen(
        self,
        tree: ReaderTreeView,
        title_info_list: List[FantaComicBookInfo],
        parent_node: ButtonTreeViewNode,
    ) -> Generator[None, None, None]:
        for i, title_info in enumerate(title_info_list):
            node = TitleTreeViewNode.create_from_fanta_info(
                title_info, self._main_screen.on_title_row_button_pressed
            )
            tree.add_node(node, parent=parent_node)

            self._inc_progress_bar()

            if (i + 1) % self.BUILD_BATCH_SIZE == 0:
                yield

    # --- Synchronous Helper Methods ---

    def _add_intro_node(self, tree: ReaderTreeView):
        self._create_and_add_simple_node(tree, INTRO_NODE_TEXT, self._main_screen.on_intro_pressed)

    def _add_the_stories_node(self, tree: ReaderTreeView) -> MainTreeViewNode:
        return self._create_and_add_simple_node(
            tree, THE_STORIES_NODE_TEXT, self._main_screen.on_the_stories_pressed
        )

    def _add_search_node(self, tree: ReaderTreeView):
        search_node = self._create_and_add_simple_node(
            tree, SEARCH_NODE_TEXT, self._main_screen.on_search_pressed
        )

        self._create_and_add_title_search_box_node(tree, search_node)
        self._create_and_add_tag_search_box_node(tree, search_node)

    def _add_appendix_node(self, tree: ReaderTreeView):
        appendix_node = self._create_and_add_simple_node(
            tree, APPENDIX_NODE_TEXT, self._main_screen.on_appendix_pressed
        )

        self._create_and_add_simple_node(
            tree,
            APPENDIX_CENSORSHIP_FIXES_NODE_TEXT,
            self._main_screen.on_appendix_censorship_fixes_pressed,
            parent_node=appendix_node,
        )

    def _add_index_node(self, tree: ReaderTreeView):
        self._create_and_add_simple_node(tree, INDEX_NODE_TEXT, self._main_screen.on_index_pressed)

    def _add_chrono_year_range_node(
        self, tree: ReaderTreeView, year_range: Tuple[int, int], parent_node: ButtonTreeViewNode
    ) -> Tuple[ButtonTreeViewNode, List[FantaComicBookInfo]]:
        return self._create_and_add_year_range_node(
            tree,
            year_range,
            self._main_screen.on_year_range_pressed,
            lambda x: x,
            lambda title_list: str(len(title_list)),
            YearRangeTreeViewNode,
            parent_node,
        )

    @staticmethod
    def _get_cs_year_range_extra_text(title_list: List[FantaComicBookInfo]) -> str:
        first_issue = min(
            title_list, key=lambda x: x.comic_book_info.issue_number
        ).comic_book_info.issue_number
        last_issue = max(
            title_list, key=lambda x: x.comic_book_info.issue_number
        ).comic_book_info.issue_number

        return f"WDCS {first_issue}-{last_issue}"

    @staticmethod
    def _get_us_year_range_extra_text(title_list: List[FantaComicBookInfo]) -> str:
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
    def _create_and_add_simple_node(
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

    def _create_and_add_title_search_box_node(
        self, tree: ReaderTreeView, parent_node: ButtonTreeViewNode
    ):
        new_node = TitleSearchBoxTreeViewNode(self._main_screen.title_search)

        new_node.bind(on_title_search_box_pressed=self._main_screen.on_title_search_box_pressed)
        new_node.bind(
            on_title_search_box_title_changed=self._main_screen.on_title_search_box_title_changed
        )

        return tree.add_node(new_node, parent=parent_node)

    def _create_and_add_tag_search_box_node(
        self, tree: ReaderTreeView, parent_node: ButtonTreeViewNode
    ):
        new_node = TagSearchBoxTreeViewNode(self._main_screen.title_search)

        new_node.bind(on_tag_search_box_pressed=self._main_screen.on_tag_search_box_pressed)
        new_node.bind(
            on_tag_search_box_text_changed=self._main_screen.on_tag_search_box_text_changed
        )
        new_node.bind(on_tag_search_box_tag_changed=self._main_screen.on_tag_search_box_tag_changed)
        new_node.bind(
            on_tag_search_box_title_changed=self._main_screen.on_tag_search_box_title_changed
        )

        return tree.add_node(new_node, parent=parent_node)

    def _create_and_add_year_range_node(
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
        year_range_titles = self._main_screen.title_lists[year_range_key]

        year_range_extra_text = get_year_range_extra_text_func(year_range_titles)
        year_range_text = get_markup_text_with_extra(year_range_str, year_range_extra_text)

        new_node = node_class(text=year_range_text)
        new_node.bind(on_press=on_press_handler)

        new_node = tree.add_node(new_node, parent=parent_node)

        return new_node, year_range_titles

    @staticmethod
    def _run_generator(gen: Generator[None, None, None], on_finish: Callable[[], None] = None):
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

    def _finished_all_nodes(self) -> None:
        self._tree_build_timing.end_time = datetime.now()
        time_in_secs = self._tree_build_timing.get_elapsed_time_in_seconds()

        logging.debug(
            f"Finished loading all nodes in {time_in_secs}s:"
            f" {self._main_screen.loading_data_popup.progress_bar_value}"
            f" nodes processed, progress bar max"
            f" = {self._main_screen.loading_data_popup.ids.loading_data_progress_bar.max}."
        )

        self._main_screen.reader_tree_events.finished_building()
