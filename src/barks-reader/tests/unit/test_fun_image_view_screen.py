# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import barks_reader.ui.fun_image_view_screen
import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.image_selector import FIT_MODE_CONTAIN, ImageInfo
from barks_reader.ui.fun_image_view_screen import FunImageViewScreen, _FunFocus
from barks_reader.ui.reader_keyboard_nav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_SPACE,
    KEY_UP,
)
from kivy.uix.boxlayout import BoxLayout

if TYPE_CHECKING:
    from collections.abc import Generator

    from kivy.uix.widget import Widget


@pytest.fixture
def _no_focus_draw() -> Generator[None]:
    """Neutralize the focus-ring helpers so nav tests assert state, not canvas draws."""
    mod = barks_reader.ui.fun_image_view_screen
    with (
        patch.object(mod, "draw_focus_highlight"),
        patch.object(mod, "clear_focus_highlight"),
        patch.object(mod, "update_focus_in_list"),
        patch.object(mod, "clear_focus_in_list"),
    ):
        yield


class TestFunImageViewScreen:
    @pytest.fixture
    def screen_setup(self) -> Generator[tuple[FunImageViewScreen, Any, MagicMock], Any]:
        """Set up the FunImageViewScreen with mocked dependencies."""
        mock_settings = MagicMock()
        mock_settings.show_fun_view_title_info = True

        # Mock dependencies used in __init__
        with (
            patch.object(barks_reader.ui.fun_image_view_screen, "ReaderNavigation") as mock_nav_cls,
            patch.object(BoxLayout, "__init__", autospec=True) as mock_layout_init,
        ):
            mock_nav_instance = mock_nav_cls.return_value

            # Mock ids for view_options_clear_all_button_pressed
            mock_custom_options_box = MagicMock()
            mock_custom_options_box.children = []

            def side_effect(instance: Widget, **_kwargs) -> None:  # noqa: ANN003
                mock_goto_button = MagicMock()
                mock_goto_button.collide_point.return_value = False
                mock_goto_title_overlay = MagicMock()
                mock_goto_title_overlay.goto_button = mock_goto_button
                mock_all_checkbox = MagicMock()
                mock_all_checkbox.active = True
                mock_custom_checkbox = MagicMock()
                mock_custom_checkbox.active = False
                instance.ids = {
                    "custom_options_box": mock_custom_options_box,
                    "goto_title_overlay": mock_goto_title_overlay,
                    "fun_options_button": MagicMock(),
                    "clear_all_button": MagicMock(),
                    "checkbox_all_image_types": mock_all_checkbox,
                    "checkbox_custom_image_types": mock_custom_checkbox,
                }
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
        assert screen._current_history_index == -1
        assert len(screen._image_history) == 0

    def test_set_load_image_func(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        mock_func = MagicMock()
        screen.set_load_image_func(mock_func)
        assert screen._load_image is not None
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

        assert len(screen._image_history) == 1
        assert screen._image_history[0] == image_info
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
        assert screen._current_history_index == 1

        # Go back
        screen._goto_previous_image()
        assert screen._current_history_index == 0
        mock_load_func.assert_called_with(info1)

        # Go back again (should stay at 0)
        screen._goto_previous_image()
        assert screen._current_history_index == 0

        # Go forward
        screen._goto_next_image()
        assert screen._current_history_index == 1
        mock_load_func.assert_called_with(info2)

        # Go forward again (should stay at 1)
        screen._goto_next_image()
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

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_enter_nav_focus_defaults_to_arrow(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.goto_title_button_active = True
        screen.fun_options_enabled = False

        screen.enter_nav_focus(MagicMock())

        assert screen.is_nav_active
        assert screen._nav_focus is _FunFocus.ARROW

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_enter_nav_focus_filter_when_arrow_inactive(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.goto_title_button_active = False
        screen.fun_options_enabled = False

        screen.enter_nav_focus(MagicMock())

        assert screen._nav_focus is _FunFocus.FILTER

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_up_moves_to_filter_down_back_to_arrow(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.goto_title_button_active = True
        screen.fun_options_enabled = False
        screen.enter_nav_focus(MagicMock())

        assert screen.handle_key(KEY_UP) is True
        assert screen._nav_focus is _FunFocus.FILTER

        assert screen.handle_key(KEY_DOWN) is True
        assert screen._nav_focus is _FunFocus.ARROW

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_enter_on_arrow_calls_goto(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        goto = MagicMock()
        screen.on_goto_title_func = goto
        screen.goto_title_button_active = True
        screen.fun_options_enabled = False
        screen.enter_nav_focus(MagicMock())

        assert screen.handle_key(KEY_ENTER) is True
        goto.assert_called_once()

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_enter_on_filter_opens_menu(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.goto_title_button_active = False  # focus starts on the filter button
        screen.fun_options_enabled = False
        screen.enter_nav_focus(MagicMock())
        assert screen._nav_focus is _FunFocus.FILTER

        assert screen.handle_key(KEY_ENTER) is True
        assert screen.fun_options_enabled is True
        assert screen._nav_focus is _FunFocus.MENU

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_escape_on_buttons_exits_to_caller(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        exit_cb = MagicMock()
        screen.goto_title_button_active = True
        screen.fun_options_enabled = False
        screen.enter_nav_focus(exit_cb)

        assert screen.handle_key(KEY_ESCAPE) is True
        exit_cb.assert_called_once()
        assert not screen.is_nav_active

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_menu_opens_focused_on_all_radio(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.ids["checkbox_custom_image_types"].active = False  # menu = [x, All, Custom]
        screen.fun_options_enabled = True
        screen.enter_nav_focus(MagicMock())

        assert screen._nav_focus is _FunFocus.MENU
        # Index 0 is the close (x) button; focus lands on the All radio (index 1).
        assert screen._menu_idx == 1

        all_idx = screen._menu_idx
        assert screen.handle_key(KEY_DOWN) is True  # -> Custom
        assert screen._menu_idx == all_idx + 1

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_up_from_all_reaches_close_button(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.ids["checkbox_custom_image_types"].active = False
        screen.fun_options_enabled = True
        screen.enter_nav_focus(MagicMock())  # idx 1 (All)

        assert screen.handle_key(KEY_UP) is True  # -> close (x) button, index 0
        assert screen._menu_idx == 0

        assert screen.handle_key(KEY_ENTER) is True  # x closes the menu
        assert screen.fun_options_enabled is False
        assert screen._nav_focus is _FunFocus.FILTER

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_selecting_custom_then_down_reaches_clear_all(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.ids["checkbox_custom_image_types"].active = False
        screen.ids["custom_options_box"].children = []
        screen.fun_options_enabled = True
        screen.enter_nav_focus(MagicMock())  # idx 1 (All)

        screen.handle_key(KEY_DOWN)  # -> Custom (index 2)
        screen.handle_key(KEY_ENTER)  # select Custom: menu grows with Clear-All
        assert screen.ids["checkbox_custom_image_types"].active is True

        with patch.object(screen, "view_options_clear_all_button_pressed") as mock_clear:
            assert screen.handle_key(KEY_DOWN) is True  # -> Clear-All (index 3)
            assert screen.handle_key(KEY_ENTER) is True

        mock_clear.assert_called_once()

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_menu_space_toggles_theme_row(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        row = MagicMock()
        row.active = False
        screen.ids["custom_options_box"].children = [row]
        screen.ids["checkbox_custom_image_types"].active = True  # menu grows with rows
        screen.fun_options_enabled = True
        # Menu = [x, All, Custom, Clear-All, row]; opens on All (index 1).
        screen.enter_nav_focus(MagicMock())

        screen.handle_key(KEY_DOWN)  # Custom (idx 2)
        screen.handle_key(KEY_DOWN)  # Clear-All (idx 3)
        screen.handle_key(KEY_DOWN)  # theme row (idx 4)
        assert screen.handle_key(KEY_SPACE) is True

        assert row.active is True

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_menu_escape_closes_menu(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.fun_options_enabled = True
        screen.enter_nav_focus(MagicMock())
        assert screen._nav_focus is _FunFocus.MENU

        assert screen.handle_key(KEY_ESCAPE) is True
        assert screen.fun_options_enabled is False
        assert screen._nav_focus is _FunFocus.FILTER

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_exit_nav_focus_deactivates(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.enter_nav_focus(MagicMock())
        assert screen.is_nav_active

        screen.exit_nav_focus()
        assert not screen.is_nav_active
