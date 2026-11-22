"""The window's modes and its saved windowed rectangle (barks_reader.core.window_state)."""

from __future__ import annotations

import pytest
from barks_reader.core.window_state import FullscreenEnum, WindowState, screen_mode


@pytest.mark.parametrize(
    ("fullscreen", "mode"),
    [
        (False, FullscreenEnum.WINDOWED),
        (0, FullscreenEnum.WINDOWED),
        (True, FullscreenEnum.FULLSCREEN),
        ("auto", FullscreenEnum.FULLSCREEN),
        ("fake", FullscreenEnum.FULLSCREEN),
    ],
)
def test_the_mode_is_read_from_kivy_s_fullscreen_value(
    fullscreen: object, mode: FullscreenEnum
) -> None:
    assert screen_mode(fullscreen) is mode


class TestWindowState:
    def test_the_saved_rectangle_as_its_edges(self) -> None:
        state = WindowState()
        state.size, state.pos = (700, 500), (150, 120)

        assert state.edges() == (150, 120, 850, 620)

    def test_a_size_and_position_are_kept(self) -> None:
        state = WindowState()

        state.save((800, 600), (10, 20))

        assert (state.size, state.pos) == ((800, 600), (10, 20))
        assert state.is_unsaved() is False

    def test_what_kivy_hands_over_as_lists_is_kept_as_tuples(self) -> None:
        """Window.system_size is a list: kept as one, no saved state would equal it."""
        state = WindowState()

        state.save([800, 600], [10, 20])  # ty: ignore[invalid-argument-type]

        assert (state.size, state.pos) == ((800, 600), (10, 20))
        assert state.is_at([800, 600], [10, 20])  # ty: ignore[invalid-argument-type]

    @pytest.mark.parametrize(
        ("size", "pos", "at"),
        [
            ((1200, 1800), (100, 50), True),
            ((999, 1800), (100, 50), False),
            ((1200, 1800), (100, 51), False),
        ],
    )
    def test_a_window_is_at_the_saved_state_by_both_its_size_and_position(
        self, size: tuple[int, int], pos: tuple[int, int], *, at: bool
    ) -> None:
        state = WindowState(size=(1200, 1800), pos=(100, 50))
        assert state.is_at(size, pos) is at

    def test_is_unsaved(self) -> None:
        # Defaults are the sentinel -> unsaved.
        assert WindowState().is_unsaved() is True
        assert WindowState(size=(800, 600), pos=(0, 0)).is_unsaved() is False
        # Either field still at its sentinel -> unsaved.
        assert WindowState(size=(800, 600)).is_unsaved() is True  # pos default (-1, -1)
        assert WindowState(pos=(10, 20)).is_unsaved() is True  # size default (0, 0)
