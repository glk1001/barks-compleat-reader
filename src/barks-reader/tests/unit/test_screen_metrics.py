from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import screen_metrics as screen_metrics_module
from barks_reader.core.platform_info import Platform
from barks_reader.core.screen_metrics import (
    ScreenInfo,
    ScreenMetrics,
    calculate_fitted_window_height,
    get_approximate_taskbar_height,
    get_best_window_height_fit,
)
from screeninfo import get_monitors


def _mock_monitor(
    *,
    x: int = 0,
    y: int = 0,
    width: int = 1920,
    height: int = 1080,
    width_mm: int | None = 100,
    height_mm: int | None = 100,
    is_primary: bool = True,
) -> MagicMock:
    monitor = MagicMock()
    monitor.x = x
    monitor.y = y
    monitor.width = width
    monitor.height = height
    monitor.width_mm = width_mm
    monitor.height_mm = height_mm
    monitor.is_primary = is_primary
    return monitor


class TestScreenMetrics:
    def test_get_approximate_taskbar_height(self) -> None:
        """Test taskbar height calculation for different platforms."""
        with patch.object(screen_metrics_module, "PLATFORM", Platform.WIN):
            assert get_approximate_taskbar_height() == 60  # noqa: PLR2004

        with patch.object(screen_metrics_module, "PLATFORM", Platform.LINUX):
            assert get_approximate_taskbar_height() == 55  # noqa: PLR2004

    def test_get_best_window_height_fit(self) -> None:
        """Test best window height calculation."""
        with patch.object(
            screen_metrics_module, get_approximate_taskbar_height.__name__, return_value=60
        ):
            assert get_best_window_height_fit(1000) == 940  # noqa: PLR2004

    def test_init_no_monitors(self) -> None:
        """Test initialization when no monitors are found."""
        with patch.object(screen_metrics_module, get_monitors.__name__, return_value=[]):
            metrics = ScreenMetrics()
            assert metrics.SCREEN_INFO == []
            assert metrics.NUM_MONITORS == 0

    def test_init_valid_monitors(self) -> None:
        """Test initialization with valid monitors."""
        mock_monitor = _mock_monitor(width_mm=508, height_mm=285)

        with patch.object(
            screen_metrics_module, get_monitors.__name__, return_value=[mock_monitor]
        ):
            metrics = ScreenMetrics()
            assert len(metrics.SCREEN_INFO) == 1
            info = metrics.SCREEN_INFO[0]
            assert info.width_pixels == 1920  # noqa: PLR2004
            assert info.height_pixels == 1080  # noqa: PLR2004
            assert info.width_in == 20  # 508 / 25.4  # noqa: PLR2004
            assert info.height_in == 11  # 285 / 25.4  # noqa: PLR2004
            assert info.is_primary is True
            # DPI check: (1920/508)*25.4 approx 96
            assert info.dpi > 0

    def test_init_invalid_dimensions(self) -> None:
        """Test initialization with monitors having invalid physical dimensions."""
        mock_monitor = _mock_monitor(
            width=1024, height=768, width_mm=None, height_mm=0, is_primary=False
        )

        with patch.object(
            screen_metrics_module, get_monitors.__name__, return_value=[mock_monitor]
        ):
            metrics = ScreenMetrics()
            assert len(metrics.SCREEN_INFO) == 1
            info = metrics.SCREEN_INFO[0]
            assert info.width_mm == 0
            assert info.height_mm == 0
            assert info.width_in == 0
            assert info.height_in == 0
            assert info.dpi == 0

    def test_get_primary_screen_info(self) -> None:
        """Test retrieving the primary screen info."""
        mock_primary = _mock_monitor(is_primary=True)
        mock_secondary = _mock_monitor(is_primary=False)

        with patch.object(
            screen_metrics_module,
            get_monitors.__name__,
            return_value=[mock_secondary, mock_primary],
        ):
            metrics = ScreenMetrics()
            primary = metrics.get_primary_screen_info()
            assert primary.is_primary is True

    def test_get_primary_screen_info_fallback(self) -> None:
        """Test fallback to first screen if no primary is marked."""
        mock_secondary = _mock_monitor(is_primary=False)

        with patch.object(
            screen_metrics_module, get_monitors.__name__, return_value=[mock_secondary]
        ):
            metrics = ScreenMetrics()
            primary = metrics.get_primary_screen_info()
            assert primary.is_primary is False
            assert primary == metrics.SCREEN_INFO[0]

    def test_get_monitor_for_pos(self) -> None:
        """Test finding a monitor for a given coordinate."""
        m1 = _mock_monitor()  # Monitor 1: 0,0 to 1920,1080
        m2 = _mock_monitor(x=1920, is_primary=False)  # Monitor 2: 1920,0 to 3840,1080

        with patch.object(screen_metrics_module, get_monitors.__name__, return_value=[m1, m2]):
            metrics = ScreenMetrics()

            # Inside M1
            assert metrics.get_monitor_for_pos(100, 100) == metrics.SCREEN_INFO[0]

            # Inside M2
            assert metrics.get_monitor_for_pos(2000, 100) == metrics.SCREEN_INFO[1]

            # Outside
            assert metrics.get_monitor_for_pos(-100, 0) is None
            assert metrics.get_monitor_for_pos(0, 2000) is None

    def test_refresh_no_change(self) -> None:
        """Test refresh returns False when monitor dimensions are unchanged."""
        mock_monitor = _mock_monitor(width_mm=508, height_mm=285)

        with patch.object(
            screen_metrics_module, get_monitors.__name__, return_value=[mock_monitor]
        ):
            metrics = ScreenMetrics()
            assert metrics.refresh() is False

    def test_refresh_detects_rotation(self) -> None:
        """Test refresh returns True when monitor dimensions change (rotation)."""
        mock_landscape = _mock_monitor(width_mm=508, height_mm=285)
        mock_portrait = _mock_monitor(width=1080, height=1920, width_mm=285, height_mm=508)

        with patch.object(
            screen_metrics_module, get_monitors.__name__, return_value=[mock_landscape]
        ):
            metrics = ScreenMetrics()

        with patch.object(
            screen_metrics_module, get_monitors.__name__, return_value=[mock_portrait]
        ):
            assert metrics.refresh() is True
            assert metrics.SCREEN_INFO[0].width_pixels == 1080  # noqa: PLR2004
            assert metrics.SCREEN_INFO[0].height_pixels == 1920  # noqa: PLR2004


