from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.graphics import Color, Line
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Iterable

    from kivy.uix.button import Button
    from kivy.uix.widget import Widget

# Kivy SDL2 key codes for navigation keys.
KEY_TAB = 9
KEY_ENTER = 13
KEY_ESCAPE = 27
KEY_F = ord("f")
KEY_UP = 273
KEY_DOWN = 274
KEY_RIGHT = 275
KEY_LEFT = 276
KEY_NUMPAD_ENTER = 271
KEY_PAGE_UP = 280
KEY_PAGE_DOWN = 281
KEY_DELETE = 127

_alt_escape_key: int = 0


def set_alt_escape_key(key: int) -> None:
    """Set the user-configured alternate Escape keycode (0 = unset)."""
    global _alt_escape_key  # noqa: PLW0603
    _alt_escape_key = int(key) if key else 0


def get_alt_escape_key() -> int:
    """Return the current alternate Escape keycode (0 = unset)."""
    return _alt_escape_key


def is_escape_key(key: int) -> bool:
    """Return True if key is real Escape or the user-configured alternate Escape."""
    return key == KEY_ESCAPE or (_alt_escape_key != 0 and key == _alt_escape_key)


MENU_FOCUS_HIGHLIGHT_GROUP = "menu_focus_highlight"


_FOCUS_BINDING_ATTR = "_focus_highlight_cb"


def _draw_highlight(
    widget: Widget,
    group: str,
    color: tuple[float, float, float, float],
    line_width: float,
) -> None:
    """Draw (or redraw) the focus rectangle at the widget's current geometry."""
    canvas_after = widget.canvas.after  # ty: ignore[unresolved-attribute]
    canvas_after.remove_group(group)
    with canvas_after:
        Color(*color, group=group)
        Line(
            rectangle=(widget.x, widget.y, widget.width, widget.height),
            width=line_width,
            group=group,
        )


def draw_focus_highlight(
    widget: Widget,
    group: str,
    color: tuple[float, float, float, float] = (1, 1, 0, 1),
    line_width: float = 2,
) -> None:
    """Draw a focus highlight that tracks the widget's geometry.

    The highlight redraws automatically when the widget's pos or size changes
    (e.g. after a deferred Kivy layout pass).
    """
    # Remove any previous binding before installing a new one.
    _unbind_highlight(widget)

    _draw_highlight(widget, group, color, line_width)

    def _on_geometry_change(*_args: object) -> None:
        _draw_highlight(widget, group, color, line_width)

    setattr(widget, _FOCUS_BINDING_ATTR, _on_geometry_change)
    widget.bind(pos=_on_geometry_change, size=_on_geometry_change)


def _unbind_highlight(widget: Widget) -> None:
    cb = getattr(widget, _FOCUS_BINDING_ATTR, None)
    if cb is not None:
        widget.unbind(pos=cb, size=cb)
        setattr(widget, _FOCUS_BINDING_ATTR, None)


def clear_focus_highlight(widget: Widget, group: str) -> None:
    _unbind_highlight(widget)
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

    def _setup_action_bar_nav(self, menu_buttons: list[Button], default_focus_idx: int = 0) -> None:
        self._menu_mode: bool = False
        self._default_btn_idx: int = default_focus_idx
        self._focused_btn_idx: int = default_focus_idx
        self._last_used_btn_idx: int = default_focus_idx
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

    # --- Page-turn hooks ---

    def _reading_next_page(self) -> None:
        """Turn to the next page. Override to use _handle_reader_key."""
        raise NotImplementedError

    def _reading_prev_page(self) -> None:
        """Turn to the previous page. Override to use _handle_reader_key."""
        raise NotImplementedError

    # --- Key handling ---

    def _handle_reader_key(self, key: int) -> bool:
        """Dispatch a key press to the menu handler or the reading-mode handler."""
        if self._menu_mode:
            return self._handle_menu_key(key)
        return self._handle_reading_key(key)

    def _handle_reading_key(self, key: int) -> bool:
        if key == KEY_RIGHT:
            self._reading_next_page()
        elif key == KEY_LEFT:
            self._reading_prev_page()
        elif key == KEY_UP or is_escape_key(key):
            self._enter_menu_mode()
        else:
            return False
        return True

    def _handle_menu_key(self, key: int) -> bool:
        if key == KEY_RIGHT:
            self._move_menu_focus(1)
        elif key == KEY_LEFT:
            self._move_menu_focus(-1)
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._activate_focused_button()
        elif is_escape_key(key):
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
            self._last_used_btn_idx = self._default_btn_idx

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
        self._dropdown_buttons_cache: list[Button] = []

    # --- Abstract hooks ---

    def _get_dropdown_buttons(self) -> list[Button]:
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
            if self._menu_mode:  # ty: ignore[unresolved-attribute]
                self._exit_menu_mode()  # ty: ignore[unresolved-attribute]

    # --- Key handling ---

    def _handle_menu_key(self, key: int) -> bool:
        if self._dropdown_nav_mode:
            return self._handle_dropdown_key(key)
        return super()._handle_menu_key(key)  # ty: ignore[unresolved-attribute]

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
        elif is_escape_key(key):
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
