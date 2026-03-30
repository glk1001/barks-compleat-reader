from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, LiteralString, override

from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.entity_types import EntityType
from comic_utils.kivy_patches import apply_text_input_remove_group_patch
from comic_utils.timing import Timing
from kivy.app import App  # can take ~2s in VM Windows
from kivy.clock import Clock
from kivy.config import Config
from kivy.core.window import Window  # can take ~1s in VM Windows
from kivy.lang import Builder
from kivy.uix.settings import Settings, SettingsWithSpinner  # can take ~1s in VM Windows
from kivy.utils import escape_markup
from loguru import logger
from screeninfo import get_monitors

from barks_reader.core import services
from barks_reader.core.filtered_title_lists import FilteredTitleLists
from barks_reader.core.platform_info import PLATFORM, Platform
from barks_reader.core.reader_consts_and_types import APP_TITLE, LONG_PATH_SETTING, OPTIONS_SETTING
from barks_reader.core.reader_settings import BARKS_READER_SECTION
from barks_reader.core.reader_utils import COMIC_PAGE_ASPECT_RATIO
from barks_reader.core.screen_metrics import SCREEN_METRICS
from barks_reader.core.settings_notifier import settings_notifier
from barks_reader.ui.app_window_geometry import AppWindowGeometryHelper
from barks_reader.ui.bottom_title_view_screen import (
    BOTTOM_TITLE_VIEW_SCREEN_KV_FILE,
    BottomTitleViewScreen,
)
from barks_reader.ui.comic_book_reader import get_barks_comic_reader_screen
from barks_reader.ui.document_reader import get_document_reader_screen
from barks_reader.ui.entity_index_screen import EntityIndexScreen
from barks_reader.ui.error_handling import handle_app_fail_with_traceback
from barks_reader.ui.font_manager import FontManager
from barks_reader.ui.fun_image_view_screen import FUN_IMAGE_VIEW_SCREEN_KV_FILE, FunImageViewScreen
from barks_reader.ui.goto_title_overlay import GOTO_TITLE_OVERLAY_KV_FILE
from barks_reader.ui.index_screen import INDEX_SCREEN_KV_FILE
from barks_reader.ui.main_index_screen import MainIndexScreen
from barks_reader.ui.main_screen import MAIN_SCREEN_KV_FILE, MainScreen  # can take ~4s on VM Window
from barks_reader.ui.platform_window_utils import log_screen_metrics
from barks_reader.ui.reader_screens import (
    COMIC_BOOK_READER_SCREEN,
    DOCUMENT_READER_SCREEN,
    MAIN_READER_SCREEN,
    ReaderScreenManager,
    ReaderScreens,
)
from barks_reader.ui.reader_settings_buildable import BuildableReaderSettings
from barks_reader.ui.reader_ui_classes import (
    ACTION_BAR_SIZE_Y,
    KIVY_HELPERS_KV_FILE,
    READER_POPUPS_KV_FILE,
    READER_TREE_VIEW_KV_FILE,
    ReaderTreeBuilderEventDispatcher,
    set_kivy_busy_cursor,
    set_kivy_normal_cursor,
)
from barks_reader.ui.screen_bundle import ScreenBundle
from barks_reader.ui.search_screen import SEARCH_SCREEN_KV_FILE, SearchScreen
from barks_reader.ui.settings_fix import SettingLongPath, SettingOptionsWithValue
from barks_reader.ui.speech_index_screen import SpeechIndexScreen
from barks_reader.ui.statistics_screen import STATISTICS_SCREEN_KV_FILE, StatisticsScreen
from barks_reader.ui.tree_view_screen import TREE_VIEW_SCREEN_KV_FILE, TreeViewScreen
from barks_reader.ui.user_error_handler import UserErrorHandler

if TYPE_CHECKING:
    from types import TracebackType

    from kivy.config import ConfigParser
    from kivy.uix.screenmanager import ScreenManager
    from kivy.uix.widget import Widget

    from barks_reader.core.config_info import ConfigInfo


