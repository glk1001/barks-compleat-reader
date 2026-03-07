from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.graphics import Color, Line
from loguru import logger

if TYPE_CHECKING:
    from kivy.uix.widget import Widget

# Kivy SDL2 key codes for navigation keys.
KEY_TAB = 9
KEY_ENTER = 13
KEY_ESCAPE = 27
KEY_UP = 273
KEY_DOWN = 274
KEY_RIGHT = 275
KEY_LEFT = 276
KEY_NUMPAD_ENTER = 271
KEY_PAGE_UP = 280
KEY_PAGE_DOWN = 281

MENU_FOCUS_HIGHLIGHT_GROUP = "menu_focus_highlight"


def draw_focus_highlight(
    widget: Widget,
    group: str,
    color: tuple[float, float, float, float] = (1, 1, 0, 1),
) -> None:
    canvas_after = widget.canvas.after  # ty: ignore[unresolved-attribute]
    canvas_after.remove_group(group)
    with canvas_after:
        Color(*color, group=group)
        Line(
            rectangle=(widget.x, widget.y, widget.width, widget.height),
            width=2,
            group=group,
        )


def clear_focus_highlight(widget: Widget, group: str) -> None:
    widget.canvas.after.remove_group(group)  # ty: ignore[unresolved-attribute]


class ActionBarNavMixin:
    """Mixin providing keyboard navigation for action bar button cycling.

    Call _setup_action_bar_nav(buttons) in __init__ before binding keyboard events.
    Override _is_action_bar_hidden / _on_action_bar_shown_for_menu /
    _on_action_bar_hidden_after_menu when the action bar can be hidden (e.g. fullscreen).
    """

    def _setup_action_bar_nav(self, menu_buttons: list) -> None:
        self._menu_mode: bool = False
        self._focused_btn_idx: int = 0
        self._last_used_btn_idx: int = 0
        self._showed_action_bar_for_menu: bool = False
        self._menu_buttons = menu_buttons

    # --- Hook overrides ---

    def _is_action_bar_hidden(self) -> bool:
        """Return True if the action bar is currently hidden."""
        return False

    def _on_action_bar_shown_for_menu(self) -> None:
        """Show the action bar when entering menu mode."""

    def _on_action_bar_hidden_after_menu(self) -> None:
        """Hide the action bar again when leaving menu mode."""

    # --- Menu mode lifecycle ---

    def _enter_menu_mode(self) -> None:
        self._menu_mode = True
        self._showed_action_bar_for_menu = False
        if self._is_action_bar_hidden():
            self._on_action_bar_shown_for_menu()
            self._showed_action_bar_for_menu = True
        self._focused_btn_idx = self._last_used_btn_idx
        self._update_menu_focus()
        logger.debug("Entered menu mode.")

    def _exit_menu_mode(self) -> None:
        self._clear_menu_focus()
        self._menu_mode = False
        if self._showed_action_bar_for_menu:
            self._on_action_bar_hidden_after_menu()
            self._showed_action_bar_for_menu = False
        logger.debug("Exited menu mode.")

    # --- Key handling ---

    def _handle_menu_key(self, key: int) -> bool:
        if key == KEY_RIGHT:
            self._move_menu_focus(1)
        elif key == KEY_LEFT:
            self._move_menu_focus(-1)
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._activate_focused_button()
        elif key == KEY_ESCAPE:
            self._exit_menu_mode()
        else:
            return False
        return True

    # --- Focus management ---

    def _move_menu_focus(self, delta: int) -> None:
        self._focused_btn_idx = (self._focused_btn_idx + delta) % len(self._menu_buttons)
        self._update_menu_focus()

    def _update_menu_focus(self) -> None:
        for i, btn in enumerate(self._menu_buttons):
            if i == self._focused_btn_idx:
                draw_focus_highlight(btn, MENU_FOCUS_HIGHLIGHT_GROUP)
            else:
                clear_focus_highlight(btn, MENU_FOCUS_HIGHLIGHT_GROUP)

    def _clear_menu_focus(self) -> None:
        for btn in self._menu_buttons:
            clear_focus_highlight(btn, MENU_FOCUS_HIGHLIGHT_GROUP)

    def _activate_focused_button(self) -> None:
        self._last_used_btn_idx = self._focused_btn_idx
        self._menu_buttons[self._focused_btn_idx].trigger_action()
        self._exit_menu_mode()
