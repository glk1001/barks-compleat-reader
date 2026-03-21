from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.graphics import Color, Line
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Iterable

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
    line_width: float = 2,
) -> None:
    canvas_after = widget.canvas.after  # ty: ignore[unresolved-attribute]
    canvas_after.remove_group(group)
    with canvas_after:
        Color(*color, group=group)
        Line(
            rectangle=(widget.x, widget.y, widget.width, widget.height),
            width=line_width,
            group=group,
        )


def clear_focus_highlight(widget: Widget, group: str) -> None:
    widget.canvas.after.remove_group(group)  # ty: ignore[unresolved-attribute]


def update_focus_in_list(
    widgets: Iterable[Widget],
    focused_idx: int,
    group: str,
    color: tuple[float, float, float, float] = (1, 1, 0, 1),
) -> None:
    """Draw a focus highlight on the widget at focused_idx, clearing all others."""
    for i, widget in enumerate(widgets):
        if i == focused_idx:
            draw_focus_highlight(widget, group, color=color)
        else:
            clear_focus_highlight(widget, group)


def clear_focus_in_list(widgets: Iterable[Widget], group: str) -> None:
    """Clear focus highlights from all widgets in the iterable."""
    for widget in widgets:
        clear_focus_highlight(widget, group)


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
        update_focus_in_list(self._menu_buttons, self._focused_btn_idx, MENU_FOCUS_HIGHLIGHT_GROUP)

    def _clear_menu_focus(self) -> None:
        clear_focus_in_list(self._menu_buttons, MENU_FOCUS_HIGHLIGHT_GROUP)

    def _clear_menu_on_touch(self) -> None:
        """Call from on_touch_down to exit menu mode on any mouse interaction."""
        if self._menu_mode:
            self._exit_menu_mode()
            self._last_used_btn_idx = 0

    def _activate_focused_button(self) -> None:
        self._last_used_btn_idx = self._focused_btn_idx
        self._menu_buttons[self._focused_btn_idx].trigger_action()
        self._exit_menu_mode()


class DropdownNavMixin:
    """Mixin for keyboard navigation within an open Kivy DropDown.

    Requires ActionBarNavMixin to also be in the MRO.

    Usage:
      1. Put DropdownNavMixin before ActionBarNavMixin in the class bases so that
         _handle_menu_key intercepts dropdown keys before the action-bar handler.
      2. Call _setup_dropdown_nav() in __init__ or an init helper.
      3. Override _get_dropdown_buttons() and _dismiss_dropdown().
      4. Optionally override _scroll_to_dropdown_button() for scrollable dropdowns.
      5. Set class-level _dropdown_wraps=False and/or _dropdown_page_step>0 as needed.
    """

    _dropdown_wraps: bool = True  # wrap at ends; set False to clamp
    _dropdown_page_step: int = 0  # 0 = no Page Up/Down keys

    def _setup_dropdown_nav(self) -> None:
        self._dropdown_nav_mode: bool = False
        self._dropdown_focused_idx: int = 0
        self._dropdown_prev_focused_idx: int = 0
        self._dropdown_buttons_cache: list = []

    # --- Abstract hooks ---

    def _get_dropdown_buttons(self) -> list:
        """Return the dropdown buttons in visual top-to-bottom order."""
        return []

    def _dismiss_dropdown(self) -> None:
        """Dismiss the dropdown."""

    def _scroll_to_dropdown_button(self, btn: object) -> None:
        """Scroll the dropdown so btn is visible (optional)."""

    # --- Lifecycle ---

    def _enter_dropdown_nav(self, initial_idx: int = 0) -> None:
        self._dropdown_nav_mode = True
        self._dropdown_buttons_cache = self._get_dropdown_buttons()
        self._dropdown_focused_idx = initial_idx
        self._dropdown_prev_focused_idx = initial_idx
        self._update_dropdown_focus()

    def _exit_dropdown_nav(self) -> None:
        self._clear_dropdown_focus()
        self._dropdown_buttons_cache = []
        self._dropdown_nav_mode = False

    def _on_dropdown_dismissed(self, _dropdown: Widget) -> None:
        if self._dropdown_nav_mode:
            self._exit_dropdown_nav()
            # noinspection PyUnresolvedReferences
            if self._menu_mode:  # ty: ignore[unresolved-attribute]
                # noinspection PyUnresolvedReferences
                self._exit_menu_mode()  # ty: ignore[unresolved-attribute]

    # --- Key handling ---

    def _handle_menu_key(self, key: int) -> bool:
        if self._dropdown_nav_mode:
            return self._handle_dropdown_key(key)
        # noinspection PyProtectedMember
        return super()._handle_menu_key(key)  # type: ignore[misc]

    def _handle_dropdown_key(self, key: int) -> bool:
        buttons = self._dropdown_buttons_cache
        if not buttons:
            return False
        n = len(buttons)
        idx = self._dropdown_focused_idx
        if key == KEY_UP:
            idx = (idx - 1) % n if self._dropdown_wraps else max(0, idx - 1)
        elif key == KEY_DOWN:
            idx = (idx + 1) % n if self._dropdown_wraps else min(n - 1, idx + 1)
        elif self._dropdown_page_step and key == KEY_PAGE_UP:
            idx = max(0, idx - self._dropdown_page_step)
        elif self._dropdown_page_step and key == KEY_PAGE_DOWN:
            idx = min(n - 1, idx + self._dropdown_page_step)
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._activate_dropdown_item()
            return True
        elif key == KEY_ESCAPE:
            self._dismiss_dropdown()
            return True
        else:
            return False
        if idx != self._dropdown_focused_idx:
            self._dropdown_focused_idx = idx
            self._update_dropdown_focus()
        return True

    def _activate_dropdown_item(self) -> None:
        self._dropdown_buttons_cache[self._dropdown_focused_idx].trigger_action()

    # --- Focus management (O(1) per keypress) ---

    def _update_dropdown_focus(self) -> None:
        buttons = self._dropdown_buttons_cache
        old_idx = self._dropdown_prev_focused_idx
        new_idx = self._dropdown_focused_idx
        if old_idx != new_idx:
            clear_focus_highlight(buttons[old_idx], MENU_FOCUS_HIGHLIGHT_GROUP)
        draw_focus_highlight(buttons[new_idx], MENU_FOCUS_HIGHLIGHT_GROUP)
        self._scroll_to_dropdown_button(buttons[new_idx])
        self._dropdown_prev_focused_idx = new_idx

    def _clear_dropdown_focus(self) -> None:
        for btn in self._dropdown_buttons_cache:
            clear_focus_highlight(btn, MENU_FOCUS_HIGHLIGHT_GROUP)
