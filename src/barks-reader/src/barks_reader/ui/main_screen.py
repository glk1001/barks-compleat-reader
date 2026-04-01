from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from barks_fantagraphics.barks_titles import BARKS_TITLE_DICT
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.factory import Factory
from kivy.properties import BooleanProperty, StringProperty  # ty: ignore[unresolved-import]
from kivy.uix.screenmanager import Screen
from loguru import logger

from barks_reader.core.image_selector import ImageInfo, ImageSelector
from barks_reader.core.reader_consts_and_types import APP_TITLE
from barks_reader.core.reader_file_paths_resolver import ReaderFilePathsResolver
from barks_reader.core.reader_formatter import get_action_bar_title
from barks_reader.core.reader_utils import (
    get_title_str_from_reader_icon_file,
    get_win_dimensions,
)
from barks_reader.core.special_overrides_handler import SpecialFantaOverrides
from barks_reader.ui.about_box import show_about_box
from barks_reader.ui.app_initializer import AppInitializer
from barks_reader.ui.background_views import BackgroundViews
from barks_reader.ui.comic_reader_manager import ComicReaderManager
from barks_reader.ui.json_settings_manager import SettingsManager
from barks_reader.ui.main_screen_nav import MainScreenNavigation
from barks_reader.ui.main_screen_window import MainScreenWindowHelper
from barks_reader.ui.navigation_coordinator import NavigationCoordinator
from barks_reader.ui.platform_window_utils import WindowManager
from barks_reader.ui.reader_keyboard_nav import (
    ActionBarNavMixin,
    DropdownNavMixin,
)
from barks_reader.ui.reader_screens import ReaderScreen
from barks_reader.ui.reader_tree_builder import ReaderTreeBuilder
from barks_reader.ui.reader_ui_classes import (
    ACTION_BAR_SIZE_Y,
    ReaderTreeBuilderEventDispatcher,
)
from barks_reader.ui.snapshot_applicator import SnapshotApplicator
from barks_reader.ui.tree_view_manager import TreeViewManager
from barks_reader.ui.user_error_handler import UserErrorHandler
from barks_reader.ui.view_state_manager import ImageThemesChange, ImageThemesToUse, ViewStateManager
from barks_reader.ui.view_states import ViewStates

if TYPE_CHECKING:
    from barks_fantagraphics.comics_database import ComicsDatabase
    from kivy.uix.button import Button
    from kivy.uix.widget import Widget

    from barks_reader.core.filtered_title_lists import FilteredTitleLists
    from barks_reader.core.reader_settings import ReaderSettings
    from barks_reader.ui.comic_book_reader import ComicBookReaderScreen
    from barks_reader.ui.font_manager import FontManager
    from barks_reader.ui.reader_screens import ScreenSwitchers
    from barks_reader.ui.screen_bundle import ScreenBundle

MAIN_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")