class TestCalculateFittedWindowHeight:
    """Tests for the calculate_fitted_window_height pure function."""

    ASPECT_RATIO = 3200.0 / 2120.0  # ~1.509
    ACTION_BAR = 45

    def test_landscape_screen_height_limited(self) -> None:
        """On a landscape screen, height is the limiting factor."""
        height = calculate_fitted_window_height(
            screen_width=1920,
            screen_height=1080,
            aspect_ratio=self.ASPECT_RATIO,
            action_bar_height=self.ACTION_BAR,
        )
        # Height-limited: max_h = int(0.9 * 1080) = 972
        assert height == 972  # noqa: PLR2004
        # Verify width fits: content_w = round((972 - 45) / 1.509...) = 614
        content_w = round((height - self.ACTION_BAR) / self.ASPECT_RATIO)
        assert content_w <= int(0.9 * 1920)

    def test_portrait_screen_width_limited(self) -> None:
        """On a portrait screen, width is the limiting factor."""
        height = calculate_fitted_window_height(
            screen_width=1080,
            screen_height=1920,
            aspect_ratio=self.ASPECT_RATIO,
            action_bar_height=self.ACTION_BAR,
        )
        # Width-limited: max_w = int(0.9 * 1080) = 972
        # content_h = round(972 * 1.509...) = 1467, total = 1467 + 45 = 1512
        content_w = round((height - self.ACTION_BAR) / self.ASPECT_RATIO)
        assert content_w <= int(0.9 * 1080)
        assert height <= int(0.9 * 1920)

    def test_square_screen(self) -> None:
        """On a square screen, width is limiting since aspect ratio > 1."""
        height = calculate_fitted_window_height(
            screen_width=1080,
            screen_height=1080,
            aspect_ratio=self.ASPECT_RATIO,
            action_bar_height=self.ACTION_BAR,
        )
        content_w = round((height - self.ACTION_BAR) / self.ASPECT_RATIO)
        assert content_w <= int(0.9 * 1080)
        assert height <= int(0.9 * 1080)

    def test_small_screen(self) -> None:
        """Produces a valid positive height even on a small screen."""
        height = calculate_fitted_window_height(
            screen_width=800,
            screen_height=600,
            aspect_ratio=self.ASPECT_RATIO,
            action_bar_height=self.ACTION_BAR,
        )
        assert height > self.ACTION_BAR
        content_w = round((height - self.ACTION_BAR) / self.ASPECT_RATIO)
        assert content_w <= int(0.9 * 800)
        assert height <= int(0.9 * 600)

    def test_custom_fit_fraction(self) -> None:
        """Respects a custom fit_fraction."""
        height_90 = calculate_fitted_window_height(
            screen_width=1920,
            screen_height=1080,
            aspect_ratio=self.ASPECT_RATIO,
            action_bar_height=self.ACTION_BAR,
            fit_fraction=0.9,
        )
        height_50 = calculate_fitted_window_height(
            screen_width=1920,
            screen_height=1080,
            aspect_ratio=self.ASPECT_RATIO,
            action_bar_height=self.ACTION_BAR,
            fit_fraction=0.5,
        )
        assert height_50 < height_90


