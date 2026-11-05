from __future__ import annotations

import ctypes
import os
import sys
from dataclasses import dataclass
from enum import Enum, auto
from functools import cache

import psutil
from loguru import logger

# The most page-decode workers any machine gets: beyond this the archive reads and
# the window's memory, not the cores, bound a load.
MAX_WORKER_COUNT = 16


class SystemTier(Enum):
    """Roughly how much the machine can take."""

    LOW = auto()
    MID = auto()
    HIGH = auto()


@dataclass(frozen=True, slots=True)
class SystemProfile:
    cpu_count: int
    ram_gb: float | None
    tier: SystemTier


@dataclass(frozen=True, slots=True)
class PrefetchParams:
    """The profile-derived prefetch limits, the same for every comic this process loads.

    The two memory figures are floors on the machine's *available* memory: the window
    shrinks while less than ``shrink_below_mib`` is left, and grows back only once more
    than ``grow_above_mib`` is. The gap between them keeps it from flapping.
    """

    prefetch_min: int
    prefetch_max_factor: float
    shrink_below_mib: float
    grow_above_mib: float


def process_rss_mib() -> float:
    """Return this process's current resident set size (RSS), in MiB."""
    return psutil.Process().memory_info().rss / (1024 * 1024)


def available_memory_mib() -> float:
    """Return the memory the machine can still give out without swapping, in MiB."""
    return psutil.virtual_memory().available / (1024 * 1024)


def release_freed_memory() -> None:
    """Hand the allocator's freed memory back to the system, where the allocator can.

    glibc keeps what a thread frees in that thread's arena, so a load's page decode
    buffers - some 45 MiB per worker, freed as each page is encoded - stay in the
    process's resident set long after, hundreds of MiB counted against the app for
    nothing. ``malloc_trim`` returns what is returnable in a millisecond or two. A
    no-op where there is no glibc (Windows, macOS, musl).
    """
    if sys.platform != "linux":
        return
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):
        # Not glibc: nothing to trim, and nothing lost.
        return


class PrefetchTuning:
    """One comic load's prefetch window: its bounds, and the memory signal that moves it.

    Pressure is read where it exists, in the machine's available memory: the window
    shrinks while that is under the profile's floor and grows back above its ceiling.
    The process's own growth is no measure of it - a full window of decoding workers
    legitimately holds hundreds of MiB of page buffers - so that is only watched, from
    the baseline :meth:`start_memory_watch` takes, for the load's log line.
    """

    def __init__(self, params: PrefetchParams, worker_count: int, num_pages: int) -> None:
        self.prefetch_min: int = params.prefetch_min
        self.prefetch_max_factor: float = params.prefetch_max_factor
        self.shrink_below_mib: float = params.shrink_below_mib
        self.grow_above_mib: float = params.grow_above_mib
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
        """Return the machine's available memory (MiB) and the window it allows.

        One step down while the available memory is under the floor, one step up
        while it is over the ceiling, nothing in between; and the process's growth
        is sampled for the peak the load logs.
        """
        self.get_memory_growth_mib()
        available_mib = available_memory_mib()

        if available_mib < self.shrink_below_mib:
            # The machine is running short - shrink the window a step.
            new_window = max(self.prefetch_min, dynamic_window - 1)
            if new_window != dynamic_window:
                logger.debug(
                    f"[prefetch] Only {available_mib:.0f} MiB available -"
                    f" shrinking window {dynamic_window} -> {new_window}"
                )
            dynamic_window = new_window
        elif available_mib > self.grow_above_mib:
            # Memory comfortable - grow window up to base_max_window.
            new_window = min(self.base_max_window, dynamic_window + 1)
            if new_window != dynamic_window:
                logger.debug(
                    f"[prefetch] {available_mib:.0f} MiB available -"
                    f" growing window {dynamic_window} -> {new_window}"
                )
            dynamic_window = new_window

        return available_mib, dynamic_window

    @staticmethod
    def detect_system_profile() -> SystemProfile:
        """Roughly classify the machine as low / mid / high end."""
        cpu_count = os.process_cpu_count() or 1

        # noinspection PyBroadException
        try:
            vmem = psutil.virtual_memory()
            ram_gb = vmem.total / (1024**3)
        except Exception:  # noqa: BLE001
            ram_gb = None

        # Classified on both cores and RAM. Unknown RAM is not assumed to be plenty: the
        # cores can still make the machine low-end, but it stops at mid-range.
        if cpu_count <= 2 or (ram_gb is not None and ram_gb <= 4):  # noqa: PLR2004
            tier = SystemTier.LOW
        elif cpu_count <= 4 or ram_gb is None or ram_gb <= 8:  # noqa: PLR2004
            tier = SystemTier.MID
        else:
            tier = SystemTier.HIGH

        return SystemProfile(cpu_count=cpu_count, ram_gb=ram_gb, tier=tier)


