import logging
import os
from collections import OrderedDict
from dataclasses import dataclass
from typing import Union, Dict, List, Callable

from kivy._clock import ClockEvent
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.properties import StringProperty, ColorProperty, NumericProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import Spinner
from kivy.uix.treeview import TreeViewNode

from background_views import BackgroundViews, ViewStates
from barks_fantagraphics.barks_payments import BARKS_PAYMENTS
from barks_fantagraphics.barks_tags import (
    BARKS_TAG_CATEGORIES_DICT,
    Tags,
    is_tag_enum,
)
from barks_fantagraphics.barks_titles import ComicBookInfo, Titles, get_title_dict, BARKS_TITLES
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.fanta_comics_info import (
    FantaComicBookInfo,
    ALL_FANTA_COMIC_BOOK_INFO,
    ALL_LISTS,
    SERIES_CS,
    SERIES_DDA,
    SERIES_MISC,
    SERIES_GG,
    SERIES_USS,
    SERIES_DDS,
    SERIES_USA,
)
from barks_fantagraphics.pages import (
    get_srce_and_dest_pages_in_order,
    FRONT_MATTER_PAGES,
    ROMAN_NUMERALS,
)
from barks_fantagraphics.title_search import BarksTitleSearch
from comic_book_reader import PageInfo, ComicBookReader
from file_paths import (
    get_comic_inset_file,
    get_edited_version,
    get_barks_reader_app_icon_file,
    get_barks_reader_up_arrow_file,
    get_barks_reader_action_bar_background_file,
    get_barks_reader_action_bar_group_background_file,
    get_barks_reader_transparent_blank_file,
    get_barks_reader_user_data_file,
)
from filtered_title_lists import FilteredTitleLists
from random_title_images import (
    ImageInfo,
    RandomTitleImages,
    FIT_MODE_COVER,
    FIT_MODE_CONTAIN,
    ALL_BUT_ORIGINAL_ART,
)
from reader_consts_and_types import (
    THE_STORIES_NODE_TEXT,
    CHRONOLOGICAL_NODE_TEXT,
    SERIES_NODE_TEXT,
    CATEGORIES_NODE_TEXT,
    SEARCH_NODE_TEXT,
    INTRO_NODE_TEXT,
    APPENDIX_NODE_TEXT,
    INDEX_NODE_TEXT,
    ACTION_BAR_SIZE_Y,
)
from reader_formatter import ReaderFormatter, get_clean_text_without_extra, LONG_TITLE_SPLITS
from reader_ui_classes import (
    ReaderTreeView,
    ReaderTreeBuilderEventDispatcher,
    LoadingDataPopup,
    ButtonTreeViewNode,
    MainTreeViewNode,
    YearRangeTreeViewNode,
    CsYearRangeTreeViewNode,
    UsYearRangeTreeViewNode,
    StoryGroupTreeViewNode,
    TitleSearchBoxTreeViewNode,
    TagSearchBoxTreeViewNode,
)


@dataclass
class ComicBookPageInfo:
    page_map: OrderedDict[str, PageInfo]
    last_body_page: str
    last_page: str


