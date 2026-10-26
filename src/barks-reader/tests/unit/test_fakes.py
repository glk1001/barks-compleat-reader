"""Pin the subtle invariants in `core.testing.fakes` that production code relies on.

The `FakeScheduler.advance` snapshot-before-iterate behavior is the regression
target here: when a scheduled callback re-schedules itself or cancels its own
handle from inside an `advance()` call, iteration must stay bounded. Production
`ViewPipeline.set_view_state` does exactly that, and an earlier `advance()`
implementation iterated the live list and recursed forever.
"""

from __future__ import annotations

import pytest
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

    def test_an_already_cancelled_interval_is_skipped_not_a_stopping_point(self) -> None:
        """A cancelled interval must be stepped over, leaving later ones to fire."""
        scheduler = FakeScheduler()
        fire_count = [0]

        cancelled = scheduler.schedule_interval(lambda: None, 1.0)
        cancelled.cancel()
        scheduler.schedule_interval(lambda: fire_count.__setitem__(0, fire_count[0] + 1), 1.0)

        scheduler.advance(3.0)

        assert fire_count[0] == 3  # noqa: PLR2004

    def test_self_cancelling_callback_does_not_stop_the_other_intervals(self) -> None:
        """Self-cancelling ends that interval's ticks only, not the whole advance."""
        scheduler = FakeScheduler()
        first_count = [0]
        second_count = [0]
        handle: list[object] = []  # late binding

        def self_cancelling() -> None:
            first_count[0] += 1
            handle[0].cancel()  # ty: ignore[unresolved-attribute]

        handle.append(scheduler.schedule_interval(self_cancelling, 1.0))
        scheduler.schedule_interval(lambda: second_count.__setitem__(0, second_count[0] + 1), 1.0)

        scheduler.advance(3.0)

        assert first_count[0] == 1
        assert second_count[0] == 3  # noqa: PLR2004

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


class TestFakeSchedulerTickArithmetic:
    """The fake counts whole periods the way a reader would, not the way floats do."""

    def test_a_fractional_period_fires_once_per_period(self) -> None:
        scheduler = FakeScheduler()
        fire_count = [0]

        scheduler.schedule_interval(lambda: fire_count.__setitem__(0, fire_count[0] + 1), 0.1)
        scheduler.advance(0.3)  # 0.3 // 0.1 is 2.0 in binary floating point

        assert fire_count[0] == 3  # noqa: PLR2004

    def test_ten_tenths_make_one_second(self) -> None:
        scheduler = FakeScheduler()
        fire_count = [0]

        scheduler.schedule_interval(lambda: fire_count.__setitem__(0, fire_count[0] + 1), 0.1)
        scheduler.advance(1.0)  # 1.0 // 0.1 is 9.0

        assert fire_count[0] == 10  # noqa: PLR2004

    def test_a_period_can_straddle_two_advances(self) -> None:
        scheduler = FakeScheduler()
        fire_count = [0]

        scheduler.schedule_interval(lambda: fire_count.__setitem__(0, fire_count[0] + 1), 1.0)
        scheduler.advance(0.5)
        assert fire_count[0] == 0
        scheduler.advance(0.5)
        assert fire_count[0] == 1
        scheduler.advance(0.9)
        assert fire_count[0] == 1
        scheduler.advance(0.1)
        assert fire_count[0] == 2  # noqa: PLR2004

    def test_a_tick_does_not_count_twice(self) -> None:
        """The residue after a tick is the time past the period, not the whole advance."""
        scheduler = FakeScheduler()
        fire_count = [0]

        scheduler.schedule_interval(lambda: fire_count.__setitem__(0, fire_count[0] + 1), 1.0)
        scheduler.advance(1.5)
        scheduler.advance(0.4)

        assert fire_count[0] == 1

    @pytest.mark.parametrize("period", [0, 0.0, -1.0])
    def test_a_period_of_zero_or_less_is_refused(self, period: float) -> None:
        scheduler = FakeScheduler()

        with pytest.raises(ValueError, match="positive period"):
            scheduler.schedule_interval(lambda: None, period)


class TestFakeSchedulerOneShots:
    def test_a_delayed_one_shot_waits_for_its_delay(self) -> None:
        scheduler = FakeScheduler()
        fired: list[str] = []

        scheduler.schedule_once(lambda: fired.append("late"), 1.0)

        assert fired == []
        assert scheduler.one_shots == [(scheduler.one_shots[0][0], 1.0)]
        scheduler.advance(0.5)
        assert fired == []
        scheduler.advance(0.5)
        assert fired == ["late"]
        assert scheduler.pending_one_shots == []

    def test_a_delayed_one_shot_fires_once_only(self) -> None:
        scheduler = FakeScheduler()
        fired: list[str] = []

        scheduler.schedule_once(lambda: fired.append("once"), 1.0)
        scheduler.advance(5.0)
        scheduler.advance(5.0)

        assert fired == ["once"]

    def test_a_cancelled_one_shot_never_fires(self) -> None:
        scheduler = FakeScheduler()
        fired: list[str] = []

        handle = scheduler.schedule_once(lambda: fired.append("never"), 1.0)
        handle.cancel()
        handle.cancel()  # idempotent, as the port promises
        scheduler.advance(2.0)

        assert fired == []
        assert scheduler.pending_one_shots == []

    def test_one_shots_fire_after_the_intervals_oldest_first(self) -> None:
        scheduler = FakeScheduler()
        order: list[str] = []

        scheduler.schedule_once(lambda: order.append("first one-shot"), 1.0)
        scheduler.schedule_once(lambda: order.append("second one-shot"), 1.0)
        scheduler.schedule_interval(lambda: order.append("tick"), 1.0)
        scheduler.advance(1.0)

        assert order == ["tick", "first one-shot", "second one-shot"]

    def test_a_one_shot_scheduled_by_a_callback_waits_for_the_next_advance(self) -> None:
        scheduler = FakeScheduler()
        order: list[str] = []

        def outer() -> None:
            order.append("outer")
            scheduler.schedule_once(lambda: order.append("inner"), 0.5)

        scheduler.schedule_once(outer, 1.0)
        scheduler.advance(1.0)
        assert order == ["outer"]
        scheduler.advance(0.5)
        assert order == ["outer", "inner"]
