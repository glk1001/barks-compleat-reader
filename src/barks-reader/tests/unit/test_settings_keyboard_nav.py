# ruff: noqa: SLF001

from __future__ import annotations

from typing import ClassVar
from unittest.mock import MagicMock, patch

from barks_reader.ui import settings_keyboard_nav as nav_module
from barks_reader.ui.reader_keyboard_nav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_NUMPAD_ENTER,
    KEY_UP,
)
from barks_reader.ui.settings_keyboard_nav import SettingsKeyboardNav

_IDX_2 = 2


def _make_item() -> MagicMock:
    """Return a mock SettingItem; isinstance checks are patched at the call site."""
    item = MagicMock()
    item.parent = None
    return item


def _make_nav(items: list[MagicMock]) -> SettingsKeyboardNav:
    panel = MagicMock()
    # Kivy stores children last-added-first, so reverse the display order.
    panel.children = list(reversed(items))
    settings = MagicMock()
    settings.interface.content.current_panel = panel
    return SettingsKeyboardNav(settings)


def _patch_settingitem(items: list[MagicMock]):  # noqa: ANN202
    """Patch isinstance(..., SettingItem) to treat our mocks as SettingItems."""
    real_isinstance = isinstance

    def fake_isinstance(obj: object, cls: type) -> bool:
        if cls is nav_module.SettingItem and obj in items:
            return True
        return real_isinstance(obj, cls)

    return patch.object(nav_module, "isinstance", fake_isinstance, create=True)


class TestHandleKey:
    def test_down_moves_focus_forward_and_wraps(self) -> None:
        items = [_make_item(), _make_item(), _make_item()]
        nav = _make_nav(items)

        with _patch_settingitem(items), patch.object(nav_module, "draw_focus_highlight"):
            assert nav.handle_key(KEY_DOWN) is True
            assert nav._focused_idx == 1
            assert nav.handle_key(KEY_DOWN) is True
            assert nav._focused_idx == _IDX_2
            assert nav.handle_key(KEY_DOWN) is True
            assert nav._focused_idx == 0

    def test_up_moves_focus_backward_and_wraps(self) -> None:
        items = [_make_item(), _make_item(), _make_item()]
        nav = _make_nav(items)

        with _patch_settingitem(items), patch.object(nav_module, "draw_focus_highlight"):
            assert nav.handle_key(KEY_UP) is True
            assert nav._focused_idx == _IDX_2
            assert nav.handle_key(KEY_UP) is True
            assert nav._focused_idx == 1

    def test_enter_dispatches_on_release(self) -> None:
        items = [_make_item(), _make_item()]
        nav = _make_nav(items)

        with _patch_settingitem(items), patch.object(nav_module, "draw_focus_highlight"):
            nav.handle_key(KEY_DOWN)  # focus idx 1
            assert nav.handle_key(KEY_ENTER) is True

        items[1].dispatch.assert_called_once_with("on_release")

    def test_numpad_enter_also_activates(self) -> None:
        items = [_make_item()]
        nav = _make_nav(items)

        with _patch_settingitem(items):
            assert nav.handle_key(KEY_NUMPAD_ENTER) is True

        items[0].dispatch.assert_called_once_with("on_release")

    def test_escape_returns_false(self) -> None:
        items = [_make_item()]
        nav = _make_nav(items)

        with _patch_settingitem(items):
            assert nav.handle_key(KEY_ESCAPE) is False

    def test_unknown_key_returns_false(self) -> None:
        items = [_make_item()]
        nav = _make_nav(items)

        with _patch_settingitem(items):
            assert nav.handle_key(999) is False

    def test_empty_panel_returns_false(self) -> None:
        nav = _make_nav([])
        assert nav.handle_key(KEY_DOWN) is False
        assert nav.handle_key(KEY_ENTER) is False


class TestReset:
    def test_reset_clears_focus_and_resets_index(self) -> None:
        items = [_make_item(), _make_item()]
        nav = _make_nav(items)

        with (
            _patch_settingitem(items),
            patch.object(nav_module, "draw_focus_highlight"),
            patch.object(nav_module, "clear_focus_highlight") as mock_clear,
        ):
            nav.handle_key(KEY_DOWN)  # focus idx 1
            nav.reset()

        mock_clear.assert_called_once()
        assert nav._focused_idx == 0
        assert nav._last_focused_item is None


class TestBooleanToggle:
    def test_enter_on_boolean_flips_value(self) -> None:
        bool_item = MagicMock()
        bool_item.values = ["0", "1"]
        bool_item.value = "0"
        bool_item.parent = None
        nav = _make_nav([bool_item])

        # Treat the mock as both SettingItem and SettingBoolean.
        real_isinstance = isinstance

        def fake_isinstance(obj: object, cls: type) -> bool:
            if obj is bool_item and cls in (nav_module.SettingItem, nav_module.SettingBoolean):
                return True
            return real_isinstance(obj, cls)

        with (
            patch.object(nav_module, "isinstance", fake_isinstance, create=True),
            patch.object(nav_module, "draw_focus_highlight"),
        ):
            assert nav.handle_key(KEY_ENTER) is True
            assert bool_item.value == "1"
            assert nav.handle_key(KEY_ENTER) is True
            assert bool_item.value == "0"

        # Should not have dispatched on_release for booleans.
        bool_item.dispatch.assert_not_called()


