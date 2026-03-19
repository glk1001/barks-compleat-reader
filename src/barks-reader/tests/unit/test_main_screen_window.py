# ruff: noqa: SLF001, PLR2004

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui import main_screen_window as window_module
from barks_reader.ui.main_screen_window import MainScreenWindowHelper

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def helper() -> Generator[MainScreenWindowHelper, Any]:
    with (
        patch.object(window_module, "WindowManager") as mock_wm_cls,
    ):
        mock_wm_instance = MagicMock()
        mock_wm_cls.return_value = mock_wm_instance

        h = MainScreenWindowHelper(
            host_screen=MagicMock(),
            comic_reader_manager=MagicMock(),
            action_bar=MagicMock(),
            fullscreen_button=MagicMock(),
            fullscreen_icon="fullscreen.png",
            fullscreen_exit_icon="exit_fullscreen.png",
            main_layout=MagicMock(),
            fun_image_view_screen=MagicMock(),
            update_fonts=MagicMock(),
        )
        # Store for assertions
        h._mock_wm_cls = mock_wm_cls  # type: ignore[attr-defined]
        yield h


class TestToggleScreenMode:
    def test_fullscreen_to_windowed(self, helper: MainScreenWindowHelper) -> None:
        with patch.object(window_module, "Clock") as mock_clock:
            helper._mock_wm_cls.is_fullscreen_now.return_value = True

            helper.toggle_screen_mode()

            mock_clock.schedule_once.assert_called_once()

    def test_windowed_to_fullscreen(self, helper: MainScreenWindowHelper) -> None:
        with patch.object(window_module, "Clock") as mock_clock:
            helper._mock_wm_cls.is_fullscreen_now.return_value = False

            helper.toggle_screen_mode()

            mock_clock.schedule_once.assert_called_once()


class TestForceFullscreen:
    def test_schedules_fullscreen(self, helper: MainScreenWindowHelper) -> None:
        with patch.object(window_module, "Clock") as mock_clock:
            helper.force_fullscreen()

            mock_clock.schedule_once.assert_called_once()


class TestExitFullscreen:
    def test_noop_when_not_fullscreen(self, helper: MainScreenWindowHelper) -> None:
        helper._mock_wm_cls.is_fullscreen_now.return_value = False

        helper.exit_fullscreen()

        helper._comic_reader_manager.clear_window_state.assert_not_called()

    def test_exits_when_fullscreen(self, helper: MainScreenWindowHelper) -> None:
        helper._mock_wm_cls.is_fullscreen_now.return_value = True

        helper.exit_fullscreen()

        helper._comic_reader_manager.clear_window_state.assert_called_once()
        helper._window_manager.goto_windowed_mode.assert_called_once()


class TestGotoWindowedMode:
    def test_clears_state_and_delegates(self, helper: MainScreenWindowHelper) -> None:
        helper._goto_windowed_mode()

        helper._comic_reader_manager.clear_window_state.assert_called_once()
        helper._window_manager.goto_windowed_mode.assert_called_once()


class TestSetHintsForWindowedMode:
    def test_sets_size_hint(self, helper: MainScreenWindowHelper) -> None:
        helper._set_hints_for_windowed_mode()

        assert helper._host.size_hint == (1, 1)


class TestOnFinishedGotoWindowedMode:
    def test_updates_button_and_fonts(self, helper: MainScreenWindowHelper) -> None:
        with (
            patch.object(window_module, "Window") as mock_window,
            patch.object(window_module, "show_action_bar") as mock_show,
        ):
            mock_window.height = 800

            helper._on_finished_goto_windowed_mode()

            assert helper._fullscreen_button.text == "Fullscreen"
            assert helper._fullscreen_button.icon == "fullscreen.png"
            helper._update_fonts.assert_called_with(800)
            mock_show.assert_called_once_with(helper._action_bar)


class TestGotoFullscreenMode:
    def test_saves_state_and_delegates(self, helper: MainScreenWindowHelper) -> None:
        helper._goto_fullscreen_mode()

        helper._comic_reader_manager.save_window_state_now.assert_called_once()
        helper._window_manager.goto_fullscreen_mode.assert_called_once()


