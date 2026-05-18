"""In-memory adapters for the view-pipeline ports.

These let tests exercise `ViewPipeline` end-to-end without Kivy, without disk
I/O, and without the global `random` module's state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_reader.core.ports import PaletteId
    from barks_reader.core.reader_colors import Color
    from barks_reader.core.view_snapshot import ViewSnapshot


# ----------------------------------------------------------------------
# Scheduler
# ----------------------------------------------------------------------


@dataclass(slots=True)
class _ScheduledInterval:
    callback: Callable[[], None]
    period_secs: float
    cancelled: bool = False


class _RecordedHandle:
    """Cancel handle for a `FakeScheduler` interval."""

    def __init__(self, scheduled: _ScheduledInterval) -> None:
        self._scheduled = scheduled

    def cancel(self) -> None:
        self._scheduled.cancelled = True


class FakeScheduler:
    """A `PeriodicScheduler` that records intervals instead of running real timers.

    Tests use `advance(secs)` to deterministically fire scheduled callbacks the
    correct number of times.
    """

    def __init__(self) -> None:
        self._intervals: list[_ScheduledInterval] = []

    @property
    def active_intervals(self) -> list[_ScheduledInterval]:
        """Return all non-cancelled intervals currently scheduled."""
        return [i for i in self._intervals if not i.cancelled]

    def schedule_interval(
        self, callback: Callable[[], None], period_secs: float
    ) -> _RecordedHandle:
        """Record the interval and return a cancellable handle."""
        scheduled = _ScheduledInterval(callback=callback, period_secs=period_secs)
        self._intervals.append(scheduled)
        return _RecordedHandle(scheduled)

    def advance(self, secs: float) -> None:
        """Advance virtual time by *secs* seconds, firing scheduled callbacks.

        Each active interval fires ``floor(secs / period)`` times.
        """
        for interval in self._intervals:
            if interval.cancelled:
                continue
            ticks = int(secs // interval.period_secs)
            for _ in range(ticks):
                interval.callback()


# ----------------------------------------------------------------------
# Color source
# ----------------------------------------------------------------------


@dataclass(slots=True)
class ScriptedColorSource:
    """A `ColorSource` that cycles through a fixed sequence per palette.

    If a palette has no scripted sequence, `next_color` returns ``default``.
    """

    palettes: dict[PaletteId, list[Color]] = field(default_factory=dict)
    default: Color = (1.0, 1.0, 1.0, 1.0)
    _indices: dict[PaletteId, int] = field(default_factory=dict, init=False, repr=False)

    def next_color(self, palette: PaletteId) -> Color:
        """Return the next color in the palette's sequence, cycling on wrap."""
        sequence = self.palettes.get(palette)
        if not sequence:
            return self.default
        index = self._indices.get(palette, 0)
        self._indices[palette] = index + 1
        return sequence[index % len(sequence)]


# ----------------------------------------------------------------------
# Snapshot sink
# ----------------------------------------------------------------------


@dataclass(slots=True)
class RecordingSink:
    """A `SnapshotSink` that records every `apply()` call to a list."""

    applied: list[ViewSnapshot] = field(default_factory=list)

    def apply(self, snapshot: ViewSnapshot) -> None:
        """Append *snapshot* to the `applied` list."""
        self.applied.append(snapshot)
