"""Production `Scheduler` adapter that wraps `kivy.clock.Clock`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.clock import Clock

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_reader.core.ports import CancelHandle


def _drop_dt(callback: Callable[[], None]) -> Callable[[float], None]:
    """Adapt the port's zero-argument callback to the `dt` Kivy's Clock passes.

    The tick returns `None` whatever *callback* returns: Kivy stops an interval
    whose callback returns `False`, and the port's callbacks are not asked to
    know that.
    """

    def tick(_dt: float) -> None:
        callback()

    return tick


class KivyClockScheduler:
    """A `Scheduler` that delegates to `kivy.clock.Clock`.

    Kivy's `ClockEvent` has the idempotent no-argument `cancel()` the port's
    `CancelHandle` asks for, so the events are returned as they are.
    """

    @staticmethod
    def schedule_interval(callback: Callable[[], None], period_secs: float) -> CancelHandle:
        """Schedule *callback* to fire every *period_secs* seconds via Kivy's Clock.

        Args:
            callback: The zero-argument callable to invoke on each tick.
            period_secs: Interval between callback invocations, in seconds.

        Returns:
            The Kivy `ClockEvent`, whose `cancel()` stops the ticks.

        """
        return Clock.schedule_interval(_drop_dt(callback), period_secs)

    @staticmethod
    def schedule_once(callback: Callable[[], None], timeout_secs: float = 0) -> CancelHandle:
        """Schedule *callback* to fire once on the UI thread after *timeout_secs*.

        Worker threads use this to marshal results onto the UI thread.

        Returns:
            The Kivy `ClockEvent`, whose `cancel()` stops the callback firing.

        """
        return Clock.schedule_once(_drop_dt(callback), timeout_secs)
