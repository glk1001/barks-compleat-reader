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
from unittest.mock import MagicMock

import pytest
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
    """Records save/restore calls for test assertions."""

    def __init__(self) -> None:
        self.saved_states: list[WindowState] = []
        self.restore_calls: list[WindowState] = []

    def save_state(self, state: WindowState) -> None:
        state.size = (1200, 1800)
        state.pos = (100, 50)
        state.screen = FullscreenEnum.WINDOWED
        self.saved_states.append(state)

    def schedule_restore(
        self,
        state: WindowState,
        on_first_resize: Callable[[], None],
        on_done: Callable[[], None],
    ) -> None:
        self.restore_calls.append(state)
        # Simulate immediate restore completion.
        on_first_resize()
        on_done()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_window() -> MagicMock:
    win = MagicMock()
    win.fullscreen = False
    win.borderless = False
    win.size = (1200, 1800)
    win.left = 100
    win.top = 50
    return win


@pytest.fixture
def fake_clock() -> MagicMock:
    clock = MagicMock()

    # Make schedule_once invoke its callback immediately.
    # noinspection PyUnusedLocal
    def immediate_schedule(callback: Callable[..., None], timeout: float = 0) -> MagicMock:  # noqa: ARG001
        callback(0.0)
        return MagicMock()

    clock.schedule_once.side_effect = immediate_schedule
    return clock


@pytest.fixture
def backend() -> _FakeBackend:
    return _FakeBackend()


@pytest.fixture
def manager(
    monkeypatch: pytest.MonkeyPatch,
    fake_window: MagicMock,
    fake_clock: MagicMock,
    backend: _FakeBackend,
) -> ManagerFixture:
    monkeypatch.setattr("barks_reader.ui.platform_window_utils.Window", fake_window)
    monkeypatch.setattr("barks_reader.ui.platform_window_utils.Clock", fake_clock)

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
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.logger", fake_logger)
        fake_window.fullscreen = True
        # No save_state_now(): _saved_window_state is still the sentinel default.

        wm.goto_windowed_mode(callbacks)

        assert fake_window.fullscreen is False
        # Geometry restore is skipped, but the windowed transition still completes.
        assert len(backend.restore_calls) == 0
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
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.Window", fake_window)
        state = WindowState()
        fake_window.fullscreen = False
        fake_window.size = (800, 600)
        fake_window.left = 10
        fake_window.top = 20

        state.save_state_now()

        assert state.screen == FullscreenEnum.WINDOWED
        assert state.size == (800, 600)
        assert state.pos == (10, 20)

    def test_is_saved_state_same_as_current(
        self, fake_window: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.Window", fake_window)
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
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.Window", fake_window)
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
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.logger", fake_logger)

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
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.logger", fake_logger)

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
    ) -> None:
        self.restore_calls.append(state)
        self.pending_on_first_resize = on_first_resize
        self.pending_on_done = on_done


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
        fake_clock: MagicMock,
        deferred_backend: _DeferredRestoreBackend,
    ) -> WindowManager:
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.Window", fake_window)
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.Clock", fake_clock)
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

    def test_interrupted_restore_does_not_finish_windowed(
        self,
        deferred_manager: WindowManager,
        fake_window: MagicMock,
        deferred_backend: _DeferredRestoreBackend,
    ) -> None:
        # Regression for the callback race: when a fullscreen transition
        # interrupts a pending windowed restore, the stale restore must not
        # report a windowed completion (to any screen's bundle).
        wm = deferred_manager
        main_finished_windowed = MagicMock()
        main_callbacks = WindowModeCallbacks(MagicMock(), main_finished_windowed, MagicMock())
        comic_finished_windowed = MagicMock()
        comic_finished_fullscreen = MagicMock()
        comic_callbacks = WindowModeCallbacks(
            MagicMock(), comic_finished_windowed, comic_finished_fullscreen
        )

        fake_window.fullscreen = False
        wm.goto_fullscreen_mode(main_callbacks)
        fake_window.fullscreen = True
        wm.goto_windowed_mode(main_callbacks)

        # The comic screen goes fullscreen while the main screen's restore is
        # still pending (do_fullscreen sets Window.fullscreen back to "auto").
        wm.goto_fullscreen_mode(comic_callbacks)
        comic_finished_fullscreen.assert_called_once()

        # The stale restore now settles: neither screen may hear "windowed".
        assert deferred_backend.pending_on_done is not None
        deferred_backend.pending_on_done()
        main_finished_windowed.assert_not_called()
        comic_finished_windowed.assert_not_called()


class TestKivyWindowBackend:
    def test_save_state(self, fake_window: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.Window", fake_window)
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
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.Window", fake_window)

        fake_clock = MagicMock()

        # noinspection PyUnusedLocal
        def run_callback(callback: Callable[..., None], timeout: float = 0) -> MagicMock:  # noqa: ARG001
            callback(0.0)
            return MagicMock()

        fake_clock.schedule_once.side_effect = run_callback
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.Clock", fake_clock)

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
        fake_clock: MagicMock,
    ) -> tuple[WindowModeController, MagicMock, WindowModeCallbacks]:
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.Window", fake_window)
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.Clock", fake_clock)
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


class _QueuedClock:
    """A fake Clock that queues callbacks until drained, FIFO like Kivy's.

    The gap between scheduling and draining models the frame in which
    ``Window.fullscreen`` has not flipped yet — the double-press race window.
    """

    def __init__(self) -> None:
        self._queue: list[Callable[[float], None]] = []

    def schedule_once(self, callback: Callable[[float], None], _timeout: float = 0) -> MagicMock:
        self._queue.append(callback)
        return MagicMock()

    def drain(self) -> None:
        """Run queued callbacks in order, including ones they schedule."""
        while self._queue:
            self._queue.pop(0)(0.0)


class TestDoublePressToggle:
    """Two rapid presses must resolve as "go, then come back", not twice one way."""

    @pytest.fixture
    def race_setup(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fake_window: MagicMock,
        backend: _FakeBackend,
    ) -> tuple[WindowModeController, WindowManager, _QueuedClock, MagicMock]:
        clock = _QueuedClock()
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.Window", fake_window)
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.Clock", clock)
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
        race_setup: tuple[WindowModeController, WindowManager, _QueuedClock, MagicMock],
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
        race_setup: tuple[WindowModeController, WindowManager, _QueuedClock, MagicMock],
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
        race_setup: tuple[WindowModeController, WindowManager, _QueuedClock, MagicMock],
    ) -> None:
        _ctrl, wm, _clock, fake_window = race_setup
        fake_window.fullscreen = False
        assert wm.is_fullscreen_target() is False
        fake_window.fullscreen = True
        assert wm.is_fullscreen_target() is True