class TestScreenInfoDerivation:
    """`_get_screen_info` converts screeninfo's raw monitors into `ScreenInfo`."""

    @staticmethod
    def _single(monitor: MagicMock) -> ScreenInfo:
        with patch.object(screen_metrics_module, get_monitors.__name__, return_value=[monitor]):
            return ScreenMetrics().SCREEN_INFO[0]

    def test_every_field_is_derived_from_the_monitor(self) -> None:
        """All eleven fields at once — they are passed positionally, so order matters."""
        info = self._single(
            _mock_monitor(
                x=1920,
                y=-40,
                width=1920,
                height=1080,
                width_mm=508,
                height_mm=285,
                is_primary=False,
            )
        )

        assert info == ScreenInfo(
            display=0,
            monitor_x=1920,
            monitor_y=-40,
            width_pixels=1920,
            height_pixels=1080,
            width_mm=508,
            height_mm=285,
            # Rounded from mm: 508 / 25.4 == 20, 285 / 25.4 == 11.2 -> 11.
            width_in=20,
            height_in=11,
            # dpi_x = (1920 / 508) * 25.4 == 96.0, dpi_y = (1080 / 285) * 25.4 == 96.25;
            # the average, truncated.
            dpi=96,
            is_primary=False,
        )

    def test_displays_are_numbered_in_monitor_order(self) -> None:
        monitors = [_mock_monitor(), _mock_monitor(x=1920), _mock_monitor(x=3840)]
        with patch.object(screen_metrics_module, get_monitors.__name__, return_value=monitors):
            metrics = ScreenMetrics()

        assert [info.display for info in metrics.SCREEN_INFO] == [0, 1, 2]
        assert metrics.NUM_MONITORS == 3  # noqa: PLR2004

    def test_a_monitor_reporting_one_millimetre_is_still_measured(self) -> None:
        """The physical-size guard is `> 0`, so 1mm is a (silly but) usable size."""
        info = self._single(_mock_monitor(width=1920, height=1080, width_mm=1, height_mm=1))

        assert (info.width_mm, info.height_mm) == (1, 1)
        assert info.dpi > 0

    @pytest.mark.parametrize(
        ("width_mm", "height_mm"),
        [
            pytest.param(None, 285, id="width_missing"),
            pytest.param(508, None, id="height_missing"),
            pytest.param(0, 285, id="width_zero"),
            pytest.param(508, 0, id="height_zero"),
            pytest.param(-1, 285, id="width_negative"),
            pytest.param(508, -1, id="height_negative"),
        ],
    )
    def test_unusable_physical_size_zeroes_every_derived_field(
        self, width_mm: int | None, height_mm: int | None
    ) -> None:
        """*Both* dimensions must be present and positive; either one failing zeroes all.

        A negative size would otherwise produce a negative DPI rather than the
        "unknown" sentinel.
        """
        info = self._single(_mock_monitor(width_mm=width_mm, height_mm=height_mm))

        assert (info.width_mm, info.height_mm, info.width_in, info.height_in, info.dpi) == (
            0,
            0,
            0,
            0,
            0,
        )
        # The pixel dimensions are still reported.
        assert (info.width_pixels, info.height_pixels) == (1920, 1080)

    def test_is_primary_defaults_to_false_when_screeninfo_reports_none(self) -> None:
        monitor = _mock_monitor()
        monitor.is_primary = None

        assert self._single(monitor).is_primary is False


