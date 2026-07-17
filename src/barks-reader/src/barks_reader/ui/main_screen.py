from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from barks_fantagraphics.barks_titles import STR_TITLE_TO_ENUM
from barks_fantagraphics.fanta_comics_info import get_fanta_info
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.factory import Factory
from kivy.properties import BooleanProperty, StringProperty  # ty: ignore[unresolved-import]
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput
from loguru import logger

from barks_reader.core.image_selector import ImageInfo
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.reader_consts_and_types import APP_TITLE
from barks_reader.core.reader_formatter import get_action_bar_title
from barks_reader.core.reader_utils import (
    get_title_str_from_reader_icon_file,
    get_win_dimensions,
)

from .about_box import show_about_box
from .action_bar_helpers import ACTION_BAR_SIZE_Y
from .main_screen_components import build_main_screen_components
from .platform_window_utils import WindowManager
from .reader_keyboard_nav import (
    ActionBarNavMixin,
    DropdownNavMixin,
    is_escape_key,
)
from .reader_screens import ReaderScreen
from .reader_tree_builder import ReaderTreeBuilder
from .settings_keyboard_nav import SettingsKeyboardNav
from .view_renderer import ImageThemesChange, ImageThemesToUse

if TYPE_CHECKING:
    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.comics_database import ComicsDatabase
    from kivy.uix.button import Button
    from kivy.uix.widget import Widget

    from barks_reader.core.filtered_title_lists import FilteredTitleLists
    from barks_reader.core.image_selector import ImageSelector
    from barks_reader.core.reader_settings import ReaderSettings

    from .comic_book_reader import ComicBookReaderScreen
    from .font_manager import FontManager
    from .reader_screens import ScreenSwitchers
    from .screen_bundle import ScreenBundle
    from .tree_view_nodes import ReaderTreeBuilderEventDispatcher
    from .user_error_handler import UserErrorHandler

MAIN_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")


def _text_input_has_focus() -> bool:
    """Report whether a TextInput currently holds the system keyboard (e.g. settings popup).

    Kivy attaches the requesting widget to ``Window._system_keyboard.target`` and clears
    the widget's ``focus`` when it releases the keyboard, so this reflects the live focus
    state regardless of how the popup was opened (mouse or keyboard).
    """
    keyboard = getattr(Window, "_system_keyboard", None)
    target = getattr(keyboard, "target", None)
    return isinstance(target, TextInput) and bool(getattr(target, "focus", False))


