from __future__ import annotations

import io
import os
import threading
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import psutil
from loguru import logger
from PIL import Image


@dataclass(frozen=True, slots=True)
class SystemProfile:
    cpu_count: int
    ram_gb: float | None
    is_low_end: bool
    is_mid_range: bool
    is_high_end: bool


class PrefetchTuning:
    def __init__(
        self,
        prefetch_min: int,
        prefetch_max_factor: float,
        memory_low_water_mib: float,
        memory_high_water_mib: float,
        worker_count: int,
        num_pages: int,
    ) -> None:
        self.prefetch_min: int = prefetch_min
        self.prefetch_max_factor: float = prefetch_max_factor
        self.memory_low_water_mib: float = memory_low_water_mib
        self.memory_high_water_mib: float = memory_high_water_mib
        self._worker_count = worker_count
        self._num_pages = num_pages
        self.base_max_window = max(self.prefetch_min, int(worker_count * self.prefetch_max_factor))

    @staticmethod
    def start_mem_trace() -> None:
        tracemalloc.start()

    @staticmethod
    def stop_mem_trace() -> None:
        tracemalloc.stop()

    def get_initial_dynamic_window(self) -> int:
        return min(self.base_max_window, self._num_pages)

    def get_new_dynamic_window(self, dynamic_window: int) -> tuple[float, int]:
        # Read memory usage.
        current_mem, _peak_mem = tracemalloc.get_traced_memory()
        current_mib = current_mem / (1024 * 1024)

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


# Cache profile + tuning so we don't recompute every time.
_SYSTEM_PROFILE: SystemProfile | None = None
_PREFETCH_TUNING: PrefetchTuning | None = None


def get_prefetch_tuning(worker_count: int, num_pages: int) -> PrefetchTuning:
    """Return tuning parameters based on system profile."""
    global _PREFETCH_TUNING  # noqa: PLW0603
    if _PREFETCH_TUNING is not None:
        return _PREFETCH_TUNING

    profile = _get_system_profile()

    if profile.is_low_end:
        # Old laptops / tiny RAM:
        # - smaller window
        # - tighter memory thresholds
        prefetch_min = 1
        prefetch_max_factor = 0.5
        mem_low = 150.0
        mem_high = 300.0
    elif profile.is_mid_range:
        # Modest PCs / mid laptops:
        prefetch_min = 2
        prefetch_max_factor = 0.75
        mem_low = 200.0
        mem_high = 350.0
    else:
        # High-end desktop / modern Ryzen / big RAM:
        prefetch_min = 2
        prefetch_max_factor = 1.0
        mem_low = 250.0
        mem_high = 450.0

    _PREFETCH_TUNING = PrefetchTuning(
        prefetch_min=prefetch_min,
        prefetch_max_factor=prefetch_max_factor,
        memory_low_water_mib=mem_low,
        memory_high_water_mib=mem_high,
        worker_count=worker_count,
        num_pages=num_pages,
    )
    _PREFETCH_TUNING.base_max_window = max(prefetch_min, int(worker_count * prefetch_max_factor))

    logger.debug(
        f"Prefetch tuning: min={prefetch_min}, max_factor={prefetch_max_factor},"
        f" mem_low={mem_low} MiB, mem_high={mem_high} MiB."
    )

    return _PREFETCH_TUNING


def _get_system_profile() -> SystemProfile:
    global _SYSTEM_PROFILE  # noqa: PLW0603
    if _SYSTEM_PROFILE is None:
        _SYSTEM_PROFILE = PrefetchTuning.detect_system_profile()
        logger.debug(
            "System profile detected: cpu_count={cpu}, ram_gb={ram}, "
            "low={low}, mid={mid}, high={high}".format(
                cpu=_SYSTEM_PROFILE.cpu_count,
                ram=f"{_SYSTEM_PROFILE.ram_gb:.1f}" if _SYSTEM_PROFILE.ram_gb else "unknown",
                low=_SYSTEM_PROFILE.is_low_end,
                mid=_SYSTEM_PROFILE.is_mid_range,
                high=_SYSTEM_PROFILE.is_high_end,
            )
        )
    return _SYSTEM_PROFILE


# We store the result so the autotuner only runs once per process.
_AUTO_TUNED_THREAD_COUNT = None
_AUTOTUNE_LOCK = threading.Lock()


def autotune_worker_count(sample_images: list[str] | None = None) -> int:  # noqa: C901
    """Automatically determine the optimal number of worker threads for ZIP + JPEG decode workloads.

    sample_images: optional list of paths (inside ZIP or filesystem)
                   to use as test samples.
                   If None, it generates synthetic JPEG bytes.

    Returns: integer worker count.
    """
    global _AUTO_TUNED_THREAD_COUNT  # noqa: PLW0603

    with _AUTOTUNE_LOCK:
        if _AUTO_TUNED_THREAD_COUNT is not None:
            return _AUTO_TUNED_THREAD_COUNT

        cpu_count = os.cpu_count() or 1

        # If 1-2 CPUs → don't bother benchmarking.
        if cpu_count <= 2:  # noqa: PLR2004
            _AUTO_TUNED_THREAD_COUNT = 1
            return 1

        logger.debug("[autotune] Starting thread count autotune...")

        # ----------------------------------------------------------
        # Step 1: obtain samples to decode
        # ----------------------------------------------------------

        if sample_images:
            samples = []
            for path in sample_images:
                p = Path(path)
                samples.append(p.read_bytes())
        else:
            # Create synthetic JPEGs in memory (fast + reliable)
            samples = []

            for _ in range(4):
                image = Image.new("RGB", (1800, 2600), (128, 64, 32))
                buf = io.BytesIO()
                image.save(buf, format="JPEG", quality=90)
                samples.append(buf.getvalue())

        # ----------------------------------------------------------
        # Step 2: test performance for various worker counts
        # ----------------------------------------------------------

        # Try these worker counts (cap at CPU count).
        test_counts = [wc for wc in [1, 2, 3, 4, 6, 8, 10, 12, 16] if wc <= cpu_count]

        times = {}

        for wc in test_counts:
            t0 = time.perf_counter()

            def task(data) -> None:  # noqa: ANN001
                img = Image.open(io.BytesIO(data))
                img.load()
                # noinspection PyUnusedLocal
                img = img.resize((900, 1300), Image.Resampling.LANCZOS)

            with ThreadPoolExecutor(max_workers=wc) as tp:
                futures = [tp.submit(task, s) for s in samples]
                for f in futures:
                    f.result()  # ensure completion

            dt = time.perf_counter() - t0
            times[wc] = dt
            logger.debug(f"[autotune] {wc} threads took {dt:.4f} sec.")

        # ----------------------------------------------------------
        # Step 3: pick the best-performing worker count.
        # ----------------------------------------------------------

        best_wc = min(times, key=lambda wc: times[wc])
        best_time = times[best_wc]

        # Some safety: don't return something silly like 1,
        # if the difference is tiny. Allow slight smoothing.
        for wc in sorted(times):
            if times[wc] <= best_time * 1.08:  # within 8 percent of fastest
                best_wc = wc

        logger.debug(f"[autotune] Best worker count selected: {best_wc}.")

        _AUTO_TUNED_THREAD_COUNT = best_wc
        return best_wc
