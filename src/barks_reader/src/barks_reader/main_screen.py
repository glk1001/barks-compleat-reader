from __future__ import annotations

from random import randrange
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_tags import (
    BARKS_TAGGED_PAGES,
    TagGroups,
    Tags,
    special_case_personal_favourites_tag_update,
)
from barks_fantagraphics.barks_titles import (
    BARKS_TITLE_DICT,
    BARKS_TITLES,
    ComicBookInfo,
    Titles,
)
from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    ALL_LISTS,
    SERIES_EXTRAS,
    FantaComicBookInfo,
)
from barks_fantagraphics.title_search import BarksTitleSearch

# noinspection PyProtectedMember
from kivy.clock import Clock
from kivy.properties import (
    BooleanProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from loguru import logger

from barks_reader.background_views import BackgroundViews, ViewStates
from barks_reader.comic_reader_manager import ComicReaderManager
from barks_reader.fantagraphics_volumes import (
    TooManyArchiveFilesError,
    WrongFantagraphicsVolumeError,
)
from barks_reader.json_settings_manager import SavedPageInfo, SettingsManager
from barks_reader.random_title_images import ImageInfo, RandomTitleImages
from barks_reader.reader_consts_and_types import (
    APP_TITLE,
    CHRONO_YEAR_RANGES,
    COMIC_PAGE_ONE,
)
from barks_reader.reader_formatter import get_action_bar_title
from barks_reader.reader_settings import FantaVolumesState
from barks_reader.reader_tree_view_utils import (
    find_tree_view_title_node,
    get_tree_view_node_id_text,
    get_tree_view_node_path,
)
from barks_reader.reader_ui_classes import (
    ACTION_BAR_SIZE_Y,
    ButtonTreeViewNode,
    LoadingDataPopup,
    ReaderTreeBuilderEventDispatcher,
    TagGroupStoryGroupTreeViewNode,
    TagStoryGroupTreeViewNode,
    TitleTreeViewNode,
    set_kivy_busy_cursor,
    set_kivy_normal_cursor,
)
from barks_reader.reader_utils import (
    get_all_files_in_dir,
    read_title_list,
)
from barks_reader.special_overrides_handler import SpecialFantaOverrides
from barks_reader.tree_view_manager import TreeViewManager
from barks_reader.user_error_handler import ErrorTypes, UserErrorHandler
from barks_reader.view_state_manager import ImageThemesChange, ImageThemesToUse, ViewStateManager

if TYPE_CHECKING:
    from pathlib import Path

    from barks_fantagraphics.comic_book import ComicBook
    from barks_fantagraphics.comics_database import ComicsDatabase

    # noinspection PyProtectedMember
    from kivy._clock import ClockEvent
    from kivy.factory import Factory
    from kivy.uix.button import Button
    from kivy.uix.treeview import TreeViewNode
    from kivy.uix.widget import Widget

    from barks_reader.bottom_title_view_screen import BottomTitleViewScreen
    from barks_reader.comic_book_reader import ComicBookReader
    from barks_reader.filtered_title_lists import FilteredTitleLists
    from barks_reader.font_manager import FontManager
    from barks_reader.fun_image_view_screen import FunImageViewScreen
    from barks_reader.reader_screens import ScreenSwitchers
    from barks_reader.reader_settings import ReaderSettings
    from barks_reader.system_file_paths import SystemFilePaths
    from barks_reader.tree_view_screen import TreeViewScreen


class MainScreen(BoxLayout, Screen):
    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
    ACTION_BAR_TITLE_COLOR = (0.0, 1.0, 0.0, 1.0)
    app_icon_filepath = StringProperty()
    action_bar_close_icon_filepath = StringProperty()
    action_bar_collapse_icon_filepath = StringProperty()
    action_bar_change_pics_icon_filepath = StringProperty()
    action_bar_settings_icon_filepath = StringProperty()
    action_bar_goto_icon_filepath = StringProperty()
    lower_title_available = BooleanProperty(defaultvalue=False)
    app_title = StringProperty()

    is_first_use_of_reader = BooleanProperty(defaultvalue=False)

    def __init__(
        self,
        comics_database: ComicsDatabase,
        reader_settings: ReaderSettings,
        reader_tree_events: ReaderTreeBuilderEventDispatcher,
        filtered_title_lists: FilteredTitleLists,
        screen_switchers: ScreenSwitchers,
        tree_view_screen: TreeViewScreen,
        bottom_title_view_screen: BottomTitleViewScreen,
        fun_image_view_screen: FunImageViewScreen,
        **kwargs: str,
    ) -> None:
        super().__init__(**kwargs)

        self.tree_view_screen = tree_view_screen
        self.bottom_title_view_screen = bottom_title_view_screen
        self.fun_image_view_screen = fun_image_view_screen

        self.add_widget(self.tree_view_screen)
        self.bottom_title_view_screen.add_widget(self.fun_image_view_screen)
        self.add_widget(self.bottom_title_view_screen)

        self._comics_database = comics_database
        self._reader_settings = reader_settings
        self._user_error_handler = UserErrorHandler(
            reader_settings,
            screen_switchers.switch_to_settings,
        )
        self._fanta_volumes_state: FantaVolumesState = FantaVolumesState.VOLUMES_NOT_SET
        self._screen_switchers = screen_switchers
        self.title_lists: dict[str, list[FantaComicBookInfo]] = (
            filtered_title_lists.get_title_lists()
        )
        self.title_search = BarksTitleSearch()
        self._random_title_images = RandomTitleImages(self._reader_settings)
        self.is_first_use_of_reader = self._reader_settings.is_first_use_of_reader

        self._json_settings_manager = SettingsManager(self._reader_settings.get_user_data_path())

        self.fanta_info: FantaComicBookInfo | None = None
        self.year_range_nodes: dict | None = None

        self.loading_data_popup = LoadingDataPopup()
        self.loading_data_popup.on_open = self._on_loading_data_popup_open
        self._loading_data_popup_image_event: ClockEvent | None = None

        self.reader_tree_events = reader_tree_events
        self.reader_tree_events.bind(on_finished_building_event=self._on_tree_build_finished)

        self._comic_reader_manager = ComicReaderManager(
            self._comics_database,
            self._reader_settings,
            self._json_settings_manager,
            self.tree_view_screen,
            self._user_error_handler,
        )
        self._read_comic_view_state: ViewStates | None = None

        background_views = BackgroundViews(
            self._reader_settings,
            self.title_lists,
            self._random_title_images,
        )

        self.view_state_manager = ViewStateManager(
            self._reader_settings,
            background_views,
            self.tree_view_screen,
            self.bottom_title_view_screen,
            self.fun_image_view_screen,
        )
        self.view_state_manager.update_background_views(ViewStates.PRE_INIT)

        self.tree_view_manager = TreeViewManager(
            background_views,
            self.view_state_manager,
            self.tree_view_screen,
            self._update_title_from_tree_view,
            self._read_article_as_comic_book,
            self._set_tag_goto_page_checkbox,
        )

        self._set_action_bar_icons(self._reader_settings.sys_file_paths)

        self._special_fanta_overrides = SpecialFantaOverrides(self._reader_settings)
        self.bottom_title_view_screen.on_title_portal_image_pressed_func = (
            self.on_title_portal_image_pressed
        )
        # TODO: push bind down
        self.bottom_title_view_screen.ids.use_overrides_checkbox.bind(
            active=self.on_use_overrides_checkbox_changed
        )
        self.fun_image_view_screen.ids.checkbox_all_image_types.bind(
            active=self.on_checkbox_all_image_types_changed
        )
        self.fun_image_view_screen.ids.checkbox_custom_image_types.bind(
            active=self.on_checkbox_custom_image_types_changed
        )
        self.fun_image_view_screen.on_goto_title_func = self.on_goto_fun_view_title

    def fonts_updated(self, font_manager: FontManager) -> None:
        self.app_title = get_action_bar_title(font_manager, APP_TITLE)

    def set_comic_book_reader(self, comic_book_reader: ComicBookReader) -> None:
        self._comic_reader_manager.comic_book_reader = comic_book_reader

    def _set_action_bar_icons(self, sys_paths: SystemFilePaths) -> None:
        self.app_icon_filepath = str(self._get_reader_app_icon_file())
        self.action_bar_close_icon_filepath = str(sys_paths.get_barks_reader_close_icon_file())
        self.action_bar_collapse_icon_filepath = str(
            sys_paths.get_barks_reader_collapse_icon_file()
        )
        self.action_bar_change_pics_icon_filepath = str(
            sys_paths.get_barks_reader_refresh_arrow_icon_file()
        )
        self.action_bar_settings_icon_filepath = str(
            sys_paths.get_barks_reader_settings_icon_file()
        )
        self.action_bar_goto_icon_filepath = str(sys_paths.get_barks_reader_goto_icon_file())

    def _get_reader_app_icon_file(self) -> Path:
        icon_files = get_all_files_in_dir(
            self._reader_settings.sys_file_paths.get_reader_icon_files_dir(),
        )
        file_index = randrange(0, len(icon_files))
        return icon_files[file_index]

    def _on_loading_data_popup_open(self) -> None:
        set_kivy_busy_cursor()

        def _show_popop() -> None:
            self._set_new_loading_data_popup_image()
            self.loading_data_popup.opacity = 1

        Clock.schedule_once(lambda _dt: _show_popop(), 0)

        self._loading_data_popup_image_event = Clock.schedule_interval(
            lambda _dt: self._set_new_loading_data_popup_image(),
            0.5,
        )

    def _set_new_loading_data_popup_image(self) -> None:
        self.loading_data_popup.splash_image_path = str(
            self._random_title_images.get_loading_screen_random_image(self.title_lists[ALL_LISTS])
        )
        logger.debug(f'New loading popup image: "{self.loading_data_popup.splash_image_path}".')

    def start_tree_build(self) -> None:
        """Kicks off the asynchronous build of the TreeView."""
        Clock.schedule_once(lambda _dt: self.loading_data_popup.open(), 0)

        # Put import here to avoid circular dependency.
        from barks_reader.reader_tree_builder import ReaderTreeBuilder  # noqa: PLC0415

        tree_builder = ReaderTreeBuilder(self)
        self.year_range_nodes = tree_builder.chrono_year_range_nodes
        Clock.schedule_once(lambda _dt: tree_builder.build_main_screen_tree(), 0)

    def _on_tree_build_finished(self, _instance: Widget) -> None:
        logger.debug("Received the 'on_finished_building_event' - dismiss the loading popup.")
        if self._loading_data_popup_image_event:
            self._loading_data_popup_image_event.cancel()

        # Linger on the last image...
        self.loading_data_popup.title = "All titles loaded!"
        set_kivy_normal_cursor()
        Clock.schedule_once(lambda _dt: self.loading_data_popup.dismiss(), 1)

        self._finished_building()

    def _finished_building(self) -> None:
        self._fanta_volumes_state = self._get_fanta_volumes_state()
        logger.debug(f"_fanta_volumes_state = {self._fanta_volumes_state}.")

        self.view_state_manager.update_background_views(ViewStates.INITIAL)

        if (
            self._fanta_volumes_state
            in [FantaVolumesState.VOLUMES_EXIST, FantaVolumesState.VOLUMES_NOT_NEEDED]
            and not self._init_comic_book_data()
        ):
            return

        if self._reader_settings.goto_saved_node_on_start:
            saved_node_path = self._json_settings_manager.get_last_selected_node_path()
            if saved_node_path:
                self._goto_saved_node(saved_node_path)

    def _get_fanta_volumes_state(self) -> FantaVolumesState:
        volumes_state = self._reader_settings.get_fantagraphics_volumes_state()
        if volumes_state in [FantaVolumesState.VOLUMES_EXIST, FantaVolumesState.VOLUMES_NOT_NEEDED]:
            return volumes_state

        error_type = (
            ErrorTypes.FantagraphicsVolumeRootNotSet
            if volumes_state == FantaVolumesState.VOLUMES_NOT_SET
            else ErrorTypes.FantagraphicsVolumeRootNotFound
        )

        def _on_error_popup_closed(fanta_volumes_missing_msg: str) -> None:
            self.tree_view_screen.main_files_not_loaded_msg = fanta_volumes_missing_msg
            self.tree_view_screen.main_files_not_loaded = True

        self._user_error_handler.handle_error(
            error_type,
            None,
            _on_error_popup_closed,
        )

        return volumes_state

    def _init_comic_book_data(self) -> bool:
        try:
            self._comic_reader_manager.init_comic_book_data()
        except (WrongFantagraphicsVolumeError, TooManyArchiveFilesError) as e:

            def _on_error_popup_closed(wrong_fanta_volumes_msg: str) -> None:
                self.tree_view_screen.main_files_not_loaded_msg = wrong_fanta_volumes_msg
                self.tree_view_screen.main_files_not_loaded = True

            error_type = (
                ErrorTypes.WrongFantagraphicsVolume
                if type(e) is WrongFantagraphicsVolumeError
                else ErrorTypes.TooManyArchiveFiles
            )
            self._user_error_handler.handle_error(error_type, e, _on_error_popup_closed)

            return False

        except Exception:
            raise
        else:
            return True

    def get_favourite_titles(self) -> list[Titles]:
        titles = read_title_list(self._reader_settings.sys_file_paths.get_favourite_titles_path())

        special_case_personal_favourites_tag_update(titles)

        return titles

    def on_action_bar_collapse(self) -> None:
        self.tree_view_screen.deselect_and_close_open_nodes()
        self.view_state_manager.update_background_views(ViewStates.INITIAL)

    def on_action_bar_change_view_images(self) -> None:
        self.view_state_manager.change_background_views()

    def on_action_bar_goto(self, button: Button) -> None:
        self.tree_view_screen.goto_node(button.text)

    def on_action_bar_pressed(self, button: Button) -> None:
        pass

    def on_goto_top_view_title(self) -> None:
        self._goto_chrono_title(self.view_state_manager.get_top_view_image_info())

    def on_goto_fun_view_title(self) -> None:
        self._goto_chrono_title(self.view_state_manager.get_bottom_view_fun_image_info())

    def _goto_chrono_title(self, image_info: ImageInfo) -> None:
        logger.debug(f'Goto title: "{image_info.from_title}", "{image_info.filename}".')
        title_fanta_info = self._get_fanta_info(image_info.from_title)

        year_nodes = self.year_range_nodes[self._get_year_range_from_info(title_fanta_info)]
        self.tree_view_screen.open_all_parent_nodes(year_nodes)

        title_node = find_tree_view_title_node(year_nodes, image_info.from_title)
        self.tree_view_manager.goto_node(title_node, scroll_to=True)

        self._title_row_selected(title_fanta_info, image_info.filename)

    def on_title_row_button_pressed(self, button: Button) -> None:
        fanta_info: FantaComicBookInfo = button.parent.fanta_info

        self.fanta_info = fanta_info
        self.set_title()
        self.view_state_manager.update_view_for_node_with_title(ViewStates.ON_TITLE_NODE)

        if isinstance(
            button.parent.parent_node,
            (TagStoryGroupTreeViewNode, TagGroupStoryGroupTreeViewNode),
        ):
            self._set_tag_goto_page_checkbox(
                button.parent.parent_node.tag,
                fanta_info.comic_book_info.get_title_str(),
            )

    @staticmethod
    def _get_year_range_from_info(fanta_info: FantaComicBookInfo) -> None | tuple[int, int]:
        sub_year = fanta_info.comic_book_info.submitted_year

        for year_range in CHRONO_YEAR_RANGES:
            if year_range[0] <= sub_year <= year_range[1]:
                return year_range

        return None

    @staticmethod
    def _get_fanta_info(title: Titles) -> FantaComicBookInfo:
        # TODO: Very roundabout way to get fanta info
        title_str = BARKS_TITLES[title]
        return ALL_FANTA_COMIC_BOOK_INFO[title_str]

    def _title_row_selected(
        self,
        new_fanta_info: FantaComicBookInfo,
        title_image_file: Path,
    ) -> None:
        self.fanta_info = new_fanta_info
        self.set_title(title_image_file)
        self.view_state_manager.update_background_views(
            ViewStates.ON_TITLE_NODE, title_str=self.fanta_info.comic_book_info.get_title_str()
        )

    def set_title(self, title_image_file: Path | None = None) -> None:
        self.view_state_manager.set_title(self.fanta_info, title_image_file)

        self._set_goto_page_checkbox()
        self._set_use_overrides_checkbox()

    def _update_title_from_tree_view(self, title_str: str) -> bool:
        logger.debug(f'Update title: "{title_str}".')
        assert title_str != ""

        title_str = ComicBookInfo.get_title_str_from_display_title(title_str)

        if title_str not in ALL_FANTA_COMIC_BOOK_INFO:
            logger.debug(f'Update title: Not configured yet: "{title_str}".')
            return False

        next_fanta_info = ALL_FANTA_COMIC_BOOK_INFO[title_str]
        if next_fanta_info.series_name == SERIES_EXTRAS:
            logger.debug(f'Title is in EXTRA series: "{title_str}".')
            return False

        self.fanta_info = next_fanta_info
        self.set_title()

        return True

    def _set_use_overrides_checkbox(self) -> None:
        title = self.fanta_info.comic_book_info.title
        if (
            self._reader_settings.use_prebuilt_archives
            or not self._special_fanta_overrides.is_title_where_overrides_are_optional(title)
        ):
            self.bottom_title_view_screen.set_overrides_state(active=False)
            return

        self.bottom_title_view_screen.set_overrides_state(
            description=self._special_fanta_overrides.get_description(title),
            active=self._special_fanta_overrides.get_overrides_setting(title),
        )

    def on_use_overrides_checkbox_changed(self, _instance: Widget, use_overrides: bool) -> None:
        logger.debug(f"Use overrides checkbox changed: use_overrides = {use_overrides}.")

        self.bottom_title_view_screen.title_inset_image_source = str(
            self._special_fanta_overrides.get_title_page_inset_file(
                self.fanta_info.comic_book_info.title,
                use_overrides,
            )
        )

        logger.debug(
            f"Use overrides changed: title_page_image_source ="
            f' "{self.bottom_title_view_screen.title_inset_image_source}".'
        )

    def on_checkbox_all_image_types_changed(self, _instance: Widget, use_all_images: bool) -> None:
        self.view_state_manager.bottom_view_fun_image_themes_changed(
            ImageThemesToUse.ALL if use_all_images else ImageThemesToUse.CUSTOM,
        )

    def on_checkbox_custom_image_types_changed(
        self, _instance: Widget, use_custom_images: bool
    ) -> None:
        self.view_state_manager.bottom_view_fun_image_themes_changed(
            ImageThemesToUse.ALL if not use_custom_images else ImageThemesToUse.CUSTOM,
        )

    def on_checkbox_row_changed(self, checkbox_row: Factory.CheckBoxRow) -> None:
        self.view_state_manager.bottom_view_alter_fun_image_themes(
            checkbox_row.theme_enum,
            ImageThemesChange.ADD if checkbox_row.active else ImageThemesChange.DISCARD,
        )

    def fun_view_options_button_pressed(self) -> None:
        self.fun_image_view_screen.fun_view_options_enabled = (
            not self.fun_image_view_screen.fun_view_options_enabled
        )
        logger.debug(
            "Fun view options button pressed."
            f" New state is '{self.fun_image_view_screen.fun_view_options_enabled}'."
        )

    def on_title_portal_image_pressed(self) -> None:
        if self.fanta_info is None:
            logger.debug(
                f'Image "{self.bottom_title_view_screen.title_inset_image_source}"'
                f" pressed. But no title selected."
            )
            return
        if self._fanta_volumes_state in [
            FantaVolumesState.VOLUMES_MISSING,
            FantaVolumesState.VOLUMES_NOT_SET,
        ]:
            reason = (
                "Fantagraphics Directory Not Set"
                if self._fanta_volumes_state == FantaVolumesState.VOLUMES_NOT_SET
                else "Fantagraphics Directory Not Found"
            )
            error_type = (
                ErrorTypes.FantagraphicsVolumeRootNotSet
                if self._fanta_volumes_state == FantaVolumesState.VOLUMES_NOT_SET
                else ErrorTypes.FantagraphicsVolumeRootNotFound
            )
            logger.warning(
                f'Image "{self.bottom_title_view_screen.title_inset_image_source}"'
                f" pressed. But {reason}."
            )

            def _on_error_popup_closed(fanta_volumes_missing_msg: str) -> None:
                self.tree_view_screen.main_files_not_loaded_msg = fanta_volumes_missing_msg
                self.tree_view_screen.main_files_not_loaded = True

            self._user_error_handler.handle_error(
                error_type,
                None,
                _on_error_popup_closed,
                f"Cannot Load Comic: {reason}",
            )
            return

        logger.debug(f'Image "{self.bottom_title_view_screen.title_inset_image_source}" pressed.')

        self._read_barks_comic_book()

        self._set_no_longer_first_use()

    def _set_no_longer_first_use(self) -> None:
        if self.is_first_use_of_reader:
            assert self._reader_settings.is_first_use_of_reader
            self._reader_settings.is_first_use_of_reader = False
            self.is_first_use_of_reader = False
            self.bottom_title_view_screen.is_first_use_of_reader = False

    def _get_comic_book(self) -> ComicBook:
        title_str = self.fanta_info.comic_book_info.get_title_str()

        comic = self._comics_database.get_comic_book(title_str)

        comic.intro_inset_file = str(
            self._special_fanta_overrides.get_inset_file(
                self.fanta_info.comic_book_info.title,
                self.bottom_title_view_screen.use_overrides_active,
            )
        )

        return comic

    def _get_page_to_first_goto(self) -> str:
        if not self.bottom_title_view_screen.goto_page_active:
            return COMIC_PAGE_ONE

        return self.bottom_title_view_screen.goto_page_num

    def _set_tag_goto_page_checkbox(self, tag: Tags | TagGroups, title_str: str) -> None:
        logger.debug(f'Setting tag goto page for ({tag.value}, "{title_str}").')

        if type(tag) is Tags:
            title = BARKS_TITLE_DICT[ComicBookInfo.get_title_str_from_display_title(title_str)]
            if (tag, title) not in BARKS_TAGGED_PAGES:
                logger.debug(f'No pages for ({tag.value}, "{title_str}").')
            else:
                page_to_goto = BARKS_TAGGED_PAGES[(tag, title)][0]
                logger.debug(f"Setting page to goto: {page_to_goto}.")
                self.bottom_title_view_screen.set_goto_page_state(page_to_goto, active=True)

    def _set_goto_page_checkbox(self, last_read_page: SavedPageInfo = None) -> None:
        if not last_read_page:
            title_str = self.fanta_info.comic_book_info.get_title_str()
            last_read_page = self._comic_reader_manager.get_last_read_page(title_str)

        if not last_read_page or (last_read_page.display_page_num == COMIC_PAGE_ONE):
            self.bottom_title_view_screen.set_goto_page_state(active=False)
        else:
            self.bottom_title_view_screen.set_goto_page_state(
                last_read_page.display_page_num, active=True
            )

    def app_closing(self) -> None:
        logger.debug("Closing app...")

        if not self.tree_view_screen.get_selected_node():
            self._json_settings_manager.save_last_selected_node_path([])
            logger.debug("Settings: No selected node to save.")
        else:
            selected_node_path = get_tree_view_node_path(self.tree_view_screen.get_selected_node())
            self._json_settings_manager.save_last_selected_node_path(selected_node_path)
            logger.debug(f'Settings: Saved last selected node "{selected_node_path}".')

    def _read_article_as_comic_book(self, article_title: Titles, view_state: ViewStates) -> None:
        self._read_comic_view_state = view_state

        page_to_first_goto = "1"
        self._comic_reader_manager.read_article_as_comic_book(article_title, page_to_first_goto)

    def _read_barks_comic_book(self) -> None:
        self._read_comic_view_state = None

        self._comic_reader_manager.read_barks_comic_book(
            self.fanta_info,
            self._get_comic_book(),
            self._get_page_to_first_goto(),
            self.bottom_title_view_screen.use_overrides_active,
        )

    def comic_closed(self) -> None:
        if self._read_comic_view_state is not None:
            self.view_state_manager.update_view_for_node(self._read_comic_view_state)
            self._read_comic_view_state = None

        if not self.fanta_info:
            return

        last_read_page = self._comic_reader_manager.comic_closed()

        self._set_goto_page_checkbox(last_read_page)

    def _goto_saved_node(self, saved_node_path: list[str]) -> None:
        logger.debug(f'Looking for saved node "{saved_node_path}"...')
        saved_node = self.tree_view_screen.find_node_by_path(saved_node_path)
        if saved_node:
            self._setup_and_selected_saved_node(saved_node)

    def _setup_and_selected_saved_node(self, saved_node: TreeViewNode) -> None:
        logger.debug(
            f'Selecting and setting up start node "{get_tree_view_node_id_text(saved_node)}".',
        )

        self.tree_view_screen.select_node(saved_node)

        if isinstance(saved_node, ButtonTreeViewNode):
            saved_node.trigger_action()
        elif isinstance(saved_node, TitleTreeViewNode):
            self.on_title_row_button_pressed(saved_node.ids.num_label)
            self.tree_view_manager.scroll_to_node(saved_node)

    def on_intro_compleat_barks_reader_pressed(self, _button: Button) -> None:
        self._screen_switchers.switch_to_intro_compleat_barks_reader()

    def intro_compleat_barks_reader_closed(self) -> None:
        self.view_state_manager.update_view_for_node(ViewStates.ON_INTRO_NODE)
