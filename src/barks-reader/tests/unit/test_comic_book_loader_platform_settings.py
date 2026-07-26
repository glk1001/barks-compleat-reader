from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call, patch

import pytest
from barks_reader.core import comic_book_loader_platform_settings as platform_settings_module
from barks_reader.core.comic_book_loader_platform_settings import (
    PrefetchTuning,
    SystemProfile,
    autotune_worker_count,
    get_prefetch_tuning,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
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
    # Both tier boundaries are inclusive on the low side: `<= 2` cores or `<= 4` GiB is
    # low-end, `<= 4` cores or `<= 8` GiB is mid-range. Each threshold is covered on and
    # either side of the boundary, since an off-by-one here silently re-tunes prefetch
    # for a whole class of machines.
    @pytest.mark.parametrize(
        ("cpu_count", "ram_gb", "expected_tier"),
        [
            pytest.param(2, 3, "low", id="low_end_few_cpus_low_ram"),
            pytest.param(8, 4, "low", id="low_ram_boundary_is_low_end"),
            pytest.param(8, 5, "mid", id="just_above_low_ram_boundary_is_mid"),
            pytest.param(2, 64, "low", id="cpu_boundary_is_low_end_whatever_the_ram"),
            pytest.param(3, 64, "mid", id="just_above_low_cpu_boundary_is_mid"),
            pytest.param(4, 8, "mid", id="mid_range"),
            pytest.param(4, 64, "mid", id="mid_cpu_boundary_is_mid_whatever_the_ram"),
            pytest.param(5, 64, "high", id="just_above_mid_cpu_boundary_is_high"),
            pytest.param(64, 8, "mid", id="mid_ram_boundary_is_mid_range"),
            pytest.param(64, 9, "high", id="just_above_mid_ram_boundary_is_high"),
            pytest.param(16, 32, "high", id="high_end"),
            pytest.param(2, None, "low", id="ram_unknown_few_cpus_is_low_end"),
            pytest.param(3, None, "mid", id="ram_unknown_just_above_low_cpu_boundary"),
            pytest.param(8, None, "high", id="ram_unknown_many_cpus_is_high_end"),
            pytest.param(4, None, "mid", id="ram_unknown_mid_cpus_is_mid_range"),
            pytest.param(5, None, "high", id="ram_unknown_just_above_mid_cpu_boundary"),
        ],
    )
    def test_profile_tier(self, cpu_count: int, ram_gb: int | None, expected_tier: str) -> None:
        profile = _detect_profile(cpu_count, ram_gb)

        assert (profile.is_low_end, profile.is_mid_range, profile.is_high_end) == (
            expected_tier == "low",
            expected_tier == "mid",
            expected_tier == "high",
        )

    def test_profile_reports_the_detected_cpu_count_and_ram(self) -> None:
        profile = _detect_profile(cpu_count=12, ram_gb=32)

        assert profile.cpu_count == 12  # noqa: PLR2004
        # Reported in GiB (1024**3 bytes), not GB.
        assert profile.ram_gb == 32.0  # noqa: PLR2004

    def test_ram_is_none_when_the_lookup_fails(self) -> None:
        profile = _detect_profile(cpu_count=8, ram_gb=None)

        assert profile.ram_gb is None
        assert profile.cpu_count == 8  # noqa: PLR2004


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

    @pytest.mark.parametrize(
        ("worker_count", "factor", "prefetch_min", "expected"),
        [
            # The factor scales the worker count *down*, and the result is floored.
            pytest.param(8, 0.5, 1, 4, id="factor_scales_workers_down"),
            pytest.param(8, 0.75, 1, 6, id="fractional_result_is_truncated"),
            # `prefetch_min` is a floor, so a tiny factor cannot shrink past it.
            pytest.param(2, 0.5, 3, 3, id="prefetch_min_is_a_floor"),
        ],
    )
    def test_base_max_window_scales_by_the_factor(
        self, worker_count: int, factor: float, prefetch_min: int, expected: int
    ) -> None:
        tuning = PrefetchTuning(
            prefetch_min=prefetch_min,
            prefetch_max_factor=factor,
            memory_low_water_mib=200.0,
            memory_high_water_mib=400.0,
            worker_count=worker_count,
            num_pages=100,
        )

        assert tuning.base_max_window == expected

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
            # Both comparisons are strict, so sitting exactly on a watermark does
            # nothing: shrink needs `> high`, grow needs `< low`.
            pytest.param(400, 4, 4, id="exactly_at_high_water_does_not_shrink"),
            pytest.param(200, 2, 2, id="exactly_at_low_water_does_not_grow"),
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

    def test_dynamic_window_reports_current_usage_in_mib(self, tuning: PrefetchTuning) -> None:
        with patch.object(
            platform_settings_module.tracemalloc,
            "get_traced_memory",
            return_value=(300 * 1024 * 1024, 999),
        ):
            current_mib, _window = tuning.get_new_dynamic_window(dynamic_window=3)

        # Converted from the traced byte count — and read from `current`, not `peak`.
        assert current_mib == 300.0  # noqa: PLR2004


class TestTracedPeak:
    def test_returns_zero_when_tracing_is_off(self) -> None:
        with patch.object(platform_settings_module.tracemalloc, "is_tracing", return_value=False):
            assert PrefetchTuning.get_traced_peak_mib() == 0.0

    def test_returns_the_peak_in_mib_when_tracing(self) -> None:
        with (
            patch.object(platform_settings_module.tracemalloc, "is_tracing", return_value=True),
            patch.object(
                platform_settings_module.tracemalloc,
                "get_traced_memory",
                return_value=(1 * 1024 * 1024, 42 * 1024 * 1024),
            ),
        ):
            # Reads `peak`, not `current`.
            assert PrefetchTuning.get_traced_peak_mib() == 42.0  # noqa: PLR2004

    def test_start_and_stop_drive_tracemalloc(self) -> None:
        with (
            patch.object(platform_settings_module.tracemalloc, "start") as mock_start,
            patch.object(platform_settings_module.tracemalloc, "stop") as mock_stop,
        ):
            PrefetchTuning.start_mem_trace()
            PrefetchTuning.stop_mem_trace()

        mock_start.assert_called_once_with()
        mock_stop.assert_called_once_with()


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
    def test_num_pages_caps_the_initial_window(self) -> None:
        with patch.object(
            platform_settings_module, "_get_system_profile", return_value=_profile(high=True)
        ):
            tuning = get_prefetch_tuning(worker_count=8, num_pages=3)

        # `num_pages` reaches the tuning object, not just the profile params.
        assert tuning.get_initial_dynamic_window() == 3  # noqa: PLR2004

    def test_base_max_window_uses_the_profile_factor(self) -> None:
        """Low-end caps the window at half the worker count (factor 0.5)."""
        with patch.object(
            platform_settings_module, "_get_system_profile", return_value=_profile(low=True)
        ):
            tuning = get_prefetch_tuning(worker_count=8, num_pages=100)

        assert tuning.base_max_window == 4  # noqa: PLR2004

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


_SYNTHETIC_JPEG_BYTES = b"synthetic-jpeg-bytes"

# The candidate worker counts the autotuner benchmarks, before the CPU cap is applied.
_ALL_TEST_COUNTS = [1, 2, 3, 4, 6, 8, 10, 12, 16]


class _Benchmark:
    """Drives `autotune_worker_count`'s benchmark loop with scripted timings.

    Records every `ThreadPoolExecutor(max_workers=...)` and every `submit(...)`, and
    feeds `time.perf_counter` a fixed sequence so the elapsed time for each candidate
    worker count is exactly what the test asks for.
    """

    def __init__(self, timings: dict[int, float], *, start_time: float = 0.0) -> None:
        self.timings = timings
        self.max_workers: list[int | None] = []
        self.submitted: list[tuple[object, tuple[object, ...]]] = []
        self._clock: list[float] = []
        for offset, worker_count in enumerate(timings):
            base = start_time * (offset + 1)
            self._clock += [base, base + timings[worker_count]]

    def pool_factory(self, max_workers: int | None = None) -> ThreadPoolExecutor:
        self.max_workers.append(max_workers)
        recorder = self

        class _RecordingPool(ThreadPoolExecutor):
            def submit(self, fn, /, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
                recorder.submitted.append((fn, args))
                return super().submit(fn, *args, **kwargs)

        # A real executor, so a mangled `submit` call still raises through `f.result()`.
        return _RecordingPool(max_workers=max_workers)

    @contextmanager
    def patched(self, cpu_count: int) -> Iterator[SimpleNamespace]:
        """Patch out the clock, the pool and the image work for one benchmark run."""
        image = MagicMock()
        # Give each synthetic sample real, identifiable bytes so what gets decoded can
        # be told apart from an empty buffer.
        image.save.side_effect = lambda buf, **_kwargs: buf.write(_SYNTHETIC_JPEG_BYTES)

        with (
            patch.object(platform_settings_module.os, "cpu_count", return_value=cpu_count),
            patch.object(platform_settings_module.time, "perf_counter", side_effect=self._clock),
            patch.object(platform_settings_module, "ThreadPoolExecutor", self.pool_factory),
            patch.object(platform_settings_module.Image, "new", return_value=image) as new,
            patch.object(platform_settings_module.Image, "open") as opened,
        ):
            yield SimpleNamespace(image=image, new=new, opened=opened)


class TestAutotuneWorkerCount:
    def test_returns_one_for_two_or_fewer_cpus(self) -> None:
        with patch.object(platform_settings_module.os, "cpu_count", return_value=2):
            result = autotune_worker_count()

        assert result == 1

    def test_benchmarks_rather_than_short_circuiting_above_two_cpus(self) -> None:
        """Three cores is one past the skip-the-benchmark cutoff."""
        bench = _Benchmark({1: 3.0, 2: 2.0, 3: 1.0})

        with bench.patched(cpu_count=3):
            result = autotune_worker_count()

        assert bench.max_workers == [1, 2, 3]
        assert result == 3  # noqa: PLR2004

    def test_caches_result(self) -> None:
        with patch.object(platform_settings_module.os, "cpu_count", return_value=2):
            first = autotune_worker_count()
            # If caching works, the second call returns instantly without a new patch needed.
            second = autotune_worker_count()

        assert first == second == 1

    def test_picks_the_largest_worker_count_within_eight_percent_of_the_fastest(self) -> None:
        """Not simply the fastest: ties within 8% resolve to the *larger* count.

        The smoothing exists so a marginally-faster single thread doesn't win over real
        parallelism, so the tie-break direction matters as much as the threshold.
        """
        # 10 workers is 7% slower than the fastest (4), so it wins; 8 and 12 are outside
        # the band even though 12 ties with 1.
        bench = _Benchmark(
            {1: 2.0, 2: 1.5, 3: 1.2, 4: 1.0, 6: 1.05, 8: 1.2, 10: 1.07, 12: 2.0, 16: 3.0},
            # A non-zero, per-candidate start time: an elapsed time computed as
            # `end + start` instead of `end - start` then reorders the results.
            start_time=1000.0,
        )
        with bench.patched(cpu_count=16) as mocks:
            result = autotune_worker_count()

        assert result == 10  # noqa: PLR2004

        # Every candidate count was benchmarked, capped at the CPU count (16 == all).
        assert bench.max_workers == _ALL_TEST_COUNTS

        # Four synthetic JPEGs, built at full page size so the decode is representative.
        assert mocks.new.call_args_list == [call("RGB", (1800, 2600), (128, 64, 32))] * 4
        assert mocks.image.save.call_count == 4  # noqa: PLR2004
        for save_call in mocks.image.save.call_args_list:
            assert save_call.kwargs == {"format": "JPEG", "quality": 90}

        # Each sample was submitted for decoding, and decoded from its own bytes.
        assert len(bench.submitted) == 4 * len(_ALL_TEST_COUNTS)
        for _fn, args in bench.submitted:
            assert args == (_SYNTHETIC_JPEG_BYTES,)
        for open_call in mocks.opened.call_args_list:
            assert open_call.args[0].getvalue() == _SYNTHETIC_JPEG_BYTES
        mocks.opened.return_value.resize.assert_called_with(
            (900, 1300), platform_settings_module.Image.Resampling.LANCZOS
        )

    def test_a_count_exactly_on_the_eight_percent_boundary_is_included(self) -> None:
        """The band is inclusive: exactly 1.08x the fastest still counts as a tie."""
        # 6 workers is 5% slower (inside the band either way); 10 is exactly 8% slower,
        # so it only wins if the comparison is `<=` rather than `<`.
        bench = _Benchmark(
            {1: 2.0, 2: 1.5, 3: 1.2, 4: 1.0, 6: 1.05, 8: 1.2, 10: 1.08, 12: 2.0, 16: 3.0}
        )

        with bench.patched(cpu_count=16):
            result = autotune_worker_count()

        assert result == 10  # noqa: PLR2004

    def test_caps_the_candidates_at_the_cpu_count(self) -> None:
        bench = _Benchmark({1: 3.0, 2: 2.0, 3: 1.9, 4: 1.0, 6: 2.0})

        with bench.patched(cpu_count=6):
            result = autotune_worker_count()

        # 8 and above are dropped; 6 is kept (the cap is inclusive).
        assert bench.max_workers == [1, 2, 3, 4, 6]
        assert result == 4  # noqa: PLR2004

    def test_caches_the_benchmark_result(self) -> None:
        bench = _Benchmark({1: 3.0, 2: 2.0, 3: 1.0})

        with bench.patched(cpu_count=3):
            first = autotune_worker_count()
            # A second benchmark run would exhaust the scripted clock and raise.
            second = autotune_worker_count()

        assert first == second == 3  # noqa: PLR2004
        assert bench.max_workers == [1, 2, 3]

    def test_supplied_sample_images_are_read_instead_of_synthesised(self, tmp_path: Path) -> None:
        sample_a = tmp_path / "a.jpg"
        sample_b = tmp_path / "b.jpg"
        sample_a.write_bytes(b"\xff\xd8\xff\xe0sample-a")
        sample_b.write_bytes(b"\xff\xd8\xff\xe0sample-b")

        bench = _Benchmark({1: 3.0, 2: 2.0, 3: 1.0})

        with bench.patched(cpu_count=3) as mocks:
            autotune_worker_count(sample_images=[str(sample_a), str(sample_b)])

        # No synthetic images were built, and both files were decoded verbatim.
        mocks.new.assert_not_called()
        assert {args for _fn, args in bench.submitted} == {
            (sample_a.read_bytes(),),
            (sample_b.read_bytes(),),
        }
