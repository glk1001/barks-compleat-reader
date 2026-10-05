"""Unit tests for AppWindowGeometryHelper.

These tests focus on ``_enforce_aspect_ratio`` -- the core decision logic that
gates whether a window resize triggers a correction. The recent Windows fix
(commit 190427c) added the degenerate-size guard at the top of this method,
and this file pins down its behavior so future refactors do not regress it.

Skipped automatically on headless CI by ``conftest.py`` (Kivy cannot create
an OpenGL context without a display).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from barks_reader.core import log_markers
from barks_reader.core.log_markers import pattern
from barks_reader.core.reader_utils import COMIC_PAGE_ASPECT_RATIO, get_win_dimensions
from barks_reader.core.screen_metrics import ScreenInfo
from barks_reader.ui.app_window_geometry import (
    MOVE_SETTLE_DELAY,
    RESIZE_CORRECTION_DELAY,
    AppWindowGeometryHelper,
    WindowSizeConstraints,
)

if TYPE_CHECKING:
    from collections.abc import Callable

CHROME = 45
MIN_WIDTH = 900


def _make_screen_info(width: int = 2560, height: int = 2400, display: int = 0) -> ScreenInfo:
    return ScreenInfo(
        display=display,
        monitor_x=0,
        monitor_y=0,
        width_pixels=width,
        height_pixels=height,
        width_mm=500,
        height_mm=300,
        width_in=20,
        height_in=12,
        dpi=96,
        is_primary=True,
    )


class _FakeClock:
    """Records ``schedule_once`` calls so tests can inspect or invoke them."""

    def __init__(self) -> None:
        self.calls: list[tuple[Callable[[float], None], float]] = []

    def schedule_once(self, callback: Callable[[float], None], timeout: float = 0) -> MagicMock:
        self.calls.append((callback, timeout))
        # Return a mock with .cancel() so the helper's debounce code works.
        return MagicMock()

    @staticmethod
    def schedule_interval(
        _callback: Callable[[float], None],
        _interval: float,
    ) -> MagicMock:
        return MagicMock()

    def fire_last(self) -> None:
        callback, _timeout = self.calls[-1]
        callback(0.0)


@pytest.fixture
def constraints() -> WindowSizeConstraints:
    return WindowSizeConstraints(
        aspect_ratio=COMIC_PAGE_ASPECT_RATIO,
        chrome_height=CHROME,
        min_window_width=MIN_WIDTH,
    )


@pytest.fixture
def fake_window() -> MagicMock:
    win = MagicMock()
    win.left = 100
    win.top = 100
    win.fullscreen = False
    win.size = (1500, 2000)
    return win


@pytest.fixture
def fake_clock() -> _FakeClock:
    return _FakeClock()


@pytest.fixture
def helper(
    monkeypatch: pytest.MonkeyPatch,
    constraints: WindowSizeConstraints,
    fake_window: MagicMock,
    fake_clock: _FakeClock,
) -> AppWindowGeometryHelper:
    screen = _make_screen_info()
    fake_metrics = MagicMock()
    fake_metrics.get_monitor_for_pos.return_value = screen
    fake_metrics.get_primary_screen_info.return_value = screen

    monkeypatch.setattr("barks_reader.ui.app_window_geometry.Window", fake_window)
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.SCREEN_METRICS", fake_metrics)
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.Clock", fake_clock)

    h = AppWindowGeometryHelper(constraints)
    h.set_main_screen_callbacks(MagicMock())
    h.set_window_ready()
    return h


# --- Degenerate-size guard ---


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (0, 0),
        (0, 45),
        (0, 100),
        (136, 45),  # The Windows hit-test minimum that caused 190427c.
        (800, 0),
        (800, 44),
        (800, 45),
    ],
)
def test_enforce_aspect_ratio_bails_on_degenerate_sizes(
    helper: AppWindowGeometryHelper, fake_clock: _FakeClock, width: int, height: int
) -> None:
    helper._enforce_aspect_ratio(width, height)  # noqa: SLF001
    assert fake_clock.calls == []


# --- What on_window_resize logs ---


def test_every_resize_event_is_logged_as_the_marker(
    helper: AppWindowGeometryHelper, fake_window: MagicMock, loguru_sink: list[str]
) -> None:
    """The GUI harness compares a test's last resize event against its first."""
    helper.on_window_resize(fake_window, 1500, 2000)

    wanted = pattern(log_markers.WINDOW_RESIZED, width=1500, height=2000)
    assert any(re.search(wanted, line) for line in loguru_sink)


