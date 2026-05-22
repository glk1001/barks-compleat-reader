from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import comic_book_loader_platform_settings as platform_settings_module
from barks_reader.core.comic_book_loader_platform_settings import (
    PrefetchTuning,
    SystemProfile,
    autotune_worker_count,
    get_prefetch_tuning,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _reset_platform_caches() -> None:
    """Reset module-level caches between tests so each test starts clean."""
    platform_settings_module._SYSTEM_PROFILE = None  # noqa: SLF001
    platform_settings_module._PREFETCH_TUNING = None  # noqa: SLF001
    platform_settings_module._AUTO_TUNED_THREAD_COUNT = None  # noqa: SLF001


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


# ---------------------------------------------------------------------------
# get_prefetch_tuning — caching + 3-way profile branch
# ---------------------------------------------------------------------------


def _profile(*, low: bool = False, mid: bool = False, high: bool = False) -> SystemProfile:
    return SystemProfile(
        cpu_count=4,
        ram_gb=8.0,
        is_low_end=low,
        is_mid_range=mid,
        is_high_end=high,
    )


class TestGetPrefetchTuning:
    def test_low_end_profile_sets_conservative_params(self) -> None:
        with patch.object(
            platform_settings_module, "_get_system_profile", return_value=_profile(low=True)
        ):
            tuning = get_prefetch_tuning(worker_count=2, num_pages=10)

        assert tuning.prefetch_min == 1
        assert tuning.prefetch_max_factor == 0.5  # noqa: PLR2004
        assert tuning.memory_low_water_mib == 150.0  # noqa: PLR2004
        assert tuning.memory_high_water_mib == 300.0  # noqa: PLR2004

    def test_mid_range_profile_sets_modest_params(self) -> None:
        with patch.object(
            platform_settings_module, "_get_system_profile", return_value=_profile(mid=True)
        ):
            tuning = get_prefetch_tuning(worker_count=4, num_pages=10)

        assert tuning.prefetch_min == 2  # noqa: PLR2004
        assert tuning.prefetch_max_factor == 0.75  # noqa: PLR2004
        assert tuning.memory_low_water_mib == 200.0  # noqa: PLR2004
        assert tuning.memory_high_water_mib == 350.0  # noqa: PLR2004

    def test_high_end_profile_sets_generous_params(self) -> None:
        with patch.object(
            platform_settings_module, "_get_system_profile", return_value=_profile(high=True)
        ):
            tuning = get_prefetch_tuning(worker_count=8, num_pages=10)

        assert tuning.prefetch_min == 2  # noqa: PLR2004
        assert tuning.prefetch_max_factor == 1.0
        assert tuning.memory_low_water_mib == 250.0  # noqa: PLR2004
        assert tuning.memory_high_water_mib == 450.0  # noqa: PLR2004

    def test_caches_result_across_calls(self) -> None:
        with patch.object(
            platform_settings_module, "_get_system_profile", return_value=_profile(high=True)
        ) as mock_profile:
            first = get_prefetch_tuning(worker_count=4, num_pages=10)
            second = get_prefetch_tuning(worker_count=99, num_pages=999)

        assert first is second
        # Profile was queried exactly once (cache prevented the second invocation).
        assert mock_profile.call_count == 1


# ---------------------------------------------------------------------------
# _get_system_profile — caching
# ---------------------------------------------------------------------------


class TestGetSystemProfile:
    def test_caches_and_returns_same_instance(self) -> None:
        with patch.object(
            PrefetchTuning, "detect_system_profile", return_value=_profile(mid=True)
        ) as mock_detect:
            first = platform_settings_module._get_system_profile()  # noqa: SLF001
            second = platform_settings_module._get_system_profile()  # noqa: SLF001

        assert first is second
        mock_detect.assert_called_once()


# ---------------------------------------------------------------------------
# autotune_worker_count
# ---------------------------------------------------------------------------


class TestAutotuneWorkerCount:
    def test_returns_one_for_two_or_fewer_cpus(self) -> None:
        with patch.object(platform_settings_module.os, "cpu_count", return_value=2):
            result = autotune_worker_count()

        assert result == 1

    def test_caches_result(self) -> None:
        with patch.object(platform_settings_module.os, "cpu_count", return_value=2):
            first = autotune_worker_count()
            # If caching works, the second call returns instantly without a new patch needed.
            second = autotune_worker_count()

        assert first == second == 1

    def test_with_sample_images_runs_benchmark(self, tmp_path: Path) -> None:
        """Multi-CPU benchmark path: feed a real (tiny) JPEG sample and stub the heavy loops."""
        # A real (tiny) JPEG file so the `p.read_bytes()` path executes.
        sample = tmp_path / "sample.jpg"
        sample.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")

        from typing import Self  # noqa: PLC0415

        class _FakePool:
            def __init__(self, *_args, **_kwargs) -> None:  # noqa: ANN002, ANN003
                pass

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_exc: object) -> None:
                return None

            def submit(self, _fn, *_args, **_kwargs) -> MagicMock:  # noqa: ANN001, ANN002, ANN003
                future = MagicMock()
                future.result.return_value = None
                return future

        with (
            patch.object(platform_settings_module.os, "cpu_count", return_value=4),
            patch.object(platform_settings_module, "ThreadPoolExecutor", _FakePool),
            patch.object(platform_settings_module.Image, "open") as mock_open,
        ):
            mock_open.return_value.load.return_value = None
            mock_open.return_value.resize.return_value = MagicMock()
            result = autotune_worker_count(sample_images=[str(sample)])

        # The function picks one of the candidate worker counts (capped at cpu_count=4).
        assert result in {1, 2, 3, 4}
