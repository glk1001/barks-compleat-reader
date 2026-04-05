# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import barks_reader.ui.navigation_coordinator
import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.image_selector import ImageInfo
from barks_reader.ui.navigation_coordinator import NavigationCoordinator, TitleTarget
from barks_reader.ui.view_states import ViewStates


@pytest.fixture
def mock_deps() -> dict[str, MagicMock]:
    return {
        "reader_settings": MagicMock(),
        "comics_database": MagicMock(),
        "view_state_manager": MagicMock(),
        "comic_reader_manager": MagicMock(),
        "bottom_title_view_screen": MagicMock(),
        "tree_view_screen": MagicMock(),
        "screen_switchers": MagicMock(),
        "special_fanta_overrides": MagicMock(),
        "user_error_handler": MagicMock(),
        "on_active_changed": MagicMock(),
    }


@pytest.fixture
def nav_coord(mock_deps: dict[str, MagicMock]) -> NavigationCoordinator:
    coord = NavigationCoordinator(**mock_deps)
    coord.set_tree_view_manager(MagicMock())
    return coord


class TestNavigationCoordinator:
    def test_select_title_sets_current_fanta_info(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "Title"

        target = TitleTarget(fanta_info=mock_fanta_info)
        nav_coord.select_title(target)

        assert nav_coord.current_fanta_info == mock_fanta_info
        mock_deps["view_state_manager"].update_view_for_node_with_title.assert_called_with(
            ViewStates.ON_TITLE_NODE, preserve_top_view=False
        )

    def test_navigate_to_chrono_title(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        image_info = ImageInfo(filename=Path("img.png"), from_title=Titles.ADVENTURE_DOWN_UNDER)

        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "Title Str"
        mock_fanta_info.comic_book_info.submitted_year = 1942

        mock_year_node = MagicMock()
        mock_year_node.nodes = []
        nav_coord.set_year_range_nodes({(1942, 1946): mock_year_node})

        with (
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "get_fanta_info",
                return_value=mock_fanta_info,
            ),
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "find_tree_view_title_node",
                return_value=MagicMock(),
            ),
        ):
            nav_coord.navigate_to_chrono_title(image_info)

            assert nav_coord.current_fanta_info == mock_fanta_info
            mock_deps["view_state_manager"].set_view_state.assert_called_with(
                ViewStates.ON_TITLE_NODE, title_str="Title Str"
            )

    def test_navigate_to_chrono_title_preserves_back_node(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        image_info = ImageInfo(filename=Path("img.png"), from_title=Titles.ADVENTURE_DOWN_UNDER)

        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "Title Str"
        mock_fanta_info.comic_book_info.submitted_year = 1942

        mock_year_node = MagicMock()
        mock_year_node.nodes = []
        nav_coord.set_year_range_nodes({(1942, 1946): mock_year_node})

        mock_search_node = MagicMock()
        mock_deps["tree_view_screen"].get_selected_node.return_value = mock_search_node

        with (
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "get_fanta_info",
                return_value=mock_fanta_info,
            ),
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "find_tree_view_title_node",
                return_value=MagicMock(),
            ),
        ):
            nav_coord.navigate_to_chrono_title(image_info)

            mock_deps[
                "tree_view_screen"
            ].ids.reader_tree_view.set_back_node.assert_called_once_with(mock_search_node)

    def test_read_comic_calls_comic_reader(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "Title"
        nav_coord._current_fanta_info = mock_fanta_info

        mock_deps["bottom_title_view_screen"].goto_page_active = True
        mock_deps["bottom_title_view_screen"].goto_page_num = "10"
        mock_deps["bottom_title_view_screen"].use_overrides_active = False
        mock_comic = MagicMock()
        mock_deps["comics_database"].get_comic_book.return_value = mock_comic

        result = nav_coord.read_comic()

        assert result is True
        mock_deps["on_active_changed"].assert_called_once()
        mock_deps["comic_reader_manager"].read_barks_comic_book.assert_called_once()

    def test_on_comic_closed_restores_view_state(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        nav_coord._read_comic_view_state = ViewStates.ON_INDEX_NODE
        mock_fanta_info = MagicMock()
        nav_coord._current_fanta_info = mock_fanta_info

        mock_last_page = MagicMock()
        mock_last_page.display_page_num = "5"
        mock_deps["comic_reader_manager"].comic_closed.return_value = mock_last_page

        nav_coord.on_comic_closed()

        mock_deps["view_state_manager"].update_view_for_node.assert_called_with(
            ViewStates.ON_INDEX_NODE
        )
        assert nav_coord._read_comic_view_state is None

    def test_on_document_closed_restores_view_state(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        nav_coord._doc_reader_close_view_state = ViewStates.ON_INTRO_NODE

        nav_coord.on_document_closed()

        mock_deps["view_state_manager"].update_view_for_node.assert_called_with(
            ViewStates.ON_INTRO_NODE
        )
        assert nav_coord._doc_reader_close_view_state is None
