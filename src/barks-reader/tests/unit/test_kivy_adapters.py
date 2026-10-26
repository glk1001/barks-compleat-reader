"""The Kivy adapters behind `core.ports`: what they hand the Clock, and what they return.

Nothing in the default test run drives these adapters otherwise; the app boots them.
The ports are ``runtime_checkable`` so the contract tests here can ask whether the
adapters the app wires in still satisfy them.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from typing import TYPE_CHECKING, cast, get_protocol_members
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core.ports import (
    CancelHandle,
    ColorSource,
    ComicBookReaderPort,
    ComicBookReaderScreenPort,
    Cursor,
    Scheduler,
    SnapshotSink,
)
from barks_reader.core.reader_colors import FixedColorSource
from barks_reader.core.reader_palette import FIXED_SCRIMS
from barks_reader.core.testing import FakeClock
from barks_reader.ui import snapshot_applicator as snapshot_applicator_module
from barks_reader.ui import ui_helpers
from barks_reader.ui.adapters import KivyClockScheduler, KivyCursor, kivy_scheduler
from barks_reader.ui.comic_book_reader import ComicBookReader, ComicBookReaderScreen
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


class TestKivyCursor:
    """The loader calls `set_normal` from its worker thread: the change must be marshalled.

    The port promises either method is safe from any thread, so the adapter has to
    schedule the SDL cursor call onto the UI thread rather than make it in place.
    """

    @pytest.mark.parametrize(
        ("change", "cursor_name"),
        [(KivyCursor.set_busy, "wait"), (KivyCursor.set_normal, "arrow")],
    )
    def test_the_cursor_changes_on_the_ui_thread_not_in_place(
        self, change: Callable[[], None], cursor_name: str
    ) -> None:
        fake_clock = FakeClock()
        window = MagicMock(name="Window")
        with (
            patch.object(ui_helpers, "Clock", fake_clock),
            patch.object(ui_helpers, "Window", window),
        ):
            change()
            window.set_system_cursor.assert_not_called()
            assert [timeout for _, timeout in fake_clock.calls] == [0]
            fake_clock.run_next()

        window.set_system_cursor.assert_called_once_with(cursor_name)


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

    @pytest.mark.parametrize(
        ("port", "widget"),
        [
            (ComicBookReaderPort, ComicBookReader),
            (ComicBookReaderScreenPort, ComicBookReaderScreen),
        ],
    )
    def test_the_reader_widgets_have_every_member_their_port_names(
        self, port: type, widget: type
    ) -> None:
        """The widgets need a running app to build, so the check is on the class.

        A member the widget sets on `self` in `__init__` counts as present.
        """
        set_in_init = _attributes_set_on_self_in_init(widget)
        missing = [
            member
            for member in sorted(get_protocol_members(port))
            if not hasattr(widget, member) and member not in set_in_init
        ]
        assert missing == []


def _attributes_set_on_self_in_init(cls: type) -> set[str]:
    """Return the names `cls.__init__` assigns on `self`."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(cls.__init__)))
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Store)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    }
