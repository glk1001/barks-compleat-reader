# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.image_selector import ImageInfo
from barks_reader.ui.background_views import ImageThemes
from barks_reader.ui.screen_bundle import ScreenBundle
from barks_reader.ui.view_state_manager import (
    ImageThemesChange,
    ImageThemesToUse,
    ViewStateManager,
)
from barks_reader.ui.view_states import ViewStates


def _make_mock_screens() -> dict[str, MagicMock]:
    """Create mock screen widgets keyed by ScreenBundle field names."""
    return {
        "tree_view": MagicMock(),
        "bottom_title_view": MagicMock(),
        "fun_image_view": MagicMock(),
        "main_index": MagicMock(),
        "speech_index": MagicMock(),
        "names_index": MagicMock(),
        "locations_index": MagicMock(),
        "statistics": MagicMock(),
        "search": MagicMock(),
    }


@pytest.fixture
def mock_screen_mocks() -> dict[str, MagicMock]:
    return _make_mock_screens()


@pytest.fixture
def mock_screens(mock_screen_mocks: dict[str, MagicMock]) -> ScreenBundle:
    return ScreenBundle(**mock_screen_mocks)


@pytest.fixture
def mock_dependencies(mock_screens: ScreenBundle) -> dict[str, Any]:
    return {
        "reader_settings": MagicMock(),
        "background_views": MagicMock(),
        "screens": mock_screens,
        "applicator": MagicMock(),
        "on_view_state_changed_func": MagicMock(),
    }


@pytest.fixture
def view_state_manager(
    mock_dependencies: dict[str, Any],
) -> ViewStateManager:
    return ViewStateManager(**mock_dependencies)


