"""Unit tests for action_bar_helpers visibility functions."""

from __future__ import annotations

from unittest.mock import MagicMock

from barks_reader.ui.action_bar_helpers import (
    ACTION_BAR_SIZE_Y,
    ActionBarVisibility,
    hide_action_bar,
    is_action_bar_visible,
    set_action_bar_visibility,
    show_action_bar,
)


def _make_action_bar() -> MagicMock:
    """Create a mock ActionBar with height, opacity, and disabled attributes."""
    bar = MagicMock()
    bar.height = 0
    bar.opacity = 0
    bar.disabled = True
    return bar


class TestSetActionBarVisibility:
    def test_visible_sets_all_three_properties(self) -> None:
        bar = _make_action_bar()
        set_action_bar_visibility(bar, ActionBarVisibility.VISIBLE)

        assert bar.height == ACTION_BAR_SIZE_Y
        assert bar.opacity == 1
        assert bar.disabled is False

    def test_hidden_sets_all_three_properties(self) -> None:
        bar = _make_action_bar()
        bar.height = ACTION_BAR_SIZE_Y
        bar.opacity = 1
        bar.disabled = False

        set_action_bar_visibility(bar, ActionBarVisibility.HIDDEN)

        assert bar.height == 0
        assert bar.opacity == 0
        assert bar.disabled is True


class TestIsActionBarVisible:
    def test_returns_true_when_not_disabled(self) -> None:
        bar = _make_action_bar()
        bar.disabled = False
        assert is_action_bar_visible(bar) is True

    def test_returns_false_when_disabled(self) -> None:
        bar = _make_action_bar()
        bar.disabled = True
        assert is_action_bar_visible(bar) is False


class TestConvenienceWrappers:
    def test_show_action_bar_makes_visible(self) -> None:
        bar = _make_action_bar()
        show_action_bar(bar)

        assert bar.height == ACTION_BAR_SIZE_Y
        assert bar.opacity == 1
        assert bar.disabled is False

    def test_hide_action_bar_makes_hidden(self) -> None:
        bar = _make_action_bar()
        bar.height = ACTION_BAR_SIZE_Y
        bar.opacity = 1
        bar.disabled = False

        hide_action_bar(bar)

        assert bar.height == 0
        assert bar.opacity == 0
        assert bar.disabled is True
