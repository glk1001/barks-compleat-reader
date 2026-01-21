# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.background_views import ImageThemes
from barks_reader.random_title_images import FIT_MODE_COVER, ImageInfo
from barks_reader.view_state_manager import (
    ImageThemesChange,
    ImageThemesToUse,
    ViewStateManager,
)
from barks_reader.view_states import ViewStates

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_dependencies() -> dict[str, MagicMock]:
    return {
        "reader_settings": MagicMock(),
        "background_views": MagicMock(),
        "tree_view_screen": MagicMock(),
        "bottom_title_view_screen": MagicMock(),
        "fun_image_view_screen": MagicMock(),
        "main_index_screen": MagicMock(),
        "speech_index_screen": MagicMock(),
        "on_view_state_changed_func": MagicMock(),
    }


@pytest.fixture
def view_state_manager(
    mock_dependencies: dict[str, MagicMock],
) -> Generator[ViewStateManager]:
    # Patch PanelImageLoader to avoid actual image loading logic
    with patch("barks_reader.view_state_manager.PanelImageLoader") as mock_loader_cls:
        # Configure mock loader instance
        mock_loader = mock_loader_cls.return_value

        # Mock load_texture to immediately call the callback with a mock texture
        # noinspection PyUnusedLocal
        def side_effect(filename, callback):  # noqa: ANN001, ANN202, ARG001
            callback(MagicMock(), None)

        mock_loader.load_texture.side_effect = side_effect

        manager = ViewStateManager(**mock_dependencies)
        yield manager


