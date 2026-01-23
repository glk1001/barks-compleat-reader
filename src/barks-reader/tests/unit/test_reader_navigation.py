from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from barks_reader import reader_navigation as nav_module
from barks_reader.reader_navigation import ReaderNavigation


class TestReaderNavigation:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.max_width = 2000
        self.top_frac = 0.1
        self.bottom_frac = 0.9
        self.nav = ReaderNavigation(self.max_width, self.top_frac, self.bottom_frac)

    def test_update_regions(self) -> None:
        win_width = 1000
        win_height = 1000
        win_left = 0
        win_top = 0

        self.nav.update_regions(win_width, win_height, win_left, win_top)

        # x_mid = 1000/2 - 0 = 500
        assert self.nav.x_mid == 500  # noqa: PLR2004

        # y_top_margin = (1000 - 0) - (0.1 * 1000) = 900
        assert self.nav.y_top_margin == 900  # noqa: PLR2004

        # y_bottom_margin = (1000 - 0) - (0.9 * 1000) = 100
        assert self.nav.y_bottom_margin == 100  # noqa: PLR2004

    @patch.object(nav_module, "WindowManager")
    def test_is_in_top_margin(self, mock_window_manager: MagicMock) -> None:
        self.nav.update_regions(1000, 1000, 0, 0)
        # y_top_margin is 900

        # Case 1: Not fullscreen
        mock_window_manager.is_fullscreen_now.return_value = False

        assert self.nav.is_in_top_margin(500, 950)
        assert self.nav.is_in_top_margin(500, 900)
        assert not self.nav.is_in_top_margin(500, 850)

        # Case 2: Fullscreen
        mock_window_manager.is_fullscreen_now.return_value = True
        # Fullscreen margins: left = 2000/4 = 500. right = 2000 - 500 = 1500.

        # Inside horizontal center area (500 < x <= 1500) AND above top margin
        assert self.nav.is_in_top_margin(600, 950)

        # Outside horizontal center area
        assert not self.nav.is_in_top_margin(400, 950)
        assert not self.nav.is_in_top_margin(1600, 950)

    @patch.object(nav_module, "WindowManager")
    def test_is_in_bottom_margin(self, mock_window_manager: MagicMock) -> None:
        self.nav.update_regions(1000, 1000, 0, 0)
        # y_bottom_margin is 100

        # Case 1: Not fullscreen
        mock_window_manager.is_fullscreen_now.return_value = False

        assert self.nav.is_in_bottom_margin(500, 50)
        assert self.nav.is_in_bottom_margin(500, 100)
        assert not self.nav.is_in_bottom_margin(500, 150)

        # Case 2: Fullscreen
        mock_window_manager.is_fullscreen_now.return_value = True

        # Inside horizontal center area AND below bottom margin
        assert self.nav.is_in_bottom_margin(600, 50)

        # Outside horizontal center area
        assert not self.nav.is_in_bottom_margin(400, 50)
        assert not self.nav.is_in_bottom_margin(1600, 50)

    def test_is_in_left_margin(self) -> None:
        self.nav.update_regions(1000, 1000, 0, 0)
        # x_mid = 500, y_bottom = 100, y_top = 900

        assert self.nav.is_in_left_margin(400, 500)
        assert not self.nav.is_in_left_margin(600, 500)
        assert not self.nav.is_in_left_margin(400, 950)
        assert not self.nav.is_in_left_margin(400, 50)

    def test_is_in_right_margin(self) -> None:
        self.nav.update_regions(1000, 1000, 0, 0)
        # x_mid = 500, y_bottom = 100, y_top = 900

        assert self.nav.is_in_right_margin(600, 500)
        assert not self.nav.is_in_right_margin(400, 500)
        assert not self.nav.is_in_right_margin(600, 950)
        assert not self.nav.is_in_right_margin(600, 50)

    def test_offset_coordinates(self) -> None:
        # Test with win_left/win_top offsets (e.g. widget not at 0,0)
        self.nav.update_regions(1000, 1000, 100, 100)

        # x_mid = 1000/2 - 100 = 400
        assert self.nav.x_mid == 400  # noqa: PLR2004

        # y_top_margin = (1000 - 100) - (0.1 * 1000) = 800
        assert self.nav.y_top_margin == 800  # noqa: PLR2004

        # y_bottom_margin = (1000 - 100) - (0.9 * 1000) = 0
        assert self.nav.y_bottom_margin == 0
