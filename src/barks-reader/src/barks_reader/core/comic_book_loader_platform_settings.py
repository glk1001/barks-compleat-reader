from __future__ import annotations

import os
from dataclasses import dataclass

import psutil
from loguru import logger

# The most page-decode workers any machine gets: beyond this the archive reads and
# the window's memory, not the cores, bound a load.
MAX_WORKER_COUNT = 16


@dataclass(frozen=True, slots=True)
class SystemProfile:
    cpu_count: int
    ram_gb: float | None
    is_low_end: bool
    is_mid_range: bool
    is_high_end: bool


@dataclass(frozen=True, slots=True)
class PrefetchParams:
    """The profile-derived prefetch limits, the same for every comic this process loads."""

    prefetch_min: int
    prefetch_max_factor: float
    memory_low_water_mib: float
    memory_high_water_mib: float


def process_rss_mib() -> float:
    """Return this process's current resident set size (RSS), in MiB."""
    return psutil.Process().memory_info().rss / (1024 * 1024)


class PrefetchTuning:
    """One comic load's prefetch window: its bounds, and the memory signal that moves it.

    The window shrinks when the process has grown past the high-water mark since the
    load began, and grows back below the low one. Growth is of the resident set, which
    holds the decoded pages (C buffers no Python tracer sees), from a baseline
    :meth:`start_memory_watch` takes.
    """

    def __init__(self, params: PrefetchParams, worker_count: int, num_pages: int) -> None:
        self.prefetch_min: int = params.prefetch_min
        self.prefetch_max_factor: float = params.prefetch_max_factor
        self.memory_low_water_mib: float = params.memory_low_water_mib
        self.memory_high_water_mib: float = params.memory_high_water_mib
        self._num_pages = num_pages
        self.base_max_window = max(self.prefetch_min, int(worker_count * self.prefetch_max_factor))
        self._rss_at_start_mib = 0.0
        self._peak_growth_mib = 0.0

    def start_memory_watch(self) -> None:
        """Take the RSS baseline the load's memory growth is measured from."""
        self._rss_at_start_mib = process_rss_mib()
        self._peak_growth_mib = 0.0

    def get_memory_growth_mib(self) -> float:
        """Return how far the RSS has grown since the watch started (never negative)."""
        growth = max(0.0, process_rss_mib() - self._rss_at_start_mib)
        self._peak_growth_mib = max(self._peak_growth_mib, growth)
        return growth

    def get_peak_memory_growth_mib(self) -> float:
        """Return the largest growth any :meth:`get_memory_growth_mib` call has seen."""
        return self._peak_growth_mib

    def get_initial_dynamic_window(self) -> int:
        return min(self.base_max_window, self._num_pages)

    def get_new_dynamic_window(self, dynamic_window: int) -> tuple[float, int]:
        current_mib = self.get_memory_growth_mib()

        # Adjust window based on memory usage.
        if current_mib > self.memory_high_water_mib:
            # Under memory pressure - shrink window a bit.
            new_window = max(self.prefetch_min, dynamic_window - 1)
            if new_window != dynamic_window:
                logger.debug(
                    f"[prefetch] High memory {current_mib:.1f}-"
                    f"shrinking window {dynamic_window} -> {new_window}"
                )
            dynamic_window = new_window
        elif current_mib < self.memory_low_water_mib:
            # Memory comfortable - grow window up to base_max_window.
            new_window = min(self.base_max_window, dynamic_window + 1)
            if new_window != dynamic_window:
                logger.debug(
                    f"[prefetch] Low memory {current_mib:.1f}-"
                    f"growing window {dynamic_window} -> {new_window}"
                )
            dynamic_window = new_window

        return current_mib, dynamic_window

    @staticmethod
    def detect_system_profile() -> SystemProfile:
        """Roughly classify the machine as low / mid / high end."""
        cpu_count = os.cpu_count() or 1

        # noinspection PyBroadException
        try:
            vmem = psutil.virtual_memory()
            ram_gb = vmem.total / (1024**3)
        except Exception:  # noqa: BLE001
            ram_gb = None

        # Conservative defaults if RAM unknown.
        if ram_gb is None:
            if cpu_count <= 2:  # noqa: PLR2004
                is_low_end = True
                is_mid_range = False
                is_high_end = False
            elif cpu_count <= 4:  # noqa: PLR2004
                is_low_end = False
                is_mid_range = True
                is_high_end = False
            else:
                is_low_end = False
                is_mid_range = False
                is_high_end = True
        # Simple classification based on both cores and RAM.
        elif cpu_count <= 2 or ram_gb <= 4:  # noqa: PLR2004
            is_low_end = True
            is_mid_range = False
            is_high_end = False
        elif cpu_count <= 4 or ram_gb <= 8:  # noqa: PLR2004
            is_low_end = False
            is_mid_range = True
            is_high_end = False
        else:
            is_low_end = False
            is_mid_range = False
            is_high_end = True

        return SystemProfile(
            cpu_count=cpu_count,
            ram_gb=ram_gb,
            is_low_end=is_low_end,
            is_mid_range=is_mid_range,
            is_high_end=is_high_end,
        )


