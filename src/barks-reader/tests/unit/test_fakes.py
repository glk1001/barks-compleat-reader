"""Pin the subtle invariants in `core.testing.fakes` that production code relies on.

The `FakeScheduler.advance` snapshot-before-iterate behavior is the regression
target here: when a scheduled callback re-schedules itself or cancels its own
handle from inside an `advance()` call, iteration must stay bounded. Production
`ViewPipeline.set_view_state` does exactly that, and an earlier `advance()`
implementation iterated the live list and recursed forever.
"""

from __future__ import annotations

from barks_reader.core.testing import FakeScheduler


class TestFakeSchedulerAdvance:
    def test_callback_rescheduling_itself_does_not_cause_runaway(self) -> None:
        """A callback that schedules another interval during advance must not retrigger."""
        scheduler = FakeScheduler()
        fire_count = [0]

        def callback() -> None:
            fire_count[0] += 1
            # Schedule a fresh interval from inside the firing callback.
            # The original `advance` bug iterated the live list and would
            # immediately pick this one up, recursing forever.
            scheduler.schedule_interval(lambda: None, 1.0)

        scheduler.schedule_interval(callback, 10.0)
        scheduler.advance(10.0)

        # One tick fires for the originally-scheduled interval.
        # The new interval scheduled from inside the callback must NOT fire
        # until the next advance() call.
        assert fire_count[0] == 1

    def test_callback_that_cancels_itself_stops_within_same_advance(self) -> None:
        """A callback that cancels its own handle must not fire again on the same advance."""
        scheduler = FakeScheduler()
        fire_count = [0]
        handle: list[object] = []  # late binding

        def callback() -> None:
            fire_count[0] += 1
            handle[0].cancel()  # ty: ignore[unresolved-attribute]

        handle.append(scheduler.schedule_interval(callback, 1.0))
        # advance enough seconds that the timer would fire 5 times if not cancelled
        scheduler.advance(5.0)

        # First tick fires, callback cancels — no further ticks.
        assert fire_count[0] == 1

    def test_advance_fires_uncancelled_interval_the_expected_number_of_times(self) -> None:
        """An uncancelled interval fires floor(secs/period) times."""
        scheduler = FakeScheduler()
        fire_count = [0]

        scheduler.schedule_interval(lambda: fire_count.__setitem__(0, fire_count[0] + 1), 2.0)
        scheduler.advance(10.0)

        assert fire_count[0] == 5  # noqa: PLR2004

    def test_schedule_once_runs_inline_and_counts(self) -> None:
        """`schedule_once` is the worker-thread bridge — must fire synchronously."""
        scheduler = FakeScheduler()
        fire_count = [0]

        scheduler.schedule_once(lambda: fire_count.__setitem__(0, fire_count[0] + 1))
        scheduler.schedule_once(lambda: fire_count.__setitem__(0, fire_count[0] + 1))

        assert fire_count[0] == 2  # noqa: PLR2004
        assert scheduler.scheduled_once_count == 2  # noqa: PLR2004
