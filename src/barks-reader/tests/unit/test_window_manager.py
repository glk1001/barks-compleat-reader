# ruff: noqa: SLF001

"""Unit tests for WindowManager with a fake WindowBackend.

Tests exercise the platform-agnostic state machine (save/clear/goto_fullscreen/
goto_windowed) without touching Win32 or a real Kivy window.  The fake backend
records calls so assertions can verify ordering and argument passing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from barks_reader.ui.platform_window_utils import (
    FullscreenEnum,
    KivyWindowBackend,
    WindowManager,
    WindowState,
)

if TYPE_CHECKING:
    from collections.abc import Callable


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
) -> tuple[WindowManager, MagicMock, MagicMock, MagicMock]:
    monkeypatch.setattr("barks_reader.ui.platform_window_utils.Window", fake_window)
    monkeypatch.setattr("barks_reader.ui.platform_window_utils.Clock", fake_clock)

    on_first_resize = MagicMock()
    on_finished_windowed = MagicMock()
    on_finished_fullscreen = MagicMock()

    # Patch _create_window_backend so the constructor uses our fake.
    monkeypatch.setattr(
        "barks_reader.ui.platform_window_utils._create_window_backend",
        lambda: backend,
    )

    wm = WindowManager(
        client="test",
        on_goto_windowed_mode_first_resize_func=on_first_resize,
        on_finished_goto_windowed_mode=on_finished_windowed,
        on_finished_goto_fullscreen_mode=on_finished_fullscreen,
    )
    return wm, on_first_resize, on_finished_windowed, on_finished_fullscreen


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSaveAndClearState:
    def test_save_state_delegates_to_backend(
        self,
        manager: tuple[WindowManager, MagicMock, MagicMock, MagicMock],
        backend: _FakeBackend,
    ) -> None:
        wm, _, _, _ = manager
        wm.save_state_now()
        assert len(backend.saved_states) == 1

    def test_clear_state_resets_to_defaults(
        self,
        manager: tuple[WindowManager, MagicMock, MagicMock, MagicMock],
    ) -> None:
        wm, _, _, _ = manager
        wm.save_state_now()
        wm.clear_state()
        assert wm._saved_window_state.size == (0, 0)
        assert wm._saved_window_state.pos == (-1, -1)


class TestGotoFullscreenMode:
    def test_already_fullscreen_fires_callback_immediately(
        self,
        manager: tuple[WindowManager, MagicMock, MagicMock, MagicMock],
        fake_window: MagicMock,
    ) -> None:
        wm, _, _, on_finished_fullscreen = manager
        fake_window.fullscreen = True

        wm.goto_fullscreen_mode()

        on_finished_fullscreen.assert_called_once()

    def test_saves_state_and_enters_fullscreen(
        self,
        manager: tuple[WindowManager, MagicMock, MagicMock, MagicMock],
        fake_window: MagicMock,
        backend: _FakeBackend,
    ) -> None:
        wm, _, _, on_finished_fullscreen = manager
        fake_window.fullscreen = False

        wm.goto_fullscreen_mode()

        # Backend should have been asked to save state.
        assert len(backend.saved_states) == 1
        # Window.fullscreen should be set to "auto".
        assert fake_window.fullscreen == "auto"
        # Completion callback fires.
        on_finished_fullscreen.assert_called_once()


class TestGotoWindowedMode:
    def test_already_windowed_fires_callback_immediately(
        self,
        manager: tuple[WindowManager, MagicMock, MagicMock, MagicMock],
        fake_window: MagicMock,
    ) -> None:
        wm, _, on_finished_windowed, _ = manager
        fake_window.fullscreen = False

        wm.goto_windowed_mode()

        on_finished_windowed.assert_called_once()

    def test_exits_fullscreen_and_restores(
        self,
        manager: tuple[WindowManager, MagicMock, MagicMock, MagicMock],
        fake_window: MagicMock,
        backend: _FakeBackend,
    ) -> None:
        wm, on_first_resize, on_finished_windowed, _ = manager
        fake_window.fullscreen = True

        # First save state so there's something to restore.
        wm.save_state_now()

        wm.goto_windowed_mode()

        # Window should exit fullscreen.
        assert fake_window.borderless is False
        assert fake_window.fullscreen is False
        # Backend should have been asked to restore.
        assert len(backend.restore_calls) == 1
        # Both callbacks fire (first_resize then finished).
        on_first_resize.assert_called_once()
        on_finished_windowed.assert_called_once()


class TestStaticHelpers:
    def test_is_fullscreen_now(
        self,
        manager: tuple[WindowManager, MagicMock, MagicMock, MagicMock],
        fake_window: MagicMock,
    ) -> None:
        wm, _, _, _ = manager
        fake_window.fullscreen = True
        assert wm.is_fullscreen_now() is True
        fake_window.fullscreen = False
        assert wm.is_fullscreen_now() is False

    def test_get_screen_mode_now(
        self,
        manager: tuple[WindowManager, MagicMock, MagicMock, MagicMock],
        fake_window: MagicMock,
    ) -> None:
        wm, _, _, _ = manager
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


class TestRoundTrip:
    def test_save_fullscreen_windowed_round_trip(
        self,
        manager: tuple[WindowManager, MagicMock, MagicMock, MagicMock],
        fake_window: MagicMock,
        backend: _FakeBackend,
    ) -> None:
        wm, on_first_resize, on_finished_windowed, on_finished_fullscreen = manager

        # Start in windowed mode -> enter fullscreen.
        fake_window.fullscreen = False
        wm.goto_fullscreen_mode()

        assert len(backend.saved_states) == 1
        on_finished_fullscreen.assert_called_once()
        assert fake_window.fullscreen == "auto"

        # Now simulate Window being in fullscreen and exit back to windowed.
        fake_window.fullscreen = True
        wm.goto_windowed_mode()

        # Backend was asked to restore the previously-saved state.
        assert len(backend.restore_calls) == 1
        restored = backend.restore_calls[0]
        assert restored.size == (1200, 1800)
        assert restored.pos == (100, 50)
        on_first_resize.assert_called_once()
        on_finished_windowed.assert_called_once()


class TestFinishRestore:
    def test_finish_restore_logs_warning_when_state_differs(
        self,
        manager: tuple[WindowManager, MagicMock, MagicMock, MagicMock],
        fake_window: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        wm, _, _, _ = manager

        fake_logger = MagicMock()
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.logger", fake_logger)

        # Saved state differs from current Window geometry.
        wm._saved_window_state.size = (1200, 1800)
        wm._saved_window_state.pos = (100, 50)
        fake_window.size = (999, 999)
        fake_window.left = 0
        fake_window.top = 0

        wm._finish_restore()

        fake_logger.warning.assert_called_once()
        fake_logger.info.assert_not_called()

    def test_finish_restore_logs_info_when_state_matches(
        self,
        manager: tuple[WindowManager, MagicMock, MagicMock, MagicMock],
        fake_window: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        wm, _, _, _ = manager

        fake_logger = MagicMock()
        monkeypatch.setattr("barks_reader.ui.platform_window_utils.logger", fake_logger)

        # Saved state matches current Window geometry.
        wm._saved_window_state.size = (1200, 1800)
        wm._saved_window_state.pos = (100, 50)
        fake_window.size = (1200, 1800)
        fake_window.left = 100
        fake_window.top = 50

        wm._finish_restore()

        fake_logger.info.assert_called_once()
        fake_logger.warning.assert_not_called()


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
