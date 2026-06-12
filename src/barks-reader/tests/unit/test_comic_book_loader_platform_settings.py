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


def _detect_profile(cpu_count: int, ram_gb: int | None) -> SystemProfile:
    """Run detect_system_profile with patched cpu_count and RAM (None = RAM lookup fails)."""
    vm_patch = (
        patch.object(platform_settings_module.psutil, "virtual_memory", side_effect=RuntimeError)
        if ram_gb is None
        else patch.object(
            platform_settings_module.psutil,
            "virtual_memory",
            return_value=MagicMock(total=ram_gb * 1024**3),
        )
    )
    with patch.object(platform_settings_module.os, "cpu_count", return_value=cpu_count), vm_patch:
        return PrefetchTuning.detect_system_profile()


class TestSystemProfile:
    @pytest.mark.parametrize(
        ("cpu_count", "ram_gb", "expected_tier"),
        [
            pytest.param(2, 3, "low", id="low_end_few_cpus_low_ram"),
            pytest.param(8, 4, "low", id="low_end_many_cpus_but_low_ram"),
            pytest.param(4, 8, "mid", id="mid_range"),
            pytest.param(16, 32, "high", id="high_end"),
            pytest.param(2, None, "low", id="ram_unknown_few_cpus_is_low_end"),
            pytest.param(8, None, "high", id="ram_unknown_many_cpus_is_high_end"),
            pytest.param(4, None, "mid", id="ram_unknown_mid_cpus_is_mid_range"),
        ],
    )
    def test_profile_tier(self, cpu_count: int, ram_gb: int | None, expected_tier: str) -> None:
        profile = _detect_profile(cpu_count, ram_gb)

        if ram_gb is None:
            assert profile.ram_gb is None
        assert (profile.is_low_end, profile.is_mid_range, profile.is_high_end) == (
            expected_tier == "low",
            expected_tier == "mid",
            expected_tier == "high",
        )


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

    # The tuning fixture has low water 200 MiB, high water 400 MiB,
    # prefetch_min 2, and base_max_window 4.
    @pytest.mark.parametrize(
        ("traced_mib", "dynamic_window", "expected_window"),
        [
            pytest.param(500, 4, 3, id="shrinks_under_high_memory"),
            pytest.param(100, 2, 3, id="grows_under_low_memory"),
            pytest.param(300, 3, 3, id="stays_when_between_thresholds"),
            pytest.param(500, 2, 2, id="does_not_shrink_below_min"),
            pytest.param(50, 4, 4, id="does_not_grow_above_base_max"),
        ],
    )
    def test_dynamic_window(
        self,
        tuning: PrefetchTuning,
        traced_mib: int,
        dynamic_window: int,
        expected_window: int,
    ) -> None:
        with patch.object(
            platform_settings_module.tracemalloc,
            "get_traced_memory",
            return_value=(traced_mib * 1024 * 1024, 0),
        ):
            _mib, new_window = tuning.get_new_dynamic_window(dynamic_window=dynamic_window)

        assert new_window == expected_window


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
    @pytest.mark.parametrize(
        (
            "profile",
            "worker_count",
            "expected_min",
            "expected_factor",
            "expected_low",
            "expected_high",
        ),
        [
            pytest.param(
                _profile(low=True), 2, 1, 0.5, 150.0, 300.0, id="low_end_conservative_params"
            ),
            pytest.param(
                _profile(mid=True), 4, 2, 0.75, 200.0, 350.0, id="mid_range_modest_params"
            ),
            pytest.param(
                _profile(high=True), 8, 2, 1.0, 250.0, 450.0, id="high_end_generous_params"
            ),
        ],
    )
    def test_profile_sets_params(
        self,
        profile: SystemProfile,
        worker_count: int,
        expected_min: int,
        expected_factor: float,
        expected_low: float,
        expected_high: float,
    ) -> None:
        with patch.object(platform_settings_module, "_get_system_profile", return_value=profile):
            tuning = get_prefetch_tuning(worker_count=worker_count, num_pages=10)

        assert tuning.prefetch_min == expected_min
        assert tuning.prefetch_max_factor == expected_factor
        assert tuning.memory_low_water_mib == expected_low
        assert tuning.memory_high_water_mib == expected_high

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
