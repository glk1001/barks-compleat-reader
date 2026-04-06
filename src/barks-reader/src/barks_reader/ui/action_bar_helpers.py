from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.metrics import dp

from barks_reader.core.reader_consts_and_types import RAW_ACTION_BAR_SIZE_Y

if TYPE_CHECKING:
    from kivy.uix.actionbar import ActionBar

ACTION_BAR_SIZE_Y = round(dp(RAW_ACTION_BAR_SIZE_Y))
ARROW_WIDTH = round(dp(20))


def show_action_bar(action_bar: ActionBar) -> None:
    action_bar.height = ACTION_BAR_SIZE_Y
    action_bar.opacity = 1
    action_bar.disabled = False


def hide_action_bar(action_bar: ActionBar) -> None:
    action_bar.height = 0
    action_bar.opacity = 0
    action_bar.disabled = True