class TestViewStateManager:
    @pytest.mark.usefixtures("view_state_manager")
    def test_init(self, mock_dependencies: dict[str, MagicMock]) -> None:
        # Check initial visibility
        assert mock_dependencies["bottom_title_view_screen"].is_visible is False
        assert mock_dependencies["fun_image_view_screen"].is_visible is False
        assert mock_dependencies["main_index_screen"].is_visible is False
        assert mock_dependencies["speech_index_screen"].is_visible is False

        # Check callback registration
        mock_dependencies["fun_image_view_screen"].set_load_image_func.assert_called_once()

    def test_bottom_view_fun_image_themes_changed(
        self, view_state_manager: ViewStateManager
    ) -> None:
        # ALL
        view_state_manager.bottom_view_fun_image_themes_changed(ImageThemesToUse.ALL)
        # noinspection PyProtectedMember
        assert view_state_manager._bottom_view_fun_image_themes is None

        # CUSTOM
        view_state_manager.bottom_view_fun_image_themes_changed(ImageThemesToUse.CUSTOM)
        # noinspection PyProtectedMember
        assert view_state_manager._bottom_view_fun_image_themes is not None
        # noinspection PyProtectedMember
        assert (
            view_state_manager._bottom_view_fun_image_themes
            == view_state_manager._bottom_view_fun_custom_image_themes
        )

    def test_bottom_view_alter_fun_image_themes(self, view_state_manager: ViewStateManager) -> None:
        # ADD
        view_state_manager.bottom_view_alter_fun_image_themes(
            ImageThemes.FORTIES, ImageThemesChange.ADD
        )
        # noinspection PyProtectedMember
        assert ImageThemes.FORTIES in view_state_manager._bottom_view_fun_custom_image_themes

        # DISCARD
        view_state_manager.bottom_view_alter_fun_image_themes(
            ImageThemes.FORTIES, ImageThemesChange.DISCARD
        )
        # noinspection PyProtectedMember
        assert ImageThemes.FORTIES not in view_state_manager._bottom_view_fun_custom_image_themes

    def test_set_view_state(
        self, view_state_manager: ViewStateManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        # Mock _set_views to verify it's called
        with patch.object(view_state_manager, "_set_views") as mock_set_views:
            view_state_manager.set_view_state(
                ViewStates.ON_INTRO_NODE, category="Cat", year_range="1940-1950", title_str="Title"
            )

            # Verify background views updates
            bg_views = mock_dependencies["background_views"]
            bg_views.set_current_category.assert_called_with("Cat")
            bg_views.set_current_year_range.assert_called_with("1940-1950")
            bg_views.set_current_bottom_view_title.assert_called_with("Title")
            bg_views.set_view_state.assert_called_with(ViewStates.ON_INTRO_NODE)

            mock_set_views.assert_called_once()
            mock_dependencies["on_view_state_changed_func"].assert_called_with(
                ViewStates.ON_INTRO_NODE
            )

    def test_change_background_views(
        self, view_state_manager: ViewStateManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        bg_views = mock_dependencies["background_views"]
        # Setup return values for getters
        bg_views.get_view_state.return_value = ViewStates.ON_TITLE_NODE
        bg_views.get_current_category.return_value = "Cat"

        # Mock set_view_state to verify call
        with patch.object(view_state_manager, "set_view_state") as mock_set_state:
            view_state_manager.change_background_views()

            mock_set_state.assert_called_once()
            args, _kwargs = mock_set_state.call_args
            assert args[0] == ViewStates.ON_TITLE_NODE
            assert args[1] == "Cat"

    def test_set_title(
        self, view_state_manager: ViewStateManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        fanta_info = MagicMock()
        fanta_info.comic_book_info.get_title_str.return_value = "Title"

        mock_dependencies[
            "reader_settings"
        ].file_paths.get_edited_version_if_possible.return_value = (Path("edited.png"), True)

        view_state_manager.set_title(fanta_info, Path("image.png"))

        mock_dependencies["bottom_title_view_screen"].fade_in_bottom_view_title.assert_called_once()
        mock_dependencies["background_views"].set_current_bottom_view_title.assert_called_with(
            "Title"
        )
        mock_dependencies["background_views"].set_bottom_view_title_image_file.assert_called_with(
            Path("edited.png")
        )
        mock_dependencies["background_views"].set_next_bottom_view_title_image.assert_called_once()
        mock_dependencies["bottom_title_view_screen"].set_title_view.assert_called_with(fanta_info)

    def test_set_views_top_view(
        self, view_state_manager: ViewStateManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        # Setup background views return values
        bg_views = mock_dependencies["background_views"]
        image_info = ImageInfo(
            filename=Path("top.png"), from_title=Titles.ATTIC_ANTICS, fit_mode=FIT_MODE_COVER
        )
        bg_views.get_top_view_image_info.return_value = image_info
        bg_views.get_top_view_image_opacity.return_value = 0.5
        bg_views.get_top_view_image_color.return_value = (1, 1, 1, 1)
        bg_views.get_bottom_view_fun_image_opacity.return_value = 0.0
        bg_views.get_bottom_view_title_opacity.return_value = 0.0
        bg_views.get_main_index_view_opacity.return_value = 0.0
        bg_views.get_speech_index_view_opacity.return_value = 0.0

        # Call _set_views (private, but tested via public methods or directly if needed)
        # noinspection PyProtectedMember
        view_state_manager._set_views()

        # Verify top view updates
        tree_screen = mock_dependencies["tree_view_screen"]
        assert tree_screen.top_view_image_opacity == 0.5  # noqa: PLR2004
        assert tree_screen.top_view_image_fit_mode == FIT_MODE_COVER
        assert tree_screen.top_view_image_color == (1, 1, 1, 1)
        # Texture should be set because loader mock calls callback immediately
        assert tree_screen.top_view_image_texture is not None
        tree_screen.set_title.assert_called_with(image_info.from_title)

    def test_set_views_fun_view(
        self, view_state_manager: ViewStateManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        bg_views = mock_dependencies["background_views"]
        image_info = ImageInfo(
            filename=Path("fun.png"), from_title=Titles.ATTIC_ANTICS, fit_mode=FIT_MODE_COVER
        )
        bg_views.get_bottom_view_fun_image_info.return_value = image_info
        bg_views.get_bottom_view_fun_image_opacity.return_value = 1.0
        bg_views.get_bottom_view_fun_image_color.return_value = (0, 1, 0, 1)
        bg_views.get_bottom_view_title_opacity.return_value = 0.0
        bg_views.get_main_index_view_opacity.return_value = 0.0
        bg_views.get_speech_index_view_opacity.return_value = 0.0

        # noinspection PyProtectedMember
        view_state_manager._set_views()

        fun_screen = mock_dependencies["fun_image_view_screen"]
        assert fun_screen.is_visible is True
        assert fun_screen.image_fit_mode == FIT_MODE_COVER
        assert fun_screen.image_color == (0, 1, 0, 1)
        assert fun_screen.image_texture is not None
        fun_screen.set_last_loaded_image_info.assert_called_with(image_info)

    def test_set_views_bottom_view(
        self, view_state_manager: ViewStateManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        bg_views = mock_dependencies["background_views"]
        image_info = ImageInfo(
            filename=Path("bottom.png"), from_title=Titles.GOOD_NEIGHBORS, fit_mode=FIT_MODE_COVER
        )
        bg_views.get_bottom_view_title_image_info.return_value = image_info
        bg_views.get_bottom_view_title_opacity.return_value = 1.0
        bg_views.get_bottom_view_fun_image_opacity.return_value = 0.0
        bg_views.get_main_index_view_opacity.return_value = 0.0
        bg_views.get_speech_index_view_opacity.return_value = 0.0
        bg_views.get_bottom_view_title_image_color.return_value = (0, 0, 1, 1)

        # noinspection PyProtectedMember
        view_state_manager._set_views()

        bottom_screen = mock_dependencies["bottom_title_view_screen"]
        assert bottom_screen.is_visible is True
        assert bottom_screen.title_image_fit_mode == FIT_MODE_COVER
        assert bottom_screen.title_image_color == (0, 0, 1, 1)
        assert bottom_screen.title_image_texture is not None

    def test_set_views_index_view(
        self, view_state_manager: ViewStateManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        bg_views = mock_dependencies["background_views"]
        bg_views.get_main_index_view_opacity.return_value = 1.0
        bg_views.get_speech_index_view_opacity.return_value = 0.0
        bg_views.get_bottom_view_fun_image_opacity.return_value = 0.0
        bg_views.get_bottom_view_title_opacity.return_value = 0.0

        # noinspection PyProtectedMember
        view_state_manager._set_views()

        assert mock_dependencies["main_index_screen"].is_visible is True
        assert mock_dependencies["speech_index_screen"].is_visible is False

    def test_load_new_fun_view_image(
        self, view_state_manager: ViewStateManager, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        image_info = ImageInfo(filename=Path("new_fun.png"), from_title=Titles.GIFT_LION)

        # noinspection PyProtectedMember
        view_state_manager._load_new_fun_view_image(image_info)

        fun_screen = mock_dependencies["fun_image_view_screen"]
        assert fun_screen.image_texture is not None

        # noinspection PyProtectedMember
        assert view_state_manager._bottom_view_fun_image_info == image_info
        mock_dependencies["background_views"].set_bottom_view_fun_image.assert_called_with(
            image_info
        )