class TestOnFinishedGotoFullscreenMode:
    def test_updates_button_and_fonts(self, helper: MainScreenWindowHelper) -> None:
        with patch.object(window_module, "Window") as mock_window:
            mock_window.height = 1080
            helper._host.height = 1080
            helper._mock_wm_cls.is_fullscreen_now.return_value = True

            helper._on_finished_goto_fullscreen_mode()

            assert helper._fullscreen_button.text == "Windowed"
            assert helper._fullscreen_button.icon == "exit_fullscreen.png"
            helper._update_fonts.assert_called_with(1080)

    def test_adjusts_host_height_when_too_small(self, helper: MainScreenWindowHelper) -> None:
        with patch.object(window_module, "Window") as mock_window:
            mock_window.height = 1080
            helper._host.height = 500
            helper._mock_wm_cls.is_fullscreen_now.return_value = True

            helper._on_finished_goto_fullscreen_mode()

            assert helper._host.height == 1080


class TestOnMainLayoutSizeChanged:
    def test_not_fullscreen_skips_resize(self, helper: MainScreenWindowHelper) -> None:
        helper._mock_wm_cls.is_fullscreen_now.return_value = False

        helper.on_main_layout_size_changed(MagicMock(), (1920, 1080))

        helper._fun_image_view_screen.on_resized.assert_called_with((1920, 1080))

    def test_fullscreen_calls_change_size(self, helper: MainScreenWindowHelper) -> None:
        helper._mock_wm_cls.is_fullscreen_now.return_value = True

        with patch.object(helper, "_change_fullscreen_win_size") as mock_change:
            helper.on_main_layout_size_changed(MagicMock(), (1920, 1080))

            mock_change.assert_called_with(1080)


class TestChangeFullscreenWinSize:
    def test_sets_size(self, helper: MainScreenWindowHelper) -> None:
        with (
            patch.object(window_module, "Window") as mock_window,
            patch.object(window_module, "get_win_width_from_height", return_value=1600),
        ):
            mock_window.height = 900
            mock_window.left = 0
            mock_window.top = 0
            mock_window.size = (1920, 1080)
            helper._mock_wm_cls.is_fullscreen_now.return_value = True
            helper._mock_wm_cls.get_screen_mode_now.return_value = "fullscreen"

            helper._change_fullscreen_win_size(1080)

            assert helper._host.size_hint == (None, None)

    def test_clamps_height_to_window(self, helper: MainScreenWindowHelper) -> None:
        with (
            patch.object(window_module, "Window") as mock_window,
            patch.object(
                window_module, "get_win_width_from_height", return_value=1600
            ) as mock_get_width,
        ):
            mock_window.height = 1080
            mock_window.left = 0
            mock_window.top = 0
            mock_window.size = (1920, 1080)
            helper._mock_wm_cls.is_fullscreen_now.return_value = True
            helper._mock_wm_cls.get_screen_mode_now.return_value = "fullscreen"

            # Pass height lower than Window.height
            helper._change_fullscreen_win_size(500)

            # Should have been clamped to 1080
            mock_get_width.assert_called_once()


class TestResizeBinding:
    def test_binds_size(self, helper: MainScreenWindowHelper) -> None:
        helper.resize_binding()

        helper._main_layout.bind.assert_called_once_with(size=helper.on_main_layout_size_changed)


class TestActionBarVisibility:
    def test_hide_action_bar(self, helper: MainScreenWindowHelper) -> None:
        with patch.object(window_module, "hide_action_bar") as mock_hide:
            helper.hide_action_bar()
            mock_hide.assert_called_once_with(helper._action_bar)

    def test_show_action_bar(self, helper: MainScreenWindowHelper) -> None:
        with patch.object(window_module, "show_action_bar") as mock_show:
            helper.show_action_bar()
            mock_show.assert_called_once_with(helper._action_bar)
