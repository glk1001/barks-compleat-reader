from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import comic_book_loader_platform_settings as platform_settings_module
from barks_reader.core.comic_book_loader_platform_settings import PrefetchTuning


class TestSystemProfile:
    def test_low_end_few_cpus_low_ram(self) -> None:
        with (
            patch.object(platform_settings_module.os, "cpu_count", return_value=2),
            patch.object(platform_settings_module.psutil, "virtual_memory") as mock_vm,
        ):
            mock_vm.return_value = MagicMock(total=3 * 1024**3)
            profile = PrefetchTuning.detect_system_profile()

        assert profile.is_low_end is True
        assert profile.is_mid_range is False
        assert profile.is_high_end is False

    def test_low_end_many_cpus_but_low_ram(self) -> None:
        with (
            patch.object(platform_settings_module.os, "cpu_count", return_value=8),
            patch.object(platform_settings_module.psutil, "virtual_memory") as mock_vm,
        ):
            mock_vm.return_value = MagicMock(total=4 * 1024**3)
            profile = PrefetchTuning.detect_system_profile()

        assert profile.is_low_end is True

    def test_mid_range(self) -> None:
        with (
            patch.object(platform_settings_module.os, "cpu_count", return_value=4),
            patch.object(platform_settings_module.psutil, "virtual_memory") as mock_vm,
        ):
            mock_vm.return_value = MagicMock(total=8 * 1024**3)
            profile = PrefetchTuning.detect_system_profile()

        assert profile.is_low_end is False
        assert profile.is_mid_range is True
        assert profile.is_high_end is False

    def test_high_end(self) -> None:
        with (
            patch.object(platform_settings_module.os, "cpu_count", return_value=16),
            patch.object(platform_settings_module.psutil, "virtual_memory") as mock_vm,
        ):
            mock_vm.return_value = MagicMock(total=32 * 1024**3)
            profile = PrefetchTuning.detect_system_profile()

        assert profile.is_low_end is False
        assert profile.is_mid_range is False
        assert profile.is_high_end is True

    def test_ram_unknown_few_cpus_is_low_end(self) -> None:
        with (
            patch.object(platform_settings_module.os, "cpu_count", return_value=2),
            patch.object(
                platform_settings_module.psutil, "virtual_memory", side_effect=RuntimeError
            ),
        ):
            profile = PrefetchTuning.detect_system_profile()

        assert profile.ram_gb is None
        assert profile.is_low_end is True

    def test_ram_unknown_many_cpus_is_high_end(self) -> None:
        with (
            patch.object(platform_settings_module.os, "cpu_count", return_value=8),
            patch.object(
                platform_settings_module.psutil, "virtual_memory", side_effect=RuntimeError
            ),
        ):
            profile = PrefetchTuning.detect_system_profile()

        assert profile.ram_gb is None
        assert profile.is_high_end is True

    def test_ram_unknown_mid_cpus_is_mid_range(self) -> None:
        with (
            patch.object(platform_settings_module.os, "cpu_count", return_value=4),
            patch.object(
                platform_settings_module.psutil, "virtual_memory", side_effect=RuntimeError
            ),
        ):
            profile = PrefetchTuning.detect_system_profile()

        assert profile.ram_gb is None
        assert profile.is_mid_range is True


class TestPrefetchTuning:
    @pytest.fixture
    def tuning(self) -> PrefetchTuning:
        return PrefetchTuning(
            prefetch_min=2,
            prefetch_max_factor=1.0,
            memory_low_water_mib=200.0,
            memory_high_water_mib=400.0,
            worker_count=4,
            num_pages=20,
        )

    def test_base_max_window(self, tuning: PrefetchTuning) -> None:
        assert tuning.base_max_window == 4  # noqa: PLR2004

    def test_initial_dynamic_window_capped_by_num_pages(self) -> None:
        tuning = PrefetchTuning(
            prefetch_min=2,
            prefetch_max_factor=1.0,
            memory_low_water_mib=200.0,
            memory_high_water_mib=400.0,
            worker_count=10,
            num_pages=3,
        )
        assert tuning.get_initial_dynamic_window() == 3  # noqa: PLR2004

    def test_initial_dynamic_window_capped_by_base_max(self, tuning: PrefetchTuning) -> None:
        assert tuning.get_initial_dynamic_window() == 4  # noqa: PLR2004

    def test_dynamic_window_shrinks_under_high_memory(self, tuning: PrefetchTuning) -> None:
        with patch.object(
            platform_settings_module.tracemalloc,
            "get_traced_memory",
            return_value=(500 * 1024 * 1024, 0),  # 500 MiB > high water 400
        ):
            _mib, new_window = tuning.get_new_dynamic_window(dynamic_window=4)

        assert new_window == 3  # noqa: PLR2004

    def test_dynamic_window_grows_under_low_memory(self, tuning: PrefetchTuning) -> None:
        with patch.object(
            platform_settings_module.tracemalloc,
            "get_traced_memory",
            return_value=(100 * 1024 * 1024, 0),  # 100 MiB < low water 200
        ):
            _mib, new_window = tuning.get_new_dynamic_window(dynamic_window=2)

        assert new_window == 3  # noqa: PLR2004

    def test_dynamic_window_stays_when_between_thresholds(self, tuning: PrefetchTuning) -> None:
        with patch.object(
            platform_settings_module.tracemalloc,
            "get_traced_memory",
            return_value=(300 * 1024 * 1024, 0),  # 300 MiB between 200 and 400
        ):
            _mib, new_window = tuning.get_new_dynamic_window(dynamic_window=3)

        assert new_window == 3  # noqa: PLR2004

    def test_dynamic_window_does_not_shrink_below_min(self, tuning: PrefetchTuning) -> None:
        with patch.object(
            platform_settings_module.tracemalloc,
            "get_traced_memory",
            return_value=(500 * 1024 * 1024, 0),
        ):
            _mib, new_window = tuning.get_new_dynamic_window(dynamic_window=2)

        assert new_window == 2  # noqa: PLR2004  (prefetch_min)

    def test_dynamic_window_does_not_grow_above_base_max(self, tuning: PrefetchTuning) -> None:
        with patch.object(
            platform_settings_module.tracemalloc,
            "get_traced_memory",
            return_value=(50 * 1024 * 1024, 0),
        ):
            _mib, new_window = tuning.get_new_dynamic_window(dynamic_window=4)

        assert new_window == 4  # noqa: PLR2004  (base_max_window)