class MainScreen(ReaderScreen, DropdownNavMixin, ActionBarNavMixin):
    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
    ACTION_BAR_TITLE_COLOR = (0.0, 1.0, 0.0, 1.0)
    app_icon_filepath = StringProperty()
    app_title = StringProperty()

    is_first_use_of_reader = BooleanProperty(defaultvalue=False)

    def __init__(
        self,
        comics_database: ComicsDatabase,
        reader_settings: ReaderSettings,
        reader_tree_events: ReaderTreeBuilderEventDispatcher,
        filtered_title_lists: FilteredTitleLists,
        screen_switchers: ScreenSwitchers,
        screens: ScreenBundle,
        font_manager: FontManager,
        user_error_handler: UserErrorHandler,
        **kwargs: str,
    ) -> None:
        super().__init__(**kwargs)

        self._comics_database = comics_database
        self._reader_settings = reader_settings
        self._screen_switchers = screen_switchers
        self._font_manager = font_manager
        self._user_error_handler = user_error_handler
        self._screens = screens

        self._wire_screens(screens)

        self._title_lists = filtered_title_lists.get_title_lists()
        resolver = ReaderFilePathsResolver(self._reader_settings.file_paths)
        self._random_title_images = ImageSelector(resolver, self._reader_settings)
        self.is_first_use_of_reader = self._reader_settings.is_first_use_of_reader

        self._action_bar = self.ids.action_bar
        self._fullscreen_button = self.ids.fullscreen_button
        self._json_settings_manager = SettingsManager(self._reader_settings.get_user_data_path())
        self._special_fanta_overrides = SpecialFantaOverrides(self._reader_settings)

        self._reader_tree_events = reader_tree_events

        user_error_handler = UserErrorHandler(reader_settings, screen_switchers.switch_to_settings)

        self._comic_reader_manager = ComicReaderManager(
            self._comics_database,
            self._reader_settings,
            self._json_settings_manager,
            self._tree_view_screen,
            user_error_handler,
        )

        self._window_helper = MainScreenWindowHelper(
            host_screen=self,
            comic_reader_manager=self._comic_reader_manager,
            action_bar=self._action_bar,
            fullscreen_button=self._fullscreen_button,
            fullscreen_icon=str(
                self._reader_settings.sys_file_paths.get_barks_reader_fullscreen_icon_file()
            ),
            fullscreen_exit_icon=str(
                self._reader_settings.sys_file_paths.get_barks_reader_fullscreen_exit_icon_file()
            ),
            main_layout=self.ids.main_layout,
            fun_image_view_screen=self._fun_image_view_screen,
            update_fonts=self.update_fonts,
        )

        background_views = BackgroundViews(
            self._reader_settings,
            self._title_lists,
            self._random_title_images,
        )

        applicator = SnapshotApplicator(
            screens,
            self._reader_settings.file_paths.barks_panels_are_encrypted,
        )

        self._view_state_manager = ViewStateManager(
            self._reader_settings,
            background_views,
            screens,
            applicator,
            self._on_view_state_changed,
        )

        self._nav_coord = NavigationCoordinator(
            reader_settings=self._reader_settings,
            comics_database=self._comics_database,
            view_state_manager=self._view_state_manager,
            comic_reader_manager=self._comic_reader_manager,
            bottom_title_view_screen=self._bottom_title_view_screen,
            tree_view_screen=self._tree_view_screen,
            screen_switchers=self._screen_switchers,
            special_fanta_overrides=self._special_fanta_overrides,
            user_error_handler=user_error_handler,
            on_active_changed=self._is_active,
        )

        self._tree_view_manager = TreeViewManager(
            self._view_state_manager,
            screens,
            self._nav_coord,
            sys_file_paths=self._reader_settings.sys_file_paths,
        )

        self._nav_coord.set_tree_view_manager(self._tree_view_manager)

        self.app_icon_filepath = str(self._random_title_images.get_random_reader_app_icon_file())

        self._app_initializer = AppInitializer(
            self._reader_settings,
            user_error_handler,
            self._comic_reader_manager,
            self._json_settings_manager,
            self._view_state_manager,
            self._tree_view_manager,
            self._tree_view_screen,
        )

        # X is first; icon_hitbox is last so Left from X wraps to it.
        self._setup_action_bar_nav(
            [
                self.ids.quit_button,
                self.ids.fullscreen_button,
                self.ids.go_back_button,
                self.ids.collapse_button,
                self.ids.change_pics_button,
                self.ids.menu_button,
                self.ids.icon_hitbox,
            ]
        )
        self._nav = MainScreenNavigation(
            screens=screens,
            tree_view_manager=self._tree_view_manager,
            bottom_base_view_screen=self._bottom_base_view_screen,
            on_title_activated=self.on_title_portal_image_pressed,
            enter_menu_mode=self._enter_menu_mode,
            handle_menu_key=self._handle_menu_key,
            is_in_menu_mode=lambda: self._menu_mode,
        )
        Window.bind(on_key_down=self._on_key_down)

        self._active = True

        self._set_initial_state()

    def _wire_screens(self, screens: ScreenBundle) -> None:
        self._tree_view_screen = screens.tree_view
        self._bottom_title_view_screen = screens.bottom_title_view
        self._fun_image_view_screen = screens.fun_image_view
        self._main_index_screen = screens.main_index
        self._speech_index_screen = screens.speech_index
        self._names_index_screen = screens.names_index
        self._locations_index_screen = screens.locations_index
        self._statistics_screen = screens.statistics
        self._search_screen = screens.search

        self.ids.main_layout.add_widget(self._tree_view_screen)
        self._bottom_base_view_screen = Screen(size_hint=(1, 1))
        for screen in screens.bottom_screens:
            self._bottom_base_view_screen.add_widget(screen)
        self.ids.main_layout.add_widget(self._bottom_base_view_screen)

    def open_menu_dots(self, button: Button) -> None:
        self.menu_dots_dropdown.open(button)

    @override
    def _activate_focused_button(self) -> None:
        if self._menu_buttons[self._focused_btn_idx] is self.ids.menu_button:
            self._last_used_btn_idx = self._focused_btn_idx
            self._open_menu_dots_for_keyboard()
        else:
            super()._activate_focused_button()

    def _get_dropdown_buttons(self) -> list:
        return list(reversed(self.menu_dots_dropdown.container.children))

    def _dismiss_dropdown(self) -> None:
        self.menu_dots_dropdown.dismiss()

    def _open_menu_dots_for_keyboard(self) -> None:
        self._clear_menu_focus()
        self.open_menu_dots(self.ids.menu_button)
        self._enter_dropdown_nav(initial_idx=0)

    def _on_menu_dropdown_dismissed(self, instance: Widget) -> None:
        self._on_dropdown_dismissed(instance)

    def _set_initial_state(self) -> None:
        self._setup_dropdown_nav()
        self.menu_dots_dropdown = Factory.MenuDropDown()
        self.menu_dots_dropdown.bind(on_select=self.on_action_bar_menu_dots_selected)
        self.menu_dots_dropdown.bind(on_dismiss=self._on_menu_dropdown_dismissed)

        self._view_state_manager.set_view_state(ViewStates.PRE_INIT)

        self._bind_screen_callbacks()

        self._window_helper.resize_binding()
        self._update_action_bar_visibility()

    def _bind_screen_callbacks(self) -> None:
        self._tree_view_screen.on_goto_title = self._on_goto_top_view_title

        for index_screen in self._screens.index_screens:
            index_screen.on_goto_title = self._nav_coord.navigate_to_title_with_page
            index_screen.on_goto_background_title_func = self._nav_coord.navigate_to_chrono_title

        self._search_screen.on_goto_title = self._nav_coord.navigate_to_search_result
        self._search_screen.on_goto_title_with_page = self._nav_coord.navigate_to_title_with_page
        self._search_screen.on_goto_background_title_func = self._nav_coord.navigate_to_chrono_title
        self._search_screen.on_search_results_title_changed = (
            self._view_state_manager.update_search_background
        )

        self._bottom_title_view_screen.set_special_fanta_overrides(self._special_fanta_overrides)
        self._bottom_title_view_screen.on_title_portal_image_pressed_func = (
            self.on_title_portal_image_pressed
        )

        self._fun_image_view_screen.ids.checkbox_all_image_types.bind(
            active=self.on_checkbox_all_image_types_changed
        )
        self._fun_image_view_screen.ids.checkbox_custom_image_types.bind(
            active=self.on_checkbox_custom_image_types_changed
        )
        self._fun_image_view_screen.on_goto_title_func = self._on_goto_fun_view_title

        self._reader_tree_events.bind(
            on_finished_building_event=self._app_initializer.on_tree_build_finished
        )

    def _is_active(self, active: bool) -> None:
        if self._active == active:
            return

        logger.debug(f"MainScreen active changed from {self._active} to {active}.")
        self._active = active

        if active:
            Window.bind(on_key_down=self._on_key_down)
        else:
            if self._nav.is_in_bottom_focus:
                self._nav.exit_bottom_focus()
            if self._menu_mode:
                self._exit_menu_mode()
            Window.unbind(on_key_down=self._on_key_down)

        width, content_h = get_win_dimensions(Window.height - ACTION_BAR_SIZE_Y, Window.width)
        self.size = width, content_h + ACTION_BAR_SIZE_Y

        logger.debug(
            f"Main screen self._active = {self._active}:"
            f" x,y = {self.x},{self.y},"
            f" Window.size = {Window.size},"
            f" self.size = {self.size}."
            f" Screen mode = {WindowManager.get_screen_mode_now()},"
            f" self._actionbar height = {self._action_bar.height}."
        )

        self._update_action_bar_visibility()

    def on_touch_down(self, touch: object) -> bool:
        if self._active:
            self._clear_menu_on_touch()
            # noinspection PyUnresolvedReferences
            if (
                self._nav.is_in_bottom_focus
                and not self._bottom_base_view_screen.collide_point(*touch.pos)  # ty: ignore[unresolved-attribute]
            ):
                self._nav.exit_bottom_focus()
        return bool(super().on_touch_down(touch))

    def _on_key_down(
        self, _window: object, key: int, _scancode: int, _codepoint: str, _modifier: list
    ) -> bool:
        return self._nav.handle_key(key)

    def set_comic_book_reader_screen(self, comic_book_reader_screen: ComicBookReaderScreen) -> None:
        self._comic_reader_manager.set_comic_book_reader_screen(comic_book_reader_screen)

    def app_closing(self) -> None:
        logger.debug("Closing app...")

        self._window_helper.exit_fullscreen()

        if not self._tree_view_screen.get_selected_node():
            self._json_settings_manager.save_last_selected_node_path(None)
            logger.debug("Settings: No selected node to save.")
        else:
            self._json_settings_manager.save_last_selected_node_path(
                self._tree_view_screen.get_selected_node()
            )

        # TODO: Still need a stale check?
        # This is not a bad place to give a warning if there is stale cpi data.
        # It's not easy to do near the start of the app because of cpi module load times.
        #        cpi_inflate.check_for_stale_data()  # noqa: ERA001

    def build_tree_view(self) -> None:
        tree_builder = ReaderTreeBuilder(
            self._reader_settings,
            self._tree_view_screen.ids.reader_tree_view,
            self._reader_tree_events,
            self._tree_view_manager,
            self._title_lists,
        )

        self._nav_coord.set_year_range_nodes(tree_builder.chrono_year_range_nodes)
        self._app_initializer.start(tree_builder, self._on_tree_build_finished)

    def _on_tree_build_finished(self) -> None:
        pass

    def display_settings(self, app_window: Widget, settings: Widget) -> bool:
        logger.debug("Display settings object.")

        if settings in app_window.children:
            return False

        app_window.add_widget(settings)

        settings.size_hint = (None, None)
        settings.size = self.size
        settings.pos_hint = {"center_x": 0.5, "center_y": 0.5}

        return True

    def _on_view_state_changed(self, view_state: ViewStates) -> None:
        self.ids.collapse_button.disabled = view_state == ViewStates.INITIAL

    def on_action_bar_go_back(self) -> None:
        logger.info("'Go back' menu item selected.")
        self._tree_view_manager.go_back_to_previous_node()
        Clock.schedule_once(lambda _dt: self._nav.enter_bottom_focus_if_index_visible(), 0)

    def on_action_bar_collapse(self) -> None:
        self._tree_view_manager.deselect_and_close_open_nodes()

    def on_action_bar_change_view_images(self) -> None:
        self.app_icon_filepath = str(self._random_title_images.get_random_reader_app_icon_file())
        self._view_state_manager.change_background_views()

    def on_action_bar_menu_dots_selected(self, _instance: Widget, value: str) -> None:
        if value == "settings":
            App.get_running_app().open_settings()
        elif value == "how-to":
            self.open_how_to()
        elif value == "about":
            self.open_about()
        else:
            msg = f"Invalid menu option: '{value}'."
            raise ValueError(msg)

    def open_how_to(self) -> None:
        doc_dir = self._reader_settings.sys_file_paths.get_how_to_doc_dir()
        self._nav_coord.open_document(doc_dir, "How To Use the Barks Reader")

    def open_about(self) -> None:
        show_about_box(
            self._font_manager,
            self._reader_settings.sys_file_paths.get_about_background_path(),
        )

    def _update_action_bar_visibility(self) -> None:
        if self._active:
            self._window_helper.show_action_bar()
        else:
            # Delay the hide a bit so we can't see it move. After a second it should be
            # covered by another screen.
            Clock.schedule_once(lambda _dt: self._window_helper.hide_action_bar(), 1)

    def toggle_screen_mode(self) -> None:
        self._window_helper.toggle_screen_mode()

    def force_fullscreen(self) -> None:
        self._window_helper.force_fullscreen()

    def update_fonts(self, height: int) -> None:
        self._font_manager.update_font_sizes(height)
        self.app_title = get_action_bar_title(self._font_manager, APP_TITLE)

    def _on_goto_top_view_title(self) -> None:
        self._nav_coord.navigate_to_chrono_title(self._view_state_manager.get_top_view_image_info())

    def _on_goto_fun_view_title(self) -> None:
        self._nav_coord.navigate_to_chrono_title(
            self._view_state_manager.get_bottom_view_fun_image_info()
        )

    def goto_reader_icon_title(self) -> None:
        logger.debug(f'App reader icon "{self.app_icon_filepath}" pressed.')

        icon_path = Path(self.app_icon_filepath)
        title_str = get_title_str_from_reader_icon_file(icon_path)
        if title_str not in BARKS_TITLE_DICT:
            msg = f'Invalid title string: "{title_str}"'
            raise ValueError(msg)

        title = BARKS_TITLE_DICT[title_str]
        image_info = ImageInfo(icon_path, title)
        self._nav_coord.navigate_to_chrono_title(image_info)

    @override
    def on_document_reader_closed(self) -> None:
        self._is_active(active=True)
        self._nav_coord.on_document_closed()

    def on_checkbox_all_image_types_changed(self, _instance: Widget, use_all_images: bool) -> None:
        self._view_state_manager.bottom_view_fun_image_themes_changed(
            ImageThemesToUse.ALL if use_all_images else ImageThemesToUse.CUSTOM,
        )

    def on_checkbox_custom_image_types_changed(
        self, _instance: Widget, use_custom_images: bool
    ) -> None:
        self._view_state_manager.bottom_view_fun_image_themes_changed(
            ImageThemesToUse.ALL if not use_custom_images else ImageThemesToUse.CUSTOM,
        )

    def on_checkbox_row_changed(self, checkbox_row: Factory.CheckBoxRow) -> None:
        self._view_state_manager.bottom_view_alter_fun_image_themes(
            checkbox_row.theme_enum,
            ImageThemesChange.ADD if checkbox_row.active else ImageThemesChange.DISCARD,
        )

    def on_title_portal_image_pressed(self) -> None:
        if self._nav_coord.current_fanta_info is None:
            logger.error("Title portal image pressed pressed. But no title selected.")
            return

        volumes_state_ok, err_msg = self._app_initializer.is_fanta_volumes_state_ok()
        if not volumes_state_ok:
            logger.error(f"Title portal image pressed pressed. But {err_msg}.")
            return

        logger.debug("Title portal image pressed pressed.")

        self._nav.save_focus_before_comic()
        if self._nav_coord.read_comic():
            self._set_no_longer_first_use()

    @override
    def on_comic_closed(self) -> None:
        self._is_active(active=True)
        self._nav.restore_focus_after_comic()
        self._nav_coord.on_comic_closed()

    def _set_no_longer_first_use(self) -> None:
        if not self.is_first_use_of_reader:
            return

        assert self._reader_settings.is_first_use_of_reader
        self._reader_settings.is_first_use_of_reader = False
        self.is_first_use_of_reader = False
        self._bottom_title_view_screen.is_first_use_of_reader = False