class TestViewStateManager:
    @pytest.mark.usefixtures("view_state_manager")
    def test_init(self, mock_screen_mocks: dict[str, MagicMock]) -> None:
        # Check initial visibility
        assert mock_screen_mocks["bottom_title_view"].is_visible is False
        assert mock_screen_mocks["fun_image_view"].is_visible is False
        assert mock_screen_mocks["main_index"].is_visible is False
        assert mock_screen_mocks["speech_index"].is_visible is False
        assert mock_screen_mocks["names_index"].is_visible is False
        assert mock_screen_mocks["locations_index"].is_visible is False
        assert mock_screen_mocks["statistics"].is_visible is False
        assert mock_screen_mocks["search"].is_visible is False

        # Check callback registration
        mock_screen_mocks["fun_image_view"].set_load_image_func.assert_called_once()

    def test_bottom_view_fun_image_themes_changed(
        self, view_state_manager: ViewStateManager
    ) -> None:
        # ALL
        view_state_manager.bottom_view_fun_image_themes_changed(ImageThemesToUse.ALL)
        assert view_state_manager._bottom_view_fun_image_themes is None

        # CUSTOM
        view_state_manager.bottom_view_fun_image_themes_changed(ImageThemesToUse.CUSTOM)
        assert view_state_manager._bottom_view_fun_image_themes is not None
        assert (
            view_state_manager._bottom_view_fun_image_themes
            == view_state_manager._bottom_view_fun_custom_image_themes
        )

    def test_bottom_view_alter_fun_image_themes(self, view_state_manager: ViewStateManager) -> None:
        # ADD
        view_state_manager.bottom_view_alter_fun_image_themes(
            ImageThemes.FORTIES, ImageThemesChange.ADD
        )
        assert ImageThemes.FORTIES in view_state_manager._bottom_view_fun_custom_image_themes

        # DISCARD
        view_state_manager.bottom_view_alter_fun_image_themes(
            ImageThemes.FORTIES, ImageThemesChange.DISCARD
        )
        assert ImageThemes.FORTIES not in view_state_manager._bottom_view_fun_custom_image_themes

    def test_set_view_state(
        self, view_state_manager: ViewStateManager, mock_dependencies: dict[str, Any]
    ) -> None:
        view_state_manager.set_view_state(
            ViewStates.ON_INTRO_NODE, category="Cat", year_range="1940-1950", title_str="Title"
        )

        # Verify background views context updates
        bg_views = mock_dependencies["background_views"]
        bg_views.set_current_category.assert_called_with("Cat")
        bg_views.set_current_year_range.assert_called_with("1940-1950")
        bg_views.set_current_bottom_view_title.assert_called_with("Title")
        bg_views.set_view_state.assert_called_with(ViewStates.ON_INTRO_NODE)

        # Verify snapshot flow
        bg_views.compute_snapshot.assert_called_once()
        mock_dependencies["applicator"].apply.assert_called_once_with(
            bg_views.compute_snapshot.return_value
        )

        # Verify callback
        mock_dependencies["on_view_state_changed_func"].assert_called_with(ViewStates.ON_INTRO_NODE)

        # Verify title image reset
        bg_views.set_bottom_view_title_image_file.assert_called_with(None)

    def test_change_background_views(
        self, view_state_manager: ViewStateManager, mock_dependencies: dict[str, Any]
    ) -> None:
        bg_views = mock_dependencies["background_views"]
        bg_views.get_view_state.return_value = ViewStates.ON_TITLE_NODE
        bg_views.get_current_category.return_value = "Cat"

        with patch.object(view_state_manager, "set_view_state") as mock_set_state:
            view_state_manager.change_background_views()

            mock_set_state.assert_called_once()
            args, _kwargs = mock_set_state.call_args
            assert args[0] == ViewStates.ON_TITLE_NODE
            assert args[1] == "Cat"

    def test_set_title(
        self,
        view_state_manager: ViewStateManager,
        mock_dependencies: dict[str, Any],
        mock_screen_mocks: dict[str, MagicMock],
    ) -> None:
        fanta_info = MagicMock()
        fanta_info.comic_book_info.get_title_str.return_value = "Title"

        mock_dependencies[
            "reader_settings"
        ].file_paths.get_edited_version_if_possible.return_value = (Path("edited.png"), True)

        view_state_manager.set_title(fanta_info, Path("image.png"))

        mock_screen_mocks["bottom_title_view"].fade_in_bottom_view_title.assert_called_once()
        mock_dependencies["background_views"].set_current_bottom_view_title.assert_called_with(
            "Title"
        )
        mock_dependencies["background_views"].set_bottom_view_title_image_file.assert_called_with(
            Path("edited.png")
        )
        mock_dependencies["background_views"].set_next_bottom_view_title_image.assert_called_once()
        mock_screen_mocks["bottom_title_view"].set_title_view.assert_called_with(fanta_info)

    def test_load_new_fun_view_image(
        self,
        view_state_manager: ViewStateManager,
        mock_dependencies: dict[str, Any],
    ) -> None:
        image_info = ImageInfo(filename=Path("new_fun.png"), from_title=Titles.GIFT_LION)

        view_state_manager._load_new_fun_view_image(image_info)

        mock_dependencies["applicator"].load_new_fun_view_image.assert_called_with(image_info)
        mock_dependencies["background_views"].set_bottom_view_fun_image.assert_called_with(
            image_info
        )

    def test_get_top_view_image_info(
        self, view_state_manager: ViewStateManager, mock_dependencies: dict[str, Any]
    ) -> None:
        expected = ImageInfo(filename=Path("top.png"))
        mock_dependencies["applicator"].get_prev_top_view_image_info.return_value = expected

        result = view_state_manager.get_top_view_image_info()
        assert result == expected

    def test_get_bottom_view_fun_image_info(
        self, view_state_manager: ViewStateManager, mock_dependencies: dict[str, Any]
    ) -> None:
        expected = ImageInfo(filename=Path("fun.png"))
        mock_dependencies["applicator"].get_prev_fun_view_image_info.return_value = expected

        result = view_state_manager.get_bottom_view_fun_image_info()
        assert result == expected
