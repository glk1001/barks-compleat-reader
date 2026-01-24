from __future__ import annotations

from unittest.mock import MagicMock, patch

from barks_reader.core import screen_metrics as screen_metrics_module
from barks_reader.core.platform_info import Platform
from barks_reader.core.screen_metrics import (
    ScreenMetrics,
    get_approximate_taskbar_height,
    get_best_window_height_fit,
)
from screeninfo import get_monitors


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
        mock_monitor = MagicMock()
        mock_monitor.x = 0
        mock_monitor.y = 0
        mock_monitor.width = 1920
        mock_monitor.height = 1080
        mock_monitor.width_mm = 508
        mock_monitor.height_mm = 285
        mock_monitor.is_primary = True

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
        mock_monitor = MagicMock()
        mock_monitor.x = 0
        mock_monitor.y = 0
        mock_monitor.width = 1024
        mock_monitor.height = 768
        mock_monitor.width_mm = None
        mock_monitor.height_mm = 0
        mock_monitor.is_primary = False

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
        mock_primary = MagicMock()
        mock_primary.is_primary = True
        mock_primary.width_mm = 100
        mock_primary.height_mm = 100

        mock_secondary = MagicMock()
        mock_secondary.is_primary = False
        mock_secondary.width_mm = 100
        mock_secondary.height_mm = 100

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
        mock_secondary = MagicMock()
        mock_secondary.is_primary = False
        mock_secondary.width_mm = 100
        mock_secondary.height_mm = 100

        with patch.object(
            screen_metrics_module, get_monitors.__name__, return_value=[mock_secondary]
        ):
            metrics = ScreenMetrics()
            primary = metrics.get_primary_screen_info()
            assert primary.is_primary is False
            assert primary == metrics.SCREEN_INFO[0]

    def test_get_monitor_for_pos(self) -> None:
        """Test finding a monitor for a given coordinate."""
        # Monitor 1: 0,0 to 1920,1080
        m1 = MagicMock()
        m1.x = 0
        m1.y = 0
        m1.width = 1920
        m1.height = 1080
        m1.width_mm = 100
        m1.height_mm = 100
        m1.is_primary = True

        # Monitor 2: 1920,0 to 3840,1080
        m2 = MagicMock()
        m2.x = 1920
        m2.y = 0
        m2.width = 1920
        m2.height = 1080
        m2.width_mm = 100
        m2.height_mm = 100
        m2.is_primary = False

        with patch.object(screen_metrics_module, get_monitors.__name__, return_value=[m1, m2]):
            metrics = ScreenMetrics()

            # Inside M1
            assert metrics.get_monitor_for_pos(100, 100) == metrics.SCREEN_INFO[0]

            # Inside M2
            assert metrics.get_monitor_for_pos(2000, 100) == metrics.SCREEN_INFO[1]

            # Outside
            assert metrics.get_monitor_for_pos(-100, 0) is None
            assert metrics.get_monitor_for_pos(0, 2000) is None
