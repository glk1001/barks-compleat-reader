from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from kivy.metrics import dp

from barks_reader.core.reader_consts_and_types import RAW_ACTION_BAR_SIZE_Y

if TYPE_CHECKING:
    from kivy.uix.actionbar import ActionBar

ACTION_BAR_SIZE_Y = round(dp(RAW_ACTION_BAR_SIZE_Y))
ARROW_WIDTH = round(dp(20))


class ActionBarVisibility(Enum):
    """Whether the action bar is visible or hidden."""

    VISIBLE = "visible"
    HIDDEN = "hidden"


def set_action_bar_visibility(action_bar: ActionBar, state: ActionBarVisibility) -> None:
    """Set action bar visibility atomically (height, opacity, disabled)."""
    if state is ActionBarVisibility.VISIBLE:
        action_bar.height = ACTION_BAR_SIZE_Y
        action_bar.opacity = 1
        action_bar.disabled = False
    else:
        action_bar.height = 0
        action_bar.opacity = 0
        action_bar.disabled = True


def is_action_bar_visible(action_bar: ActionBar) -> bool:
    """Return True if the action bar is currently visible."""
    return not action_bar.disabled


def show_action_bar(action_bar: ActionBar) -> None:
    """Show the action bar. Prefer ``set_action_bar_visibility`` in new code."""
    set_action_bar_visibility(action_bar, ActionBarVisibility.VISIBLE)


def hide_action_bar(action_bar: ActionBar) -> None:
    """Hide the action bar. Prefer ``set_action_bar_visibility`` in new code."""
    set_action_bar_visibility(action_bar, ActionBarVisibility.HIDDEN)