DEFAULT_WINDOW_HEIGHT_PERCENT = 0.96
WINDOW_SHOW_DELAY = 2.0
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

        self._window_geometry = AppWindowGeometryHelper()

    def suppress_aspect_ratio_correction(self, duration: float = 2.0) -> None:
        """Temporarily suppress aspect ratio corrections.

        Args:
            duration: How long to suppress, in seconds.

        Call this before a programmatic window resize (e.g., closing the comic reader) to
        prevent the correction from firing on spurious OS resize events and creating a loop.

        """
        self._window_geometry.suppress_aspect_ratio_correction(duration)

    def close_app(self) -> None:
        self._window_geometry.stop_polling()
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

    # noinspection LongLine
    @override
    def build(self) -> Widget:
        logger.debug("Building app...")

        assert Window is not None

        # Kivy 2.3.1 bug: several methods call canvas._remove_group() but the
        # Canvas Cython extension only exposes the public remove_group().
        # Patch the Python-level methods that make the bad call instead.
        # TODO: Remove when Kivy fixes canvas._remove_group (broken in Kivy 2.3.1).
        from kivy.uix.screenmanager import SwapTransition  # noqa: PLC0415

        apply_text_input_remove_group_patch()

        if not hasattr(SwapTransition, "_kivy_workaround_applied"):
            _orig_st = SwapTransition.on_complete

            # noinspection PyShadowingNames
            def _patched_swap_on_complete(self: SwapTransition) -> None:
                try:
                    _orig_st(self)
                except AttributeError as exc:
                    if "_remove_group" in str(exc):
                        for screen in self.screen_in, self.screen_out:
                            for canvas in screen.canvas.before, screen.canvas.after:
                                # noinspection SpellCheckingInspection
                                canvas.remove_group("swaptransition_scale")
                        # noinspection LongLine
                        super(SwapTransition, self).on_complete()  # ty:ignore[invalid-super-argument]
                    else:
                        raise

            SwapTransition.on_complete = _patched_swap_on_complete
            SwapTransition._kivy_workaround_applied = True  # noqa: SLF001

        self._initialize_settings_and_db()

        logger.debug("Loading kv files...")
        # Pass the font manager to kv lang so it can be accessed
        Builder.load_string("#:set fm app.font_manager")
        Builder.load_string("#:set sys_paths app.reader_settings.sys_file_paths")

        Builder.load_file(str(KIVY_HELPERS_KV_FILE))
        Builder.load_file(str(READER_POPUPS_KV_FILE))
        Builder.load_file(str(READER_TREE_VIEW_KV_FILE))
        Builder.load_file(str(TREE_VIEW_SCREEN_KV_FILE))
        Builder.load_file(str(BOTTOM_TITLE_VIEW_SCREEN_KV_FILE))
        Builder.load_file(str(FUN_IMAGE_VIEW_SCREEN_KV_FILE))
        Builder.load_file(str(INDEX_SCREEN_KV_FILE))
        Builder.load_file(str(STATISTICS_SCREEN_KV_FILE))
        Builder.load_file(str(SEARCH_SCREEN_KV_FILE))
        Builder.load_file(str(MAIN_SCREEN_KV_FILE))
        Builder.load_file(str(GOTO_TITLE_OVERLAY_KV_FILE))

        root = self._build_screens()

        assert self._main_screen is not None
        self._window_geometry.set_main_screen_callbacks(
            update_fonts=self._main_screen.update_fonts,
        )

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

        if self.reader_settings.use_virtual_keyboard:
            Window.allow_vkeyboard = True
            Window.docked_vkeyboard = True
            Window.single_vkeyboard = True
            Window.use_syskeyboard = False
            if PLATFORM == Platform.LINUX:
                self._enable_linux_touchscreen_input()

        self.reader_settings.validate_settings()

        self._comics_database.set_inset_info(
            self.reader_settings.file_paths.get_comic_inset_files_dir(),
            self.reader_settings.file_paths.get_inset_file_ext(),
        )

        self.reader_settings.sys_file_paths.set_barks_reader_files_dir(
            self.reader_settings.reader_files_dir
        )

    @staticmethod
    def _enable_linux_touchscreen_input() -> None:
        """Register MTD providers so touchscreen taps can be distinguished from mouse clicks."""
        from barks_reader.ui.touch_keyboard import enable_linux_touchscreen_input  # noqa: PLC0415

        enable_linux_touchscreen_input()

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
        names_index_screen = EntityIndexScreen(
            EntityType.PERSON, self.reader_settings, self.font_manager, user_error_handler
        )
        locations_index_screen = EntityIndexScreen(
            EntityType.LOCATION, self.reader_settings, self.font_manager, user_error_handler
        )
        statistics_screen = StatisticsScreen(
            self.reader_settings.sys_file_paths.get_statistics_dir()
        )
        search_screen = SearchScreen(self.reader_settings, self.font_manager)
        screens = ScreenBundle(
            tree_view=tree_view_screen,
            bottom_title_view=bottom_title_view_screen,
            fun_image_view=fun_image_view_screen,
            main_index=main_index_screen,
            speech_index=speech_index_screen,
            names_index=names_index_screen,
            locations_index=locations_index_screen,
            statistics=statistics_screen,
            search=search_screen,
        )
        self._main_screen = MainScreen(
            self._comics_database,
            self.reader_settings,
            reader_tree_events,
            filtered_title_lists,
            self._reader_screen_manager.screen_switchers,
            screens,
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

        logger.debug("Instantiating document reader screen...")
        document_reader_screen = get_document_reader_screen(
            DOCUMENT_READER_SCREEN,
            self.font_manager,
            self._screen_switchers.close_document_reader,
        )

        reader_screens = ReaderScreens(
            self._main_screen,
            comic_reader_screen,
            document_reader_screen,
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
            Window.bind(on_move=self._window_geometry.on_window_pos_change)
        Window.bind(on_resize=self._window_geometry.on_window_resize)

        # On Windows the DPI scaling artifacts in the SDL2 backend make the aspect-ratio
        # correction converge unreliably, causing erratic resize oscillations whenever the
        # user drags the window border.  Locking the window prevents that entirely while
        # still allowing programmatic resizes (monitor changes, comic open/close).
        if PLATFORM == Platform.WIN:
            Window.resizable = False

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

        self._window_geometry.start_rotation_polling()

        # All the behind the scenes sizing and moving is done.
        # Now make the main window visible.
        def show_the_window(*_args: Any) -> None:  # noqa: ANN401
            self._window_geometry.set_window_ready()
            Window.show()
            _log_screen_settings()

        Clock.schedule_once(show_the_window, WINDOW_SHOW_DELAY)


def _log_screen_settings() -> None:
    logger.info(f"Screen info: {SCREEN_METRICS.SCREEN_INFO[0]}.")
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