def test_an_aspect_ratio_correction_names_the_event_and_the_size_it_applies(
    helper: AppWindowGeometryHelper,
    fake_window: MagicMock,
    fake_clock: _FakeClock,
    loguru_sink: list[str],
) -> None:
    """The correction used to resize the window silently; now the log says why."""
    helper.on_window_resize(fake_window, 1500, 2000)
    fake_clock.fire_last()

    width, content_h = get_win_dimensions(2000 - CHROME, 2560)
    assert fake_window.size == (width, content_h + CHROME)
    corrected = f"-> Window.size = ({width}, {content_h + CHROME})"
    assert any(
        "Aspect-ratio correction: resize event 1500,2000 " in line and corrected in line
        for line in loguru_sink
    )


# --- Gating conditions in on_window_resize ---


def test_resize_skipped_when_window_not_ready(
    monkeypatch: pytest.MonkeyPatch,
    constraints: WindowSizeConstraints,
    fake_window: MagicMock,
    fake_clock: _FakeClock,
) -> None:
    screen = _make_screen_info()
    fake_metrics = MagicMock()
    fake_metrics.get_monitor_for_pos.return_value = screen
    fake_metrics.get_primary_screen_info.return_value = screen
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.Window", fake_window)
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.SCREEN_METRICS", fake_metrics)
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.Clock", fake_clock)

    h = AppWindowGeometryHelper(constraints)
    h.set_main_screen_callbacks(MagicMock())
    # Deliberately do not call set_window_ready().

    h.on_window_resize(fake_window, 1500, 2000)
    assert fake_clock.calls == []


def test_resize_skipped_when_fullscreen(
    helper: AppWindowGeometryHelper, fake_window: MagicMock, fake_clock: _FakeClock
) -> None:
    fake_window.fullscreen = True
    helper.on_window_resize(fake_window, 1500, 2000)
    assert fake_clock.calls == []


def test_resize_skipped_when_suppression_active(
    helper: AppWindowGeometryHelper, fake_window: MagicMock, fake_clock: _FakeClock
) -> None:
    helper.suppress_aspect_ratio_correction(duration=2.0)
    # suppress_aspect_ratio_correction itself schedules a clear callback;
    # snapshot the call count and assert it does not grow.
    baseline = len(fake_clock.calls)
    helper.on_window_resize(fake_window, 1500, 2000)
    assert len(fake_clock.calls) == baseline


# --- Aspect-ratio correction ---


def test_correction_scheduled_when_width_does_not_match_height(
    helper: AppWindowGeometryHelper, fake_window: MagicMock, fake_clock: _FakeClock
) -> None:
    # Choose a height large enough that the min-width fallback does not kick in.
    height = 2000
    expected_width, _ = get_win_dimensions(height - CHROME, 2560)
    bogus_width = expected_width + 200  # Force a mismatch.

    fake_window.size = (bogus_width, height)  # the event reports the window's size
    helper._enforce_aspect_ratio(bogus_width, height)  # noqa: SLF001

    assert len(fake_clock.calls) == 1, "Expected exactly one scheduled correction."

    fake_clock.fire_last()
    assert fake_window.size == (expected_width, height)


def test_a_correction_for_a_size_the_window_has_left_is_dropped(
    helper: AppWindowGeometryHelper,
    fake_window: MagicMock,
    fake_clock: _FakeClock,
    loguru_sink: list[str],
) -> None:
    """Leaving fullscreen: a transient size's correction, after the restore had landed."""
    height = 2000
    right_width, _ = get_win_dimensions(height - CHROME, 2560)
    fake_window.size = (right_width + 300, height)
    helper.on_window_resize(fake_window, right_width + 300, height)
    restored = (right_width - 100, height - 200)
    fake_window.size = restored  # the restore, before the correction fires
    fake_clock.fire_last()
    assert fake_window.size == restored
    assert any("Aspect-ratio correction dropped" in line for line in loguru_sink)


