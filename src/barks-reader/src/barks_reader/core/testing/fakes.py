"""In-memory adapters for the platform-service ports.

These let tests exercise core modules end-to-end without Kivy, without disk
I/O, and without the global `random` module's state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo

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


@dataclass(slots=True)
class _ScheduledOneShot:
    callback: Callable[[], None]
    timeout_secs: float
    due_at: float
    fired: bool = False
    cancelled: bool = False


class _RecordedHandle:
    """Cancel handle for a `FakeScheduler` interval or one-shot."""

    def __init__(self, scheduled: _ScheduledInterval | _ScheduledOneShot) -> None:
        self._scheduled = scheduled

    def cancel(self) -> None:
        self._scheduled.cancelled = True


class FakeScheduler:
    """A `Scheduler` that records what is scheduled and fires it on `advance(secs)`.

    Tests use `advance(secs)` to deterministically fire interval callbacks the
    correct number of times, and the one-shots whose delay has elapsed. A one-shot
    with no delay (`schedule_once(cb)`) runs inline on the calling thread at once —
    matching the synchronous-null behavior needed by worker-thread → UI-thread
    bridges in `comic_book_loader` and `panel_image_loader`. ``one_shots`` lists
    every `schedule_once` call as (callback, timeout_secs), oldest first, so a test
    can assert the delay a caller asked for.
    """

    def __init__(self) -> None:
        self._intervals: list[_ScheduledInterval] = []
        self._one_shots: list[_ScheduledOneShot] = []
        self._now = 0.0

    @property
    def active_intervals(self) -> list[_ScheduledInterval]:
        """Return all non-cancelled intervals currently scheduled."""
        return [i for i in self._intervals if not i.cancelled]

    @property
    def one_shots(self) -> list[tuple[Callable[[], None], float]]:
        """Return every `schedule_once` call so far as (callback, timeout_secs), oldest first."""
        return [(s.callback, s.timeout_secs) for s in self._one_shots]

    @property
    def scheduled_once_count(self) -> int:
        """Return how many times `schedule_once` has been called."""
        return len(self._one_shots)

    @property
    def pending_one_shots(self) -> list[Callable[[], None]]:
        """Return the delayed one-shots not yet fired or cancelled, oldest first."""
        return [s.callback for s in self._one_shots if not s.fired and not s.cancelled]

    def schedule_interval(
        self, callback: Callable[[], None], period_secs: float
    ) -> _RecordedHandle:
        """Record the interval and return a cancellable handle."""
        scheduled = _ScheduledInterval(callback=callback, period_secs=period_secs)
        self._intervals.append(scheduled)
        return _RecordedHandle(scheduled)

    def schedule_once(
        self, callback: Callable[[], None], timeout_secs: float = 0
    ) -> _RecordedHandle:
        """Record the one-shot; run it inline when it has no delay, else on `advance()`."""
        scheduled = _ScheduledOneShot(callback, timeout_secs, due_at=self._now + timeout_secs)
        self._one_shots.append(scheduled)
        if timeout_secs <= 0:
            self._fire_one_shot(scheduled)
        return _RecordedHandle(scheduled)

    @staticmethod
    def _fire_one_shot(scheduled: _ScheduledOneShot) -> None:
        scheduled.fired = True
        scheduled.callback()

    def advance(self, secs: float) -> None:
        """Advance virtual time by *secs* seconds, firing scheduled callbacks.

        Each interval active at the *start* of the call fires ``floor(secs /
        period)`` times, then every delayed one-shot whose time has come fires,
        oldest first. Callbacks scheduled by callbacks during this advance do not
        fire — they wait for the next `advance()` call. This avoids runaway
        recursion when a callback reschedules itself.
        """
        self._now += secs
        snapshot = list(self._intervals)
        for interval in snapshot:
            if interval.cancelled:
                continue
            ticks = int(secs // interval.period_secs)
            for _ in range(ticks):
                if interval.cancelled:
                    break
                interval.callback()
        for one_shot in list(self._one_shots):
            if one_shot.fired or one_shot.cancelled or one_shot.due_at > self._now:
                continue
            self._fire_one_shot(one_shot)


# ----------------------------------------------------------------------
# Clock
# ----------------------------------------------------------------------


@dataclass(slots=True)
class _ScheduledOnce:
    """One ``schedule_once`` call, and the handle Kivy would return for it."""

    callback: Callable[[float], None]
    timeout: float
    fired: bool = False
    cancelled: bool = False

    def cancel(self) -> None:
        self.cancelled = True


class FakeClock:
    """A stand-in for Kivy's ``Clock`` whose ``schedule_once`` callbacks fire on demand.

    ``calls`` is every ``schedule_once`` made, oldest first, as (callback, timeout);
    ``pending`` the callbacks not yet fired or cancelled. ``run_next()`` fires the
    oldest pending one, ``fire_last()`` the most recently scheduled, ``drain()`` every
    pending one in order, including those they schedule. With ``immediate=True`` a
    callback runs as it is scheduled. The handles cancel, as Kivy's do, and a
    cancelled callback never fires.
    """

    def __init__(self, *, immediate: bool = False) -> None:
        self._immediate = immediate
        self._scheduled: list[_ScheduledOnce] = []

    @property
    def calls(self) -> list[tuple[Callable[[float], None], float]]:
        """Return every ``schedule_once`` call so far, oldest first."""
        return [(s.callback, s.timeout) for s in self._scheduled]

    @property
    def pending(self) -> list[Callable[[float], None]]:
        """Return the callbacks scheduled but not yet fired or cancelled, oldest first."""
        return [s.callback for s in self._scheduled if not s.fired and not s.cancelled]

    def schedule_once(
        self, callback: Callable[[float], None], timeout: float = 0
    ) -> _ScheduledOnce:
        """Record the call, running it at once in immediate mode; return its handle."""
        scheduled = _ScheduledOnce(callback, timeout)
        self._scheduled.append(scheduled)
        if self._immediate:
            self._fire(scheduled)
        return scheduled

    @staticmethod
    def schedule_interval(callback: Callable[[float], None], interval: float) -> _ScheduledOnce:
        """Return a cancellable handle; the interval never fires."""
        return _ScheduledOnce(callback, interval)

    @staticmethod
    def _fire(scheduled: _ScheduledOnce) -> None:
        scheduled.fired = True
        scheduled.callback(0.0)

    def run_next(self) -> bool:
        """Fire the oldest pending callback; False when there is none."""
        for scheduled in self._scheduled:
            if not scheduled.fired and not scheduled.cancelled:
                self._fire(scheduled)
                return True
        return False

    def fire_last(self) -> None:
        """Fire the most recently scheduled callback, unless it was cancelled."""
        last = self._scheduled[-1]
        if not last.cancelled:
            self._fire(last)

    def drain(self) -> None:
        """Fire every pending callback in order, including the ones they schedule."""
        while self.run_next():
            pass


# ----------------------------------------------------------------------
# Navigation payloads
# ----------------------------------------------------------------------


def fake_fanta_info() -> FantaComicBookInfo:
    """Return a sentinel ``FantaComicBookInfo``: compared by identity, never dereferenced."""
    return cast("FantaComicBookInfo", object())


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
# Cursor
# ----------------------------------------------------------------------


@dataclass(slots=True)
class RecordingCursor:
    """A `Cursor` that records every state change to a list."""

    states: list[str] = field(default_factory=list)

    def set_busy(self) -> None:
        """Record a busy-cursor state change."""
        self.states.append("busy")

    def set_normal(self) -> None:
        """Record a normal-cursor state change."""
        self.states.append("normal")


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