class TestPopupNavWiring:
    def test_enter_attaches_popup_nav_when_item_has_popup(self) -> None:
        item = _make_item()
        popup = MagicMock()
        popup.content.children = []  # no buttons / textinput
        item.popup = popup
        nav = _make_nav([item])

        with _patch_settingitem([item]), patch.object(nav_module, "draw_focus_highlight"):
            nav.handle_key(KEY_ENTER)

        assert nav._popup_nav is not None
        item.dispatch.assert_called_once_with("on_release")

    def test_keys_route_to_popup_nav_when_active(self) -> None:
        item = _make_item()
        popup = MagicMock()
        popup.content.children = []
        item.popup = popup
        nav = _make_nav([item])

        sentinel_handler = MagicMock(return_value=True)
        with _patch_settingitem([item]), patch.object(nav_module, "draw_focus_highlight"):
            nav.handle_key(KEY_ENTER)
            assert nav._popup_nav is not None
            object.__setattr__(nav._popup_nav, "handle_key", sentinel_handler)
            assert nav.handle_key(KEY_DOWN) is True

        sentinel_handler.assert_called_once_with(KEY_DOWN)


class TestPopupKeyboardNav:
    @staticmethod
    def _make_popup(
        buttons: list | None = None,
        textinput: object = None,
    ) -> MagicMock:
        # Kivy stores children last-added-first, so for visual order [b0, b1, ...]
        # content.children must be [..., b1, b0] (reversed).
        visual: list = list(buttons or [])
        if textinput is not None:
            visual.append(textinput)
        popup = MagicMock()
        popup.content.children = list(reversed(visual))
        return popup

    @staticmethod
    def _patch(buttons: list, textinput: object = None):  # noqa: ANN205
        real_isinstance = isinstance

        def fake_isinstance(obj: object, cls: type) -> bool:
            if cls is nav_module.Button and obj in buttons:
                return True
            if cls is nav_module.TextInput and textinput is not None and obj is textinput:
                return True
            return real_isinstance(obj, cls)

        return patch.object(nav_module, "isinstance", fake_isinstance, create=True)

    def test_down_up_moves_focus_through_buttons(self) -> None:
        b0, b1, b2 = MagicMock(state="normal"), MagicMock(state="normal"), MagicMock(state="normal")
        buttons = [b0, b1, b2]
        popup = self._make_popup(buttons=buttons)

        with self._patch(buttons), patch.object(nav_module, "draw_focus_highlight"):
            popup_nav = nav_module._PopupKeyboardNav(popup, lambda: None)
            assert popup_nav._focused_idx == 0
            assert popup_nav.handle_key(KEY_DOWN) is True
            assert popup_nav._focused_idx == 1
            assert popup_nav.handle_key(KEY_UP) is True
            assert popup_nav._focused_idx == 0

    def test_initial_focus_on_pressed_toggle(self) -> None:
        b0, b1 = MagicMock(state="normal"), MagicMock(state="down")
        buttons = [b0, b1]
        popup = self._make_popup(buttons=buttons)

        with self._patch(buttons), patch.object(nav_module, "draw_focus_highlight"):
            popup_nav = nav_module._PopupKeyboardNav(popup, lambda: None)
            assert popup_nav._focused_idx == 1

    def test_enter_dispatches_on_focused_button(self) -> None:
        b0, b1 = MagicMock(state="normal"), MagicMock(state="normal")
        buttons = [b0, b1]
        popup = self._make_popup(buttons=buttons)

        with self._patch(buttons), patch.object(nav_module, "draw_focus_highlight"):
            popup_nav = nav_module._PopupKeyboardNav(popup, lambda: None)
            popup_nav.handle_key(KEY_DOWN)
            popup_nav.handle_key(KEY_ENTER)

        b1.dispatch.assert_called_once_with("on_release")

    def test_escape_dismisses_popup(self) -> None:
        buttons = [MagicMock(state="normal")]
        popup = self._make_popup(buttons=buttons)

        with self._patch(buttons), patch.object(nav_module, "draw_focus_highlight"):
            popup_nav = nav_module._PopupKeyboardNav(popup, lambda: None)
            assert popup_nav.handle_key(27) is True

        popup.dismiss.assert_called_once()

    def test_textinput_present_focuses_and_passes_through(self) -> None:
        class _FakeInput:
            children: ClassVar[list] = []
            focus = False

        textinput = _FakeInput()
        popup = self._make_popup(textinput=textinput)

        with self._patch([], textinput=textinput):
            popup_nav = nav_module._PopupKeyboardNav(popup, lambda: None)
            assert textinput.focus is True
            # Non-escape keys pass through (return False) so TextInput handles them.
            assert popup_nav.handle_key(KEY_DOWN) is False
            assert popup_nav.handle_key(ord("a")) is False
            # Escape still dismisses.
            assert popup_nav.handle_key(27) is True

    def test_dismiss_callback_clears_state(self) -> None:
        buttons = [MagicMock(state="normal")]
        popup = self._make_popup(buttons=buttons)
        cleared = []

        with (
            self._patch(buttons),
            patch.object(nav_module, "draw_focus_highlight"),
            patch.object(nav_module, "clear_focus_highlight"),
        ):
            popup_nav = nav_module._PopupKeyboardNav(popup, lambda: cleared.append(True))
            popup_nav._handle_dismiss()

        assert cleared == [True]
