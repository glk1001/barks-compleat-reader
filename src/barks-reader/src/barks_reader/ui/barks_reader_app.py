# ruff: noqa: ERA001

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, LiteralString, override

from barks_fantagraphics.comics_database import ComicsDatabase
from comic_utils.timing import Timing
from kivy.app import App  # can take ~2s in VM Windows
from kivy.clock import Clock
from kivy.config import Config
from kivy.core.window import Window, WindowBase  # can take ~1s in VM Windows
from kivy.lang import Builder
from kivy.uix.settings import Settings, SettingsWithSpinner  # can take ~1s in VM Windows
from kivy.utils import escape_markup
from loguru import logger
from screeninfo import get_monitors

from barks_reader.core import services
from barks_reader.core.filtered_title_lists import FilteredTitleLists
from barks_reader.core.reader_consts_and_types import APP_TITLE, LONG_PATH_SETTING, OPTIONS_SETTING
from barks_reader.core.reader_settings import BARKS_READER_SECTION
from barks_reader.core.reader_utils import get_win_width_from_height
from barks_reader.core.screen_metrics import (
    SCREEN_METRICS,
    get_best_window_height_fit,
)
from barks_reader.core.settings_notifier import settings_notifier
from barks_reader.ui.bottom_title_view_screen import (
    BOTTOM_TITLE_VIEW_SCREEN_KV_FILE,
    BottomTitleViewScreen,
)
from barks_reader.ui.comic_book_reader import get_barks_comic_reader_screen
from barks_reader.ui.error_handling import handle_app_fail_with_traceback
from barks_reader.ui.font_manager import FontManager
from barks_reader.ui.fun_image_view_screen import FUN_IMAGE_VIEW_SCREEN_KV_FILE, FunImageViewScreen
from barks_reader.ui.index_screen import INDEX_SCREEN_KV_FILE
from barks_reader.ui.intro_compleat_barks_reader import (
    get_intro_compleat_barks_reader_screen,  # can take ~3s on VM Windows
)
from barks_reader.ui.main_index_screen import MainIndexScreen
from barks_reader.ui.main_screen import MAIN_SCREEN_KV_FILE, MainScreen  # can take ~4s on VM Window
from barks_reader.ui.platform_window_utils import log_screen_metrics
from barks_reader.ui.reader_screens import (
    COMIC_BOOK_READER_SCREEN,
    INTRO_COMPLEAT_BARKS_READER_SCREEN,
    MAIN_READER_SCREEN,
    ReaderScreenManager,
    ReaderScreens,
)
from barks_reader.ui.reader_settings_buildable import BuildableReaderSettings
from barks_reader.ui.reader_ui_classes import (
    ACTION_BAR_SIZE_Y,
    READER_POPUPS_KV_FILE,
    READER_TREE_VIEW_KV_FILE,
    ReaderTreeBuilderEventDispatcher,
    set_kivy_busy_cursor,
    set_kivy_normal_cursor,
)
from barks_reader.ui.settings_fix import SettingLongPath, SettingOptionsWithValue
from barks_reader.ui.speech_index_screen import SpeechIndexScreen
from barks_reader.ui.tree_view_screen import TREE_VIEW_SCREEN_KV_FILE, TreeViewScreen
from barks_reader.ui.user_error_handler import UserErrorHandler

if TYPE_CHECKING:
    from types import TracebackType

    from kivy.config import ConfigParser
    from kivy.uix.screenmanager import ScreenManager
    from kivy.uix.widget import Widget

    from barks_reader.core.config_info import ConfigInfo


COMIC_PAGE_ASPECT_RATIO = 3200.0 / 2120.0
DEFAULT_WINDOW_HEIGHT_PERCENT = 0.96
WINDOW_SHOW_DELAY = 2.0
MOVE_SETTLE_DELAY = 4.0
DEFAULT_WINDOW_LEFT = 2400
DEFAULT_WINDOW_TOP = 50


