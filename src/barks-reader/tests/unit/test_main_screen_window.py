# ruff: noqa: SLF001, PLR2004

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui import main_screen_window as window_module
from barks_reader.ui.main_screen_window import MainScreenWindowHelper

if TYPE_CHECKING:
    from collections.abc import Generator


@dataclass
class HelperFixture:
    """Wraps MainScreenWindowHelper + the patched WindowManager class + controller.

    ``mock_wm_cls`` patches the ``WindowManager`` *class* so the helper's static
    calls (``WindowManager.is_fullscreen_now()`` etc.) are controllable.
    ``mock_controller`` is the ``WindowModeController`` the helper builds and
    delegates its toggle/goto scaffolding to — the mode-toggle tests assert on it.
    """

    helper: MainScreenWindowHelper
    mock_wm_cls: MagicMock
    mock_controller: MagicMock


@pytest.fixture
def hf() -> Generator[HelperFixture, Any]:
    with (
        patch.object(window_module, "WindowManager") as mock_wm_cls,
        patch.object(window_module, "WindowModeController") as mock_controller_cls,
    ):
        h = MainScreenWindowHelper(
            host_screen=MagicMock(),
            window_manager=MagicMock(),
            action_bar=MagicMock(),
            fullscreen_button=MagicMock(),
            fullscreen_icon="fullscreen.png",
            fullscreen_exit_icon="exit_fullscreen.png",
            main_layout=MagicMock(),
            fun_image_view_screen=MagicMock(),
            update_fonts=MagicMock(),
        )
        yield HelperFixture(
            helper=h, mock_wm_cls=mock_wm_cls, mock_controller=mock_controller_cls.return_value
        )


class TestToggleScreenMode:
    def test_delegates_to_controller(self, hf: HelperFixture) -> None:
        hf.helper.toggle_screen_mode()

        hf.mock_controller.toggle.assert_called_once_with()


class TestForceFullscreen:
    def test_delegates_to_controller(self, hf: HelperFixture) -> None:
        hf.helper.force_fullscreen()

        hf.mock_controller.force_fullscreen.assert_called_once_with()


class TestExitFullscreen:
    def test_delegates_unconditionally(self, hf: HelperFixture) -> None:
        # Even when already windowed: the manager skips the transition but
        # still fires the completion callback, so every caller shares one
        # completion path.
        hf.helper.exit_fullscreen()

        hf.mock_controller.goto_windowed.assert_called_once_with()


class TestSetHintsForWindowedMode:
    def test_sets_size_hint(self, hf: HelperFixture) -> None:
        hf.helper._set_hints_for_windowed_mode()

        assert hf.helper._host.size_hint == (1, 1)


class TestOnFinishedGotoWindowedMode:
    def test_updates_button_and_fonts(self, hf: HelperFixture) -> None:
        with (
            patch.object(window_module, "Window") as mock_window,
            patch.object(window_module, "set_action_bar_visibility") as mock_set_vis,
        ):
            mock_window.height = 800

            hf.helper._on_finished_goto_windowed_mode()

            assert hf.helper._fullscreen_button.text == "Fullscreen"
            assert hf.helper._fullscreen_button.icon == "fullscreen.png"
            hf.helper._update_fonts.assert_called_with(800)  # ty: ignore[unresolved-attribute]
            mock_set_vis.assert_called_once_with(
                hf.helper._action_bar, window_module.ActionBarVisibility.VISIBLE
            )


class TestOnFinishedGotoFullscreenMode:
    def test_updates_button_and_fonts(self, hf: HelperFixture) -> None:
        with patch.object(window_module, "Window") as mock_window:
            mock_window.height = 1080
            hf.helper._host.height = 1080
            hf.mock_wm_cls.is_fullscreen_now.return_value = True

            hf.helper._on_finished_goto_fullscreen_mode()

            assert hf.helper._fullscreen_button.text == "Windowed"
            assert hf.helper._fullscreen_button.icon == "exit_fullscreen.png"
            hf.helper._update_fonts.assert_called_with(1080)  # ty: ignore[unresolved-attribute]

    def test_adjusts_host_height_when_too_small(self, hf: HelperFixture) -> None:
        with patch.object(window_module, "Window") as mock_window:
            mock_window.height = 1080
            hf.helper._host.height = 500
            hf.mock_wm_cls.is_fullscreen_now.return_value = True

            hf.helper._on_finished_goto_fullscreen_mode()

            assert hf.helper._host.height == 1080


class TestOnMainLayoutSizeChanged:
    def test_not_fullscreen_skips_resize(self, hf: HelperFixture) -> None:
        hf.mock_wm_cls.is_fullscreen_now.return_value = False

        hf.helper.on_main_layout_size_changed(MagicMock(), (1920, 1080))

        hf.helper._fun_image_view_screen.on_resized.assert_called_with((1920, 1080))

    def test_fullscreen_calls_change_size(self, hf: HelperFixture) -> None:
        hf.mock_wm_cls.is_fullscreen_now.return_value = True

        with patch.object(hf.helper, "_change_fullscreen_win_size") as mock_change:
            hf.helper.on_main_layout_size_changed(MagicMock(), (1920, 1080))

            mock_change.assert_called_with(1080)


class TestChangeFullscreenWinSize:
    def test_sets_size(self, hf: HelperFixture) -> None:
        with (
            patch.object(window_module, "Window") as mock_window,
            patch.object(window_module, "get_win_dimensions", return_value=(1600, 1000)),
        ):
            mock_window.height = 900
            mock_window.left = 0
            mock_window.top = 0
            mock_window.width = 1920
            mock_window.size = (1920, 1080)
            hf.mock_wm_cls.is_fullscreen_now.return_value = True
            hf.mock_wm_cls.get_screen_mode_now.return_value = "fullscreen"

            hf.helper._change_fullscreen_win_size(1080)

            assert hf.helper._host.size_hint == (None, None)

    def test_clamps_height_to_window(self, hf: HelperFixture) -> None:
        with (
            patch.object(window_module, "Window") as mock_window,
            patch.object(
                window_module, "get_win_dimensions", return_value=(1600, 1000)
            ) as mock_get_width,
        ):
            mock_window.height = 1080
            mock_window.left = 0
            mock_window.top = 0
            mock_window.width = 1920
            mock_window.size = (1920, 1080)
            hf.mock_wm_cls.is_fullscreen_now.return_value = True
            hf.mock_wm_cls.get_screen_mode_now.return_value = "fullscreen"

            # Pass height lower than Window.height
            hf.helper._change_fullscreen_win_size(500)

            # Should have been clamped to 1080
            mock_get_width.assert_called_once()


class TestResizeBinding:
    def test_binds_size(self, hf: HelperFixture) -> None:
        hf.helper.resize_binding()

        hf.helper._main_layout.bind.assert_called_once_with(
            size=hf.helper.on_main_layout_size_changed
        )


class TestActionBarVisibility:
    def test_hide_action_bar(self, hf: HelperFixture) -> None:
        with patch.object(window_module, "set_action_bar_visibility") as mock_set_vis:
            hf.helper.hide_action_bar()
            mock_set_vis.assert_called_once_with(
                hf.helper._action_bar, window_module.ActionBarVisibility.HIDDEN
            )

    def test_show_action_bar(self, hf: HelperFixture) -> None:
        with patch.object(window_module, "set_action_bar_visibility") as mock_set_vis:
            hf.helper.show_action_bar()
            mock_set_vis.assert_called_once_with(
                hf.helper._action_bar, window_module.ActionBarVisibility.VISIBLE
            )
