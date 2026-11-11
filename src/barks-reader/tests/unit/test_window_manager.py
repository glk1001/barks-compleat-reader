# ruff: noqa: SLF001

"""Unit tests for WindowManager with a fake WindowBackend.

Tests exercise the platform-agnostic state machine (save/goto_fullscreen/
goto_windowed) without touching Win32 or a real Kivy window.  The fake backend
records calls so assertions can verify ordering and argument passing.

The per-transition completion callbacks are passed as a ``WindowModeCallbacks``
bundle on each ``goto_*`` call (not baked into the manager) and captured by
closure through the transition's deferred steps, so a single shared
``WindowManager`` can serve multiple screens even when transitions overlap.
The fixture returns the bundle alongside its member mocks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core.platform_info import Platform
from barks_reader.core.screen_metrics import ScreenInfo
from barks_reader.core.testing import FakeClock
from barks_reader.ui import platform_window_utils as window_utils_module
from barks_reader.ui import platform_window_win32 as win32_module
from barks_reader.ui.platform_window_utils import (
    FullscreenEnum,
    KivyWindowBackend,
    WindowManager,
    WindowModeCallbacks,
    WindowModeController,
    WindowState,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# Fixture return: the window manager, its callback bundle, then the bundle's three
# member mocks (first-resize, finished-windowed, finished-fullscreen).
ManagerFixture = tuple[WindowManager, WindowModeCallbacks, MagicMock, MagicMock, MagicMock]


# ---------------------------------------------------------------------------
# Fake backend
# ---------------------------------------------------------------------------


class _FakeBackend:
    """Records save/restore/cancel calls for test assertions."""

    def __init__(self) -> None:
        self.saved_states: list[WindowState] = []
        self.restore_calls: list[WindowState] = []
        self.cancel_calls = 0
        self.move_calls: list[WindowState] = []
        # How many restores had been started at each move_now.
        self.restores_at_move: list[int] = []
        # The window, when a test wants to see its fullscreen flag at move_now.
        self.window: MagicMock | None = None
        self.fullscreen_at_move: list[object] = []
        self.hold_calls: list[WindowState] = []
        self.fullscreen_at_hold: list[object] = []
        self.fullscreen_at_release: list[object] = []
        self.fullscreen_at_quiet: list[object] = []

    def save_state(self, state: WindowState) -> None:
        state.size = (1200, 1800)
        state.pos = (100, 50)
        self.saved_states.append(state)

    def hold_windowed_rect(self, state: WindowState) -> None:
        self.hold_calls.append(state)
        if self.window is not None:
            self.fullscreen_at_hold.append(self.window.fullscreen)

    def release_windowed_rect(self) -> None:
        if self.window is not None:
            self.fullscreen_at_release.append(self.window.fullscreen)

    def quiet_frame_for_fullscreen(self) -> None:
        if self.window is not None:
            self.fullscreen_at_quiet.append(self.window.fullscreen)

    def move_now(self, state: WindowState) -> None:
        self.move_calls.append(state)
        self.restores_at_move.append(len(self.restore_calls))
        if self.window is not None:
            self.fullscreen_at_move.append(self.window.fullscreen)

    def schedule_restore(
        self,
        state: WindowState,
        on_first_resize: Callable[[], None],
        on_done: Callable[[], None],
    ) -> Callable[[], None]:
        self.restore_calls.append(state)
        # Simulate immediate restore completion.
        on_first_resize()
        on_done()

        def cancel() -> None:
            self.cancel_calls += 1

        return cancel


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_window() -> MagicMock:
    win = MagicMock()
    # Window.size in the units a ``Window.size =`` takes: the same as it, as on Linux
    # and Windows. A Retina Mac's differ, two pixels to a point.
    type(win).system_size = property(lambda w: tuple(w.size))
    win.fullscreen = False
    win.borderless = False
    win.size = (1200, 1800)
    win.left = 100
    win.top = 50
    return win


@pytest.fixture
def fake_clock() -> FakeClock:
    """Make a Clock that runs each scheduled callback as it is scheduled."""
    return FakeClock(immediate=True)


@pytest.fixture
def backend() -> _FakeBackend:
    return _FakeBackend()


@pytest.fixture
def manager(
    monkeypatch: pytest.MonkeyPatch,
    fake_window: MagicMock,
    fake_clock: FakeClock,
    backend: _FakeBackend,
) -> ManagerFixture:
    monkeypatch.setattr(window_utils_module, "Window", fake_window)
    monkeypatch.setattr(window_utils_module, "Clock", fake_clock)

    on_first_resize = MagicMock()
    on_finished_windowed = MagicMock()
    on_finished_fullscreen = MagicMock()
    callbacks = WindowModeCallbacks(
        on_windowed_first_resize=on_first_resize,
        on_finished_windowed=on_finished_windowed,
        on_finished_fullscreen=on_finished_fullscreen,
    )

    # Patch _create_window_backend so the constructor uses our fake.
    monkeypatch.setattr(
        "barks_reader.ui.platform_window_utils._create_window_backend",
        lambda: backend,
    )

    wm = WindowManager()
    return wm, callbacks, on_first_resize, on_finished_windowed, on_finished_fullscreen


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSaveState:
    def test_save_state_delegates_to_backend(
        self,
        manager: ManagerFixture,
        backend: _FakeBackend,
    ) -> None:
        wm, *_ = manager
        wm.save_state_now()
        assert len(backend.saved_states) == 1


class TestGotoFullscreenMode:
    def test_a_rectangle_held_for_an_exit_is_let_go_before_fullscreen_begins(
        self,
        manager: ManagerFixture,
        fake_window: MagicMock,
        backend: _FakeBackend,
    ) -> None:
        """Still held, it would keep the window at its windowed size, in fullscreen."""
        wm, callbacks, *_ = manager
        fake_window.fullscreen = False
        backend.window = fake_window

        wm.goto_fullscreen_mode(callbacks)

        assert backend.fullscreen_at_release == [False]
        assert fake_window.fullscreen == "auto"

    def test_the_windows_frame_is_quieted_before_fullscreen_begins(
        self,
        manager: ManagerFixture,
        fake_window: MagicMock,
        backend: _FakeBackend,
    ) -> None:
        """On Windows the caption can flash as its style is taken away."""
        wm, callbacks, *_ = manager
        fake_window.fullscreen = False
        backend.window = fake_window

        wm.goto_fullscreen_mode(callbacks)

        assert backend.fullscreen_at_quiet == [False]

    def test_already_fullscreen_fires_callback_immediately(
        self,
        manager: ManagerFixture,
        fake_window: MagicMock,
    ) -> None:
        wm, callbacks, _, _, on_finished_fullscreen = manager
        fake_window.fullscreen = True

        wm.goto_fullscreen_mode(callbacks)

        on_finished_fullscreen.assert_called_once()

    def test_saves_state_and_enters_fullscreen(
        self,
        manager: ManagerFixture,
        fake_window: MagicMock,
        backend: _FakeBackend,
    ) -> None:
        wm, callbacks, _, _, on_finished_fullscreen = manager
        fake_window.fullscreen = False

        wm.goto_fullscreen_mode(callbacks)

        # Backend should have been asked to save state.
        assert len(backend.saved_states) == 1
        # Window.fullscreen should be set to "auto".
        assert fake_window.fullscreen == "auto"
        # Completion callback fires.
        on_finished_fullscreen.assert_called_once()


class TestGotoWindowedMode:
    def test_already_windowed_fires_callback_immediately(
        self,
        manager: ManagerFixture,
        fake_window: MagicMock,
    ) -> None:
        wm, callbacks, _, on_finished_windowed, _ = manager
        fake_window.fullscreen = False

        wm.goto_windowed_mode(callbacks)

        on_finished_windowed.assert_called_once()

    def test_exits_fullscreen_and_restores(
        self,
        manager: ManagerFixture,
        fake_window: MagicMock,
        backend: _FakeBackend,
    ) -> None:
        wm, callbacks, on_first_resize, on_finished_windowed, _ = manager
        fake_window.fullscreen = True

        # First save state so there's something to restore.
        wm.save_state_now()

        wm.goto_windowed_mode(callbacks)

        # Window should exit fullscreen.
        assert fake_window.borderless is False
        assert fake_window.fullscreen is False
        # Backend should have been asked to restore.
        assert len(backend.restore_calls) == 1
        # Both callbacks fire (first_resize then finished).
        on_first_resize.assert_called_once()
        on_finished_windowed.assert_called_once()

    def test_moves_the_window_as_soon_as_fullscreen_ends(
        self,
        manager: ManagerFixture,
        fake_window: MagicMock,
        backend: _FakeBackend,
    ) -> None:
        # Regression: on Windows, SDL's fullscreen exit sizes the window for a frame
        # the custom titlebar hides; the saved rectangle goes back before a frame draws.
        wm, callbacks, _, _, _ = manager
        fake_window.fullscreen = True
        wm.save_state_now()
        backend.window = fake_window

        wm.goto_windowed_mode(callbacks)

        assert backend.move_calls == [backend.saved_states[0]]
        assert backend.fullscreen_at_move == [False]  # after the exit, not before

    def test_the_restore_starts_in_the_frame_fullscreen_ends(
        self,
        fake_window: MagicMock,
        backend: _FakeBackend,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Frames are slow while fullscreen ends: a frame's wait showed as a late snap."""
        clock = MagicMock()
        monkeypatch.setattr(window_utils_module, "Clock", clock)
        monkeypatch.setattr(window_utils_module, "Window", fake_window)
        monkeypatch.setattr(window_utils_module, "_create_window_backend", lambda: backend)
        wm = WindowManager()
        fake_window.fullscreen = True
        wm.save_state_now()

        wm.goto_windowed_mode(MagicMock())
        (do_windowed, _delay), _ = clock.schedule_once.call_args
        clock.schedule_once.reset_mock()
        do_windowed(0)

        assert backend.restore_calls == [backend.saved_states[0]]

    def test_the_restore_is_listening_before_the_window_is_moved(
        self,
        manager: ManagerFixture,
        fake_window: MagicMock,
        backend: _FakeBackend,
    ) -> None:
        """On Windows the exit's resize, and a frame drawn for it, come inside the move."""
        wm, callbacks, _, _, _ = manager
        fake_window.fullscreen = True
        wm.save_state_now()

        wm.goto_windowed_mode(callbacks)

        assert backend.restores_at_move == [1]

    def test_the_saved_rectangle_is_held_before_fullscreen_ends(
        self,
        manager: ManagerFixture,
        fake_window: MagicMock,
        backend: _FakeBackend,
    ) -> None:
        """The exit itself asks for the wrong rectangle: holding after it is too late."""
        wm, callbacks, _, _, _ = manager
        fake_window.fullscreen = True
        wm.save_state_now()
        backend.window = fake_window

        wm.goto_windowed_mode(callbacks)

        assert backend.hold_calls == [backend.saved_states[0]]
        assert backend.fullscreen_at_hold == [True]

    def test_exits_fullscreen_without_saved_state_skips_restore(
        self,
        manager: ManagerFixture,
        fake_window: MagicMock,
        backend: _FakeBackend,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Regression: the app started already fullscreen, so goto_fullscreen_mode
        # skipped its save. Exiting to windowed must not assert/crash (or restore
        # the sentinel geometry) — it leaves the geometry and finishes the transition.
        wm, callbacks, on_first_resize, on_finished_windowed, _ = manager
        fake_logger = MagicMock()
        monkeypatch.setattr(window_utils_module, "logger", fake_logger)
        fake_window.fullscreen = True
        # No save_state_now(): _saved_window_state is still the sentinel default.

        wm.goto_windowed_mode(callbacks)

        assert fake_window.fullscreen is False
        # Geometry restore is skipped, but the windowed transition still completes.
        assert len(backend.restore_calls) == 0
        assert backend.move_calls == []  # no saved rectangle to move to
        assert backend.hold_calls == []  # nor to hold
        on_first_resize.assert_called_once()
        on_finished_windowed.assert_called_once()
        fake_logger.warning.assert_called_once()


class TestStaticHelpers:
    def test_is_fullscreen_now(
        self,
        manager: ManagerFixture,
        fake_window: MagicMock,
    ) -> None:
        wm, *_ = manager
        fake_window.fullscreen = True
        assert wm.is_fullscreen_now() is True
        fake_window.fullscreen = False
        assert wm.is_fullscreen_now() is False

    def test_get_screen_mode_now(
        self,
        manager: ManagerFixture,
        fake_window: MagicMock,
    ) -> None:
        wm, *_ = manager
        fake_window.fullscreen = False
        assert wm.get_screen_mode_now() == "windowed"
        fake_window.fullscreen = True
        assert wm.get_screen_mode_now() == "fullscreen"


class TestWindowState:
    def test_save_state_now(self, fake_window: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(window_utils_module, "Window", fake_window)
        state = WindowState()
        fake_window.fullscreen = False
        fake_window.size = (800, 600)
        fake_window.left = 10
        fake_window.top = 20

        state.save_state_now()

        assert state.size == (800, 600)
        assert state.pos == (10, 20)

    def test_a_retina_window_is_saved_in_the_units_a_restore_takes(
        self, fake_window: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Window.size reads 2x on a Retina Mac; saved as read, a restore doubled it."""
        monkeypatch.setattr(window_utils_module, "Window", fake_window)
        fake_window.size = (1748, 2730)
        type(fake_window).system_size = property(lambda _w: (874, 1365))
        state = WindowState()

        state.save_state_now()

        assert state.size == (874, 1365)
        assert state.is_saved_state_same_as_current() is True

    def test_is_saved_state_same_as_current(
        self, fake_window: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(window_utils_module, "Window", fake_window)
        state = WindowState()
        state.size = (1200, 1800)
        state.pos = (100, 50)
        # fake_window has matching values from fixture.
        assert state.is_saved_state_same_as_current() is True

        state.size = (999, 999)
        assert state.is_saved_state_same_as_current() is False

    def test_get_current_screen_mode(
        self, fake_window: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(window_utils_module, "Window", fake_window)
        fake_window.fullscreen = False
        assert WindowState.get_current_screen_mode() == FullscreenEnum.WINDOWED
        fake_window.fullscreen = True
        assert WindowState.get_current_screen_mode() == FullscreenEnum.FULLSCREEN

    def test_is_unsaved(self) -> None:
        # Defaults are the sentinel -> unsaved.
        assert WindowState().is_unsaved() is True
        # Both captured (pos (0, 0) is a real corner, not the (-1, -1) sentinel).
        assert WindowState(size=(800, 600), pos=(0, 0)).is_unsaved() is False
        # Either sentinel alone still counts as unsaved.
        assert WindowState(size=(800, 600)).is_unsaved() is True  # pos default (-1, -1)
        assert WindowState(pos=(10, 20)).is_unsaved() is True  # size default (0, 0)


class TestRoundTrip:
    def test_save_fullscreen_windowed_round_trip(
        self,
        manager: ManagerFixture,
        fake_window: MagicMock,
        backend: _FakeBackend,
    ) -> None:
        wm, callbacks, on_first_resize, on_finished_windowed, on_finished_fullscreen = manager

        # Start in windowed mode -> enter fullscreen.
        fake_window.fullscreen = False
        wm.goto_fullscreen_mode(callbacks)

        assert len(backend.saved_states) == 1
        on_finished_fullscreen.assert_called_once()
        assert fake_window.fullscreen == "auto"

        # Now simulate Window being in fullscreen and exit back to windowed.
        fake_window.fullscreen = True
        wm.goto_windowed_mode(callbacks)

        # Backend was asked to restore the previously-saved state.
        assert len(backend.restore_calls) == 1
        restored = backend.restore_calls[0]
        assert restored.size == (1200, 1800)
        assert restored.pos == (100, 50)
        on_first_resize.assert_called_once()
        on_finished_windowed.assert_called_once()

    def test_shared_store_restores_across_screens_without_seeding(
        self,
        manager: ManagerFixture,
        fake_window: MagicMock,
        backend: _FakeBackend,
    ) -> None:
        # The cross-screen guarantee that lets us delete the old seeding coupling:
        # one screen going fullscreen saves the windowed geometry, and a *different*
        # screen's later windowed toggle restores it — because both screens share
        # this single WindowManager instance (and thus one geometry store). Each
        # screen passes its own callback bundle per call.
        wm, _, _, _, _ = manager

        main_finished_fullscreen = MagicMock()
        main_finished_windowed = MagicMock()
        main_screen_callbacks = WindowModeCallbacks(
            on_windowed_first_resize=MagicMock(),
            on_finished_windowed=main_finished_windowed,
            on_finished_fullscreen=main_finished_fullscreen,
        )
        comic_first_resize = MagicMock()
        comic_finished_windowed = MagicMock()
        comic_screen_callbacks = WindowModeCallbacks(
            on_windowed_first_resize=comic_first_resize,
            on_finished_windowed=comic_finished_windowed,
            on_finished_fullscreen=MagicMock(),
        )

        # Main screen goes fullscreen (captures the windowed geometry).
        fake_window.fullscreen = False
        wm.goto_fullscreen_mode(main_screen_callbacks)
        main_finished_fullscreen.assert_called_once()

        # Comic screen (opened while already fullscreen) toggles back to windowed —
        # no explicit seed needed; the shared store still has the geometry.
        fake_window.fullscreen = True
        wm.goto_windowed_mode(comic_screen_callbacks)

        assert len(backend.restore_calls) == 1
        restored = backend.restore_calls[0]
        assert restored.size == (1200, 1800)
        assert restored.pos == (100, 50)
        # The comic screen's bundle completes the transition; the main screen's
        # windowed callbacks are untouched.
        comic_first_resize.assert_called_once()
        comic_finished_windowed.assert_called_once()
        main_finished_windowed.assert_not_called()


class TestFinishRestore:
    def test_finish_restore_logs_warning_when_state_differs(
        self,
        manager: ManagerFixture,
        fake_window: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        wm, callbacks, *_ = manager

        fake_logger = MagicMock()
        monkeypatch.setattr(window_utils_module, "logger", fake_logger)

        # Saved state differs from current Window geometry.
        wm._saved_window_state.size = (1200, 1800)
        wm._saved_window_state.pos = (100, 50)
        fake_window.size = (999, 999)
        fake_window.left = 0
        fake_window.top = 0

        wm._finish_restore(callbacks)

        fake_logger.warning.assert_called_once()
        fake_logger.info.assert_not_called()

    def test_finish_restore_logs_info_when_state_matches(
        self,
        manager: ManagerFixture,
        fake_window: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        wm, callbacks, *_ = manager

        fake_logger = MagicMock()
        monkeypatch.setattr(window_utils_module, "logger", fake_logger)

        # Saved state matches current Window geometry.
        wm._saved_window_state.size = (1200, 1800)
        wm._saved_window_state.pos = (100, 50)
        fake_window.size = (1200, 1800)
        fake_window.left = 100
        fake_window.top = 50

        wm._finish_restore(callbacks)

        fake_logger.info.assert_called_once()
        fake_logger.warning.assert_not_called()


class _DeferredRestoreBackend(_FakeBackend):
    """Like _FakeBackend, but holds the restore callbacks for the test to fire later.

    Models the real backends' delayed geometry restore (0.05s Kivy / longer on
    Win32), which is the window in which a second transition can interleave.
    """

    def __init__(self) -> None:
        super().__init__()
        self.pending_on_first_resize: Callable[[], None] | None = None
        self.pending_on_done: Callable[[], None] | None = None

    def schedule_restore(
        self,
        state: WindowState,
        on_first_resize: Callable[[], None],
        on_done: Callable[[], None],
    ) -> Callable[[], None]:
        self.restore_calls.append(state)
        self.pending_on_first_resize = on_first_resize
        self.pending_on_done = on_done

        def cancel() -> None:
            # Models ClockEvent.cancel: the pending callbacks will never fire.
            self.cancel_calls += 1
            self.pending_on_first_resize = None
            self.pending_on_done = None

        return cancel


class TestInterleavedTransitions:
    """A goto_* landing while another transition's restore is still in flight."""

    @pytest.fixture
    def deferred_backend(self) -> _DeferredRestoreBackend:
        return _DeferredRestoreBackend()

    @pytest.fixture
    def deferred_manager(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fake_window: MagicMock,
        fake_clock: FakeClock,
        deferred_backend: _DeferredRestoreBackend,
    ) -> WindowManager:
        monkeypatch.setattr(window_utils_module, "Window", fake_window)
        monkeypatch.setattr(window_utils_module, "Clock", fake_clock)
        monkeypatch.setattr(
            "barks_reader.ui.platform_window_utils._create_window_backend",
            lambda: deferred_backend,
        )
        return WindowManager()

    def test_fullscreen_during_pending_restore_keeps_saved_geometry(
        self,
        deferred_manager: WindowManager,
        fake_window: MagicMock,
        deferred_backend: _DeferredRestoreBackend,
    ) -> None:
        # Regression for the shared-store race: re-entering fullscreen while a
        # windowed restore is still in flight must not save the transitional
        # (monitor-sized) geometry over the real windowed geometry.
        wm = deferred_manager
        first = WindowModeCallbacks(MagicMock(), MagicMock(), MagicMock())
        second = WindowModeCallbacks(MagicMock(), MagicMock(), MagicMock())

        # Windowed -> fullscreen captures the real windowed geometry.
        fake_window.fullscreen = False
        wm.goto_fullscreen_mode(first)
        assert len(deferred_backend.saved_states) == 1

        # Fullscreen -> windowed: the restore is scheduled but has not settled
        # (do_windowed already cleared Window.fullscreen).
        fake_window.fullscreen = True
        wm.goto_windowed_mode(first)
        assert fake_window.fullscreen is False
        assert deferred_backend.pending_on_done is not None

        # Second transition interleaves: back to fullscreen. No new save.
        wm.goto_fullscreen_mode(second)
        assert len(deferred_backend.saved_states) == 1

    def test_interrupting_fullscreen_cancels_the_scheduled_restore(
        self,
        deferred_manager: WindowManager,
        fake_window: MagicMock,
        deferred_backend: _DeferredRestoreBackend,
    ) -> None:
        # The fullscreen transition supersedes the pending windowed restore:
        # the backend restore is cancelled outright, so the stale resize can
        # never fire on the now-fullscreen window.
        wm = deferred_manager
        main_callbacks = WindowModeCallbacks(MagicMock(), MagicMock(), MagicMock())
        comic_finished_fullscreen = MagicMock()
        comic_callbacks = WindowModeCallbacks(MagicMock(), MagicMock(), comic_finished_fullscreen)

        fake_window.fullscreen = False
        wm.goto_fullscreen_mode(main_callbacks)
        fake_window.fullscreen = True
        wm.goto_windowed_mode(main_callbacks)
        assert deferred_backend.pending_on_done is not None

        wm.goto_fullscreen_mode(comic_callbacks)

        comic_finished_fullscreen.assert_called_once()
        assert deferred_backend.cancel_calls == 1
        assert deferred_backend.pending_on_done is None  # the resize will never fire
        # The cancelled transition is fully retired: a later fullscreen entry
        # saves geometry again instead of seeing a phantom pending restore.
        saves_before = len(deferred_backend.saved_states)
        fake_window.fullscreen = False
        wm.goto_fullscreen_mode(comic_callbacks)
        assert len(deferred_backend.saved_states) == saves_before + 1

    def test_stale_on_done_after_cancel_does_not_finish_windowed(
        self,
        deferred_manager: WindowManager,
        fake_window: MagicMock,
        deferred_backend: _DeferredRestoreBackend,
    ) -> None:
        # Belt and braces: a backend event whose resize had already fired when
        # the cancel landed still must not report a windowed completion (to
        # any screen's bundle) once the window is fullscreen again.
        wm = deferred_manager
        main_finished_windowed = MagicMock()
        main_callbacks = WindowModeCallbacks(MagicMock(), main_finished_windowed, MagicMock())
        comic_callbacks = WindowModeCallbacks(MagicMock(), MagicMock(), MagicMock())

        fake_window.fullscreen = False
        wm.goto_fullscreen_mode(main_callbacks)
        fake_window.fullscreen = True
        wm.goto_windowed_mode(main_callbacks)
        stale_on_done = deferred_backend.pending_on_done
        assert stale_on_done is not None

        wm.goto_fullscreen_mode(comic_callbacks)  # cancels; window is fullscreen again

        stale_on_done()  # the already-fired event settles anyway
        main_finished_windowed.assert_not_called()

    def test_fullscreen_superseding_before_scheduling_skips_restore(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fake_window: MagicMock,
        backend: _FakeBackend,
    ) -> None:
        # The fullscreen command lands in the same frame as the windowed one,
        # before the windowed chain reaches the backend: restore_saved sees the
        # window heading fullscreen and retires the transition — no backend
        # restore is ever scheduled, and no windowed callbacks fire.
        clock = FakeClock()
        monkeypatch.setattr(window_utils_module, "Window", fake_window)
        monkeypatch.setattr(window_utils_module, "Clock", clock)
        monkeypatch.setattr(
            "barks_reader.ui.platform_window_utils._create_window_backend",
            lambda: backend,
        )
        wm = WindowManager()
        windowed_first_resize = MagicMock()
        windowed_finished = MagicMock()
        windowed_cbs = WindowModeCallbacks(windowed_first_resize, windowed_finished, MagicMock())
        fullscreen_finished = MagicMock()
        fullscreen_cbs = WindowModeCallbacks(MagicMock(), MagicMock(), fullscreen_finished)

        fake_window.fullscreen = True
        wm.goto_windowed_mode(windowed_cbs)
        wm.goto_fullscreen_mode(fullscreen_cbs)  # same frame: nothing scheduled yet
        clock.drain()

        assert backend.restore_calls == []
        windowed_first_resize.assert_not_called()
        windowed_finished.assert_not_called()
        fullscreen_finished.assert_called_once()
        assert fake_window.fullscreen == "auto"


class TestKivyWindowBackend:
    def test_save_state(self, fake_window: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(window_utils_module, "Window", fake_window)
        backend = KivyWindowBackend()
        state = WindowState()
        fake_window.fullscreen = False
        fake_window.size = (800, 600)
        fake_window.left = 10
        fake_window.top = 20

        backend.save_state(state)

        assert state.size == (800, 600)
        assert state.pos == (10, 20)

    def test_schedule_restore(
        self,
        fake_window: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(window_utils_module, "Window", fake_window)

        monkeypatch.setattr(window_utils_module, "Clock", FakeClock(immediate=True))

        backend = KivyWindowBackend()
        state = WindowState(size=(1024, 768), pos=(50, 50))
        on_first = MagicMock()
        on_done = MagicMock()

        backend.schedule_restore(state, on_first, on_done)

        assert fake_window.size == (1024, 768)
        assert (fake_window.left, fake_window.top) == (50, 50)
        on_first.assert_called_once()
        on_done.assert_called_once()


class TestWindowModeController:
    """The per-screen toggle scaffolding over a (mocked) shared WindowManager."""

    @pytest.fixture
    def controller(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fake_window: MagicMock,
        fake_clock: FakeClock,
    ) -> tuple[WindowModeController, MagicMock, WindowModeCallbacks]:
        monkeypatch.setattr(window_utils_module, "Window", fake_window)
        monkeypatch.setattr(window_utils_module, "Clock", fake_clock)
        window_manager = MagicMock()
        callbacks = WindowModeCallbacks(
            on_windowed_first_resize=MagicMock(),
            on_finished_windowed=MagicMock(),
            on_finished_fullscreen=MagicMock(),
        )
        return WindowModeController("test", window_manager, callbacks), window_manager, callbacks

    def test_goto_fullscreen_delegates_with_callbacks(
        self, controller: tuple[WindowModeController, MagicMock, WindowModeCallbacks]
    ) -> None:
        ctrl, window_manager, callbacks = controller
        ctrl.goto_fullscreen()
        window_manager.goto_fullscreen_mode.assert_called_once_with(callbacks)

    def test_goto_windowed_delegates_with_callbacks(
        self, controller: tuple[WindowModeController, MagicMock, WindowModeCallbacks]
    ) -> None:
        ctrl, window_manager, callbacks = controller
        ctrl.goto_windowed()
        window_manager.goto_windowed_mode.assert_called_once_with(callbacks)

    def test_toggle_from_windowed_goes_fullscreen(
        self,
        controller: tuple[WindowModeController, MagicMock, WindowModeCallbacks],
    ) -> None:
        ctrl, window_manager, callbacks = controller
        window_manager.is_fullscreen_target.return_value = False

        ctrl.toggle()  # fake_clock runs the scheduled switch immediately

        window_manager.goto_fullscreen_mode.assert_called_once_with(callbacks)
        window_manager.goto_windowed_mode.assert_not_called()

    def test_toggle_from_fullscreen_goes_windowed(
        self,
        controller: tuple[WindowModeController, MagicMock, WindowModeCallbacks],
    ) -> None:
        ctrl, window_manager, callbacks = controller
        window_manager.is_fullscreen_target.return_value = True

        ctrl.toggle()

        window_manager.goto_windowed_mode.assert_called_once_with(callbacks)
        window_manager.goto_fullscreen_mode.assert_not_called()

    def test_force_fullscreen_goes_fullscreen_even_when_already_fullscreen(
        self,
        controller: tuple[WindowModeController, MagicMock, WindowModeCallbacks],
        fake_window: MagicMock,
    ) -> None:
        ctrl, window_manager, callbacks = controller
        fake_window.fullscreen = True

        ctrl.force_fullscreen()

        window_manager.goto_fullscreen_mode.assert_called_once_with(callbacks)


# ---------------------------------------------------------------------------
# Double-press toggle race (the Window.fullscreen flip lands a frame late)
# ---------------------------------------------------------------------------


class TestDoublePressToggle:
    """Two rapid presses must resolve as "go, then come back", not twice one way."""

    @pytest.fixture
    def race_setup(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fake_window: MagicMock,
        backend: _FakeBackend,
    ) -> tuple[WindowModeController, WindowManager, FakeClock, MagicMock]:
        clock = FakeClock()
        monkeypatch.setattr(window_utils_module, "Window", fake_window)
        monkeypatch.setattr(window_utils_module, "Clock", clock)
        monkeypatch.setattr(
            "barks_reader.ui.platform_window_utils._create_window_backend",
            lambda: backend,
        )
        wm = WindowManager()
        callbacks = WindowModeCallbacks(
            on_windowed_first_resize=MagicMock(),
            on_finished_windowed=MagicMock(),
            on_finished_fullscreen=MagicMock(),
        )
        return WindowModeController("test", wm, callbacks), wm, clock, fake_window

    def test_double_press_from_windowed_ends_windowed(
        self,
        race_setup: tuple[WindowModeController, WindowManager, FakeClock, MagicMock],
    ) -> None:
        ctrl, wm, clock, fake_window = race_setup
        fake_window.fullscreen = False

        ctrl.toggle()
        # The flip has not landed yet — this is the race window the second
        # press used to misread.
        assert fake_window.fullscreen is False
        assert wm.is_fullscreen_target() is True
        ctrl.toggle()

        clock.drain()

        assert not fake_window.fullscreen

    def test_double_press_from_fullscreen_ends_fullscreen(
        self,
        race_setup: tuple[WindowModeController, WindowManager, FakeClock, MagicMock],
    ) -> None:
        ctrl, wm, clock, fake_window = race_setup
        fake_window.fullscreen = True

        ctrl.toggle()
        assert wm.is_fullscreen_target() is False
        ctrl.toggle()

        clock.drain()

        assert fake_window.fullscreen == "auto"

    def test_target_mirrors_actual_state_when_settled(
        self,
        race_setup: tuple[WindowModeController, WindowManager, FakeClock, MagicMock],
    ) -> None:
        _ctrl, wm, _clock, fake_window = race_setup
        fake_window.fullscreen = False
        assert wm.is_fullscreen_target() is False
        fake_window.fullscreen = True
        assert wm.is_fullscreen_target() is True


# ---------------------------------------------------------------------------
# Which backend a platform gets
# ---------------------------------------------------------------------------


class TestCreateWindowBackend:
    def test_windows_gets_the_win32_backend_when_it_bound_its_window(self) -> None:
        with (
            patch.object(window_utils_module, "PLATFORM", Platform.WIN),
            patch.object(win32_module, "Win32WindowBackend") as win32_class,
        ):
            win32_class.return_value.is_available.return_value = True
            backend = window_utils_module._create_window_backend()

        assert backend is win32_class.return_value

    def test_windows_falls_back_to_kivy_when_win32_found_no_window(
        self, loguru_sink: list[str]
    ) -> None:
        with (
            patch.object(window_utils_module, "PLATFORM", Platform.WIN),
            patch.object(win32_module, "Win32WindowBackend") as win32_class,
        ):
            win32_class.return_value.is_available.return_value = False
            backend = window_utils_module._create_window_backend()

        assert isinstance(backend, KivyWindowBackend)
        assert "Win32 backend unavailable; falling back to Kivy backend." in loguru_sink

    def test_any_other_platform_gets_the_kivy_backend_and_win32_is_not_tried(self) -> None:
        with (
            patch.object(window_utils_module, "PLATFORM", Platform.LINUX),
            patch.object(win32_module, "Win32WindowBackend") as win32_class,
        ):
            backend = window_utils_module._create_window_backend()

        assert isinstance(backend, KivyWindowBackend)
        win32_class.assert_not_called()


# ---------------------------------------------------------------------------
# The custom titlebar's drag region
# ---------------------------------------------------------------------------


class TestSetTitlebarDragRegion:
    def test_with_the_os_titlebar_nothing_is_registered(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        window = MagicMock(custom_titlebar=False)
        monkeypatch.setattr(window_utils_module, "Window", window)

        window_utils_module.set_titlebar_drag_region(MagicMock())

        window.set_custom_titlebar.assert_not_called()

    def test_the_region_is_registered_with_the_window(
        self, monkeypatch: pytest.MonkeyPatch, loguru_sink: list[str]
    ) -> None:
        window = MagicMock(custom_titlebar=True)
        window.set_custom_titlebar.return_value = True
        monkeypatch.setattr(window_utils_module, "Window", window)
        region = MagicMock()

        window_utils_module.set_titlebar_drag_region(region)

        window.set_custom_titlebar.assert_called_once_with(region)
        assert not any("drag region failed" in line for line in loguru_sink)

    def test_a_region_the_window_refuses_is_warned_of(
        self, monkeypatch: pytest.MonkeyPatch, loguru_sink: list[str]
    ) -> None:
        window = MagicMock(custom_titlebar=True)
        window.set_custom_titlebar.return_value = False
        monkeypatch.setattr(window_utils_module, "Window", window)

        window_utils_module.set_titlebar_drag_region(MagicMock())

        assert "Window: setting the custom-titlebar drag region failed." in loguru_sink


# ---------------------------------------------------------------------------
# The monitors logged at boot
# ---------------------------------------------------------------------------


def _screen(display: int, *, is_primary: bool, width_mm: int = 0, dpi: int = 0) -> ScreenInfo:
    return ScreenInfo(
        display=display,
        monitor_x=1920 * display,
        monitor_y=0,
        width_pixels=1920,
        height_pixels=1080,
        width_mm=width_mm,
        height_mm=width_mm * 9 // 16,
        width_in=round(width_mm / 25.4),
        height_in=round(width_mm * 9 / 16 / 25.4),
        dpi=dpi,
        is_primary=is_primary,
    )


class TestLogScreenMetrics:
    """It is the first thing `reader_main` runs: a line that raises here stops the boot."""

    def test_a_screen_of_unknown_physical_size_is_logged_whole(
        self, loguru_sink: list[str]
    ) -> None:
        screens = [_screen(0, is_primary=True)]  # as a VM reports one: no size, no dpi
        with patch.object(window_utils_module.SCREEN_METRICS, "SCREEN_INFO", screens):
            window_utils_module.log_screen_metrics()

        assert loguru_sink[0] == "--- Detailed Monitor Metrics ---"
        assert "Display 0: 1920 x 1080 pixels at (0, 0)." in loguru_sink
        assert "  -> Physical Size: 0mm x 0mm (0.00in x 0.00in)." in loguru_sink
        assert "  -> Calculated DPI: 0.00." in loguru_sink
        assert loguru_sink[-1] == "--------------------------------"

    def test_each_display_has_its_own_lines_and_the_primary_says_so(
        self, loguru_sink: list[str]
    ) -> None:
        screens = [
            _screen(0, is_primary=False, width_mm=600, dpi=81),
            _screen(1, is_primary=True, width_mm=1210, dpi=40),
        ]
        with patch.object(window_utils_module.SCREEN_METRICS, "SCREEN_INFO", screens):
            window_utils_module.log_screen_metrics()

        first = loguru_sink.index("Display 0: 1920 x 1080 pixels at (0, 0).")
        second = loguru_sink.index("Display 1: 1920 x 1080 pixels at (1920, 0).")
        assert loguru_sink[first + 1 : first + 4] == [
            "  -> Physical Size: 600mm x 337mm (24.00in x 13.00in).",
            "  -> Calculated DPI: 81.00.",
            "  -> Primary: False.",
        ]
        assert loguru_sink[second + 1 : second + 4] == [
            "  -> Physical Size: 1210mm x 680mm (48.00in x 27.00in).",
            "  -> Calculated DPI: 40.00.",
            "  -> Primary: True.",
        ]