def test_a_resize_already_in_proportion_cancels_a_pending_correction(
    helper: AppWindowGeometryHelper, fake_window: MagicMock
) -> None:
    height = 2000
    right_width, _ = get_win_dimensions(height - CHROME, 2560)
    fake_window.size = (right_width + 300, height)
    helper.on_window_resize(fake_window, right_width + 300, height)
    pending = helper._correction_event  # noqa: SLF001
    assert pending is not None
    fake_window.size = (right_width, height)
    helper.on_window_resize(fake_window, right_width, height)
    pending.cancel.assert_called_once_with()
    assert helper._correction_event is None  # noqa: SLF001


def test_correction_not_scheduled_when_already_correct(
    helper: AppWindowGeometryHelper, fake_clock: _FakeClock
) -> None:
    # Replace the update_fonts callback with a recording mock so we can assert
    # the no-correction path called it.
    update_fonts = MagicMock()
    helper.set_main_screen_callbacks(update_fonts)

    height = 2000
    expected_width, _ = get_win_dimensions(height - CHROME, 2560)

    helper._enforce_aspect_ratio(expected_width, height)  # noqa: SLF001

    assert fake_clock.calls == []
    update_fonts.assert_called_once_with(height)


def test_min_width_fallback_when_height_is_too_small(
    helper: AppWindowGeometryHelper, fake_window: MagicMock, fake_clock: _FakeClock
) -> None:
    # Pick an input that produces a correct_width below MIN_WIDTH so the
    # fallback branch fires. The fixture monitor is tall enough to accommodate
    # the fallback height, so it should be applied.
    fake_window.size = (1000, 800)  # the event reports the window's size
    helper._enforce_aspect_ratio(1000, 800)  # noqa: SLF001

    assert len(fake_clock.calls) == 1
    fake_clock.fire_last()

    expected_height = round(MIN_WIDTH * COMIC_PAGE_ASPECT_RATIO) + CHROME
    assert fake_window.size == (MIN_WIDTH, expected_height)


# --- Suppression context-management ---


def test_suppress_clears_pending_correction_event(
    helper: AppWindowGeometryHelper,
) -> None:
    # First, trigger a correction so a _correction_event is set.
    helper._enforce_aspect_ratio(1500, 2000)  # noqa: SLF001
    assert helper._correction_event is not None  # noqa: SLF001

    # Now suppress -- should cancel and clear the pending event.
    helper.suppress_aspect_ratio_correction(duration=1.0)
    assert helper._correction_event is None  # noqa: SLF001
    assert helper._suppress_correction is True  # noqa: SLF001


# --- Monitor-change handling (on_window_pos_change) ---


def _make_helper_two_monitors(
    monkeypatch: pytest.MonkeyPatch,
    constraints: WindowSizeConstraints,
    fake_window: MagicMock,
    fake_clock: _FakeClock,
) -> tuple[AppWindowGeometryHelper, MagicMock]:
    """Build a helper whose metrics stub returns different monitors based on position."""
    monitor_a = _make_screen_info(width=2560, height=2400)
    monitor_b = ScreenInfo(
        display=1,
        monitor_x=2560,
        monitor_y=0,
        width_pixels=1920,
        height_pixels=1080,
        width_mm=400,
        height_mm=225,
        width_in=16,
        height_in=9,
        dpi=120,
        is_primary=False,
    )

    fake_metrics = MagicMock()
    # Start on monitor_a.
    fake_metrics.get_monitor_for_pos.return_value = monitor_a
    fake_metrics.get_primary_screen_info.return_value = monitor_a

    monkeypatch.setattr("barks_reader.ui.app_window_geometry.Window", fake_window)
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.SCREEN_METRICS", fake_metrics)
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.Clock", fake_clock)

    h = AppWindowGeometryHelper(constraints)
    h.set_main_screen_callbacks(MagicMock())
    h.set_window_ready()

    # Now switch so future lookups return monitor_b.
    fake_metrics.get_monitor_for_pos.return_value = monitor_b
    return h, fake_metrics


def test_on_window_pos_change_triggers_resize_on_monitor_change(
    monkeypatch: pytest.MonkeyPatch,
    constraints: WindowSizeConstraints,
    fake_window: MagicMock,
    fake_clock: _FakeClock,
) -> None:
    fake_window.height = 2000
    fake_window.size = (1500, 2000)

    h, _ = _make_helper_two_monitors(monkeypatch, constraints, fake_window, fake_clock)
    h.on_window_pos_change(fake_window)

    # A guarded resize schedules 3 Clock.schedule_once calls (resize, reposition, reset guard).
    assert len(fake_clock.calls) >= 1


