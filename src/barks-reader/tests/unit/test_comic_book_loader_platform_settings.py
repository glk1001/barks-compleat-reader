from __future__ import annotations

import ctypes
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import comic_book_loader_platform_settings as platform_settings_module
from barks_reader.core.comic_book_loader_platform_settings import (
    MAX_WORKER_COUNT,
    PrefetchParams,
    PrefetchTuning,
    SystemProfile,
    available_memory_mib,
    get_max_worker_count,
    get_prefetch_tuning,
    process_rss_mib,
    release_freed_memory,
)


@pytest.fixture(autouse=True)
def _reset_platform_caches() -> None:
    """Reset module-level caches between tests so each test starts clean."""
    platform_settings_module._SYSTEM_PROFILE = None  # noqa: SLF001
    platform_settings_module._PREFETCH_PARAMS = None  # noqa: SLF001


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


_PARAMS = PrefetchParams(
    prefetch_min=2,
    prefetch_max_factor=1.0,
    shrink_below_mib=200.0,
    grow_above_mib=400.0,
)


def _rss(mib: float) -> MagicMock:
    """Return a `psutil.Process` whose RSS is *mib* MiB."""
    process = MagicMock()
    process.memory_info.return_value.rss = int(mib * 1024 * 1024)
    return process


def _available(mib: float) -> MagicMock:
    """Return a `psutil.virtual_memory()` result with *mib* MiB available."""
    return MagicMock(available=int(mib * 1024 * 1024))


class TestPrefetchTuning:
    @pytest.fixture
    def tuning(self) -> PrefetchTuning:
        return PrefetchTuning(_PARAMS, worker_count=4, num_pages=20)

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
        params = PrefetchParams(
            prefetch_min=prefetch_min,
            prefetch_max_factor=factor,
            shrink_below_mib=200.0,
            grow_above_mib=400.0,
        )
        tuning = PrefetchTuning(params, worker_count=worker_count, num_pages=100)

        assert tuning.base_max_window == expected

    def test_initial_dynamic_window_capped_by_num_pages(self) -> None:
        tuning = PrefetchTuning(_PARAMS, worker_count=10, num_pages=3)
        assert tuning.get_initial_dynamic_window() == 3  # noqa: PLR2004

    def test_initial_dynamic_window_capped_by_base_max(self, tuning: PrefetchTuning) -> None:
        assert tuning.get_initial_dynamic_window() == 4  # noqa: PLR2004

    # The tuning fixture shrinks below 200 MiB available and grows above 400 MiB,
    # with prefetch_min 2 and base_max_window 4.
    @pytest.mark.parametrize(
        ("available_mib", "dynamic_window", "expected_window"),
        [
            pytest.param(100, 4, 3, id="shrinks_when_the_machine_is_short"),
            pytest.param(500, 2, 3, id="grows_when_the_machine_is_comfortable"),
            pytest.param(300, 3, 3, id="stays_when_between_the_floors"),
            pytest.param(100, 2, 2, id="does_not_shrink_below_min"),
            pytest.param(900, 4, 4, id="does_not_grow_above_base_max"),
            # Both comparisons are strict, so sitting exactly on a floor does
            # nothing: shrink needs `< shrink_below`, grow needs `> grow_above`.
            pytest.param(200, 4, 4, id="exactly_at_the_shrink_floor_does_not_shrink"),
            pytest.param(400, 2, 2, id="exactly_at_the_grow_ceiling_does_not_grow"),
        ],
    )
    def test_dynamic_window(
        self,
        tuning: PrefetchTuning,
        available_mib: int,
        dynamic_window: int,
        expected_window: int,
    ) -> None:
        """The window moves on the machine's available memory, not this process's size.

        Regression: it moved on the process's own growth since the load began, and a
        full window of workers decoding pages grows it by hundreds of MiB as a matter
        of course - so every load on a big machine shrank its window to the minimum
        and took twice as long.
        """
        with (
            patch.object(
                platform_settings_module.psutil,
                "virtual_memory",
                return_value=_available(available_mib),
            ),
            # The process has grown enormously: that is not the signal.
            patch.object(platform_settings_module.psutil, "Process", return_value=_rss(9000.0)),
        ):
            _mib, new_window = tuning.get_new_dynamic_window(dynamic_window=dynamic_window)

        assert new_window == expected_window

    def test_dynamic_window_reports_the_available_memory_in_mib(
        self, tuning: PrefetchTuning
    ) -> None:
        with patch.object(
            platform_settings_module.psutil, "virtual_memory", return_value=_available(300.0)
        ):
            available_mib, _window = tuning.get_new_dynamic_window(dynamic_window=3)

        assert available_mib == 300.0  # noqa: PLR2004

    def test_dynamic_window_samples_the_growth_for_the_peak(self, tuning: PrefetchTuning) -> None:
        """The process's growth is still watched, for the load's log line."""
        with patch.object(platform_settings_module.psutil, "Process", return_value=_rss(1000.0)):
            tuning.start_memory_watch()
        with (
            patch.object(platform_settings_module.psutil, "Process", return_value=_rss(1300.0)),
            patch.object(
                platform_settings_module.psutil, "virtual_memory", return_value=_available(300.0)
            ),
        ):
            tuning.get_new_dynamic_window(dynamic_window=3)

        assert tuning.get_peak_memory_growth_mib() == 300.0  # noqa: PLR2004


