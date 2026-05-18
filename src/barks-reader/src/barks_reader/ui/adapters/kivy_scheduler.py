"""Production `PeriodicScheduler` adapter that wraps `kivy.clock.Clock`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.clock import Clock

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_reader.core.ports import CancelHandle


class _ClockEventHandle:
    """Wraps a Kivy `ClockEvent` to satisfy the `CancelHandle` protocol."""

    def __init__(self, event: object) -> None:
        self._event = event

    def cancel(self) -> None:
        """Cancel the underlying Kivy clock event."""
        self._event.cancel()  # ty: ignore[unresolved-attribute]


class KivyClockScheduler:
    """A `PeriodicScheduler` that delegates to `kivy.clock.Clock.schedule_interval`.

    Kivy's clock callbacks receive a `dt: float` argument; this adapter drops it
    so the port's zero-argument callback signature is preserved.
    """

    @staticmethod
    def schedule_interval(callback: Callable[[], None], period_secs: float) -> CancelHandle:
        """Schedule *callback* to fire every *period_secs* seconds via Kivy's Clock.

        Args:
            callback: The zero-argument callable to invoke on each tick.
            period_secs: Interval between callback invocations, in seconds.

        Returns:
            A cancellable handle wrapping the underlying Kivy `ClockEvent`.

        """
        event = Clock.schedule_interval(lambda _dt: callback(), period_secs)
        return _ClockEventHandle(event)