class BarksReaderApp(App):
    """The main Kivy application class for the Barks Reader."""

    def __init__(self, config_info: ConfigInfo, comics_db: ComicsDatabase, **kwargs: str) -> None:
        super().__init__(**kwargs)

        self.timing = Timing()

        self.title = APP_TITLE
        self.settings_cls = SettingsWithSpinner

        self._config_info = config_info
        self._comics_database = comics_db
        self.reader_settings = BuildableReaderSettings()
        self.font_manager = FontManager()

        self._reader_screen_manager = ReaderScreenManager(self.open_settings)
        self._screen_switchers = self._reader_screen_manager.screen_switchers

        self._main_screen: MainScreen | None = None

        self._current_monitor = SCREEN_METRICS.get_monitor_for_pos(Window.left, Window.top)
        self._resize_event = None
        self._resize_requested_size = 0, 0

    # TODO: Move this Window stuff to MainScreen.
    def _on_window_pos_change(self, _window: WindowBase) -> None:
        # Check if we've changed monitors. Adjust height if required.

        if Window.fullscreen:
            # Leave fullscreen alone.
            return

        monitor = SCREEN_METRICS.get_monitor_for_pos(Window.left, Window.top)
        assert monitor is not None
        if monitor.display == self._current_monitor.display:
            return

        old_height = Window.height
        old_max_height = get_best_window_height_fit(self._current_monitor.height_pixels)
        scale_factor = old_height / old_max_height
        logger.debug(
            f"Changed to monitor {monitor.display} from monitor {self._current_monitor.display}:"
            f" old size = {Window.size}, old_max_height = {old_max_height},"
            f" scale_factor = {scale_factor:.2f}."
        )

        self._current_monitor = monitor

        new_max_height = get_best_window_height_fit(monitor.height_pixels)
        new_height = round(scale_factor * new_max_height)

        if new_height != old_height:
            self._change_win_height_after_move(new_height)

    def _change_win_height_after_move(self, new_height: int) -> None:
        # Changing window size after a move is tricky. What I think happens is the OS
        # window manager calls window resize at end of the drag operation and this size
        # is the old monitor size which overrides the new size. To work around this a
        # guard is set up and used in the resize event handler '_on_window_resize'.

        new_width = get_win_width_from_height(new_height - ACTION_BAR_SIZE_Y)

        def do_resize(_dt: float) -> None:
            logger.debug(f"Executing resize to new monitor size ({new_width}, {new_height}).")
            Window.size = (new_width, new_height)

        def do_reset_resize(_dt: float) -> None:
            logger.debug("Clearing resize event.")
            self._resize_event = None
            self._resize_requested_size = 0, 0

        self._resize_requested_size = new_width, new_height

        Clock.schedule_once(do_resize, 0)
        self._resize_event = Clock.schedule_once(do_reset_resize, MOVE_SETTLE_DELAY)

    def _on_window_resize(self, _window: WindowBase, width: int, height: int) -> None:
        # logger.debug(
        #     f"Main window resize event:"
        #     f" width, height = {width},{height},"
        #     f" Window.fullscreen = {Window.fullscreen},"
        #     f" self._resize_event = {self._resize_event},"
        #     f" self._resize_requested_size = {self._resize_requested_size},"
        # )

        if Window.fullscreen:
            # Leave fullscreen alone.
            return

        if not self._resize_event or ((width, height) == self._resize_requested_size):
            return

        assert self._resize_requested_size != (0, 0)
        Window.size = self._resize_requested_size
        logger.debug(f"Forced reset main window size after resize event: {Window.size}.")
        self._main_screen.update_fonts(Window.height)

    def close_app(self) -> None:
        self._main_screen.app_closing()
        App.get_running_app().stop()
        Window.close()

    @override
    def display_settings(self, settings: Widget) -> bool:
        win = self._app_window
        if not win:
            msg = "No windows are set on the application, you cannot open settings yet."
            raise RuntimeError(msg)

        return self._main_screen.display_settings(win, settings)

    # noinspection LongLine
    @override
    def get_application_config(self, _default_path: str = "") -> LiteralString | str:  # ty:ignore[invalid-method-override]
        return str(self._config_info.app_config_path)

    @override
    def build_config(self, config: ConfigParser) -> None:
        """Set default values for the application configuration."""
        # Set default window geometry if not already present in the config file
        primary_monitor = get_monitors()[0]
        default_height = round(DEFAULT_WINDOW_HEIGHT_PERCENT * primary_monitor.height)
        default_width = round(default_height / COMIC_PAGE_ASPECT_RATIO)
        default_height_incl_action_bar = default_height + ACTION_BAR_SIZE_Y

        config.setdefaults(
            "graphics",
            {
                "width": default_width,
                "height": default_height_incl_action_bar,
                "left": DEFAULT_WINDOW_LEFT,
                "top": DEFAULT_WINDOW_TOP,
            },
        )

        # Delegate to the settings class to set its own defaults
        self.reader_settings.build_config(config)

    @override
    def build_settings(self, settings: Settings) -> None:
        # Register our custom widget type with the name 'longpath'
        settings.register_type(LONG_PATH_SETTING, SettingLongPath)
        settings.register_type(OPTIONS_SETTING, SettingOptionsWithValue)

        self.reader_settings.build_settings(settings)
        self.config.write()
        settings.interface.menu.height = ACTION_BAR_SIZE_Y

        logger.info(f"Time taken up to build settings: {self.timing.get_elapsed_time_with_unit()}.")

    @override
    def on_config_change(
        self,
        _config: ConfigParser,
        section: str,
        key: str,
        value: Any,
    ) -> None:  # ty:ignore[invalid-method-override]
        logger.info(f"Config change: section = '{section}', key = '{key}', value = '{value}'.")
        if self.reader_settings.on_changed_setting(section, key, value) and (
            section == BARKS_READER_SECTION
        ):
            settings_notifier.notify(section, key)

    @override
    def build(self) -> Widget:
        logger.debug("Building app...")

        assert Window is not None

        self._initialize_settings_and_db()

        logger.debug("Loading kv files...")
        # Pass the font manager to kv lang so it can be accessed
        Builder.load_string("#:set fm app.font_manager")
        Builder.load_string("#:set sys_paths app.reader_settings.sys_file_paths")

        Builder.load_file(str(READER_POPUPS_KV_FILE))
        Builder.load_file(str(READER_TREE_VIEW_KV_FILE))
        Builder.load_file(str(TREE_VIEW_SCREEN_KV_FILE))
        Builder.load_file(str(BOTTOM_TITLE_VIEW_SCREEN_KV_FILE))
        Builder.load_file(str(FUN_IMAGE_VIEW_SCREEN_KV_FILE))
        Builder.load_file(str(INDEX_SCREEN_KV_FILE))
        Builder.load_file(str(MAIN_SCREEN_KV_FILE))

        root = self._build_screens()

        logger.debug("Building the main tree view...")
        self._main_screen.build_tree_view()

        self._finalize_window_setup()

        logger.info(f"Time taken up to build kivy: {self.timing.get_elapsed_time_with_unit()}.")

        return root

    def _initialize_settings_and_db(self) -> None:
        """Handle the initial setup of settings and the database."""
        self.reader_settings.set_config(
            self.config, Path(self.get_application_config()), self._config_info.app_data_dir
        )
        self.reader_settings.set_barks_panels_dir()
        self.reader_settings.validate_settings()

        self._comics_database.set_inset_info(
            self.reader_settings.file_paths.get_comic_inset_files_dir(),
            self.reader_settings.file_paths.get_inset_file_ext(),
        )

        self.reader_settings.sys_file_paths.set_barks_reader_files_dir(
            self.reader_settings.reader_files_dir
        )

    def _build_screens(self) -> ScreenManager:
        logger.debug("Instantiating main screen...")
        # TODO: Can probably move some of these into main_screen
        user_error_handler = UserErrorHandler(
            self.reader_settings, self._reader_screen_manager.screen_switchers.switch_to_settings
        )

        filtered_title_lists = FilteredTitleLists()
        reader_tree_events = ReaderTreeBuilderEventDispatcher()
        tree_view_screen = TreeViewScreen(self.reader_settings)
        bottom_title_view_screen = BottomTitleViewScreen(self.reader_settings, self.font_manager)
        fun_image_view_screen = FunImageViewScreen(self.reader_settings)
        main_index_screen = MainIndexScreen(
            self.reader_settings, self.font_manager, user_error_handler
        )
        speech_index_screen = SpeechIndexScreen(
            self.reader_settings, self.font_manager, user_error_handler
        )
        self._main_screen = MainScreen(
            self._comics_database,
            self.reader_settings,
            reader_tree_events,
            filtered_title_lists,
            self._reader_screen_manager.screen_switchers,
            tree_view_screen,
            bottom_title_view_screen,
            fun_image_view_screen,
            main_index_screen,
            speech_index_screen,
            self.font_manager,
            user_error_handler,
            name=MAIN_READER_SCREEN,
        )
        self._set_custom_title_bar()
        # noinspection LongLine
        self._main_screen.update_fonts(Config.getint("graphics", "height"))  # ty: ignore[unresolved-attribute]

        logger.debug("Instantiating comic reader screen...")
        comic_reader_screen = get_barks_comic_reader_screen(
            COMIC_BOOK_READER_SCREEN,
            self.reader_settings,
            self._main_screen.app_icon_filepath,
            self.font_manager,
            self._screen_switchers.switch_to_comic_book_reader,
            self._screen_switchers.close_comic_book_reader,
        )
        self._main_screen.set_comic_book_reader_screen(comic_reader_screen)

        logger.debug("Instantiating introduction screen...")
        intro_screen = get_intro_compleat_barks_reader_screen(
            INTRO_COMPLEAT_BARKS_READER_SCREEN,
            self.reader_settings,
            self._main_screen.app_icon_filepath,
            self.font_manager,
            self._screen_switchers.close_intro_compleat_barks_reader,
        )

        reader_screens = ReaderScreens(
            self._main_screen,
            comic_reader_screen,
            intro_screen,
        )

        return self._reader_screen_manager.add_screens(reader_screens)

    def _set_custom_title_bar(self) -> None:
        Window.custom_titlebar = True
        title_bar = self._main_screen.ids.draggable_title_bar
        if Window.set_custom_titlebar(title_bar):
            logger.info("Window: setting custom titlebar successful")
        else:
            logger.warning("Window: setting custom titlebar not allowed on this system.")

    def _finalize_window_setup(self) -> None:
        """Finalize window state after the main build process.

        This includes forcing an initial resize event to ensure all widgets
        are correctly sized based on the loaded configuration.
        """
        self.icon = str(self.reader_settings.sys_file_paths.get_barks_reader_app_window_icon_path())

        if SCREEN_METRICS.NUM_MONITORS > 1:
            Window.bind(on_move=self._on_window_pos_change)
            Window.bind(on_resize=self._on_window_resize)

        # This is a known Kivy workaround. By briefly changing the window position,
        # we force an `on_resize` event to fire, which ensures that all UI elements
        # that depend on window size are correctly initialized.
        config_left = Config.getint("graphics", "left")  # ty:ignore[unresolved-attribute]
        Window.left = config_left + 1
        Window.left = config_left
        config_top = Config.getint("graphics", "top")  # ty:ignore[unresolved-attribute]
        Window.top = config_top + 1
        Window.top = config_top

        if self.reader_settings.goto_fullscreen_on_app_start:
            self._main_screen.force_fullscreen()

        # All the behind the scenes sizing and moving is done.
        # Now make the main window visible.
        def show_the_window(*_args: Any) -> None:  # noqa: ANN401
            Window.show()
            _log_screen_settings()

        Clock.schedule_once(show_the_window, WINDOW_SHOW_DELAY)