class TestMemoryWatch:
    """The RSS replaced tracemalloc: the decoded pages are C buffers, which it never saw."""

    def test_growth_is_measured_from_the_watch_start(self) -> None:
        tuning = PrefetchTuning(_PARAMS, worker_count=4, num_pages=20)

        with patch.object(platform_settings_module.psutil, "Process", return_value=_rss(1200.0)):
            tuning.start_memory_watch()
        with patch.object(platform_settings_module.psutil, "Process", return_value=_rss(1250.5)):
            assert tuning.get_memory_growth_mib() == 50.5  # noqa: PLR2004

    def test_a_shrinking_process_reads_as_no_growth(self) -> None:
        """RSS can fall below the baseline (the previous comic freed): that is not pressure."""
        tuning = PrefetchTuning(_PARAMS, worker_count=4, num_pages=20)

        with patch.object(platform_settings_module.psutil, "Process", return_value=_rss(1200.0)):
            tuning.start_memory_watch()
        with patch.object(platform_settings_module.psutil, "Process", return_value=_rss(900.0)):
            assert tuning.get_memory_growth_mib() == 0.0

    def test_the_peak_is_the_largest_growth_sampled(self) -> None:
        tuning = PrefetchTuning(_PARAMS, worker_count=4, num_pages=20)

        with patch.object(platform_settings_module.psutil, "Process", return_value=_rss(1000.0)):
            tuning.start_memory_watch()
        for rss in (1100.0, 1400.0, 1200.0):
            with patch.object(platform_settings_module.psutil, "Process", return_value=_rss(rss)):
                tuning.get_memory_growth_mib()

        assert tuning.get_peak_memory_growth_mib() == 400.0  # noqa: PLR2004

    def test_a_new_watch_forgets_the_old_peak(self) -> None:
        tuning = PrefetchTuning(_PARAMS, worker_count=4, num_pages=20)

        with patch.object(platform_settings_module.psutil, "Process", return_value=_rss(1000.0)):
            tuning.start_memory_watch()
        with patch.object(platform_settings_module.psutil, "Process", return_value=_rss(1400.0)):
            tuning.get_memory_growth_mib()
            tuning.start_memory_watch()

        assert tuning.get_peak_memory_growth_mib() == 0.0

    def test_before_any_sample_the_peak_is_zero(self) -> None:
        assert (
            PrefetchTuning(_PARAMS, worker_count=4, num_pages=20).get_peak_memory_growth_mib()
            == 0.0
        )

    def test_rss_is_reported_in_mebibytes(self) -> None:
        with patch.object(platform_settings_module.psutil, "Process", return_value=_rss(150.0)):
            assert process_rss_mib() == 150.0  # noqa: PLR2004

    def test_available_memory_is_reported_in_mebibytes(self) -> None:
        with patch.object(
            platform_settings_module.psutil, "virtual_memory", return_value=_available(2048.0)
        ):
            assert available_memory_mib() == 2048.0  # noqa: PLR2004


class TestReleaseFreedMemory:
    """glibc's arenas keep what the workers freed; `malloc_trim` gives it back."""

    def test_on_linux_the_allocator_is_trimmed(self) -> None:
        libc = MagicMock()
        with (
            patch.object(platform_settings_module.sys, "platform", "linux"),
            patch.object(ctypes, "CDLL", return_value=libc) as cdll,
        ):
            release_freed_memory()

        cdll.assert_called_once_with("libc.so.6")
        libc.malloc_trim.assert_called_once_with(0)

    @pytest.mark.parametrize("platform", ["win32", "darwin"])
    def test_elsewhere_nothing_is_attempted(self, platform: str) -> None:
        with (
            patch.object(platform_settings_module.sys, "platform", platform),
            patch.object(ctypes, "CDLL") as cdll,
        ):
            release_freed_memory()

        cdll.assert_not_called()

    def test_a_libc_without_the_call_is_left_alone(self) -> None:
        """A Linux without glibc (musl has no malloc_trim) must not take the app down."""
        with (
            patch.object(platform_settings_module.sys, "platform", "linux"),
            patch.object(ctypes, "CDLL", side_effect=OSError("no libc.so.6")),
        ):
            release_freed_memory()
        libc = MagicMock(spec=[])  # no malloc_trim attribute
        with (
            patch.object(platform_settings_module.sys, "platform", "linux"),
            patch.object(ctypes, "CDLL", return_value=libc),
        ):
            release_freed_memory()