def test_on_window_pos_change_skipped_when_fullscreen(
    monkeypatch: pytest.MonkeyPatch,
    constraints: WindowSizeConstraints,
    fake_window: MagicMock,
    fake_clock: _FakeClock,
) -> None:
    fake_window.fullscreen = True
    h, _ = _make_helper_two_monitors(monkeypatch, constraints, fake_window, fake_clock)
    h.on_window_pos_change(fake_window)
    assert fake_clock.calls == []


def test_on_window_pos_change_skipped_when_same_monitor(
    monkeypatch: pytest.MonkeyPatch,
    constraints: WindowSizeConstraints,
    fake_window: MagicMock,
    fake_clock: _FakeClock,
) -> None:
    # Keep returning monitor_a so display stays the same.
    screen = _make_screen_info()
    fake_metrics = MagicMock()
    fake_metrics.get_monitor_for_pos.return_value = screen
    fake_metrics.get_primary_screen_info.return_value = screen
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.Window", fake_window)
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.SCREEN_METRICS", fake_metrics)
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.Clock", fake_clock)

    h = AppWindowGeometryHelper(constraints)
    h.set_main_screen_callbacks(MagicMock())
    h.set_window_ready()

    h.on_window_pos_change(fake_window)
    assert fake_clock.calls == []


def test_on_window_pos_change_skipped_when_monitor_is_none(
    monkeypatch: pytest.MonkeyPatch,
    constraints: WindowSizeConstraints,
    fake_window: MagicMock,
    fake_clock: _FakeClock,
) -> None:
    screen = _make_screen_info()
    fake_metrics = MagicMock()
    fake_metrics.get_primary_screen_info.return_value = screen
    # First call (constructor) returns a monitor; subsequent calls return None.
    fake_metrics.get_monitor_for_pos.side_effect = [screen, None]
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.Window", fake_window)
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.SCREEN_METRICS", fake_metrics)
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.Clock", fake_clock)

    h = AppWindowGeometryHelper(constraints)
    h.set_main_screen_callbacks(MagicMock())
    h.set_window_ready()

    h.on_window_pos_change(fake_window)
    assert fake_clock.calls == []


# --- Guarded resize path in on_window_resize ---


def test_resize_guard_reapplies_requested_size(
    helper: AppWindowGeometryHelper, fake_window: MagicMock
) -> None:
    # Simulate an active resize guard by setting internal state.
    helper._resize_event = MagicMock()  # noqa: SLF001
    helper._resize_requested_size = (1200, 1800)  # noqa: SLF001

    # OS fires a resize with a different size — the guard should re-apply the requested size.
    helper.on_window_resize(fake_window, 1000, 1500)
    assert fake_window.size == (1200, 1800)


def test_resize_guard_does_not_reapply_when_size_matches(
    helper: AppWindowGeometryHelper, fake_window: MagicMock
) -> None:
    update_fonts = MagicMock()
    helper.set_main_screen_callbacks(update_fonts)

    helper._resize_event = MagicMock()  # noqa: SLF001
    helper._resize_requested_size = (1200, 1800)  # noqa: SLF001
    fake_window.height = 1800

    # Size matches the guard — should not re-assign, but should update fonts.
    helper.on_window_resize(fake_window, 1200, 1800)
    update_fonts.assert_called_once_with(1800)


# --- Rotation polling ---


def test_start_and_stop_rotation_polling(
    helper: AppWindowGeometryHelper,
) -> None:
    helper.start_rotation_polling()
    assert helper._rotation_poll_event is not None  # noqa: SLF001

    helper.stop_polling()
    assert helper._rotation_poll_event is None  # noqa: SLF001


def test_rotation_check_skipped_when_fullscreen(
    helper: AppWindowGeometryHelper, fake_window: MagicMock
) -> None:
    fake_window.fullscreen = True
    # If _check_for_rotation ran while fullscreen, it would call refresh().
    # Verify it returns early (no error, no side effect).
    helper._check_for_rotation(0.0)  # noqa: SLF001


