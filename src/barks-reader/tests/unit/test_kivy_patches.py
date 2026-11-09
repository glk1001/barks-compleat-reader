"""The workarounds for Kivy 2.3.1's call to a canvas method that does not exist."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_kivy_ui.kivy_patches import apply_swap_transition_remove_group_patch
from kivy.uix.screenmanager import Screen, SwapTransition, TransitionBase

if TYPE_CHECKING:
    from collections.abc import Iterator

_WORKAROUND_FLAG = "_kivy_workaround_applied"


class TestSwapTransitionWorkaround:
    """SwapTransition ends by calling that method.

    That one AttributeError is caught and the transition finished by hand, and any
    other is raised.
    """

    @pytest.fixture
    def patched(self) -> Iterator[MagicMock]:
        """Install the patch over a failing original.

        Returns the original on_complete the patch wraps; Kivy's own is put back after.
        """
        had_flag = _WORKAROUND_FLAG in SwapTransition.__dict__
        if had_flag:
            delattr(SwapTransition, _WORKAROUND_FLAG)

        original = MagicMock(name="SwapTransition.on_complete")
        try:
            with patch.object(SwapTransition, "on_complete", original):
                apply_swap_transition_remove_group_patch()
                assert SwapTransition.on_complete is not original
                yield original
        finally:
            if had_flag:
                setattr(SwapTransition, _WORKAROUND_FLAG, True)
            elif _WORKAROUND_FLAG in SwapTransition.__dict__:
                delattr(SwapTransition, _WORKAROUND_FLAG)

    @staticmethod
    def _transition() -> SwapTransition:
        transition = SwapTransition()
        transition.screen_in = Screen()
        transition.screen_out = Screen()
        return transition

    def test_the_missing_canvas_method_is_worked_around(self, patched: MagicMock) -> None:
        patched.side_effect = AttributeError("'Canvas' object has no attribute '_remove_group'")
        transition = self._transition()

        with patch.object(TransitionBase, "on_complete") as finish:
            transition.on_complete()

        patched.assert_called_once_with(transition)
        finish.assert_called_once_with()

    def test_any_other_attribute_error_is_raised(self, patched: MagicMock) -> None:
        patched.side_effect = AttributeError("something else")
        with pytest.raises(AttributeError, match="something else"):
            self._transition().on_complete()

    def test_without_an_error_the_original_does_it_all(self, patched: MagicMock) -> None:
        transition = self._transition()
        with patch.object(TransitionBase, "on_complete") as finish:
            transition.on_complete()
        patched.assert_called_once_with(transition)
        finish.assert_not_called()

    def test_applying_it_again_leaves_it_alone(self) -> None:
        original = MagicMock(name="SwapTransition.on_complete")
        with (
            patch.object(SwapTransition, _WORKAROUND_FLAG, True, create=True),  # noqa: FBT003
            patch.object(SwapTransition, "on_complete", original),
        ):
            apply_swap_transition_remove_group_patch()
            assert SwapTransition.on_complete is original
