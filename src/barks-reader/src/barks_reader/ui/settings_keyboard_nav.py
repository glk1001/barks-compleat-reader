from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.uix.scrollview import ScrollView
from kivy.uix.settings import SettingBoolean, SettingItem

from barks_reader.core.keys import KEY_DOWN, KEY_ENTER, KEY_NUMPAD_ENTER, KEY_UP, is_escape_key

from .reader_keyboard_nav import (
    MENU_FOCUS_HIGHLIGHT_GROUP,
    clear_focus_highlight,
    draw_focus_highlight,
)

if TYPE_CHECKING:
    from kivy.uix.widget import Widget


class SettingsKeyboardNav:
    """Keyboard navigation for the Kivy Settings widget.

    Up/Down move focus through the SettingItems in the currently visible panel, and
    stop at its ends.
    Enter activates the focused item: toggles bool switches, otherwise opens
    its popup, which is on the shared frame (``ui.popup_frame``) and takes its own
    keys while it is open. Escape is not handled here at the panel level — the
    caller closes the settings screen.
    """

    def __init__(self, settings: Widget) -> None:
        self._settings = settings
        self._focused_idx: int = 0
        self._last_focused_item: SettingItem | None = None

    def handle_key(self, key: int) -> bool:
        """Return True if the key was consumed by settings navigation."""
        if is_escape_key(key):
            return False

        items = self._get_current_panel_items()
        if not items:
            return False

        # A list stops at its ends, as the app's other lists do: wrapped, Down past the
        # last item lost the reader's place at the top.
        if key == KEY_UP:
            self._focused_idx = max(0, self._focused_idx - 1)
            self._apply_focus(items)
            return True
        if key == KEY_DOWN:
            self._focused_idx = min(len(items) - 1, self._focused_idx + 1)
            self._apply_focus(items)
            return True
        if key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            idx = min(self._focused_idx, len(items) - 1)
            self._activate_item(items[idx])
            return True
        return False

    def focus_first(self) -> None:
        """Show the focus on the first item, where the keys start from.

        Without it the first item is focused invisibly: Enter would act on it unseen, and
        the first Down would land on the second item.
        """
        items = self._get_current_panel_items()
        if not items:
            return
        self._focused_idx = 0
        self._apply_focus(items)

    def blur(self) -> None:
        """Take the ring off the focused item, keeping which one it is (the X has it)."""
        if self._last_focused_item is not None:
            clear_focus_highlight(self._last_focused_item, MENU_FOCUS_HIGHLIGHT_GROUP)
            self._last_focused_item = None

    def refocus(self) -> None:
        """Put the ring back on the focused item (the X gave it back)."""
        items = self._get_current_panel_items()
        if items:
            self._apply_focus(items)

    def reset(self) -> None:
        """Clear focus highlight and reset internal state."""
        if self._last_focused_item is not None:
            clear_focus_highlight(self._last_focused_item, MENU_FOCUS_HIGHLIGHT_GROUP)
            self._last_focused_item = None
        self._focused_idx = 0

    def _activate_item(self, item: SettingItem) -> None:
        if isinstance(item, SettingBoolean):
            _toggle_boolean(item)
            return
        item.dispatch("on_release")

    def _apply_focus(self, items: list[SettingItem]) -> None:
        idx = min(self._focused_idx, len(items) - 1)
        item = items[idx]
        if self._last_focused_item is not None and self._last_focused_item is not item:
            clear_focus_highlight(self._last_focused_item, MENU_FOCUS_HIGHLIGHT_GROUP)
        draw_focus_highlight(item, MENU_FOCUS_HIGHLIGHT_GROUP)
        self._last_focused_item = item
        if idx == 0:
            # The first item means the panel's top, its section heading too: a
            # scroll to the item alone left the heading above the view (the panel
            # keeps its scroll between openings, and Up walks back to the first
            # item). A jump, not a scroll to the item: that animation would write
            # over it frame by frame.
            self._scroll_to_top(item)
        else:
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
        # Kivy's menu interfaces and PinnedTitleSettingsInterface hold the ContentPanel
        # in `.content`; a bare ContentPanel used as the interface is itself.
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
        scroll_view = _scroll_view_of(item)
        if scroll_view is not None:
            scroll_view.scroll_to(item)

    @staticmethod
    def _scroll_to_top(item: Widget) -> None:
        scroll_view = _scroll_view_of(item)
        if scroll_view is not None:
            scroll_view.scroll_y = 1.0


def _scroll_view_of(item: Widget) -> ScrollView | None:
    """Return the scroll view `item` sits in, or None."""
    parent = item.parent
    while parent is not None and not isinstance(parent, ScrollView):
        parent = parent.parent
    return parent


def _toggle_boolean(item: SettingItem) -> None:
    values = list(getattr(item, "values", []))
    if len(values) < 2:  # noqa: PLR2004
        return
    item.value = values[0] if item.value == values[1] else values[1]
