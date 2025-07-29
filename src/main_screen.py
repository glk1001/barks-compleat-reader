import logging
from random import randrange
from typing import Union, Dict, List

# noinspection PyProtectedMember
from kivy._clock import ClockEvent
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import StringProperty, ColorProperty, NumericProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import Spinner
from kivy.uix.treeview import TreeViewNode

from background_views import BackgroundViews, ViewStates
from barks_fantagraphics.barks_tags import (
    Tags,
    is_tag_enum,
    TagGroups,
    BARKS_TAG_CATEGORIES_DICT,
    BARKS_TAGGED_PAGES,
)
from barks_fantagraphics.barks_titles import ComicBookInfo, Titles, BARKS_TITLES, BARKS_TITLE_DICT
from barks_fantagraphics.comic_book import ComicBook
from barks_fantagraphics.comics_consts import (
    PageType,
    ROMAN_NUMERALS,
    BACK_MATTER_PAGES,
    CARL_BARKS_FONT_NAME,
)
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
from barks_fantagraphics.title_search import BarksTitleSearch
from build_comic_images import ComicBookImageBuilder
from comic_book_page_info import ComicBookPageInfo, ComicBookPageInfoManager
from comic_book_reader import ComicBookReader
from fantagraphics_volumes import WrongFantagraphicsVolumeError, TooManyArchiveFilesError
from filtered_title_lists import FilteredTitleLists
from font_manager import FontManager
from json_settings_manager import SettingsManager, SavedPageInfo
from random_title_images import (
    ImageInfo,
    RandomTitleImages,
    FileTypes,
    FIT_MODE_COVER,
    FIT_MODE_CONTAIN,
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
    APPENDIX_CENSORSHIP_FIXES_NODE_TEXT,
)
from reader_formatter import ReaderFormatter, get_clean_text_without_extra, LONG_TITLE_SPLITS
from reader_settings import ReaderSettings
from reader_tree_view_utils import (
    get_tree_view_node_path,
    find_node_by_path,
    get_tree_view_node_id_text,
    find_tree_view_node,
    find_tree_view_title_node,
)
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
    TagStoryGroupTreeViewNode,
    TagGroupStoryGroupTreeViewNode,
    TitleTreeViewNode,
)
from reader_utils import (
    set_kivy_normal_cursor,
    set_kivy_busy_cursor,
    get_all_files_in_dir,
    read_text_paragraphs,
)
from special_overrides_handler import SpecialFantaOverrides
from system_file_paths import SystemFilePaths
from user_error_handler import UserErrorHandler, ErrorTypes

NODE_TYPE_TO_VIEW_STATE_MAP = {
    YearRangeTreeViewNode: ViewStates.ON_YEAR_RANGE_NODE,
    CsYearRangeTreeViewNode: ViewStates.ON_CS_YEAR_RANGE_NODE,
    UsYearRangeTreeViewNode: ViewStates.ON_US_YEAR_RANGE_NODE,
}

NODE_TEXT_TO_VIEW_STATE_MAP = {
    INTRO_NODE_TEXT: ViewStates.ON_INTRO_NODE,
    THE_STORIES_NODE_TEXT: ViewStates.ON_THE_STORIES_NODE,
    SEARCH_NODE_TEXT: ViewStates.ON_SEARCH_NODE,
    APPENDIX_NODE_TEXT: ViewStates.ON_APPENDIX_NODE,
    APPENDIX_CENSORSHIP_FIXES_NODE_TEXT: ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE,
    INDEX_NODE_TEXT: ViewStates.ON_INDEX_NODE,
    CHRONOLOGICAL_NODE_TEXT: ViewStates.ON_CHRONO_BY_YEAR_NODE,
    SERIES_NODE_TEXT: ViewStates.ON_SERIES_NODE,
    CATEGORIES_NODE_TEXT: ViewStates.ON_CATEGORIES_NODE,
    SERIES_CS: ViewStates.ON_CS_NODE,
    SERIES_DDA: ViewStates.ON_DD_NODE,
    SERIES_USA: ViewStates.ON_US_NODE,
    SERIES_DDS: ViewStates.ON_DDS_NODE,
    SERIES_USS: ViewStates.ON_USS_NODE,
    SERIES_GG: ViewStates.ON_GG_NODE,
    SERIES_MISC: ViewStates.ON_MISC_NODE,
}

COMIC_PAGE_ONE = ROMAN_NUMERALS[1]

TITLE_VIEW_IMAGE_TYPES = {
    t for t in FileTypes if t not in [FileTypes.INSET, FileTypes.ORIGINAL_ART]
}


