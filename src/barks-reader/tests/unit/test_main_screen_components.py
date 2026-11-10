# ruff: noqa: SLF001
"""`build_main_screen_components`: what the main screen's collaborators are handed.

Every `MainScreen` test injects a ready-made bundle in the builder's place, so this
is the one place the wiring itself is run. The collaborator classes are stood in:
what is checked is who is given what, not what each then does with it.
"""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass, fields
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui import main_screen_components as components_module
from barks_reader.ui.main_screen_components import (
    MainScreenComponents,
    build_main_screen_components,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from barks_reader.ui.screen_bundle import ScreenBundle

_STOOD_IN_CLASSES = (
    "AppInitializer",
    "ComicLayoutBuilder",
    "ComicReaderManager",
    "FantagraphicsPanelSegmentsAdapter",
    "ImageSelector",
    "KivyClockScheduler",
    "LastReadPageTracker",
    "MainScreenNavigation",
    "MainScreenWindowHelper",
    "NavigationCoordinator",
    "NavigationModel",
    "ReaderFilePathsResolver",
    "ReadingHistoryStore",
    "ReadingHistoryTracker",
    "SettingsManager",
    "SnapshotApplicator",
    "SpecialFantaOverrides",
    "TreeViewManager",
    "ViewPipeline",
    "ViewRenderer",
)


@dataclass(frozen=True)
class _Built:
    components: MainScreenComponents
    classes: dict[str, MagicMock]
    host: MagicMock
    window_manager: MagicMock


@pytest.fixture
def built(screens: ScreenBundle) -> Generator[_Built]:
    host = MagicMock()
    host._screens = screens
    window_manager = MagicMock()

    with ExitStack() as stack:
        classes = {
            name: stack.enter_context(patch.object(components_module, name))
            for name in _STOOD_IN_CLASSES
        }
        components = build_main_screen_components(host, window_manager)
        yield _Built(components, classes, host, window_manager)


def test_the_bundle_holds_each_collaborator_that_was_built(built: _Built) -> None:
    made_by = {
        "random_title_images": "ImageSelector",
        "json_settings_manager": "SettingsManager",
        "special_fanta_overrides": "SpecialFantaOverrides",
        "comic_reader_manager": "ComicReaderManager",
        "window_helper": "MainScreenWindowHelper",
        "renderer": "ViewRenderer",
        "nav_coord": "NavigationCoordinator",
        "tree_view_manager": "TreeViewManager",
        "app_initializer": "AppInitializer",
        "nav": "MainScreenNavigation",
    }
    assert set(made_by) == {field.name for field in fields(MainScreenComponents)}

    for field_name, class_name in made_by.items():
        assert getattr(built.components, field_name) is built.classes[class_name].return_value


def test_everyone_shares_the_hosts_one_error_handler(built: _Built) -> None:
    handler = built.host._user_error_handler

    assert handler in built.classes["ComicReaderManager"].call_args.args
    assert built.classes["NavigationCoordinator"].call_args.kwargs["user_error_handler"] is handler
    assert handler in built.classes["AppInitializer"].call_args.args


def test_the_window_helper_gets_the_shared_window_manager(built: _Built) -> None:
    helper_kwargs = built.classes["MainScreenWindowHelper"].call_args.kwargs

    assert helper_kwargs["window_manager"] is built.window_manager
    assert helper_kwargs["host_screen"] is built.host


def test_the_history_screen_is_given_the_store_the_tracker_writes(built: _Built) -> None:
    store_class = built.classes["ReadingHistoryStore"]
    store = store_class.return_value

    store_class.assert_called_once_with(built.host._reader_settings.get_user_history_path())
    built.host._screens.history.set_history_store.assert_called_once_with(store)
    assert built.classes["ReadingHistoryTracker"].call_args.args == (store,)


def test_history_is_recorded_only_while_the_setting_says_so(built: _Built) -> None:
    is_enabled = built.classes["ReadingHistoryTracker"].call_args.kwargs["is_enabled"]
    settings = built.host._reader_settings

    settings.record_reading_history = True
    assert is_enabled() is True
    settings.record_reading_history = False
    assert is_enabled() is False


def test_the_coordinator_and_the_tree_manager_are_given_each_other(built: _Built) -> None:
    coordinator = built.classes["NavigationCoordinator"].return_value
    tree_manager = built.classes["TreeViewManager"].return_value

    assert coordinator in built.classes["TreeViewManager"].call_args.args
    coordinator.set_tree_view_manager.assert_called_once_with(tree_manager)


def test_the_views_pick_their_images_from_the_one_selector(built: _Built) -> None:
    pipeline_kwargs = built.classes["ViewPipeline"].call_args.kwargs

    assert pipeline_kwargs["image_selector"] is built.components.random_title_images
    built.classes["ImageSelector"].assert_called_once()


def test_the_renderer_is_built_over_the_pipeline_and_the_hosts_screens(built: _Built) -> None:
    renderer_kwargs = built.classes["ViewRenderer"].call_args.kwargs

    assert renderer_kwargs["pipeline"] is built.classes["ViewPipeline"].return_value
    assert renderer_kwargs["applicator"] is built.classes["SnapshotApplicator"].return_value
    assert renderer_kwargs["screens"] is built.host._screens
    assert renderer_kwargs["on_view_state_changed"] is built.host._on_view_state_changed


def test_the_key_navigation_reads_menu_mode_as_it_is_now(built: _Built) -> None:
    nav_kwargs = built.classes["MainScreenNavigation"].call_args.kwargs

    built.host._menu_mode = False
    assert nav_kwargs["is_in_menu_mode"]() is False
    built.host._menu_mode = True
    assert nav_kwargs["is_in_menu_mode"]() is True
    assert nav_kwargs["tree_view_manager"] is built.classes["TreeViewManager"].return_value
