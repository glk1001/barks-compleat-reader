# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import barks_reader.ui.main_screen
import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.random_title_images import ImageInfo
from barks_reader.ui.main_screen import MainScreen
from barks_reader.ui.view_states import ViewStates
from kivy.uix.screenmanager import Screen

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_dependencies() -> dict[str, MagicMock]:
    return {
        "comics_database": MagicMock(),
        "reader_settings": MagicMock(),
        "reader_tree_events": MagicMock(),
        "filtered_title_lists": MagicMock(),
        "screen_switchers": MagicMock(),
        "tree_view_screen": MagicMock(),
        "bottom_title_view_screen": MagicMock(),
        "fun_image_view_screen": MagicMock(),
        "main_index_screen": MagicMock(),
        "speech_index_screen": MagicMock(),
        "statistics_screen": MagicMock(),
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

            self.ids = MagicMock()
            self.ids.main_layout = MagicMock()
            self.ids.action_bar = MagicMock()
            self.ids.fullscreen_button = MagicMock()
            self.ids.collapse_button = MagicMock()

        mock_screen_init.side_effect = side_effect

        # Patch other internal initializations
        with (
            patch.object(barks_reader.ui.main_screen, "WindowManager"),
            patch.object(barks_reader.ui.main_screen, "RandomTitleImages"),
            patch.object(barks_reader.ui.main_screen, "SettingsManager"),
            patch.object(barks_reader.ui.main_screen, "SpecialFantaOverrides"),
            patch.object(barks_reader.ui.main_screen, "UserErrorHandler"),
            patch.object(barks_reader.ui.main_screen, "ComicReaderManager"),
            patch.object(barks_reader.ui.main_screen, "BackgroundViews"),
            patch.object(barks_reader.ui.main_screen, "ViewStateManager"),
            patch.object(barks_reader.ui.main_screen, "TreeViewManager"),
            patch.object(barks_reader.ui.main_screen, "AppInitializer"),
            patch.object(barks_reader.ui.main_screen, "Factory"),
            patch.object(barks_reader.ui.main_screen, "Screen"),
        ):
            screen = MainScreen(**mock_dependencies)

            yield screen


class TestMainScreen:
    def test_init(self, main_screen: MainScreen) -> None:
        # noinspection PyProtectedMember
        assert main_screen._active is True
        # noinspection PyProtectedMember
        assert main_screen._view_state_manager is not None

    def test_on_action_bar_go_back(self, main_screen: MainScreen) -> None:
        # noinspection PyProtectedMember
        main_screen.on_action_bar_go_back()
        # noinspection PyProtectedMember
        main_screen._tree_view_manager.go_back_to_previous_node.assert_called_once()

    def test_on_action_bar_collapse(self, main_screen: MainScreen) -> None:
        main_screen.on_action_bar_collapse()
        # noinspection PyProtectedMember
        main_screen._tree_view_manager.deselect_and_close_open_nodes.assert_called_once()

    def test_on_action_bar_change_view_images(self, main_screen: MainScreen) -> None:
        # noinspection PyProtectedMember
        main_screen._random_title_images.get_random_reader_app_icon_file.return_value = "icon.png"

        main_screen.on_action_bar_change_view_images()

        assert main_screen.app_icon_filepath == "icon.png"
        # noinspection PyProtectedMember
        main_screen._view_state_manager.change_background_views.assert_called_once()

    def test_on_view_state_changed(self, main_screen: MainScreen) -> None:
        # Initial state -> disabled
        # noinspection PyProtectedMember
        main_screen._on_view_state_changed(ViewStates.INITIAL)
        assert main_screen.ids.collapse_button.disabled is True

        # Other state -> enabled
        # noinspection PyProtectedMember
        main_screen._on_view_state_changed(ViewStates.ON_TITLE_NODE)
        assert main_screen.ids.collapse_button.disabled is False

    def test_goto_chrono_title(self, main_screen: MainScreen) -> None:
        # Setup
        image_info = ImageInfo(filename=Path("img.png"), from_title=Titles.ADVENTURE_DOWN_UNDER)

        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "Title Str"
        mock_fanta_info.comic_book_info.submitted_year = 1942

        # Mock _get_fanta_info
        # noinspection PyProtectedMember,LongLine
        main_screen._get_fanta_info = MagicMock(return_value=mock_fanta_info)  # type: ignore[assignment]

        # Mock year range nodes
        mock_year_node = MagicMock()
        mock_year_node.nodes = []
        # noinspection PyProtectedMember
        main_screen._year_range_nodes = {(1942, 1946): mock_year_node}

        # Mock find_tree_view_title_node
        with patch.object(barks_reader.ui.main_screen, "find_tree_view_title_node") as mock_find:
            mock_title_node = MagicMock()
            mock_find.return_value = mock_title_node

            # noinspection PyProtectedMember
            main_screen._goto_chrono_title(image_info)

            # Verify interactions
            # noinspection PyProtectedMember
            main_screen._tree_view_manager.open_all_parent_nodes.assert_called_with(mock_year_node)
            # noinspection PyProtectedMember
            main_screen._tree_view_manager.goto_node.assert_called_with(
                mock_title_node, scroll_to=True
            )
            # noinspection PyProtectedMember
            main_screen._view_state_manager.set_view_state.assert_called_with(
                ViewStates.ON_TITLE_NODE, title_str="Title Str"
            )

    def test_goto_title_with_page_num_comic(self, main_screen: MainScreen) -> None:
        image_info = ImageInfo(filename=Path("img.png"), from_title=Titles.ADVENTURE_DOWN_UNDER)

        with patch.object(main_screen, "_goto_chrono_title") as mock_goto_chrono:
            # noinspection PyProtectedMember
            main_screen._goto_title_with_page_num(image_info, "5")

            mock_goto_chrono.assert_called_with(image_info)
            # noinspection PyProtectedMember, PyUnresolvedReferences
            main_screen._bottom_title_view_screen.set_goto_page_state.assert_called_with(
                "5", active=True
            )

    def test_read_barks_comic_book(self, main_screen: MainScreen) -> None:
        # Setup
        # noinspection PyProtectedMember
        main_screen._bottom_title_view_screen.goto_page_active = True
        # noinspection PyProtectedMember
        main_screen._bottom_title_view_screen.goto_page_num = "10"
        # noinspection PyProtectedMember
        main_screen._bottom_title_view_screen.use_overrides_active = False

        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "Title"
        main_screen.fanta_info = mock_fanta_info

        mock_comic = MagicMock()
        # noinspection PyProtectedMember
        main_screen._comics_database.get_comic_book.return_value = mock_comic

        # Execute
        # noinspection PyProtectedMember
        main_screen._read_barks_comic_book()

        # Verify
        # noinspection PyProtectedMember
        assert main_screen._active is False
        # noinspection PyProtectedMember
        main_screen._comic_reader_manager.read_barks_comic_book.assert_called_with(
            mock_fanta_info,
            mock_comic,
            "10",
            False,  # noqa: FBT003
        )

    def test_on_comic_closed(self, main_screen: MainScreen) -> None:
        # Setup
        # noinspection PyProtectedMember
        main_screen._read_comic_view_state = ViewStates.ON_INDEX_NODE
        main_screen.fanta_info = MagicMock()

        mock_last_page = MagicMock()
        mock_last_page.display_page_num = "5"
        # noinspection PyProtectedMember
        main_screen._comic_reader_manager.comic_closed.return_value = mock_last_page

        # Execute
        main_screen.on_comic_closed()

        # Verify
        # noinspection PyProtectedMember
        assert main_screen._active is True
        # noinspection PyProtectedMember
        assert main_screen._read_comic_view_state is None
        # noinspection PyProtectedMember
        main_screen._view_state_manager.update_view_for_node.assert_called_with(
            ViewStates.ON_INDEX_NODE
        )
        # noinspection PyProtectedMember, PyUnresolvedReferences
        main_screen._bottom_title_view_screen.set_goto_page_state.assert_called_with(
            "5", active=True
        )

    def test_set_next_title(self, main_screen: MainScreen) -> None:
        mock_info = MagicMock()
        mock_info.comic_book_info.get_title_str.return_value = "Title"

        # noinspection PyProtectedMember
        main_screen._set_next_title(mock_info, None)

        assert main_screen.fanta_info == mock_info
        # noinspection PyProtectedMember
        main_screen._view_state_manager.update_view_for_node_with_title.assert_called_with(
            ViewStates.ON_TITLE_NODE
        )
