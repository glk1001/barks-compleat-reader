"""Composition root for `MainScreen`'s collaborator graph.

`MainScreen.__init__` used to new up ~15 collaborators inline — a 120-line
composition root that made the constructor hard to read and forced tests to
patch every collaborator class. `build_main_screen_components` assembles that
graph in one place and returns it as a `MainScreenComponents` bundle, so the
constructor is thin assembly and a test can patch this single factory.

The builder is intimately coupled to the host `MainScreen` (it needs the widget
for `host_screen=`, its `ids`, and a handful of bound-method callbacks), so it
reads host internals directly; that coupling is the nature of a composition root
and is kept contained here rather than smeared across the constructor.
"""

# ruff: noqa: SLF001

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from barks_reader.core.comic_book_page_info import ComicLayoutBuilder
from barks_reader.core.image_selector import ImageSelector
from barks_reader.core.navigation import NavigationModel
from barks_reader.core.page_info_adapters import FantagraphicsPanelSegmentsAdapter
from barks_reader.core.reader_file_paths_resolver import ReaderFilePathsResolver
from barks_reader.core.special_overrides_handler import SpecialFantaOverrides
from barks_reader.core.view_pipeline import ViewPipeline

from .adapters import KivyClockScheduler, TintColorSource
from .app_initializer import AppInitializer
from .comic_reader_manager import ComicReaderManager
from .json_settings_manager import SettingsManager
from .last_read_page_tracker import LastReadPageTracker
from .main_screen_nav import MainScreenNavigation
from .main_screen_window import MainScreenWindowHelper
from .navigation_coordinator import NavigationCoordinator
from .snapshot_applicator import SnapshotApplicator
from .tree_view_manager import TreeViewManager
from .user_error_handler import UserErrorHandler
from .view_renderer import ViewRenderer

if TYPE_CHECKING:
    from .main_screen import MainScreen
    from .platform_window_utils import WindowManager


@dataclass(frozen=True, slots=True)
class MainScreenComponents:
    """The collaborator graph `MainScreen` delegates to after construction."""

    random_title_images: ImageSelector
    json_settings_manager: SettingsManager
    special_fanta_overrides: SpecialFantaOverrides
    comic_reader_manager: ComicReaderManager
    window_helper: MainScreenWindowHelper
    renderer: ViewRenderer
    nav_coord: NavigationCoordinator
    tree_view_manager: TreeViewManager
    app_initializer: AppInitializer
    nav: MainScreenNavigation


def build_main_screen_components(
    host: MainScreen, window_manager: WindowManager
) -> MainScreenComponents:
    """Assemble `MainScreen`'s collaborator graph around *host*.

    Reads the external dependencies and wired screens off *host* (already set by
    the constructor) and returns the constructed collaborators. *window_manager*
    is the single shared instance, also injected into the comic reader screen, so
    the saved window geometry lives in one place. Side-effect-free on *host*
    except for the deferred `nav_coord.set_tree_view_manager` wiring that breaks
    the coordinator/tree-manager cycle.
    """
    reader_settings = host._reader_settings
    comics_database = host._comics_database
    screens = host._screens
    screen_switchers = host._screen_switchers

    resolver = ReaderFilePathsResolver(reader_settings.file_paths)
    random_title_images = ImageSelector(resolver, reader_settings)

    json_settings_manager = SettingsManager(reader_settings.get_user_data_path())
    last_read_page_tracker = LastReadPageTracker(json_settings_manager)
    special_fanta_overrides = SpecialFantaOverrides(reader_settings)

    user_error_handler = UserErrorHandler(reader_settings, screen_switchers.switch_to_settings)

    panel_segments_adapter = FantagraphicsPanelSegmentsAdapter(
        comics_database,
        reader_settings.sys_file_paths.get_barks_reader_fantagraphics_panel_segments_root_dir(),
    )
    layout_builder = ComicLayoutBuilder(
        sorted_pages_port=panel_segments_adapter,
        required_dimensions_port=panel_segments_adapter,
    )

    comic_reader_manager = ComicReaderManager(
        comics_database,
        reader_settings,
        last_read_page_tracker,
        layout_builder,
        host._tree_view_screen,
        user_error_handler,
    )

    window_helper = MainScreenWindowHelper(
        host_screen=host,
        window_manager=window_manager,
        action_bar=host._action_bar,
        fullscreen_button=host._fullscreen_button,
        fullscreen_icon=str(reader_settings.sys_file_paths.get_barks_reader_fullscreen_icon_file()),
        fullscreen_exit_icon=str(
            reader_settings.sys_file_paths.get_barks_reader_fullscreen_exit_icon_file()
        ),
        main_layout=host.ids.main_layout,
        fun_image_view_screen=host._fun_image_view_screen,
        update_fonts=host.update_fonts,
    )

    pipeline = ViewPipeline(
        reader_settings=reader_settings,
        title_lists=host._title_lists,
        image_selector=random_title_images,
        scheduler=KivyClockScheduler(),
        colors=TintColorSource(),
    )
    applicator = SnapshotApplicator(screens)
    renderer = ViewRenderer(
        reader_settings=reader_settings,
        pipeline=pipeline,
        applicator=applicator,
        screens=screens,
        nav_model=NavigationModel(),
        on_view_state_changed=host._on_view_state_changed,
    )

    nav_coord = NavigationCoordinator(
        reader_settings=reader_settings,
        comics_database=comics_database,
        renderer=renderer,
        comic_reader_manager=comic_reader_manager,
        bottom_title_view_screen=host._bottom_title_view_screen,
        tree_view_screen=host._tree_view_screen,
        screen_switchers=screen_switchers,
        special_fanta_overrides=special_fanta_overrides,
        user_error_handler=user_error_handler,
        on_active_changed=host._is_active,
    )

    tree_view_manager = TreeViewManager(
        renderer,
        screens,
        nav_coord,
        sys_file_paths=reader_settings.sys_file_paths,
    )
    nav_coord.set_tree_view_manager(tree_view_manager)

    app_initializer = AppInitializer(
        reader_settings,
        user_error_handler,
        comic_reader_manager,
        json_settings_manager,
        renderer,
        tree_view_manager,
        host._tree_view_screen,
    )

    nav = MainScreenNavigation(
        screens=screens,
        tree_view_manager=tree_view_manager,
        bottom_base_view_screen=host._bottom_base_view_screen,
        on_title_activated=host.on_title_portal_image_pressed,
        enter_menu_mode=host._enter_menu_mode,
        handle_menu_key=host._handle_menu_key,
        is_in_menu_mode=lambda: host._menu_mode,
    )

    return MainScreenComponents(
        random_title_images=random_title_images,
        json_settings_manager=json_settings_manager,
        special_fanta_overrides=special_fanta_overrides,
        comic_reader_manager=comic_reader_manager,
        window_helper=window_helper,
        renderer=renderer,
        nav_coord=nav_coord,
        tree_view_manager=tree_view_manager,
        app_initializer=app_initializer,
        nav=nav,
    )
