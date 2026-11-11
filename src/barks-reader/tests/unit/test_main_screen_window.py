# ruff: noqa: SLF001, PLR2004

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import log_markers
from barks_reader.core.log_markers import pattern
from barks_reader.core.reader_utils import COMIC_PAGE_ASPECT_RATIO
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
            update_fonts=MagicMock(),
            content_aspect_ratio=lambda: COMIC_PAGE_ASPECT_RATIO,
        )
        yield HelperFixture(
            helper=h, mock_wm_cls=mock_wm_cls, mock_controller=mock_controller_cls.return_value
        )


class TestToggleScreenMode:
    def test_delegates_to_controller(self, hf: HelperFixture) -> None:
        with patch.object(window_module, "Window"), patch.object(window_module, "Clock"):
            hf.helper.toggle_screen_mode()

        hf.mock_controller.toggle.assert_called_once_with()

    def test_the_frames_drawn_after_a_toggle_are_logged_for_half_a_second(
        self, hf: HelperFixture, loguru_sink: list[str]
    ) -> None:
        """What a log has to say whether a frame was drawn half way through the change."""
        with (
            patch.object(window_module, "Window") as window,
            patch.object(window_module, "Clock") as clock,
        ):
            window.size = (2560, 1440)
            window.fullscreen = "auto"
            hf.helper._host.size = [1848, 1440]
            hf.helper._host.pos = [356, 0]
            hf.helper._action_bar.size = [1848, 45]

            hf.helper.toggle_screen_mode()

            bound = window.bind.call_args.kwargs
            (on_tick, every), _ = clock.schedule_interval.call_args
            assert every == 0
            on_tick(0)
            bound["on_draw"](window)
            bound["on_flip"](window)
            lines = [s for s in loguru_sink if "MainScreen frame +" in s]
            assert len(lines) == 1
            assert "ms (ticked +" in lines[0]
            assert "ms, drawing +" in lines[0]
            assert (
                "window = (2560, 1440), fullscreen = auto,"
                " screen = [1848, 1440] at [356, 0], action bar = [1848, 45]." in lines[0]
            )
            (stop, delay), _ = clock.schedule_once.call_args
            assert delay == window_module._FRAME_LOG_SECONDS
            stop(0)
            clock.schedule_interval.return_value.cancel.assert_called_once_with()
            window.unbind.assert_called_once_with(**bound)


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
            patch.object(window_module, "log_window_geometry") as mock_log_geometry,
        ):
            mock_window.height = 800

            hf.helper._on_finished_goto_windowed_mode()

            mock_log_geometry.assert_called_once_with("MainScreen windowed")

            assert hf.helper._fullscreen_button.text == "Fullscreen"
            assert hf.helper._fullscreen_button.icon == "fullscreen.png"
            hf.helper._update_fonts.assert_called_with(800)  # ty: ignore[unresolved-attribute]
            mock_set_vis.assert_called_once_with(
                hf.helper._action_bar, window_module.ActionBarVisibility.VISIBLE
            )


class TestOnFinishedGotoFullscreenMode:
    def test_updates_button_and_fonts(self, hf: HelperFixture) -> None:
        with (
            patch.object(window_module, "Window") as mock_window,
            patch.object(window_module, "log_window_geometry") as mock_log_geometry,
        ):
            mock_window.height = 1080
            mock_window.width = 1920
            hf.helper._host.height = 1080
            hf.mock_wm_cls.is_fullscreen_now.return_value = True

            hf.helper._on_finished_goto_fullscreen_mode()

            mock_log_geometry.assert_called_once_with("MainScreen fullscreen")

            assert hf.helper._fullscreen_button.text == "Windowed"
            assert hf.helper._fullscreen_button.icon == "exit_fullscreen.png"
            hf.helper._update_fonts.assert_called_with(1080)  # ty: ignore[unresolved-attribute]

    def test_adjusts_host_height_when_too_small(self, hf: HelperFixture) -> None:
        with patch.object(window_module, "Window") as mock_window:
            mock_window.height = 1080
            mock_window.width = 1920
            hf.helper._host.height = 500
            hf.mock_wm_cls.is_fullscreen_now.return_value = True

            hf.helper._on_finished_goto_fullscreen_mode()

            assert hf.helper._host.height == 1080

    def test_a_screen_narrower_than_a_page_sizes_the_fonts_from_the_box(
        self, hf: HelperFixture
    ) -> None:
        with (
            patch.object(window_module, "Window") as mock_window,
            patch.object(window_module, "log_window_geometry"),
        ):
            mock_window.height = 2560
            mock_window.width = 1440
            hf.helper._host.height = 2219
            hf.mock_wm_cls.is_fullscreen_now.return_value = True

            hf.helper._on_finished_goto_fullscreen_mode()

            box_height = round(1440 * COMIC_PAGE_ASPECT_RATIO) + window_module.ACTION_BAR_SIZE_Y
            assert box_height < 2560
            hf.helper._update_fonts.assert_called_once_with(box_height)  # ty: ignore[unresolved-attribute]


