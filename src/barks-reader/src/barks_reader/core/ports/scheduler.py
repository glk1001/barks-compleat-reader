"""Scheduler port — abstracts the Kivy `Clock` so `core` stays Kivy-free."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable


@runtime_checkable
class CancelHandle(Protocol):
    """Handle returned by `Scheduler.schedule_interval` to cancel a timer."""

    def cancel(self) -> None:
        """Cancel the scheduled interval. Idempotent."""
        ...


@runtime_checkable
class Scheduler(Protocol):
    """Marshal a callback onto the UI thread (one-shot or repeating).

    The production adapter wraps `kivy.clock.Clock`. Test adapters
    (`core.testing.fakes.FakeScheduler`) record interval schedules and expose
    `.advance(seconds)` to fire them, while one-shot schedules run inline.
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

    def schedule_once(self, callback: Callable[[], None], timeout_secs: float = 0) -> None:
        """Schedule *callback* to fire once after *timeout_secs*.

        The dominant use is `timeout_secs=0` — marshal a worker-thread result
        onto the UI thread on the next frame. Production runs the callback on
        the UI thread; tests run it inline on the calling thread.

        Args:
            callback: The zero-argument callable to invoke.
            timeout_secs: Delay before invocation, in seconds.

        """
        ...
