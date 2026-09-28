"""What the app holds in memory, counted after a full collection, for the GUI leak tests.

A GUI test cannot see inside the app, and the app's resident size says little on
its own: it rises with whatever garbage the collector has not reached yet, and
the allocator keeps freed memory. So a test asks. It writes a request id to the
file named by ``MEMORY_CENSUS_FILE_ENV_VAR``, and the app runs a full garbage
collection and answers with one ``MEMORY_CENSUS`` log line: its live widgets,
textures and objects, and its resident size. What is still alive after a full
collection is what the app holds on purpose, or leaks - a test that does the
same thing again and again and sees those counts climb has found a leak. The
GUI probe sets the variable; with it unset, which is every normal run, the app
never looks.

This module is the part without Kivy: the census and the request file.
``barks_reader.ui.memory_census`` says what a widget and a texture are, and
drives it from a clock.
"""

from __future__ import annotations

import gc
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import psutil

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

MEMORY_CENSUS_FILE_ENV_VAR = "BARKS_READER_MEMORY_CENSUS_FILE"

_MIB = 1024 * 1024


@dataclass(frozen=True, slots=True)
class MemoryCensus:
    """What was alive after a full garbage collection.

    Attributes:
        widgets: Live widgets, whether on screen or not.
        textures: Live textures.
        objects: Every object the collector tracks.
        rss_mib: The process's resident size, in MiB.
        took_ms: How long the collection and the count took, in milliseconds.

    """

    widgets: int
    textures: int
    objects: int
    rss_mib: int
    took_ms: int


def take_census(
    is_widget: Callable[[object], bool], is_texture: Callable[[object], bool]
) -> MemoryCensus:
    """Collect every generation, then count what is still alive.

    Args:
        is_widget: Whether an object is a widget.
        is_texture: Whether an object is a texture.

    Returns:
        The counts, and the resident size once the garbage has gone.

    """
    start = time.perf_counter()
    gc.collect()
    live = gc.get_objects()
    widgets = sum(1 for obj in live if is_widget(obj))
    textures = sum(1 for obj in live if is_texture(obj))
    objects = len(live)
    del live
    return MemoryCensus(
        widgets=widgets,
        textures=textures,
        objects=objects,
        rss_mib=round(psutil.Process().memory_info().rss / _MIB),
        took_ms=round((time.perf_counter() - start) * 1000),
    )


def take_request(request_file: Path) -> str | None:
    """Return the request id waiting in `request_file` and remove it, or None.

    The probe writes the file whole and renames it into place, so one that is
    there holds a whole id; an empty one is left for the next look.

    Args:
        request_file: The file a test writes a request id into.

    Returns:
        The request id, or None when no request is waiting.

    """
    try:
        request = request_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not request:
        return None
    request_file.unlink(missing_ok=True)
    return request