class MainScreen(BoxLayout, Screen):
    MAIN_TITLE_BACKGROUND_COLOR = (1, 1, 1, 0.05)
    MAIN_TITLE_COLOR = (1, 1, 0, 1)
    MAIN_TITLE_FONT_NAME = "Carl Barks Script"
    MAIN_TITLE_FONT_SIZE = sp(30)
    main_title_text = StringProperty()

    TITLE_INFO_LABEL_COLOR = (1.0, 0.99, 0.9, 1.0)
    TITLE_EXTRA_INFO_LABEL_COLOR = (1.0, 1.0, 1.0, 1.0)
    title_info_text = StringProperty()
    extra_title_info_text = StringProperty()
    title_page_image_source = StringProperty()
    APP_ICON_FILE = get_barks_reader_app_icon_file()
    UP_ARROW_FILE = get_barks_reader_up_arrow_file()
    UP_ARROW_WIDTH = dp(20)
    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
    ACTION_BAR_BACKGROUND_PATH = get_barks_reader_action_bar_background_file()
    ACTION_BAR_GROUP_BACKGROUND_PATH = get_barks_reader_action_bar_group_background_file()
    ACTION_BAR_TRANSPARENT_BLANK_PATH = get_barks_reader_transparent_blank_file()
    ACTION_BAR_BACKGROUND_COLOR = (0.6, 0.7, 0.2, 1)
    ACTION_BUTTON_BACKGROUND_COLOR = (0.6, 1.0, 0.2, 1)

    DEBUG_BACKGROUND_OPACITY = 0

    intro_text = StringProperty()
    intro_text_opacity = NumericProperty(0.0)

    top_view_image_source = StringProperty()
    top_view_image_fit_mode = StringProperty(FIT_MODE_COVER)
    top_view_image_color = ColorProperty()
    top_view_image_opacity = NumericProperty(0.0)

    bottom_view_title_opacity = NumericProperty(0.0)
    bottom_view_title_image_source = StringProperty()
    bottom_view_title_image_fit_mode = StringProperty(FIT_MODE_COVER)
    bottom_view_title_image_color = ColorProperty()
    bottom_view_fun_image_opacity = NumericProperty(0.0)
    bottom_view_fun_image_source = StringProperty()
    bottom_view_fun_image_fit_mode = StringProperty(FIT_MODE_CONTAIN)
    bottom_view_fun_image_color = ColorProperty()

    def __init__(
        self,
        comics_database: ComicsDatabase,
        reader_tree_events: ReaderTreeBuilderEventDispatcher,
        filtered_title_lists: FilteredTitleLists,
        switch_to_comic_reader: Callable[[], None],
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.comics_database = comics_database
        self.switch_to_comic_book_reader = switch_to_comic_reader
        self.filtered_title_lists: FilteredTitleLists = filtered_title_lists
        self.title_lists: Dict[str, List[FantaComicBookInfo]] = (
            filtered_title_lists.get_title_lists()
        )
        self.title_dict: Dict[str, Titles] = get_title_dict()
        self.title_search = BarksTitleSearch()
        self.all_fanta_titles = ALL_FANTA_COMIC_BOOK_INFO
        self.random_title_images = RandomTitleImages()

        self.store = JsonStore(get_barks_reader_user_data_file())

        self.formatter = ReaderFormatter()
        self.fanta_info: Union[FantaComicBookInfo, None] = None
        self.year_range_nodes = None

        self.loading_data_popup = LoadingDataPopup()
        self.loading_data_popup.on_open = self.on_loading_data_popup_open
        self.loading_data_popup_image_event: Union[ClockEvent, None] = None

        self.reader_tree_events = reader_tree_events
        self.reader_tree_events.bind(on_finished_building_event=self.on_tree_build_finished)

        self.comic_book_reader: Union[ComicBookReader, None] = None

        self.top_view_image_info: ImageInfo = ImageInfo()
        self.bottom_view_fun_image_info: ImageInfo = ImageInfo()
        self.bottom_view_title_image_info: ImageInfo = ImageInfo()

        self.background_views = BackgroundViews(
            self.all_fanta_titles, self.title_lists, self.random_title_images
        )
        self.update_background_views(ViewStates.PRE_INIT)

    def on_loading_data_popup_open(self) -> None:
        self.set_new_loading_data_popup_image()
        self.loading_data_popup_image_event = Clock.schedule_interval(
            lambda dt: self.set_new_loading_data_popup_image(), 0.5
        )

    def set_new_loading_data_popup_image(self) -> None:
        self.loading_data_popup.splash_image_path = (
            self.random_title_images.get_loading_screen_random_image(self.title_lists[ALL_LISTS])
        )
        logging.debug(f'New loading popup image: "{self.loading_data_popup.splash_image_path}".')

    def on_tree_build_finished(self, _instance):
        logging.debug(f"'on_finished_building_event' received: dismiss the popup.")
        if self.loading_data_popup_image_event:
            self.loading_data_popup_image_event.cancel()

        # Linger on the last image...
        self.loading_data_popup.title = "All titles loaded!"
        Clock.schedule_once(lambda dt: self.loading_data_popup.dismiss(), 2)

        self.update_background_views(ViewStates.INITIAL)

    def on_action_bar_collapse(self):
        something_was_open = False
        for node in self.ids.reader_tree_view.iterate_open_nodes():
            if node.is_open:
                self.ids.reader_tree_view.toggle_node(node)
                self.close_open_nodes(node)
                something_was_open = True

        if something_was_open:
            self.update_background_views(ViewStates.INITIAL)

    def close_open_nodes(self, start_node: TreeViewNode) -> None:
        for node in start_node.nodes:
            if node.is_open:
                self.ids.reader_tree_view.toggle_node(node)
                self.close_open_nodes(node)

    def on_action_bar_change_view_images(self):
        self.change_background_views()

    def on_action_bar_goto(self, button: Button):
        node = self.find_node(self.ids.reader_tree_view.root, button.text)
        if node:
            self.close_open_nodes(self.ids.reader_tree_view.root)
            self.open_all_parent_nodes(node)
            self.goto_node(node)

    @staticmethod
    def find_node(start_node: TreeViewNode, node_text: str):
        nodes_to_visit = start_node.nodes.copy()

        while nodes_to_visit:
            current_node = nodes_to_visit.pop()
            if not hasattr(current_node, "text"):
                continue
            current_node_text = get_clean_text_without_extra(current_node.text)
            if current_node_text == node_text:
                return current_node
            nodes_to_visit.extend(current_node.nodes)

        return None

    def on_action_bar_pressed(self, button: Button):
        pass

    def on_goto_top_view_title(self) -> None:
        self.goto_chrono_title(self.top_view_image_info)

    def on_goto_fun_view_title(self, _button: Button) -> None:
        self.goto_chrono_title(self.bottom_view_fun_image_info)

    def goto_chrono_title(self, image_info: ImageInfo) -> None:
        title_fanta_info = self.get_fanta_info(image_info.from_title)

        year_nodes = self.year_range_nodes[
            self.filtered_title_lists.get_year_range_from_info(title_fanta_info)
        ]
        self.open_all_parent_nodes(year_nodes)

        title_node = self.find_title_node(year_nodes, image_info.from_title)
        self.goto_node(title_node, scroll_to=True)

        self.title_row_selected(title_fanta_info, image_info.filename)

    def goto_node(self, node: TreeViewNode, scroll_to=False) -> None:
        def show_node(n):
            self.ids.reader_tree_view.select_node(n)
            if scroll_to:
                self.scroll_to_node(n)

        Clock.schedule_once(lambda dt, item=node: show_node(item))

    def scroll_to_node(self, node: TreeViewNode) -> None:
        Clock.schedule_once(lambda dt: self.ids.scroll_view.scroll_to(node, padding=50), 0)

    def get_fanta_info(self, title: Titles) -> FantaComicBookInfo:
        # TODO: Very roundabout way to get fanta info
        title_str = BARKS_TITLES[title]
        return self.all_fanta_titles[title_str]

    @staticmethod
    def find_title_node(start_node: TreeViewNode, target_title: Titles):
        nodes_to_visit = start_node.nodes.copy()

        while nodes_to_visit:
            current_node = nodes_to_visit.pop()
            node_title = current_node.get_title()
            if node_title == target_title:
                return current_node
            nodes_to_visit.extend(current_node.nodes)

        return None

    def title_row_selected(self, new_fanta_info: FantaComicBookInfo, title_image_file: str):
        self.fanta_info = new_fanta_info
        self.set_title(title_image_file)

        self.update_background_views(ViewStates.ON_TITLE_NODE)

    def open_all_parent_nodes(self, node: TreeViewNode) -> None:
        # Get all the parent nodes first, then open from top parent down to last child.
        parent_nodes = []
        parent_node = node
        while parent_node and isinstance(parent_node, TreeViewNode):
            parent_nodes.append(parent_node)
            parent_node = parent_node.parent_node

        for parent_node in reversed(parent_nodes):
            if not parent_node.is_open:
                self.ids.reader_tree_view.toggle_node(parent_node)

    def on_node_expanded(self, _tree: ReaderTreeView, node: ButtonTreeViewNode):
        logging.debug(f'Node expanded: "{node.text}" ({type(node)}).')

        if type(node) == YearRangeTreeViewNode:
            self.update_background_views(ViewStates.ON_YEAR_RANGE_NODE, year_range=node.text)
        elif type(node) == CsYearRangeTreeViewNode:
            self.update_background_views(ViewStates.ON_CS_YEAR_RANGE_NODE, cs_year_range=node.text)
        elif type(node) == UsYearRangeTreeViewNode:
            self.update_background_views(ViewStates.ON_US_YEAR_RANGE_NODE, us_year_range=node.text)
        elif isinstance(node, MainTreeViewNode):
            if node.text == INTRO_NODE_TEXT:
                self.update_background_views(ViewStates.ON_INTRO_NODE)
            elif node.text == THE_STORIES_NODE_TEXT:
                self.update_background_views(ViewStates.ON_THE_STORIES_NODE)
            elif node.text == SEARCH_NODE_TEXT:
                self.update_background_views(ViewStates.ON_SEARCH_NODE)
            elif node.text == APPENDIX_NODE_TEXT:
                self.update_background_views(ViewStates.ON_APPENDIX_NODE)
            elif node.text == INDEX_NODE_TEXT:
                self.update_background_views(ViewStates.ON_INDEX_NODE)
        elif isinstance(node, StoryGroupTreeViewNode):
            node_text = get_clean_text_without_extra(node.text)
            logging.debug(f'Clean node text: "{node_text}"')
            if node_text == CHRONOLOGICAL_NODE_TEXT:
                self.update_background_views(ViewStates.ON_CHRONO_BY_YEAR_NODE)
            elif node_text == SERIES_NODE_TEXT:
                self.update_background_views(ViewStates.ON_SERIES_NODE)
            elif node_text == CATEGORIES_NODE_TEXT:
                self.update_background_views(ViewStates.ON_CATEGORIES_NODE)
            elif node_text == SERIES_CS:
                self.update_background_views(ViewStates.ON_CS_NODE)
            elif node_text == SERIES_DDA:
                self.update_background_views(ViewStates.ON_DD_NODE)
            elif node_text == SERIES_USA:
                self.update_background_views(ViewStates.ON_US_NODE)
            elif node_text == SERIES_DDS:
                self.update_background_views(ViewStates.ON_DDS_NODE)
            elif node_text == SERIES_USS:
                self.update_background_views(ViewStates.ON_USS_NODE)
            elif node_text == SERIES_GG:
                self.update_background_views(ViewStates.ON_GG_NODE)
            elif node_text == SERIES_MISC:
                self.update_background_views(ViewStates.ON_MISC_NODE)
            elif node_text in BARKS_TAG_CATEGORIES_DICT:
                self.update_background_views(ViewStates.ON_CATEGORY_NODE, category=node_text)
            elif is_tag_enum(node_text):
                logging.debug(f'Tag node expanded: "{node_text}".')
                self.update_background_views(ViewStates.ON_TAG_NODE, tag=Tags(node_text))

        self.scroll_to_node(node.nodes[0])

    def on_intro_pressed(self, _button: Button):
        self.update_background_views(ViewStates.ON_INTRO_NODE)

        self.intro_text = "hello line 1\nhello line 2\nhello line 3\n"

    def on_the_stories_pressed(self, _button: Button):
        self.update_background_views(ViewStates.ON_THE_STORIES_NODE)

    def on_search_pressed(self, _button: Button):
        self.update_background_views(ViewStates.ON_SEARCH_NODE)

    def on_title_search_box_pressed(self, instance: TitleSearchBoxTreeViewNode):
        logging.debug(f"Title search box pressed: {instance}.")

        if not instance.get_current_title():
            logging.debug("Have not got title search box text yet.")
            self.update_background_views(ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET)
        elif self.background_views.get_view_state() != ViewStates.ON_TITLE_SEARCH_BOX_NODE:
            logging.debug(
                f"Forcing title search box change:"
                f" view state = {self.background_views.get_view_state()},"
                f' title search box text = "{instance.get_current_title()}",'
                f' title spinner text = "{instance.ids.title_spinner.text}"'
            )
            self.on_title_search_box_title_changed(
                instance.ids.title_spinner, instance.ids.title_spinner.text
            )

    def on_title_search_box_title_changed(self, _spinner: Spinner, title_str: str):
        logging.debug(f'Title search box title changed: "{title_str}".')

        if not title_str:
            self.update_background_views(ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET)
        elif self.update_title(title_str):
            self.update_background_views(ViewStates.ON_TITLE_SEARCH_BOX_NODE)
        else:
            self.update_background_views(ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET)

    def on_tag_search_box_pressed(self, instance: TagSearchBoxTreeViewNode):
        logging.debug(f"Tag search box pressed: {instance}.")

        if not instance.get_current_tag():
            logging.debug("Have not got tag search box text yet.")
            self.update_background_views(ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET)
        elif self.background_views.get_view_state() != ViewStates.ON_TAG_SEARCH_BOX_NODE:
            logging.debug(
                f"Forcing tag search box change:"
                f" view state = {self.background_views.get_view_state()},"
                f' tag search box text = "{instance.get_current_tag()}",'
                f' tag title spinner text = "{instance.ids.tag_title_spinner.text}"'
            )
            self.on_tag_search_box_title_changed(
                instance.ids.tag_title_spinner, instance.ids.tag_title_spinner.text
            )

    def on_tag_search_box_text_changed(self, instance: TagSearchBoxTreeViewNode, text: str):
        logging.debug(f'Tag search box text changed: text: "{text}".')

        if not instance.get_current_title():
            self.update_background_views(ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET)

    def on_tag_search_box_tag_changed(self, instance: TagSearchBoxTreeViewNode, tag_str: str):
        logging.debug(f'Tag search box tag changed: "{tag_str}".')

        if not tag_str:
            return

        if not instance.get_current_title():
            self.update_background_views(ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET)

    def on_tag_search_box_title_changed(self, _instance, title_str: str):
        logging.debug(f'Tag search box title changed: "{title_str}".')

        if not title_str:
            self.update_background_views(ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET)
        elif self.update_title(title_str):
            self.update_background_views(ViewStates.ON_TAG_SEARCH_BOX_NODE)
        else:
            self.update_background_views(ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET)

    def update_title(self, title_str: str) -> bool:
        logging.debug(f'Update title: "{title_str}".')
        assert title_str != ""

        title_str = ComicBookInfo.get_title_str_from_display_title(title_str)

        if title_str not in self.all_fanta_titles:
            logging.debug(f'Update title: Not configured yet: "{title_str}".')
            return False

        self.fanta_info = self.all_fanta_titles[title_str]
        self.set_title()
        return True

    def on_appendix_pressed(self, _button: Button):
        self.update_background_views(ViewStates.ON_APPENDIX_NODE)

    def on_index_pressed(self, _button: Button):
        self.update_background_views(ViewStates.ON_INDEX_NODE)

    def on_chrono_pressed(self, _button: Button):
        self.update_background_views(ViewStates.ON_CHRONO_BY_YEAR_NODE)

    def on_year_range_pressed(self, button: Button):
        self.update_background_views(ViewStates.ON_YEAR_RANGE_NODE, year_range=button.text)

    def on_cs_year_range_pressed(self, button: Button):
        self.update_background_views(ViewStates.ON_CS_YEAR_RANGE_NODE, cs_year_range=button.text)

    def on_us_year_range_pressed(self, button: Button):
        self.update_background_views(ViewStates.ON_US_YEAR_RANGE_NODE, us_year_range=button.text)

    def on_series_pressed(self, _button: Button):
        self.update_background_views(ViewStates.ON_SERIES_NODE)

    def cs_pressed(self, _button: Button):
        self.update_background_views(ViewStates.ON_CS_NODE)

    def dd_pressed(self, _button: Button):
        self.update_background_views(ViewStates.ON_DD_NODE)

    def us_pressed(self, _button: Button):
        self.update_background_views(ViewStates.ON_US_NODE)

    def dds_pressed(self, _button: Button):
        self.update_background_views(ViewStates.ON_DDS_NODE)

    def uss_pressed(self, _button: Button):
        self.update_background_views(ViewStates.ON_USS_NODE)

    def gg_pressed(self, _button: Button):
        self.update_background_views(ViewStates.ON_GG_NODE)

    def misc_pressed(self, _button: Button):
        self.update_background_views(ViewStates.ON_MISC_NODE)

    def on_categories_pressed(self, _button: Button):
        self.update_background_views(ViewStates.ON_CATEGORIES_NODE)

    def on_category_pressed(self, button: Button):
        self.update_background_views(ViewStates.ON_CATEGORY_NODE, category=button.text)

    def on_title_row_button_pressed(self, button: Button):
        self.fanta_info = button.parent.fanta_info
        self.set_title()

        self.update_background_views(ViewStates.ON_TITLE_NODE)

    def change_background_views(self) -> None:
        self.update_background_views(
            self.background_views.get_view_state(),
            self.background_views.get_current_category(),
            self.background_views.get_current_year_range(),
            self.background_views.get_current_cs_year_range(),
            self.background_views.get_current_us_year_range(),
            self.background_views.get_current_tag(),
        )

    def update_background_views(
        self,
        tree_node: ViewStates,
        category: str = "",
        year_range: str = "",
        cs_year_range: str = "",
        us_year_range: str = "",
        tag: Union[None, Tags] = None,
    ) -> None:
        self.background_views.set_current_category(category)
        self.background_views.set_current_year_range(get_clean_text_without_extra(year_range))
        self.background_views.set_current_cs_year_range(get_clean_text_without_extra(cs_year_range))
        self.background_views.set_current_us_year_range(get_clean_text_without_extra(us_year_range))
        self.background_views.set_current_tag(tag)

        self.background_views.set_view_state(tree_node)

        self.intro_text_opacity = 0.0

        self.top_view_image_info = self.background_views.get_top_view_image_info()
        self.top_view_image_opacity = self.background_views.get_top_view_image_opacity()
        self.top_view_image_source = self.top_view_image_info.filename
        self.top_view_image_fit_mode = self.top_view_image_info.fit_mode
        self.top_view_image_color = self.background_views.get_top_view_image_color()

        self.bottom_view_fun_image_opacity = (
            self.background_views.get_bottom_view_fun_image_opacity()
        )
        self.bottom_view_fun_image_info = self.background_views.get_bottom_view_fun_image_info()
        self.bottom_view_fun_image_source = self.bottom_view_fun_image_info.filename
        self.bottom_view_fun_image_fit_mode = self.bottom_view_fun_image_info.fit_mode
        self.bottom_view_fun_image_color = self.background_views.get_bottom_view_fun_image_color()

        self.bottom_view_title_opacity = self.background_views.get_bottom_view_title_opacity()
        self.bottom_view_title_image_info = self.background_views.get_bottom_view_title_image_info()
        self.bottom_view_title_image_source = self.bottom_view_title_image_info.filename
        self.bottom_view_title_image_fit_mode = self.bottom_view_title_image_info.fit_mode
        self.bottom_view_title_image_color = (
            self.background_views.get_bottom_view_title_image_color()
        )

    def set_title(self, title_image_file: str = "") -> None:
        logging.debug(f'Setting title to "{self.fanta_info.comic_book_info.get_title_str()}".')

        if title_image_file:
            title_image_file = get_edited_version(title_image_file)
        else:
            title_image_file = self.random_title_images.get_random_image_for_title(
                self.fanta_info.comic_book_info.get_title_str(),
                ALL_BUT_ORIGINAL_ART,
                use_edited_only=True,
            )
        self.background_views.set_bottom_view_title_image_file(title_image_file)

        payment_info = BARKS_PAYMENTS[self.fanta_info.comic_book_info.title]

        self.main_title_text = self.get_main_title_str()
        self.title_info_text = self.formatter.get_title_info(self.fanta_info, payment_info)
        self.extra_title_info_text = self.formatter.get_extra_title_info(self.fanta_info)
        self.title_page_image_source = get_comic_inset_file(
            self.fanta_info.comic_book_info.title, use_edited_only=True
        )

    def get_main_title_str(self):
        if self.fanta_info.comic_book_info.is_barks_title:
            if self.fanta_info.comic_book_info.title in LONG_TITLE_SPLITS:
                return LONG_TITLE_SPLITS[self.fanta_info.comic_book_info.title]
            return self.fanta_info.comic_book_info.get_title_str()

        return self.fanta_info.comic_book_info.get_title_from_issue_name()

    def on_image_pressed(self):
        if self.fanta_info is None:
            logging.debug(f'Image "{self.title_page_image_source}" pressed. But no title selected.')
            return

        title_str = self.fanta_info.comic_book_info.get_title_str()
        logging.debug(
            f'Image "{self.title_page_image_source}" pressed. Want to load "{title_str}".'
        )

        self.switch_to_comic_book_reader()

        comic_page_info = self.get_comic_page_info(title_str)
        page_to_first_goto = self.get_page_to_first_goto(comic_page_info, title_str)

        self.comic_book_reader.read_comic(
            self.fanta_info, page_to_first_goto, comic_page_info.page_map
        )

    def get_page_to_first_goto(self, comic_page_info: ComicBookPageInfo, title_str: str) -> str:
        if not self.store.exists(title_str):
            return "i"

        last_read_page = self.store.get(title_str)["last_read_page"]
        last_read_page_info = comic_page_info.page_map[last_read_page]

        if (last_read_page_info.page_type in FRONT_MATTER_PAGES) or (
            (last_read_page_info.page_type == PageType.BODY)
            and (last_read_page != comic_page_info.last_body_page)
        ):
            page_to_first_goto = last_read_page
        else:
            page_to_first_goto = "i"

        logging.debug(f'"{title_str}": There was a usable last read page "{page_to_first_goto}".')

        return page_to_first_goto

    def comic_closed(self):
        title_str = self.fanta_info.comic_book_info.get_title_str()
        last_read_page = self.comic_book_reader.get_last_read_page()
        self.store.put(title_str, last_read_page=last_read_page)
        logging.debug(f'"{title_str}": Saved last read page "{last_read_page}".')

    def get_comic_page_info(self, title_str: str) -> ComicBookPageInfo:
        comic = self.comics_database.get_comic_book(title_str)
        pages = get_srce_and_dest_pages_in_order(comic)
        dest_pages = pages.dest_pages

        last_body_page = ""
        last_page = ""
        page_map = OrderedDict()
        body_start_page_num = -1
        orig_page_num = 0
        for page in dest_pages:
            orig_page_num += 1

            if page.page_type not in FRONT_MATTER_PAGES and body_start_page_num == -1:
                body_start_page_num = orig_page_num

            page_info = PageInfo(
                orig_page_num - 1, page.page_type, os.path.basename(page.page_filename)
            )
            if body_start_page_num == -1:
                page_map[ROMAN_NUMERALS[orig_page_num]] = page_info
            else:
                last_page_str = str(orig_page_num - body_start_page_num + 1)
                page_map[last_page_str] = page_info
                if page.page_type == PageType.BODY:
                    last_body_page = last_page_str

        return ComicBookPageInfo(page_map, last_body_page, last_page)