# ---------------------------------------------------------------------------
# get_prefetch_tuning — per-load tuning on process-wide, profile-derived limits
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
            "expected_shrink_below",
            "expected_grow_above",
        ),
        [
            pytest.param(
                _profile(low=True), 2, 1, 0.5, 384.0, 768.0, id="low_end_conservative_params"
            ),
            pytest.param(
                _profile(mid=True), 4, 2, 0.75, 512.0, 1024.0, id="mid_range_modest_params"
            ),
            pytest.param(
                _profile(high=True), 8, 2, 1.0, 768.0, 1536.0, id="high_end_generous_params"
            ),
        ],
    )
    def test_profile_sets_params(
        self,
        profile: SystemProfile,
        worker_count: int,
        expected_min: int,
        expected_factor: float,
        expected_shrink_below: float,
        expected_grow_above: float,
    ) -> None:
        with patch.object(platform_settings_module, "_get_system_profile", return_value=profile):
            tuning = get_prefetch_tuning(worker_count=worker_count, num_pages=10)

        assert tuning.prefetch_min == expected_min
        assert tuning.prefetch_max_factor == expected_factor
        assert tuning.shrink_below_mib == expected_shrink_below
        assert tuning.grow_above_mib == expected_grow_above

    def test_each_load_gets_its_own_window_on_the_cached_limits(self) -> None:
        """Regression: the first comic's tuning was cached and handed to every later one.

        A 2-page one-pager opened first then capped every later comic at two pages
        in flight, whatever its size and the machine's workers. The profile is read
        once; the window is built for each load's worker and page counts.
        """
        with patch.object(
            platform_settings_module, "_get_system_profile", return_value=_profile(high=True)
        ) as mock_profile:
            one_pager = get_prefetch_tuning(worker_count=2, num_pages=2)
            long_comic = get_prefetch_tuning(worker_count=16, num_pages=186)

        assert one_pager.get_initial_dynamic_window() == 2  # noqa: PLR2004
        assert long_comic.get_initial_dynamic_window() == 16  # noqa: PLR2004
        assert long_comic.base_max_window == 16  # noqa: PLR2004
        assert long_comic is not one_pager
        # The limits still come from one profile read, not one per load.
        assert mock_profile.call_count == 1
        assert (long_comic.prefetch_min, long_comic.shrink_below_mib) == (
            one_pager.prefetch_min,
            one_pager.shrink_below_mib,
        )


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
# get_max_worker_count
# ---------------------------------------------------------------------------


class TestGetMaxWorkerCount:
    """A table of the CPU count, in place of a benchmark that measured nothing.

    The benchmark decoded four samples per candidate count, so every count above
    four did the same work and its tie-break (the largest within 8%) always chose
    the biggest candidate: the CPU count, capped. This returns that without the
    second of decoding at boot.
    """

    @pytest.mark.parametrize(
        ("cpu_count", "expected"),
        [
            pytest.param(1, 1, id="one_core_is_one_worker"),
            pytest.param(2, 1, id="two_cores_is_still_one_worker"),
            pytest.param(3, 3, id="three_cores_is_a_worker_per_core"),
            pytest.param(8, 8, id="eight_cores_is_a_worker_per_core"),
            pytest.param(16, 16, id="the_cap_is_inclusive"),
            pytest.param(32, 16, id="beyond_the_cap_is_capped"),
        ],
    )
    def test_a_worker_per_core_past_two_cores_up_to_the_cap(
        self, cpu_count: int, expected: int
    ) -> None:
        with patch.object(platform_settings_module.os, "cpu_count", return_value=cpu_count):
            assert get_max_worker_count() == expected

    def test_an_unknown_cpu_count_is_one_worker(self) -> None:
        with patch.object(platform_settings_module.os, "cpu_count", return_value=None):
            assert get_max_worker_count() == 1

    def test_the_cap_is_sixteen(self) -> None:
        assert MAX_WORKER_COUNT == 16  # noqa: PLR2004