class TestRefitFullscreen:
    def test_the_box_and_the_fonts_follow_a_new_layout(self, hf: HelperFixture) -> None:
        with patch.object(window_module, "Window") as mock_window:
            mock_window.height = 1024
            mock_window.width = 1280
            hf.mock_wm_cls.is_fullscreen_now.return_value = True
            hf.mock_wm_cls.get_screen_mode_now.return_value = "fullscreen"
            hf.helper._content_aspect_ratio = lambda: 0.75

            hf.helper.refit_fullscreen()

            box_height = round(1280 * 0.75) + window_module.ACTION_BAR_SIZE_Y
            assert box_height < 1024
            assert hf.helper._host.size == (1280, box_height)
            hf.helper._update_fonts.assert_called_once_with(box_height)  # ty: ignore[unresolved-attribute]

    def test_a_windowed_screen_is_left_alone(self, hf: HelperFixture) -> None:
        hf.mock_wm_cls.is_fullscreen_now.return_value = False

        hf.helper.refit_fullscreen()

        hf.helper._update_fonts.assert_not_called()  # ty: ignore[unresolved-attribute]


class TestRestoreWindowedSizeHints:
    def test_a_fixed_size_is_kept_in_fullscreen(
        self, hf: HelperFixture, loguru_sink: list[str]
    ) -> None:
        """Fullscreen fixes the size on purpose (the box narrower than the window)."""
        hf.mock_wm_cls.is_fullscreen_now.return_value = True
        hf.helper._host.size_hint_x = None
        hf.helper._host.size_hint_y = None
        hf.helper._host.size_hint = (None, None)

        hf.helper.restore_windowed_size_hints()

        assert hf.helper._host.size_hint == (None, None)
        restored = pattern(log_markers.MAIN_SIZE_HINTS_RESTORED)
        assert not any(re.search(restored, line) for line in loguru_sink)

    @pytest.mark.parametrize(("hint_x", "hint_y"), [(1, None), (None, 1), (1, 1)])
    def test_a_size_that_follows_the_window_either_way_is_left(
        self, hf: HelperFixture, hint_x: float | None, hint_y: float | None
    ) -> None:
        hf.mock_wm_cls.is_fullscreen_now.return_value = False
        hf.helper._host.size_hint_x = hint_x
        hf.helper._host.size_hint_y = hint_y
        hf.helper._host.size_hint = (hint_x, hint_y)

        hf.helper.restore_windowed_size_hints()

        assert hf.helper._host.size_hint == (hint_x, hint_y)

    def test_a_size_fixed_while_windowed_follows_the_window_again(self, hf: HelperFixture) -> None:
        hf.mock_wm_cls.is_fullscreen_now.return_value = False
        hf.helper._host.size_hint_x = None
        hf.helper._host.size_hint_y = None
        hf.helper._host.size = (1742, 1360)

        hf.helper.restore_windowed_size_hints()

        assert hf.helper._host.size_hint == (1, 1)


class TestOnMainLayoutSizeChanged:
    def test_not_fullscreen_skips_resize(self, hf: HelperFixture) -> None:
        hf.mock_wm_cls.is_fullscreen_now.return_value = False

        hf.helper.on_main_layout_size_changed(MagicMock(), (1920, 1080))

        hf.mock_controller.set_fullscreen_size.assert_not_called()

    def test_windowed_with_the_host_size_still_fixed_lets_it_follow_the_window(
        self, hf: HelperFixture, loguru_sink: list[str]
    ) -> None:
        """A fullscreen another screen drove leaves the size fixed: it is freed, and said."""
        hf.mock_wm_cls.is_fullscreen_now.return_value = False
        hf.helper._host.size_hint_x = None
        hf.helper._host.size_hint_y = None
        hf.helper._host.size = (831, 1300)

        hf.helper.on_main_layout_size_changed(MagicMock(), (782, 1225))

        assert hf.helper._host.size_hint == (1, 1)
        restored = pattern(log_markers.MAIN_SIZE_HINTS_RESTORED, width=831, height=1300)
        assert any(re.search(restored, line) for line in loguru_sink)

    def test_windowed_with_the_hints_restored_is_quiet(
        self, hf: HelperFixture, loguru_sink: list[str]
    ) -> None:
        hf.mock_wm_cls.is_fullscreen_now.return_value = False
        hf.helper._host.size_hint_x = 1
        hf.helper._host.size_hint_y = 1
        hf.helper._host.size_hint = (1, 1)

        hf.helper.on_main_layout_size_changed(MagicMock(), (782, 1225))

        assert hf.helper._host.size_hint == (1, 1)
        restored = pattern(log_markers.MAIN_SIZE_HINTS_RESTORED)
        assert not any(re.search(restored, line) for line in loguru_sink)

    def test_the_layout_s_new_size_and_window_mode_are_logged(
        self, hf: HelperFixture, loguru_sink: list[str]
    ) -> None:
        hf.mock_wm_cls.is_fullscreen_now.return_value = False
        hf.mock_wm_cls.get_screen_mode_now.return_value = "windowed"
        hf.helper._host.size_hint_x = 1
        hf.helper._host.size_hint_y = 1

        hf.helper.on_main_layout_size_changed(MagicMock(), (782, 1225))

        logged = pattern(log_markers.MAIN_LAYOUT_SIZE, width=782, height=1225, mode="windowed")
        assert any(re.search(logged, line) for line in loguru_sink)

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
