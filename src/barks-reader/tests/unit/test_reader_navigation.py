from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui import reader_navigation as nav_module
from barks_reader.ui.reader_navigation import ReaderNavigation


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


def _inside_points(rect: tuple[int, int, int, int]) -> list[tuple[int, int]]:
    """Return the centre and the four corners of `rect`, all inside it."""
    x, y, w, h = rect
    return [
        (x + w // 2, y + h // 2),
        (x, y),
        (x + w - 1, y),
        (x, y + h - 1),
        (x + w - 1, y + h - 1),
    ]


class TestTapRegions:
    """Every point of a reported region is one its own check accepts."""

    WIDTH = 1000
    HEIGHT = 1000

    @pytest.fixture
    def nav(self) -> ReaderNavigation:
        nav = ReaderNavigation(2000, 0.1, 0.9)
        nav.update_regions(self.WIDTH, self.HEIGHT, 0, 0)
        return nav

    @pytest.mark.parametrize("fullscreen", [False, True])
    @patch.object(nav_module, "WindowManager")
    def test_each_region_is_inside_its_check(
        self, mock_window_manager: MagicMock, nav: ReaderNavigation, *, fullscreen: bool
    ) -> None:
        mock_window_manager.is_fullscreen_now.return_value = fullscreen
        regions = nav.tap_regions(self.WIDTH, self.HEIGHT)
        checks = {
            "left margin": nav.is_in_left_margin,
            "right margin": nav.is_in_right_margin,
            "top margin": nav.is_in_top_margin,
        }
        assert set(regions) == set(checks)
        for name, rect in regions.items():
            for point in _inside_points(rect):
                assert checks[name](*point), (name, rect, point)

    @patch.object(nav_module, "WindowManager")
    def test_the_left_and_right_margins_meet_at_the_middle(
        self, mock_window_manager: MagicMock, nav: ReaderNavigation
    ) -> None:
        mock_window_manager.is_fullscreen_now.return_value = False
        regions = nav.tap_regions(self.WIDTH, self.HEIGHT)
        left_x, _, left_w, _ = regions["left margin"]
        right_x, _, right_w, _ = regions["right margin"]
        assert left_x + left_w == right_x == nav.x_mid
        assert right_x + right_w == self.WIDTH

    @patch.object(nav_module, "WindowManager")
    def test_fullscreen_narrows_the_top_margin_to_the_middle(
        self, mock_window_manager: MagicMock, nav: ReaderNavigation
    ) -> None:
        mock_window_manager.is_fullscreen_now.return_value = True
        x, _, w, _ = nav.tap_regions(self.WIDTH, self.HEIGHT)["top margin"]
        # The fullscreen band is (500, 1500]: in a 1000-wide widget, 501 to the edge.
        assert (x, x + w) == (501, self.WIDTH)
        assert not nav.is_in_top_margin(x - 1, 950)

    def test_no_regions_before_the_sizes_are_known(self) -> None:
        # Before update_regions every margin is -1: nothing to press yet.
        nav = ReaderNavigation(2000, 0.1, 0.9)
        with patch.object(nav_module, "WindowManager") as mock_window_manager:
            mock_window_manager.is_fullscreen_now.return_value = False
            regions = nav.tap_regions(self.WIDTH, self.HEIGHT)
        assert "left margin" not in regions
        assert "right margin" not in regions