def test_rotation_detected_triggers_guarded_resize(
    monkeypatch: pytest.MonkeyPatch,
    constraints: WindowSizeConstraints,
    fake_window: MagicMock,
    fake_clock: _FakeClock,
) -> None:
    screen = _make_screen_info()
    fake_metrics = MagicMock()
    fake_metrics.get_monitor_for_pos.return_value = screen
    fake_metrics.get_primary_screen_info.return_value = screen
    # First call (during construction) returns False; subsequent call (during
    # rotation check) returns True to indicate rotation was detected.
    fake_metrics.refresh.return_value = True

    monkeypatch.setattr("barks_reader.ui.app_window_geometry.Window", fake_window)
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.SCREEN_METRICS", fake_metrics)
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.Clock", fake_clock)

    h = AppWindowGeometryHelper(constraints)
    h.set_main_screen_callbacks(MagicMock())
    h.set_window_ready()

    h._check_for_rotation(0.0)  # noqa: SLF001

    # Rotation handler schedules: do_resize, do_reposition, do_reset_resize.
    assert len(fake_clock.calls) >= 1
    # Resize guard should be set with the new requested size.
    assert h._resize_requested_size != (0, 0)  # noqa: SLF001


# --- Second degenerate guard (after correct_width computation) ---


def test_correction_skipped_when_monitor_lookup_fails_after_construction(
    monkeypatch: pytest.MonkeyPatch,
    constraints: WindowSizeConstraints,
    fake_window: MagicMock,
    fake_clock: _FakeClock,
) -> None:
    """When monitor lookup returns None mid-resize, the second degenerate guard fires.

    This exercises the ``correct_width <= 0`` branch (line 224 in
    ``app_window_geometry.py``): get_win_dimensions with monitor_w=0 produces a
    degenerate correct_width, and the min-width fallback also fails because the
    monitor is None. No correction should be scheduled.
    """
    screen = _make_screen_info()
    fake_metrics = MagicMock()
    fake_metrics.get_primary_screen_info.return_value = screen
    # Return a monitor at construction, then None for all subsequent lookups.
    fake_metrics.get_monitor_for_pos.side_effect = [screen, None, None, None]

    monkeypatch.setattr("barks_reader.ui.app_window_geometry.Window", fake_window)
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.SCREEN_METRICS", fake_metrics)
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.Clock", fake_clock)

    h = AppWindowGeometryHelper(constraints)
    h.set_main_screen_callbacks(MagicMock())
    h.set_window_ready()

    # Trigger _enforce_aspect_ratio with a tiny height that will, combined with
    # monitor_w=0, push correct_width below MIN_WIDTH and prevent the fallback.
    h._enforce_aspect_ratio(800, 100)  # noqa: SLF001

    # No correction scheduled — the second degenerate guard should have fired.
    assert fake_clock.calls == []


# --- The guarded resize's three steps, as the clock runs them ---


def test_a_guarded_resize_sizes_then_moves_the_window_then_drops_its_guard(
    helper: AppWindowGeometryHelper, fake_window: MagicMock, fake_clock: _FakeClock
) -> None:
    helper._schedule_guarded_resize(1200, 1800, reposition=(30, 40))  # noqa: SLF001
    (resize, resize_at), (move, move_at), (reset, reset_at) = fake_clock.calls
    assert (resize_at, move_at, reset_at) == (0, RESIZE_CORRECTION_DELAY, MOVE_SETTLE_DELAY)
    assert helper._resize_requested_size == (1200, 1800)  # noqa: SLF001
    assert helper._resize_event is not None  # noqa: SLF001

    resize(0.0)
    assert fake_window.size == (1200, 1800)

    move(0.0)
    assert (fake_window.left, fake_window.top) == (30, 40)

    reset(0.0)
    assert helper._resize_event is None  # noqa: SLF001
    assert helper._resize_requested_size == (0, 0)  # noqa: SLF001


def test_a_guarded_resize_with_nowhere_to_go_leaves_the_window_where_it_is(
    helper: AppWindowGeometryHelper, fake_window: MagicMock, fake_clock: _FakeClock
) -> None:
    helper._schedule_guarded_resize(1200, 1800)  # noqa: SLF001
    _, (move, _), _ = fake_clock.calls
    move(0.0)
    assert (fake_window.left, fake_window.top) == (100, 100)


