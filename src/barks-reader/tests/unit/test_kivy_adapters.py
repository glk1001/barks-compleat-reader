"""The Kivy adapters behind `core.ports`: what they hand the Clock, and what they return.

Nothing in the default test run drives these adapters otherwise; the app boots them.
The ports are ``runtime_checkable`` so the contract tests here can ask whether the
adapters the app wires in still satisfy them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core.ports import CancelHandle, ColorSource, Cursor, Scheduler, SnapshotSink
from barks_reader.core.reader_colors import FixedColorSource
from barks_reader.core.reader_palette import FIXED_SCRIMS
from barks_reader.core.testing import FakeClock
from barks_reader.ui import snapshot_applicator as snapshot_applicator_module
from barks_reader.ui.adapters import KivyClockScheduler, KivyCursor, kivy_scheduler
from barks_reader.ui.snapshot_applicator import SnapshotApplicator

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from barks_reader.ui.screen_bundle import ScreenBundle


@pytest.fixture
def clock() -> MagicMock:
    return MagicMock(name="Clock")


@pytest.fixture
def patched_clock(clock: MagicMock) -> Iterator[MagicMock]:
    with patch.object(kivy_scheduler, "Clock", clock):
        yield clock


class TestKivyClockScheduler:
    def test_an_interval_tick_calls_the_callback_with_no_arguments(
        self, patched_clock: MagicMock
    ) -> None:
        callback = MagicMock()

        KivyClockScheduler.schedule_interval(callback, 2.5)

        tick, period = patched_clock.schedule_interval.call_args.args
        assert period == 2.5  # noqa: PLR2004
        tick(0.016)
        callback.assert_called_once_with()

    def test_a_tick_returns_none_whatever_the_callback_returns(
        self, patched_clock: MagicMock
    ) -> None:
        """Kivy stops an interval whose callback returns False; the port's never does."""
        # Typed as the port's callback, as a refactored caller that grew a return would be.
        returns_false = cast("Callable[[], None]", lambda: False)
        KivyClockScheduler.schedule_interval(returns_false, 1.0)

        tick = patched_clock.schedule_interval.call_args.args[0]
        assert tick(0.016) is None

    def test_the_interval_handle_is_the_clock_event(self, patched_clock: MagicMock) -> None:
        handle = KivyClockScheduler.schedule_interval(MagicMock(), 1.0)

        assert handle is patched_clock.schedule_interval.return_value
        handle.cancel()
        patched_clock.schedule_interval.return_value.cancel.assert_called_once_with()

    def test_a_one_shot_keeps_its_delay_and_returns_the_clock_event(
        self, patched_clock: MagicMock
    ) -> None:
        callback = MagicMock()

        handle = KivyClockScheduler.schedule_once(callback, 1.0)

        tick, timeout = patched_clock.schedule_once.call_args.args
        assert timeout == 1.0
        tick(1.0)
        callback.assert_called_once_with()
        assert handle is patched_clock.schedule_once.return_value

    def test_a_one_shot_defaults_to_the_next_frame(self, patched_clock: MagicMock) -> None:
        KivyClockScheduler.schedule_once(MagicMock())

        assert patched_clock.schedule_once.call_args.args[1] == 0

    def test_a_cancelled_one_shot_never_fires_on_a_kivy_like_clock(self) -> None:
        fake_clock = FakeClock()
        callback = MagicMock()
        with patch.object(kivy_scheduler, "Clock", fake_clock):
            handle = KivyClockScheduler.schedule_once(callback, 1.0)
            handle.cancel()
            fake_clock.drain()

        callback.assert_not_called()


class TestTheAdaptersSatisfyTheirPorts:
    def test_the_scheduler_and_its_handles(self) -> None:
        fake_clock = FakeClock()
        scheduler = KivyClockScheduler()
        assert isinstance(scheduler, Scheduler)
        with patch.object(kivy_scheduler, "Clock", fake_clock):
            assert isinstance(scheduler.schedule_interval(MagicMock(), 1.0), CancelHandle)
            assert isinstance(scheduler.schedule_once(MagicMock(), 1.0), CancelHandle)

    def test_the_cursor(self) -> None:
        assert isinstance(KivyCursor(), Cursor)

    def test_the_color_source(self) -> None:
        assert isinstance(FixedColorSource(FIXED_SCRIMS), ColorSource)

    def test_the_snapshot_sink(self, screens: ScreenBundle) -> None:
        with patch.object(snapshot_applicator_module, "PanelTextureLoader"):
            assert isinstance(SnapshotApplicator(screens), SnapshotSink)
