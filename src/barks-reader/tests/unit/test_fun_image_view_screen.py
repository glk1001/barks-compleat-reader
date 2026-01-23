# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.random_title_images import FIT_MODE_CONTAIN, ImageInfo
from barks_reader.fun_image_view_screen import FunImageViewScreen

if TYPE_CHECKING:
    from collections.abc import Generator

    from kivy.uix.widget import Widget


class TestFunImageViewScreen:
    @pytest.fixture
    def screen_setup(self) -> Generator[tuple[FunImageViewScreen, Any, MagicMock], Any]:
        """Set up the FunImageViewScreen with mocked dependencies."""
        mock_settings = MagicMock()
        mock_settings.show_fun_view_title_info = True

        # Mock dependencies used in __init__
        with (
            patch("barks_reader.fun_image_view_screen.ReaderNavigation") as mock_nav_cls,
            patch("kivy.uix.boxlayout.BoxLayout.__init__", autospec=True) as mock_layout_init,
        ):
            mock_nav_instance = mock_nav_cls.return_value

            # Mock ids for view_options_clear_all_button_pressed
            mock_custom_options_box = MagicMock()
            mock_custom_options_box.children = []

            def side_effect(instance: Widget, **_kwargs) -> None:  # noqa: ANN003
                instance.ids = {"custom_options_box": mock_custom_options_box}
                # Initialize properties that might be set in kv
                instance.x = 0
                instance.y = 0
                instance.width = 100
                instance.height = 100

            mock_layout_init.side_effect = side_effect

            screen = FunImageViewScreen(mock_settings)

            yield screen, mock_nav_instance, mock_settings

    def test_initialization(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        """Test that the screen initializes with correct default values."""
        screen, _, _ = screen_setup
        assert screen.goto_title_button_active is True
        assert screen.is_visible is False
        assert screen.image_fit_mode == FIT_MODE_CONTAIN
        assert screen.fun_options_enabled is False
        # noinspection PyProtectedMember
        assert screen._current_history_index == -1
        # noinspection PyProtectedMember
        assert len(screen._image_history) == 0

    def test_set_load_image_func(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        mock_func = MagicMock()
        screen.set_load_image_func(mock_func)
        # noinspection PyProtectedMember
        assert screen._load_image == mock_func

    def test_set_last_loaded_image_info(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup

        image_info = ImageInfo(
            filename=Path("test.png"),
            from_title=Titles.DONALD_DUCK_FINDS_PIRATE_GOLD,
            fit_mode=FIT_MODE_CONTAIN,
        )

        screen.set_last_loaded_image_info(image_info)

        # noinspection PyProtectedMember
        assert len(screen._image_history) == 1
        # noinspection PyProtectedMember
        assert screen._image_history[0] == image_info
        # noinspection PyProtectedMember
        assert screen._current_history_index == 0
        assert screen.current_title_str != ""

    def test_navigation_previous_next(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup

        mock_load_func = MagicMock()
        screen.set_load_image_func(mock_load_func)

        # Add two images to history
        info1 = ImageInfo(Path("1.png"), Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, FIT_MODE_CONTAIN)
        info2 = ImageInfo(Path("2.png"), Titles.LAND_OF_THE_TOTEM_POLES, FIT_MODE_CONTAIN)

        screen.set_last_loaded_image_info(info1)
        screen.set_last_loaded_image_info(info2)

        # Current index should be 1 (pointing to info2)
        # noinspection PyProtectedMember
        assert screen._current_history_index == 1

        # Go back
        # noinspection PyProtectedMember
        screen._goto_previous_image()
        # noinspection PyProtectedMember
        assert screen._current_history_index == 0
        mock_load_func.assert_called_with(info1)

        # Go back again (should stay at 0)
        # noinspection PyProtectedMember
        screen._goto_previous_image()
        # noinspection PyProtectedMember
        assert screen._current_history_index == 0

        # Go forward
        # noinspection PyProtectedMember
        screen._goto_next_image()
        # noinspection PyProtectedMember
        assert screen._current_history_index == 1
        mock_load_func.assert_called_with(info2)

        # Go forward again (should stay at 1)
        # noinspection PyProtectedMember
        screen._goto_next_image()
        # noinspection PyProtectedMember
        assert screen._current_history_index == 1

    def test_on_touch_down_navigation(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, mock_nav, _ = screen_setup

        # Enable visibility so touch is processed
        screen.is_visible = True
        screen.fun_options_enabled = False

        # Mock touch
        touch = MagicMock()
        touch.x = 100
        touch.y = 100

        # Mock navigation checks
        mock_nav.is_in_left_margin.return_value = True
        mock_nav.is_in_right_margin.return_value = False

        # Mock internal methods to verify calls
        # noinspection PyProtectedMember
        with (
            patch.object(screen, "_goto_previous_image") as mock_prev,
            patch.object(screen, "_goto_next_image") as mock_next,
        ):
            # Test Left Click
            handled = screen.on_touch_down(touch)
            assert handled is True
            mock_prev.assert_called_once()
            mock_next.assert_not_called()

            # Reset
            mock_prev.reset_mock()
            mock_nav.is_in_left_margin.return_value = False
            mock_nav.is_in_right_margin.return_value = True

            # Test Right Click
            handled = screen.on_touch_down(touch)
            assert handled is True
            mock_prev.assert_not_called()
            mock_next.assert_called_once()

    def test_fun_options_button_pressed(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup

        assert screen.fun_options_enabled is False
        screen.fun_options_button_pressed()
        assert screen.fun_options_enabled is True
        screen.fun_options_button_pressed()
        assert screen.fun_options_enabled is False

    def test_on_goto_title(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup

        mock_callback = MagicMock()
        screen.on_goto_title_func = mock_callback

        screen.on_goto_title()
        mock_callback.assert_called_once()