def _log_screen_settings() -> None:
    logger.info(f"Window pos = {Window.left},{Window.top}.")

    assert Config is not None
    logger.info(
        f"Config win pos = {Config.getint('graphics', 'left')},{Config.getint('graphics', 'top')}."
    )
    logger.info(f"Window size = {Window.size}, dpi = {Window.dpi}.")
    logger.info(
        f"Config win size"
        f" = {Config.getint('graphics', 'width')},{Config.getint('graphics', 'height')}."
    )


# noinspection LongLine
def _handle_app_exception(
    config_info: ConfigInfo,
    exc_type: type[BaseException] | None,
    exc_value: BaseException | None,
    exc_traceback: TracebackType | None,
) -> None:
    handle_app_fail_with_traceback(
        "app",
        "Barks Reader",
        exc_type,
        exc_value,
        exc_traceback,
        log_path=str(config_info.app_log_path),
        log_the_error=False,
        background_image_file=config_info.error_background_path,
    )


def reader_main(config_info: ConfigInfo) -> None:
    # noinspection PyBroadException
    try:
        kivy_services = services.PlatformServices(
            schedule_once=Clock.schedule_once,
            set_busy_cursor=set_kivy_busy_cursor,
            set_normal_cursor=set_kivy_normal_cursor,
            escape_markup=escape_markup,
        )

        # 3. Register it once
        services.register(kivy_services)

        log_screen_metrics()

        comics_database = ComicsDatabase(for_building_comics=False)

        logger.debug("Running kivy app...")

        assert Config is not None
        assert Config.getint("kivy", "exit_on_escape") == 0
        assert config_info.app_log_path is not None
        assert config_info.error_background_path is not None

        kivy_app = BarksReaderApp(config_info, comics_database)

        kivy_app.run()
    except Exception:  # noqa: BLE001
        logger.exception("There's been a program error - the Barks reader app is terminating: ")
        _handle_app_exception(config_info, *sys.exc_info())

    logger.debug("Terminating...")
    logger.info(
        f"Final window size = {Window.size}, dpi = {Window.dpi}, pos = {Window.left},{Window.top}."
    )