# The profile and the limits drawn from it are read once per process; the tuning
# built from them is per load, as the worker and page counts are.
_SYSTEM_PROFILE: SystemProfile | None = None
_PREFETCH_PARAMS: PrefetchParams | None = None


def get_prefetch_tuning(worker_count: int, num_pages: int) -> PrefetchTuning:
    """Return the prefetch tuning for a load of *num_pages* pages on *worker_count* workers.

    Args:
        worker_count: The workers this load's pool has: the window's ceiling scales with it.
        num_pages: The pages the load has: the initial window never exceeds it.

    Returns:
        A fresh :class:`PrefetchTuning` for this load, on the process-wide limits.

    """
    return PrefetchTuning(_get_prefetch_params(), worker_count=worker_count, num_pages=num_pages)


def _get_prefetch_params() -> PrefetchParams:
    global _PREFETCH_PARAMS  # noqa: PLW0603
    if _PREFETCH_PARAMS is not None:
        return _PREFETCH_PARAMS

    profile = _get_system_profile()

    if profile.is_low_end:
        # Old laptops / tiny RAM:
        # - smaller window
        # - tighter memory thresholds
        params = PrefetchParams(
            prefetch_min=1,
            prefetch_max_factor=0.5,
            memory_low_water_mib=150.0,
            memory_high_water_mib=300.0,
        )
    elif profile.is_mid_range:
        # Modest PCs / mid-laptops:
        params = PrefetchParams(
            prefetch_min=2,
            prefetch_max_factor=0.75,
            memory_low_water_mib=200.0,
            memory_high_water_mib=350.0,
        )
    else:
        # High-end desktop / modern Ryzen / big RAM:
        params = PrefetchParams(
            prefetch_min=2,
            prefetch_max_factor=1.0,
            memory_low_water_mib=250.0,
            memory_high_water_mib=450.0,
        )

    _PREFETCH_PARAMS = params

    logger.debug(
        f"Prefetch tuning: min={params.prefetch_min}, max_factor={params.prefetch_max_factor},"
        f" mem_low={params.memory_low_water_mib} MiB, mem_high={params.memory_high_water_mib} MiB."
    )

    return params


def _get_system_profile() -> SystemProfile:
    global _SYSTEM_PROFILE  # noqa: PLW0603
    profile = _SYSTEM_PROFILE
    if profile is None:
        profile = PrefetchTuning.detect_system_profile()
        _SYSTEM_PROFILE = profile
    logger.debug(
        "System profile detected: cpu_count={cpu}, ram_gb={ram}, "
        "low={low}, mid={mid}, high={high}".format(
            cpu=profile.cpu_count,
            ram=f"{profile.ram_gb:.1f}" if profile.ram_gb else "unknown",
            low=profile.is_low_end,
            mid=profile.is_mid_range,
            high=profile.is_high_end,
        )
    )
    return profile


def get_max_worker_count() -> int:
    """Return the page-decode worker count for this machine.

    One worker on two cores or fewer, where a pool would only add switching; otherwise
    a worker per core, capped at :data:`MAX_WORKER_COUNT`. This replaces a boot-time
    benchmark that decoded four sample pages per candidate count: with only four
    tasks, every count above four did the same work, and its tie-break always chose
    the largest, so it measured nothing and cost a second at startup.

    Returns:
        The worker count.

    """
    cpu_count = os.cpu_count() or 1
    if cpu_count <= 2:  # noqa: PLR2004
        return 1
    return min(cpu_count, MAX_WORKER_COUNT)