# --- Monitors that cannot be found, and moves that need no resize ---


def _helper_with_metrics(
    monkeypatch: pytest.MonkeyPatch,
    constraints: WindowSizeConstraints,
    fake_window: MagicMock,
    fake_clock: _FakeClock,
    fake_metrics: MagicMock,
) -> AppWindowGeometryHelper:
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.Window", fake_window)
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.SCREEN_METRICS", fake_metrics)
    monkeypatch.setattr("barks_reader.ui.app_window_geometry.Clock", fake_clock)
    h = AppWindowGeometryHelper(constraints)
    h.set_main_screen_callbacks(MagicMock())
    h.set_window_ready()
    return h


def test_a_window_starting_off_every_monitor_takes_the_primary(
    monkeypatch: pytest.MonkeyPatch,
    constraints: WindowSizeConstraints,
    fake_window: MagicMock,
    fake_clock: _FakeClock,
) -> None:
    """Windows can report an off-screen Window.left/top at startup."""
    primary = _make_screen_info(display=3)
    fake_metrics = MagicMock()
    fake_metrics.get_monitor_for_pos.return_value = None
    fake_metrics.get_primary_screen_info.return_value = primary

    h = _helper_with_metrics(monkeypatch, constraints, fake_window, fake_clock, fake_metrics)

    assert h._current_monitor is primary  # noqa: SLF001


def test_a_move_to_a_monitor_of_the_same_height_keeps_the_size(
    monkeypatch: pytest.MonkeyPatch,
    constraints: WindowSizeConstraints,
    fake_window: MagicMock,
    fake_clock: _FakeClock,
) -> None:
    monitor_a, monitor_b = _make_screen_info(display=0), _make_screen_info(display=1)
    fake_metrics = MagicMock()
    fake_metrics.get_monitor_for_pos.return_value = monitor_a
    fake_metrics.get_primary_screen_info.return_value = monitor_a
    fake_window.height = 2000
    h = _helper_with_metrics(monkeypatch, constraints, fake_window, fake_clock, fake_metrics)
    fake_metrics.get_monitor_for_pos.return_value = monitor_b

    h.on_window_pos_change(fake_window)

    assert h._current_monitor is monitor_b  # noqa: SLF001
    assert fake_clock.calls == []


def test_a_rotation_off_every_monitor_fits_the_primary(
    monkeypatch: pytest.MonkeyPatch,
    constraints: WindowSizeConstraints,
    fake_window: MagicMock,
    fake_clock: _FakeClock,
) -> None:
    primary = _make_screen_info(width=1440, height=2560, display=2)
    fake_metrics = MagicMock()
    fake_metrics.get_monitor_for_pos.return_value = None
    fake_metrics.get_primary_screen_info.return_value = primary
    h = _helper_with_metrics(monkeypatch, constraints, fake_window, fake_clock, fake_metrics)

    h._handle_rotation()  # noqa: SLF001

    assert h._current_monitor is primary  # noqa: SLF001
    width, height = h._resize_requested_size  # noqa: SLF001
    assert 0 < width <= primary.width_pixels
    assert 0 < height <= primary.height_pixels


def test_stopping_polling_that_never_started_does_nothing(
    helper: AppWindowGeometryHelper,
) -> None:
    helper.stop_polling()
    assert helper._rotation_poll_event is None  # noqa: SLF001


def test_a_second_drag_step_replaces_the_pending_correction(
    helper: AppWindowGeometryHelper, fake_window: MagicMock, fake_clock: _FakeClock
) -> None:
    """Only one correction fires after a drag: each new step cancels the last one's."""
    height = 2000
    right_width, _ = get_win_dimensions(height - CHROME, 2560)
    fake_window.size = (right_width + 200, height)
    helper._enforce_aspect_ratio(right_width + 200, height)  # noqa: SLF001
    first = helper._correction_event  # noqa: SLF001

    fake_window.size = (right_width + 250, height)
    helper._enforce_aspect_ratio(right_width + 250, height)  # noqa: SLF001

    first.cancel.assert_called_once_with()
    assert helper._correction_event is not first  # noqa: SLF001
    assert len(fake_clock.calls) == 2  # noqa: PLR2004
