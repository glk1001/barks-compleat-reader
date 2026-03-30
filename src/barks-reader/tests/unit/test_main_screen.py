# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import barks_reader.ui.main_screen
import pytest
from barks_reader.ui.main_screen import MainScreen
from barks_reader.ui.screen_bundle import ScreenBundle
from barks_reader.ui.view_states import ViewStates
from kivy.uix.screenmanager import Screen

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_dependencies() -> dict[str, Any]:
    screens = ScreenBundle(
        tree_view=MagicMock(),
        bottom_title_view=MagicMock(),
        fun_image_view=MagicMock(),
        main_index=MagicMock(),
        speech_index=MagicMock(),
        names_index=MagicMock(),
        locations_index=MagicMock(),
        statistics=MagicMock(),
        search=MagicMock(),
    )
    return {
        "comics_database": MagicMock(),
        "reader_settings": MagicMock(),
        "reader_tree_events": MagicMock(),
        "filtered_title_lists": MagicMock(),
        "screen_switchers": MagicMock(),
        "screens": screens,
        "font_manager": MagicMock(),
        "user_error_handler": MagicMock(),
    }


@pytest.fixture
def main_screen(
    mock_dependencies: dict[str, MagicMock],
) -> Generator[MainScreen]:
    # Patch Kivy Screen __init__ to avoid window creation
    with patch.object(Screen, "__init__", autospec=True) as mock_screen_init:

        def side_effect(self, **kwargs) -> None:  # noqa: ANN001, ANN003
            from kivy.uix.widget import Widget  # noqa: PLC0415

            # Initialize Widget base to set up children list, properties, etc.
            Widget.__init__(self, **kwargs)

            self.ids = {
                "main_layout": MagicMock(),
                "action_bar": MagicMock(),
                "fullscreen_button": MagicMock(),
                "collapse_button": MagicMock(),
                "quit_button": MagicMock(),
                "go_back_button": MagicMock(),
                "change_pics_button": MagicMock(),
                "menu_button": MagicMock(),
                "icon_hitbox": MagicMock(),
            }

        mock_screen_init.side_effect = side_effect

        # Patch other internal initializations
        with (
            patch.object(barks_reader.ui.main_screen, "WindowManager"),
            patch.object(barks_reader.ui.main_screen, "ImageSelector"),
            patch.object(barks_reader.ui.main_screen, "ReaderFilePathsResolver"),
            patch.object(barks_reader.ui.main_screen, "SettingsManager"),
            patch.object(barks_reader.ui.main_screen, "SpecialFantaOverrides"),
            patch.object(barks_reader.ui.main_screen, "UserErrorHandler"),
            patch.object(barks_reader.ui.main_screen, "ComicReaderManager"),
            patch.object(barks_reader.ui.main_screen, "BackgroundViews"),
            patch.object(barks_reader.ui.main_screen, "ViewStateManager"),
            patch.object(barks_reader.ui.main_screen, "TreeViewManager"),
            patch.object(barks_reader.ui.main_screen, "NavigationCoordinator"),
            patch.object(barks_reader.ui.main_screen, "MainScreenNavigation"),
            patch.object(barks_reader.ui.main_screen, "MainScreenWindowHelper"),
            patch.object(barks_reader.ui.main_screen, "AppInitializer"),
            patch.object(barks_reader.ui.main_screen, "Factory"),
            patch.object(barks_reader.ui.main_screen, "Screen"),
        ):
            screen = MainScreen(**mock_dependencies)

            yield screen


class TestMainScreen:
    def test_init(self, main_screen: MainScreen) -> None:
        assert main_screen._active is True
        assert main_screen._view_state_manager is not None

    def test_on_action_bar_go_back(self, main_screen: MainScreen) -> None:
        main_screen.on_action_bar_go_back()
        main_screen._tree_view_manager.go_back_to_previous_node.assert_called_once()

    def test_on_action_bar_collapse(self, main_screen: MainScreen) -> None:
        main_screen.on_action_bar_collapse()
        main_screen._tree_view_manager.deselect_and_close_open_nodes.assert_called_once()

    def test_on_action_bar_change_view_images(self, main_screen: MainScreen) -> None:
        main_screen._random_title_images.get_random_reader_app_icon_file.return_value = "icon.png"

        main_screen.on_action_bar_change_view_images()

        assert main_screen.app_icon_filepath == "icon.png"
        main_screen._view_state_manager.change_background_views.assert_called_once()

    def test_on_view_state_changed(self, main_screen: MainScreen) -> None:
        # Initial state -> disabled
        main_screen._on_view_state_changed(ViewStates.INITIAL)
        assert main_screen.ids.collapse_button.disabled is True

        # Other state -> enabled
        main_screen._on_view_state_changed(ViewStates.ON_TITLE_NODE)
        assert main_screen.ids.collapse_button.disabled is False

    def test_on_title_portal_image_pressed_no_title(self, main_screen: MainScreen) -> None:
        main_screen._nav_coord.current_fanta_info = None
        main_screen.on_title_portal_image_pressed()
        main_screen._nav_coord.read_comic.assert_not_called()

    def test_on_title_portal_image_pressed_delegates_to_coordinator(
        self, main_screen: MainScreen
    ) -> None:
        main_screen._nav_coord.current_fanta_info = MagicMock()
        main_screen._app_initializer.is_fanta_volumes_state_ok.return_value = (True, "")
        main_screen._nav_coord.read_comic.return_value = True

        main_screen.on_title_portal_image_pressed()

        main_screen._nav.save_focus_before_comic.assert_called_once()
        main_screen._nav_coord.read_comic.assert_called_once()

    def test_on_comic_closed_delegates_to_coordinator(self, main_screen: MainScreen) -> None:
        main_screen._active = False

        main_screen.on_comic_closed()

        assert main_screen._active is True
        main_screen._nav.restore_focus_after_comic.assert_called_once()
        main_screen._nav_coord.on_comic_closed.assert_called_once()

    def test_on_document_reader_closed_delegates_to_coordinator(
        self, main_screen: MainScreen
    ) -> None:
        main_screen._active = False

        main_screen.on_document_reader_closed()

        assert main_screen._active is True
        main_screen._nav_coord.on_document_closed.assert_called_once()