# The floors are on the machine's available memory. A worker decoding a page holds
# some 45 MiB (the full-size decode and its resize), so they sit a window's worth
# above where swapping would start, lower where the window is smaller anyway.
_PARAMS_BY_TIER = {
    # Old laptops / tiny RAM: a smaller window, backing off sooner.
    SystemTier.LOW: PrefetchParams(
        prefetch_min=1,
        prefetch_max_factor=0.5,
        shrink_below_mib=384.0,
        grow_above_mib=768.0,
    ),
    # Modest PCs / mid-laptops:
    SystemTier.MID: PrefetchParams(
        prefetch_min=2,
        prefetch_max_factor=0.75,
        shrink_below_mib=512.0,
        grow_above_mib=1024.0,
    ),
    # High-end desktop / modern Ryzen / big RAM:
    SystemTier.HIGH: PrefetchParams(
        prefetch_min=2,
        prefetch_max_factor=1.0,
        shrink_below_mib=768.0,
        grow_above_mib=1536.0,
    ),
}


def get_prefetch_tuning(worker_count: int, num_pages: int) -> PrefetchTuning:
    """Return the prefetch tuning for a load of *num_pages* pages on *worker_count* workers.

    Args:
        worker_count: The workers this load's pool has: the window's ceiling scales with it.
        num_pages: The pages the load has: the initial window never exceeds it.

    Returns:
        A fresh :class:`PrefetchTuning` for this load, on the process-wide limits.

    """
    return PrefetchTuning(_get_prefetch_params(), worker_count=worker_count, num_pages=num_pages)


@cache
def _get_prefetch_params() -> PrefetchParams:
    """Return the machine's limits: read once per process, unlike each load's tuning."""
    profile = PrefetchTuning.detect_system_profile()
    ram = f"{profile.ram_gb:.1f}" if profile.ram_gb else "unknown"
    logger.debug(
        f"System profile detected: cpu_count={profile.cpu_count}, ram_gb={ram},"
        f" tier={profile.tier.name}."
    )

    params = _PARAMS_BY_TIER[profile.tier]
    logger.debug(
        f"Prefetch tuning: min={params.prefetch_min}, max_factor={params.prefetch_max_factor},"
        f" shrink below {params.shrink_below_mib:.0f} MiB available,"
        f" grow above {params.grow_above_mib:.0f} MiB."
    )

    return params


def get_max_worker_count() -> int:
    """Return the page-decode worker count for this machine.

    The cores are those this process may use, which an affinity mask or container can limit.
    One worker on two cores or fewer, where a pool would only add switching; otherwise
    a worker per core, capped at :data:`MAX_WORKER_COUNT`. This replaces a boot-time
    benchmark that decoded four sample pages per candidate count: with only four
    tasks, every count above four did the same work, and its tie-break always chose
    the largest, so it measured nothing and cost a second at startup.

    Returns:
        The worker count.

    """
    cpu_count = os.process_cpu_count() or 1
    if cpu_count <= 2:  # noqa: PLR2004
        return 1
    return min(cpu_count, MAX_WORKER_COUNT)
