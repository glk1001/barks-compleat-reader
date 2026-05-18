"""Periodic-scheduler port — abstracts the Kivy `Clock` so `core` stays Kivy-free."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable


@runtime_checkable
class CancelHandle(Protocol):
    """Handle returned by `PeriodicScheduler.schedule_interval` to cancel a timer."""

    def cancel(self) -> None:
        """Cancel the scheduled interval. Idempotent."""
        ...


@runtime_checkable
class PeriodicScheduler(Protocol):
    """Schedule a callback to fire repeatedly on a fixed interval.

    The production adapter wraps `kivy.clock.Clock.schedule_interval`. The test
    adapter (`core.testing.fakes.FakeScheduler`) records intervals and exposes
    `.advance(seconds)` to fire callbacks deterministically.
    """

    def schedule_interval(self, callback: Callable[[], None], period_secs: float) -> CancelHandle:
        """Schedule *callback* to be invoked every *period_secs* seconds.

        Args:
            callback: The zero-argument callable to invoke on each tick.
            period_secs: Interval between callback invocations, in seconds.

        Returns:
            A handle whose `.cancel()` method stops further callbacks.

        """
        ...
