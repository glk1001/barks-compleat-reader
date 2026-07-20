from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.settings import SettingBoolean, SettingItem
from kivy.uix.textinput import TextInput

from .reader_keyboard_nav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_NUMPAD_ENTER,
    KEY_UP,
    MENU_FOCUS_HIGHLIGHT_GROUP,
    clear_focus_highlight,
    draw_focus_highlight,
    is_escape_key,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.widget import Widget


class SettingsKeyboardNav:
    """Keyboard navigation for the Kivy Settings widget.

    Up/Down cycles focus through SettingItems in the currently visible panel.
    Enter activates the focused item: toggles bool switches, otherwise opens
    its popup and attaches a popup-keyboard navigator. Escape is not handled
    here at the panel level — the caller closes the settings screen.
    """

    def __init__(self, settings: Widget) -> None:
        self._settings = settings
        self._focused_idx: int = 0
        self._last_focused_item: SettingItem | None = None
        self._popup_nav: _PopupKeyboardNav | None = None

    def handle_key(self, key: int) -> bool:  # noqa: PLR0911
        """Return True if the key was consumed by settings navigation."""
        if self._popup_nav is not None:
            return self._popup_nav.handle_key(key)

        if is_escape_key(key):
            return False

        items = self._get_current_panel_items()
        if not items:
            return False

        if key == KEY_UP:
            self._focused_idx = (self._focused_idx - 1) % len(items)
            self._apply_focus(items)
            return True
        if key == KEY_DOWN:
            self._focused_idx = (self._focused_idx + 1) % len(items)
            self._apply_focus(items)
            return True
        if key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            idx = min(self._focused_idx, len(items) - 1)
            self._activate_item(items[idx])
            return True
        return False

    def reset(self) -> None:
        """Clear focus highlight and reset internal state."""
        if self._last_focused_item is not None:
            clear_focus_highlight(self._last_focused_item, MENU_FOCUS_HIGHLIGHT_GROUP)
            self._last_focused_item = None
        self._focused_idx = 0
        self._popup_nav = None

    def _activate_item(self, item: SettingItem) -> None:
        if isinstance(item, SettingBoolean):
            _toggle_boolean(item)
            return
        item.dispatch("on_release")
        popup = getattr(item, "popup", None)
        if popup is not None:
            self._popup_nav = _PopupKeyboardNav(popup, self._clear_popup_nav)

    def _clear_popup_nav(self) -> None:
        self._popup_nav = None

    def _apply_focus(self, items: list[SettingItem]) -> None:
        idx = min(self._focused_idx, len(items) - 1)
        item = items[idx]
        if self._last_focused_item is not None and self._last_focused_item is not item:
            clear_focus_highlight(self._last_focused_item, MENU_FOCUS_HIGHLIGHT_GROUP)
        draw_focus_highlight(item, MENU_FOCUS_HIGHLIGHT_GROUP)
        self._last_focused_item = item
        self._scroll_to_item(item)

    def _get_current_panel_items(self) -> list[SettingItem]:
        panel = self._find_current_panel()
        if panel is None:
            return []
        # Kivy children are stored last-added-first; reverse for visual top-to-bottom order.
        return [c for c in reversed(panel.children) if isinstance(c, SettingItem)]

    def _find_current_panel(self) -> Widget | None:
        interface = getattr(self._settings, "interface", None)
        if interface is None:
            return None
        # InterfaceWithSpinner/Sidebar wrap a ContentPanel in `.content`;
        # InterfaceWithNoMenu *is* the ContentPanel, so fall back to itself.
        content = getattr(interface, "content", None) or interface
        current = getattr(content, "current_panel", None)
        if current is not None:
            return current
        for child in content.children:
            if any(isinstance(c, SettingItem) for c in getattr(child, "children", [])):
                return child
        return None

    @staticmethod
    def _scroll_to_item(item: Widget) -> None:
        parent = item.parent
        while parent is not None and not isinstance(parent, ScrollView):
            parent = parent.parent
        if parent is not None:
            parent.scroll_to(item)


def _toggle_boolean(item: SettingItem) -> None:
    values = list(getattr(item, "values", []))
    if len(values) < 2:  # noqa: PLR2004
        return
    item.value = values[0] if item.value == values[1] else values[1]


class _PopupKeyboardNav:
    """Keyboard navigation for a settings popup (options list or numeric/string input)."""

    def __init__(self, popup: Widget, on_dismissed: Callable[[], None]) -> None:
        self._popup = popup
        self._on_dismissed = on_dismissed
        content = getattr(popup, "content", None)
        self._buttons: list[Button] = _collect_buttons(content) if content is not None else []
        self._textinput: Widget | None = (
            _find_first(content, TextInput) if content is not None else None
        )
        self._focused_idx: int = self._initial_focus_idx()
        self._last_focused: Widget | None = None

        if self._textinput is not None:
            self._textinput.focus = True
        elif self._buttons:
            self._apply_focus()

        popup.bind(on_dismiss=self._handle_dismiss)

    def handle_key(self, key: int) -> bool:  # noqa: PLR0911
        if is_escape_key(key):
            self._popup.dismiss()
            return True
        if self._textinput is not None and getattr(self._textinput, "focus", False):
            return False
        if not self._buttons:
            return False
        if key == KEY_UP:
            self._focused_idx = (self._focused_idx - 1) % len(self._buttons)
            self._apply_focus()
            return True
        if key == KEY_DOWN:
            self._focused_idx = (self._focused_idx + 1) % len(self._buttons)
            self._apply_focus()
            return True
        if key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._buttons[self._focused_idx].dispatch("on_release")
            return True
        return False

    def _handle_dismiss(self, *_args: object) -> None:
        if self._last_focused is not None:
            clear_focus_highlight(self._last_focused, MENU_FOCUS_HIGHLIGHT_GROUP)
            self._last_focused = None
        self._on_dismissed()

    def _initial_focus_idx(self) -> int:
        for i, btn in enumerate(self._buttons):
            if getattr(btn, "state", None) == "down":
                return i
        return 0

    def _apply_focus(self) -> None:
        idx = min(self._focused_idx, len(self._buttons) - 1)
        btn = self._buttons[idx]
        if self._last_focused is not None and self._last_focused is not btn:
            clear_focus_highlight(self._last_focused, MENU_FOCUS_HIGHLIGHT_GROUP)
        draw_focus_highlight(btn, MENU_FOCUS_HIGHLIGHT_GROUP)
        self._last_focused = btn


def _collect_buttons(root: Widget) -> list[Button]:
    result: list[Button] = []
    _walk_buttons(root, result)
    return result


def _walk_buttons(widget: Widget, out: list[Button]) -> None:
    for child in reversed(getattr(widget, "children", [])):
        if isinstance(child, Button):
            out.append(child)
        else:
            _walk_buttons(child, out)


def _find_first(widget: Widget, cls: type) -> Widget | None:
    for child in reversed(getattr(widget, "children", [])):
        if isinstance(child, cls):
            return child
        found = _find_first(child, cls)
        if found is not None:
            return found
    return None