class MainScreen(BoxLayout, Screen):
    UP_ARROW_WIDTH = dp(20)
    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
    ACTION_BAR_TITLE_COLOR = (0.0, 1.0, 0.0, 1.0)
    app_icon_filepath = StringProperty()
    up_arrow_filepath = StringProperty()
    action_bar_close_icon_filepath = StringProperty()
    action_bar_collapse_icon_filepath = StringProperty()
    action_bar_change_pics_icon_filepath = StringProperty()
    action_bar_settings_icon_filepath = StringProperty()
    action_bar_goto_icon_filepath = StringProperty()
    app_title = StringProperty()

    not_all_titles_loaded = BooleanProperty(False)
    not_all_titles_loaded_msg = StringProperty()

    MAIN_TITLE_BACKGROUND_COLOR = (0.01, 0.01, 0.01, 0.075)
    MAIN_TITLE_COLOR = (1, 1, 0, 1)
    main_title_text = StringProperty()

    TITLE_INFO_LABEL_COLOR = (1.0, 0.99, 0.9, 1.0)
    TITLE_EXTRA_INFO_LABEL_COLOR = (1.0, 1.0, 1.0, 1.0)
    MAX_TITLE_INFO_LEN_BEFORE_SHORTEN = 36
    title_info_text = StringProperty()
    title_extra_info_text = StringProperty()
    title_page_image_source = StringProperty()

    DEBUG_BACKGROUND_OPACITY = 0

    intro_text = StringProperty()
    intro_text_opacity = NumericProperty(0.0)

    appendix_censorship_fixes_text = StringProperty()
    appendix_censorship_fixes_text_opacity = NumericProperty(0.0)

    top_view_image_source = StringProperty()
    top_view_image_fit_mode = StringProperty(FIT_MODE_COVER)
    top_view_image_color = ColorProperty()
    top_view_image_opacity = NumericProperty(0.0)

    bottom_view_title_opacity = NumericProperty(0.0)
    bottom_view_title_image_source = StringProperty()
    bottom_view_title_image_fit_mode = StringProperty(FIT_MODE_COVER)
    bottom_view_title_image_color = ColorProperty()
    bottom_view_title_goto_page_num = StringProperty()
    bottom_view_fun_image_opacity = NumericProperty(0.0)
    bottom_view_fun_image_source = StringProperty()
    bottom_view_fun_image_fit_mode = StringProperty(FIT_MODE_CONTAIN)
    bottom_view_fun_image_color = ColorProperty()
    bottom_view_fun_image_from_title = BooleanProperty(True)

    def __init__(
        self,
        app: App,
        comics_database: ComicsDatabase,
        reader_settings: ReaderSettings,
        reader_tree_events: ReaderTreeBuilderEventDispatcher,
        filtered_title_lists: FilteredTitleLists,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self._app = app
        self._comics_database = comics_database
        self._reader_settings = reader_settings
        self._user_error_handler = UserErrorHandler(app, reader_settings)
        self.filtered_title_lists: FilteredTitleLists = filtered_title_lists
        self.title_lists: Dict[str, List[FantaComicBookInfo]] = (
            filtered_title_lists.get_title_lists()
        )
        self._title_dict: Dict[str, Titles] = BARKS_TITLE_DICT
        self.title_search = BarksTitleSearch()
        self.all_fanta_titles = ALL_FANTA_COMIC_BOOK_INFO
        self._random_title_images = RandomTitleImages(self._reader_settings)

        self._json_settings_manager = SettingsManager(self._reader_settings.get_user_data_path())

        self._formatter = ReaderFormatter()
        self._fanta_info: Union[FantaComicBookInfo, None] = None
        self.year_range_nodes: Union[Dict, None] = None

        self.loading_data_popup = LoadingDataPopup()
        self.loading_data_popup.on_open = self._on_loading_data_popup_open
        self._loading_data_popup_image_event: Union[ClockEvent, None] = None

        self.reader_tree_events = reader_tree_events
        self.reader_tree_events.bind(on_finished_building_event=self._on_tree_build_finished)

        self.comic_book_reader: Union[ComicBookReader, None] = None
        self._comic_page_info_mgr = ComicBookPageInfoManager(
            self._comics_database, self._reader_settings
        )
        self._comic_page_info: Union[ComicBookPageInfo, None] = None

        self._top_view_image_info: ImageInfo = ImageInfo()
        self._bottom_view_fun_image_info: ImageInfo = ImageInfo()
        self._bottom_view_title_image_info: ImageInfo = ImageInfo()

        self._background_views = BackgroundViews(
            self._reader_settings,
            self.all_fanta_titles,
            self.title_lists,
            self._random_title_images,
        )
        self._update_view_for_node(ViewStates.PRE_INIT)

        self._set_action_bar_icons(self._reader_settings.sys_file_paths)

        self._special_fanta_overrides = SpecialFantaOverrides(self._reader_settings)
        self.ids.use_overrides_checkbox.bind(active=self.on_use_overrides_checkbox_changed)

    def fonts_updated(self, font_manager: FontManager) -> None:
        self.app_title = (
            f"[font={CARL_BARKS_FONT_NAME}]"
            f"[size={int(font_manager.app_title_font_size)}]"
            f"{self._app.title}"
        )

    def _set_action_bar_icons(self, sys_paths: SystemFilePaths):
        self.app_icon_filepath = self._get_reader_app_icon_file()
        self.up_arrow_filepath = sys_paths.get_up_arrow_file()
        self.action_bar_close_icon_filepath = sys_paths.get_barks_reader_close_icon_file()
        self.action_bar_collapse_icon_filepath = sys_paths.get_barks_reader_collapse_icon_file()
        self.action_bar_change_pics_icon_filepath = (
            sys_paths.get_barks_reader_refresh_arrow_icon_file()
        )
        self.action_bar_settings_icon_filepath = sys_paths.get_barks_reader_settings_icon_file()
        self.action_bar_goto_icon_filepath = sys_paths.get_barks_reader_goto_icon_file()

    def _get_reader_app_icon_file(self) -> str:
        icon_files = get_all_files_in_dir(
            self._reader_settings.sys_file_paths.get_reader_icon_files_dir()
        )
        file_index = randrange(0, len(icon_files))
        return icon_files[file_index]

    def _on_loading_data_popup_open(self) -> None:
        set_kivy_busy_cursor()

        def _show_popop() -> None:
            self._set_new_loading_data_popup_image()
            self.loading_data_popup.opacity = 1

        Clock.schedule_once(lambda dt: _show_popop(), 0)

        self._loading_data_popup_image_event = Clock.schedule_interval(
            lambda dt: self._set_new_loading_data_popup_image(), 0.5
        )

    def _set_new_loading_data_popup_image(self) -> None:
        self.loading_data_popup.splash_image_path = (
            self._random_title_images.get_loading_screen_random_image(self.title_lists[ALL_LISTS])
        )
        logging.debug(f'New loading popup image: "{self.loading_data_popup.splash_image_path}".')

    def start_tree_build(self):
        """Kicks off the asynchronous build of the TreeView."""

        if not self.main_files_exist():
            return

        Clock.schedule_once(lambda dt: self.loading_data_popup.open(), 0)

        from reader_tree_builder import ReaderTreeBuilder

        tree_builder = ReaderTreeBuilder(self)
        self.year_range_nodes = tree_builder.chrono_year_range_nodes
        Clock.schedule_once(lambda dt: tree_builder.build_main_screen_tree(), 0)

    def _on_tree_build_finished(self, _instance):
        logging.debug(f"Received the 'on_finished_building_event' - dismiss the loading popup.")
        if self._loading_data_popup_image_event:
            self._loading_data_popup_image_event.cancel()

        # Linger on the last image...
        self.loading_data_popup.title = "All titles loaded!"
        set_kivy_normal_cursor()
        Clock.schedule_once(lambda dt: self.loading_data_popup.dismiss(), 1)

        self._update_view_for_node(ViewStates.INITIAL)

        if not self.init_comic_book_data():
            return

        if self._reader_settings.goto_saved_node_on_start:
            saved_node_path = self._json_settings_manager.get_last_selected_node_path()
            if saved_node_path:
                self._goto_saved_node(saved_node_path)

    def main_files_exist(self) -> bool:
        if self._reader_settings.is_valid_fantagraphics_volumes_dir(
            self._reader_settings.fantagraphics_volumes_dir
        ):
            return True

        def _on_error_popup_closed(not_all_titles_loaded_msg: str) -> None:
            self.not_all_titles_loaded_msg = not_all_titles_loaded_msg
            self.not_all_titles_loaded = True

        self._user_error_handler.handle_error(
            ErrorTypes.FantagraphicsVolumeRootNotFound, None, _on_error_popup_closed
        )

        return False

    def init_comic_book_data(self) -> bool:
        try:
            self.comic_book_reader.init_data()
            return True

        except (WrongFantagraphicsVolumeError, TooManyArchiveFilesError) as e:

            def _on_error_popup_closed(not_all_titles_loaded_msg: str) -> None:
                self.not_all_titles_loaded_msg = not_all_titles_loaded_msg
                self.not_all_titles_loaded = True

            error_type = (
                ErrorTypes.WrongFantagraphicsVolume
                if type(e) == WrongFantagraphicsVolumeError
                else ErrorTypes.TooManyArchiveFiles
            )
            self._user_error_handler.handle_error(error_type, e, _on_error_popup_closed)

            return False

        except Exception as e:
            raise e

    def on_action_bar_collapse(self):
        for node in self.ids.reader_tree_view.iterate_open_nodes():
            self.ids.reader_tree_view.deselect_node(node)

            if node.is_open:
                self.ids.reader_tree_view.toggle_node(node)
                self._close_open_nodes(node)

        self._update_view_for_node(ViewStates.INITIAL)

    def _close_open_nodes(self, start_node: TreeViewNode) -> None:
        for node in start_node.nodes:
            if node.is_open:
                self.ids.reader_tree_view.toggle_node(node)
                self._close_open_nodes(node)

    def on_action_bar_change_view_images(self):
        self._change_background_views()

    def on_action_bar_goto(self, button: Button):
        node = find_tree_view_node(self.ids.reader_tree_view.root, button.text)
        if node:
            self._close_open_nodes(self.ids.reader_tree_view.root)
            self._open_all_parent_nodes(node)
            self._goto_node(node)

    def on_action_bar_pressed(self, button: Button):
        pass

    def on_goto_top_view_title(self) -> None:
        self._goto_chrono_title(self._top_view_image_info)

    def on_goto_fun_view_title(self, _button: Button) -> None:
        self._goto_chrono_title(self._bottom_view_fun_image_info)

    def _goto_chrono_title(self, image_info: ImageInfo) -> None:
        title_fanta_info = self._get_fanta_info(image_info.from_title)

        year_nodes = self.year_range_nodes[
            self.filtered_title_lists.get_year_range_from_info(title_fanta_info)
        ]
        self._open_all_parent_nodes(year_nodes)

        title_node = find_tree_view_title_node(year_nodes, image_info.from_title)
        self._goto_node(title_node, scroll_to=True)

        self._title_row_selected(title_fanta_info, image_info.filename)

    def _goto_node(self, node: TreeViewNode, scroll_to=False) -> None:
        def show_node(n):
            self.ids.reader_tree_view.select_node(n)
            if scroll_to:
                self._scroll_to_node(n)

        Clock.schedule_once(lambda dt, item=node: show_node(item))

    def _scroll_to_node(self, node: TreeViewNode) -> None:
        Clock.schedule_once(lambda dt: self.ids.scroll_view.scroll_to(node, padding=50), 0)

    def _get_fanta_info(self, title: Titles) -> FantaComicBookInfo:
        # TODO: Very roundabout way to get fanta info
        title_str = BARKS_TITLES[title]
        return self.all_fanta_titles[title_str]

    def _title_row_selected(self, new_fanta_info: FantaComicBookInfo, title_image_file: str):
        self._fanta_info = new_fanta_info
        self._set_title(title_image_file)

        self._update_view_for_node(ViewStates.ON_TITLE_NODE)

    def _open_all_parent_nodes(self, node: TreeViewNode) -> None:
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
        node_type = type(node)
        if node_type == TitleTreeViewNode:
            return

        logging.debug(f'Node expanded: "{node.text}" ({node_type}).')

        view_state_params = {}
        new_view_state = None
        clean_node_text = get_clean_text_without_extra(node.text)

        if node_type in NODE_TYPE_TO_VIEW_STATE_MAP:
            new_view_state = NODE_TYPE_TO_VIEW_STATE_MAP[node_type]
            if new_view_state == ViewStates.ON_YEAR_RANGE_NODE:
                view_state_params["year_range"] = node.text
            elif new_view_state == ViewStates.ON_CS_YEAR_RANGE_NODE:
                view_state_params["cs_year_range"] = node.text
            elif new_view_state == ViewStates.ON_US_YEAR_RANGE_NODE:
                view_state_params["us_year_range"] = node.text
        elif isinstance(node, MainTreeViewNode) and node.text in NODE_TEXT_TO_VIEW_STATE_MAP:
            new_view_state = NODE_TEXT_TO_VIEW_STATE_MAP[node.text]
        elif isinstance(node, StoryGroupTreeViewNode):
            if clean_node_text in NODE_TEXT_TO_VIEW_STATE_MAP:
                new_view_state = NODE_TEXT_TO_VIEW_STATE_MAP[clean_node_text]
            elif clean_node_text in BARKS_TAG_CATEGORIES_DICT:
                new_view_state = ViewStates.ON_CATEGORY_NODE
                view_state_params["category"] = clean_node_text
            elif is_tag_enum(clean_node_text):
                logging.debug(f'Tag node expanded: "{clean_node_text}".')
                new_view_state = ViewStates.ON_TAG_NODE
                view_state_params["tag"] = Tags(clean_node_text)

        if new_view_state:
            self._update_background_views(new_view_state, **view_state_params)
        else:
            logging.warning(f"No view state mapping found for node: {node.text} ({node_type})")

        if node.nodes:
            self._scroll_to_node(node.nodes[0])
        else:
            self._scroll_to_node(node)

    def on_intro_pressed(self, _button: Button):
        self._update_view_for_node(ViewStates.ON_INTRO_NODE)
        self.intro_text_opacity = 1
        self.intro_text = read_text_paragraphs(
            self._reader_settings.sys_file_paths.get_intro_text_file()
        )

    def on_the_stories_pressed(self, _button: Button):
        self._update_view_for_node(ViewStates.ON_THE_STORIES_NODE)

    def on_search_pressed(self, _button: Button):
        self._update_view_for_node(ViewStates.ON_SEARCH_NODE)

    def on_title_search_box_pressed(self, instance: TitleSearchBoxTreeViewNode):
        logging.debug(f"Title search box pressed: {instance}.")

        if not instance.get_current_title():
            logging.debug("Have not got title search box text yet.")
            self._update_view_for_node(ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET)
        elif self._background_views.get_view_state() != ViewStates.ON_TITLE_SEARCH_BOX_NODE:
            logging.debug(
                f"Forcing title search box change:"
                f" view state = {self._background_views.get_view_state()},"
                f' title search box text = "{instance.get_current_title()}",'
                f' title spinner text = "{instance.ids.title_spinner.text}"'
            )
            self.on_title_search_box_title_changed(
                instance.ids.title_spinner, instance.ids.title_spinner.text
            )

    def on_title_search_box_title_changed(self, _spinner: Spinner, title_str: str):
        logging.debug(f'Title search box title changed: "{title_str}".')

        if not title_str:
            self._update_view_for_node(ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET)
        elif self._update_title(title_str):
            self._update_view_for_node(ViewStates.ON_TITLE_SEARCH_BOX_NODE)
        else:
            self._update_view_for_node(ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET)

    def on_tag_search_box_pressed(self, instance: TagSearchBoxTreeViewNode):
        logging.debug(f"Tag search box pressed: {instance}.")

        if not instance.get_current_tag_str():
            logging.debug("Have not got tag search box text yet.")
            self._update_view_for_node(ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET)
        elif self._background_views.get_view_state() != ViewStates.ON_TAG_SEARCH_BOX_NODE:
            logging.debug(
                f"Forcing tag search box change:"
                f" view state = {self._background_views.get_view_state()},"
                f' tag search box text = "{instance.get_current_tag_str()}",'
                f' tag title spinner text = "{instance.ids.tag_title_spinner.text}"'
            )
            self.on_tag_search_box_title_changed(instance, instance.ids.tag_title_spinner.text)

    def on_tag_search_box_text_changed(self, instance: TagSearchBoxTreeViewNode, text: str):
        logging.debug(f'Tag search box text changed: text: "{text}".')

        if not instance.get_current_title():
            self._update_view_for_node(ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET)

    def on_tag_search_box_tag_changed(self, instance: TagSearchBoxTreeViewNode, tag_str: str):
        logging.debug(f'Tag search box tag changed: "{tag_str}".')

        if not tag_str:
            return

        if not instance.get_current_title():
            self._update_view_for_node(ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET)

    def on_tag_search_box_title_changed(self, instance: TagSearchBoxTreeViewNode, title_str: str):
        logging.debug(
            f'Tag search box title changed: "{title_str}".'
            f' Tag: "{instance.get_current_tag().value}".'
        )

        if not title_str:
            self._update_view_for_node(ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET)
        elif self._update_title(title_str):
            self._update_view_for_node(ViewStates.ON_TAG_SEARCH_BOX_NODE)
            self._set_tag_goto_page_checkbox(instance.get_current_tag(), title_str)
        else:
            self._update_view_for_node(ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET)

    def _update_title(self, title_str: str) -> bool:
        logging.debug(f'Update title: "{title_str}".')
        assert title_str != ""

        title_str = ComicBookInfo.get_title_str_from_display_title(title_str)

        if title_str not in self.all_fanta_titles:
            logging.debug(f'Update title: Not configured yet: "{title_str}".')
            return False

        self._fanta_info = self.all_fanta_titles[title_str]
        self._set_title()

        return True

    def on_appendix_pressed(self, _button: Button):
        self._update_view_for_node(ViewStates.ON_APPENDIX_NODE)

    def on_appendix_censorship_fixes_pressed(self, _button: Button):
        self._update_view_for_node(ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE)
        self.appendix_censorship_fixes_text_opacity = 1
        self.appendix_censorship_fixes_text = read_text_paragraphs(
            self._reader_settings.sys_file_paths.get_censorship_fixes_text_file()
        )

    def on_index_pressed(self, _button: Button):
        self._update_view_for_node(ViewStates.ON_INDEX_NODE)

    def on_chrono_pressed(self, _button: Button):
        self._update_view_for_node(ViewStates.ON_CHRONO_BY_YEAR_NODE)

    def on_year_range_pressed(self, button: Button):
        self._update_view_for_node(ViewStates.ON_YEAR_RANGE_NODE, year_range=button.text)

    def on_cs_year_range_pressed(self, button: Button):
        self._update_view_for_node(ViewStates.ON_CS_YEAR_RANGE_NODE, cs_year_range=button.text)

    def on_us_year_range_pressed(self, button: Button):
        self._update_view_for_node(ViewStates.ON_US_YEAR_RANGE_NODE, us_year_range=button.text)

    def on_series_pressed(self, _button: Button):
        self._update_view_for_node(ViewStates.ON_SERIES_NODE)

    def cs_pressed(self, _button: Button):
        self._update_view_for_node(ViewStates.ON_CS_NODE)

    def dd_pressed(self, _button: Button):
        self._update_view_for_node(ViewStates.ON_DD_NODE)

    def us_pressed(self, _button: Button):
        self._update_view_for_node(ViewStates.ON_US_NODE)

    def dds_pressed(self, _button: Button):
        self._update_view_for_node(ViewStates.ON_DDS_NODE)

    def uss_pressed(self, _button: Button):
        self._update_view_for_node(ViewStates.ON_USS_NODE)

    def gg_pressed(self, _button: Button):
        self._update_view_for_node(ViewStates.ON_GG_NODE)

    def misc_pressed(self, _button: Button):
        self._update_view_for_node(ViewStates.ON_MISC_NODE)

    def on_categories_pressed(self, _button: Button):
        self._update_view_for_node(ViewStates.ON_CATEGORIES_NODE)

    def on_category_pressed(self, button: Button):
        self._update_view_for_node(ViewStates.ON_CATEGORY_NODE, category=button.text)

    def on_title_row_button_pressed(self, button: Button):
        self._fanta_info = button.parent.fanta_info
        self._set_title()

        self._update_view_for_node(ViewStates.ON_TITLE_NODE)

        if isinstance(button.parent.parent_node, TagStoryGroupTreeViewNode) or isinstance(
            button.parent.parent_node, TagGroupStoryGroupTreeViewNode
        ):
            self._set_tag_goto_page_checkbox(
                button.parent.parent_node.tag, self._fanta_info.comic_book_info.get_title_str()
            )

    def _change_background_views(self) -> None:
        self._update_background_views(
            self._background_views.get_view_state(),
            self._background_views.get_current_category(),
            self._background_views.get_current_year_range(),
            self._background_views.get_current_cs_year_range(),
            self._background_views.get_current_us_year_range(),
            self._background_views.get_current_tag(),
        )

    def _update_view_for_node(self, view_state: ViewStates, **args) -> None:
        self._update_background_views(view_state, **args)

    def _update_background_views(
        self,
        tree_node: ViewStates,
        category: str = "",
        year_range: str = "",
        cs_year_range: str = "",
        us_year_range: str = "",
        tag: Union[None, Tags] = None,
    ) -> None:
        self._background_views.set_current_category(category)
        self._background_views.set_current_year_range(get_clean_text_without_extra(year_range))
        self._background_views.set_current_cs_year_range(
            get_clean_text_without_extra(cs_year_range)
        )
        self._background_views.set_current_us_year_range(
            get_clean_text_without_extra(us_year_range)
        )
        self._background_views.set_current_tag(tag)

        self._background_views.set_view_state(tree_node)

        self.intro_text_opacity = 0.0
        self.appendix_censorship_fixes_text_opacity = 0.0

        self._top_view_image_info = self._background_views.get_top_view_image_info()
        self.top_view_image_opacity = self._background_views.get_top_view_image_opacity()
        self.top_view_image_source = self._top_view_image_info.filename
        self.top_view_image_fit_mode = self._top_view_image_info.fit_mode
        self.top_view_image_color = self._background_views.get_top_view_image_color()

        self.bottom_view_fun_image_opacity = (
            self._background_views.get_bottom_view_fun_image_opacity()
        )
        self._bottom_view_fun_image_info = self._background_views.get_bottom_view_fun_image_info()
        self.bottom_view_fun_image_source = self._bottom_view_fun_image_info.filename
        self.bottom_view_fun_image_fit_mode = self._bottom_view_fun_image_info.fit_mode
        self.bottom_view_fun_image_color = self._background_views.get_bottom_view_fun_image_color()
        self.bottom_view_fun_image_from_title = (
            self._bottom_view_fun_image_info.from_title is not None
        )

        self.bottom_view_title_opacity = self._background_views.get_bottom_view_title_opacity()
        self._bottom_view_title_image_info = (
            self._background_views.get_bottom_view_title_image_info()
        )
        self.bottom_view_title_image_source = self._bottom_view_title_image_info.filename
        self.bottom_view_title_image_fit_mode = self._bottom_view_title_image_info.fit_mode
        self.bottom_view_title_image_color = (
            self._background_views.get_bottom_view_title_image_color()
        )

    def _set_title(self, title_image_file: str = "") -> None:
        logging.debug(f'Setting title to "{self._fanta_info.comic_book_info.get_title_str()}".')

        if title_image_file:
            title_image_file = self._reader_settings.file_paths.get_edited_version_if_possible(
                title_image_file
            )[0]
            logging.debug(f'Using provided title image file "{title_image_file}".')
        else:
            title_image_file = self._random_title_images.get_random_image_for_title(
                self._fanta_info.comic_book_info.get_title_str(),
                TITLE_VIEW_IMAGE_TYPES,
                use_edited_only=True,
            )
            logging.debug(f'Using random title image file "{title_image_file}".')
        self._background_views.set_bottom_view_title_image_file(title_image_file)

        self.main_title_text = self._get_main_title_str()
        self.title_info_text = self._formatter.get_title_info(
            self._fanta_info, self.MAX_TITLE_INFO_LEN_BEFORE_SHORTEN
        )
        self.title_extra_info_text = self._formatter.get_title_extra_info(self._fanta_info)
        self.title_page_image_source = self._reader_settings.file_paths.get_comic_inset_file(
            self._fanta_info.comic_book_info.title, use_edited_only=True
        )
        logging.debug(f'Using title image source "{self.title_page_image_source}".')

        self._set_goto_page_checkbox()
        self._set_use_overrides_checkbox()

    def _set_use_overrides_checkbox(self) -> None:
        title = self._fanta_info.comic_book_info.title
        if (
            self._reader_settings.use_prebuilt_archives
            or not self._special_fanta_overrides.is_title_where_overrides_are_optional(title)
        ):
            self.ids.use_overrides_layout.opacity = 0
            self.ids.use_overrides_checkbox.active = True
            return

        self.ids.use_overrides_layout.opacity = 1
        self.ids.use_overrides_label.text = self._special_fanta_overrides.get_description(title)
        self.ids.use_overrides_checkbox.active = (
            self._special_fanta_overrides.get_overrides_setting(title)
        )

    def on_use_overrides_checkbox_changed(self, _instance, use_overrides: bool) -> None:
        logging.debug(f"Use overrides checkbox changed: use_overrides = {use_overrides}.")

        self.title_page_image_source = self._special_fanta_overrides.get_title_page_inset_file(
            self._fanta_info.comic_book_info.title, use_overrides
        )

        logging.debug(
            f'Use overrides changed: title_page_image_source = "{self.title_page_image_source}".'
        )

    def _get_main_title_str(self):
        if self._fanta_info.comic_book_info.is_barks_title:
            if self._fanta_info.comic_book_info.title in LONG_TITLE_SPLITS:
                return LONG_TITLE_SPLITS[self._fanta_info.comic_book_info.title]
            return self._fanta_info.comic_book_info.get_title_str()

        return self._fanta_info.comic_book_info.get_title_from_issue_name()

    def on_image_pressed(self):
        if self._fanta_info is None:
            logging.debug(f'Image "{self.title_page_image_source}" pressed. But no title selected.')
            return

        comic = self._get_comic_book()
        self._comic_page_info = self._comic_page_info_mgr.get_comic_page_info(comic)
        page_to_first_goto = self._get_page_to_first_goto()

        comic_book_image_builder = ComicBookImageBuilder(
            comic, self._reader_settings.sys_file_paths.get_empty_page_file()
        )
        comic_book_image_builder.set_required_dim(self._comic_page_info.required_dim)

        logging.debug(f'Image "{self.title_page_image_source}" pressed.')
        logging.debug(
            f'Load "{self._fanta_info.comic_book_info.get_title_str()}"'
            f' and goto page "{page_to_first_goto}".'
        )

        self.comic_book_reader.read_comic(
            self._fanta_info,
            self.ids.use_overrides_checkbox.active,
            comic_book_image_builder,
            page_to_first_goto,
            self._comic_page_info.page_map,
        )

    def _get_comic_book(self) -> ComicBook:
        title_str = self._fanta_info.comic_book_info.get_title_str()

        comic = self._comics_database.get_comic_book(title_str)

        comic.intro_inset_file = self._special_fanta_overrides.get_inset_file(
            self._fanta_info.comic_book_info.title, self.ids.use_overrides_checkbox.active
        )

        return comic

    def _get_page_to_first_goto(self) -> str:
        if not self.ids.goto_page_checkbox.active:
            return COMIC_PAGE_ONE

        return self.bottom_view_title_goto_page_num

    def _set_tag_goto_page_checkbox(self, tag: Union[Tags, TagGroups], title_str: str) -> None:
        logging.debug(f'Setting tag goto page for ({tag.value}, "{title_str}").')

        if type(tag) == Tags:
            title = self._title_dict[ComicBookInfo.get_title_str_from_display_title(title_str)]
            if (tag, title) not in BARKS_TAGGED_PAGES:
                logging.debug(f'No pages for ({tag.value}, "{title_str}").')
            else:
                page_to_goto = BARKS_TAGGED_PAGES[(tag, title)][0]
                logging.debug(f"Setting page to goto: {page_to_goto}.")
                self.ids.goto_page_layout.opacity = 1
                self.ids.goto_page_checkbox.active = True
                self.bottom_view_title_goto_page_num = page_to_goto

    def _set_goto_page_checkbox(self, last_read_page: SavedPageInfo = None):
        if not last_read_page:
            title_str = self._fanta_info.comic_book_info.get_title_str()
            last_read_page = self._get_last_read_page(title_str)

        if not last_read_page or (last_read_page.display_page_num == COMIC_PAGE_ONE):
            self.ids.goto_page_layout.opacity = 0
            self.ids.goto_page_checkbox.active = False
        else:
            self.ids.goto_page_layout.opacity = 1
            self.ids.goto_page_checkbox.active = True
            self.bottom_view_title_goto_page_num = last_read_page.display_page_num

    def _get_last_read_page(self, title_str: str) -> Union[SavedPageInfo, None]:
        last_read_page_info = self._json_settings_manager.get_last_read_page(title_str)
        if not last_read_page_info:
            return None

        if self._is_on_or_past_last_body_page(last_read_page_info):
            # The comic has been read. Go back to the first page.
            last_read_page_info.display_page_num = COMIC_PAGE_ONE

        logging.debug(f'"{title_str}": Last read page "{last_read_page_info}".')

        return last_read_page_info

    @staticmethod
    def _is_on_or_past_last_body_page(page_info: SavedPageInfo) -> bool:
        return (page_info.page_type in BACK_MATTER_PAGES) or (
            (page_info.page_type == PageType.BODY)
            and (page_info.display_page_num == page_info.last_body_page)
        )

    def _get_last_read_page_from_comic(self) -> Union[SavedPageInfo, None]:
        last_read_page_str = self.comic_book_reader.get_last_read_page()
        if not last_read_page_str:
            return None

        last_read_page = self._comic_page_info.page_map[last_read_page_str]

        return SavedPageInfo(
            last_read_page.page_index,
            last_read_page.display_page_num,
            last_read_page.page_type,
            self._comic_page_info.last_body_page,
        )

    def app_closing(self) -> None:
        logging.debug("Closing app...")

        if not self.ids.reader_tree_view.selected_node:
            self._json_settings_manager.save_last_selected_node_path([])
            logging.debug("Settings: No selected node to save.")
        else:
            selected_node_path = get_tree_view_node_path(self.ids.reader_tree_view.selected_node)
            self._json_settings_manager.save_last_selected_node_path(selected_node_path)
            logging.debug(f'Settings: Saved last selected node "{selected_node_path}".')

    def comic_closed(self):
        title_str = self._fanta_info.comic_book_info.get_title_str()
        last_read_page = self._get_last_read_page_from_comic()

        if not last_read_page:
            logging.warning(f'"{title_str}": There was no valid last read page.')
        else:
            self._json_settings_manager.save_last_read_page(title_str, last_read_page)
            logging.debug(
                f'"{title_str}": Saved last read page "{last_read_page.display_page_num}".'
            )

            if self._is_on_or_past_last_body_page(last_read_page):
                last_read_page.display_page_num = COMIC_PAGE_ONE

            self._set_goto_page_checkbox(last_read_page)

    def _goto_saved_node(self, saved_node_path: List[str]) -> None:
        logging.debug(f'Looking for saved node "{saved_node_path}"...')
        saved_node = find_node_by_path(self.ids.reader_tree_view, list(reversed(saved_node_path)))
        if saved_node:
            self._setup_and_selected_saved_node(saved_node)

    def _setup_and_selected_saved_node(self, saved_node: TreeViewNode) -> None:
        logging.debug(
            f'Selecting and setting up start node "{get_tree_view_node_id_text(saved_node)}".'
        )

        self.ids.reader_tree_view.select_node(saved_node)

        if isinstance(saved_node, ButtonTreeViewNode):
            saved_node.trigger_action()
        elif isinstance(saved_node, TitleTreeViewNode):
            self.on_title_row_button_pressed(saved_node.ids.num_label)
            self._scroll_to_node(saved_node)