class MainScreen(ReaderScreen, DropdownNavMixin, ActionBarNavMixin):
    ACTION_BAR_HEIGHT = ACTION_BAR_SIZE_Y
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
        window_manager: WindowManager,
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
        self._include_one_pagers_in_chrono = filtered_title_lists.include_one_pagers_in_chrono
        self.is_first_use_of_reader = self._reader_settings.is_first_use_of_reader

        self._action_bar = self.ids.action_bar
        self._fullscreen_button = self.ids.fullscreen_button
        self._reader_tree_events = reader_tree_events

        # Assemble the collaborator graph (see main_screen_components).
        components = build_main_screen_components(self, window_manager)
        self._random_title_images = components.random_title_images
        self._json_settings_manager = components.json_settings_manager
        self._special_fanta_overrides = components.special_fanta_overrides
        self._comic_reader_manager = components.comic_reader_manager
        self._window_helper = components.window_helper
        self._renderer = components.renderer
        self._nav_coord = components.nav_coord
        self._tree_view_manager = components.tree_view_manager
        self._app_initializer = components.app_initializer
        self._nav = components.nav

        self.app_icon_filepath = str(self._random_title_images.get_random_reader_app_icon_file())

        # X is first; icon_hitbox is last so Left from X wraps to it.
        self._setup_action_bar_nav(
            [
                self.ids.quit_button,
                self.ids.fullscreen_button,
                self.ids.go_back_button,
                self.ids.collapse_button,
                self.ids.change_pics_button,
                self.ids.menu_button,
                self.ids.action_bar.icon_hitbox,
            ]
        )
        Window.bind(on_key_down=self._on_key_down)

        self._settings_nav: SettingsKeyboardNav | None = None
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
        self._history_screen = screens.history
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

    def _get_dropdown_buttons(self) -> list[Button]:
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

        self._renderer.render_state(ViewStates.PRE_INIT)

        self._bind_screen_callbacks()

        self._window_helper.resize_binding()
        self._update_action_bar_visibility()

    def _bind_screen_callbacks(self) -> None:
        self._tree_view_screen.on_goto_title = self._on_goto_top_view_title

        for index_screen in self._screens.index_screens:
            index_screen.on_goto_title = self._nav_coord.navigate_to_title_with_page
            index_screen.on_goto_background_title_func = self._nav_coord.navigate_to_chrono_title

        self._history_screen.on_goto_title = self._on_goto_history_title
        self._history_screen.get_background_image = self._get_history_background_image

        self._search_screen.on_goto_title = self._nav_coord.navigate_to_search_result
        self._search_screen.on_goto_title_with_page = self._nav_coord.navigate_to_title_with_page
        self._search_screen.on_goto_background_title_func = self._nav_coord.navigate_to_chrono_title
        self._search_screen.on_search_results_title_changed = (
            self._renderer.update_search_background
        )

        self._bottom_title_view_screen.set_special_fanta_overrides(self._special_fanta_overrides)
        self._bottom_title_view_screen.on_title_portal_image_pressed_func = (
            self.on_title_portal_image_pressed
        )
        self._bottom_title_view_screen.on_wiki_page_button_pressed_func = (
            self.on_wiki_page_button_pressed
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
        if width > 0 and content_h > 0:
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
            if (
                self._nav.is_in_bottom_focus
                and not self._bottom_base_view_screen.collide_point(*touch.pos)  # ty: ignore[unresolved-attribute]
            ):
                self._nav.exit_bottom_focus()
        return bool(super().on_touch_down(touch))

    def _on_key_down(
        self, _window: object, key: int, _scancode: int, _codepoint: str, _modifier: list[str]
    ) -> bool:
        # Ignore keys while another screen is on top (comic/document/wiki reader).
        # Its own handler owns the keyboard; in particular the wiki reader's search
        # field must receive keystrokes rather than have them drive this tree. The
        # main-screen handler stays bound throughout, so this guard is what yields.
        if self.manager is not None and self.manager.current != self.name:
            return False
        # When a text field holds the keyboard (e.g. editing a directory path in a
        # settings popup), let it receive cursor/editing keystrokes. Kivy binds the
        # system keyboard to Window.on_key_down, so returning truthy here would consume
        # the key before the focused TextInput's handler runs. Escape still falls through
        # so the settings/popup close handling below can run.
        if not is_escape_key(key) and _text_input_has_focus():
            return False
        if self._settings_nav is not None:
            if self._settings_nav.handle_key(key):
                return True
            if is_escape_key(key):
                self._close_settings()
                return True
            return True
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
            include_one_pagers_in_chrono=self._include_one_pagers_in_chrono,
        )

        self._nav_coord.set_year_range_nodes(tree_builder.chrono_year_range_nodes)
        self._nav_coord.set_series_nodes(tree_builder.series_nodes)
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

        self._settings_nav = SettingsKeyboardNav(settings)
        settings.bind(on_close=self._on_settings_closed)

        return True

    def _on_settings_closed(self, *_args: object) -> None:
        if self._settings_nav is not None:
            self._settings_nav.reset()
            self._settings_nav = None

    def _close_settings(self) -> None:
        if self._settings_nav is not None:
            self._settings_nav.reset()
            self._settings_nav = None
        App.get_running_app().close_settings()

    def _on_view_state_changed(self, view_state: ViewStates) -> None:
        self.ids.collapse_button.disabled = view_state == ViewStates.INITIAL
        self._nav.on_bottom_screen_visibility_changed()

    def on_action_bar_go_back(self) -> None:
        logger.info("'Go back' menu item selected.")
        self._tree_view_manager.go_back_to_previous_node()
        Clock.schedule_once(lambda _dt: self._nav.enter_bottom_focus_if_index_visible(), 0)

    def on_action_bar_collapse(self) -> None:
        self._tree_view_manager.deselect_and_close_open_nodes(from_collapse_all=True)

    def on_action_bar_change_view_images(self) -> None:
        self.app_icon_filepath = str(self._random_title_images.get_random_reader_app_icon_file())
        self._renderer.refresh()
        if self._history_screen.is_visible:
            self._history_screen.update_background_image()

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
        self._nav_coord.navigate_to_chrono_title(self._renderer.get_top_view_image_info())

    def _on_goto_fun_view_title(self) -> None:
        self._nav_coord.navigate_to_chrono_title(self._renderer.get_bottom_view_fun_image_info())

    def goto_reader_icon_title(self) -> None:
        logger.debug(f'App reader icon "{self.app_icon_filepath}" pressed.')

        icon_path = Path(self.app_icon_filepath)
        title_str = get_title_str_from_reader_icon_file(icon_path)
        if title_str not in STR_TITLE_TO_ENUM:
            msg = f'Invalid title string: "{title_str}"'
            raise ValueError(msg)

        title = STR_TITLE_TO_ENUM[title_str]
        image_info = ImageInfo(icon_path, title)
        self._nav_coord.navigate_to_chrono_title(image_info)

    @override
    def on_document_reader_closed(self) -> None:
        self._is_active(active=True)
        self._nav_coord.on_document_closed()

    def on_checkbox_all_image_types_changed(self, _instance: Widget, use_all_images: bool) -> None:
        self._renderer.bottom_view_fun_image_themes_changed(
            ImageThemesToUse.ALL if use_all_images else ImageThemesToUse.CUSTOM,
        )

    def on_checkbox_custom_image_types_changed(
        self, _instance: Widget, use_custom_images: bool
    ) -> None:
        self._renderer.bottom_view_fun_image_themes_changed(
            ImageThemesToUse.ALL if not use_custom_images else ImageThemesToUse.CUSTOM,
        )

    def on_checkbox_row_changed(self, checkbox_row: Factory.CheckBoxRow) -> None:
        self._renderer.bottom_view_alter_fun_image_themes(
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

    def on_wiki_page_button_pressed(self) -> None:
        """Open the wiki at the current title's story page (the "Wiki Page" chip)."""
        fanta_info = self._nav_coord.current_fanta_info
        if fanta_info is None:
            logger.error("Wiki page button pressed. But no title selected.")
            return

        logger.debug("Wiki page button pressed.")
        self._nav_coord.open_wiki_page_for_title(fanta_info.comic_book_info.title)

    @override
    def on_comic_closed(self) -> None:
        self._is_active(active=True)
        self._nav.restore_focus_after_comic()
        self._nav_coord.on_comic_closed()

    @override
    def on_wiki_reader_closed(self) -> None:
        self._is_active(active=True)

    def goto_title_from_wiki(self, title: Titles) -> None:
        """Select ``title`` in the tree and title view, on behalf of the wiki screen.

        The index screens' ``on_goto_title`` behavior — the wiki closes itself
        first, so the user lands here with the title's reading controls up.
        """
        self._nav_coord.navigate_to_chrono_title(ImageInfo(from_title=title, filename=None))

    def _on_goto_history_title(self, title: Titles) -> None:
        """Select ``title`` in the tree and title view, from a history row."""
        self._nav_coord.navigate_to_chrono_title(ImageInfo(from_title=title, filename=None))

    def _get_history_background_image(self, titles: list[Titles]) -> ImageInfo:
        """Pick a random panel image from the history's titles for the backdrop."""
        title_infos = [info for title in titles if (info := get_fanta_info(title)) is not None]
        return self._random_title_images.get_random_image(title_infos)

    @property
    def image_selector(self) -> ImageSelector:
        """The app-wide panel image selector (share it so no-repeat memory pools)."""
        return self._random_title_images

    def _set_no_longer_first_use(self) -> None:
        if not self.is_first_use_of_reader:
            return

        assert self._reader_settings.is_first_use_of_reader
        self._reader_settings.is_first_use_of_reader = False
        self.is_first_use_of_reader = False
        self._bottom_title_view_screen.is_first_use_of_reader = False