class TestMonitorForPosBounds:
    """The hit test is half-open: inclusive at the origin, exclusive at the far edge."""

    @staticmethod
    def _two_monitors() -> ScreenMetrics:
        monitors = [_mock_monitor(), _mock_monitor(x=1920, is_primary=False)]
        with patch.object(screen_metrics_module, get_monitors.__name__, return_value=monitors):
            return ScreenMetrics()

    @pytest.mark.parametrize(
        ("x", "y", "expected_display"),
        [
            pytest.param(0, 0, 0, id="top_left_corner_is_inside"),
            pytest.param(1919, 1079, 0, id="last_pixel_is_inside"),
            # The far edge belongs to the *next* monitor, not this one.
            pytest.param(1920, 0, 1, id="far_edge_belongs_to_the_next_monitor"),
            pytest.param(3839, 1079, 1, id="last_pixel_of_the_second_monitor"),
        ],
    )
    def test_bounds(self, x: int, y: int, expected_display: int) -> None:
        found = self._two_monitors().get_monitor_for_pos(x, y)

        assert found is not None
        assert found.display == expected_display

    @pytest.mark.parametrize(
        ("x", "y"),
        [
            pytest.param(3840, 0, id="past_the_right_edge"),
            pytest.param(0, 1080, id="past_the_bottom_edge"),
            pytest.param(-1, 0, id="left_of_the_origin"),
            pytest.param(0, -1, id="above_the_origin"),
        ],
    )
    def test_positions_outside_every_monitor_return_none(self, x: int, y: int) -> None:
        assert self._two_monitors().get_monitor_for_pos(x, y) is None


class TestFittedWindowHeightBranches:
    def test_width_limited_result_is_derived_from_the_width_budget(self) -> None:
        """A tall/narrow screen forces the width-limited branch.

        The returned height is the content height implied by the width budget *plus*
        the action bar, not the raw content height.
        """
        # 0.9 * 1000 = 900 wide, 0.9 * 3000 = 2700 tall. Height-limited would need
        # (2700 - 100) / 1.5 = 1733 px of width, far past the 900 available.
        result = calculate_fitted_window_height(
            screen_width=1000,
            screen_height=3000,
            aspect_ratio=1.5,
            action_bar_height=100,
        )

        # content_h = round(900 * 1.5) = 1350, plus the 100px bar.
        assert result == 1450  # noqa: PLR2004

    def test_height_limited_result_is_the_whole_height_budget(self) -> None:
        # 0.9 * 3000 = 2700 wide, 0.9 * 1000 = 900 tall. Content is 800 x 533, which
        # fits the width budget easily.
        result = calculate_fitted_window_height(
            screen_width=3000,
            screen_height=1000,
            aspect_ratio=1.5,
            action_bar_height=100,
        )

        assert result == 900  # noqa: PLR2004

    def test_the_action_bar_is_subtracted_from_the_height_budget(self) -> None:
        """The bar eats into the budget; it is not added on top of it.

        On a square screen with a square aspect the two differ visibly: subtracting
        leaves 500px of content that fits the width budget (height-limited, 900),
        while adding would overflow it and fall through to the width-limited branch.
        """
        result = calculate_fitted_window_height(
            screen_width=1000,
            screen_height=1000,
            aspect_ratio=1.0,
            action_bar_height=400,
        )

        assert result == 900  # noqa: PLR2004

    def test_the_fit_fraction_scales_both_budgets(self) -> None:
        result = calculate_fitted_window_height(
            screen_width=3000,
            screen_height=1000,
            aspect_ratio=1.5,
            action_bar_height=100,
            fit_fraction=0.5,
        )

        # Height-limited again, but against half the screen rather than 90% of it.
        assert result == 500  # noqa: PLR2004


class TestRefreshUpdatesCounts:
    def test_monitor_count_tracks_the_new_monitor_list(self) -> None:
        with patch.object(
            screen_metrics_module, get_monitors.__name__, return_value=[_mock_monitor()]
        ):
            metrics = ScreenMetrics()
        assert metrics.NUM_MONITORS == 1

        two = [_mock_monitor(), _mock_monitor(x=1920, is_primary=False)]
        with patch.object(screen_metrics_module, get_monitors.__name__, return_value=two):
            changed = metrics.refresh()

        assert changed is True
        assert metrics.NUM_MONITORS == 2  # noqa: PLR2004
        assert len(metrics.SCREEN_INFO) == 2  # noqa: PLR2004
